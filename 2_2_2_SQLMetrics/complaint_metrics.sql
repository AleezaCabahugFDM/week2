-- ============================================================================
-- complaint_metrics.sql   Week 2 | Exercise 2.2.2 - Calculate Complaint
--                         Operations Metrics
-- Source: complaint_analyst_view (Exercise 2.2.1), one row per complaint.
--
-- Plain SQL: runs in psql and the Supabase SQL Editor.
--   psql:      psql -d complaints -f complaint_metrics.sql
--   Supabase:  highlight one query and press Run. The LAST query (S) is the
--              metrics summary: run it alone, then use "Export > CSV" to get
--              complaint_metrics.csv.
--
-- DEFINITIONS (full detail in metric_definitions.md)
--   complaint count   = COUNT(*) of complaints (one row per complaint)
--   distinct customers= COUNT(DISTINCT customer_id); one customer with 4
--                       complaints counts once. NOT additive across groups.
--   open / backlog    = status NOT IN ('RESOLVED','CLOSED')
--   closed            = status IN ('RESOLVED','CLOSED')
--   escalated backlog = open complaints whose status is ESCALATED OR whose
--                       review decision was ESCALATED (status is not always
--                       updated: CMP009 was escalated but is UNDER_REVIEW)
--   closed date       = investigation.end_date (see note R below)
--   resolution days   = closed date - created_at date, closed complaints ONLY
--   as_of_date        = 2025-02-24 (newest complaint) for backlog age
-- ============================================================================


-- ===========================================================================
-- STEP 1. VOLUMES
-- ===========================================================================

-- M1. Overall volume, backlog and affected customers
SELECT COUNT(*)                                              AS complaint_count,
       COUNT(DISTINCT v.customer_id)                         AS distinct_customers,
       COUNT(*) FILTER (WHERE v.is_open)                     AS backlog_count,
       COUNT(DISTINCT v.customer_id) FILTER (WHERE v.is_open) AS customers_with_open_complaint,
       COUNT(*) FILTER (WHERE v.is_open AND (v.status = 'ESCALATED' OR COALESCE(v.review_decisions, '') LIKE '%ESCALATED%')) AS escalated_backlog_count,
       COUNT(*) FILTER (WHERE NOT v.is_open)                 AS closed_count
FROM   complaint_analyst_view AS v;


-- M2. Volume by category: complaints vs distinct customers
SELECT v.category,
       COUNT(*)                                   AS complaint_count,
       COUNT(DISTINCT v.customer_id)              AS distinct_customers,
       COUNT(*) FILTER (WHERE v.is_open)          AS open_count
FROM   complaint_analyst_view AS v
GROUP  BY v.category
ORDER  BY complaint_count DESC, v.category;


-- M3. Volume by status
SELECT v.status,
       COUNT(*)                                   AS complaint_count,
       COUNT(DISTINCT v.customer_id)              AS distinct_customers
FROM   complaint_analyst_view AS v
GROUP  BY v.status
ORDER  BY complaint_count DESC, v.status;


-- M4. Volume by month the complaint was opened (created_at)
SELECT TO_CHAR(DATE_TRUNC('month', v.created_at), 'YYYY-MM') AS opened_month,
       COUNT(*)                                             AS complaint_count,
       COUNT(DISTINCT v.customer_id)                        AS distinct_customers
FROM   complaint_analyst_view AS v
GROUP  BY DATE_TRUNC('month', v.created_at)
ORDER  BY DATE_TRUNC('month', v.created_at);


-- M5. Backlog by priority, with age as of the as-of date
WITH params AS (SELECT DATE '2025-02-24' AS as_of_date)        -- <-- as-of date
SELECT v.priority,
       COUNT(*)                                                AS backlog_count,
       ROUND(AVG(p.as_of_date - v.created_at::date), 1)        AS avg_age_days,
       MAX(p.as_of_date - v.created_at::date)                  AS oldest_age_days
FROM   complaint_analyst_view AS v
CROSS  JOIN params AS p
WHERE  v.is_open
GROUP  BY v.priority
ORDER  BY CASE v.priority WHEN 'Critical' THEN 1 WHEN 'High' THEN 2
                          WHEN 'Medium'   THEN 3 WHEN 'Low'  THEN 4 END;


-- M5b. Escalated backlog: open complaints that were escalated.
-- Two sources are checked because the complaint status is not always updated
-- when a reviewer escalates (CMP009: review ESCALATED, status UNDER_REVIEW).
SELECT v.complaint_id,
       v.category,
       v.priority,
       v.status,
       v.review_decisions,
       CASE WHEN v.status = 'ESCALATED' THEN 'complaint status'
            ELSE 'review decision' END              AS escalated_by,
       v.created_at
FROM   complaint_analyst_view AS v
WHERE  v.is_open
  AND  (v.status = 'ESCALATED' OR COALESCE(v.review_decisions, '') LIKE '%ESCALATED%')
ORDER  BY v.created_at, v.complaint_id;


-- ===========================================================================
-- STEP 2. RESOLUTION
-- R. Closed date: the complaint table has no closed date. The status-history
--    closure timestamp is the load time of the setup script (not 2025), so it
--    would give ~650 days and change on every reload. The investigation
--    end_date is the real 2025 date the case was resolved, so it is used.
--    Resolution days = end_date - created_at::date (whole calendar days).
--    Only CLOSED/RESOLVED complaints are included; open cases are excluded.
-- ===========================================================================

-- M6. Closed-case duration by category
-- Every category is listed. Categories with no closed cases show
-- closed_count 0 and NULL durations (unknown, NOT zero days).
WITH closed AS (
    SELECT v.complaint_id,
           v.category,
           (MAX(i.end_date) - v.created_at::date) AS resolution_days
    FROM   complaint_analyst_view AS v
    JOIN   investigation AS i ON i.complaint_id = v.complaint_id
    WHERE  NOT v.is_open                  -- exclude unresolved cases
      AND  i.end_date IS NOT NULL
    GROUP  BY v.complaint_id, v.category, v.created_at
)
SELECT cat.category,
       COUNT(cl.complaint_id)                                          AS closed_count,
       ROUND(AVG(cl.resolution_days), 1)                               AS avg_resolution_days,
       PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY cl.resolution_days) AS median_resolution_days,
       MIN(cl.resolution_days)                                         AS min_resolution_days,
       MAX(cl.resolution_days)                                         AS max_resolution_days
FROM   (SELECT DISTINCT category FROM complaint_analyst_view) AS cat
LEFT   JOIN closed AS cl ON cl.category = cat.category
GROUP  BY cat.category
ORDER  BY closed_count DESC, cat.category;


-- M7. Closed complaints that cannot be measured (no investigation end date).
-- These are left out of M6; this lists them so nothing disappears silently.
SELECT v.complaint_id,
       v.category,
       v.status,
       v.created_at
FROM   complaint_analyst_view AS v
WHERE  NOT v.is_open
  AND  NOT EXISTS (SELECT 1 FROM investigation AS i
                    WHERE i.complaint_id = v.complaint_id AND i.end_date IS NOT NULL)
ORDER  BY v.complaint_id;


-- ===========================================================================
-- V. CHECKS - one result table, each row PASS or FAIL. Nothing is changed.
-- ===========================================================================
WITH
cat AS (SELECT category, COUNT(*) AS n, COUNT(DISTINCT customer_id) AS dc
        FROM complaint_analyst_view GROUP BY category),
closed AS (
    SELECT v.complaint_id, v.is_open,
           (MAX(i.end_date) - v.created_at::date) AS resolution_days
    FROM   complaint_analyst_view AS v
    JOIN   investigation AS i ON i.complaint_id = v.complaint_id
    WHERE  NOT v.is_open AND i.end_date IS NOT NULL
    GROUP  BY v.complaint_id, v.is_open, v.created_at
),
checks (check_id, check_name, expected, actual) AS (
    SELECT 'V01', 'View rows = complaint table rows (source is complete)',
           (SELECT COUNT(*) FROM complaint), (SELECT COUNT(*) FROM complaint_analyst_view)
    UNION ALL
    SELECT 'V02', 'M2 category counts sum to total complaints',
           (SELECT COUNT(*) FROM complaint), (SELECT SUM(n) FROM cat)
    UNION ALL
    SELECT 'V03', 'M3 status counts sum to total complaints',
           (SELECT COUNT(*) FROM complaint),
           (SELECT SUM(n) FROM (SELECT COUNT(*) AS n FROM complaint_analyst_view GROUP BY status) s)
    UNION ALL
    SELECT 'V04', 'M4 month counts sum to total complaints',
           (SELECT COUNT(*) FROM complaint),
           (SELECT SUM(n) FROM (SELECT COUNT(*) AS n FROM complaint_analyst_view
                                 GROUP BY DATE_TRUNC('month', created_at)) s)
    UNION ALL
    SELECT 'V05', 'Backlog + closed = total complaints',
           (SELECT COUNT(*) FROM complaint),
           (SELECT COUNT(*) FILTER (WHERE is_open) + COUNT(*) FILTER (WHERE NOT is_open)
              FROM complaint_analyst_view)
    UNION ALL
    SELECT 'V06', 'Distinct customers overall = customer table (10)',
           (SELECT COUNT(*) FROM customer),
           (SELECT COUNT(DISTINCT customer_id) FROM complaint_analyst_view)
    UNION ALL
    -- Distinct customers are NOT additive: adding the per-category numbers
    -- double-counts customers who complain in more than one category.
    SELECT 'V07', 'Distinct customers per category sum (22) > overall (10): not additive',
           1, CASE WHEN (SELECT SUM(dc) FROM cat)
                      > (SELECT COUNT(DISTINCT customer_id) FROM complaint_analyst_view)
                   THEN 1 ELSE 0 END
    UNION ALL
    SELECT 'V08', 'Resolution uses closed cases only (no open case included)',
           0, (SELECT COUNT(*) FROM closed WHERE is_open)
    UNION ALL
    SELECT 'V09', 'Resolution: closed cases measured + unmeasurable = all closed',
           (SELECT COUNT(*) FROM complaint_analyst_view WHERE NOT is_open),
           (SELECT COUNT(*) FROM closed)
         + (SELECT COUNT(*) FROM complaint_analyst_view AS v
             WHERE NOT v.is_open
               AND NOT EXISTS (SELECT 1 FROM investigation AS i
                                WHERE i.complaint_id = v.complaint_id AND i.end_date IS NOT NULL))
    UNION ALL
    SELECT 'V10', 'Boundary: no negative resolution durations',
           0, (SELECT COUNT(*) FROM closed WHERE resolution_days < 0)
    UNION ALL
    -- CMP001 has an investigation end date but is still OPEN: it must NOT count
    SELECT 'V11', 'Negative: open CMP001 (investigation ended) is excluded from resolution',
           0, (SELECT COUNT(*) FROM closed WHERE complaint_id = 'CMP001')
    UNION ALL
    -- A category with no closed cases must show NULL average, not 0
    SELECT 'V12', 'Negative: category with no closed cases has NULL avg (not 0)',
           1, (SELECT CASE WHEN AVG(cl.resolution_days) IS NULL THEN 1 ELSE 0 END
                 FROM closed AS cl
                 JOIN complaint_analyst_view AS v ON v.complaint_id = cl.complaint_id
                WHERE v.category = 'Fraud Claim')
    UNION ALL
    SELECT 'V13', 'CMP005 resolution = 3 days (2025-01-15 -> 2025-01-18)',
           3, (SELECT resolution_days FROM closed WHERE complaint_id = 'CMP005')
    UNION ALL
    SELECT 'V14', 'Escalated backlog = 1 (CMP009, escalated by review decision)',
           1, (SELECT COUNT(*) FROM complaint_analyst_view AS v WHERE v.is_open AND (v.status = 'ESCALATED' OR COALESCE(v.review_decisions, '') LIKE '%ESCALATED%'))
    UNION ALL
    SELECT 'V15', 'Escalated backlog is part of open backlog (never larger)',
           1, CASE WHEN (SELECT COUNT(*) FROM complaint_analyst_view AS v WHERE v.is_open AND (v.status = 'ESCALATED' OR COALESCE(v.review_decisions, '') LIKE '%ESCALATED%'))
                     <= (SELECT COUNT(*) FROM complaint_analyst_view WHERE is_open)
                   THEN 1 ELSE 0 END
    UNION ALL
    SELECT 'V16', 'Boundary: escalated by status alone = 0 (why review decisions are also used)',
           0, (SELECT COUNT(*) FROM complaint_analyst_view WHERE status = 'ESCALATED')
)
SELECT ch.check_id, ch.check_name, ch.expected, ch.actual,
       CASE WHEN ch.actual = ch.expected THEN 'PASS' ELSE 'FAIL' END AS result
FROM   checks AS ch
ORDER  BY ch.check_id;


-- ===========================================================================
-- S. METRICS SUMMARY -> complaint_metrics.csv
-- One row per metric value, with its grouping and the calculation date.
-- Run this query alone and export the result as CSV.
-- ===========================================================================
WITH params AS (SELECT DATE '2025-02-24' AS as_of_date),
v AS (SELECT * FROM complaint_analyst_view),
closed AS (
    SELECT v.complaint_id, v.category,
           (MAX(i.end_date) - v.created_at::date) AS resolution_days
    FROM   v
    JOIN   investigation AS i ON i.complaint_id = v.complaint_id
    WHERE  NOT v.is_open AND i.end_date IS NOT NULL
    GROUP  BY v.complaint_id, v.category, v.created_at
),
m (sort_key, metric_name, grouping, group_value, metric_value, unit) AS (
    -- overall
    SELECT 1, 'complaint_count',    'overall', 'all', COUNT(*)::numeric, 'complaints' FROM v
    UNION ALL
    SELECT 2, 'distinct_customers', 'overall', 'all', COUNT(DISTINCT customer_id)::numeric, 'customers' FROM v
    UNION ALL
    SELECT 3, 'backlog_count',      'overall', 'all', (COUNT(*) FILTER (WHERE is_open))::numeric, 'complaints' FROM v
    UNION ALL
    SELECT 4, 'customers_with_open_complaint', 'overall', 'all',
           (COUNT(DISTINCT customer_id) FILTER (WHERE is_open))::numeric, 'customers' FROM v
    UNION ALL
    SELECT 3.1, 'escalated_backlog_count', 'overall', 'all',
           (COUNT(*) FILTER (WHERE v.is_open AND (v.status = 'ESCALATED' OR COALESCE(v.review_decisions, '') LIKE '%ESCALATED%')))::numeric, 'complaints' FROM v
    UNION ALL
    SELECT 3.2, 'escalated_by_status_only', 'overall', 'all',
           (COUNT(*) FILTER (WHERE v.is_open AND v.status = 'ESCALATED'))::numeric, 'complaints' FROM v
    UNION ALL
    SELECT 5, 'closed_count',       'overall', 'all', (COUNT(*) FILTER (WHERE NOT is_open))::numeric, 'complaints' FROM v
    UNION ALL
    SELECT 6, 'backlog_avg_age_days', 'overall', 'all',
           ROUND(AVG(p.as_of_date - v.created_at::date), 1), 'days'
    FROM v CROSS JOIN params AS p WHERE v.is_open
    UNION ALL
    SELECT 7, 'avg_resolution_days', 'overall', 'all', ROUND(AVG(resolution_days), 1), 'days' FROM closed
    UNION ALL
    -- by category
    SELECT 10, 'complaint_count',    'category', category, COUNT(*)::numeric, 'complaints' FROM v GROUP BY category
    UNION ALL
    SELECT 11, 'distinct_customers', 'category', category, COUNT(DISTINCT customer_id)::numeric, 'customers' FROM v GROUP BY category
    UNION ALL
    SELECT 12, 'closed_count',       'category', cat.category, COUNT(cl.complaint_id)::numeric, 'complaints'
    FROM (SELECT DISTINCT category FROM v) AS cat LEFT JOIN closed AS cl ON cl.category = cat.category
    GROUP BY cat.category
    UNION ALL
    SELECT 13, 'avg_resolution_days','category', cat.category, ROUND(AVG(cl.resolution_days), 1), 'days'
    FROM (SELECT DISTINCT category FROM v) AS cat LEFT JOIN closed AS cl ON cl.category = cat.category
    GROUP BY cat.category
    UNION ALL
    -- by status
    SELECT 20, 'complaint_count',    'status', status, COUNT(*)::numeric, 'complaints' FROM v GROUP BY status
    UNION ALL
    SELECT 21, 'distinct_customers', 'status', status, COUNT(DISTINCT customer_id)::numeric, 'customers' FROM v GROUP BY status
    UNION ALL
    -- by month opened
    SELECT 30, 'complaint_count',    'opened_month', TO_CHAR(DATE_TRUNC('month', created_at), 'YYYY-MM'),
           COUNT(*)::numeric, 'complaints' FROM v GROUP BY DATE_TRUNC('month', created_at)
    UNION ALL
    SELECT 31, 'distinct_customers', 'opened_month', TO_CHAR(DATE_TRUNC('month', created_at), 'YYYY-MM'),
           COUNT(DISTINCT customer_id)::numeric, 'customers' FROM v GROUP BY DATE_TRUNC('month', created_at)
    UNION ALL
    -- backlog by priority
    SELECT 40, 'backlog_count',      'priority', priority, COUNT(*)::numeric, 'complaints'
    FROM v WHERE is_open GROUP BY priority
)
SELECT m.metric_name,
       m.grouping,
       m.group_value,
       m.metric_value,                 -- NULL = no data to measure (not zero)
       m.unit,
       CURRENT_DATE                     AS calculation_date,
       (SELECT as_of_date FROM params)  AS as_of_date
FROM   m
ORDER  BY m.sort_key, m.grouping, m.group_value;