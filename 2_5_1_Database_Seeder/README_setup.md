# 2.5.1 Database Setup — One Command

Recreates the complaint training database from scratch: schema from 2.1.1, then validated seed data from CSV. No manual SQL editing.

```bash
python3 seed_database.py --create-db --reset
```

## What's in this folder

| File | Purpose |
|---|---|
| `seed_database.py` | Initialization and seeding command |
| `seed_run_log.txt` | Stage, count and error evidence (appended on every run) |
| `integrity_report.txt` | Counts and orphan checks from the latest run (overwritten each run) |
| `data/*.csv` | Seed-ready data: employees, customers, accounts, complaints, service requests |
| `data/source/` | The project's synthetic data as supplied, saved as CSV. Edit these, not `data/*.csv` |
| `data/reference/` | Scenario and question sets, converted to CSV. Not loaded into the database |
| `prepare_seed_data.py` | Converts `data/source/` into `data/*.csv` (see "Where the seed data comes from") |
| `test_data/invalid_rows/` | Same data plus 11 deliberately bad rows (negative test) |
| `test_data/missing_header/` | `complaints.csv` without the `customer_id` header (negative test) |
| `test_data/invalid_rows_report.txt` | Report from a run that rejected the 11 bad rows |
| `test_data/invalid_rows_strict_report.txt` | Report from the same run in `--strict` mode (rolled back) |
| `tests/test_seed_database.py` | Unit and integration tests |

The schema is read from `../2_1_1_schema/database_schema.sql`. Only its DDL block (the first `BEGIN … COMMIT`) is used; the seed `INSERT`s in that file are replaced by the CSV load here.

## Prerequisites

1. **PostgreSQL 14+** running and reachable. Check: `pg_isready -h localhost -p 5432`.
2. **Python 3.9+** with `psycopg2-binary`:

   ```bash
   python3 -m pip install psycopg2-binary
   ```

   The repo's `.venv` already has it: use `../.venv/bin/python` instead of `python3`.
3. **Connection settings** as environment variables, or in the untracked `.env` file at the repo root (picked up automatically; shell variables win):

   | Variable | Example |
   |---|---|
   | `DB_HOST` | `localhost` |
   | `DB_PORT` | `5432` |
   | `DB_NAME` | `complaints_training` |
   | `DB_USER` | `postgres` |
   | `DB_PASSWORD` | your password |

   The user needs permission to create tables, and to create databases if you use `--create-db`. The password is never written to the log or report.

## Run it

From this folder:

```bash
cd 2_5_1_Database_Seeder
```

```bash
python3 seed_database.py --create-db --reset
```

| Option | Effect |
|---|---|
| `--create-db` | Create the database named by `DB_NAME` if it does not exist |
| `--reset` | Drop and recreate the 16 schema tables if they already exist. **Deletes their data.** Without it, the command refuses to touch an existing schema |
| `--strict` | Roll back the whole run if any row is rejected |
| `--dbname NAME` | Use a different database than `DB_NAME` (e.g. a scratch copy) |
| `--data-dir DIR` | Load CSVs from another folder (default `data/`) |
| `--schema FILE`, `--log FILE`, `--report FILE` | Override default paths |

Exit codes: `0` committed, `1` integrity or strict failure (rolled back), `2` setup problem such as a missing header, missing file, existing schema without `--reset`, or no connection (nothing changed), `3` unexpected error (rolled back).

## Expected output

On the shipped data the console ends with:

```
STAGE load: employee         source=10  inserted=10  rejected=0
STAGE load: customer         source=100 inserted=100 rejected=0
STAGE load: account          source=150 inserted=150 rejected=0
STAGE load: complaint        source=120 inserted=120 rejected=0
STAGE load: service_request  source=60  inserted=60  rejected=0
STAGE verify: account -> customer                                  PASS
...
COMMIT: PASSED - committed
RUN END: success
```

`integrity_report.txt` shows `result : PASSED - committed`, every count row `PASS`, every orphan check `0  PASS`, 39 complaints with no `account_id` and 18 service requests with no `account_id`. Those are valid general complaints, not orphans.

Only the 5 seeded tables get rows. The other 11 tables (transactions, fee, investigation, review, …) are created empty.

## Where the seed data comes from

The project's synthetic data (customers, accounts, complaints, service requests) is kept as supplied in `data/source/`. The Excel accounts sheet was saved as CSV, with balances rounded to cents to remove Excel float noise such as `10256.459999999999`. Everything else is unchanged.

That data doesn't match the 2.1.1 schema's column names and allowed values. Rather than change the schema (the 2.1.1 contract), `prepare_seed_data.py` maps the data onto it. After editing anything in `data/source/`, regenerate the seed files:

```bash
python3 prepare_seed_data.py
```

The script stops without writing anything if it meets a source value it has no mapping for.

| Table | Change | Why |
|---|---|---|
| customer | segment `Standard` → `Retail`, `Premium` → `Premier`, `Small Business` → `Business` | Schema only allows Retail / Premier / Business |
| customer | `risk_category` dropped; `phone_number` empty | No such column / not in source |
| account | `current_balance` → `balance`; status `Active` → `ACTIVE`, `Restricted` → `RESTRICTED` | Schema column name and upper-case statuses |
| account | `account_number` generated: `A00042` → `100000042` | Required and unique, not in source |
| account | `open_date` set to `2025-01-01` for every account (**placeholder**) | Required, not in source. Chosen to fall before the earliest complaint |
| complaint | status `In Review` → `UNDER_REVIEW`, `Escalated` → `ESCALATED`, `Open` → `OPEN`, `Closed` → `CLOSED` | Schema status list |
| complaint | `date_opened` → `created_at` (midnight) | Schema column name and type |
| complaint | `customer_narrative` = "[Placeholder] *category* complaint received by *channel*…" | Required, and the source has no complaint text |
| complaint | `date_closed` dropped; `assigned_employee_id` empty | No such column / not in source |
| service_request | status `Completed` → `CLOSED`, `In Progress` → `IN_PROGRESS`, `Open` → `OPEN` | Schema status list |
| service_request | `closed_date` = `created_date` for CLOSED requests (**placeholder**) | Schema requires a closed date when CLOSED; the source has none |
| service_request | `complaint_id` dropped; `account_id` taken from the linked complaint | No `complaint_id` column. The account keeps the request's account context |
| employee | Kept from the 2.1.1 seed (10 staff) | The source set has no staff file |

Not loaded. These are converted to CSV in `data/reference/` for later exercises:
- `banking_complaint_scenarios.csv`: 20 classification test cases with expected category and urgency. Keeping them out of the database stops a later classifier or agent from looking up the answers.
- `sql_rag_question_set.csv`: 5 evaluation questions for the SQL/RAG work.

Data-quality issue reported, not fixed: 37 of the 60 service requests are dated before the complaint they belong to. The dates are kept as given. The link to the complaint isn't stored in the schema, so it doesn't break any database rule.

## How it works

The whole run is **one transaction**. PostgreSQL DDL is transactional, so the reset, table creation and inserts either all commit or all roll back. A failed run leaves the database exactly as it was before you ran the command.

1. **Initialize**: run the 2.1.1 DDL in dependency order (employee → customer → account → complaint → …). Each table is logged as it is created. Existing tables are only dropped with `--reset`.
2. **Validate**: read every CSV first. A missing file or missing required header is critical and stops the run before any insert.
3. **Load** in FK order. Each row is checked against the rules in `seed_validation_rules.md`, and an invalid row is rejected with a logged reason:
   - required values present, no duplicate key in the file
   - every foreign key resolves to a row that was actually *inserted*, so a child of a rejected parent is rejected too
   - when a complaint or service request has an account, that account must belong to the same customer
   - any remaining database constraint (segment, priority, date order, …) rejects that row only, using a savepoint
4. **Verify**: compare source rows = inserted + rejected = rows in the database, then run 8 orphan and consistency checks. Any failure rolls the run back.

## Verify it yourself

Run the tests. They use a throwaway database, `complaints_seed_test`, which is created and dropped:

```bash
../.venv/bin/python -m unittest discover -s tests -v
```

Try the negative cases against a scratch database:

```bash
python3 seed_database.py --dbname complaints_seed --create-db --reset --data-dir test_data/invalid_rows
```

```bash
python3 seed_database.py --dbname complaints_seed --reset --strict --data-dir test_data/invalid_rows
```

```bash
python3 seed_database.py --dbname complaints_seed --reset --data-dir test_data/missing_header
```

Expected results: 11 rows rejected and the rest committed; then the same run rolled back with exit 1; then a missing `customer_id` header with exit 2. After the last two, the database still holds what the first run committed.

Check counts directly:

```bash
psql -h localhost -U postgres -d complaints_seed -c "SELECT 'complaint', COUNT(*) FROM complaint UNION ALL SELECT 'account', COUNT(*) FROM account"
```

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `Missing environment variable(s): DB_...` | Set the variables, or create `.env` at the repo root |
| `Cannot connect to localhost:5432/...` | PostgreSQL isn't running, or host, port or password is wrong. Check with `pg_isready` |
| `database "..." does not exist` | Add `--create-db` |
| `16 schema table(s) already exist ... Re-run with --reset` | Safety stop. Add `--reset` only if you mean to wipe those tables |
| `permission denied to create database` | Create the database as an admin, or use a user with `CREATEDB` |
| `missing required header(s): ...` | Fix the CSV's first line. Headers must match the column names in the table above the CSV files |
| `REJECT ... line N` warnings | That row broke a rule and was skipped. The reason is in the log and the report. Use `--strict` to make any rejection fatal |
| `ModuleNotFoundError: psycopg2` | `python3 -m pip install psycopg2-binary`, or use `../.venv/bin/python` |

## Known limitations

- `--reset` uses `DROP TABLE … CASCADE` from the 2.1.1 schema. It also drops dependent views created by other exercises, such as `complaint_analyst_view` from 2.2.1. Re-run those scripts afterwards.
- Only employees, customers, accounts, complaints and service requests come from CSV. The other tables are created empty. No complaint is assigned to an employee.
- **Some source information is not stored**, because the 2.1.1 schema has no column for it: complaint `date_closed`, customer `risk_category`, and the service request → complaint link. So questions like "average closure time by category" can't be answered from this database yet. Storing them needs a schema change plus an update to the 2.1.1 data dictionary.
- Complaint narratives, account open dates and service request closed dates are **placeholders**, as listed in the table above. Don't treat them as real values in analysis.
- The IDs differ from the 2.1.1 seed (`C0001`, not `CUS001`). Queries and tests from earlier exercises that use the old IDs, including the 2.4.2 integration tests, need updating before they run against a database built by this command.
- Rows created later by the 2.4.2 API (e.g. new complaints) are lost on `--reset`. They are not in the CSVs.
- The CSVs are loaded in full into memory. That's fine for training-sized data, not for millions of rows.
- The run log is appended and never rotated. Delete `seed_run_log.txt` to start fresh.

## Handover

Exercise 2.5.2 deletes and recreates the environment using only this command and this guide:

```bash
python3 seed_database.py --create-db --reset
```
