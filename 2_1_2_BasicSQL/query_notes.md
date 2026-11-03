# Query Notes: SQL Reasoning and Issues

Week 2 | Exercise 2.1.2 · Step 4

These notes explain the decisions in `basic_queries.sql`. Every choice below is checked by a validation query (V01–V14 at the end of the file), and all 14 checks pass.

## Question → query map

| # | Question (`basic_query_questions.md`) | Query | Rows returned | Proven by |
|---|---|---|---|---|
| 1 | List all open complaints. | Q1 | 29 | V01 |
| 2 | List high-priority unresolved complaints. | Q2 | 12 | V02 |
| 3 | Count complaints by status. | Q3 | 4 statuses | V03 |
| 4 | Count complaints by category. | Q4 | 7 categories | V04 |
| 5 | Show complaints for a supplied customer ID. | Q5 (`CUS009`) | 3 | V05, V06, V07 |
| 6 | Show complaints opened within a supplied date range. | Q6 (2025-02-01 to 2025-02-14) | 10 | V08, V09, V10 |
| 7 | List closed complaints where date_closed is missing (expected zero). | Q7 | **0, as expected** | V11, V12 |
| 8 | Show the ten most recently opened complaints. | Q8 | 10 | V13 |

---

## 1. Filter choice: what counts as "open" / "unresolved" (Q1, Q2)

```sql
WHERE c.status NOT IN ('RESOLVED', 'CLOSED')
```

**Business meaning:** a complaint is open while someone still has work to do on it: `OPEN`, `IN_PROGRESS`, `UNDER_REVIEW`, `PENDING_APPROVAL`, `CHANGES_REQUESTED` or `ESCALATED`. "Open" (Q1) and "unresolved" (Q2) mean the same thing.

**Why this filter:** `status = 'OPEN'` would return only 19 and miss the 10 complaints that are being worked on (`IN_PROGRESS`, `UNDER_REVIEW`). Listing the two finished statuses is shorter and stays correct if another in-progress status is added later.

**High priority (Q2)** is `priority IN ('High', 'Critical')`. Critical is above High, so leaving it out would hide the three most urgent complaints (all fraud claims). Q2 returns 3 Critical + 9 High = 12.

**Checks:** V01 shows open + closed = 30. V02 shows Q2 equals an independent count of open High/Critical complaints. V14 shows that exact values are case-sensitive: `priority = 'high'` returns nothing.

## 2. Date condition: inclusive dates applied as a half-open range (Q6)

```sql
WHERE c.created_at >= p.start_date
  AND c.created_at <  p.end_date + 1
```

**Business meaning:** an analyst asking for "1 to 14 February" expects every complaint made on 14 February to be included, whatever the time.

**Why:** `created_at` is a `TIMESTAMP` with a time of day. The obvious version has a bug:

```sql
-- WRONG: '2025-02-14' means midnight, so a complaint at 2025-02-14 11:00 is missed
WHERE c.created_at BETWEEN '2025-02-01' AND '2025-02-14'
```

Adding one day to the end date and using `<` catches every timestamp on the last day. Back-to-back ranges never overlap or leave a gap.

**Checks:**
- **V08 (boundary):** CMP030 was created 2025-02-24 13:15. A range of 2025-02-24 to 2025-02-24 finds it; `BETWEEN` on the same dates would return 0.
- **V09 (boundary):** 1–31 January plus 1–28 February covers all 30 complaints exactly.
- **V10 (negative):** a start date after the end date returns 0 rows, not an error.

## 3. NULL handling

### Q7: a missing closure date is a NULL from a LEFT JOIN

The `complaint` table has **no `date_closed` column**. A complaint's closure is recorded only as the status-history row that moved it to `RESOLVED` or `CLOSED`, so that row's `status_timestamp` is used as the closed date:

```sql
WITH closure AS (
    SELECT h.complaint_id, MAX(h.status_timestamp) AS date_closed
    FROM   complaint_status_history AS h
    WHERE  h.new_status IN ('RESOLVED', 'CLOSED')
    GROUP  BY h.complaint_id
)
SELECT ...
FROM   complaint AS c
LEFT   JOIN closure AS cl ON cl.complaint_id = c.complaint_id
WHERE  c.status IN ('RESOLVED', 'CLOSED')
  AND  cl.date_closed IS NULL;
```

**Why a LEFT JOIN:** an inner join would drop exactly the rows the question is looking for (closed complaints with no closure record). The LEFT JOIN keeps them, and their `date_closed` comes back NULL. The test must be `IS NULL`; `= NULL` is never true.

**Checks:**
- **V11:** the result is 0, as the question expects. The one closed complaint (CMP005) has its closure row.
- **V12 (negative):** a zero result could also mean the query is broken. V12 runs the same logic on a test `CLOSED` complaint held in memory (not inserted) and confirms it **is** flagged.

The schema was not changed to add a `date_closed` column, so the table and field names that 2.2.1 relies on stay the same.

### Q5: complaints with no account are still returned

CMP029 (CUS009) has `account_id = NULL`. Q5 filters only on `customer_id`, so it returns all 3 of CUS009's complaints, with `account_id` shown as NULL (**V05**). A filter such as `account_id <> 'ACC001'` would silently drop NULL rows, because any comparison with NULL is unknown, not true. Use `IS DISTINCT FROM` when NULL rows must be kept.

## 4. Parameters (user-supplied values: Q5, Q6)

```sql
WITH params AS (
    SELECT 'CUS009'::varchar AS customer_id          -- <-- supplied value
)
SELECT ... FROM complaint AS c
JOIN   params AS p ON c.customer_id = p.customer_id
```

- The supplied value appears **once**, in a `params` CTE at the top of the query, typed (`::varchar`, `DATE '...'`). The query body refers only to `p.customer_id`, `p.start_date`, `p.end_date`.
- This is plain SQL, so it runs in both psql and the Supabase SQL Editor. psql variables (`\set`, `:'name'`) were used in an earlier draft but fail in Supabase with `syntax error at or near "\"`.
- In the API (later exercises) the `params` CTE is replaced by bind placeholders: `WHERE c.customer_id = $1` (psycopg: `%s`). Values are never concatenated into the SQL string.
- **V07** shows that an injection-style value (`CUS001' OR '1'='1`) is treated as plain text and matches nothing. **V06** shows that an unknown customer returns 0 rows, not an error.

## 5. Other choices

- **Explicit columns, never `SELECT *`.** The output stays stable if columns are added later, and the API knows exactly what comes back.
- **Table aliases** (`c` complaint, `h` status history, `p` params) on every column, so the queries extend into the joins in 2.2.1 without renaming.
- **Priority ordering.** Sorting `priority` alphabetically gives Critical, High, Low, Medium. A `CASE` maps it to 1–4 for true urgency order (Q1, Q2).
- **Deterministic ordering.** Every list has an `ORDER BY` with `complaint_id` as the final tie-breaker, so results are identical on every run and the CSV can be compared between runs. In Q8 this decides the 10th row if two complaints share a timestamp. There are no ties in the current data, and **V13** proves no complaint outside the ten is newer.
- **Checks return one table.** V01–V14 are a single `SELECT`, so all of them show in the Supabase editor, which displays only the last result.

## 6. Dialect-specific (PostgreSQL) syntax

| Syntax | Used in | Standard SQL / other databases |
|---|---|---|
| `'CUS009'::varchar` cast | Q5 | Standard form is `CAST('CUS009' AS VARCHAR(20))`. |
| `DATE '2025-02-01'` literal | Q6, V08–V10 | SQL standard; SQL Server uses `CAST('2025-02-01' AS DATE)`. |
| `date + 1` (adds one day) | Q6, V08–V10 | PostgreSQL-specific. Standard: `date + INTERVAL '1' DAY`; SQL Server `DATEADD(day, 1, d)`. |
| `LIMIT 10` | Q8 | Not in SQL Server (`TOP 10`) or Oracle; standard is `FETCH FIRST 10 ROWS ONLY`. |
| `$v$...$v$` dollar quoting | V07 | PostgreSQL only; used so the test string can contain quotes. |
| `WITH ... (VALUES ...)` | V12 | Standard, but some databases need a `SELECT` per row instead of `VALUES`. |
| Bind placeholder `$1` | API (later) | psycopg uses `%s`, JDBC/ODBC use `?`. |

## 7. Issues and limitations

1. **No `date_closed` column.** Q7 uses the status-history closure row instead (section 3). If a `date_closed` column is added to `complaint` later, Q7 should be changed to `WHERE status IN ('RESOLVED','CLOSED') AND date_closed IS NULL`, and the source specification updated with it.
2. **Closure timestamps are load time.** CMP005's `date_closed` is the moment the setup script ran (2026), not a real 2025 date, because the seed does not supply history timestamps. That is enough for Q7 (present vs missing) but not for measuring time to close.
3. **Almost everything is open.** 29 of 30 complaints are open and none are `RESOLVED`, so Q1 returns nearly the whole table and Q7 has only one closed complaint to test. V12 covers the case the real data cannot.
4. **Representative parameters.** The CSV uses `customer_id = CUS009`, which includes a NULL-account complaint, and 2025-02-01 to 2025-02-14, a range that starts exactly on the first February complaint (CMP011, 09:15).
5. **Results were not edited.** `basic_query_results.csv` was exported directly from a run of `basic_queries.sql`. Where output looked odd, the cause was traced to the data (`query_exploration.md`, section 5), not corrected in the CSV.

## 8. How the results were produced

```bash
psql -d complaints -v ON_ERROR_STOP=1 -f basic_queries.sql   # Q1–Q8, then the V01–V14 table
```

In Supabase, open the SQL Editor, paste the file, highlight one query and press **Run** (running the whole file shows the check table).

`basic_query_results.csv` holds one line per result row:

| Column | Content |
|---|---|
| `query_id` | Q1–Q8, or V01–V14 |
| `question` | The question from `basic_query_questions.md`, or the check name |
| `parameters_used` | Supplied values (Q5, Q6) |
| `row_number` | 1..n; Q7 has one line with row_number 0 recording "0 rows returned - expected" |
| `result` | `column=value` pairs; NULL written as `NULL` |
| `check_status` | `PASS` / `FAIL` for V01–V14, and `PASS` for Q7's expected zero |