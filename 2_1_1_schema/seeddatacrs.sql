-- ==========================================
-- EMPLOYEE
-- ==========================================
INSERT INTO employee VALUES
('EMP001','John','Smith','john.smith@bank.com','Analyst'),
('EMP002','Sarah','Lee','sarah.lee@bank.com','Analyst'),
('EMP003','Michael','Brown','michael.brown@bank.com','Reviewer'),
('EMP004','Emma','Wilson','emma.wilson@bank.com','Reviewer'),
('EMP005','David','Clark','david.clark@bank.com','Manager'),
('EMP006','Sophia','Martin','sophia.martin@bank.com','Analyst'),
('EMP007','James','Taylor','james.taylor@bank.com','Analyst'),
('EMP008','Olivia','White','olivia.white@bank.com','Reviewer'),
('EMP009','Daniel','Hall','daniel.hall@bank.com','Supervisor'),
('EMP010','Ava','King','ava.king@bank.com','Manager');

-- ==========================================
-- CUSTOMER
-- ==========================================
INSERT INTO customer
(customer_id,first_name,last_name,email,phone_number,segment)
VALUES
('CUS001','William','Johnson','william@email.com','4165551001','Retail'),
('CUS002','Emily','Moore','emily@email.com','4165551002','Retail'),
('CUS003','Benjamin','Miller','ben@email.com','4165551003','Premier'),
('CUS004','Charlotte','Davis','charlotte@email.com','4165551004','Retail'),
('CUS005','Lucas','Garcia','lucas@email.com','4165551005','Business'),
('CUS006','Amelia','Martinez','amelia@email.com','4165551006','Retail'),
('CUS007','Henry','Rodriguez','henry@email.com','4165551007','Premier'),
('CUS008','Mia','Anderson','mia@email.com','4165551008','Retail'),
('CUS009','Elijah','Thomas','elijah@email.com','4165551009','Business'),
('CUS010','Harper','Jackson','harper@email.com','4165551010','Retail');

-- ==========================================
-- ACCOUNT
-- ==========================================
INSERT INTO account VALUES
('ACC001','CUS001','100000001','Chequing','ACTIVE',2500.50,'2023-01-10'),
('ACC002','CUS002','100000002','Savings','ACTIVE',5000.00,'2023-02-15'),
('ACC003','CUS003','100000003','Chequing','ACTIVE',15000.00,'2022-11-05'),
('ACC004','CUS004','100000004','Savings','ACTIVE',3200.75,'2023-04-20'),
('ACC005','CUS005','100000005','Business','ACTIVE',55000.00,'2022-08-11'),
('ACC006','CUS006','100000006','Chequing','ACTIVE',980.00,'2023-06-01'),
('ACC007','CUS007','100000007','Savings','ACTIVE',21000.00,'2022-12-14'),
('ACC008','CUS008','100000008','Chequing','ACTIVE',1800.10,'2023-03-09'),
('ACC009','CUS009','100000009','Business','ACTIVE',45000.50,'2021-10-21'),
('ACC010','CUS010','100000010','Savings','ACTIVE',7200.20,'2023-07-18');

-- ==========================================
-- COMPLAINT
-- ==========================================
INSERT INTO complaint VALUES
('CMP001','CUS001','ACC001','Phone','Fee Dispute','Unexpected overdraft fee','High','OPEN','2025-01-01 09:00:00','EMP001'),
('CMP002','CUS002','ACC002','Email','Service Delay','Delay in account update','Medium','IN_PROGRESS','2025-01-05 11:15:00','EMP002'),
('CMP003','CUS003','ACC003','Branch','Transaction Error','Duplicate debit transaction','High','UNDER_REVIEW','2025-01-09 14:00:00','EMP001'),
('CMP004','CUS004','ACC004','Web','Online Banking','Login issue','Low','OPEN','2025-01-12 10:00:00','EMP006'),
('CMP005','CUS005','ACC005','Phone','Fee Dispute','Incorrect service fee','Medium','CLOSED','2025-01-15 13:00:00','EMP007'),
('CMP006','CUS006','ACC006','Email','Card Issue','Card blocked unexpectedly','High','OPEN','2025-01-18 12:00:00','EMP002'),
('CMP007','CUS007','ACC007','Web','Transaction Error','ATM withdrawal issue','High','IN_PROGRESS','2025-01-20 09:30:00','EMP001'),
('CMP008','CUS008','ACC008','Phone','Customer Service','Poor support experience','Low','OPEN','2025-01-22 15:00:00','EMP006'),
('CMP009','CUS009','ACC009','Branch','Fraud Claim','Unauthorized transfer','Critical','UNDER_REVIEW','2025-01-24 16:30:00','EMP007'),
('CMP010','CUS010','ACC010','Email','Fee Dispute','Monthly fee charged incorrectly','Medium','OPEN','2025-01-25 08:45:00','EMP002');

-- ==========================================
-- COMPLAINT STATUS HISTORY
-- ==========================================
INSERT INTO complaint_status_history
(complaint_id,old_status,new_status,changed_by,comments)
VALUES
('CMP001',NULL,'OPEN','EMP001','Complaint created'),
('CMP002','OPEN','IN_PROGRESS','EMP002','Investigation started'),
('CMP003','OPEN','UNDER_REVIEW','EMP001','Assigned for review'),
('CMP004',NULL,'OPEN','EMP006','Complaint opened'),
('CMP005','IN_PROGRESS','CLOSED','EMP007','Resolved'),
('CMP006',NULL,'OPEN','EMP002','Complaint opened'),
('CMP007','OPEN','IN_PROGRESS','EMP001','Analyst assigned'),
('CMP008',NULL,'OPEN','EMP006','Complaint created'),
('CMP009','IN_PROGRESS','UNDER_REVIEW','EMP007','Fraud review initiated'),
('CMP010',NULL,'OPEN','EMP002','Complaint registered');

-- ==========================================
-- TRANSACTIONS
-- ==========================================
INSERT INTO transactions VALUES
('TXN001','ACC001','DEBIT',35.00,'2025-01-01 08:00:00',2535.50,2500.50,'ATM withdrawal'),
('TXN002','ACC002','CREDIT',1000.00,'2025-01-03 09:15:00',4000.00,5000.00,'Payroll'),
('TXN003','ACC003','DEBIT',250.00,'2025-01-04 10:00:00',15250.00,15000.00,'Bill payment'),
('TXN004','ACC004','CREDIT',500.75,'2025-01-07 12:00:00',2700.00,3200.75,'Transfer'),
('TXN005','ACC005','DEBIT',5000.00,'2025-01-10 14:30:00',60000.00,55000.00,'Vendor payment'),
('TXN006','ACC006','DEBIT',20.00,'2025-01-11 11:00:00',1000.00,980.00,'Service fee'),
('TXN007','ACC007','CREDIT',1000.00,'2025-01-12 13:45:00',20000.00,21000.00,'Deposit'),
('TXN008','ACC008','DEBIT',199.90,'2025-01-13 09:20:00',2000.00,1800.10,'Purchase'),
('TXN009','ACC009','DEBIT',4999.50,'2025-01-14 16:00:00',50000.00,45000.50,'Business transfer'),
('TXN010','ACC010','CREDIT',700.20,'2025-01-16 08:15:00',6500.00,7200.20,'Interest payment');

-- ==========================================
-- FEE
-- ==========================================
INSERT INTO fee VALUES
('FEE001','ACC001','TXN001','Overdraft',35.00,'2025-01-01 08:01:00',FALSE),
('FEE002','ACC002',NULL,'Maintenance',10.00,'2025-01-03 00:00:00',FALSE),
('FEE003','ACC003',NULL,'Wire',20.00,'2025-01-04 00:00:00',FALSE),
('FEE004','ACC004',NULL,'Maintenance',10.00,'2025-01-07 00:00:00',FALSE),
('FEE005','ACC005','TXN005','Business Service',50.00,'2025-01-10 15:00:00',FALSE),
('FEE006','ACC006','TXN006','Card Replacement',15.00,'2025-01-11 11:30:00',FALSE),
('FEE007','ACC007',NULL,'Wire',25.00,'2025-01-12 14:00:00',FALSE),
('FEE008','ACC008',NULL,'Maintenance',10.00,'2025-01-13 00:00:00',FALSE),
('FEE009','ACC009','TXN009','Business Service',75.00,'2025-01-14 16:30:00',FALSE),
('FEE010','ACC010',NULL,'Maintenance',10.00,'2025-01-16 00:00:00',FALSE);

-- ==========================================
-- SERVICE REQUEST
-- ==========================================
INSERT INTO service_request VALUES
('SR001','CUS001','ACC001','Address Change','CLOSED','2025-01-01','2025-01-02'),
('SR002','CUS002','ACC002','Card Replacement','OPEN','2025-01-03',NULL),
('SR003','CUS003','ACC003','Limit Increase','OPEN','2025-01-04',NULL),
('SR004','CUS004','ACC004','Statement Request','CLOSED','2025-01-05','2025-01-06'),
('SR005','CUS005','ACC005','Business Support','OPEN','2025-01-06',NULL),
('SR006','CUS006','ACC006','PIN Reset','CLOSED','2025-01-07','2025-01-08'),
('SR007','CUS007','ACC007','Account Update','OPEN','2025-01-08',NULL),
('SR008','CUS008','ACC008','Cheque Book','OPEN','2025-01-09',NULL),
('SR009','CUS009','ACC009','Wire Transfer Setup','OPEN','2025-01-10',NULL),
('SR010','CUS010','ACC010','Interest Inquiry','CLOSED','2025-01-11','2025-01-12');

-- ==========================================
-- POLICY DOCUMENT
-- ==========================================
INSERT INTO policy_document VALUES
('POL001','Complaint Resolution Policy','1.0','2024-01-01','ACTIVE'),
('POL002','Fee Reversal Policy','1.1','2024-02-01','ACTIVE'),
('POL003','Fraud Investigation Policy','2.0','2024-03-01','ACTIVE'),
('POL004','Customer Service Policy','1.0','2024-04-01','ACTIVE'),
('POL005','Data Privacy Policy','3.0','2024-05-01','ACTIVE'),
('POL006','Account Management Policy','1.2','2024-06-01','ACTIVE'),
('POL007','AML Compliance Policy','2.5','2024-07-01','ACTIVE'),
('POL008','Service Request Policy','1.0','2024-08-01','ACTIVE'),
('POL009','Refund Policy','1.3','2024-09-01','ACTIVE'),
('POL010','Audit Policy','1.0','2024-10-01','ACTIVE');

-- ==========================================
-- POLICY SECTION
-- ==========================================
INSERT INTO policy_section VALUES
('SEC001','POL001','Complaint Intake','All complaints must be recorded.'),
('SEC002','POL002','Fee Assessment','Fees reviewed within 5 days.'),
('SEC003','POL003','Fraud Escalation','Escalate suspected fraud.'),
('SEC004','POL004','Response SLA','Respond within 2 business days.'),
('SEC005','POL005','Data Handling','Protect customer data.'),
('SEC006','POL006','Account Updates','Verify identity before changes.'),
('SEC007','POL007','AML Monitoring','Monitor suspicious activities.'),
('SEC008','POL008','Request Lifecycle','Track requests through closure.'),
('SEC009','POL009','Refund Approval','Manager approval required.'),
('SEC010','POL010','Audit Controls','Maintain audit records.');

-- ==========================================
-- INVESTIGATION
-- ==========================================
INSERT INTO investigation VALUES
('INV001','CMP001','EMP001','2025-01-02','2025-01-04','Overdraft fee verified'),
('INV002','CMP002','EMP002','2025-01-06',NULL,'Reviewing account updates'),
('INV003','CMP003','EMP001','2025-01-10',NULL,'Examining duplicate transaction'),
('INV004','CMP004','EMP006','2025-01-12',NULL,'Technical team engaged'),
('INV005','CMP005','EMP007','2025-01-16','2025-01-18','Fee reversal approved'),
('INV006','CMP006','EMP002','2025-01-18',NULL,'Card system analysis'),
('INV007','CMP007','EMP001','2025-01-21',NULL,'ATM records requested'),
('INV008','CMP008','EMP006','2025-01-22',NULL,'Service quality assessment'),
('INV009','CMP009','EMP007','2025-01-25',NULL,'Fraud analysis underway'),
('INV010','CMP010','EMP002','2025-01-26',NULL,'Fee verification');

-- ==========================================
-- RECOMMENDATION
-- ==========================================
INSERT INTO recommendation
(recommendation_id,investigation_id,recommendation_text,confidence_score)
VALUES
('REC001','INV001','Reverse overdraft fee',95.5),
('REC002','INV002','Notify customer of delay',90.0),
('REC003','INV003','Refund duplicate transaction',98.0),
('REC004','INV004','Reset online banking profile',88.5),
('REC005','INV005','Issue refund',97.0),
('REC006','INV006','Replace customer card',92.0),
('REC007','INV007','Credit disputed withdrawal',93.0),
('REC008','INV008','Apology and coaching',85.0),
('REC009','INV009','Freeze account and investigate',99.0),
('REC010','INV010','Refund monthly fee',91.0);

-- ==========================================
-- REVIEW REQUEST
-- ==========================================
INSERT INTO review_request
(review_request_id,complaint_id,recommendation_id,reviewer_id,status)
VALUES
('RR001','CMP001','REC001','EMP003','PENDING'),
('RR002','CMP002','REC002','EMP004','APPROVED'),
('RR003','CMP003','REC003','EMP003','PENDING'),
('RR004','CMP004','REC004','EMP008','PENDING'),
('RR005','CMP005','REC005','EMP004','APPROVED'),
('RR006','CMP006','REC006','EMP003','PENDING'),
('RR007','CMP007','REC007','EMP008','PENDING'),
('RR008','CMP008','REC008','EMP004','APPROVED'),
('RR009','CMP009','REC009','EMP003','UNDER_REVIEW'),
('RR010','CMP010','REC010','EMP008','PENDING');

-- ==========================================
-- REVIEW DECISION
-- ==========================================
INSERT INTO review_decision
(decision_id,review_request_id,decision,decision_reason)
VALUES
('DEC001','RR001','APPROVED','Valid fee dispute'),
('DEC002','RR002','APPROVED','Customer notified'),
('DEC003','RR003','REQUEST_CHANGES','Need transaction evidence'),
('DEC004','RR004','APPROVED','Issue confirmed'),
('DEC005','RR005','APPROVED','Refund justified'),
('DEC006','RR006','REQUEST_CHANGES','Need card logs'),
('DEC007','RR007','APPROVED','ATM evidence supports claim'),
('DEC008','RR008','APPROVED','Service issue verified'),
('DEC009','RR009','ESCALATED','Potential fraud case'),
('DEC010','RR010','APPROVED','Fee charged in error');

-- ==========================================
-- CUSTOMER RESPONSE
-- ==========================================
INSERT INTO customer_response VALUES
('RES001','CMP001','Your fee has been reversed.','EMP003','2025-01-05'),
('RES002','CMP002','Investigation is ongoing.','EMP004','2025-01-06'),
('RES003','CMP003','Additional review required.','EMP003','2025-01-12'),
('RES004','CMP004','Online banking reset completed.','EMP008','2025-01-13'),
('RES005','CMP005','Refund issued successfully.','EMP004','2025-01-19'),
('RES006','CMP006','Replacement card approved.','EMP003','2025-01-20'),
('RES007','CMP007','ATM claim is being reviewed.','EMP008','2025-01-22'),
('RES008','CMP008','We apologize for your experience.','EMP004','2025-01-23'),
('RES009','CMP009','Fraud investigation has started.','EMP003','2025-01-26'),
('RES010','CMP010','Fee refund approved.','EMP008','2025-01-27');

-- ==========================================
-- AUDIT LOG
-- ==========================================
INSERT INTO audit_log
(entity_name,entity_id,action_type,performed_by,details)
VALUES
('COMPLAINT','CMP001','CREATE','EMP001','Complaint created'),
('COMPLAINT','CMP002','UPDATE','EMP002','Status updated'),
('COMPLAINT','CMP003','UPDATE','EMP001','Assigned for review'),
('COMPLAINT','CMP004','CREATE','EMP006','Complaint opened'),
('COMPLAINT','CMP005','CLOSE','EMP007','Complaint resolved'),
('SERVICE_REQUEST','SR002','CREATE','EMP002','Request entered'),
('INVESTIGATION','INV003','UPDATE','EMP001','Evidence requested'),
('RECOMMENDATION','REC005','CREATE','EMP007','Recommendation generated'),
('REVIEW_REQUEST','RR009','ESCALATE','EMP003','Fraud risk detected'),
('CUSTOMER_RESPONSE','RES010','SEND','EMP008','Response sent');

-- =====================================================
-- ADDITIONAL COMPLAINTS (CMP011 - CMP030)
-- =====================================================

INSERT INTO complaint VALUES

-- CUS001 (3 additional complaints)
('CMP011','CUS001','ACC001','Web','Service Delay',
 'Complaint not updated within SLA',
 'Medium','OPEN','2025-02-01 09:15:00','EMP001'),

('CMP012','CUS001','ACC001','Phone','Fee Dispute',
 'Unexpected service charge',
 'High','UNDER_REVIEW','2025-02-03 10:00:00','EMP002'),

('CMP013','CUS001','ACC001','Email','Customer Service',
 'Unsatisfactory support response',
 'Low','OPEN','2025-02-05 14:00:00','EMP006'),

-- CUS002 (2 additional complaints)
('CMP014','CUS002','ACC002','Web','Online Banking',
 'Mobile app login issue',
 'Medium','OPEN','2025-02-06 09:30:00','EMP006'),

('CMP015','CUS002','ACC002','Phone','Transaction Error',
 'Duplicate debit posted',
 'High','IN_PROGRESS','2025-02-08 11:15:00','EMP001'),

-- CUS003 (3 additional complaints)
('CMP016','CUS003','ACC003','Branch','Transaction Error',
 'ATM withdrawal discrepancy',
 'High','UNDER_REVIEW','2025-02-09 13:10:00','EMP001'),

('CMP017','CUS003','ACC003','Email','Fee Dispute',
 'Wire fee charged incorrectly',
 'Medium','OPEN','2025-02-11 09:40:00','EMP002'),

('CMP018','CUS003','ACC003','Web','Service Delay',
 'No response received',
 'Low','OPEN','2025-02-12 16:00:00','EMP006'),

-- CUS004 (1 additional complaint)
('CMP019','CUS004','ACC004','Phone','Customer Service',
 'Long hold times',
 'Low','OPEN','2025-02-13 10:45:00','EMP007'),

-- CUS005 (2 additional complaints)
('CMP020','CUS005','ACC005','Email','Fee Dispute',
 'Business account charge disputed',
 'Medium','OPEN','2025-02-14 11:00:00','EMP002'),

('CMP021','CUS005','ACC005','Branch','Service Delay',
 'Delayed account update',
 'Medium','IN_PROGRESS','2025-02-15 15:00:00','EMP001'),

-- CUS006 (2 additional complaints, one NULL account)
('CMP022','CUS006','ACC006','Web','Card Issue',
 'Card declined during purchase',
 'High','OPEN','2025-02-16 09:00:00','EMP002'),

('CMP023','CUS006',NULL,'Phone','Customer Service',
 'General complaint regarding service',
 'Low','OPEN','2025-02-17 14:30:00','EMP006'),

-- CUS007 (3 additional complaints)
('CMP024','CUS007','ACC007','Web','Transaction Error',
 'Transfer not reflected',
 'High','UNDER_REVIEW','2025-02-18 08:45:00','EMP001'),

('CMP025','CUS007','ACC007','Email','Online Banking',
 'Unable to download statements',
 'Medium','OPEN','2025-02-19 12:00:00','EMP002'),

('CMP026','CUS007','ACC007','Phone','Fee Dispute',
 'Investment fee concern',
 'Low','OPEN','2025-02-20 16:15:00','EMP007'),

-- CUS008 (1 additional complaint)
('CMP027','CUS008','ACC008','Web','Customer Service',
 'Agent disconnected call',
 'Low','OPEN','2025-02-21 10:00:00','EMP006'),

-- CUS009 (2 additional complaints, one NULL account)
('CMP028','CUS009','ACC009','Branch','Fraud Claim',
 'Suspicious transaction detected',
 'Critical','UNDER_REVIEW','2025-02-22 09:20:00','EMP007'),

('CMP029','CUS009',NULL,'Email','Fraud Claim',
 'Potential identity theft concern',
 'Critical','OPEN','2025-02-23 11:45:00','EMP007'),

-- CUS010 (1 additional complaint, NULL account)
('CMP030','CUS010',NULL,'Web','Service Delay',
 'No response to inquiry',
 'Medium','OPEN','2025-02-24 13:15:00','EMP006');


-- =====================================================
-- COMPLAINT STATUS HISTORY
-- =====================================================

INSERT INTO complaint_status_history
(complaint_id,old_status,new_status,changed_by,comments)
VALUES

('CMP011',NULL,'OPEN','EMP001','Complaint created'),
('CMP012','OPEN','UNDER_REVIEW','EMP002','Escalated for analyst review'),
('CMP013',NULL,'OPEN','EMP006','Complaint registered'),

('CMP014',NULL,'OPEN','EMP006','Complaint received'),
('CMP015','OPEN','IN_PROGRESS','EMP001','Investigation started'),

('CMP016','OPEN','UNDER_REVIEW','EMP001','Assigned for review'),
('CMP017',NULL,'OPEN','EMP002','Complaint registered'),
('CMP018',NULL,'OPEN','EMP006','Complaint logged'),

('CMP019',NULL,'OPEN','EMP007','Complaint opened'),

('CMP020',NULL,'OPEN','EMP002','Complaint created'),
('CMP021','OPEN','IN_PROGRESS','EMP001','Investigation started'),

('CMP022',NULL,'OPEN','EMP002','Complaint received'),
('CMP023',NULL,'OPEN','EMP006','General complaint logged'),

('CMP024','OPEN','UNDER_REVIEW','EMP001','Evidence collection started'),
('CMP025',NULL,'OPEN','EMP002','Complaint registered'),
('CMP026',NULL,'OPEN','EMP007','Complaint opened'),

('CMP027',NULL,'OPEN','EMP006','Complaint created'),

('CMP028','IN_PROGRESS','UNDER_REVIEW','EMP007',
 'Fraud investigation initiated'),

('CMP029',NULL,'OPEN','EMP007',
 'Potential fraud complaint registered'),

('CMP030',NULL,'OPEN','EMP006',
 'Complaint logged');
