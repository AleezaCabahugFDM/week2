-- complaint_metrics.sql
-- Week 2 | Exercise 2.2.2 - Calculate Complaint Operations Metrics
-- Source: complaint_analyst_view (run 2_2_1_SQLJoins/complaint_analyst_view.sql first)
--   psql -d complaints -f complaint_metrics.sql
--
-- Rules (more detail in metric_definitions.md):
--   open / backlog = is_open = true  (status is not RESOLVED or CLOSED)
--   closed         = is_open = false
--   escalated      = status is ESCALATED, or a reviewer's decision was ESCALATED
--   closed date    = investigation.end_date
--   as-of date     = 2025-02-24 (the newest complaint), used for backlog age
--
-- The LAST query (S) makes complaint_metrics.csv. Run it alone and export as CSV.


-- M1. Overall numbers
SELECT COUNT(*) AS complaint_count,
       COUNT(DISTINCT customer_id) AS distinct_customers
FROM complaint_analyst_view;

SELECT COUNT(*) AS backlog_count,
       COUNT(DISTINCT customer_id) AS customers_with_open_complaint
FROM complaint_analyst_view
WHERE is_open = true;

SELECT COUNT(*) AS closed_count
FROM complaint_analyst_view
WHERE is_open = false;


-- M2. Volume by category
SELECT category,
       COUNT(*) AS complaint_count,
       COUNT(DISTINCT customer_id) AS distinct_customers
FROM complaint_analyst_view
GROUP BY category
ORDER BY complaint_count DESC;


-- M3. Volume by status
SELECT status,
       COUNT(*) AS complaint_count,
       COUNT(DISTINCT customer_id) AS distinct_customers
FROM complaint_analyst_view
GROUP BY status
ORDER BY complaint_count DESC;


-- M4. Volume by month opened
SELECT TO_CHAR(created_at, 'YYYY-MM') AS opened_month,
       COUNT(*) AS complaint_count,
       COUNT(DISTINCT customer_id) AS distinct_customers
FROM complaint_analyst_view
GROUP BY opened_month
ORDER BY opened_month;


-- M5. Backlog by priority, with age in days on the as-of date
SELECT priority,
       COUNT(*) AS backlog_count,
       ROUND(AVG(DATE '2025-02-24' - CAST(created_at AS DATE)), 1) AS avg_age_days,
       MAX(DATE '2025-02-24' - CAST(created_at AS DATE)) AS oldest_age_days
FROM complaint_analyst_view
WHERE is_open = true
GROUP BY priority
ORDER BY backlog_count DESC;


-- M6. Escalated backlog (expected 1 row: CMP009)
-- CMP009 was escalated by a reviewer but its status is still UNDER_REVIEW,
-- so we also look in review_decision.
SELECT complaint_id, category, priority, status
FROM complaint_analyst_view
WHERE is_open = true
  AND (status = 'ESCALATED'
       OR complaint_id IN (
           SELECT rr.complaint_id
           FROM review_request rr
           JOIN review_decision rd ON rr.review_request_id = rd.review_request_id
           WHERE rd.decision = 'ESCALATED'
       ));


-- M7. Resolution time for closed complaints, by category
-- Resolution days = investigation end date - date opened.
-- Open complaints are left out (they have not finished yet).
SELECT v.category,
       COUNT(*) AS closed_count,
       ROUND(AVG(i.end_date - CAST(v.created_at AS DATE)), 1) AS avg_resolution_days
FROM complaint_analyst_view v
JOIN investigation i ON v.complaint_id = i.complaint_id
WHERE v.is_open = false
  AND i.end_date IS NOT NULL
GROUP BY v.category;


-- CHECKS
-- Each check returns one number. The expected answer is in the comment.

-- V01. The view has every complaint (expected 30)
SELECT COUNT(*) FROM complaint_analyst_view;

-- V02. Backlog + closed = total (expected 29 + 1 = 30)
SELECT COUNT(*) FROM complaint_analyst_view WHERE is_open = true;
SELECT COUNT(*) FROM complaint_analyst_view WHERE is_open = false;

-- V03. Distinct customers overall (expected 10)
SELECT COUNT(DISTINCT customer_id) FROM complaint_analyst_view;

-- V04. Escalated by status alone (expected 0, which is why review decisions are also used)
SELECT COUNT(*) FROM complaint_analyst_view WHERE status = 'ESCALATED';

-- V05. CMP001 has an investigation end date but is still open,
--      so it must NOT be in the resolution numbers (expected 0)
SELECT COUNT(*)
FROM complaint_analyst_view v
JOIN investigation i ON v.complaint_id = i.complaint_id
WHERE v.is_open = false AND v.complaint_id = 'CMP001';

-- V06. CMP005 resolution days (expected 3: 2025-01-15 to 2025-01-18)
SELECT i.end_date - CAST(v.created_at AS DATE)
FROM complaint_analyst_view v
JOIN investigation i ON v.complaint_id = i.complaint_id
WHERE v.complaint_id = 'CMP005';


-- S. METRICS SUMMARY -> complaint_metrics.csv
-- One row per metric. Run this query alone and export the result as CSV.
SELECT metric_name, grouping, group_value, metric_value, unit,
       CURRENT_DATE AS calculation_date,
       DATE '2025-02-24' AS as_of_date
FROM (
    -- overall
    SELECT 'complaint_count' AS metric_name, 'overall' AS grouping, 'all' AS group_value,
           COUNT(*) AS metric_value, 'complaints' AS unit
    FROM complaint_analyst_view

    UNION ALL
    SELECT 'distinct_customers', 'overall', 'all', COUNT(DISTINCT customer_id), 'customers'
    FROM complaint_analyst_view

    UNION ALL
    SELECT 'backlog_count', 'overall', 'all', COUNT(*), 'complaints'
    FROM complaint_analyst_view WHERE is_open = true

    UNION ALL
    SELECT 'customers_with_open_complaint', 'overall', 'all', COUNT(DISTINCT customer_id), 'customers'
    FROM complaint_analyst_view WHERE is_open = true

    UNION ALL
    SELECT 'escalated_backlog_count', 'overall', 'all', COUNT(*), 'complaints'
    FROM complaint_analyst_view
    WHERE is_open = true
      AND (status = 'ESCALATED'
           OR complaint_id IN (
               SELECT rr.complaint_id
               FROM review_request rr
               JOIN review_decision rd ON rr.review_request_id = rd.review_request_id
               WHERE rd.decision = 'ESCALATED'
           ))

    UNION ALL
    SELECT 'escalated_by_status_only', 'overall', 'all', COUNT(*), 'complaints'
    FROM complaint_analyst_view WHERE is_open = true AND status = 'ESCALATED'

    UNION ALL
    SELECT 'closed_count', 'overall', 'all', COUNT(*), 'complaints'
    FROM complaint_analyst_view WHERE is_open = false

    UNION ALL
    SELECT 'backlog_avg_age_days', 'overall', 'all',
           ROUND(AVG(DATE '2025-02-24' - CAST(created_at AS DATE)), 1), 'days'
    FROM complaint_analyst_view WHERE is_open = true

    UNION ALL
    SELECT 'avg_resolution_days', 'overall', 'all',
           ROUND(AVG(i.end_date - CAST(v.created_at AS DATE)), 1), 'days'
    FROM complaint_analyst_view v
    JOIN investigation i ON v.complaint_id = i.complaint_id
    WHERE v.is_open = false AND i.end_date IS NOT NULL

    -- by category
    UNION ALL
    SELECT 'complaint_count', 'category', category, COUNT(*), 'complaints'
    FROM complaint_analyst_view GROUP BY category

    UNION ALL
    SELECT 'distinct_customers', 'category', category, COUNT(DISTINCT customer_id), 'customers'
    FROM complaint_analyst_view GROUP BY category

    UNION ALL
    SELECT 'closed_count', 'category', category,
           SUM(CASE WHEN is_open = false THEN 1 ELSE 0 END), 'complaints'
    FROM complaint_analyst_view GROUP BY category

    -- blank (NULL) when a category has no closed complaints: unknown, not 0 days
    UNION ALL
    SELECT 'avg_resolution_days', 'category', v.category,
           ROUND(AVG(CASE WHEN v.is_open = false THEN i.end_date - CAST(v.created_at AS DATE) END), 1),
           'days'
    FROM complaint_analyst_view v
    LEFT JOIN investigation i ON v.complaint_id = i.complaint_id
    GROUP BY v.category

    -- by status
    UNION ALL
    SELECT 'complaint_count', 'status', status, COUNT(*), 'complaints'
    FROM complaint_analyst_view GROUP BY status

    UNION ALL
    SELECT 'distinct_customers', 'status', status, COUNT(DISTINCT customer_id), 'customers'
    FROM complaint_analyst_view GROUP BY status

    -- by month opened
    UNION ALL
    SELECT 'complaint_count', 'opened_month', TO_CHAR(created_at, 'YYYY-MM'), COUNT(*), 'complaints'
    FROM complaint_analyst_view GROUP BY TO_CHAR(created_at, 'YYYY-MM')

    UNION ALL
    SELECT 'distinct_customers', 'opened_month', TO_CHAR(created_at, 'YYYY-MM'),
           COUNT(DISTINCT customer_id), 'customers'
    FROM complaint_analyst_view GROUP BY TO_CHAR(created_at, 'YYYY-MM')

    -- backlog by priority
    UNION ALL
    SELECT 'backlog_count', 'priority', priority, COUNT(*), 'complaints'
    FROM complaint_analyst_view WHERE is_open = true GROUP BY priority
) AS metrics
ORDER BY grouping, metric_name, group_value;
