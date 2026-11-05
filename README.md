# Week 2: Banking Complaint Data (SQL and Python)

FDM Forward Deployed AI Engineer · Week 2 · Structured-data foundation

This repo holds my Week 2 exercises. They all work on one synthetic banking complaint database: customers, accounts, complaints, and the investigations and reviews behind them. Each exercise builds on the one before it.

```
2.1.1 build the database ──► 2.1.2 basic queries ──► 2.2.1 joins + analyst view ──► 2.2.2 metrics
                                                                                        │
2.5.1 seeder ◄── 2.4.2 repositories ◄── 2.4.1 Python analysis ◄── 2.3.2 SQL vs RAG ◄── 2.3.1 advanced SQL
```

All data is synthetic training data. No real customer information is used.

## Folders at a glance

| Exercise | Folder | Type | What it is |
|---|---|---|---|
| 2.1.1 | [2_1_1_schema](2_1_1_schema) | SQL | Builds the database: 16 tables, keys and rules, plus sample data |
| 2.1.2 | [2_1_2_BasicSQL](2_1_2_BasicSQL) | SQL | 8 basic questions answered with simple queries |
| 2.2.1 | [2_2_1_SQLJoins](2_2_1_SQLJoins) | SQL | Joins complaints to customers and accounts, and a safe view for analysts |
| 2.2.2 | [2_2_2_SQLMetrics](2_2_2_SQLMetrics) | SQL | Business metrics (backlog, resolution time) with clear definitions |
| 2.3.1 | [2_3_1_AdvancedSQL](2_3_1_AdvancedSQL) | SQL | CASE, CTE, ROW_NUMBER and RANK queries |
| 2.3.2 | [2_3_2_retrieval](2_3_2_retrieval) | Design | When to use SQL, document search (RAG), or both, and the risks of each |
| 2.4.1 | [2_4_1_PythonAnalysis](2_4_1_PythonAnalysis) | Python | Reads a complaints CSV, checks it, and writes a summary |
| 2.4.2 | [2_4_2_Repositories](2_4_2_Repositories) | Python | Safe, reusable code that gets data from the database |
| 2.5.1 | [2_5_1_Database_Seeder](2_5_1_Database_Seeder) | Python | One command that builds the database and loads the shared CSV data |

---

## 2.1.1 Build the database

**Goal:** design and create the PostgreSQL database every later exercise uses.

| File | What it is |
|---|---|
| `database_schema.sql` | Creates the 16 tables in the right order, with primary keys, foreign keys and `CHECK` rules, then inserts the sample data |
| `data_dictionary.md` | Every table and column: type, whether it can be empty, what it means, and an example |
| `complaint_erd.png` | Diagram of the tables and how they link |
| `seed_validation.sql` | Checks that the data loaded correctly |
| `seed_validation.txt` | The output of those checks |

**What I did:**
- Built the tables in dependency order: parents (customer, employee) before children (account, complaint).
- Extended the supplied setup script with extra rules the data already follows:
  - an account must belong to the complaint's customer
  - balances must add up
  - only allowed statuses and priorities can be used
  - a closed item needs a closed date
- Loaded the sample data: 10 customers, 10 accounts, 30 complaints, and 10 rows in most other tables.
- Ran the validation checks: row counts, broken links, and rule checks.

**Handover:** all later SQL exercises and the 2.4.2 repositories use these tables. 2.5.1 rebuilds them from this file.

## 2.1.2 Basic SQL

**Goal:** answer simple business questions with clear, correct queries.

| File | What it is |
|---|---|
| `query_exploration.md` | What's in the database before writing queries: row counts, empty values, surprises |
| `basic_queries.sql` | Queries Q1–Q8 plus checks V01–V07 |
| `basic_query_results.csv` | The check results |
| `query_notes.md` | Why each query is written the way it is |

**Results:**

| Question | Answer |
|---|---|
| Open complaints | 29 |
| High-priority unresolved complaints | 12 |
| Complaints for customer `CUS009` | 3 |
| Complaints opened 1–14 Feb 2025 | 10 |
| Closed complaints with a missing closed date | 0, as expected |

The other questions count complaints by status (4) and category (7), and list the 10 most recent.

**Key decision:** "open" means the status is *not* `RESOLVED` or `CLOSED`, so In Progress, Under Review, Escalated and the rest count as open. Every later exercise uses this rule.

## 2.2.1 SQL joins

**Goal:** combine complaint, customer and account data without losing or repeating complaints.

| File | What it is |
|---|---|
| `join_queries.sql` | Join queries J1–J3 |
| `complaint_analyst_view.sql` | `complaint_analyst_view`: one row per complaint, with only the fields an analyst needs |
| `join_validation.md` | Which join was used where, and why, with before/after counts |
| `missing_account_test.md` | Proof that complaints with no account aren't lost |

**What I did:**
- Used an inner `JOIN` to customer (every complaint has one) and a `LEFT JOIN` to account. 3 complaints (CMP023, CMP029, CMP030) have no account, and an inner join would silently drop them.
- Checked the counts at each step: 30 → 30 → 30. The wrong join gives 27, which shows the problem.
- The view leaves out personal and sensitive data: names, email, phone, account number, balance. I justified each field that's kept.

## 2.2.2 SQL metrics

**Goal:** turn the analyst view into business metrics with exact definitions.

| File | What it is |
|---|---|
| `complaint_metrics.sql` | Metric queries M1–M7, checks V01–V06, and a summary query |
| `complaint_metrics.csv` | The summary: one row per metric value |
| `metric_definitions.md` | What each metric counts, what it leaves out, and its caveats |

**What I did:**
- Defined each metric: complaint count, distinct customers, backlog, backlog age, escalated backlog and average resolution days.
- Used a fixed as-of date (**2025-02-24**, the newest complaint) so the numbers don't change with today's date.
- Left open cases out of resolution time, and showed a blank instead of 0 when nothing can be measured.
- Counted escalations from review decisions as well as status, because status alone misses CMP009.
- Noted that distinct customer counts don't add up across groups.

**Handover:** 2.3.1 and 2.4.1 use the same definitions.

## 2.3.1 Advanced SQL

**Goal:** use advanced SQL features on real complaint questions.

| File | What it is |
|---|---|
| `advanced_queries.sql` | The queries and 8 checks |
| `advanced_query_results.csv` | The check results |
| `advanced_sql_explanation.md` | What each query does and why |

| Question | SQL feature |
|---|---|
| Unresolved complaints by age (0–7, 8–30, 31+ days) | `CASE` |
| Repeat complainants | CTE (`WITH`) |
| Latest status of each complaint | `ROW_NUMBER()` |
| Customers ranked by complaint count | `RANK()` |

All 8 checks pass.

## 2.3.2 SQL vs RAG (retrieval design)

**Goal:** decide which questions should be answered with SQL, with document search (RAG), or with both, and how to keep each one safe.

| File | What it is |
|---|---|
| `sql_rag_decision_matrix.csv` | 11 questions, each classed as SQL, RAG, hybrid or tool action, with the reason, data sources and whether a human must approve |
| `hybrid_flow_designs.md` | 5 step-by-step flows that use SQL for facts and documents for policy |
| `retrieval_risks.md` | What can go wrong with each approach, the controls, approval points and tests |

**Key decisions:**
- **SQL** for exact facts and counts.
- **RAG** for policy wording, quoted with a citation.
- **Never** let an AI auto-approve a high-risk case or delete records.
- Wrong IDs (like `C0001` instead of `CUS001`) must say "customer not found" instead of "0 complaints".

## 2.4.1 Python analysis

**Goal:** a simple Python script that checks a complaints CSV and writes an honest summary.

| File | What it is |
|---|---|
| `complaint_analysis.py` | The script. Standard Python only, no extra libraries |
| `complaint_analysis_output.csv` | All the calculated numbers |
| `complaint_analysis_summary.md` | A plain-English summary for managers |
| `failure_test_results.md` | What happens with a missing file, a missing column, an empty file and incomplete rows |
| `complaints.csv` | The shared input data (120 complaints) |

**How to run:**

```bash
cd 2_4_1_PythonAnalysis
python3 complaint_analysis.py complaints.csv
```

**What it does:**
1. Checks the file exists and has the 6 required columns.
2. Counts empty values.
3. Skips bad rows with a warning.
4. Counts complaints by status and category, finds the biggest category, and works out the average days to close per category.
5. Writes the CSV and the summary.

**Results:**
- 120 complaints: 86 open, 34 closed.
- Biggest category: Mortgage Servicing, 31 complaints (25.8%).
- Closed cases took 10.1 days on average.

The summary says clearly what the data can't show: no trends and no causes.

**What I changed:** simplified the code to beginner style, removed FastAPI, and removed a test file that isn't a deliverable.

## 2.4.2 Repositories

**Goal:** one safe, reusable way for Python to get data from the database, so later code never writes its own SQL.

| File | What it is |
|---|---|
| `src/data/database_manager.py` | Opens and closes the connection. Saves if a query worked, undoes it if it failed, and never shows the password |
| `src/data/customer_repository.py` | `get_by_id` |
| `src/data/account_repository.py` | `get_for_customer` |
| `src/data/complaint_repository.py` | `get_by_id`, `get_for_customer`, `create` |
| `tests/test_repositories.py` | 20 tests: valid, missing and failure cases |
| `README.md` | Setup, example calls, who does what, and where SQL is allowed |

**How to run the tests:**

```bash
cd 2_4_2_Repositories
set -a; source ../.env; set +a
../.venv/bin/python -m unittest discover -s tests -v
```

**What I did:**
- Every query uses `%s` placeholders, so text like `x' OR '1'='1` can't break in.
- Bad data is rejected by the database and undone: an invalid priority, a duplicate ID, another customer's account.
- It reads only from the database, never from CSV files.
- Simplified the code to beginner style: plain classes and `try`/`except`/`finally`.

**Result:** 20 of 20 tests pass against the local database, and the tests leave no test rows behind.

**Needs:** PostgreSQL, `psycopg2` (installed in `.venv`), and the `DB_*` settings in `.env`.

## 2.5.1 Database seeder

**Goal:** one command that rebuilds the database from nothing and loads the shared CSV data, so nobody has to write SQL by hand.

| File | What it is |
|---|---|
| `seed_database.py` | The command: builds the tables, checks the CSVs, loads them, then checks the result |
| `seed_run_log.txt` | Every stage, count and error from each run |
| `integrity_report.txt` | Row counts (file vs database) and orphan checks |
| `README_setup.md` | Prerequisites, the one command, expected output and troubleshooting |

**What it does:**
1. Builds the 2.1.1 tables. It only wipes existing tables if you add `--reset`.
2. Checks every CSV has the right headers, then loads customers, accounts, complaints and service requests. Any row with a broken link is rejected with a reason.
3. If anything critical fails, **everything is undone**, so the database is never half-loaded.
4. Compares counts and checks for orphan rows.

**Result:** a test run into a throwaway database loaded 100 customers, 150 accounts, 120 complaints and 60 service requests, with nothing rejected and all 8 orphan checks passing. 13 of 13 tests pass.

**Still to do:**
- **The data doesn't fit the tables.** The shared CSVs don't fully match the 2.1.1 tables. For example, they have no account numbers, no account open dates and no complaint text, and some values are worded differently (`Active` vs `ACTIVE`). Right now stand-in values fill those gaps.
- **The plan:**
  - Keep the 2.1.1 design and translate the obvious values.
  - Label and document every stand-in.
  - Remove the files that aren't deliverables.
  - Simplify the code.
  - Seed into a separate database so the `--reset` option can't wipe the one 2.4.2 uses.

**Handover:** 2.5.2 deletes and rebuilds the environment using only this utility and its README.

---

## Setup (for the Python exercises)

| Item | Needed for | Notes |
|---|---|---|
| Python 3.9+ | 2.4.1, 2.4.2, 2.5.1 | 2.4.1 needs nothing else |
| PostgreSQL | 2.1.1–2.3.1, 2.4.2, 2.5.1 | Running locally on port 5432 |
| `.venv` | 2.4.2, 2.5.1 | Holds `psycopg2`, the library Python uses to talk to PostgreSQL |
| `.env` | 2.4.2, 2.5.1 | Your database settings: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`. Never committed |
| `.gitignore` | Everything | Keeps `.env`, `.venv`, `.vscode`, `__pycache__` and `.DS_Store` off GitHub |

## Rules used across every exercise

- **Open** means the status is not `RESOLVED` or `CLOSED`.
- **Unknown is not zero:** if nothing can be measured, show blank or "unknown", never 0.
- **No personal data** in analyst views or outputs.
- **SQL always uses placeholders** for values, never pasted-in text.
- **Errors are reported, not hidden:** bad rows are skipped or rejected with a reason.
- **No trend claims** from a single snapshot of data.
