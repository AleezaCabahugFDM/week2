# Query Notes

Week 2 | Exercise 2.1.2 · Step 4

These notes explain the choices in `basic_queries.sql`. The checks at the end of the file (V01–V07) all pass. Their results are in `basic_query_results.csv`.

## Question → query map

| # | Question | Query | Rows returned |
|---|---|---|---|
| 1 | List all open complaints. | Q1 | 29 |
| 2 | List high-priority unresolved complaints. | Q2 | 12 |
| 3 | Count complaints by status. | Q3 | 4 statuses |
| 4 | Count complaints by category. | Q4 | 7 categories |
| 5 | Show complaints for a supplied customer ID. | Q5 (`CUS009`) | 3 |
| 6 | Show complaints opened within a supplied date range. | Q6 (2025-02-01 to 2025-02-14) | 10 |
| 7 | List closed complaints where date_closed is missing (expected zero). | Q7 | **0, as expected** |
| 8 | Show the ten most recently opened complaints. | Q8 | 10 |

---

## 1. What "open" means (Q1, Q2)

```sql
WHERE status NOT IN ('RESOLVED', 'CLOSED')
```

A complaint is open while someone still has work to do on it. Using `status = 'OPEN'` would only find 19 and miss the 10 that are `IN_PROGRESS` or `UNDER_REVIEW`.

**High priority (Q2)** is `priority IN ('High', 'Critical')`. Critical is more urgent than High, so it is included. Q2 returns 3 Critical + 9 High = 12.

Values are case-sensitive: `priority = 'high'` finds nothing (check V07).

## 2. Date range (Q6)

```sql
WHERE created_at >= '2025-02-01'
  AND created_at < '2025-02-15'
```

`created_at` has a time of day. `BETWEEN '2025-02-01' AND '2025-02-14'` would stop at midnight on the 14th and miss complaints made later that day. Writing "before the 15th" includes the whole of the 14th.

Check V06 proves this: CMP030 was made on 2025-02-24 at 13:15 and is found by a one-day range for that date.

## 3. NULLs and missing values

**Q7.** The `complaint` table has no `date_closed` column. A complaint is closed in `complaint_status_history` (a row with `new_status` RESOLVED or CLOSED). So Q7 looks for closed complaints that have **no** such history row:

```sql
WHERE status IN ('RESOLVED', 'CLOSED')
  AND complaint_id NOT IN (
      SELECT complaint_id FROM complaint_status_history
      WHERE new_status IN ('RESOLVED', 'CLOSED'))
```

The only closed complaint (CMP005) has its history row, so the result is 0, as expected.

**Q5.** CMP029 (CUS009) has no account (`account_id` is NULL). Q5 only filters on `customer_id`, so it still returns all 3 of CUS009's complaints (check V04). A customer that does not exist returns 0 rows, not an error (check V05).

## 4. Supplied values (Q5, Q6)

The customer ID and dates are typed straight into the query so it is easy to read and run. To try another value, change it in the `WHERE` line. In the API (2.4.2) the value is passed as a placeholder (`%s`), never pasted into the SQL text.

## 5. Other choices

- `SELECT *` keeps the queries short. All columns of `complaint` are shown.
- Every list has an `ORDER BY` so the order is the same each time.
- Q8 uses `ORDER BY created_at DESC LIMIT 10`. No two complaints share a timestamp, so the ten rows are always the same.

## 6. PostgreSQL-specific syntax

| Syntax | Used in | Other databases |
|---|---|---|
| `LIMIT 10` | Q8 | SQL Server uses `TOP 10`; standard SQL is `FETCH FIRST 10 ROWS ONLY`. |
| Comparing a timestamp to `'2025-02-01'` | Q6 | Most databases convert the text automatically; some need `CAST('2025-02-01' AS DATE)`. |

## 7. Issues and limitations

1. **No `date_closed` column.** Q7 uses the status history instead.
2. **Almost everything is open.** 29 of 30 complaints are open, so Q1 returns nearly the whole table and Q7 has only one closed complaint to look at.
3. **Results were not edited.** `basic_query_results.csv` comes straight from running the checks.

## 8. How to run

```bash
psql -d complaints -f basic_queries.sql
```

In Supabase, paste the file into the SQL Editor. Running the whole file shows only the last result, which is the check table. To see one question's answer, highlight that query and press **Run**.

`basic_query_results.csv` has one row per check: `check_id`, `check_name`, `expected`, `actual`, `result` (PASS/FAIL).
