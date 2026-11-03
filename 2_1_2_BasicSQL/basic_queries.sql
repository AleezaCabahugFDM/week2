-- ============================================================================
-- basic_queries.sql  (Week 2 | Exercise 2.1.2 - Query Complaint Data)
-- Database: built by database_schema.sql from Exercise 2.1.1 (PostgreSQL)
--
-- Run with defaults:
--   psql -d complaints -f basic_queries.sql
-- Run with your own values (any parameter can be overridden):
--   psql -d complaints -v customer_id=CUS003 -v start_date=2025-02-01 \
--        -v end_date=2025-03-01 -f basic_queries.sql
--
-- Parameters use psql variables (:'name' = safely quoted literal).
-- In an API these become bind placeholders ($1, %s, ?), never string concatenation.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Parameter defaults (only applied if not passed with -v)
-- ---------------------------------------------------------------------------
\if :{?customer_id}   \else \set customer_id   'CUS001'      \endif
\if :{?priority}      \else \set priority      'High'        \endif
\if :{?category}      \else \set category      'Fee Dispute' \endif
\if :{?start_date}    \else \set start_date    '2025-02-01'  \endif
\if :{?end_date}      \else \set end_date      '2025-03-01'  \endif
\if :{?as_of_date}    \else \set as_of_date    '2025-02-24'  \endif
\if :{?days_back}     \else \set days_back     7             \endif
\if :{?keyword}       \else \set keyword       'fee'         \endif
\if :{?min_complaints}\else \set min_complaints 3            \endif
\if :{?row_limit}     \else \set row_limit     5             \endif

\pset null '(null)'


-- ===========================================================================
-- A. OPEN CASES
-- "Open" = any status that is not RESOLVED or CLOSED (i.e. still needs work).
-- ===========================================================================

-- Q01: How many complaints are in each status?
SELECT c.status        AS complaint_status,
       COUNT(*)        AS complaint_count
FROM   complaint AS c
GROUP  BY c.status
ORDER  BY complaint_count DESC, complaint_status;

-- Q02: How many complaints are still open (not RESOLVED or CLOSED)?
SELECT COUNT(*) AS open_complaint_count
FROM   complaint AS c
WHERE  c.status NOT IN ('RESOLVED', 'CLOSED');

-- Q03: List all open complaints, most urgent first, then oldest first.
SELECT c.complaint_id,
       c.customer_id,
       c.category,
       c.priority,
       c.status,
       c.created_at
FROM   complaint AS c
WHERE  c.status NOT IN ('RESOLVED', 'CLOSED')
ORDER  BY CASE c.priority
            WHEN 'Critical' THEN 1
            WHEN 'High'     THEN 2
            WHEN 'Medium'   THEN 3
            WHEN 'Low'      THEN 4
          END,
          c.created_at;


-- ===========================================================================
-- B. PRIORITIES
-- ===========================================================================

-- Q04: How many complaints are there at each priority level?
SELECT c.priority  AS priority,
       COUNT(*)    AS complaint_count
FROM   complaint AS c
GROUP  BY c.priority
ORDER  BY CASE c.priority
            WHEN 'Critical' THEN 1 WHEN 'High' THEN 2
            WHEN 'Medium'   THEN 3 WHEN 'Low'  THEN 4
          END;

-- Q05: Which open complaints are High or Critical priority (escalation list)?
SELECT c.complaint_id,
       c.customer_id,
       c.category,
       c.priority,
       c.status,
       c.created_at
FROM   complaint AS c
WHERE  c.priority IN ('High', 'Critical')
  AND  c.status NOT IN ('RESOLVED', 'CLOSED')
ORDER  BY CASE c.priority WHEN 'Critical' THEN 1 ELSE 2 END, c.created_at;

-- Q06: Which complaints have a given priority? [parameter: priority]
SELECT c.complaint_id,
       c.category,
       c.status,
       c.created_at
FROM   complaint AS c
WHERE  c.priority = :'priority'
ORDER  BY c.created_at;


-- ===========================================================================
-- C. CATEGORIES AND CHANNELS
-- ===========================================================================

-- Q07: How many complaints are there per category, and how many of those are open?
SELECT c.category                                                       AS category,
       COUNT(*)                                                         AS total_complaints,
       COUNT(*) FILTER (WHERE c.status NOT IN ('RESOLVED', 'CLOSED'))   AS open_complaints
FROM   complaint AS c
GROUP  BY c.category
ORDER  BY total_complaints DESC, category;

-- Q08: Which complaints belong to a given category? [parameter: category]
SELECT c.complaint_id,
       c.customer_id,
       c.priority,
       c.status,
       c.customer_narrative
FROM   complaint AS c
WHERE  c.category = :'category'
ORDER  BY c.complaint_id;

-- Q09: How many complaints arrived through each channel?
SELECT c.channel   AS channel,
       COUNT(*)    AS complaint_count
FROM   complaint AS c
GROUP  BY c.channel
ORDER  BY complaint_count DESC, channel;

-- Q10: Which complaints mention a keyword in the customer's own words? [parameter: keyword]
--      Case-insensitive; the keyword is quoted by psql, so it cannot inject SQL.
SELECT c.complaint_id,
       c.category,
       c.customer_narrative
FROM   complaint AS c
WHERE  c.customer_narrative ILIKE '%' || :'keyword' || '%'
ORDER  BY c.complaint_id;


-- ===========================================================================
-- D. CUSTOMERS
-- ===========================================================================

-- Q11: What complaints has a given customer raised? [parameter: customer_id]
SELECT c.complaint_id,
       c.account_id,
       c.category,
       c.priority,
       c.status,
       c.created_at
FROM   complaint AS c
WHERE  c.customer_id = :'customer_id'
ORDER  BY c.created_at;

-- Q12: How many complaints has each customer raised (repeat complainants first)?
SELECT c.customer_id                                                    AS customer_id,
       COUNT(*)                                                         AS total_complaints,
       COUNT(*) FILTER (WHERE c.status NOT IN ('RESOLVED', 'CLOSED'))   AS open_complaints
FROM   complaint AS c
GROUP  BY c.customer_id
ORDER  BY total_complaints DESC, customer_id;

-- Q13: Which customers have at least N complaints? [parameter: min_complaints]
SELECT c.customer_id  AS customer_id,
       COUNT(*)       AS total_complaints
FROM   complaint AS c
GROUP  BY c.customer_id
HAVING COUNT(*) >= :min_complaints
ORDER  BY total_complaints DESC, customer_id;

-- Q14: Which complaints are not linked to any account? (NULL handling)
SELECT c.complaint_id,
       c.customer_id,
       c.category,
       c.customer_narrative
FROM   complaint AS c
WHERE  c.account_id IS NULL
ORDER  BY c.complaint_id;

-- Q15: How many complaints are linked vs not linked to an account?
SELECT CASE WHEN c.account_id IS NULL THEN 'No account' ELSE 'Linked to account' END AS account_link,
       COUNT(*)                                                                    AS complaint_count
FROM   complaint AS c
GROUP  BY CASE WHEN c.account_id IS NULL THEN 'No account' ELSE 'Linked to account' END
ORDER  BY account_link DESC;


-- ===========================================================================
-- E. RECENT ACTIVITY AND DATES
-- The seed data is from Jan-Feb 2025, so "recent" is measured from an
-- as-of date parameter, not from today's date (which would return nothing).
-- ===========================================================================

-- Q16: Which complaints were received in a date range? [parameters: start_date, end_date]
--      Half-open range: start_date inclusive, end_date exclusive.
SELECT c.complaint_id,
       c.customer_id,
       c.category,
       c.status,
       c.created_at
FROM   complaint AS c
WHERE  c.created_at >= :'start_date'::date
  AND  c.created_at <  :'end_date'::date
ORDER  BY c.created_at;

-- Q17: Which complaints arrived in the last N days before the as-of date?
--      [parameters: as_of_date, days_back]
SELECT c.complaint_id,
       c.category,
       c.priority,
       c.status,
       c.created_at
FROM   complaint AS c
WHERE  c.created_at >= :'as_of_date'::date - (:days_back * INTERVAL '1 day')
  AND  c.created_at <  :'as_of_date'::date + INTERVAL '1 day'
ORDER  BY c.created_at DESC;

-- Q18: What are the N most recent complaints? [parameter: row_limit]
SELECT c.complaint_id,
       c.customer_id,
       c.category,
       c.status,
       c.created_at
FROM   complaint AS c
ORDER  BY c.created_at DESC, c.complaint_id DESC
LIMIT  :row_limit;

-- Q19: How many complaints were received per month?
SELECT TO_CHAR(DATE_TRUNC('month', c.created_at), 'YYYY-MM')  AS received_month,
       COUNT(*)                                               AS complaint_count
FROM   complaint AS c
GROUP  BY DATE_TRUNC('month', c.created_at)
ORDER  BY DATE_TRUNC('month', c.created_at);

-- Q20: How long has each open complaint been open, as of the as-of date? [parameter: as_of_date]
SELECT c.complaint_id,
       c.priority,
       c.status,
       c.created_at,
       (:'as_of_date'::date - c.created_at::date) AS days_open
FROM   complaint AS c
WHERE  c.status NOT IN ('RESOLVED', 'CLOSED')
ORDER  BY days_open DESC, c.complaint_id;


-- ===========================================================================
-- F. WORKLOAD AND SUPPORTING DATA
-- ===========================================================================

-- Q21: How many open complaints does each assigned employee hold? (unassigned shown explicitly)
SELECT COALESCE(c.assigned_employee_id, '(unassigned)')  AS assigned_employee_id,
       COUNT(*)                                          AS open_complaints
FROM   complaint AS c
WHERE  c.status NOT IN ('RESOLVED', 'CLOSED')
GROUP  BY COALESCE(c.assigned_employee_id, '(unassigned)')
ORDER  BY open_complaints DESC, assigned_employee_id;

-- Q22: What is the total of fees not yet reversed, per account?
SELECT f.account_id          AS account_id,
       COUNT(*)              AS fee_count,
       SUM(f.amount)         AS unreversed_fee_total
FROM   fee AS f
WHERE  f.reversed = FALSE
GROUP  BY f.account_id
ORDER  BY unreversed_fee_total DESC, account_id;

-- Q23: Which service requests are still open, and for how many days (as of the as-of date)?
SELECT sr.request_id,
       sr.customer_id,
       sr.request_type,
       sr.status,
       sr.created_date,
       (:'as_of_date'::date - sr.created_date) AS days_open
FROM   service_request AS sr
WHERE  sr.closed_date IS NULL
ORDER  BY days_open DESC, sr.request_id;


-- ===========================================================================
-- V. VALIDATION CHECKS (expected vs actual; each row returns PASS or FAIL)
-- ===========================================================================

-- V01: Status counts (Q01) add up to the total number of complaints.
SELECT 'V01 status counts sum to total' AS check_name,
       (SELECT SUM(n) FROM (SELECT COUNT(*) AS n FROM complaint GROUP BY status) s) AS actual,
       (SELECT COUNT(*) FROM complaint) AS expected,
       CASE WHEN (SELECT SUM(n) FROM (SELECT COUNT(*) AS n FROM complaint GROUP BY status) s)
               = (SELECT COUNT(*) FROM complaint) THEN 'PASS' ELSE 'FAIL' END AS result;

-- V02: Open (Q02) + closed/resolved = total.
SELECT 'V02 open + closed = total' AS check_name,
       (SELECT COUNT(*) FROM complaint WHERE status NOT IN ('RESOLVED','CLOSED'))
     + (SELECT COUNT(*) FROM complaint WHERE status IN ('RESOLVED','CLOSED')) AS actual,
       (SELECT COUNT(*) FROM complaint) AS expected,
       CASE WHEN (SELECT COUNT(*) FROM complaint WHERE status NOT IN ('RESOLVED','CLOSED'))
               + (SELECT COUNT(*) FROM complaint WHERE status IN ('RESOLVED','CLOSED'))
               = (SELECT COUNT(*) FROM complaint) THEN 'PASS' ELSE 'FAIL' END AS result;

-- V03: Priority counts (Q04) add up to the total.
SELECT 'V03 priority counts sum to total' AS check_name,
       (SELECT SUM(n) FROM (SELECT COUNT(*) AS n FROM complaint GROUP BY priority) s) AS actual,
       (SELECT COUNT(*) FROM complaint) AS expected,
       CASE WHEN (SELECT SUM(n) FROM (SELECT COUNT(*) AS n FROM complaint GROUP BY priority) s)
               = (SELECT COUNT(*) FROM complaint) THEN 'PASS' ELSE 'FAIL' END AS result;

-- V04: Linked + unlinked (Q15) = total; NULL accounts are not silently dropped.
SELECT 'V04 account linked + unlinked = total' AS check_name,
       (SELECT COUNT(account_id) FROM complaint) + (SELECT COUNT(*) FROM complaint WHERE account_id IS NULL) AS actual,
       (SELECT COUNT(*) FROM complaint) AS expected,
       CASE WHEN (SELECT COUNT(account_id) FROM complaint) + (SELECT COUNT(*) FROM complaint WHERE account_id IS NULL)
               = (SELECT COUNT(*) FROM complaint) THEN 'PASS' ELSE 'FAIL' END AS result;

-- V05: NULL trap: "account_id <> 'ACC001'" misses NULL rows; IS DISTINCT FROM keeps them.
SELECT 'V05 <> drops NULLs, IS DISTINCT FROM keeps them' AS check_name,
       (SELECT COUNT(*) FROM complaint WHERE account_id IS DISTINCT FROM 'ACC001')
     - (SELECT COUNT(*) FROM complaint WHERE account_id <> 'ACC001') AS actual,
       (SELECT COUNT(*) FROM complaint WHERE account_id IS NULL) AS expected,
       CASE WHEN (SELECT COUNT(*) FROM complaint WHERE account_id IS DISTINCT FROM 'ACC001')
               - (SELECT COUNT(*) FROM complaint WHERE account_id <> 'ACC001')
               = (SELECT COUNT(*) FROM complaint WHERE account_id IS NULL) THEN 'PASS' ELSE 'FAIL' END AS result;

-- V06: Boundary - a complaint created exactly at the start of the range is included
--      (CMP011 at 2025-02-01 09:15 is the first February complaint).
SELECT 'V06 date range includes start boundary' AS check_name,
       (SELECT COUNT(*) FROM complaint WHERE complaint_id = 'CMP011'
          AND created_at >= DATE '2025-02-01' AND created_at < DATE '2025-03-01') AS actual,
       1 AS expected,
       CASE WHEN (SELECT COUNT(*) FROM complaint WHERE complaint_id = 'CMP011'
          AND created_at >= DATE '2025-02-01' AND created_at < DATE '2025-03-01') = 1
            THEN 'PASS' ELSE 'FAIL' END AS result;

-- V07: Boundary - "BETWEEN '2025-01-01' AND '2025-01-31'" misses timestamps later on Jan 31;
--      the half-open range does not. January + February ranges must cover every complaint.
SELECT 'V07 Jan + Feb half-open ranges cover all rows' AS check_name,
       (SELECT COUNT(*) FROM complaint WHERE created_at >= DATE '2025-01-01' AND created_at < DATE '2025-02-01')
     + (SELECT COUNT(*) FROM complaint WHERE created_at >= DATE '2025-02-01' AND created_at < DATE '2025-03-01') AS actual,
       (SELECT COUNT(*) FROM complaint) AS expected,
       CASE WHEN (SELECT COUNT(*) FROM complaint WHERE created_at >= DATE '2025-01-01' AND created_at < DATE '2025-02-01')
               + (SELECT COUNT(*) FROM complaint WHERE created_at >= DATE '2025-02-01' AND created_at < DATE '2025-03-01')
               = (SELECT COUNT(*) FROM complaint) THEN 'PASS' ELSE 'FAIL' END AS result;

-- V08: Negative - an unknown customer returns zero rows, not an error.
SELECT 'V08 unknown customer returns 0 rows' AS check_name,
       (SELECT COUNT(*) FROM complaint WHERE customer_id = 'CUS999') AS actual,
       0 AS expected,
       CASE WHEN (SELECT COUNT(*) FROM complaint WHERE customer_id = 'CUS999') = 0
            THEN 'PASS' ELSE 'FAIL' END AS result;

-- V09: Negative - an injection-style value is treated as plain text and matches nothing.
SELECT 'V09 injection-style input matches nothing' AS check_name,
       (SELECT COUNT(*) FROM complaint WHERE customer_id = $v$CUS001' OR '1'='1$v$) AS actual,
       0 AS expected,
       CASE WHEN (SELECT COUNT(*) FROM complaint WHERE customer_id = $v$CUS001' OR '1'='1$v$) = 0
            THEN 'PASS' ELSE 'FAIL' END AS result;

-- V10: Negative - values are case-sensitive: 'high' is not a valid priority and returns 0 rows.
SELECT 'V10 wrong-case priority returns 0 rows' AS check_name,
       (SELECT COUNT(*) FROM complaint WHERE priority = 'high') AS actual,
       0 AS expected,
       CASE WHEN (SELECT COUNT(*) FROM complaint WHERE priority = 'high') = 0
            THEN 'PASS' ELSE 'FAIL' END AS result;

-- V11: Category totals (Q07) add up to the total.
SELECT 'V11 category counts sum to total' AS check_name,
       (SELECT SUM(n) FROM (SELECT COUNT(*) AS n FROM complaint GROUP BY category) s) AS actual,
       (SELECT COUNT(*) FROM complaint) AS expected,
       CASE WHEN (SELECT SUM(n) FROM (SELECT COUNT(*) AS n FROM complaint GROUP BY category) s)
               = (SELECT COUNT(*) FROM complaint) THEN 'PASS' ELSE 'FAIL' END AS result;

-- V12: Every open service request has status OPEN or IN_PROGRESS (no closed rows without a date).
SELECT 'V12 open service requests have open status' AS check_name,
       (SELECT COUNT(*) FROM service_request WHERE closed_date IS NULL AND status = 'CLOSED') AS actual,
       0 AS expected,
       CASE WHEN (SELECT COUNT(*) FROM service_request WHERE closed_date IS NULL AND status = 'CLOSED') = 0
            THEN 'PASS' ELSE 'FAIL' END AS result;