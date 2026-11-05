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

-- Before any join (expected 30)
SELECT COUNT(*) FROM complaint;

-- After joining customer (expected 30)
SELECT COUNT(*)
FROM complaint c
JOIN customer cu ON c.customer_id = cu.customer_id;

-- After joining account with LEFT JOIN (expected 30 rows and 30 distinct complaints)
SELECT COUNT(*), COUNT(DISTINCT c.complaint_id)
FROM complaint c
JOIN customer cu ON c.customer_id = cu.customer_id
LEFT JOIN account a ON c.account_id = a.account_id;

-- WRONG: joining account with INNER JOIN loses the 3 no-account complaints (expected 27)
SELECT COUNT(*)
FROM complaint c
JOIN customer cu ON c.customer_id = cu.customer_id
JOIN account a ON c.account_id = a.account_id;
