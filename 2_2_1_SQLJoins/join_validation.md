-- ============================================================================
-- join_queries.sql   Week 2 | Exercise 2.2.1 - Join Customer, Account and
--                    Complaint Context
-- Database: built by database_schema.sql in Exercise 2.1.1 (PostgreSQL 16)
--
-- Answers join_query_questions.md:
--   J1  Show each complaint with customer name.
--   J2  Add optional account type without dropping complaints with no account.
--   J3  Verify distinct complaint count before and after joins.
--   (Question 4, complaint_analyst_view, is in complaint_analyst_view.sql.)
-- Then V01-V07: validation checks that return PASS / FAIL.
--
-- Plain SQL: runs in psql and the Supabase SQL Editor.
--   psql:      psql -d complaints -f join_queries.sql
--   Supabase:  highlight one query and press Run (the editor shows only the
--              last result; running the whole file shows the check table).
--
-- JOIN RULES
--   complaint -> customer : INNER JOIN. Every complaint must have a customer
--                           (customer_id is NOT NULL with a foreign key).
--   complaint -> account  : LEFT JOIN. account_id is optional; 3 complaints
--                           (CMP023, CMP029, CMP030) have none.
--   Grain: ONE ROW PER COMPLAINT. Each join goes to the "one" side
--   (a complaint has one customer and at most one account), so no row repeats.
-- ============================================================================


-- ===========================================================================
-- J1. Show each complaint with customer name.
-- INNER JOIN: the customer relationship is mandatory.
-- ===========================================================================
SELECT c.complaint_id,
       c.customer_id,
       cu.first_name || ' ' || cu.last_name AS customer_name,
       c.category,
       c.priority,
       c.status,
       c.created_at
FROM   complaint AS c
INNER  JOIN customer AS cu ON cu.customer_id = c.customer_id
ORDER  BY c.complaint_id;


-- ===========================================================================
-- J2. Add optional account type without dropping complaints that have no account.
-- LEFT JOIN keeps every complaint. Where there is no account, account_id and
-- account_type come back NULL, and account_link says so in words.
-- ===========================================================================
SELECT c.complaint_id,
       c.customer_id,
       cu.first_name || ' ' || cu.last_name AS customer_name,
       c.account_id,
       a.account_type,
       CASE WHEN c.account_id IS NULL THEN 'No account'
            ELSE 'Linked to account' END     AS account_link,
       c.category,
       c.priority,
       c.status,
       c.created_at
FROM   complaint AS c
INNER  JOIN customer AS cu ON cu.customer_id = c.customer_id
LEFT   JOIN account  AS a  ON a.account_id   = c.account_id
ORDER  BY c.complaint_id;


-- ===========================================================================
-- J2-WRONG (for comparison only). The same query with INNER JOIN to account
-- silently drops the 3 complaints that have no account: 27 rows, not 30.
-- ===========================================================================
SELECT c.complaint_id,
       a.account_type
FROM   complaint AS c
INNER  JOIN customer AS cu ON cu.customer_id = c.customer_id
INNER  JOIN account  AS a  ON a.account_id   = c.account_id     -- wrong join type
ORDER  BY c.complaint_id;


-- ===========================================================================
-- J3. Verify distinct complaint count before and after joins.
-- COUNT(*) counts rows; COUNT(DISTINCT complaint_id) counts complaints.
-- If they differ, a join has duplicated complaints. If they drop below 30,
-- a join has lost complaints.
-- ===========================================================================
SELECT '1. complaint only'                         AS join_step,
       COUNT(*)                                    AS row_count,
       COUNT(DISTINCT c.complaint_id)              AS distinct_complaints
FROM   complaint AS c
UNION ALL
SELECT '2. + INNER JOIN customer',
       COUNT(*),
       COUNT(DISTINCT c.complaint_id)
FROM   complaint AS c
INNER  JOIN customer AS cu ON cu.customer_id = c.customer_id
UNION ALL
SELECT '3. + LEFT JOIN account (correct)',
       COUNT(*),
       COUNT(DISTINCT c.complaint_id)
FROM   complaint AS c
INNER  JOIN customer AS cu ON cu.customer_id = c.customer_id
LEFT   JOIN account  AS a  ON a.account_id   = c.account_id
UNION ALL
SELECT '4. + INNER JOIN account (wrong: loses rows)',
       COUNT(*),
       COUNT(DISTINCT c.complaint_id)
FROM   complaint AS c
INNER  JOIN customer AS cu ON cu.customer_id = c.customer_id
INNER  JOIN account  AS a  ON a.account_id   = c.account_id
UNION ALL
-- One-to-many trap: a customer can have MANY accounts. Joining account on
-- customer_id (instead of account_id) repeats a complaint once per account
-- the customer owns. In the seed data every customer has one account, so
-- step 5 adds a SECOND account for CUS001 in memory (nothing is inserted)
-- to show what happens.
SELECT '5. + account ON customer_id, CUS001 with 2 accounts (wrong: duplicates)',
       COUNT(*),
       COUNT(DISTINCT c.complaint_id)
FROM   complaint AS c
INNER  JOIN customer AS cu ON cu.customer_id = c.customer_id
LEFT   JOIN (SELECT a.account_id, a.customer_id, a.account_type FROM account AS a
             UNION ALL
             SELECT 'ACC_TEST', 'CUS001', 'Savings') AS a2
       ON a2.customer_id = c.customer_id
UNION ALL
SELECT '6. + account ON account_id, same 2 accounts (correct: no duplicates)',
       COUNT(*),
       COUNT(DISTINCT c.complaint_id)
FROM   complaint AS c
INNER  JOIN customer AS cu ON cu.customer_id = c.customer_id
LEFT   JOIN (SELECT a.account_id, a.customer_id, a.account_type FROM account AS a
             UNION ALL
             SELECT 'ACC_TEST', 'CUS001', 'Savings') AS a2
       ON a2.account_id = c.account_id
ORDER  BY join_step;


-- ===========================================================================
-- V. VALIDATION CHECKS - one result table, each row PASS or FAIL.
-- ===========================================================================
WITH
j2 AS (
    SELECT c.complaint_id, c.account_id, a.account_type
    FROM   complaint AS c
    INNER  JOIN customer AS cu ON cu.customer_id = c.customer_id
    LEFT   JOIN account  AS a  ON a.account_id   = c.account_id
),
checks (check_id, check_name, expected, actual) AS (
    SELECT 'V01', 'J1 returns every complaint once (INNER JOIN customer loses none)',
           (SELECT COUNT(*) FROM complaint),
           (SELECT COUNT(DISTINCT c.complaint_id) FROM complaint AS c
              INNER JOIN customer AS cu ON cu.customer_id = c.customer_id)
    UNION ALL
    SELECT 'V02', 'J1 every complaint has a customer name (no NULL names)',
           0,
           (SELECT COUNT(*) FROM complaint AS c
              INNER JOIN customer AS cu ON cu.customer_id = c.customer_id
             WHERE cu.first_name IS NULL OR cu.last_name IS NULL)
    UNION ALL
    SELECT 'V03', 'J2 row count = complaint count (LEFT JOIN keeps all 30)',
           (SELECT COUNT(*) FROM complaint),
           (SELECT COUNT(*) FROM j2)
    UNION ALL
    SELECT 'V04', 'J2 no duplicates: COUNT(*) = COUNT(DISTINCT complaint_id)',
           (SELECT COUNT(DISTINCT complaint_id) FROM j2),
           (SELECT COUNT(*) FROM j2)
    UNION ALL
    SELECT 'V05', 'J2 complaints with no account are kept (CMP023, CMP029, CMP030)',
           3,
           (SELECT COUNT(*) FROM j2
             WHERE account_id IS NULL AND account_type IS NULL
               AND complaint_id IN ('CMP023', 'CMP029', 'CMP030'))
    UNION ALL
    SELECT 'V06', 'J2 every linked complaint found its account_type',
           0,
           (SELECT COUNT(*) FROM j2 WHERE account_id IS NOT NULL AND account_type IS NULL)
    UNION ALL
    SELECT 'V07', 'Negative: INNER JOIN account would lose exactly the 3 no-account complaints',
           3,
           (SELECT COUNT(*) FROM complaint)
         - (SELECT COUNT(*) FROM complaint AS c
              INNER JOIN account AS a ON a.account_id = c.account_id)
)
SELECT ch.check_id,
       ch.check_name,
       ch.expected,
       ch.actual,
       CASE WHEN ch.actual = ch.expected THEN 'PASS' ELSE 'FAIL' END AS result
FROM   checks AS ch
ORDER  BY ch.check_id;