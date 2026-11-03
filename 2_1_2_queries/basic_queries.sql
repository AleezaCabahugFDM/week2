-- =====================================================================
-- Exercise 2.1.2: Query Complaint Data
-- File:     basic_queries.sql
-- Database: crs (PostgreSQL 16)
--
-- Run:
--   psql -d crs -v customer_id=CUS001 \
--               -v start_date=2025-02-01 \
--               -v end_date=2025-02-15 \
--               -f basic_queries.sql
--
-- If a variable isn't supplied, the defaults below are used, so the
-- file runs end to end either way.
-- =====================================================================

\if :{?customer_id}
\else
  \set customer_id CUS001
\endif

\if :{?start_date}
\else
  \set start_date 2025-02-01
\endif

\if :{?end_date}
\else
  \set end_date 2025-02-15
\endif

-- ---------------------------------------------------------------------
-- Q1. List all open complaints.
-- "Open" is read as status = 'OPEN'. Expected: 19 rows.
-- (If "open" means "not closed", use c.status <> 'CLOSED' for 29 rows.)
-- Complaints with a NULL account_id are still included.
-- ---------------------------------------------------------------------
SELECT c.complaint_id,
       c.customer_id,
       c.account_id,
       c.category,
       c.priority,
       c.status,
       c.created_at,
       c.assigned_employee_id
FROM   complaint AS c
WHERE  c.status = 'OPEN'
ORDER  BY c.created_at;

-- ---------------------------------------------------------------------
-- Q2. List high-priority complaints that are still unresolved.
-- "High priority" includes Critical; "unresolved" means not CLOSED.
-- Expected: 12 rows (3 Critical, 9 High). Critical rows are listed first.
-- ---------------------------------------------------------------------
SELECT c.complaint_id,
       c.customer_id,
       c.category,
       c.priority,
       c.status,
       c.created_at
FROM   complaint AS c
WHERE  c.priority IN ('High', 'Critical')
  AND  c.status <> 'CLOSED'
ORDER  BY CASE c.priority WHEN 'Critical' THEN 1 ELSE 2 END,
          c.created_at;


-- ---------------------------------------------------------------------
-- Q3. Count complaints by status.
-- Check: the counts add up to 30.
-- ---------------------------------------------------------------------
SELECT c.status,
       COUNT(*) AS complaint_count
FROM   complaint AS c
GROUP  BY c.status
ORDER  BY complaint_count DESC,
          c.status;


-- ---------------------------------------------------------------------
-- Q4. Count complaints by category.
-- Check: the counts add up to 30.
-- ---------------------------------------------------------------------
SELECT c.category,
       COUNT(*) AS complaint_count
FROM   complaint AS c
GROUP  BY c.category
ORDER  BY complaint_count DESC,
          c.category;


-- ---------------------------------------------------------------------
-- Q5. List complaints for a supplied customer ID.
-- Parameter: :customer_id (psql variable, never string concatenation).
-- Example CUS001: 4 rows. Boundary test CUS999: 0 rows, no error.
-- ---------------------------------------------------------------------
SELECT c.complaint_id,
       c.account_id,
       c.channel,
       c.category,
       c.priority,
       c.status,
       c.created_at
FROM   complaint AS c
WHERE  c.customer_id = :'customer_id'
ORDER  BY c.created_at;


-- ---------------------------------------------------------------------
-- Q6. List complaints opened within a supplied date range.
-- Parameters: :start_date, :end_date (inclusive dates).
-- Half-open range (>= start, < end + 1 day) so complaints opened later
-- on the end date are kept. BETWEEN would drop CMP021 (2025-02-15 15:00).
-- Example 2025-02-01 to 2025-02-15: 11 rows (CMP011 to CMP021).
-- ---------------------------------------------------------------------
SELECT c.complaint_id,
       c.customer_id,
       c.category,
       c.priority,
       c.status,
       c.created_at
FROM   complaint AS c
WHERE  c.created_at >= :'start_date'::date
  AND  c.created_at <  :'end_date'::date + INTERVAL '1 day'
ORDER  BY c.created_at;


-- ---------------------------------------------------------------------
-- Q7. Find closed complaints where the close date is missing.
-- Uses IS NULL, because = NULL never matches.
-- Expected 0 rows; actual 1 row (CMP005). This is a real data issue in
-- the seed and is documented in query_notes.md, not hidden.
-- ---------------------------------------------------------------------
SELECT c.complaint_id,
       c.customer_id,
       c.status,
       c.created_at,
       c.date_closed
FROM   complaint AS c
WHERE  c.status = 'CLOSED'
  AND  c.date_closed IS NULL
ORDER  BY c.complaint_id;


-- ---------------------------------------------------------------------
-- Q8. List the ten most recently opened complaints.
-- complaint_id is a tie-breaker so the order is stable.
-- PostgreSQL LIMIT 10 (SQL Server equivalent: SELECT TOP 10).
-- Expected newest first: CMP030 ... CMP021.
-- ---------------------------------------------------------------------
SELECT c.complaint_id,
       c.customer_id,
       c.category,
       c.priority,
       c.status,
       c.created_at
FROM   complaint AS c
ORDER  BY c.created_at DESC,
          c.complaint_id DESC
LIMIT  10;