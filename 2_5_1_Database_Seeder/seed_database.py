# seed_database.py
# Week 2 | Exercise 2.5.1 - Build the database and load the shared CSV data.
#
# How to run (from this folder):
#   python3 seed_database.py            first time, or when the tables don't exist yet
#   python3 seed_database.py --reset    rebuild: DELETES the existing tables and their data
#
# Steps:
#   1. Initialize  create the 2.1.1 tables (only replaces existing tables with --reset)
#   2. Validate    check the 4 CSV files and their headers, then check every row
#                  and load the good ones. Bad rows are rejected with a reason.
#   3. Verify      compare counts and look for orphan rows, then write integrity_report.txt
#
# Everything is one transaction. If anything critical fails, it is all undone
# and the database is left exactly as it was.

import csv
import os
import sys
from datetime import datetime

import psycopg2
from psycopg2 import sql

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(HERE, "..", "2_1_1_schema", "database_schema.sql")
ENV_FILE = os.path.join(HERE, "..", ".env")
LOG_FILE = os.path.join(HERE, "seed_run_log.txt")
REPORT_FILE = os.path.join(HERE, "integrity_report.txt")

# The seeder fills its own database, so --reset can never wipe
# complaints_training (the database 2.4.2 uses).
DATABASE_NAME = "complaints_seed"

# The columns each shared file must have.
REQUIRED_HEADERS = {
    "customers.csv": ["customer_id", "first_name", "last_name", "segment", "email"],
    "accounts.csv": ["account_id", "customer_id", "account_type", "status", "current_balance"],
    "complaints.csv": ["complaint_id", "customer_id", "account_id", "category", "status",
                       "date_opened", "channel", "priority"],
    "service_requests.csv": ["request_id", "complaint_id", "customer_id", "request_type",
                             "status", "created_date"],
}

# The shared files word some values differently from the 2.1.1 tables.
# source value -> table value. A value not listed here is rejected, never guessed.
CUSTOMER_SEGMENT = {"Standard": "Retail", "Premium": "Premier", "Small Business": "Business"}
ACCOUNT_STATUS = {"Active": "ACTIVE", "Inactive": "INACTIVE", "Closed": "CLOSED", "Restricted": "RESTRICTED"}
COMPLAINT_STATUS = {"Open": "OPEN", "In Progress": "IN_PROGRESS", "In Review": "UNDER_REVIEW",
                    "Escalated": "ESCALATED", "Resolved": "RESOLVED", "Closed": "CLOSED"}
REQUEST_STATUS = {"Open": "OPEN", "In Progress": "IN_PROGRESS", "Completed": "CLOSED"}
PRIORITIES = ["Low", "Medium", "High", "Critical"]

# Stand-ins: the 2.1.1 tables need these values, but the shared files don't have them.
# Each one is listed in integrity_report.txt and README_setup.md.
ACCOUNT_OPEN_DATE = "2026-01-01"           # before the earliest complaint (2026-01-02)
NO_COMPLAINT_TEXT = "[No complaint text in source data]"

STAND_INS = [
    "account.account_number = the account_id (the file has no account numbers)",
    "account.open_date = " + ACCOUNT_OPEN_DATE + " for every account (the file has no open dates)",
    "complaint.customer_narrative = '" + NO_COMPLAINT_TEXT + "' (the file has no complaint text)",
    "complaint.created_at = date_opened at 00:00 (the file has dates, not times)",
    "service_request.closed_date = created_date for Completed requests (the file has no closed date)",
    "service_request.account_id = the account of the linked complaint (the file links to a complaint, not an account)",
    "Not loaded: customers.risk_category and complaints.date_closed (the 2.1.1 tables have no column for them)",
]


class SeedError(Exception):
    """A critical problem. The run stops and nothing is saved."""


# ----- Small helpers -----

def log(message):
    """Print a line and add it to seed_run_log.txt."""
    line = datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " " + message
    print(line)
    log_file = open(LOG_FILE, "a", encoding="utf-8")
    log_file.write(line + "\n")
    log_file.close()


def read_env_file():
    """Read NAME=value lines from the .env file. Settings already in the terminal win."""
    if not os.path.isfile(ENV_FILE):
        return
    env_file = open(ENV_FILE, encoding="utf-8")
    for line in env_file:
        line = line.strip()
        if line == "" or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")      # allow DB_PASSWORD="secret" or 'secret'
        if name.strip() not in os.environ:
            os.environ[name.strip()] = value
    env_file.close()


def get_settings():
    missing = []
    for name in ["DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD"]:
        if not os.environ.get(name):
            missing.append(name)
    if len(missing) > 0:
        # Name the missing settings, but never show any values.
        raise SeedError("missing setting(s): " + ", ".join(missing) + " (put them in the .env file)")
    return {
        "host": os.environ["DB_HOST"],
        "port": int(os.environ["DB_PORT"]),
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],     # never printed or logged
    }


def read_date(text):
    """Shared files use dates like 4/28/2026. Gives back a date, or None if it isn't one."""
    try:
        return datetime.strptime(text, "%m/%d/%Y").date()
    except ValueError:
        return None


def is_number(text):
    try:
        float(text)
        return True
    except ValueError:
        return False


# ----- Step 1: initialize -----

def create_database_if_missing(settings):
    connection = psycopg2.connect(dbname="postgres", connect_timeout=5, **settings)
    connection.autocommit = True        # CREATE DATABASE can't run inside a transaction
    cursor = connection.cursor()
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DATABASE_NAME,))
    if cursor.fetchone() is None:
        # sql.Identifier quotes the name safely (a name can't use a %s placeholder)
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE_NAME)))
        log("STAGE init: created database " + DATABASE_NAME)
    else:
        log("STAGE init: database " + DATABASE_NAME + " already exists")
    cursor.close()
    connection.close()


def initialize(cursor, reset):
    # Safety stop: never replace existing tables unless --reset was given.
    cursor.execute("SELECT COUNT(*) FROM information_schema.tables "
                   "WHERE table_schema = 'public' AND table_name = 'customer'")
    tables_exist = cursor.fetchone()[0] > 0
    if tables_exist and not reset:
        raise SeedError("the tables already exist, so nothing was changed. "
                        "Run again with --reset to delete and rebuild them.")
    if tables_exist:
        log("STAGE init: --reset given, deleting and rebuilding the existing tables")

    if not os.path.isfile(SCHEMA_FILE):
        raise SeedError("schema file not found: " + SCHEMA_FILE)
    schema_file = open(SCHEMA_FILE, encoding="utf-8")
    schema = schema_file.read()
    schema_file.close()

    # database_schema.sql has two parts: the tables (first BEGIN ... COMMIT), then the old
    # 2.1.1 sample rows. Only the tables are used. The shared CSV files replace the sample rows.
    tables_part = schema.split("COMMIT;")[0].replace("BEGIN;", "", 1)
    cursor.execute(tables_part)        # drops (if they exist) and creates the tables in dependency order
    log("STAGE init: created " + str(tables_part.count("CREATE TABLE")) + " tables from 2_1_1_schema/database_schema.sql")


# ----- Step 2: validate and load -----

def read_csv(folder, file_name):
    """Read one shared file. A missing file or a missing header is critical."""
    path = os.path.join(folder, file_name)
    if not os.path.isfile(path):
        raise SeedError(file_name + " not found in " + folder)
    csv_file = open(path, newline="", encoding="utf-8-sig")
    reader = csv.DictReader(csv_file)
    headers = []
    for header in reader.fieldnames or []:
        headers.append(header.strip())
    reader.fieldnames = headers

    missing = []
    for header in REQUIRED_HEADERS[file_name]:
        if header not in headers:
            missing.append(header)
    if len(missing) > 0:
        csv_file.close()
        raise SeedError(file_name + " is missing required header(s): " + ", ".join(missing))

    rows = []
    for row in reader:
        clean = {}
        for header in headers:
            clean[header] = (row[header] or "").strip()
        rows.append(clean)
    csv_file.close()
    log("STAGE validate: " + file_name + " headers OK, " + str(len(rows)) + " rows")
    return rows


def first_blank(row, columns):
    """Gives back the first required column that is empty, or None."""
    for column in columns:
        if row[column] == "":
            return column
    return None


class Loader:
    """Checks each row before it is inserted, and remembers what has been loaded,
    so a row whose customer, account or complaint was rejected is rejected too."""

    def __init__(self, cursor):
        self.cursor = cursor
        self.customers = []          # loaded customer IDs
        self.account_owner = {}      # account_id -> customer_id
        self.complaint_info = {}     # complaint_id -> (customer_id, account_id)
        self.request_ids = []
        self.results = []            # one entry per table: name, source, inserted, rejected
        self.rejected = []           # every rejected row, for the report

    def reject(self, file_name, line, row_id, reason):
        self.rejected.append(file_name + " line " + str(line) + " (" + (row_id or "<blank>") + "): " + reason)
        log("REJECT " + file_name + " line " + str(line) + " (" + (row_id or "<blank>") + "): " + reason)

    def finish(self, table, file_name, rows, inserted):
        rejected = len(rows) - inserted
        self.results.append({"table": table, "source": len(rows), "inserted": inserted, "rejected": rejected})
        log("STAGE load: " + table + " source=" + str(len(rows)) + " inserted=" + str(inserted)
            + " rejected=" + str(rejected))

    def load_customers(self, rows):
        inserted = 0
        line = 1                     # line 1 is the header
        for row in rows:
            line = line + 1
            row_id = row["customer_id"]
            blank = first_blank(row, ["customer_id", "first_name", "last_name", "segment"])
            if blank:
                self.reject("customers.csv", line, row_id, "required value '" + blank + "' is empty")
                continue
            if row_id in self.customers:
                self.reject("customers.csv", line, row_id, "duplicate customer_id")
                continue
            if row["segment"] not in CUSTOMER_SEGMENT:
                self.reject("customers.csv", line, row_id, "unknown segment '" + row["segment"] + "'")
                continue

            self.cursor.execute(
                "INSERT INTO customer (customer_id, first_name, last_name, email, phone_number, segment) "
                "VALUES (%s, %s, %s, %s, NULL, %s)",
                (row_id, row["first_name"], row["last_name"], row["email"] or None,
                 CUSTOMER_SEGMENT[row["segment"]]),
            )
            self.customers.append(row_id)
            inserted = inserted + 1
        self.finish("customer", "customers.csv", rows, inserted)

    def load_accounts(self, rows):
        inserted = 0
        line = 1
        for row in rows:
            line = line + 1
            row_id = row["account_id"]
            blank = first_blank(row, ["account_id", "customer_id", "account_type", "status", "current_balance"])
            if blank:
                self.reject("accounts.csv", line, row_id, "required value '" + blank + "' is empty")
                continue
            if row_id in self.account_owner:
                self.reject("accounts.csv", line, row_id, "duplicate account_id")
                continue
            if row["customer_id"] not in self.customers:
                self.reject("accounts.csv", line, row_id, "customer_id '" + row["customer_id"] + "' does not exist")
                continue
            if row["status"] not in ACCOUNT_STATUS:
                self.reject("accounts.csv", line, row_id, "unknown status '" + row["status"] + "'")
                continue
            if not is_number(row["current_balance"]):
                self.reject("accounts.csv", line, row_id, "balance '" + row["current_balance"] + "' is not a number")
                continue

            self.cursor.execute(
                "INSERT INTO account (account_id, customer_id, account_number, account_type, status, balance, open_date) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (row_id, row["customer_id"], row_id, row["account_type"], ACCOUNT_STATUS[row["status"]],
                 row["current_balance"], ACCOUNT_OPEN_DATE),
            )
            self.account_owner[row_id] = row["customer_id"]
            inserted = inserted + 1
        self.finish("account", "accounts.csv", rows, inserted)

    def load_complaints(self, rows):
        inserted = 0
        line = 1
        for row in rows:
            line = line + 1
            row_id = row["complaint_id"]
            customer_id = row["customer_id"]
            account_id = row["account_id"] or None          # an account is optional
            blank = first_blank(row, ["complaint_id", "customer_id", "category", "status",
                                      "date_opened", "channel", "priority"])
            if blank:
                self.reject("complaints.csv", line, row_id, "required value '" + blank + "' is empty")
                continue
            if row_id in self.complaint_info:
                self.reject("complaints.csv", line, row_id, "duplicate complaint_id")
                continue
            if customer_id not in self.customers:
                self.reject("complaints.csv", line, row_id, "customer_id '" + customer_id + "' does not exist")
                continue
            if account_id is not None and account_id not in self.account_owner:
                self.reject("complaints.csv", line, row_id, "account_id '" + account_id + "' does not exist")
                continue
            if account_id is not None and self.account_owner[account_id] != customer_id:
                self.reject("complaints.csv", line, row_id, "account_id '" + account_id + "' belongs to customer '"
                            + self.account_owner[account_id] + "', not '" + customer_id + "'")
                continue
            if row["status"] not in COMPLAINT_STATUS:
                self.reject("complaints.csv", line, row_id, "unknown status '" + row["status"] + "'")
                continue
            if row["priority"] not in PRIORITIES:
                self.reject("complaints.csv", line, row_id, "unknown priority '" + row["priority"] + "'")
                continue
            opened = read_date(row["date_opened"])
            if opened is None:
                self.reject("complaints.csv", line, row_id, "date_opened '" + row["date_opened"] + "' is not a M/D/YYYY date")
                continue

            self.cursor.execute(
                "INSERT INTO complaint (complaint_id, customer_id, account_id, channel, category, customer_narrative, "
                "priority, status, created_at, assigned_employee_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)",
                (row_id, customer_id, account_id, row["channel"], row["category"], NO_COMPLAINT_TEXT,
                 row["priority"], COMPLAINT_STATUS[row["status"]], opened),
            )
            self.complaint_info[row_id] = (customer_id, account_id)
            inserted = inserted + 1
        self.finish("complaint", "complaints.csv", rows, inserted)

    def load_service_requests(self, rows):
        inserted = 0
        line = 1
        for row in rows:
            line = line + 1
            row_id = row["request_id"]
            customer_id = row["customer_id"]
            complaint_id = row["complaint_id"] or None      # a linked complaint is optional
            blank = first_blank(row, ["request_id", "customer_id", "request_type", "status", "created_date"])
            if blank:
                self.reject("service_requests.csv", line, row_id, "required value '" + blank + "' is empty")
                continue
            if row_id in self.request_ids:
                self.reject("service_requests.csv", line, row_id, "duplicate request_id")
                continue
            if customer_id not in self.customers:
                self.reject("service_requests.csv", line, row_id, "customer_id '" + customer_id + "' does not exist")
                continue
            if complaint_id is not None and complaint_id not in self.complaint_info:
                self.reject("service_requests.csv", line, row_id, "complaint_id '" + complaint_id + "' does not exist")
                continue
            if complaint_id is not None and self.complaint_info[complaint_id][0] != customer_id:
                self.reject("service_requests.csv", line, row_id, "complaint_id '" + complaint_id
                            + "' belongs to another customer")
                continue
            if row["status"] not in REQUEST_STATUS:
                self.reject("service_requests.csv", line, row_id, "unknown status '" + row["status"] + "'")
                continue
            created = read_date(row["created_date"])
            if created is None:
                self.reject("service_requests.csv", line, row_id, "created_date '" + row["created_date"] + "' is not a M/D/YYYY date")
                continue

            status = REQUEST_STATUS[row["status"]]
            account_id = None
            if complaint_id is not None:
                account_id = self.complaint_info[complaint_id][1]
            closed = None
            if status == "CLOSED":
                closed = created                            # stand-in, see STAND_INS

            self.cursor.execute(
                "INSERT INTO service_request (request_id, customer_id, account_id, request_type, status, "
                "created_date, closed_date) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (row_id, customer_id, account_id, row["request_type"], status, created, closed),
            )
            self.request_ids.append(row_id)
            inserted = inserted + 1
        self.finish("service_request", "service_requests.csv", rows, inserted)


# ----- Step 3: verify -----

COUNT_QUERIES = {
    "customer": "SELECT COUNT(*) FROM customer",
    "account": "SELECT COUNT(*) FROM account",
    "complaint": "SELECT COUNT(*) FROM complaint",
    "service_request": "SELECT COUNT(*) FROM service_request",
}

# Each check should find 0 rows. A row found is an orphan or a broken link.
ORPHAN_CHECKS = [
    ("account -> customer",
     "SELECT a.account_id FROM account a LEFT JOIN customer c ON a.customer_id = c.customer_id "
     "WHERE c.customer_id IS NULL"),
    ("complaint -> customer",
     "SELECT x.complaint_id FROM complaint x LEFT JOIN customer c ON x.customer_id = c.customer_id "
     "WHERE c.customer_id IS NULL"),
    ("complaint -> account (when there is one)",
     "SELECT x.complaint_id FROM complaint x LEFT JOIN account a ON x.account_id = a.account_id "
     "WHERE x.account_id IS NOT NULL AND a.account_id IS NULL"),
    ("complaint account belongs to the complaint customer",
     "SELECT x.complaint_id FROM complaint x JOIN account a ON x.account_id = a.account_id "
     "WHERE a.customer_id <> x.customer_id"),
    ("service_request -> customer",
     "SELECT s.request_id FROM service_request s LEFT JOIN customer c ON s.customer_id = c.customer_id "
     "WHERE c.customer_id IS NULL"),
    ("service_request -> account (when there is one)",
     "SELECT s.request_id FROM service_request s LEFT JOIN account a ON s.account_id = a.account_id "
     "WHERE s.account_id IS NOT NULL AND a.account_id IS NULL"),
    ("service_request account belongs to the request customer",
     "SELECT s.request_id FROM service_request s JOIN account a ON s.account_id = a.account_id "
     "WHERE a.customer_id <> s.customer_id"),
]


def verify(cursor, loader):
    """Gives back (report lines, failures). Any failure means everything is undone."""
    failures = []
    lines = ["ROW COUNTS (file vs inserted vs database)", "-" * 72,
             "table              file  inserted  rejected  in_db  result"]
    for result in loader.results:
        cursor.execute(COUNT_QUERIES[result["table"]])
        in_db = cursor.fetchone()[0]
        ok = result["inserted"] + result["rejected"] == result["source"] and in_db == result["inserted"]
        if not ok:
            failures.append("count mismatch for " + result["table"])
        lines.append(result["table"].ljust(17) + str(result["source"]).rjust(6) + str(result["inserted"]).rjust(10)
                     + str(result["rejected"]).rjust(10) + str(in_db).rjust(7) + "  " + ("PASS" if ok else "FAIL"))

    lines += ["", "ORPHAN AND CONSISTENCY CHECKS (each should find 0 rows)", "-" * 72]
    for name, check_sql in ORPHAN_CHECKS:
        cursor.execute(check_sql)
        bad_ids = []
        for row in cursor.fetchall():
            bad_ids.append(row[0])
        if len(bad_ids) > 0:
            failures.append(name + ": " + ", ".join(bad_ids))
        lines.append(name.ljust(58) + str(len(bad_ids)).rjust(3) + "  " + ("PASS" if len(bad_ids) == 0 else "FAIL"))
        log("STAGE verify: " + name + " " + ("PASS" if len(bad_ids) == 0 else "FAIL"))

    cursor.execute("SELECT COUNT(*) FROM complaint WHERE account_id IS NULL")
    complaints_without_account = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM service_request WHERE account_id IS NULL")
    requests_without_account = cursor.fetchone()[0]
    lines += ["", "OPTIONAL ACCOUNT LINKS (allowed, not orphans)", "-" * 72,
              "complaints with no account:        " + str(complaints_without_account),
              "service requests with no account:  " + str(requests_without_account)]

    lines += ["", "REJECTED ROWS", "-" * 72]
    if len(loader.rejected) == 0:
        lines.append("none")
    else:
        lines += loader.rejected

    lines += ["", "STAND-IN VALUES (the shared files don't have these, see README_setup.md)", "-" * 72]
    lines += STAND_INS
    return lines, failures


def write_report(settings, data_folder, reset, result, body):
    lines = ["INTEGRITY REPORT - Exercise 2.5.1 Database Seeder", "=" * 72,
             "generated : " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             "database  : " + settings["user"] + "@" + settings["host"] + ":" + str(settings["port"]) + "/" + DATABASE_NAME,
             "data      : " + data_folder,
             "reset     : " + str(reset),
             "result    : " + result, ""]
    report = open(REPORT_FILE, "w", encoding="utf-8")
    report.write("\n".join(lines + body) + "\n")
    report.close()


# ----- Run everything -----

def run(reset, data_folder):
    read_env_file()
    settings = get_settings()
    folder_name = os.path.relpath(data_folder, HERE)
    log("RUN START: database=" + DATABASE_NAME + " on " + settings["host"] + ":" + str(settings["port"])
        + " reset=" + str(reset) + " data=" + folder_name)

    create_database_if_missing(settings)
    connection = psycopg2.connect(dbname=DATABASE_NAME, connect_timeout=5, **settings)
    cursor = connection.cursor()
    log("STAGE init: connected, everything below is one transaction")
    try:
        initialize(cursor, reset)

        # Read and check all 4 files before inserting anything.
        customers = read_csv(data_folder, "customers.csv")
        accounts = read_csv(data_folder, "accounts.csv")
        complaints = read_csv(data_folder, "complaints.csv")
        requests = read_csv(data_folder, "service_requests.csv")

        # Parents before children, so every link can be checked.
        loader = Loader(cursor)
        loader.load_customers(customers)
        loader.load_accounts(accounts)
        loader.load_complaints(complaints)
        loader.load_service_requests(requests)

        body, failures = verify(cursor, loader)
        if len(failures) > 0:
            connection.rollback()
            for failure in failures:
                log("CRITICAL: " + failure)
            write_report(settings, folder_name, reset, "FAILED - everything undone, database unchanged",
                         body + ["", "FAILURES"] + failures)
            log("ROLLBACK: integrity check failed, nothing was saved")
            return False

        connection.commit()
        result = "PASSED - saved"
        if len(loader.rejected) > 0:
            result = result + " (" + str(len(loader.rejected)) + " row(s) rejected, see below)"
        write_report(settings, folder_name, reset, result, body)
        log("COMMIT: " + result)
        log("Report written to integrity_report.txt")
        return True
    except Exception:
        connection.rollback()          # anything unexpected: undo everything
        log("ROLLBACK: nothing was saved")
        raise
    finally:
        cursor.close()
        connection.close()


def main():
    reset = "--reset" in sys.argv
    data_folder = os.path.join(HERE, "data")
    if "--data" in sys.argv:            # used for the failure tests: --data <folder>
        data_folder = os.path.abspath(sys.argv[sys.argv.index("--data") + 1])

    try:
        ok = run(reset, data_folder)
    except SeedError as error:
        log("CRITICAL: " + str(error))
        ok = False
    except psycopg2.Error as error:
        log("DATABASE ERROR: " + str(error).strip().splitlines()[0])
        ok = False

    if ok:
        log("RUN END: success")
        sys.exit(0)
    log("RUN END: failed, no changes saved")
    sys.exit(1)


if __name__ == "__main__":
    main()
