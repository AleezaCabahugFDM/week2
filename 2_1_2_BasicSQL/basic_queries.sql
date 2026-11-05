-- basic_queries.sql
-- Week 2 | Exercise 2.1.2 - Query Complaint Data
-- Run in psql or the Supabase SQL Editor:
--   psql -d complaints -f basic_queries.sql
--
-- "Open" means the status is not RESOLVED or CLOSED.
-- "High priority" means High or Critical.


-- Q1. List all open complaints. (29 rows)
SELECT *
FROM complaint
WHERE status NOT IN ('RESOLVED', 'CLOSED')
ORDER BY created_at;


-- Q2. List high-priority unresolved complaints. (12 rows)
SELECT *
FROM complaint
WHERE priority IN ('High', 'Critical')
  AND status NOT IN ('RESOLVED', 'CLOSED')
ORDER BY created_at;


-- Q3. Count complaints by status. (4 rows)
SELECT status, COUNT(*) AS complaint_count
FROM complaint
GROUP BY status
ORDER BY complaint_count DESC;


-- Q4. Count complaints by category. (7 rows)
SELECT category, COUNT(*) AS complaint_count
FROM complaint
GROUP BY category
ORDER BY complaint_count DESC;


-- Q5. Show complaints for a supplied customer ID. (3 rows)
-- Change 'CUS009' to look at another customer.
-- In the API this value is passed as a placeholder (%s), not typed in.
SELECT *
FROM complaint
WHERE customer_id = 'CUS009'
ORDER BY created_at;


-- Q6. Show complaints opened within a supplied date range. (10 rows)
-- Range: 1 Feb 2025 to 14 Feb 2025.
-- created_at has a time, so "up to 14 Feb" is written as "before 15 Feb".
SELECT *
FROM complaint
WHERE created_at >= '2025-02-01'
  AND created_at < '2025-02-15'
ORDER BY created_at;


-- Q7. List closed complaints where date_closed is missing. (0 rows expected)
-- There is no date_closed column. A complaint is closed in the status
-- history table, so a closed complaint with no RESOLVED/CLOSED history row
-- has a missing closed date.
SELECT *
FROM complaint
WHERE status IN ('RESOLVED', 'CLOSED')
  AND complaint_id NOT IN (
      SELECT complaint_id
      FROM complaint_status_history
      WHERE new_status IN ('RESOLVED', 'CLOSED')
  );


-- Q8. Show the ten most recently opened complaints. (10 rows)
SELECT *
FROM complaint
ORDER BY created_at DESC
LIMIT 10;


-- CHECKS
-- One table: each row is a check with the expected and actual answer.
-- In Supabase, running the whole file shows this table.
SELECT check_id, check_name, expected, actual,
       CASE WHEN actual = expected THEN 'PASS' ELSE 'FAIL' END AS result
FROM (
    SELECT 'V01' AS check_id, 'Total complaints' AS check_name,
           30 AS expected, COUNT(*) AS actual
    FROM complaint

    UNION ALL
    SELECT 'V02', 'Open complaints (Q1)', 29, COUNT(*)
    FROM complaint WHERE status NOT IN ('RESOLVED', 'CLOSED')

    UNION ALL
    SELECT 'V03', 'High-priority unresolved complaints (Q2)', 12, COUNT(*)
    FROM complaint WHERE priority IN ('High', 'Critical') AND status NOT IN ('RESOLVED', 'CLOSED')

    UNION ALL
    SELECT 'V04', 'CUS009 complaint with no account is still found (Q5)', 1, COUNT(*)
    FROM complaint WHERE customer_id = 'CUS009' AND account_id IS NULL

    UNION ALL
    SELECT 'V05', 'A customer that does not exist returns nothing', 0, COUNT(*)
    FROM complaint WHERE customer_id = 'CUS999'

    UNION ALL
    SELECT 'V06', 'Complaint made at 13:15 on the last day is included (CMP030)', 1, COUNT(*)
    FROM complaint WHERE created_at >= '2025-02-24' AND created_at < '2025-02-25'

    UNION ALL
    SELECT 'V07', 'Values are case-sensitive: ''high'' is not a priority', 0, COUNT(*)
    FROM complaint WHERE priority = 'high'
) AS checks
ORDER BY check_id;
