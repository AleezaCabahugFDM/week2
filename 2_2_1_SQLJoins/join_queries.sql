-- join_queries.sql
-- Week 2 | Exercise 2.2.1 - Join Customer, Account and Complaint Context
-- Run in psql or the Supabase SQL Editor:
--   psql -d complaints -f join_queries.sql
--
-- complaint -> customer : INNER JOIN (every complaint has a customer)
-- complaint -> account  : LEFT JOIN  (3 complaints have no account)


-- J1. Show each complaint with customer name. (30 rows)
SELECT c.complaint_id,
       cu.first_name,
       cu.last_name,
       c.category,
       c.priority,
       c.status
FROM complaint c
JOIN customer cu ON c.customer_id = cu.customer_id
ORDER BY c.complaint_id;


-- J2. Add the account type without dropping complaints that have no account. (30 rows)
-- LEFT JOIN keeps every complaint. No account = NULL account_type.
SELECT c.complaint_id,
       cu.first_name,
       cu.last_name,
       c.account_id,
       a.account_type,
       c.category,
       c.status
FROM complaint c
JOIN customer cu ON c.customer_id = cu.customer_id
LEFT JOIN account a ON c.account_id = a.account_id
ORDER BY c.complaint_id;


-- J3. Check the complaint count before and after the joins.
-- If the numbers change, a join lost or repeated complaints.
-- Expected: 30, 30, 30 and then 27 for the wrong INNER JOIN.
SELECT '1. complaint only' AS join_step, COUNT(*) AS row_count
FROM complaint

UNION ALL
SELECT '2. + JOIN customer', COUNT(*)
FROM complaint c
JOIN customer cu ON c.customer_id = cu.customer_id

UNION ALL
SELECT '3. + LEFT JOIN account (correct)', COUNT(*)
FROM complaint c
JOIN customer cu ON c.customer_id = cu.customer_id
LEFT JOIN account a ON c.account_id = a.account_id

UNION ALL
SELECT '4. + JOIN account (wrong: loses 3)', COUNT(*)
FROM complaint c
JOIN customer cu ON c.customer_id = cu.customer_id
JOIN account a ON c.account_id = a.account_id

ORDER BY join_step;
