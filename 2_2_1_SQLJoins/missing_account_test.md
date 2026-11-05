# Missing Account Test

Week 2 | Exercise 2.2.1 · Step 4

**What we are testing:** a complaint with no `account_id` must still show up after the joins. It must not disappear.

**Test data:** 3 complaints have no account.

| Complaint | Customer | Why there is no account |
|---|---|---|
| CMP023 | CUS006 | A general service complaint |
| CMP029 | CUS009 | Identity theft, not tied to one account |
| CMP030 | CUS010 | No response to an inquiry |

## Test 1: the join query (LEFT JOIN account)

```sql
SELECT c.complaint_id,
       c.customer_id,
       c.account_id,
       a.account_type,
       c.category,
       c.status
FROM complaint c
JOIN customer cu ON c.customer_id = cu.customer_id
LEFT JOIN account a ON c.account_id = a.account_id
WHERE c.account_id IS NULL
ORDER BY c.complaint_id;
```

**Result:**

```
 complaint_id | customer_id | account_id | account_type |     category     | status
--------------+-------------+------------+--------------+------------------+--------
 CMP023       | CUS006      | NULL       | NULL         | Customer Service | OPEN
 CMP029       | CUS009      | NULL       | NULL         | Fraud Claim      | OPEN
 CMP030       | CUS010      | NULL       | NULL         | Service Delay    | OPEN
(3 rows)
```

**PASS.** All 3 complaints are there. Their account fields are NULL, which is correct.

## Test 2: the analyst view

```sql
SELECT complaint_id, customer_id, account_id, account_type, has_account, is_open
FROM complaint_analyst_view
WHERE account_id IS NULL
ORDER BY complaint_id;
```

**Result:**

```
 complaint_id | customer_id | account_id | account_type | has_account | is_open
--------------+-------------+------------+--------------+-------------+---------
 CMP023       | CUS006      | NULL       | NULL         | f           | t
 CMP029       | CUS009      | NULL       | NULL         | f           | t
 CMP030       | CUS010      | NULL       | NULL         | f           | t
(3 rows)
```

**PASS.** The view keeps them too. `has_account = f` (false) makes this easy to filter.

## Test 3: negative test (what goes wrong with INNER JOIN)

```sql
SELECT COUNT(*) AS rows_with_inner_join
FROM complaint c
JOIN account a ON c.account_id = a.account_id
WHERE c.complaint_id IN ('CMP023', 'CMP029', 'CMP030');
```

**Result:** `0`

**PASS (as expected).** With an INNER JOIN, all 3 complaints disappear. This proves the LEFT JOIN is needed, not just a style choice.

## Summary

| Test | Expected | Actual | Result |
|---|---|---|---|
| LEFT JOIN query keeps no-account complaints | 3 | 3 | PASS |
| Analyst view keeps no-account complaints | 3 | 3 | PASS |
| INNER JOIN loses them (negative test) | 0 | 0 | PASS |

The same idea is checked in J3 of `join_queries.sql` (LEFT JOIN keeps 30, INNER JOIN drops to 27) and check C02 in `complaint_analyst_view.sql`.

**To reproduce:** run the queries above in psql or the Supabase SQL Editor (run `complaint_analyst_view.sql` first for Test 2). In Supabase, NULLs show as empty cells or `NULL`.