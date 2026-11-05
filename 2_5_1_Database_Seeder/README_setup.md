# 2.5.1 Database Setup: One Command

Week 2 | Exercise 2.5.1

`seed_database.py` builds the complaint training database from nothing and loads the shared CSV data. You never have to write SQL by hand.

```bash
python3 seed_database.py
```

## What's in this folder

| File | What it is |
|---|---|
| `seed_database.py` | The setup command |
| `seed_run_log.txt` | Every stage, count and error from each run. Each run is added to the end |
| `integrity_report.txt` | Row counts and orphan checks from the latest successful run. Replaced each time |
| `README_setup.md` | This guide |
| `data/` | The 4 shared CSV files, exactly as supplied: `customers.csv`, `accounts.csv`, `complaints.csv`, `service_requests.csv` |

The tables come from `../2_1_1_schema/database_schema.sql`. Only its table-creation part (the first `BEGIN … COMMIT`) is used. The CSV files replace its old sample rows.

## Prerequisites

1. **PostgreSQL** running on your computer. Check it with:

   ```bash
   pg_isready -h localhost -p 5432
   ```

   You should see `accepting connections`.

2. **Python 3.9+** with `psycopg2`, the library Python uses to talk to PostgreSQL. The repo's `.venv` already has it. Otherwise:

   ```bash
   python3 -m pip install psycopg2-binary
   ```

3. **A `.env` file** in the repo folder (one level up from this folder), with the names from `environment_example.txt`:

   ```
   DB_HOST=localhost
   DB_PORT=5432
   DB_USER=postgres
   DB_PASSWORD=your_password
   ```

   - The user needs permission to create databases and tables.
   - The script reads `.env` itself. Settings already in your terminal win.
   - The password is never printed or written to the log or report, and `.gitignore` keeps `.env` off GitHub.
   - `DB_NAME` is not used: the seeder always fills its own database, **`complaints_seed`**. That way `--reset` can never wipe `complaints_training`, which 2.4.2 uses.

## Run it

From this folder:

```bash
cd 2_5_1_Database_Seeder
```

**First time** (the database or tables don't exist yet):

```bash
../.venv/bin/python seed_database.py
```

**Rebuild from scratch** (deletes the existing tables and their data, then loads again):

```bash
../.venv/bin/python seed_database.py --reset
```

If you've installed `psycopg2` yourself, use `python3` instead of `../.venv/bin/python`.

## What it does

| Step | What happens |
|---|---|
| 1. Initialize | Creates the `complaints_seed` database if it's missing, then the 16 tables from 2.1.1 in dependency order. If the tables already exist, it **stops** unless you add `--reset`. |
| 2. Validate | Checks all 4 files exist and have the required headers *before* inserting anything. |
| 3. Load | Checks every row, then loads customers → accounts → complaints → service requests (parents first). A bad row is **rejected with a reason** and the rest carry on. A row whose customer, account or complaint was rejected is rejected too. |
| 4. Verify | Compares file counts with the database, and runs 7 orphan and consistency checks. |
| 5. Save or undo | Everything above is **one transaction**. If a critical check fails, it's all undone and the database is left exactly as it was. Otherwise it's saved. |

**Critical** (stops the run and undoes everything): a missing setting, a missing file, a missing header, a database error, a count mismatch, or a failed orphan check.

**A rejected row** (recorded, and the run carries on) is any row that breaks one of the rules below.

## Rules each row is checked against

From `seed_validation_rules.md`, plus the 2.1.1 table rules:

- Required values aren't empty, and IDs aren't repeated.
- Every link points at something that was loaded:
  - an account's customer
  - a complaint's customer and account
  - a service request's customer and complaint
- **A complaint's account, when there is one, belongs to that complaint's customer.** The same goes for a service request's complaint.
- Values are ones the tables allow, translated from the shared files' wording:

  | File value | Table value |
  |---|---|
  | Segment `Standard` / `Premium` / `Small Business` | `Retail` / `Premier` / `Business` |
  | Account status `Active` / `Restricted` | `ACTIVE` / `RESTRICTED` |
  | Complaint status `Open` / `In Review` / `Escalated` / `Closed` | `OPEN` / `UNDER_REVIEW` / `ESCALATED` / `CLOSED` |
  | Request status `Open` / `In Progress` / `Completed` | `OPEN` / `IN_PROGRESS` / `CLOSED` |
  | Dates like `4/28/2026` | `2026-04-28` |

  A value not in this list is rejected, never guessed.
- Priority is `Low`, `Medium`, `High` or `Critical`, and balances are numbers.

## Expected output

The last lines on screen should be:

```
STAGE load: customer source=100 inserted=100 rejected=0
STAGE load: account source=150 inserted=150 rejected=0
STAGE load: complaint source=120 inserted=120 rejected=0
STAGE load: service_request source=60 inserted=60 rejected=0
STAGE verify: ... PASS          (7 checks)
COMMIT: PASSED - saved
RUN END: success
```

`integrity_report.txt` then shows:

| Table | File | Inserted | Rejected | In database |
|---|---:|---:|---:|---:|
| customer | 100 | 100 | 0 | 100 |
| account | 150 | 150 | 0 | 150 |
| complaint | 120 | 120 | 0 | 120 |
| service_request | 60 | 60 | 0 | 60 |

All 7 orphan checks find 0 rows. 39 complaints and 18 service requests have no account, which is allowed.

## Stand-in values (known limitations)

The 2.1.1 tables require some values the shared files don't have. To keep the 2.1.1 design unchanged, the seeder fills them with clearly labelled stand-ins. They're also listed at the end of every `integrity_report.txt`.

| Column | Stand-in | Why |
|---|---|---|
| `account.account_number` | The `account_id`, e.g. `A00042` | The file has no account numbers |
| `account.open_date` | `2026-01-01` for every account | The file has no open dates. This is before the earliest complaint (2026-01-02) |
| `complaint.customer_narrative` | `[No complaint text in source data]` | The file has no complaint text |
| `complaint.created_at` | `date_opened` at 00:00 | The file has dates but no times |
| `service_request.closed_date` | Same as `created_date` for `Completed` requests | The table needs a closed date for closed requests, and the file has none |
| `service_request.account_id` | The account of the linked complaint | The file links a request to a complaint, not an account |

**Not loaded:**
- `customers.risk_category` and `complaints.date_closed`. The 2.1.1 tables have no column for them, so resolution times **can't** be worked out from the seeded database. 2.4.1 calculates them from the CSV instead.
- No employees, policies, investigations or other tables. The shared files only cover customers, accounts, complaints and service requests, so those tables are created but left empty.

**Other limitations:**
- Mapping `Standard` → `Retail` and `Small Business` → `Business` is my reading of the two sets of names. It isn't defined anywhere in the source files.
- The whole load is one transaction. That's fine at this size, but a very large file would hold the transaction open for a long time.

## Failure tests

These were run on 2026-11-05. Their output is in `seed_run_log.txt`. The test files aren't kept in the repo. To repeat a test, copy `data/` to a new folder, make the change, and run with `--data <folder>`.

| Test | How | Result |
|---|---|---|
| Bad rows | Added 15 bad rows to a copy of `data/`: a duplicate ID, an empty first name, segment `Gold`, an unknown customer (on an account and on a complaint), status `Frozen`, balance `abc`, an account of a rejected customer, another customer's account, priority `Urgent`, date `2026-13-45`, an unknown account, an unknown complaint, a complaint of another customer, status `Done` | All 15 rejected with the right reason. The 430 good rows loaded. **PASS** |
| Missing header | Removed `customer_id` from the `complaints.csv` header | Stopped with `CRITICAL: complaints.csv is missing required header(s): customer_id`. The tables it had already rebuilt were undone, so the database still had its 100 customers. **PASS** |
| Missing file | Left out `service_requests.csv` | Stopped with `CRITICAL: service_requests.csv not found`. Nothing saved. **PASS** |
| No `--reset` | Ran again on a database that already had the tables | Stopped with `the tables already exist, so nothing was changed`. **PASS** |
| Fresh setup | Deleted the `complaints_seed` database, then ran `seed_database.py` | Created the database and tables, and loaded all 430 rows. **PASS** |

The 2.4.2 repositories also work on the seeded database. For example, `CustomerRepository.get_by_id("C0015")` returns a customer with complaint `CP00001`.

## Troubleshooting

| Message | What to do |
|---|---|
| `missing setting(s): DB_HOST, ...` | Create or fix `.env` in the repo folder (see Prerequisites) |
| `connection ... failed: Connection refused` | PostgreSQL isn't running. Start it, then check with `pg_isready` |
| `password authentication failed` | Check `DB_USER` and `DB_PASSWORD` in `.env` |
| `permission denied to create database` | Use a user that can create databases, or ask an admin to create `complaints_seed` for you |
| `the tables already exist, so nothing was changed` | Add `--reset` to rebuild (this deletes the current data) |
| `... is missing required header(s): ...` or `... not found` | A data file was changed or removed. Restore `data/` from git: `git checkout -- data` |
| `REJECT ... line N ...` | That row broke a rule. Fix it in `data/`, or leave it: the rest still loads |
| `ModuleNotFoundError: No module named 'psycopg2'` | Use `../.venv/bin/python`, or install `psycopg2-binary` |

**Handover:** 2.5.2 deletes and rebuilds the environment using only this command and this guide. The connection and validation pattern matches 2.4.2.
