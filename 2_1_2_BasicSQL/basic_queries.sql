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
-- Each check returns one number. The expected answer is in the comment.

-- V01. Total complaints (expected 30)
SELECT COUNT(*) FROM complaint;

-- V02. Open + closed = total (expected 29 + 1 = 30)
SELECT COUNT(*) FROM complaint WHERE status NOT IN ('RESOLVED', 'CLOSED');
SELECT COUNT(*) FROM complaint WHERE status IN ('RESOLVED', 'CLOSED');

-- V03. Complaints with no account are still found for CUS009 (expected 1)
SELECT COUNT(*) FROM complaint WHERE customer_id = 'CUS009' AND account_id IS NULL;

-- V04. A customer that does not exist returns nothing (expected 0)
SELECT COUNT(*) FROM complaint WHERE customer_id = 'CUS999';

-- V05. A complaint made late on the last day is included (expected 1, CMP030 at 13:15)
SELECT COUNT(*) FROM complaint WHERE created_at >= '2025-02-24' AND created_at < '2025-02-25';

-- V06. Values are case-sensitive: 'high' is not a priority (expected 0)
SELECT COUNT(*) FROM complaint WHERE priority = 'high';
