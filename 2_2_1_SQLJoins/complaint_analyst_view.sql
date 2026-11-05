-- complaint_analyst_view.sql
-- Week 2 | Exercise 2.2.1 - Question 4
-- Creates complaint_analyst_view: one row per complaint.
-- Used by 2.2.2 (metrics) and 2.3.1 (advanced queries).
--   psql -d complaints -f complaint_analyst_view.sql
--
-- Personal data is left out on purpose: no customer names, email, phone,
-- account number or balance.

DROP VIEW IF EXISTS complaint_analyst_view;

CREATE VIEW complaint_analyst_view AS
SELECT c.complaint_id,
       c.created_at,
       c.channel,
       c.category,
       c.priority,
       c.status,
       CASE WHEN c.status IN ('RESOLVED', 'CLOSED') THEN false
            ELSE true
       END AS is_open,
       c.customer_narrative,
       c.customer_id,
       cu.segment AS customer_segment,
       c.account_id,
       a.account_type,
       CASE WHEN c.account_id IS NULL THEN false
            ELSE true
       END AS has_account,
       c.assigned_employee_id
FROM complaint c
JOIN customer cu ON c.customer_id = cu.customer_id
LEFT JOIN account a ON c.account_id = a.account_id;


-- CHECKS

-- C01. One row per complaint (expected 30 and 30)
SELECT COUNT(*), COUNT(DISTINCT complaint_id) FROM complaint_analyst_view;

-- C02. Complaints with no account are kept (expected 3)
SELECT COUNT(*) FROM complaint_analyst_view WHERE account_id IS NULL;

-- C03. Open complaints (expected 29)
SELECT COUNT(*) FROM complaint_analyst_view WHERE is_open = true;
