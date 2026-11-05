#!/usr/bin/env python3
"""Database initialization and seeding utility (Exercise 2.5.1).

One command recreates the complaint training database:

    python3 seed_database.py --create-db --reset

Stages
  1. Initialize  run the DDL section of 2_1_1_schema/database_schema.sql in
                 dependency order. Existing tables are only dropped with --reset.
  2. Validate    check required headers, duplicate keys, required values and
                 foreign keys before insert (seed_validation_rules.md).
  3. Load        insert employees, customers, accounts, complaints and service
                 requests. Invalid rows are rejected with a reason.
  4. Verify      compare source/inserted counts and run orphan checks, then
                 write integrity_report.txt.

Everything runs in ONE transaction (PostgreSQL DDL is transactional). If a
critical check fails (missing header, missing file, integrity failure, or any
rejected row under --strict) the whole run is rolled back and the database is
left exactly as it was before the command started.
"""

import argparse
import csv
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
DEFAULT_SCHEMA = REPO_ROOT / "2_1_1_schema" / "database_schema.sql"
DEFAULT_DATA_DIR = HERE / "data"
DEFAULT_LOG = HERE / "seed_run_log.txt"
DEFAULT_REPORT = HERE / "integrity_report.txt"
REQUIRED_SETTINGS = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]

log = logging.getLogger("seed_database")


# ---------------------------------------------------------------------------
# Seed specification: load order, required headers, keys and foreign keys.
# Load order is the FK dependency order: parents before children.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ForeignKey:
    columns: tuple          # columns in this file
    parent: str             # parent table
    nullable: bool = False  # True when the FK may be empty (e.g. optional account)


@dataclass(frozen=True)
class TableSpec:
    table: str
    csv_file: str
    columns: tuple          # required headers, in insert order
    key: str
    not_null: tuple
    foreign_keys: tuple = ()


SEED_SPECS = (
    TableSpec("employee", "employees.csv",
              ("employee_id", "first_name", "last_name", "email", "role"),
              "employee_id", ("employee_id", "first_name", "last_name", "email", "role")),
    TableSpec("customer", "customers.csv",
              ("customer_id", "first_name", "last_name", "email", "phone_number", "segment"),
              "customer_id", ("customer_id", "first_name", "last_name", "segment")),
    TableSpec("account", "accounts.csv",
              ("account_id", "customer_id", "account_number", "account_type", "status", "balance", "open_date"),
              "account_id", ("account_id", "customer_id", "account_number", "account_type", "status", "balance", "open_date"),
              (ForeignKey(("customer_id",), "customer"),)),
    TableSpec("complaint", "complaints.csv",
              ("complaint_id", "customer_id", "account_id", "channel", "category", "customer_narrative",
               "priority", "status", "created_at", "assigned_employee_id"),
              "complaint_id", ("complaint_id", "customer_id", "channel", "category", "customer_narrative",
                               "priority", "status", "created_at"),
              (ForeignKey(("customer_id",), "customer"),
               ForeignKey(("account_id", "customer_id"), "account", nullable=True),
               ForeignKey(("assigned_employee_id",), "employee", nullable=True))),
    TableSpec("service_request", "service_requests.csv",
              ("request_id", "customer_id", "account_id", "request_type", "status", "created_date", "closed_date"),
              "request_id", ("request_id", "customer_id", "request_type", "status", "created_date"),
              (ForeignKey(("customer_id",), "customer"),
               ForeignKey(("account_id", "customer_id"), "account", nullable=True))),
)


class SeedError(Exception):
    """Critical failure: the run is rolled back."""


@dataclass
class TableResult:
    table: str
    source_rows: int = 0
    inserted: int = 0
    rejected: list = field(default_factory=list)  # (line_no, key, reason)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
def load_dotenv(path):
    """Minimal .env loader. Never overrides variables already set in the shell."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def db_settings(dbname_override=None):
    missing = [n for n in REQUIRED_SETTINGS if not os.environ.get(n)]
    if dbname_override:
        missing = [n for n in missing if n != "DB_NAME"]
    if missing:
        raise SeedError(f"Missing environment variable(s): {', '.join(missing)}")
    return {
        "host": os.environ["DB_HOST"],
        "port": int(os.environ["DB_PORT"]),
        "dbname": dbname_override or os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
    }


# ---------------------------------------------------------------------------
# Stage 1: initialization
# ---------------------------------------------------------------------------
def read_schema_statements(schema_path):
    """Return the DDL statements from database_schema.sql (seed INSERTs excluded).

    The 2.1.1 file is the source of truth for the schema. Its first
    BEGIN ... COMMIT block is the DDL; the seed data that follows is replaced by
    the CSV load in this utility.
    """
    if not schema_path.is_file():
        raise SeedError(f"Schema file not found: {schema_path}")
    text = schema_path.read_text(encoding="utf-8")
    match = re.search(r"^\s*COMMIT\s*;", text, re.MULTILINE | re.IGNORECASE)
    ddl = text[: match.start()] if match else text
    ddl = "\n".join(l for l in ddl.splitlines() if not l.strip().startswith("--"))
    statements = [s.strip() for s in ddl.split(";") if s.strip()]
    statements = [s for s in statements if s.upper() not in ("BEGIN", "COMMIT")]
    if not any(s.upper().startswith("CREATE TABLE") for s in statements):
        raise SeedError(f"No CREATE TABLE statements found in {schema_path}")
    return statements


def schema_tables(statements):
    return [re.match(r"CREATE TABLE\s+(\w+)", s, re.I).group(1)
            for s in statements if re.match(r"CREATE TABLE", s, re.I)]


def existing_tables(cur, tables):
    cur.execute("SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = ANY(%s) ORDER BY table_name",
                (list(tables),))
    return [r[0] for r in cur.fetchall()]


def initialize_schema(cur, statements, reset):
    tables = schema_tables(statements)
    found = existing_tables(cur, tables)
    if found and not reset:
        raise SeedError(
            f"{len(found)} schema table(s) already exist ({', '.join(found[:5])}"
            f"{', ...' if len(found) > 5 else ''}). Nothing was changed. "
            "Re-run with --reset to drop and recreate them (this deletes their data).")
    drops = [s for s in statements if s.upper().startswith("DROP")]
    creates = [s for s in statements if not s.upper().startswith("DROP")]
    if found:
        log.info("STAGE init: --reset given, dropping %d table(s) in reverse dependency order", len(drops))
        for stmt in drops:
            cur.execute(stmt)
    else:
        log.info("STAGE init: database is empty, no reset needed")
    created = indexes = 0
    for stmt in creates:
        cur.execute(stmt)
        name = re.match(r"CREATE (?:UNIQUE )?(TABLE|INDEX)\s+(\w+)", stmt, re.I)
        if name and name.group(1).upper() == "TABLE":
            created += 1
            log.info("STAGE init: created table %-26s (%d/%d)", name.group(2), created, len(tables))
        elif name:
            indexes += 1
    log.info("STAGE init: complete - %d tables, %d indexes", created, indexes)


# ---------------------------------------------------------------------------
# Stage 2 + 3: validate and load
# ---------------------------------------------------------------------------
def read_csv(path, spec):
    """Read a seed CSV. Missing file or missing required headers are critical."""
    if not path.is_file():
        raise SeedError(f"{spec.table}: source file not found: {path}")
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = [h.strip() for h in (reader.fieldnames or [])]
        missing = [c for c in spec.columns if c not in headers]
        if missing:
            raise SeedError(f"{spec.table}: {path.name} is missing required header(s): {', '.join(missing)}")
        reader.fieldnames = headers
        rows = []
        for line_no, raw in enumerate(reader, start=2):
            row = {c: (raw.get(c) or "").strip() or None for c in spec.columns}
            rows.append((line_no, row))
    return rows


def validate_row(spec, row, accepted, seen_keys):
    """Return a rejection reason, or None if the row may be inserted.

    `accepted` holds the keys already inserted for parent tables, so a child row
    whose parent was rejected is rejected too (FKs must resolve before commit).
    """
    key = row.get(spec.key)
    for col in spec.not_null:
        if row.get(col) is None:
            return f"required value '{col}' is empty"
    if key in seen_keys:
        return f"duplicate {spec.key} '{key}' in source file"
    for fk in spec.foreign_keys:
        values = tuple(row.get(c) for c in fk.columns)
        if fk.nullable and values[0] is None:
            continue  # optional link (e.g. general complaint with no account)
        if fk.parent == "account":
            account_id, customer_id = values
            owner = accepted["account"].get(account_id)
            if owner is None:
                return f"account_id '{account_id}' does not exist in accounts"
            if owner != customer_id:
                return (f"account_id '{account_id}' belongs to customer '{owner}', "
                        f"not to customer '{customer_id}'")
        elif values[0] not in accepted[fk.parent]:
            return f"{fk.columns[0]} '{values[0]}' does not exist in {fk.parent}"
    return None


def load_table(cur, spec, rows, accepted):
    result = TableResult(spec.table, source_rows=len(rows))
    seen = set()
    cols = ", ".join(spec.columns)
    placeholders = ", ".join(["%s"] * len(spec.columns))
    sql = f"INSERT INTO {spec.table} ({cols}) VALUES ({placeholders})"
    for line_no, row in rows:
        key = row.get(spec.key) or "<blank>"
        reason = validate_row(spec, row, accepted, seen)
        if reason is None:
            # Savepoint per row: a CHECK/type violation rejects this row only.
            cur.execute("SAVEPOINT seed_row")
            try:
                cur.execute(sql, [row[c] for c in spec.columns])
                cur.execute("RELEASE SAVEPOINT seed_row")
            except Exception as exc:  # psycopg2.Error, reported as the reason
                cur.execute("ROLLBACK TO SAVEPOINT seed_row")
                reason = "database rejected row: " + str(exc).strip().splitlines()[0]
        if reason:
            result.rejected.append((line_no, key, reason))
            log.warning("REJECT %s line %d (%s): %s", spec.csv_file, line_no, key, reason)
            continue
        seen.add(row[spec.key])
        result.inserted += 1
        if spec.table == "account":
            accepted["account"][row["account_id"]] = row["customer_id"]
        else:
            accepted[spec.table].add(row[spec.key])
    log.info("STAGE load: %-16s source=%-3d inserted=%-3d rejected=%d",
             spec.table, result.source_rows, result.inserted, len(result.rejected))
    return result


def validate_and_load(cur, data_dir):
    # Read and header-check every file first, so a bad header aborts before any insert.
    sources = {}
    for spec in SEED_SPECS:
        sources[spec.table] = read_csv(data_dir / spec.csv_file, spec)
        log.info("STAGE validate: %-20s headers OK, %d data row(s)", spec.csv_file, len(sources[spec.table]))
    accepted = {spec.table: set() for spec in SEED_SPECS}
    accepted["account"] = {}  # account_id -> owning customer_id
    return [load_table(cur, spec, sources[spec.table], accepted) for spec in SEED_SPECS]


# ---------------------------------------------------------------------------
# Stage 4: verify integrity
# ---------------------------------------------------------------------------
ORPHAN_CHECKS = (
    ("account -> customer",
     "SELECT a.account_id FROM account a LEFT JOIN customer c ON c.customer_id = a.customer_id "
     "WHERE c.customer_id IS NULL"),
    ("complaint -> customer",
     "SELECT x.complaint_id FROM complaint x LEFT JOIN customer c ON c.customer_id = x.customer_id "
     "WHERE c.customer_id IS NULL"),
    ("complaint -> account (when present)",
     "SELECT x.complaint_id FROM complaint x LEFT JOIN account a ON a.account_id = x.account_id "
     "WHERE x.account_id IS NOT NULL AND a.account_id IS NULL"),
    ("complaint account belongs to complaint customer",
     "SELECT x.complaint_id FROM complaint x JOIN account a ON a.account_id = x.account_id "
     "WHERE a.customer_id <> x.customer_id"),
    ("complaint -> assigned employee (when present)",
     "SELECT x.complaint_id FROM complaint x LEFT JOIN employee e ON e.employee_id = x.assigned_employee_id "
     "WHERE x.assigned_employee_id IS NOT NULL AND e.employee_id IS NULL"),
    ("service_request -> customer",
     "SELECT s.request_id FROM service_request s LEFT JOIN customer c ON c.customer_id = s.customer_id "
     "WHERE c.customer_id IS NULL"),
    ("service_request -> account (when present)",
     "SELECT s.request_id FROM service_request s LEFT JOIN account a ON a.account_id = s.account_id "
     "WHERE s.account_id IS NOT NULL AND a.account_id IS NULL"),
    ("service_request account belongs to request customer",
     "SELECT s.request_id FROM service_request s JOIN account a ON a.account_id = s.account_id "
     "WHERE a.customer_id <> s.customer_id"),
)


def verify_integrity(cur, results):
    """Return (report_lines, failures). Any failure is critical."""
    failures = []
    lines = ["ROW COUNTS (source vs inserted vs database)", "-" * 78,
             f"{'table':<18}{'source':>8}{'inserted':>10}{'rejected':>10}{'in_db':>8}  result"]
    for r in results:
        cur.execute(f"SELECT COUNT(*) FROM {r.table}")
        in_db = cur.fetchone()[0]
        ok = (r.inserted + len(r.rejected) == r.source_rows) and in_db == r.inserted
        if not ok:
            failures.append(f"count mismatch for {r.table}")
        lines.append(f"{r.table:<18}{r.source_rows:>8}{r.inserted:>10}{len(r.rejected):>10}{in_db:>8}  "
                     f"{'PASS' if ok else 'FAIL'}")
    lines += ["", "ORPHAN / CONSISTENCY CHECKS (expected 0 rows each)", "-" * 78]
    for name, sql in ORPHAN_CHECKS:
        cur.execute(sql)
        bad = [row[0] for row in cur.fetchall()]
        if bad:
            failures.append(f"{name}: {', '.join(bad)}")
        lines.append(f"{name:<55}{len(bad):>4}  {'PASS' if not bad else 'FAIL ' + ', '.join(bad)}")
        log.info("STAGE verify: %-52s %s", name, "PASS" if not bad else "FAIL")

    cur.execute("SELECT COUNT(*) FROM complaint WHERE account_id IS NULL")
    general = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM service_request WHERE account_id IS NULL")
    sr_general = cur.fetchone()[0]
    lines += ["", "OPTIONAL ACCOUNT LINKS (valid by design, not orphans)", "-" * 78,
              f"complaints with no account_id (general / identity / fraud): {general}",
              f"service requests with no account_id:                        {sr_general}"]

    rejected = [(r.table, *rej) for r in results for rej in r.rejected]
    lines += ["", "REJECTED ROWS", "-" * 78]
    lines += [f"{t}: line {n} ({k}) - {why}" for t, n, k, why in rejected] or ["none"]
    return lines, failures


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def ensure_database(settings):
    import psycopg2
    from psycopg2 import sql
    admin = dict(settings, dbname="postgres")
    conn = psycopg2.connect(**admin, connect_timeout=5)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings["dbname"],))
            if cur.fetchone():
                log.info("STAGE connect: database '%s' already exists", settings["dbname"])
            else:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings["dbname"])))
                log.info("STAGE connect: created database '%s'", settings["dbname"])
    finally:
        conn.close()


def write_report(path, settings, args, body, status):
    header = [
        "INTEGRITY REPORT - Exercise 2.5.1 Database Seeder",
        "=" * 78,
        f"generated : {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"database  : {settings['user']}@{settings['host']}:{settings['port']}/{settings['dbname']}",
        f"data dir  : {args.data_dir}",
        f"mode      : reset={args.reset} strict={args.strict}",
        f"result    : {status}",
        "",
    ]
    path.write_text("\n".join(header + body) + "\n", encoding="utf-8")


def run(args):
    import psycopg2

    settings = db_settings(args.dbname)
    log.info("=" * 70)
    log.info("RUN START %s  db=%s@%s:%s/%s  reset=%s strict=%s  data=%s",
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"), settings["user"], settings["host"],
             settings["port"], settings["dbname"], args.reset, args.strict, args.data_dir)
    statements = read_schema_statements(args.schema)
    log.info("STAGE init: read %d DDL statement(s) from %s", len(statements), args.schema.name)

    if args.create_db:
        ensure_database(settings)
    try:
        conn = psycopg2.connect(**settings, connect_timeout=5)
    except psycopg2.OperationalError as exc:
        raise SeedError(f"Cannot connect to {settings['host']}:{settings['port']}/{settings['dbname']}: "
                        f"{str(exc).strip().splitlines()[0]}")
    log.info("STAGE connect: connected; opening a single transaction")
    try:
        with conn.cursor() as cur:
            initialize_schema(cur, statements, args.reset)
            results = validate_and_load(cur, args.data_dir)
            body, failures = verify_integrity(cur, results)
            rejected = sum(len(r.rejected) for r in results)
            if args.strict and rejected:
                failures.append(f"--strict: {rejected} row(s) rejected")
            if failures:
                for f in failures:
                    log.error("CRITICAL: %s", f)
                conn.rollback()
                status = "FAILED - transaction rolled back, database unchanged"
                write_report(args.report, settings, args, body + ["", "FAILURES"] + failures, status)
                log.error("ROLLBACK: %s", status)
                return 1
            conn.commit()
            status = "PASSED - committed" + (f" ({rejected} row(s) rejected, see below)" if rejected else "")
            write_report(args.report, settings, args, body, status)
            log.info("COMMIT: %s", status)
            log.info("Report written to %s", args.report)
            return 0
    except Exception:
        conn.rollback()
        log.error("ROLLBACK: transaction rolled back, database unchanged")
        raise
    finally:
        conn.close()


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Initialize and seed the complaint training database.")
    p.add_argument("--reset", action="store_true",
                   help="drop and recreate existing schema tables (DELETES their data)")
    p.add_argument("--create-db", action="store_true", help="create the database first if it does not exist")
    p.add_argument("--strict", action="store_true", help="roll back the whole run if any row is rejected")
    p.add_argument("--dbname", help="database name (overrides DB_NAME)")
    p.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="folder holding the seed CSV files")
    p.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA, help="schema SQL file (2.1.1)")
    p.add_argument("--log", type=Path, default=DEFAULT_LOG, help="run log file (appended)")
    p.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="integrity report file (overwritten)")
    return p.parse_args(argv)


def setup_logging(log_path):
    for handler in list(log.handlers):
        handler.close()
        log.removeHandler(handler)
    log.setLevel(logging.INFO)
    log.propagate = False
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
    for handler in (logging.StreamHandler(sys.stdout), logging.FileHandler(log_path, encoding="utf-8")):
        handler.setFormatter(fmt)
        log.addHandler(handler)


def main(argv=None):
    args = parse_args(argv)
    for env in (Path.cwd() / ".env", REPO_ROOT / ".env"):
        load_dotenv(env)
    setup_logging(args.log)
    try:
        code = run(args)
    except SeedError as exc:
        log.error("CRITICAL: %s", exc)
        log.error("RUN END: failed, no changes committed")
        return 2
    except Exception as exc:
        log.error("UNEXPECTED ERROR: %s: %s", type(exc).__name__, str(exc).strip().splitlines()[0])
        log.error("RUN END: failed, no changes committed")
        return 3
    log.info("RUN END: %s", "success" if code == 0 else "failed, no changes committed")
    return code


if __name__ == "__main__":
    sys.exit(main())
