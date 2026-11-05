"""Database initialization and seeding utility - Week 2, Exercise 2.5.1.

One command recreates the complaint training database:

    python3 seed_database.py --create-db --reset

What it does, in this order:
  1. Initialize  create the tables from 2_1_1_schema/database_schema.sql
                 (existing tables are only dropped when you add --reset)
  2. Validate    check every CSV file has the required headers
  3. Load        insert employees, customers, accounts, complaints and service requests.
                 Rows that break a rule are rejected with a reason.
  4. Verify      compare counts and look for orphan rows, then write integrity_report.txt

Everything happens in ONE transaction. If something critical fails, the whole
run is rolled back and the database is left exactly as it was.
"""

import argparse
import csv
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import psycopg2
from psycopg2 import sql

HERE = Path(__file__).parent
REPO_ROOT = HERE.parent
SCHEMA_FILE = REPO_ROOT / "2_1_1_schema" / "database_schema.sql"
REQUIRED_SETTINGS = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]

# The tables to load, in foreign-key order: parents before children.
TABLES = [
    {"table": "employee", "file": "employees.csv", "key": "employee_id",
     "columns": ["employee_id", "first_name", "last_name", "email", "role"],
     "required": ["employee_id", "first_name", "last_name", "email", "role"]},
    {"table": "customer", "file": "customers.csv", "key": "customer_id",
     "columns": ["customer_id", "first_name", "last_name", "email", "phone_number", "segment"],
     "required": ["customer_id", "first_name", "last_name", "segment"]},
    {"table": "account", "file": "accounts.csv", "key": "account_id",
     "columns": ["account_id", "customer_id", "account_number", "account_type", "status", "balance", "open_date"],
     "required": ["account_id", "customer_id", "account_number", "account_type", "status", "balance", "open_date"]},
    {"table": "complaint", "file": "complaints.csv", "key": "complaint_id",
     "columns": ["complaint_id", "customer_id", "account_id", "channel", "category", "customer_narrative",
                 "priority", "status", "created_at", "assigned_employee_id"],
     "required": ["complaint_id", "customer_id", "channel", "category", "customer_narrative",
                  "priority", "status", "created_at"]},
    {"table": "service_request", "file": "service_requests.csv", "key": "request_id",
     "columns": ["request_id", "customer_id", "account_id", "request_type", "status", "created_date", "closed_date"],
     "required": ["request_id", "customer_id", "request_type", "status", "created_date"]},
]

# Each check should find 0 rows. Any row found is an orphan or a broken link.
ORPHAN_CHECKS = [
    ("account -> customer",
     "SELECT a.account_id FROM account a LEFT JOIN customer c ON a.customer_id = c.customer_id "
     "WHERE c.customer_id IS NULL"),
    ("complaint -> customer",
     "SELECT x.complaint_id FROM complaint x LEFT JOIN customer c ON x.customer_id = c.customer_id "
     "WHERE c.customer_id IS NULL"),
    ("complaint -> account (when present)",
     "SELECT x.complaint_id FROM complaint x LEFT JOIN account a ON x.account_id = a.account_id "
     "WHERE x.account_id IS NOT NULL AND a.account_id IS NULL"),
    ("complaint account belongs to complaint customer",
     "SELECT x.complaint_id FROM complaint x JOIN account a ON x.account_id = a.account_id "
     "WHERE a.customer_id <> x.customer_id"),
    ("complaint -> assigned employee (when present)",
     "SELECT x.complaint_id FROM complaint x LEFT JOIN employee e ON x.assigned_employee_id = e.employee_id "
     "WHERE x.assigned_employee_id IS NOT NULL AND e.employee_id IS NULL"),
    ("service_request -> customer",
     "SELECT s.request_id FROM service_request s LEFT JOIN customer c ON s.customer_id = c.customer_id "
     "WHERE c.customer_id IS NULL"),
    ("service_request -> account (when present)",
     "SELECT s.request_id FROM service_request s LEFT JOIN account a ON s.account_id = a.account_id "
     "WHERE s.account_id IS NOT NULL AND a.account_id IS NULL"),
    ("service_request account belongs to request customer",
     "SELECT s.request_id FROM service_request s JOIN account a ON s.account_id = a.account_id "
     "WHERE a.customer_id <> s.customer_id"),
]


class SeedError(Exception):
    """A critical problem. The run stops and nothing is saved."""


# ---------- Logging: print to the screen and add to the log file ----------

LOG_FILE = HERE / "seed_run_log.txt"


def log(message):
    line = f"{datetime.now():%H:%M:%S} {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ---------- Settings ----------

def load_dotenv(path):
    """Read KEY=value lines from a .env file. Variables already set in the shell win."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


def db_settings(dbname=None):
    missing = [name for name in REQUIRED_SETTINGS if not os.environ.get(name)]
    if dbname:
        missing = [name for name in missing if name != "DB_NAME"]
    if missing:
        raise SeedError(f"Missing environment variable(s): {', '.join(missing)}")
    return {
        "host": os.environ["DB_HOST"],
        "port": int(os.environ["DB_PORT"]),
        "dbname": dbname or os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
    }


def create_database_if_missing(settings):
    connection = psycopg2.connect(**dict(settings, dbname="postgres"), connect_timeout=5)
    connection.autocommit = True     # CREATE DATABASE cannot run inside a transaction
    with connection.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (settings["dbname"],))
        if cur.fetchone():
            log(f"STAGE connect: database '{settings['dbname']}' already exists")
        else:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(settings["dbname"])))
            log(f"STAGE connect: created database '{settings['dbname']}'")
    connection.close()


# ---------- Stage 1: initialize ----------

def read_schema(schema_file=SCHEMA_FILE):
    """Return the table-creation part of database_schema.sql (the first BEGIN ... COMMIT block).

    The INSERTs after it are the old 2.1.1 sample data, which the CSV files replace.
    """
    if not schema_file.is_file():
        raise SeedError(f"Schema file not found: {schema_file}")
    text = schema_file.read_text(encoding="utf-8")
    ddl = text.split("\nCOMMIT;")[0].replace("BEGIN;", "", 1)
    tables = re.findall(r"CREATE TABLE (\w+)", ddl)
    if not tables:
        raise SeedError(f"No CREATE TABLE statements found in {schema_file}")
    return ddl, tables


def initialize(cur, reset):
    ddl, tables = read_schema()
    cur.execute("SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = ANY(%s)", (tables,))
    existing = cur.fetchone()[0]

    # Safety stop: never wipe existing tables unless --reset was given.
    if existing and not reset:
        raise SeedError(f"{existing} schema table(s) already exist. Nothing was changed. "
                        "Re-run with --reset to drop and recreate them (this deletes their data).")
    if existing:
        log(f"STAGE init: --reset given, dropping and recreating {existing} existing table(s)")

    cur.execute(ddl)     # the schema file drops (IF EXISTS) and creates every table in dependency order
    log(f"STAGE init: created {len(tables)} tables: {', '.join(tables)}")


# ---------- Stage 2: validate headers ----------

def read_csv(path, spec):
    """Read one seed file. A missing file or missing header is critical.

    Returns a list of (line_number, row). Empty cells become None (NULL in the database).
    """
    if not path.is_file():
        raise SeedError(f"{spec['table']}: source file not found: {path}")
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = [h.strip() for h in (reader.fieldnames or [])]
        missing = [c for c in spec["columns"] if c not in headers]
        if missing:
            raise SeedError(f"{spec['table']}: {path.name} is missing required header(s): {', '.join(missing)}")
        reader.fieldnames = headers
        rows = []
        for line_number, raw in enumerate(reader, start=2):     # line 1 is the header
            row = {c: (raw.get(c) or "").strip() or None for c in spec["columns"]}
            rows.append((line_number, row))
    return rows


# ---------- Stage 3: check and load rows ----------

def check_row(table, row, required, seen_keys, key, loaded):
    """Return why the row must be rejected, or None if it is OK to insert.

    `loaded` holds the IDs already inserted, so a row whose parent was rejected is rejected too.
    loaded["account"] maps account_id -> the customer who owns it.
    """
    for column in required:
        if row[column] is None:
            return f"required value '{column}' is empty"
    if row[key] in seen_keys:
        return f"duplicate {key} '{row[key]}' in source file"

    if table == "account" and row["customer_id"] not in loaded["customer"]:
        return f"customer_id '{row['customer_id']}' does not exist in customer"

    if table in ("complaint", "service_request"):
        if row["customer_id"] not in loaded["customer"]:
            return f"customer_id '{row['customer_id']}' does not exist in customer"
        account_id = row["account_id"]
        if account_id is not None:            # an account is optional
            owner = loaded["account"].get(account_id)
            if owner is None:
                return f"account_id '{account_id}' does not exist in accounts"
            if owner != row["customer_id"]:
                return f"account_id '{account_id}' belongs to customer '{owner}', not to customer '{row['customer_id']}'"

    if table == "complaint":
        employee_id = row["assigned_employee_id"]
        if employee_id is not None and employee_id not in loaded["employee"]:
            return f"assigned_employee_id '{employee_id}' does not exist in employee"
    return None


def load_table(cur, spec, rows, loaded):
    table, key, columns = spec["table"], spec["key"], spec["columns"]
    insert_sql = (f"INSERT INTO {table} ({', '.join(columns)}) "
                  f"VALUES ({', '.join(['%s'] * len(columns))})")
    seen_keys = set()
    inserted = 0
    rejected = []      # (line_number, key value, reason)

    for line_number, row in rows:
        reason = check_row(table, row, spec["required"], seen_keys, key, loaded)
        if reason is None:
            # A savepoint lets the database reject just this row (for example a bad segment value)
            # without cancelling the rest of the run.
            cur.execute("SAVEPOINT one_row")
            try:
                cur.execute(insert_sql, [row[c] for c in columns])
                cur.execute("RELEASE SAVEPOINT one_row")
            except psycopg2.Error as error:
                cur.execute("ROLLBACK TO SAVEPOINT one_row")
                reason = "database rejected row: " + str(error).strip().splitlines()[0]

        if reason:
            rejected.append((line_number, row[key] or "<blank>", reason))
            log(f"REJECT {spec['file']} line {line_number} ({row[key] or '<blank>'}): {reason}")
            continue

        seen_keys.add(row[key])
        inserted += 1
        if table == "account":
            loaded["account"][row["account_id"]] = row["customer_id"]
        else:
            loaded[table].add(row[key])

    log(f"STAGE load: {table:<16} source={len(rows):<3} inserted={inserted:<3} rejected={len(rejected)}")
    return {"table": table, "source": len(rows), "inserted": inserted, "rejected": rejected}


def validate_and_load(cur, data_dir):
    # Check every file's headers first, so a bad header stops the run before any insert.
    all_rows = {}
    for spec in TABLES:
        all_rows[spec["table"]] = read_csv(data_dir / spec["file"], spec)
        log(f"STAGE validate: {spec['file']:<20} headers OK, {len(all_rows[spec['table']])} data row(s)")

    loaded = {"employee": set(), "customer": set(), "account": {}, "complaint": set(), "service_request": set()}
    return [load_table(cur, spec, all_rows[spec["table"]], loaded) for spec in TABLES]


# ---------- Stage 4: verify ----------

def verify(cur, results):
    """Return (report_lines, failures). Any failure means the run is rolled back."""
    failures = []
    lines = ["ROW COUNTS (source vs inserted vs database)", "-" * 78,
             f"{'table':<18}{'source':>8}{'inserted':>10}{'rejected':>10}{'in_db':>8}  result"]
    for r in results:
        cur.execute(f"SELECT COUNT(*) FROM {r['table']}")     # table name comes from TABLES, not from input
        in_db = cur.fetchone()[0]
        ok = r["inserted"] + len(r["rejected"]) == r["source"] and in_db == r["inserted"]
        if not ok:
            failures.append(f"count mismatch for {r['table']}")
        lines.append(f"{r['table']:<18}{r['source']:>8}{r['inserted']:>10}{len(r['rejected']):>10}{in_db:>8}  "
                     f"{'PASS' if ok else 'FAIL'}")

    lines += ["", "ORPHAN / CONSISTENCY CHECKS (expected 0 rows each)", "-" * 78]
    for name, check_sql in ORPHAN_CHECKS:
        cur.execute(check_sql)
        bad = [row[0] for row in cur.fetchall()]
        if bad:
            failures.append(f"{name}: {', '.join(bad)}")
        lines.append(f"{name:<55}{len(bad):>4}  {'PASS' if not bad else 'FAIL ' + ', '.join(bad)}")
        log(f"STAGE verify: {name:<52} {'PASS' if not bad else 'FAIL'}")

    cur.execute("SELECT COUNT(*) FROM complaint WHERE account_id IS NULL")
    complaints_without_account = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM service_request WHERE account_id IS NULL")
    requests_without_account = cur.fetchone()[0]
    lines += ["", "OPTIONAL ACCOUNT LINKS (valid by design, not orphans)", "-" * 78,
              f"complaints with no account_id (general / identity / fraud): {complaints_without_account}",
              f"service requests with no account_id:                        {requests_without_account}"]

    lines += ["", "REJECTED ROWS", "-" * 78]
    rejected_lines = [f"{r['table']}: line {n} ({k}) - {why}" for r in results for n, k, why in r["rejected"]]
    lines += rejected_lines or ["none"]
    return lines, failures


def write_report(path, settings, args, body, result):
    header = [
        "INTEGRITY REPORT - Exercise 2.5.1 Database Seeder",
        "=" * 78,
        f"generated : {datetime.now():%Y-%m-%d %H:%M:%S}",
        f"database  : {settings['user']}@{settings['host']}:{settings['port']}/{settings['dbname']}",
        f"data dir  : {args.data_dir}",
        f"mode      : reset={args.reset} strict={args.strict}",
        f"result    : {result}",
        "",
    ]
    Path(path).write_text("\n".join(header + body) + "\n", encoding="utf-8")


# ---------- Run everything ----------

def run(args):
    settings = db_settings(args.dbname)
    log("=" * 70)
    log(f"RUN START  db={settings['user']}@{settings['host']}:{settings['port']}/{settings['dbname']}  "
        f"reset={args.reset} strict={args.strict}  data={args.data_dir}")

    if args.create_db:
        create_database_if_missing(settings)
    try:
        connection = psycopg2.connect(**settings, connect_timeout=5)
    except psycopg2.OperationalError as error:
        raise SeedError(f"Cannot connect to {settings['host']}:{settings['port']}/{settings['dbname']}: "
                        f"{str(error).strip().splitlines()[0]}")
    log("STAGE connect: connected, starting one transaction")

    try:
        with connection.cursor() as cur:
            initialize(cur, args.reset)
            results = validate_and_load(cur, Path(args.data_dir))
            report, failures = verify(cur, results)

            rejected = sum(len(r["rejected"]) for r in results)
            if args.strict and rejected:
                failures.append(f"--strict: {rejected} row(s) rejected")

            if failures:
                connection.rollback()
                for failure in failures:
                    log(f"CRITICAL: {failure}")
                result = "FAILED - transaction rolled back, database unchanged"
                write_report(args.report, settings, args, report + ["", "FAILURES"] + failures, result)
                log(f"ROLLBACK: {result}")
                return False

            connection.commit()
            result = "PASSED - committed" + (f" ({rejected} row(s) rejected, see below)" if rejected else "")
            write_report(args.report, settings, args, report, result)
            log(f"COMMIT: {result}")
            log(f"Report written to {args.report}")
            return True
    except Exception:
        connection.rollback()     # anything unexpected: undo everything
        raise
    finally:
        connection.close()


def main(argv=None):
    global LOG_FILE
    parser = argparse.ArgumentParser(description="Initialize and seed the complaint training database.")
    parser.add_argument("--reset", action="store_true", help="drop and recreate existing tables (DELETES their data)")
    parser.add_argument("--create-db", action="store_true", help="create the database first if it does not exist")
    parser.add_argument("--strict", action="store_true", help="roll back everything if any row is rejected")
    parser.add_argument("--dbname", help="database name (instead of DB_NAME)")
    parser.add_argument("--data-dir", default=HERE / "data", help="folder with the seed CSV files")
    parser.add_argument("--log", default=HERE / "seed_run_log.txt", help="run log file (added to each run)")
    parser.add_argument("--report", default=HERE / "integrity_report.txt", help="integrity report (replaced each run)")
    args = parser.parse_args(argv)

    LOG_FILE = Path(args.log)
    load_dotenv(Path.cwd() / ".env")
    load_dotenv(REPO_ROOT / ".env")

    try:
        ok = run(args)
    except SeedError as error:
        log(f"CRITICAL: {error}")
        ok = False
    except Exception as error:
        log(f"UNEXPECTED ERROR: {type(error).__name__}: {str(error).strip().splitlines()[0]}")
        ok = False

    log("RUN END: " + ("success" if ok else "failed, no changes saved"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
