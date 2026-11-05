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
-- One table: each row is a check with the expected and actual answer.
-- In Supabase, running the whole file shows this table.
SELECT check_id, check_name, expected, actual,
       CASE WHEN actual = expected THEN 'PASS' ELSE 'FAIL' END AS result
FROM (
    SELECT 'V01' AS check_id, 'Unresolved complaints (the buckets add up to this)' AS check_name,
           29 AS expected, COUNT(*) AS actual
    FROM complaint_analyst_view WHERE is_open = true

    UNION ALL
    SELECT 'V02', 'CMP023 is 7 days old (last day of 0-7)', 7,
           DATE '2025-02-24' - CAST(created_at AS DATE)
    FROM complaint_analyst_view WHERE complaint_id = 'CMP023'

    UNION ALL
    SELECT 'V03', 'CMP022 is 8 days old (first day of 8-30)', 8,
           DATE '2025-02-24' - CAST(created_at AS DATE)
    FROM complaint_analyst_view WHERE complaint_id = 'CMP022'

    UNION ALL
    SELECT 'V04', 'CMP010 is 30 days old (last day of 8-30)', 30,
           DATE '2025-02-24' - CAST(created_at AS DATE)
    FROM complaint_analyst_view WHERE complaint_id = 'CMP010'

    UNION ALL
    SELECT 'V05', 'CMP009 is 31 days old (first day of 31+)', 31,
           DATE '2025-02-24' - CAST(created_at AS DATE)
    FROM complaint_analyst_view WHERE complaint_id = 'CMP009'

    UNION ALL
    SELECT 'V06', 'Customers who have complained (Q2 rows)', 10, COUNT(DISTINCT customer_id)
    FROM complaint_analyst_view

    UNION ALL
    SELECT 'V07', 'Complaints with status history (Q3 rows)', 30, COUNT(DISTINCT complaint_id)
    FROM complaint_status_history

    UNION ALL
    SELECT 'V08', 'Customers tied for the most complaints (CUS001, CUS003, CUS007)', 3, COUNT(*)
    FROM (SELECT customer_id FROM complaint_analyst_view
          GROUP BY customer_id
          HAVING COUNT(*) = 4) AS top_customers
) AS checks
ORDER BY check_id;
