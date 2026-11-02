SELECT 'complaint' AS table_name, count(*) FROM complaint
UNION ALL SELECT 'complaint_status_history', count(*) FROM complaint_status_history
UNION ALL SELECT 'customer', count(*) FROM customer
UNION ALL SELECT 'account', count(*) FROM account
UNION ALL SELECT 'audit_log', count(*) FROM audit_log;