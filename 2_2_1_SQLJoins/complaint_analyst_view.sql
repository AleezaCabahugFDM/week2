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
SELECT c.complaint_id,                          -- identifies the complaint
       c.created_at,                            -- age and monthly volume (2.2.2, 2.3.1)
       c.category,                              -- volume by category
       c.priority,                              -- urgency / backlog by priority
       c.status,                                -- workflow stage
       c.status NOT IN ('RESOLVED', 'CLOSED') AS is_open,   -- true = backlog, false = closed
       c.customer_narrative,                    -- complaint text analysts need (may contain personal details)
       c.customer_id,                           -- ID only, no name: counts customers, repeat complainants
       cu.segment AS customer_segment,          -- service level
       c.account_id,                            -- which account, NULL if none
       a.account_type,                          -- product the complaint is about
       c.account_id IS NOT NULL AS has_account  -- true/false: easy filter for no-account complaints
FROM complaint c
JOIN customer cu ON c.customer_id = cu.customer_id
LEFT JOIN account a ON c.account_id = a.account_id;


-- CHECKS: one row. Expected: 30, 30, 3, 29
SELECT COUNT(*) AS view_rows,
       COUNT(DISTINCT complaint_id) AS distinct_complaints,
       SUM(CASE WHEN account_id IS NULL THEN 1 ELSE 0 END) AS no_account,
       SUM(CASE WHEN is_open THEN 1 ELSE 0 END) AS open_complaints
FROM complaint_analyst_view;
