-- ============================================================================
-- advanced_queries.sql   Week 2 | Exercise 2.3.1 - Use CTEs, CASE and
--                        Window Functions
-- Source: complaint_analyst_view (2.2.1, one row per complaint) and
--         complaint_status_history (2.1.1).
--
-- Answers advanced_sql_questions.md:
--   Q1a  CASE        - age bucket for every unresolved complaint (0-7, 8-30, 31+)
--   Q1b  CASE        - count of unresolved complaints per age bucket
--   Q2   CTE         - identify repeat complainants
--   Q3   ROW_NUMBER  - latest status per complaint
--   Q4   RANK etc.   - rank customers by complaint count
--   V01-V16         - checks, one table, PASS / FAIL
--
-- Plain SQL: runs in psql and the Supabase SQL Editor.
--   psql:      psql -d complaints -f advanced_queries.sql
--   Supabase:  run complaint_analyst_view.sql first, then highlight one query
--              and press Run (running the whole file shows the check table).
--
-- Same definitions as 2.2.2 (metric_definitions.md):
--   unresolved / open = status NOT IN ('RESOLVED','CLOSED')   (view: is_open)
--   escalated         = status ESCALATED or a review decision ESCALATED
--   as_of_date        = 2025-02-24, the newest complaint (data stops there)
-- ============================================================================


-- ===========================================================================
-- Q1a. Use CASE for unresolved age buckets 0-7, 8-30 and 31+ days.
-- Grain: one row per unresolved complaint (29 rows).
-- age_days = as_of_date - date opened, in whole calendar days.
-- Each age falls in exactly one bucket:
--   0..7 -> '0-7 days'   8..30 -> '8-30 days'   31 or more -> '31+ days'
-- A negative age (opened after the as-of date) is NOT forced into a bucket;
-- it is flagged so the data problem is visible.
-- ===========================================================================
WITH params AS (
    SELECT DATE '2025-02-24' AS as_of_date            -- <-- as-of date
),
unresolved_complaints AS (
    SELECT v.complaint_id,
           v.customer_id,
           v.category,
           v.priority,
           v.status,
           v.created_at,
           p.as_of_date - v.created_at::date AS age_days
    FROM   complaint_analyst_view AS v
    CROSS  JOIN params AS p
    WHERE  v.is_open
)
SELECT u.complaint_id,
       u.customer_id,
       u.category,
       u.priority,
       u.status,
       u.created_at,
       u.age_days,
       CASE
           WHEN u.age_days < 0              THEN 'Invalid: opened after as-of date'
           WHEN u.age_days BETWEEN 0 AND 7  THEN '0-7 days'
           WHEN u.age_days BETWEEN 8 AND 30 THEN '8-30 days'
           ELSE                                  '31+ days'
       END AS age_bucket
FROM   unresolved_complaints AS u
ORDER  BY u.age_days DESC, u.complaint_id;


-- ===========================================================================
-- Q1b. How many unresolved complaints are in each age bucket?
-- Grain: one row per bucket. Every bucket is listed, even if empty.
-- ===========================================================================
WITH params AS (
    SELECT DATE '2025-02-24' AS as_of_date            -- <-- as-of date
),
age_buckets (bucket_order, age_bucket) AS (
    VALUES (1, '0-7 days'), (2, '8-30 days'), (3, '31+ days')
),
bucketed_complaints AS (
    SELECT v.complaint_id,
           v.priority,
           CASE
               WHEN p.as_of_date - v.created_at::date < 0              THEN 'Invalid: opened after as-of date'
               WHEN p.as_of_date - v.created_at::date BETWEEN 0 AND 7  THEN '0-7 days'
               WHEN p.as_of_date - v.created_at::date BETWEEN 8 AND 30 THEN '8-30 days'
               ELSE                                                         '31+ days'
           END AS age_bucket
    FROM   complaint_analyst_view AS v
    CROSS  JOIN params AS p
    WHERE  v.is_open
)
SELECT b.age_bucket,
       COUNT(bc.complaint_id)                                                    AS unresolved_count,
       COUNT(bc.complaint_id) FILTER (WHERE bc.priority IN ('High', 'Critical')) AS high_or_critical_count
FROM   age_buckets AS b
LEFT   JOIN bucketed_complaints AS bc ON bc.age_bucket = b.age_bucket
GROUP  BY b.bucket_order, b.age_bucket
ORDER  BY b.bucket_order;


-- ===========================================================================
-- Q2. Use a CTE to identify repeat complainants.
-- Repeat complainant = a customer with 2 or more complaints (open or closed).
-- Grain: one row per customer who has complained (10 rows).
-- Each CTE is one business step, named for what it answers:
--   complaints_per_customer     how many complaints, and when, per customer?
--   same_category_repeaters     which customers complained about the SAME
--                               category more than once?
--   escalated_customers         which customers have an escalated complaint?
--   repeat_complainants         put it together and label each customer
-- ===========================================================================
WITH complaints_per_customer AS (
    SELECT v.customer_id,
           v.customer_segment,
           COUNT(*)                          AS total_complaints,
           COUNT(*) FILTER (WHERE v.is_open) AS open_complaints,
           COUNT(DISTINCT v.category)        AS distinct_categories,
           MIN(v.created_at)                 AS first_complaint_at,
           MAX(v.created_at)                 AS latest_complaint_at
    FROM   complaint_analyst_view AS v
    GROUP  BY v.customer_id, v.customer_segment
),
same_category_repeaters AS (
    SELECT v.customer_id,
           STRING_AGG(DISTINCT v.category, ', ' ORDER BY v.category) AS repeated_categories
    FROM   complaint_analyst_view AS v
    WHERE  (v.customer_id, v.category) IN (
               SELECT x.customer_id, x.category
               FROM   complaint_analyst_view AS x
               GROUP  BY x.customer_id, x.category
               HAVING COUNT(*) >= 2)
    GROUP  BY v.customer_id
),
escalated_customers AS (
    SELECT DISTINCT v.customer_id
    FROM   complaint_analyst_view AS v
    WHERE  v.is_open
      AND  (v.status = 'ESCALATED' OR COALESCE(v.review_decisions, '') LIKE '%ESCALATED%')
),
repeat_complainants AS (
    SELECT cpc.customer_id,
           cpc.customer_segment,
           cpc.total_complaints,
           cpc.open_complaints,
           cpc.distinct_categories,
           cpc.first_complaint_at,
           cpc.latest_complaint_at,
           (cpc.total_complaints >= 2)          AS is_repeat_complainant,
           (scr.customer_id IS NOT NULL)        AS has_same_category_repeat,
           scr.repeated_categories,
           (ec.customer_id IS NOT NULL)         AS has_escalated_complaint
    FROM   complaints_per_customer      AS cpc
    LEFT   JOIN same_category_repeaters AS scr ON scr.customer_id = cpc.customer_id
    LEFT   JOIN escalated_customers     AS ec  ON ec.customer_id  = cpc.customer_id
)
SELECT rc.customer_id,
       rc.customer_segment,
       rc.total_complaints,
       rc.open_complaints,
       rc.distinct_categories,
       rc.first_complaint_at,
       rc.latest_complaint_at,
       rc.is_repeat_complainant,
       rc.has_same_category_repeat,
       rc.repeated_categories,
       rc.has_escalated_complaint
FROM   repeat_complainants AS rc
WHERE  rc.is_repeat_complainant
ORDER  BY rc.has_escalated_complaint DESC,
          rc.has_same_category_repeat DESC,
          rc.total_complaints DESC,
          rc.customer_id;


-- ===========================================================================
-- Q3. Use ROW_NUMBER to select latest status per complaint.
-- Grain: one row per complaint (30 rows).
--   PARTITION BY complaint_id : restart the numbering for each complaint
--   ORDER BY status_timestamp DESC, status_history_id DESC : newest first
-- status_history_id breaks ties. It matters here: all 30 timestamps are the
-- same (load time), so without it the "latest" row would be picked at random.
-- latest_matches_complaint shows if the history agrees with complaint.status.
-- ===========================================================================
WITH ranked_status_history AS (
    SELECT h.complaint_id,
           h.status_history_id,
           h.old_status,
           h.new_status,
           h.status_timestamp,
           ROW_NUMBER() OVER (
               PARTITION BY h.complaint_id
               ORDER BY h.status_timestamp DESC, h.status_history_id DESC
           ) AS recency_rank,
           COUNT(*) OVER (PARTITION BY h.complaint_id) AS history_rows
    FROM   complaint_status_history AS h
)
SELECT c.complaint_id,
       r.new_status                AS latest_status,
       r.old_status                AS previous_status,
       r.status_history_id         AS latest_history_id,
       r.history_rows,
       c.status                    AS complaint_status,
       (r.new_status = c.status)   AS latest_matches_complaint
FROM   complaint AS c
LEFT   JOIN ranked_status_history AS r
       ON r.complaint_id = c.complaint_id
      AND r.recency_rank = 1          -- keep only the newest row per complaint
ORDER  BY c.complaint_id;


-- ===========================================================================
-- Q4. Rank customers by complaint count.
-- Grain: one row per customer (10 rows).
--   ORDER BY total_complaints DESC : most complaints first (no PARTITION BY:
--   all customers are ranked together)
--   RANK       : ties share a rank, then a gap  (1,1,1,4,...)
--   DENSE_RANK : ties share a rank, no gap      (1,1,1,2,...)
--   ROW_NUMBER : unique position; ties broken by customer_id, so the order
--                is the same on every run
-- open_rank_in_segment uses PARTITION BY segment: ranks restart per segment.
-- ===========================================================================
WITH customer_complaint_counts AS (
    SELECT v.customer_id,
           v.customer_segment,
           COUNT(*)                              AS total_complaints,
           COUNT(*) FILTER (WHERE v.is_open)     AS open_complaints
    FROM   complaint_analyst_view AS v
    GROUP  BY v.customer_id, v.customer_segment
)
SELECT cc.customer_id,
       cc.customer_segment,
       cc.total_complaints,
       cc.open_complaints,
       RANK()       OVER (ORDER BY cc.total_complaints DESC)                  AS complaint_rank,
       DENSE_RANK() OVER (ORDER BY cc.total_complaints DESC)                  AS complaint_dense_rank,
       ROW_NUMBER() OVER (ORDER BY cc.total_complaints DESC, cc.customer_id)  AS complaint_position,
       RANK()       OVER (PARTITION BY cc.customer_segment
                          ORDER BY cc.open_complaints DESC)                   AS open_rank_in_segment
FROM   customer_complaint_counts AS cc
ORDER  BY complaint_position;


-- ===========================================================================
-- V. CHECKS - one result table, each row PASS or FAIL. Nothing is changed.
-- ===========================================================================
WITH
params AS (SELECT DATE '2025-02-24' AS as_of_date),
aged AS (
    SELECT v.complaint_id,
           p.as_of_date - v.created_at::date AS age_days
    FROM   complaint_analyst_view AS v
    CROSS  JOIN params AS p
    WHERE  v.is_open
),
bucket_rule AS (       -- the same CASE as Q1, applied to any age
    SELECT a.complaint_id, a.age_days,
           CASE
               WHEN a.age_days < 0              THEN 'Invalid: opened after as-of date'
               WHEN a.age_days BETWEEN 0 AND 7  THEN '0-7 days'
               WHEN a.age_days BETWEEN 8 AND 30 THEN '8-30 days'
               ELSE                                  '31+ days'
           END AS age_bucket
    FROM   (SELECT complaint_id, age_days FROM aged
            UNION ALL
            -- test ages held in memory (not inserted): edges and a bad value
            SELECT 'TEST_' || t.age_days, t.age_days
            FROM   (VALUES (-1), (0), (7), (8), (30), (31), (365)) AS t(age_days)) AS a
),
per_customer AS (      -- the same rule as Q2, plus test customers held in memory
    SELECT x.customer_id, COUNT(*) AS n, (COUNT(*) >= 2) AS is_repeat_complainant
    FROM   (SELECT v.customer_id FROM complaint_analyst_view AS v
            UNION ALL
            SELECT t.customer_id
            FROM   (VALUES ('TEST_ONE'), ('TEST_TWO'), ('TEST_TWO')) AS t(customer_id)) AS x
    GROUP  BY x.customer_id
),
latest AS (
    SELECT h.complaint_id, h.new_status,
           ROW_NUMBER() OVER (PARTITION BY h.complaint_id
                              ORDER BY h.status_timestamp DESC, h.status_history_id DESC) AS rn
    FROM   complaint_status_history AS h
),
cust AS (
    SELECT v.customer_id, COUNT(*) AS n,
           ROW_NUMBER() OVER (ORDER BY COUNT(*) DESC, v.customer_id) AS pos,
           RANK()       OVER (ORDER BY COUNT(*) DESC)                AS rnk,
           DENSE_RANK() OVER (ORDER BY COUNT(*) DESC)                AS drnk
    FROM   complaint_analyst_view AS v
    GROUP  BY v.customer_id
),
checks (check_id, check_name, expected, actual) AS (
    -- Q1 age buckets
    SELECT 'V01', 'Q1 bucket counts sum to unresolved complaints (29)',
           (SELECT COUNT(*) FROM complaint_analyst_view WHERE is_open),
           (SELECT COUNT(*) FROM bucket_rule WHERE complaint_id NOT LIKE 'TEST_%')
    UNION ALL
    SELECT 'V02', 'Q1 boundary (real): CMP030 age 0 -> 0-7',
           1, (SELECT COUNT(*) FROM bucket_rule WHERE complaint_id = 'CMP030' AND age_days = 0 AND age_bucket = '0-7 days')
    UNION ALL
    SELECT 'V03', 'Q1 boundary (real): CMP023 age 7 -> 0-7',
           1, (SELECT COUNT(*) FROM bucket_rule WHERE complaint_id = 'CMP023' AND age_days = 7 AND age_bucket = '0-7 days')
    UNION ALL
    SELECT 'V04', 'Q1 boundary (real): CMP022 age 8 -> 8-30',
           1, (SELECT COUNT(*) FROM bucket_rule WHERE complaint_id = 'CMP022' AND age_days = 8 AND age_bucket = '8-30 days')
    UNION ALL
    SELECT 'V05', 'Q1 boundary (real): CMP010 age 30 -> 8-30',
           1, (SELECT COUNT(*) FROM bucket_rule WHERE complaint_id = 'CMP010' AND age_days = 30 AND age_bucket = '8-30 days')
    UNION ALL
    SELECT 'V06', 'Q1 boundary (real): CMP009 age 31 -> 31+',
           1, (SELECT COUNT(*) FROM bucket_rule WHERE complaint_id = 'CMP009' AND age_days = 31 AND age_bucket = '31+ days')
    UNION ALL
    SELECT 'V07', 'Q1 boundary (test): ages 0,7 / 8,30 / 31,365 land in 0-7 / 8-30 / 31+',
           6, (SELECT COUNT(*) FROM bucket_rule
                WHERE (complaint_id IN ('TEST_0', 'TEST_7')    AND age_bucket = '0-7 days')
                   OR (complaint_id IN ('TEST_8', 'TEST_30')   AND age_bucket = '8-30 days')
                   OR (complaint_id IN ('TEST_31', 'TEST_365') AND age_bucket = '31+ days'))
    UNION ALL
    SELECT 'V08', 'Q1 negative (test): age -1 is flagged Invalid, not put in a bucket',
           1, (SELECT COUNT(*) FROM bucket_rule WHERE complaint_id = 'TEST_-1' AND age_bucket LIKE 'Invalid%')
    UNION ALL
    -- Q2 repeat complainants
    SELECT 'V09', 'Q2 grain: one row per customer (10), no duplicates',
           (SELECT COUNT(DISTINCT customer_id) FROM complaint_analyst_view),
           (SELECT COUNT(*) FROM per_customer WHERE customer_id NOT LIKE 'TEST_%')
    UNION ALL
    SELECT 'V10', 'Q2 repeat complainants (2+ complaints) = 10 of 10 customers',
           10, (SELECT COUNT(*) FROM per_customer WHERE customer_id NOT LIKE 'TEST_%' AND is_repeat_complainant)
    UNION ALL
    SELECT 'V11', 'Q2 customers repeating the same category = 7',
           7, (SELECT COUNT(DISTINCT customer_id) FROM
                 (SELECT customer_id FROM complaint_analyst_view
                   GROUP BY customer_id, category HAVING COUNT(*) >= 2) s)
    UNION ALL
    SELECT 'V12', 'Q2 negative (test): a customer with 1 complaint is NOT a repeat complainant',
           0, (SELECT COUNT(*) FROM per_customer WHERE customer_id = 'TEST_ONE' AND is_repeat_complainant)
    UNION ALL
    SELECT 'V13', 'Q2 boundary (test): exactly 2 complaints IS a repeat complainant',
           1, (SELECT COUNT(*) FROM per_customer WHERE customer_id = 'TEST_TWO' AND n = 2 AND is_repeat_complainant)
    UNION ALL
    -- Q3 latest status
    SELECT 'V14', 'Q3 exactly one latest row per complaint (30)',
           (SELECT COUNT(*) FROM complaint),
           (SELECT CASE WHEN COUNT(*) = COUNT(DISTINCT complaint_id) THEN COUNT(*) ELSE -1 END
              FROM latest WHERE rn = 1)
    UNION ALL
    SELECT 'V15', 'Q3 latest history status = complaint.status for all complaints',
           0, (SELECT COUNT(*) FROM complaint AS c
                LEFT JOIN latest AS l ON l.complaint_id = c.complaint_id AND l.rn = 1
                WHERE l.new_status IS DISTINCT FROM c.status)
    UNION ALL
    -- Q4 ranking
    SELECT 'V16', 'Q4 ties: 3 share rank 1, next RANK is 4, next DENSE_RANK is 2, 10 unique ROW_NUMBERs',
           1, CASE WHEN (SELECT COUNT(*) FROM cust WHERE rnk = 1) = 3
                    AND (SELECT MIN(rnk)  FROM cust WHERE rnk  > 1) = 4
                    AND (SELECT MIN(drnk) FROM cust WHERE drnk > 1) = 2
                    AND (SELECT COUNT(DISTINCT pos) FROM cust) = 10
                    AND (SELECT customer_id FROM cust WHERE pos = 1) = 'CUS001'
                   THEN 1 ELSE 0 END
)
SELECT ch.check_id,
       ch.check_name,
       ch.expected,
       ch.actual,
       CASE WHEN ch.actual = ch.expected THEN 'PASS' ELSE 'FAIL' END AS result
FROM   checks AS ch
ORDER  BY ch.check_id;