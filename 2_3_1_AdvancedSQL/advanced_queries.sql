-- advanced_queries.sql
-- Week 2 | Exercise 2.3.1 - Use CTEs, CASE and Window Functions
-- Source: complaint_analyst_view (run 2_2_1_SQLJoins/complaint_analyst_view.sql first)
--         and complaint_status_history.
--   psql -d complaints -f advanced_queries.sql
--
-- Unresolved = is_open = true (status is not RESOLVED or CLOSED).
-- Age is counted up to the as-of date 2025-02-24 (the newest complaint).


-- Q1a. Use CASE to put each unresolved complaint in an age bucket. (29 rows)
SELECT complaint_id,
       priority,
       status,
       created_at,
       DATE '2025-02-24' - CAST(created_at AS DATE) AS age_days,
       CASE
           WHEN DATE '2025-02-24' - CAST(created_at AS DATE) <= 7  THEN '0-7 days'
           WHEN DATE '2025-02-24' - CAST(created_at AS DATE) <= 30 THEN '8-30 days'
           ELSE '31+ days'
       END AS age_bucket
FROM complaint_analyst_view
WHERE is_open = true
ORDER BY age_days DESC;


-- Q1b. Count unresolved complaints in each age bucket. (3 rows)
SELECT CASE
           WHEN DATE '2025-02-24' - CAST(created_at AS DATE) <= 7  THEN '0-7 days'
           WHEN DATE '2025-02-24' - CAST(created_at AS DATE) <= 30 THEN '8-30 days'
           ELSE '31+ days'
       END AS age_bucket,
       COUNT(*) AS unresolved_count,
       SUM(CASE WHEN priority IN ('High', 'Critical') THEN 1 ELSE 0 END) AS high_or_critical_count
FROM complaint_analyst_view
WHERE is_open = true
GROUP BY age_bucket
ORDER BY MIN(DATE '2025-02-24' - CAST(created_at AS DATE));


-- Q2. Use a CTE to find repeat complainants (customers with 2 or more complaints). (10 rows)
WITH customer_counts AS (
    SELECT customer_id,
           COUNT(*) AS total_complaints
    FROM complaint_analyst_view
    GROUP BY customer_id
)
SELECT customer_id, total_complaints
FROM customer_counts
WHERE total_complaints >= 2
ORDER BY total_complaints DESC, customer_id;


-- Q3. Use ROW_NUMBER to get the latest status of each complaint. (30 rows)
-- Number each complaint's history rows, newest first, then keep row 1.
-- All timestamps are the same (load time), so status_history_id breaks the tie.
WITH numbered_history AS (
    SELECT complaint_id,
           new_status,
           status_timestamp,
           ROW_NUMBER() OVER (
               PARTITION BY complaint_id
               ORDER BY status_timestamp DESC, status_history_id DESC
           ) AS row_num
    FROM complaint_status_history
)
SELECT complaint_id, new_status AS latest_status, status_timestamp
FROM numbered_history
WHERE row_num = 1
ORDER BY complaint_id;


-- Q4. Rank customers by complaint count. (10 rows)
--   RANK       ties share a rank, then it skips  (1, 1, 1, 4)
--   DENSE_RANK ties share a rank, no skip        (1, 1, 1, 2)
--   ROW_NUMBER every row gets its own number     (1, 2, 3, 4)
WITH customer_counts AS (
    SELECT customer_id,
           COUNT(*) AS total_complaints
    FROM complaint_analyst_view
    GROUP BY customer_id
)
SELECT customer_id,
       total_complaints,
       RANK() OVER (ORDER BY total_complaints DESC) AS complaint_rank,
       DENSE_RANK() OVER (ORDER BY total_complaints DESC) AS complaint_dense_rank,
       ROW_NUMBER() OVER (ORDER BY total_complaints DESC, customer_id) AS complaint_position
FROM customer_counts
ORDER BY complaint_position;


-- CHECKS
-- Each check returns one number. The expected answer is in the comment.

-- V01. Unresolved complaints, so the buckets should add up to this (expected 29)
SELECT COUNT(*) FROM complaint_analyst_view WHERE is_open = true;

-- V02. Edge of the first bucket: CMP023 is 7 days old (expected 7, so 0-7 days)
SELECT DATE '2025-02-24' - CAST(created_at AS DATE) FROM complaint_analyst_view WHERE complaint_id = 'CMP023';

-- V03. Start of the second bucket: CMP022 is 8 days old (expected 8, so 8-30 days)
SELECT DATE '2025-02-24' - CAST(created_at AS DATE) FROM complaint_analyst_view WHERE complaint_id = 'CMP022';

-- V04. Edge of the second bucket: CMP010 is 30 days old (expected 30, so 8-30 days)
SELECT DATE '2025-02-24' - CAST(created_at AS DATE) FROM complaint_analyst_view WHERE complaint_id = 'CMP010';

-- V05. Start of the last bucket: CMP009 is 31 days old (expected 31, so 31+ days)
SELECT DATE '2025-02-24' - CAST(created_at AS DATE) FROM complaint_analyst_view WHERE complaint_id = 'CMP009';

-- V06. Customers who have complained (expected 10)
SELECT COUNT(DISTINCT customer_id) FROM complaint_analyst_view;

-- V07. Complaints that have status history, so Q3 should return this many rows (expected 30)
SELECT COUNT(DISTINCT complaint_id) FROM complaint_status_history;

-- V08. Customers tied for the most complaints (expected 3: CUS001, CUS003, CUS007)
SELECT COUNT(*)
FROM (SELECT customer_id FROM complaint_analyst_view
      GROUP BY customer_id
      HAVING COUNT(*) = 4) AS top_customers;
