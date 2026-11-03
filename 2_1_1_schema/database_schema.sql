-- ============================================================================
-- FDM Banking Complaint Resolution Assistant
-- PostgreSQL schema for seeddatacrs.sql
-- Synthetic training database
-- ============================================================================

BEGIN;

-- Drop in reverse dependency order so the setup script is repeatable.
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS customer_response CASCADE;
DROP TABLE IF EXISTS review_decision CASCADE;
DROP TABLE IF EXISTS review_request CASCADE;
DROP TABLE IF EXISTS recommendation CASCADE;
DROP TABLE IF EXISTS investigation CASCADE;
DROP TABLE IF EXISTS policy_section CASCADE;
DROP TABLE IF EXISTS policy_document CASCADE;
DROP TABLE IF EXISTS service_request CASCADE;
DROP TABLE IF EXISTS fee CASCADE;
DROP TABLE IF EXISTS transactions CASCADE;
DROP TABLE IF EXISTS complaint_status_history CASCADE;
DROP TABLE IF EXISTS complaint CASCADE;
DROP TABLE IF EXISTS account CASCADE;
DROP TABLE IF EXISTS customer CASCADE;
DROP TABLE IF EXISTS employee CASCADE;

-- --------------------------------------------------------------------------
-- EMPLOYEE
-- --------------------------------------------------------------------------
CREATE TABLE employee (
    employee_id      VARCHAR(20) PRIMARY KEY,
    first_name       VARCHAR(80) NOT NULL,
    last_name        VARCHAR(80) NOT NULL,
    email            VARCHAR(255) NOT NULL UNIQUE,
    role             VARCHAR(40) NOT NULL,
    CONSTRAINT chk_employee_role CHECK (
        role IN ('Analyst', 'Reviewer', 'Manager', 'Supervisor', 'Specialist')
    )
);

-- --------------------------------------------------------------------------
-- CUSTOMER
-- --------------------------------------------------------------------------
CREATE TABLE customer (
    customer_id      VARCHAR(20) PRIMARY KEY,
    first_name       VARCHAR(80) NOT NULL,
    last_name        VARCHAR(80) NOT NULL,
    email            VARCHAR(255),
    phone_number     VARCHAR(30),
    segment          VARCHAR(40) NOT NULL,
    CONSTRAINT chk_customer_segment CHECK (
        segment IN ('Retail', 'Premier', 'Business')
    )
);

-- --------------------------------------------------------------------------
-- ACCOUNT
-- --------------------------------------------------------------------------
CREATE TABLE account (
    account_id       VARCHAR(20) PRIMARY KEY,
    customer_id      VARCHAR(20) NOT NULL,
    account_number   VARCHAR(40) NOT NULL UNIQUE,
    account_type     VARCHAR(40) NOT NULL,
    status           VARCHAR(30) NOT NULL,
    balance          NUMERIC(15,2) NOT NULL DEFAULT 0,
    open_date        DATE NOT NULL,
    CONSTRAINT fk_account_customer
        FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    CONSTRAINT chk_account_status CHECK (status IN ('ACTIVE', 'INACTIVE', 'CLOSED', 'RESTRICTED'))
);

-- --------------------------------------------------------------------------
-- COMPLAINT
-- account_id is intentionally nullable. The seed data contains general or
-- identity/fraud complaints that are not tied to one specific account.
-- customer_narrative preserves the customer's original complaint text.
-- --------------------------------------------------------------------------
CREATE TABLE complaint (
    complaint_id         VARCHAR(20) PRIMARY KEY,
    customer_id          VARCHAR(20) NOT NULL,
    account_id           VARCHAR(20),
    channel              VARCHAR(30) NOT NULL,
    category             VARCHAR(80) NOT NULL,
    customer_narrative   TEXT NOT NULL,
    priority             VARCHAR(20) NOT NULL,
    status               VARCHAR(30) NOT NULL,
    created_at           TIMESTAMP NOT NULL,
    assigned_employee_id VARCHAR(20),
    CONSTRAINT fk_complaint_customer
        FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    CONSTRAINT fk_complaint_account
        FOREIGN KEY (account_id) REFERENCES account(account_id),
    CONSTRAINT fk_complaint_assignee
        FOREIGN KEY (assigned_employee_id) REFERENCES employee(employee_id),
    CONSTRAINT chk_complaint_priority CHECK (priority IN ('Low', 'Medium', 'High', 'Critical')),
    CONSTRAINT chk_complaint_status CHECK (
        status IN ('OPEN', 'IN_PROGRESS', 'UNDER_REVIEW', 'PENDING_APPROVAL',
                   'CHANGES_REQUESTED', 'ESCALATED', 'RESOLVED', 'CLOSED')
    )
);

-- --------------------------------------------------------------------------
-- COMPLAINT STATUS HISTORY
-- Seed INSERTs omit an ID column, so status_history_id is generated.
-- --------------------------------------------------------------------------
CREATE TABLE complaint_status_history (
    status_history_id BIGSERIAL PRIMARY KEY,
    complaint_id      VARCHAR(20) NOT NULL,
    old_status        VARCHAR(30),
    new_status        VARCHAR(30) NOT NULL,
    changed_by        VARCHAR(20) NOT NULL,
    comments          TEXT,
    status_timestamp  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_status_history_complaint
        FOREIGN KEY (complaint_id) REFERENCES complaint(complaint_id),
    CONSTRAINT fk_status_history_employee
        FOREIGN KEY (changed_by) REFERENCES employee(employee_id)
);

-- --------------------------------------------------------------------------
-- TRANSACTIONS
-- --------------------------------------------------------------------------
CREATE TABLE transactions (
    transaction_id    VARCHAR(20) PRIMARY KEY,
    account_id        VARCHAR(20) NOT NULL,
    transaction_type  VARCHAR(40) NOT NULL,
    amount            NUMERIC(15,2) NOT NULL,
    transaction_date  TIMESTAMP NOT NULL,
    balance_before    NUMERIC(15,2),
    balance_after     NUMERIC(15,2),
    description       VARCHAR(255),
    CONSTRAINT fk_transaction_account
        FOREIGN KEY (account_id) REFERENCES account(account_id),
    CONSTRAINT chk_transaction_type CHECK (transaction_type IN ('DEBIT', 'CREDIT')),
    CONSTRAINT chk_transaction_amount CHECK (amount >= 0)
);

-- --------------------------------------------------------------------------
-- FEE
-- transaction_id is nullable because some fees are assessed independently.
-- --------------------------------------------------------------------------
CREATE TABLE fee (
    fee_id           VARCHAR(20) PRIMARY KEY,
    account_id       VARCHAR(20) NOT NULL,
    transaction_id   VARCHAR(20),
    fee_type         VARCHAR(80) NOT NULL,
    amount           NUMERIC(15,2) NOT NULL,
    fee_date         TIMESTAMP NOT NULL,
    reversed         BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_fee_account
        FOREIGN KEY (account_id) REFERENCES account(account_id),
    CONSTRAINT fk_fee_transaction
        FOREIGN KEY (transaction_id) REFERENCES transactions(transaction_id),
    CONSTRAINT chk_fee_amount CHECK (amount >= 0)
);

-- --------------------------------------------------------------------------
-- SERVICE REQUEST
-- --------------------------------------------------------------------------
CREATE TABLE service_request (
    request_id       VARCHAR(20) PRIMARY KEY,
    customer_id      VARCHAR(20) NOT NULL,
    account_id       VARCHAR(20),
    request_type     VARCHAR(100) NOT NULL,
    status           VARCHAR(30) NOT NULL,
    created_date     DATE NOT NULL,
    closed_date      DATE,
    CONSTRAINT fk_service_request_customer
        FOREIGN KEY (customer_id) REFERENCES customer(customer_id),
    CONSTRAINT fk_service_request_account
        FOREIGN KEY (account_id) REFERENCES account(account_id),
    CONSTRAINT chk_service_request_status CHECK (status IN ('OPEN', 'IN_PROGRESS', 'CLOSED')),
    CONSTRAINT chk_service_request_dates CHECK (closed_date IS NULL OR closed_date >= created_date)
);

-- --------------------------------------------------------------------------
-- POLICY DOCUMENT / POLICY SECTION
-- These relational records can store metadata/searchable sections used by
-- exercises. The richer RAG document/vector store can remain separate and
-- link through stable policy IDs/source IDs.
-- --------------------------------------------------------------------------
CREATE TABLE policy_document (
    policy_id        VARCHAR(20) PRIMARY KEY,
    title            VARCHAR(255) NOT NULL,
    version          VARCHAR(30) NOT NULL,
    effective_date   DATE NOT NULL,
    status           VARCHAR(30) NOT NULL,
    CONSTRAINT chk_policy_status CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'RETIRED', 'DRAFT'))
);

CREATE TABLE policy_section (
    section_id       VARCHAR(20) PRIMARY KEY,
    policy_id        VARCHAR(20) NOT NULL,
    section_title    VARCHAR(255) NOT NULL,
    section_text     TEXT NOT NULL,
    CONSTRAINT fk_policy_section_document
        FOREIGN KEY (policy_id) REFERENCES policy_document(policy_id)
);

-- --------------------------------------------------------------------------
-- INVESTIGATION
-- --------------------------------------------------------------------------
CREATE TABLE investigation (
    investigation_id VARCHAR(20) PRIMARY KEY,
    complaint_id     VARCHAR(20) NOT NULL,
    analyst_id       VARCHAR(20) NOT NULL,
    start_date       DATE NOT NULL,
    end_date         DATE,
    findings         TEXT,
    CONSTRAINT fk_investigation_complaint
        FOREIGN KEY (complaint_id) REFERENCES complaint(complaint_id),
    CONSTRAINT fk_investigation_analyst
        FOREIGN KEY (analyst_id) REFERENCES employee(employee_id),
    CONSTRAINT chk_investigation_dates CHECK (end_date IS NULL OR end_date >= start_date)
);

-- --------------------------------------------------------------------------
-- RECOMMENDATION
-- --------------------------------------------------------------------------
CREATE TABLE recommendation (
    recommendation_id   VARCHAR(20) PRIMARY KEY,
    investigation_id    VARCHAR(20) NOT NULL,
    recommendation_text TEXT NOT NULL,
    confidence_score    NUMERIC(5,2),
    CONSTRAINT fk_recommendation_investigation
        FOREIGN KEY (investigation_id) REFERENCES investigation(investigation_id),
    CONSTRAINT chk_confidence_score CHECK (
        confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100)
    )
);

-- --------------------------------------------------------------------------
-- REVIEW REQUEST / REVIEW DECISION
-- --------------------------------------------------------------------------
CREATE TABLE review_request (
    review_request_id  VARCHAR(20) PRIMARY KEY,
    complaint_id       VARCHAR(20) NOT NULL,
    recommendation_id  VARCHAR(20) NOT NULL,
    reviewer_id        VARCHAR(20) NOT NULL,
    status             VARCHAR(30) NOT NULL,
    CONSTRAINT fk_review_request_complaint
        FOREIGN KEY (complaint_id) REFERENCES complaint(complaint_id),
    CONSTRAINT fk_review_request_recommendation
        FOREIGN KEY (recommendation_id) REFERENCES recommendation(recommendation_id),
    CONSTRAINT fk_review_request_reviewer
        FOREIGN KEY (reviewer_id) REFERENCES employee(employee_id),
    CONSTRAINT chk_review_request_status CHECK (
        status IN ('PENDING', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'CHANGES_REQUESTED', 'ESCALATED')
    )
);

CREATE TABLE review_decision (
    decision_id        VARCHAR(20) PRIMARY KEY,
    review_request_id  VARCHAR(20) NOT NULL,
    decision           VARCHAR(30) NOT NULL,
    decision_reason    TEXT NOT NULL,
    decision_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_review_decision_request
        FOREIGN KEY (review_request_id) REFERENCES review_request(review_request_id),
    CONSTRAINT chk_review_decision CHECK (
        decision IN ('APPROVED', 'REJECTED', 'REQUEST_CHANGES', 'ESCALATED')
    )
);

-- --------------------------------------------------------------------------
-- CUSTOMER RESPONSE
-- --------------------------------------------------------------------------
CREATE TABLE customer_response (
    response_id      VARCHAR(20) PRIMARY KEY,
    complaint_id     VARCHAR(20) NOT NULL,
    response_text    TEXT NOT NULL,
    sent_by          VARCHAR(20) NOT NULL,
    sent_date        DATE NOT NULL,
    CONSTRAINT fk_customer_response_complaint
        FOREIGN KEY (complaint_id) REFERENCES complaint(complaint_id),
    CONSTRAINT fk_customer_response_employee
        FOREIGN KEY (sent_by) REFERENCES employee(employee_id)
);

-- --------------------------------------------------------------------------
-- AUDIT LOG
-- entity_name + entity_id form a polymorphic logical reference, so entity_id
-- is intentionally not declared as a foreign key to one table.
-- Seed INSERTs omit audit_id, which is generated automatically.
-- --------------------------------------------------------------------------
CREATE TABLE audit_log (
    audit_id        BIGSERIAL PRIMARY KEY,
    entity_name     VARCHAR(60) NOT NULL,
    entity_id       VARCHAR(40) NOT NULL,
    action_type     VARCHAR(40) NOT NULL,
    performed_by    VARCHAR(20),
    details         TEXT,
    performed_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_employee
        FOREIGN KEY (performed_by) REFERENCES employee(employee_id)
);

-- --------------------------------------------------------------------------
-- Useful indexes for the exercises and later API/RAG/agent layers
-- --------------------------------------------------------------------------
CREATE INDEX idx_account_customer ON account(customer_id);
CREATE INDEX idx_complaint_customer ON complaint(customer_id);
CREATE INDEX idx_complaint_account ON complaint(account_id);
CREATE INDEX idx_complaint_status ON complaint(status);
CREATE INDEX idx_complaint_priority ON complaint(priority);
CREATE INDEX idx_complaint_assignee ON complaint(assigned_employee_id);
CREATE INDEX idx_complaint_created_at ON complaint(created_at);
CREATE INDEX idx_status_history_complaint ON complaint_status_history(complaint_id, status_timestamp);
CREATE INDEX idx_transaction_account_date ON transactions(account_id, transaction_date);
CREATE INDEX idx_fee_account_date ON fee(account_id, fee_date);
CREATE INDEX idx_service_request_customer ON service_request(customer_id);
CREATE INDEX idx_policy_section_policy ON policy_section(policy_id);
CREATE INDEX idx_investigation_complaint ON investigation(complaint_id);
CREATE INDEX idx_recommendation_investigation ON recommendation(investigation_id);
CREATE INDEX idx_review_request_complaint ON review_request(complaint_id);
CREATE INDEX idx_review_request_reviewer ON review_request(reviewer_id);
CREATE INDEX idx_review_decision_request ON review_decision(review_request_id);
CREATE INDEX idx_response_complaint ON customer_response(complaint_id);
CREATE INDEX idx_audit_entity ON audit_log(entity_name, entity_id);
CREATE INDEX idx_audit_actor_time ON audit_log(performed_by, performed_at);

COMMIT;

-- ============================================================================
-- SEED DATA
-- ============================================================================

-- Existing synthetic seed data
BEGIN;

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

COMMIT;


-- ============================================================================
-- Validation queries for FDM Banking Complaint Resolution Assistant seed data
-- PostgreSQL
-- ============================================================================

-- Expected core row counts from seeddatacrs.sql.
SELECT 'employee' AS table_name, COUNT(*) AS row_count FROM employee
UNION ALL SELECT 'customer', COUNT(*) FROM customer
UNION ALL SELECT 'account', COUNT(*) FROM account
UNION ALL SELECT 'complaint', COUNT(*) FROM complaint
UNION ALL SELECT 'complaint_status_history', COUNT(*) FROM complaint_status_history
UNION ALL SELECT 'transactions', COUNT(*) FROM transactions
UNION ALL SELECT 'fee', COUNT(*) FROM fee
UNION ALL SELECT 'service_request', COUNT(*) FROM service_request
UNION ALL SELECT 'policy_document', COUNT(*) FROM policy_document
UNION ALL SELECT 'policy_section', COUNT(*) FROM policy_section
UNION ALL SELECT 'investigation', COUNT(*) FROM investigation
UNION ALL SELECT 'recommendation', COUNT(*) FROM recommendation
UNION ALL SELECT 'review_request', COUNT(*) FROM review_request
UNION ALL SELECT 'review_decision', COUNT(*) FROM review_decision
UNION ALL SELECT 'customer_response', COUNT(*) FROM customer_response
UNION ALL SELECT 'audit_log', COUNT(*) FROM audit_log
ORDER BY table_name;

-- Complaints with no account are valid and intentionally preserved.
SELECT complaint_id, customer_id, category, customer_narrative
FROM complaint
WHERE account_id IS NULL
ORDER BY complaint_id;

-- Referential-integrity sanity checks. Each should return 0 rows.
SELECT c.*
FROM complaint c
LEFT JOIN customer cu ON cu.customer_id = c.customer_id
WHERE cu.customer_id IS NULL;

SELECT c.*
FROM complaint c
LEFT JOIN account a ON a.account_id = c.account_id
WHERE c.account_id IS NOT NULL AND a.account_id IS NULL;

SELECT a.*
FROM account a
LEFT JOIN customer c ON c.customer_id = a.customer_id
WHERE c.customer_id IS NULL;

SELECT rr.*
FROM review_request rr
LEFT JOIN recommendation r ON r.recommendation_id = rr.recommendation_id
WHERE r.recommendation_id IS NULL;

-- Ensure each seeded policy section points to a real policy.
SELECT ps.*
FROM policy_section ps
LEFT JOIN policy_document pd ON pd.policy_id = ps.policy_id
WHERE pd.policy_id IS NULL;

-- Useful exercise query: complaints and their assigned analyst.
SELECT c.complaint_id,
       c.customer_id,
       c.account_id,
       c.category,
       c.priority,
       c.status,
       c.customer_narrative,
       e.first_name || ' ' || e.last_name AS assigned_analyst
FROM complaint c
LEFT JOIN employee e ON e.employee_id = c.assigned_employee_id
ORDER BY c.created_at, c.complaint_id;
