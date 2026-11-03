-- ============================================================================
-- complaint_analyst_view.sql   Week 2 | Exercise 2.2.1
-- Creates complaint_analyst_view: ONE ROW PER COMPLAINT, for analysts and for
-- the metrics in Exercise 2.2.2.
--
-- Run in psql or the Supabase SQL Editor (safe to re-run; drops nothing).
--   psql -d complaints -f complaint_analyst_view.sql
--
-- JOINS
--   customer : INNER JOIN (mandatory)    account  : LEFT JOIN (optional)
--   employee : LEFT JOIN (optional)      investigation / review: aggregated
--                                         to one row per complaint, then LEFT JOIN
--
-- PERSONAL DATA LEFT OUT ON PURPOSE (not needed to analyse a complaint):
--   customer first_name, last_name, email, phone_number
--   account account_number and balance
--   employee email
-- Analysts can still look a customer up by customer_id if they are allowed to.
--
-- security_invoker = true: the view runs with the permissions of the person
-- querying it, so it cannot be used to read tables they have no access to
-- (recommended by Supabase for views in the public schema).
-- ============================================================================

-- CREATE OR REPLACE: safe to re-run, and nothing is dropped. (If you ever
-- remove or rename a column, PostgreSQL will refuse to replace the view;
-- delete the old view in the Supabase Table Editor, then run this file again.)
CREATE OR REPLACE VIEW complaint_analyst_view
WITH (security_invoker = true) AS
WITH inv AS (           -- one row per complaint
    SELECT i.complaint_id,
           COUNT(*)                    AS investigation_count,
           BOOL_OR(i.end_date IS NULL) AS has_open_investigation
    FROM   investigation AS i
    GROUP  BY i.complaint_id
),
rev AS (                -- one row per complaint
    SELECT rr.complaint_id,
           COUNT(*)                    AS review_request_count,
           STRING_AGG(DISTINCT rd.decision, ', ' ORDER BY rd.decision) AS review_decisions
    FROM   review_request AS rr
    LEFT   JOIN review_decision AS rd ON rd.review_request_id = rr.review_request_id
    GROUP  BY rr.complaint_id
)
SELECT
    -- The complaint itself (why: identify, route and prioritise the case)
    c.complaint_id,
    c.created_at,
    c.channel,
    c.category,
    c.priority,
    c.status,
    (c.status NOT IN ('RESOLVED', 'CLOSED'))        AS is_open,
    c.customer_narrative,     -- the complaint text; analysts need it to work the case

    -- Customer context (why: segment drives service level; no names/contact details)
    cu.customer_id,
    cu.segment                                       AS customer_segment,

    -- Account context (why: what product the complaint is about; NULL = no account)
    a.account_id,
    a.account_type,
    a.status                                         AS account_status,
    (a.account_id IS NOT NULL)                       AS has_account,

    -- Ownership (why: workload; NULL = unassigned)
    c.assigned_employee_id,
    e.role                                           AS assignee_role,

    -- Workflow progress (why: what has been done so far)
    COALESCE(inv.investigation_count, 0)             AS investigation_count,
    COALESCE(inv.has_open_investigation, FALSE)      AS has_open_investigation,
    COALESCE(rev.review_request_count, 0)            AS review_request_count,
    rev.review_decisions
FROM   complaint AS c
INNER  JOIN customer AS cu ON cu.customer_id = c.customer_id
LEFT   JOIN account  AS a  ON a.account_id   = c.account_id
LEFT   JOIN employee AS e  ON e.employee_id  = c.assigned_employee_id
LEFT   JOIN inv            ON inv.complaint_id = c.complaint_id
LEFT   JOIN rev            ON rev.complaint_id = c.complaint_id;

COMMENT ON VIEW complaint_analyst_view IS
    'One row per complaint with customer segment, optional account, assignee and workflow counts. Excludes customer names/contact details, account number and balance.';


-- ===========================================================================
-- CHECKS - the view keeps the complaint grain and hides personal data.
-- ===========================================================================
WITH checks (check_id, check_name, expected, actual) AS (
    SELECT 'C01', 'View rows = complaint rows',
           (SELECT COUNT(*) FROM complaint), (SELECT COUNT(*) FROM complaint_analyst_view)
    UNION ALL
    SELECT 'C02', 'No duplicates: COUNT(DISTINCT complaint_id) = COUNT(*)',
           (SELECT COUNT(*) FROM complaint_analyst_view),
           (SELECT COUNT(DISTINCT complaint_id) FROM complaint_analyst_view)
    UNION ALL
    SELECT 'C03', 'Complaints without an account are in the view (3)',
           3, (SELECT COUNT(*) FROM complaint_analyst_view WHERE account_id IS NULL)
    UNION ALL
    SELECT 'C04', 'Every complaint ID in the table is in the view',
           0, (SELECT COUNT(*) FROM complaint AS c
                WHERE NOT EXISTS (SELECT 1 FROM complaint_analyst_view AS v
                                   WHERE v.complaint_id = c.complaint_id))
    UNION ALL
    SELECT 'C05', 'No personal-data columns exposed (names, email, phone, account number, balance)',
           0, (SELECT COUNT(*) FROM information_schema.columns
                WHERE table_name = 'complaint_analyst_view'
                  AND column_name IN ('first_name', 'last_name', 'email', 'phone_number',
                                      'account_number', 'balance'))
    UNION ALL
    SELECT 'C06', 'Open count in view matches complaint table (29)',
           (SELECT COUNT(*) FROM complaint WHERE status NOT IN ('RESOLVED', 'CLOSED')),
           (SELECT COUNT(*) FROM complaint_analyst_view WHERE is_open)
)
SELECT ch.check_id,
       ch.check_name,
       ch.expected,
       ch.actual,
       CASE WHEN ch.actual = ch.expected THEN 'PASS' ELSE 'FAIL' END AS result
FROM   checks AS ch
ORDER  BY ch.check_id;