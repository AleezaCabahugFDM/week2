# Query Notes: SQL Reasoning and Issues

Week 2 | Exercise 2.1.2 · Step 4

These notes explain the main decisions in `basic_queries.sql`. Each choice is checked by a validation query (V01–V12), and all 12 checks pass.

---

## 1. Filter choice: what counts as an "open" complaint

```sql
WHERE c.status NOT IN ('RESOLVED', 'CLOSED')
```

**Business meaning:** a complaint is open while someone still has work to do on it. That includes `OPEN`, `IN_PROGRESS`, `UNDER_REVIEW`, `PENDING_APPROVAL`, `CHANGES_REQUESTED` and `ESCALATED`.

**Why this filter:** filtering on `status = 'OPEN'` would give 19, which misses 10 complaints that are being worked on (`IN_PROGRESS`, `UNDER_REVIEW`). Listing the two *finished* statuses is shorter and stays correct if a new in-progress status is added later.

**Result:** 29 open complaints out of 30.
**Check:** V02 confirms open + closed/resolved = 30.

## 2. Date condition: half-open date range

```sql
WHERE c.created_at >= :'start_date'::date
  AND c.created_at <  :'end_date'::date
```

**Why:** `created_at` is a `TIMESTAMP` that includes a time of day. The obvious version has a bug:

```sql
-- WRONG: '2025-01-31' means midnight, so a complaint at 2025-01-31 14:00 is missed
WHERE created_at BETWEEN '2025-01-01' AND '2025-01-31'
```

The half-open range (start included, end excluded) catches every timestamp in the period. Back-to-back ranges also never overlap or leave a gap: Jan 1 → Feb 1, then Feb 1 → Mar 1.

**Checks:**
- **V06 (boundary):** CMP011, created 2025-02-01 09:15, is included in a February range.
- **V07:** the January and February ranges add up to all 30 complaints.

**"Recent" uses an as-of date, not today.** The seed data is from early 2025, so `now() - INTERVAL '7 days'` returns nothing. Q17 and Q20 measure from an `as_of_date` parameter (default `2025-02-24`, the newest complaint). In a live system, pass today's date.

## 3. NULL handling: complaints with no account

Three complaints (CMP023, CMP029, CMP030) have `account_id = NULL` on purpose.

**Choice:** find them with `IS NULL` (Q14) and label them explicitly instead of letting them vanish (Q15):

```sql
CASE WHEN c.account_id IS NULL THEN 'No account' ELSE 'Linked to account' END
```

**Why it matters:** in SQL, any comparison with NULL is "unknown", not true. So this query silently drops the three NULL rows:

```sql
WHERE account_id <> 'ACC001'      -- returns 23 rows, not 26
```

When NULL rows should be kept, use `IS DISTINCT FROM`, which treats NULL as a normal value:

```sql
WHERE account_id IS DISTINCT FROM 'ACC001'   -- returns 26 rows
```

**Check:** V05 proves the difference is exactly the 3 NULL rows. V04 confirms linked + unlinked = 30.

The same idea appears in Q21. `COALESCE(c.assigned_employee_id, '(unassigned)')` shows unassigned complaints as a visible group instead of a blank. There are none today, but the query is ready for them.

## 4. Parameters (user-supplied values)

Values a user would type (customer ID, priority, category, dates, keyword, limits) are **parameters**, not hard-coded:

```sql
WHERE c.customer_id = :'customer_id'
```

- `:'name'` makes psql insert the value as a **safely quoted literal**, so input like `CUS001' OR '1'='1` is treated as text, not SQL. **V09** proves this returns 0 rows.
- Defaults are set at the top with `\if :{?name} \else \set name ... \endif`, so the file runs on its own. Any value can be overridden: `psql -v customer_id=CUS003 -f basic_queries.sql`.
- In the API (later exercises) these become bind placeholders such as `$1` (psycopg uses `%s`), never string concatenation.

## 5. Other choices

- **Explicit columns, never `SELECT *`.** The output stays stable if columns are added later, and the API knows exactly what comes back.
- **Table aliases** (`c` for complaint, `f` for fee, `sr` for service_request) on every column, so the queries can be extended into joins in 2.2.1 without renaming.
- **Priority ordering.** Sorting `priority` alphabetically gives Critical, High, Low, Medium, which is wrong. A `CASE` maps it to 1–4 for a true urgency order.
- **Deterministic ordering.** Every list has an `ORDER BY` with a tie-breaker (usually the ID), so results are the same on every run and the CSV can be compared between runs.
- **Exact values are case-sensitive.** `priority = 'high'` returns nothing (V10). Keyword search (Q10) uses `ILIKE` because users type in any case.

## 6. Dialect-specific (PostgreSQL / psql) syntax

| Syntax | Used in | Standard SQL / other databases |
|---|---|---|
| `:'name'`, `:name`, `\set`, `\if` | Parameters | psql only. Use `?` or `$1` placeholders from application code. |
| `ILIKE` | Q10 | PostgreSQL only. Elsewhere: `LOWER(col) LIKE LOWER(?)`. |
| `COUNT(*) FILTER (WHERE ...)` | Q07, Q12 | SQL standard but not in MySQL/SQL Server. Elsewhere: `SUM(CASE WHEN ... THEN 1 ELSE 0 END)`. |
| `::date` cast | Q16, Q17, Q20 | Standard form is `CAST(x AS DATE)`. |
| `INTERVAL '1 day'` | Q17 | Syntax varies (e.g. SQL Server `DATEADD`). |
| `date - date` returns whole days | Q20, Q23 | PostgreSQL-specific. Elsewhere: `DATEDIFF`. |
| `DATE_TRUNC`, `TO_CHAR` | Q19 | PostgreSQL/Oracle. Varies elsewhere. |
| `IS DISTINCT FROM` | V05 | SQL standard. Not in MySQL (use `NOT (a <=> b)`). |
| `LIMIT` | Q18 | Not in SQL Server (`TOP`) or Oracle (`FETCH FIRST`). |
| `$v$...$v$` dollar quoting | V09 | PostgreSQL only. Used so the test string can contain quotes. |

## 7. Issues and limitations

1. **The question list was not provided.** `basic_query_questions.md` (named in the brief) was not available, so the 23 questions were written from the scenario: open cases, priorities, categories, customers and recent activity. If the official list differs, map or add queries to match it.
2. **Status-history timestamps are not usable.** All 30 `status_timestamp` values equal the time the setup script ran. Recent activity uses `complaint.created_at` instead.
3. **Almost everything is open.** 29 of 30 complaints are open and none are `RESOLVED`, so "open vs closed" comparisons are lopsided.
4. **Q22 returns every fee** because no fee is marked reversed, even though some customers were told their fee was refunded (a seed-data issue documented in 2.1.1).
5. **Results were not edited.** Where output looked odd, the cause was traced to the data (see `query_exploration.md`, section 5), not fixed in the CSV.

## 8. How the results were produced

```bash
psql -d complaints -f basic_queries.sql            # runs all 23 queries + 12 checks
```

`basic_query_results.csv` holds one line per result row:

- `query_id`
- `question`
- `parameters_used`
- `row_number`
- `result`, written as `column=value` pairs
- `check_status`, filled in for V01–V12

It was produced with the default parameter values shown at the top of `basic_queries.sql`.