-- ============================================================================
-- basic_queries.sql   Week 2 | Exercise 2.1.2 - Query Complaint Data
-- Database: built by database_schema.sql in Exercise 2.1.1 (PostgreSQL 16)
--
-- Answers the 8 questions in basic_query_questions.md (Q1-Q8), then runs
-- validation checks (V01-V14) that return PASS / FAIL.
--
-- Plain SQL: runs unchanged in psql, the Supabase SQL Editor, pgAdmin, DBeaver.
--   psql:      psql -d complaints -f basic_queries.sql   (shows every result)
--   Supabase:  highlight one query and press Run (the editor shows only the
--              last result; running the whole file shows the check table).
--
-- PARAMETERS
-- User-supplied values (Q5 customer ID, Q6 date range) are set in ONE place,
-- a "params" CTE at the top of the query. Change the value there; the query
-- body never contains the literal. In the API (later exercises) the params
-- CTE is replaced by bind placeholders, e.g. WHERE c.customer_id = $1
-- (psycopg: %s), never by string concatenation.
--
-- DEFINITIONS USED THROUGHOUT
--   open / unresolved  = status NOT IN ('RESOLVED','CLOSED')
--   high priority      = priority IN ('High','Critical')
--   date_closed        = the complaint table has no date_closed column; the
--                        closure date is the status_timestamp of the status
--                        history row that moved the complaint to RESOLVED or
--                        CLOSED (see query_notes.md, section 3).
-- ============================================================================


-- ===========================================================================
-- Q1. List all open complaints.
-- "Open" = still needs work: any status except RESOLVED or CLOSED
-- (OPEN, IN_PROGRESS, UNDER_REVIEW, PENDING_APPROVAL, CHANGES_REQUESTED, ESCALATED).
-- Most urgent first, then oldest first.
-- ===========================================================================
SELECT c.complaint_id,
       c.customer_id,
       c.account_id,
       c.category,
       c.priority,
       c.status,
       c.created_at,
       c.assigned_employee_id
FROM   complaint AS c
WHERE  c.status NOT IN ('RESOLVED', 'CLOSED')
ORDER  BY CASE c.priority
            WHEN 'Critical' THEN 1
            WHEN 'High'     THEN 2
            WHEN 'Medium'   THEN 3
            WHEN 'Low'      THEN 4
          END,
          c.created_at,
          c.complaint_id;


-- ===========================================================================
-- Q2. List high-priority unresolved complaints.
-- High priority = High or Critical (Critical is above High, so it is included).
-- Unresolved    = same definition as "open" in Q1.
-- ===========================================================================
SELECT c.complaint_id,
       c.customer_id,
       c.category,
       c.priority,
       c.status,
       c.created_at,
       c.assigned_employee_id
FROM   complaint AS c
WHERE  c.priority IN ('High', 'Critical')
  AND  c.status NOT IN ('RESOLVED', 'CLOSED')
ORDER  BY CASE c.priority WHEN 'Critical' THEN 1 ELSE 2 END,
          c.created_at,
          c.complaint_id;


-- ===========================================================================
-- Q3. Count complaints by status.
-- ===========================================================================
SELECT c.status   AS complaint_status,
       COUNT(*)   AS complaint_count
FROM   complaint AS c
GROUP  BY c.status
ORDER  BY complaint_count DESC, complaint_status;


-- ===========================================================================
-- Q4. Count complaints by category.
-- ===========================================================================
SELECT c.category  AS category,
       COUNT(*)    AS complaint_count
FROM   complaint AS c
GROUP  BY c.category
ORDER  BY complaint_count DESC, category;


-- ===========================================================================
-- Q5. Show complaints for a supplied customer ID.        [parameter: customer_id]
-- Complaints with no linked account (account_id NULL) are still returned,
-- because the filter is on customer_id only.
-- ===========================================================================
WITH params AS (
    SELECT 'CUS009'::varchar AS customer_id          -- <-- supplied value
)
SELECT c.complaint_id,
       c.customer_id,
       c.account_id,
       c.category,
       c.priority,
       c.status,
       c.created_at
FROM   complaint AS c
JOIN   params    AS p ON c.customer_id = p.customer_id
ORDER  BY c.created_at, c.complaint_id;


-- ===========================================================================
-- Q6. Show complaints opened within a supplied date range.
--     [parameters: start_date, end_date - both INCLUSIVE calendar dates]
-- created_at is a TIMESTAMP, so the range is applied half-open:
--   created_at >= start_date  AND  created_at < end_date + 1 day
-- This includes complaints made at any time on end_date.
-- ===========================================================================
WITH params AS (
    SELECT DATE '2025-02-01' AS start_date,          -- <-- supplied value
           DATE '2025-02-14' AS end_date             -- <-- supplied value
)
SELECT c.complaint_id,
       c.customer_id,
       c.category,
       c.priority,
       c.status,
       c.created_at
FROM   complaint AS c
CROSS  JOIN params AS p
WHERE  c.created_at >= p.start_date
  AND  c.created_at <  p.end_date + 1
ORDER  BY c.created_at, c.complaint_id;


-- ===========================================================================
-- Q7. List closed complaints where date_closed is missing (expected zero).
-- Closed = status RESOLVED or CLOSED. Their closure date comes from the status
-- history row that recorded the move to RESOLVED/CLOSED. LEFT JOIN keeps
-- closed complaints that have no such row; a NULL date_closed = missing.
-- ===========================================================================
WITH closure AS (
    SELECT h.complaint_id,
           MAX(h.status_timestamp) AS date_closed
    FROM   complaint_status_history AS h
    WHERE  h.new_status IN ('RESOLVED', 'CLOSED')
    GROUP  BY h.complaint_id
)
SELECT c.complaint_id,
       c.customer_id,
       c.status,
       c.created_at,
       cl.date_closed
FROM   complaint AS c
LEFT   JOIN closure AS cl ON cl.complaint_id = c.complaint_id
WHERE  c.status IN ('RESOLVED', 'CLOSED')
  AND  cl.date_closed IS NULL
ORDER  BY c.complaint_id;


-- ===========================================================================
-- Q8. Show the ten most recently opened complaints.
-- complaint_id breaks ties so the result is the same on every run.
-- ===========================================================================
SELECT c.complaint_id,
       c.customer_id,
       c.category,
       c.priority,
       c.status,
       c.created_at
FROM   complaint AS c
ORDER  BY c.created_at DESC, c.complaint_id DESC
LIMIT  10;


-- ===========================================================================
-- V. VALIDATION CHECKS - one result table, each row PASS or FAIL.
-- Includes negative and boundary tests. Nothing is inserted or changed.
-- ===========================================================================
WITH
total AS (SELECT COUNT(*) AS n FROM complaint),
open_c AS (
    SELECT c.complaint_id, c.priority
    FROM   complaint AS c
    WHERE  c.status NOT IN ('RESOLVED', 'CLOSED')
),
closure AS (
    SELECT h.complaint_id, MAX(h.status_timestamp) AS date_closed
    FROM   complaint_status_history AS h
    WHERE  h.new_status IN ('RESOLVED', 'CLOSED')
    GROUP  BY h.complaint_id
),
q8 AS (
    SELECT c.complaint_id, c.created_at
    FROM   complaint AS c
    ORDER  BY c.created_at DESC, c.complaint_id DESC
    LIMIT  10
),
checks (check_id, check_name, expected, actual) AS (
    -- Q1: open + closed/resolved account for every complaint
    SELECT 'V01', 'Q1 open + closed/resolved = total complaints',
           (SELECT n FROM total),
           (SELECT COUNT(*) FROM open_c)
         + (SELECT COUNT(*) FROM complaint WHERE status IN ('RESOLVED', 'CLOSED'))
    UNION ALL
    -- Q2: every Q2 row is open AND High/Critical; count matches a direct count
    SELECT 'V02', 'Q2 = open complaints with priority High or Critical',
           (SELECT COUNT(*) FROM open_c WHERE priority IN ('High', 'Critical')),
           (SELECT COUNT(*) FROM complaint
             WHERE priority IN ('High', 'Critical') AND status NOT IN ('RESOLVED', 'CLOSED'))
    UNION ALL
    -- Q3: status counts add up to the total
    SELECT 'V03', 'Q3 status counts sum to total',
           (SELECT n FROM total),
           (SELECT SUM(k) FROM (SELECT COUNT(*) AS k FROM complaint GROUP BY status) s)
    UNION ALL
    -- Q4: category counts add up to the total
    SELECT 'V04', 'Q4 category counts sum to total',
           (SELECT n FROM total),
           (SELECT SUM(k) FROM (SELECT COUNT(*) AS k FROM complaint GROUP BY category) s)
    UNION ALL
    -- Q5 null handling: CUS009 has 3 complaints, one with NULL account (CMP029)
    SELECT 'V05', 'Q5 keeps complaints with NULL account (CUS009 -> 3 rows)',
           3,
           (SELECT COUNT(*) FROM complaint WHERE customer_id = 'CUS009')
    UNION ALL
    -- Q5 negative: unknown customer returns zero rows, not an error
    SELECT 'V06', 'Q5 negative: unknown customer CUS999 returns 0 rows',
           0,
           (SELECT COUNT(*) FROM complaint WHERE customer_id = 'CUS999')
    UNION ALL
    -- Q5 negative: injection-style input is treated as text and matches nothing
    SELECT 'V07', 'Q5 negative: injection-style customer ID returns 0 rows',
           0,
           (SELECT COUNT(*) FROM complaint WHERE customer_id = $v$CUS001' OR '1'='1$v$)
    UNION ALL
    -- Q6 boundary: CMP030 was created 2025-02-24 13:15. A one-day range on
    -- 2025-02-24 must include it; BETWEEN on the same date would miss it.
    SELECT 'V08', 'Q6 boundary: end date is inclusive (2025-02-24 -> CMP030 found)',
           1,
           (SELECT COUNT(*) FROM complaint
             WHERE created_at >= DATE '2025-02-24' AND created_at < DATE '2025-02-24' + 1)
    UNION ALL
    -- Q6 boundary: January + February ranges cover every complaint, no gaps/overlap
    SELECT 'V09', 'Q6 boundary: Jan 1-31 + Feb 1-28 ranges cover all complaints',
           (SELECT n FROM total),
           (SELECT COUNT(*) FROM complaint
             WHERE created_at >= DATE '2025-01-01' AND created_at < DATE '2025-01-31' + 1)
         + (SELECT COUNT(*) FROM complaint
             WHERE created_at >= DATE '2025-02-01' AND created_at < DATE '2025-02-28' + 1)
    UNION ALL
    -- Q6 negative: start date after end date returns zero rows, not an error
    SELECT 'V10', 'Q6 negative: start after end (Feb 14 -> Feb 1) returns 0 rows',
           0,
           (SELECT COUNT(*) FROM complaint
             WHERE created_at >= DATE '2025-02-14' AND created_at < DATE '2025-02-01' + 1)
    UNION ALL
    -- Q7: expected zero closed complaints without a closure date
    SELECT 'V11', 'Q7 closed complaints with missing date_closed = 0',
           0,
           (SELECT COUNT(*) FROM complaint AS c
              LEFT JOIN closure AS cl ON cl.complaint_id = c.complaint_id
             WHERE c.status IN ('RESOLVED', 'CLOSED') AND cl.date_closed IS NULL)
    UNION ALL
    -- Q7 negative: the same logic DOES flag a closed complaint with no closure
    -- record (a test row built in memory, not inserted)
    SELECT 'V12', 'Q7 negative: logic flags a test CLOSED complaint with no history',
           1,
           (SELECT COUNT(*) FROM (VALUES ('TEST01'::varchar, 'CLOSED'::varchar)) AS t(complaint_id, status)
              LEFT JOIN closure AS cl ON cl.complaint_id = t.complaint_id
             WHERE t.status IN ('RESOLVED', 'CLOSED') AND cl.date_closed IS NULL)
    UNION ALL
    -- Q8: exactly 10 rows, and no complaint outside them is newer
    SELECT 'V13', 'Q8 returns 10 rows and none outside them is newer',
           10,
           CASE WHEN (SELECT COUNT(*) FROM q8) = 10
                 AND NOT EXISTS (SELECT 1 FROM complaint AS c
                                  WHERE c.complaint_id NOT IN (SELECT complaint_id FROM q8)
                                    AND c.created_at > (SELECT MIN(created_at) FROM q8))
                THEN 10 ELSE -1 END
    UNION ALL
    -- Exact values are case-sensitive: 'high' is not a valid priority
    SELECT 'V14', 'Negative: wrong-case priority ''high'' returns 0 rows',
           0,
           (SELECT COUNT(*) FROM complaint WHERE priority = 'high')
)
SELECT ch.check_id,
       ch.check_name,
       ch.expected,
       ch.actual,
       CASE WHEN ch.actual = ch.expected THEN 'PASS' ELSE 'FAIL' END AS result
FROM   checks AS ch
ORDER  BY ch.check_id;