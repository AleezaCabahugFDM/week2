-- =====================================================================
-- seed_validation_queries.sql
-- Banking Complaint Resolution Assistant — seed data validation
--
-- Run AFTER database_schema.sql and seeddatacrs.sql.
-- Returns ONE result table (so it shows fully in the Supabase SQL Editor):
--   section | check_no | check_name | expected | actual | result | detail
--
-- result values:
--   PASS  - check met its expected value
--   FAIL  - integrity problem (must be fixed before handover)
--   WARN  - data-quality finding in the supplied seed data; schema is fine,
--           recorded as a known limitation
--
-- Negative tests try bad inserts inside a sub-transaction that is always
-- rolled back, so this script never changes your data.
-- =====================================================================

CREATE OR REPLACE FUNCTION pg_temp.try_sql(stmt text)
RETURNS text
LANGUAGE plpgsql
AS $$
BEGIN
    BEGIN
        EXECUTE stmt;
        -- Force a rollback of whatever the statement did
        RAISE EXCEPTION '__ACCEPTED__';
    EXCEPTION WHEN OTHERS THEN
        IF SQLERRM = '__ACCEPTED__' THEN
            RETURN 'ACCEPTED';
        END IF;
        RETURN 'REJECTED: ' || SQLERRM;
    END;
END;
$$;

WITH
-- ---------------------------------------------------------------------
-- 1. ROW COUNTS (expected values from seeddatacrs.sql)
-- ---------------------------------------------------------------------
row_counts AS (
    SELECT '1. Row counts' AS section, n AS check_no, 'Rows in ' || t AS check_name,
           exp::text AS expected, act::text AS actual,
           CASE WHEN act = exp THEN 'PASS' ELSE 'FAIL' END AS result,
           NULL::text AS detail
    FROM (VALUES
        (1.01, 'employee',                 10, (SELECT count(*) FROM employee)),
        (1.02, 'customer',                 10, (SELECT count(*) FROM customer)),
        (1.03, 'account',                  10, (SELECT count(*) FROM account)),
        (1.04, 'transactions',             10, (SELECT count(*) FROM transactions)),
        (1.05, 'fee',                      10, (SELECT count(*) FROM fee)),
        (1.06, 'service_request',          10, (SELECT count(*) FROM service_request)),
        (1.07, 'complaint',                30, (SELECT count(*) FROM complaint)),
        (1.08, 'complaint_status_history', 30, (SELECT count(*) FROM complaint_status_history)),
        (1.09, 'investigation',            10, (SELECT count(*) FROM investigation)),
        (1.10, 'recommendation',           10, (SELECT count(*) FROM recommendation)),
        (1.11, 'review_request',           10, (SELECT count(*) FROM review_request)),
        (1.12, 'review_decision',          10, (SELECT count(*) FROM review_decision)),
        (1.13, 'customer_response',        10, (SELECT count(*) FROM customer_response)),
        (1.14, 'policy_document',          10, (SELECT count(*) FROM policy_document)),
        (1.15, 'policy_section',           10, (SELECT count(*) FROM policy_section)),
        (1.16, 'audit_log',                10, (SELECT count(*) FROM audit_log))
    ) AS v(n, t, exp, act)
),

-- ---------------------------------------------------------------------
-- 2. ORPHAN CHECKS (child rows whose parent does not exist) — expect 0
--    Foreign keys already prevent these; the queries prove it on the data.
-- ---------------------------------------------------------------------
orphans AS (
    SELECT '2. Orphan checks' AS section, n AS check_no, name AS check_name,
           '0' AS expected, cnt::text AS actual,
           CASE WHEN cnt = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
           ids AS detail
    FROM (
        SELECT 2.01 n, 'account -> customer' name, count(*) cnt, string_agg(a.account_id, ', ') ids
          FROM account a LEFT JOIN customer c USING (customer_id) WHERE c.customer_id IS NULL
        UNION ALL
        SELECT 2.02, 'complaint -> customer', count(*), string_agg(x.complaint_id, ', ')
          FROM complaint x LEFT JOIN customer c USING (customer_id) WHERE c.customer_id IS NULL
        UNION ALL
        SELECT 2.03, 'complaint -> account (when account given)', count(*), string_agg(x.complaint_id, ', ')
          FROM complaint x LEFT JOIN account a USING (account_id)
          WHERE x.account_id IS NOT NULL AND a.account_id IS NULL
        UNION ALL
        SELECT 2.04, 'complaint -> assigned employee', count(*), string_agg(x.complaint_id, ', ')
          FROM complaint x LEFT JOIN employee e ON e.employee_id = x.assigned_employee_id
          WHERE x.assigned_employee_id IS NOT NULL AND e.employee_id IS NULL
        UNION ALL
        SELECT 2.05, 'complaint_status_history -> complaint', count(*), string_agg(h.complaint_id, ', ')
          FROM complaint_status_history h LEFT JOIN complaint x USING (complaint_id) WHERE x.complaint_id IS NULL
        UNION ALL
        SELECT 2.06, 'complaint_status_history -> changed_by employee', count(*), string_agg(h.complaint_id, ', ')
          FROM complaint_status_history h LEFT JOIN employee e ON e.employee_id = h.changed_by WHERE e.employee_id IS NULL
        UNION ALL
        SELECT 2.07, 'transactions -> account', count(*), string_agg(t.transaction_id, ', ')
          FROM transactions t LEFT JOIN account a USING (account_id) WHERE a.account_id IS NULL
        UNION ALL
        SELECT 2.08, 'fee -> account', count(*), string_agg(f.fee_id, ', ')
          FROM fee f LEFT JOIN account a USING (account_id) WHERE a.account_id IS NULL
        UNION ALL
        SELECT 2.09, 'fee -> transaction (when transaction given)', count(*), string_agg(f.fee_id, ', ')
          FROM fee f LEFT JOIN transactions t USING (transaction_id)
          WHERE f.transaction_id IS NOT NULL AND t.transaction_id IS NULL
        UNION ALL
        SELECT 2.10, 'service_request -> customer', count(*), string_agg(s.request_id, ', ')
          FROM service_request s LEFT JOIN customer c USING (customer_id) WHERE c.customer_id IS NULL
        UNION ALL
        SELECT 2.11, 'service_request -> account (when account given)', count(*), string_agg(s.request_id, ', ')
          FROM service_request s LEFT JOIN account a USING (account_id)
          WHERE s.account_id IS NOT NULL AND a.account_id IS NULL
        UNION ALL
        SELECT 2.12, 'investigation -> complaint', count(*), string_agg(i.investigation_id, ', ')
          FROM investigation i LEFT JOIN complaint x USING (complaint_id) WHERE x.complaint_id IS NULL
        UNION ALL
        SELECT 2.13, 'investigation -> analyst employee', count(*), string_agg(i.investigation_id, ', ')
          FROM investigation i LEFT JOIN employee e ON e.employee_id = i.analyst_id WHERE e.employee_id IS NULL
        UNION ALL
        SELECT 2.14, 'recommendation -> investigation', count(*), string_agg(r.recommendation_id, ', ')
          FROM recommendation r LEFT JOIN investigation i USING (investigation_id) WHERE i.investigation_id IS NULL
        UNION ALL
        SELECT 2.15, 'review_request -> complaint / recommendation / reviewer', count(*), string_agg(rr.review_request_id, ', ')
          FROM review_request rr
          LEFT JOIN complaint x      ON x.complaint_id = rr.complaint_id
          LEFT JOIN recommendation r ON r.recommendation_id = rr.recommendation_id
          LEFT JOIN employee e       ON e.employee_id = rr.reviewer_id
          WHERE x.complaint_id IS NULL OR r.recommendation_id IS NULL OR e.employee_id IS NULL
        UNION ALL
        SELECT 2.16, 'review_decision -> review_request', count(*), string_agg(d.decision_id, ', ')
          FROM review_decision d LEFT JOIN review_request rr USING (review_request_id) WHERE rr.review_request_id IS NULL
        UNION ALL
        SELECT 2.17, 'customer_response -> complaint / sent_by', count(*), string_agg(cr.response_id, ', ')
          FROM customer_response cr
          LEFT JOIN complaint x ON x.complaint_id = cr.complaint_id
          LEFT JOIN employee e  ON e.employee_id = cr.sent_by
          WHERE x.complaint_id IS NULL OR e.employee_id IS NULL
        UNION ALL
        SELECT 2.18, 'policy_section -> policy_document', count(*), string_agg(ps.section_id, ', ')
          FROM policy_section ps LEFT JOIN policy_document p USING (policy_id) WHERE p.policy_id IS NULL
        UNION ALL
        SELECT 2.19, 'audit_log -> performed_by employee', count(*), string_agg(al.audit_id::text, ', ')
          FROM audit_log al LEFT JOIN employee e ON e.employee_id = al.performed_by WHERE e.employee_id IS NULL
        UNION ALL
        -- Polymorphic reference: no FK possible, so this check is the only protection
        SELECT 2.20, 'audit_log entity_id resolves to a real row (polymorphic)', count(*),
               string_agg(al.entity_name || ':' || al.entity_id, ', ')
          FROM audit_log al
          WHERE NOT CASE al.entity_name
                WHEN 'COMPLAINT'         THEN EXISTS (SELECT 1 FROM complaint         WHERE complaint_id      = al.entity_id)
                WHEN 'SERVICE_REQUEST'   THEN EXISTS (SELECT 1 FROM service_request   WHERE request_id        = al.entity_id)
                WHEN 'INVESTIGATION'     THEN EXISTS (SELECT 1 FROM investigation     WHERE investigation_id  = al.entity_id)
                WHEN 'RECOMMENDATION'    THEN EXISTS (SELECT 1 FROM recommendation    WHERE recommendation_id = al.entity_id)
                WHEN 'REVIEW_REQUEST'    THEN EXISTS (SELECT 1 FROM review_request    WHERE review_request_id = al.entity_id)
                WHEN 'REVIEW_DECISION'   THEN EXISTS (SELECT 1 FROM review_decision   WHERE decision_id       = al.entity_id)
                WHEN 'CUSTOMER_RESPONSE' THEN EXISTS (SELECT 1 FROM customer_response WHERE response_id       = al.entity_id)
                ELSE FALSE END
    ) q
),

-- ---------------------------------------------------------------------
-- 3. INVALID STATUS / CODE VALUES — expect 0
-- ---------------------------------------------------------------------
invalid_status AS (
    SELECT '3. Invalid status checks' AS section, n AS check_no, name AS check_name,
           '0' AS expected, cnt::text AS actual,
           CASE WHEN cnt = 0 THEN 'PASS' ELSE 'FAIL' END AS result,
           ids AS detail
    FROM (
        SELECT 3.01 n, 'complaint.status outside lifecycle list' name, count(*) cnt, string_agg(complaint_id, ', ') ids
          FROM complaint WHERE status NOT IN ('OPEN','IN_PROGRESS','UNDER_REVIEW','PENDING_APPROVAL','CHANGES_REQUESTED','ESCALATED','RESOLVED','CLOSED')
        UNION ALL
        SELECT 3.02, 'complaint.priority outside Low/Medium/High/Critical', count(*), string_agg(complaint_id, ', ')
          FROM complaint WHERE priority NOT IN ('Low','Medium','High','Critical')
        UNION ALL
        SELECT 3.03, 'complaint.channel outside Phone/Email/Branch/Web', count(*), string_agg(complaint_id, ', ')
          FROM complaint WHERE channel NOT IN ('Phone','Email','Branch','Web')
        UNION ALL
        SELECT 3.04, 'complaint_status_history old/new status invalid', count(*), string_agg(complaint_id, ', ')
          FROM complaint_status_history
          WHERE new_status NOT IN ('OPEN','IN_PROGRESS','UNDER_REVIEW','PENDING_APPROVAL','CHANGES_REQUESTED','ESCALATED','RESOLVED','CLOSED')
             OR (old_status IS NOT NULL AND old_status NOT IN ('OPEN','IN_PROGRESS','UNDER_REVIEW','PENDING_APPROVAL','CHANGES_REQUESTED','ESCALATED','RESOLVED','CLOSED'))
        UNION ALL
        SELECT 3.05, 'account.status invalid', count(*), string_agg(account_id, ', ')
          FROM account WHERE status NOT IN ('ACTIVE','INACTIVE','CLOSED','RESTRICTED')
        UNION ALL
        SELECT 3.06, 'service_request.status invalid', count(*), string_agg(request_id, ', ')
          FROM service_request WHERE status NOT IN ('OPEN','IN_PROGRESS','CLOSED')
        UNION ALL
        SELECT 3.07, 'review_request.status invalid', count(*), string_agg(review_request_id, ', ')
          FROM review_request WHERE status NOT IN ('PENDING','UNDER_REVIEW','APPROVED','REJECTED','CHANGES_REQUESTED','ESCALATED')
        UNION ALL
        SELECT 3.08, 'review_decision.decision invalid', count(*), string_agg(decision_id, ', ')
          FROM review_decision WHERE decision NOT IN ('APPROVED','REJECTED','REQUEST_CHANGES','ESCALATED')
        UNION ALL
        SELECT 3.09, 'transactions.transaction_type not DEBIT/CREDIT', count(*), string_agg(transaction_id, ', ')
          FROM transactions WHERE transaction_type NOT IN ('DEBIT','CREDIT')
        UNION ALL
        SELECT 3.10, 'policy_document.status invalid', count(*), string_agg(policy_id, ', ')
          FROM policy_document WHERE status NOT IN ('ACTIVE','SUPERSEDED','RETIRED','DRAFT')
        UNION ALL
        SELECT 3.11, 'recommendation.confidence_score outside 0-100', count(*), string_agg(recommendation_id, ', ')
          FROM recommendation WHERE confidence_score < 0 OR confidence_score > 100
    ) q
),

-- ---------------------------------------------------------------------
-- 4. ACCOUNT / CUSTOMER AND CROSS-TABLE CONSISTENCY — expect 0
-- ---------------------------------------------------------------------
consistency AS (
    SELECT '4. Consistency checks' AS section, n AS check_no, name AS check_name,
           exp AS expected, cnt::text AS actual,
           CASE WHEN cnt::text = exp THEN 'PASS' ELSE 'FAIL' END AS result,
           ids AS detail
    FROM (
        SELECT 4.01 n, 'complaint account belongs to the complaining customer' name, '0' exp,
               count(*) cnt, string_agg(x.complaint_id, ', ') ids
          FROM complaint x JOIN account a ON a.account_id = x.account_id
          WHERE a.customer_id <> x.customer_id
        UNION ALL
        SELECT 4.02, 'service_request account belongs to the requesting customer', '0',
               count(*), string_agg(s.request_id, ', ')
          FROM service_request s JOIN account a ON a.account_id = s.account_id
          WHERE a.customer_id <> s.customer_id
        UNION ALL
        SELECT 4.03, 'fee transaction is on the same account as the fee', '0',
               count(*), string_agg(f.fee_id, ', ')
          FROM fee f JOIN transactions t ON t.transaction_id = f.transaction_id
          WHERE t.account_id <> f.account_id
        UNION ALL
        SELECT 4.04, 'transaction balance_after = balance_before -/+ amount', '0',
               count(*), string_agg(transaction_id, ', ')
          FROM transactions
          WHERE balance_after <> CASE transaction_type WHEN 'DEBIT' THEN balance_before - amount
                                                       ELSE balance_before + amount END
        UNION ALL
        SELECT 4.05, 'account.balance = balance_after of its latest transaction', '0',
               count(*), string_agg(a.account_id, ', ')
          FROM account a
          JOIN LATERAL (SELECT balance_after FROM transactions t
                        WHERE t.account_id = a.account_id
                        ORDER BY transaction_date DESC LIMIT 1) lt ON TRUE
          WHERE lt.balance_after <> a.balance
        UNION ALL
        SELECT 4.06, 'complaint.status = new_status of its latest history row', '0',
               count(*), string_agg(x.complaint_id, ', ')
          FROM complaint x
          JOIN LATERAL (SELECT new_status FROM complaint_status_history h
                        WHERE h.complaint_id = x.complaint_id
                        ORDER BY status_timestamp DESC, status_history_id DESC LIMIT 1) lh ON TRUE
          WHERE lh.new_status <> x.status
        UNION ALL
        SELECT 4.07, 'every complaint has at least one status history row', '0',
               count(*), string_agg(x.complaint_id, ', ')
          FROM complaint x
          WHERE NOT EXISTS (SELECT 1 FROM complaint_status_history h WHERE h.complaint_id = x.complaint_id)
        UNION ALL
        SELECT 4.08, 'review_request complaint = complaint behind its recommendation', '0',
               count(*), string_agg(rr.review_request_id, ', ')
          FROM review_request rr
          JOIN recommendation r ON r.recommendation_id = rr.recommendation_id
          JOIN investigation i  ON i.investigation_id  = r.investigation_id
          WHERE i.complaint_id <> rr.complaint_id
        UNION ALL
        SELECT 4.09, 'CLOSED service requests have closed_date; open ones do not', '0',
               count(*), string_agg(request_id, ', ')
          FROM service_request
          WHERE (status = 'CLOSED') <> (closed_date IS NOT NULL)
        UNION ALL
        SELECT 4.10, 'investigation end_date not before start_date', '0',
               count(*), string_agg(investigation_id, ', ')
          FROM investigation WHERE end_date < start_date
        UNION ALL
        SELECT 4.11, 'investigation starts on/after complaint was raised', '0',
               count(*), string_agg(i.investigation_id, ', ')
          FROM investigation i JOIN complaint x USING (complaint_id)
          WHERE i.start_date < x.created_at::date
        UNION ALL
        SELECT 4.12, 'customer response sent on/after complaint was raised', '0',
               count(*), string_agg(cr.response_id, ', ')
          FROM customer_response cr JOIN complaint x USING (complaint_id)
          WHERE cr.sent_date < x.created_at::date
        UNION ALL
        SELECT 4.13, 'review_request reviewer has role Reviewer', '0',
               count(*), string_agg(rr.review_request_id, ', ')
          FROM review_request rr JOIN employee e ON e.employee_id = rr.reviewer_id
          WHERE e.role <> 'Reviewer'
        UNION ALL
        SELECT 4.14, 'investigation analyst has role Analyst', '0',
               count(*), string_agg(i.investigation_id, ', ')
          FROM investigation i JOIN employee e ON e.employee_id = i.analyst_id
          WHERE e.role <> 'Analyst'
        UNION ALL
        SELECT 4.15, 'complaint assigned to an Analyst', '0',
               count(*), string_agg(x.complaint_id, ', ')
          FROM complaint x JOIN employee e ON e.employee_id = x.assigned_employee_id
          WHERE e.role <> 'Analyst'
        UNION ALL
        -- Boundary: unmatched account must be stored, not rejected (spec AT-02)
        SELECT 4.16, 'complaints stored with NULL account (unmatched, spec AT-02)', '3',
               count(*), string_agg(complaint_id, ', ')
          FROM complaint WHERE account_id IS NULL
    ) q
),

-- ---------------------------------------------------------------------
-- 5. DATA-QUALITY FINDINGS IN THE SUPPLIED SEED DATA (WARN, not FAIL)
--    The schema accepts these rows; they are recorded as known limitations.
-- ---------------------------------------------------------------------
dq_findings AS (
    SELECT '5. Seed data-quality findings' AS section, n AS check_no, name AS check_name,
           '0' AS expected, cnt::text AS actual,
           CASE WHEN cnt = 0 THEN 'PASS' ELSE 'WARN' END AS result,
           ids AS detail
    FROM (
        SELECT 5.01 n, 'review_request.status disagrees with its review_decision' name,
               count(*) cnt,
               string_agg(rr.review_request_id || ' (' || rr.status || ' vs ' || d.decision || ')', ', '
                          ORDER BY rr.review_request_id) ids
          FROM review_request rr JOIN review_decision d USING (review_request_id)
          WHERE rr.status <> d.decision
        UNION ALL
        SELECT 5.02, 'first history row has non-NULL old_status (earlier transition missing)',
               count(*),
               string_agg(h.complaint_id || ' (' || h.old_status || '->' || h.new_status || ')', ', '
                          ORDER BY h.complaint_id)
          FROM complaint_status_history h
          WHERE h.old_status IS NOT NULL
            AND NOT EXISTS (SELECT 1 FROM complaint_status_history p
                            WHERE p.complaint_id = h.complaint_id
                              AND p.status_history_id < h.status_history_id)
        UNION ALL
        SELECT 5.03, 'customer told a fee was reversed/refunded but no fee on the account is reversed',
               count(*), string_agg(cr.response_id || ' (' || x.complaint_id || ')', ', ' ORDER BY cr.response_id)
          FROM customer_response cr
          JOIN complaint x ON x.complaint_id = cr.complaint_id
          WHERE (cr.response_text ILIKE '%reversed%' OR cr.response_text ILIKE '%refund%')
            AND NOT EXISTS (SELECT 1 FROM fee f WHERE f.account_id = x.account_id AND f.reversed)
        UNION ALL
        SELECT 5.04, 'status history timestamps are load time, not real event time',
               count(*), 'status_timestamp defaulted at load; seed supplies no event times'
          FROM complaint_status_history
          WHERE status_timestamp > (SELECT max(created_at) FROM complaint) + interval '1 year'
        UNION ALL
        SELECT 5.05, 'overdraft fee charged while the balance stayed positive',
               count(*), string_agg(f.fee_id || ' (balance_after ' || t.balance_after || ')', ', ')
          FROM fee f JOIN transactions t ON t.transaction_id = f.transaction_id
          WHERE f.fee_type = 'Overdraft' AND t.balance_after >= 0
        UNION ALL
        SELECT 5.06, 'complaint still OPEN although its investigation has ended',
               count(*), string_agg(x.complaint_id || ' (' || i.investigation_id || ' ended ' || i.end_date || ')', ', ')
          FROM complaint x JOIN investigation i USING (complaint_id)
          WHERE x.status = 'OPEN' AND i.end_date IS NOT NULL
        UNION ALL
        SELECT 5.07, 'complaints with no investigation (intake data only)',
               count(*), min(x.complaint_id) || ' - ' || max(x.complaint_id)
          FROM complaint x
          WHERE NOT EXISTS (SELECT 1 FROM investigation i WHERE i.complaint_id = x.complaint_id)
    ) q
),

-- ---------------------------------------------------------------------
-- 6. NEGATIVE AND BOUNDARY TESTS — each insert is rolled back
-- ---------------------------------------------------------------------
neg_tests AS (
    SELECT '6. Negative / boundary tests' AS section, n AS check_no, name AS check_name,
           exp AS expected, split_part(outcome, ':', 1) AS actual,
           CASE WHEN split_part(outcome, ':', 1) = exp THEN 'PASS' ELSE 'FAIL' END AS result,
           outcome AS detail
    FROM (
        SELECT n, name, exp, pg_temp.try_sql(stmt) AS outcome
        FROM (VALUES
            (6.01, 'complaint for another customer''s account', 'REJECTED',
             $q$INSERT INTO complaint VALUES ('TST01','CUS001','ACC002','Web','Fee Dispute','test','Low','OPEN',now(),'EMP001')$q$),
            (6.02, 'complaint for unknown customer', 'REJECTED',
             $q$INSERT INTO complaint VALUES ('TST02','CUS999',NULL,'Web','Fee Dispute','test','Low','OPEN',now(),'EMP001')$q$),
            (6.03, 'complaint with invalid status DONE', 'REJECTED',
             $q$INSERT INTO complaint VALUES ('TST03','CUS001','ACC001','Web','Fee Dispute','test','Low','DONE',now(),'EMP001')$q$),
            (6.04, 'complaint with invalid priority Urgent', 'REJECTED',
             $q$INSERT INTO complaint VALUES ('TST04','CUS001','ACC001','Web','Fee Dispute','test','Urgent','OPEN',now(),'EMP001')$q$),
            (6.05, 'complaint with missing narrative', 'REJECTED',
             $q$INSERT INTO complaint VALUES ('TST05','CUS001','ACC001','Web','Fee Dispute',NULL,'Low','OPEN',now(),'EMP001')$q$),
            (6.06, 'duplicate complaint_id CMP001', 'REJECTED',
             $q$INSERT INTO complaint VALUES ('CMP001','CUS001','ACC001','Web','Fee Dispute','test','Low','OPEN',now(),'EMP001')$q$),
            (6.07, 'transaction whose balances do not add up', 'REJECTED',
             $q$INSERT INTO transactions VALUES ('TST07','ACC001','DEBIT',10,now(),100,95,'test')$q$),
            (6.08, 'fee linked to another account''s transaction', 'REJECTED',
             $q$INSERT INTO fee VALUES ('TST08','ACC002','TXN001','Overdraft',1,now(),FALSE)$q$),
            (6.09, 'CLOSED service request without closed_date', 'REJECTED',
             $q$INSERT INTO service_request VALUES ('TST09','CUS001','ACC001','Test','CLOSED','2025-01-01',NULL)$q$),
            (6.10, 'investigation ending before it starts', 'REJECTED',
             $q$INSERT INTO investigation VALUES ('TST10','CMP001','EMP001','2025-01-10','2025-01-05','test')$q$),
            (6.11, 'recommendation confidence 150', 'REJECTED',
             $q$INSERT INTO recommendation (recommendation_id,investigation_id,recommendation_text,confidence_score) VALUES ('TST11','INV001','test',150)$q$),
            (6.12, 'review decision without a reason (spec AT-09)', 'REJECTED',
             $q$INSERT INTO review_decision (decision_id,review_request_id,decision,decision_reason) VALUES ('TST12','RR001','APPROVED',NULL)$q$),
            (6.13, 'status history with invalid new_status', 'REJECTED',
             $q$INSERT INTO complaint_status_history (complaint_id,old_status,new_status,changed_by) VALUES ('CMP001','OPEN','FINISHED','EMP001')$q$),
            (6.17, 'status history OPEN -> OPEN (no change)', 'REJECTED',
             $q$INSERT INTO complaint_status_history (complaint_id,old_status,new_status,changed_by) VALUES ('CMP001','OPEN','OPEN','EMP001')$q$),
            (6.18, 'service request for another customer''s account', 'REJECTED',
             $q$INSERT INTO service_request VALUES ('TST18','CUS001','ACC003','Test','OPEN','2025-01-01',NULL)$q$),
            (6.19, 'audit log with unknown action_type HACK', 'REJECTED',
             $q$INSERT INTO audit_log (entity_name,entity_id,action_type,performed_by) VALUES ('COMPLAINT','CMP001','HACK','EMP001')$q$),
            (6.20, 'delete a customer who still has accounts/complaints', 'REJECTED',
             $q$DELETE FROM customer WHERE customer_id = 'CUS001'$q$),
            (6.14, 'BOUNDARY: complaint with NULL account is accepted', 'ACCEPTED',
             $q$INSERT INTO complaint VALUES ('TST14','CUS001',NULL,'Web','Service Delay','test','Low','OPEN',now(),'EMP001')$q$),
            (6.15, 'BOUNDARY: confidence exactly 100 is accepted', 'ACCEPTED',
             $q$INSERT INTO recommendation (recommendation_id,investigation_id,recommendation_text,confidence_score) VALUES ('TST15','INV001','test',100)$q$),
            (6.16, 'BOUNDARY: fee with no transaction is accepted', 'ACCEPTED',
             $q$INSERT INTO fee VALUES ('TST16','ACC001',NULL,'Maintenance',10,now(),FALSE)$q$)
        ) AS v(n, name, exp, stmt)
    ) q
)

SELECT section, check_no, check_name, expected, actual, result, detail
FROM (
    SELECT * FROM row_counts
    UNION ALL SELECT * FROM orphans
    UNION ALL SELECT * FROM invalid_status
    UNION ALL SELECT * FROM consistency
    UNION ALL SELECT * FROM dq_findings
    UNION ALL SELECT * FROM neg_tests
) all_checks
ORDER BY check_no;