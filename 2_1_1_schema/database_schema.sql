-- =====================================================================
-- database_schema.sql — Banking Complaint Resolution Assistant — Database Schema (PostgreSQL / Supabase)
-- Source: Logical ERD + seeddatacrs.sql + Exercise 1.3.1 Complaint Spec
--
-- Column ORDER matches seeddatacrs.sql exactly, because several seed
-- INSERTs omit a column list (employee, account, complaint, transactions,
-- fee, service_request, policy_document, policy_section, investigation,
-- customer_response). Do not reorder or add columns to those tables
-- without updating the seed file.
--
-- Supabase: paste this file into SQL Editor and Run, then do the same with seeddatacrs.sql.
-- =====================================================================

DROP TABLE IF EXISTS audit_log                CASCADE;
DROP TABLE IF EXISTS customer_response        CASCADE;
DROP TABLE IF EXISTS review_decision          CASCADE;
DROP TABLE IF EXISTS review_request           CASCADE;
DROP TABLE IF EXISTS recommendation           CASCADE;
DROP TABLE IF EXISTS investigation            CASCADE;
DROP TABLE IF EXISTS policy_section           CASCADE;
DROP TABLE IF EXISTS policy_document          CASCADE;
DROP TABLE IF EXISTS service_request          CASCADE;
DROP TABLE IF EXISTS fee                      CASCADE;
DROP TABLE IF EXISTS transactions             CASCADE;
DROP TABLE IF EXISTS complaint_status_history CASCADE;
DROP TABLE IF EXISTS complaint                CASCADE;
DROP TABLE IF EXISTS account                  CASCADE;
DROP TABLE IF EXISTS customer                 CASCADE;
DROP TABLE IF EXISTS employee                 CASCADE;

-- =====================================================================
-- MASTER / REFERENCE
-- =====================================================================

CREATE TABLE employee (
    employee_id   VARCHAR(10)  PRIMARY KEY,
    first_name    VARCHAR(50)  NOT NULL,
    last_name     VARCHAR(50)  NOT NULL,
    email         VARCHAR(100) NOT NULL UNIQUE,
    role          VARCHAR(20)  NOT NULL
        CHECK (role IN ('Analyst','Reviewer','Supervisor','Manager'))
);

CREATE TABLE customer (
    customer_id   VARCHAR(10)  PRIMARY KEY,
    first_name    VARCHAR(50)  NOT NULL,
    last_name     VARCHAR(50)  NOT NULL,
    email         VARCHAR(100) UNIQUE,
    phone_number  VARCHAR(20),
    segment       VARCHAR(20)  NOT NULL
        CHECK (segment IN ('Retail','Premier','Business'))
);

CREATE TABLE account (
    account_id      VARCHAR(10)   PRIMARY KEY,
    customer_id     VARCHAR(10)   NOT NULL REFERENCES customer(customer_id),
    account_number  VARCHAR(20)   NOT NULL UNIQUE,
    account_type    VARCHAR(20)   NOT NULL
        CHECK (account_type IN ('Chequing','Savings','Business')),
    status          VARCHAR(20)   NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE','DORMANT','FROZEN','CLOSED')),
    balance         NUMERIC(15,2) NOT NULL DEFAULT 0,
    open_date       DATE          NOT NULL,
    -- Lets child tables verify an account really belongs to the customer
    CONSTRAINT uq_account_customer UNIQUE (account_id, customer_id)
);

-- =====================================================================
-- SUPPORTING TRANSACTION DATA
-- =====================================================================

CREATE TABLE transactions (
    transaction_id    VARCHAR(10)   PRIMARY KEY,
    account_id        VARCHAR(10)   NOT NULL REFERENCES account(account_id),
    transaction_type  VARCHAR(10)   NOT NULL
        CHECK (transaction_type IN ('DEBIT','CREDIT')),
    amount            NUMERIC(15,2) NOT NULL CHECK (amount > 0),
    transaction_date  TIMESTAMP     NOT NULL,
    balance_before    NUMERIC(15,2) NOT NULL,
    balance_after     NUMERIC(15,2) NOT NULL,
    description       VARCHAR(255),
    -- Balance arithmetic must reconcile with the transaction direction
    CONSTRAINT chk_txn_balance CHECK (
        (transaction_type = 'DEBIT'  AND balance_after = balance_before - amount) OR
        (transaction_type = 'CREDIT' AND balance_after = balance_before + amount)
    ),
    CONSTRAINT uq_txn_account UNIQUE (transaction_id, account_id)
);

CREATE TABLE fee (
    fee_id          VARCHAR(10)   PRIMARY KEY,
    account_id      VARCHAR(10)   NOT NULL REFERENCES account(account_id),
    transaction_id  VARCHAR(10),                          -- nullable
    fee_type        VARCHAR(50)   NOT NULL,
    amount          NUMERIC(10,2) NOT NULL CHECK (amount >= 0),
    fee_date        TIMESTAMP     NOT NULL,
    reversed        BOOLEAN       NOT NULL DEFAULT FALSE,
    -- If a fee is tied to a transaction, it must be the same account's transaction
    CONSTRAINT fk_fee_txn_same_account
        FOREIGN KEY (transaction_id, account_id)
        REFERENCES transactions(transaction_id, account_id)
);

CREATE TABLE service_request (
    request_id    VARCHAR(10) PRIMARY KEY,
    customer_id   VARCHAR(10) NOT NULL REFERENCES customer(customer_id),
    account_id    VARCHAR(10),                            -- nullable
    request_type  VARCHAR(50) NOT NULL,
    status        VARCHAR(20) NOT NULL
        CHECK (status IN ('OPEN','IN_PROGRESS','CLOSED','CANCELLED')),
    created_date  DATE        NOT NULL,
    closed_date   DATE,
    CONSTRAINT fk_sr_account_owner
        FOREIGN KEY (account_id, customer_id)
        REFERENCES account(account_id, customer_id),
    CONSTRAINT chk_sr_dates  CHECK (closed_date IS NULL OR closed_date >= created_date),
    CONSTRAINT chk_sr_closed CHECK ((status = 'CLOSED') = (closed_date IS NOT NULL))
);

-- =====================================================================
-- COMPLAINT WORKFLOW
-- =====================================================================

CREATE TABLE complaint (
    complaint_id          VARCHAR(10)  PRIMARY KEY,
    customer_id           VARCHAR(10)  NOT NULL REFERENCES customer(customer_id),
    account_id            VARCHAR(10),                    -- nullable: unmatched account (AT-02)
    channel               VARCHAR(20)  NOT NULL
        CHECK (channel IN ('Phone','Email','Branch','Web')),
    category              VARCHAR(50)  NOT NULL,          -- taxonomy pending business approval (spec §Clarification log)
    customer_narrative    TEXT         NOT NULL,
    priority              VARCHAR(10)  NOT NULL
        CHECK (priority IN ('Low','Medium','High','Critical')),
    status                VARCHAR(20)  NOT NULL DEFAULT 'OPEN'
        CHECK (status IN ('OPEN','IN_PROGRESS','UNDER_REVIEW','ESCALATED','RESOLVED','CLOSED')),
    created_at            TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    assigned_employee_id  VARCHAR(10)  REFERENCES employee(employee_id),
    -- When an account is given, it must belong to the complaining customer
    CONSTRAINT fk_complaint_account_owner
        FOREIGN KEY (account_id, customer_id)
        REFERENCES account(account_id, customer_id)
);

CREATE TABLE complaint_status_history (
    status_history_id  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    complaint_id       VARCHAR(10)  NOT NULL REFERENCES complaint(complaint_id),
    old_status         VARCHAR(20),                       -- NULL on creation
    new_status         VARCHAR(20)  NOT NULL,
    changed_by         VARCHAR(10)  NOT NULL REFERENCES employee(employee_id),
    comments           VARCHAR(255),
    changed_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,  -- audit timestamp (spec §7)
    CONSTRAINT chk_status_values CHECK (
        new_status IN ('OPEN','IN_PROGRESS','UNDER_REVIEW','ESCALATED','RESOLVED','CLOSED') AND
        (old_status IS NULL OR old_status IN ('OPEN','IN_PROGRESS','UNDER_REVIEW','ESCALATED','RESOLVED','CLOSED'))
    )
);

CREATE TABLE investigation (
    investigation_id  VARCHAR(10) PRIMARY KEY,
    complaint_id      VARCHAR(10) NOT NULL REFERENCES complaint(complaint_id),
    analyst_id        VARCHAR(10) NOT NULL REFERENCES employee(employee_id),
    start_date        DATE        NOT NULL,
    end_date          DATE,
    findings          TEXT,
    CONSTRAINT chk_inv_dates CHECK (end_date IS NULL OR end_date >= start_date)
);

CREATE TABLE recommendation (
    recommendation_id    VARCHAR(10)  PRIMARY KEY,
    investigation_id     VARCHAR(10)  NOT NULL REFERENCES investigation(investigation_id),
    recommendation_text  TEXT         NOT NULL,
    confidence_score     NUMERIC(5,2)
        CHECK (confidence_score BETWEEN 0 AND 100),
    created_at           TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE review_request (
    review_request_id  VARCHAR(10) PRIMARY KEY,
    complaint_id       VARCHAR(10) NOT NULL REFERENCES complaint(complaint_id),
    recommendation_id  VARCHAR(10) NOT NULL REFERENCES recommendation(recommendation_id),
    reviewer_id        VARCHAR(10) NOT NULL REFERENCES employee(employee_id),
    status             VARCHAR(20) NOT NULL DEFAULT 'PENDING'
        CHECK (status IN ('PENDING','UNDER_REVIEW','APPROVED','REJECTED','ESCALATED')),
    requested_at       TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE review_decision (
    decision_id        VARCHAR(10)  PRIMARY KEY,
    review_request_id  VARCHAR(10)  NOT NULL REFERENCES review_request(review_request_id),
    decision           VARCHAR(20)  NOT NULL
        CHECK (decision IN ('APPROVED','REJECTED','REQUEST_CHANGES','ESCALATED')),
    decision_reason    VARCHAR(255) NOT NULL,             -- rationale required (spec §7, AT-09)
    decided_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE customer_response (
    response_id    VARCHAR(10) PRIMARY KEY,
    complaint_id   VARCHAR(10) NOT NULL REFERENCES complaint(complaint_id),
    response_text  TEXT        NOT NULL,
    sent_by        VARCHAR(10) NOT NULL REFERENCES employee(employee_id),
    sent_date      DATE        NOT NULL
);

-- =====================================================================
-- POLICY METADATA
-- =====================================================================

CREATE TABLE policy_document (
    policy_id       VARCHAR(10)  PRIMARY KEY,
    title           VARCHAR(150) NOT NULL,
    version         VARCHAR(10)  NOT NULL,
    effective_date  DATE         NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('DRAFT','ACTIVE','RETIRED')),
    CONSTRAINT uq_policy_title_version UNIQUE (title, version)
);

CREATE TABLE policy_section (
    section_id     VARCHAR(10)  PRIMARY KEY,
    policy_id      VARCHAR(10)  NOT NULL REFERENCES policy_document(policy_id),
    section_title  VARCHAR(150) NOT NULL,
    section_text   TEXT         NOT NULL
);

-- =====================================================================
-- AUDIT (polymorphic: entity_name + entity_id, no FK on entity_id)
-- =====================================================================

CREATE TABLE audit_log (
    audit_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    entity_name   VARCHAR(50)  NOT NULL
        CHECK (entity_name IN ('COMPLAINT','SERVICE_REQUEST','INVESTIGATION','RECOMMENDATION',
                               'REVIEW_REQUEST','REVIEW_DECISION','CUSTOMER_RESPONSE')),
    entity_id     VARCHAR(20)  NOT NULL,
    action_type   VARCHAR(20)  NOT NULL
        CHECK (action_type IN ('CREATE','UPDATE','CLOSE','ESCALATE','SEND','OVERRIDE','APPROVE','REJECT')),
    performed_by  VARCHAR(10)  NOT NULL REFERENCES employee(employee_id),
    details       TEXT,
    performed_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================================
-- INDEXES on foreign keys and common lookups
-- =====================================================================

CREATE INDEX idx_account_customer        ON account(customer_id);
CREATE INDEX idx_txn_account             ON transactions(account_id);
CREATE INDEX idx_fee_account             ON fee(account_id);
CREATE INDEX idx_fee_txn                 ON fee(transaction_id);
CREATE INDEX idx_sr_customer             ON service_request(customer_id);
CREATE INDEX idx_sr_account              ON service_request(account_id);
CREATE INDEX idx_complaint_customer      ON complaint(customer_id);
CREATE INDEX idx_complaint_account       ON complaint(account_id);
CREATE INDEX idx_complaint_assigned      ON complaint(assigned_employee_id);
CREATE INDEX idx_complaint_status        ON complaint(status, priority);
CREATE INDEX idx_complaint_category      ON complaint(category);
CREATE INDEX idx_csh_complaint           ON complaint_status_history(complaint_id);
CREATE INDEX idx_inv_complaint           ON investigation(complaint_id);
CREATE INDEX idx_rec_investigation       ON recommendation(investigation_id);
CREATE INDEX idx_rr_complaint            ON review_request(complaint_id);
CREATE INDEX idx_rr_reviewer             ON review_request(reviewer_id);
CREATE INDEX idx_rd_review_request       ON review_decision(review_request_id);
CREATE INDEX idx_resp_complaint          ON customer_response(complaint_id);
CREATE INDEX idx_section_policy          ON policy_section(policy_id);
CREATE INDEX idx_audit_entity            ON audit_log(entity_name, entity_id);
CREATE INDEX idx_audit_performed_by      ON audit_log(performed_by);

-- =====================================================================
-- SUPABASE: ROW LEVEL SECURITY
-- Supabase exposes every table in the public schema through its REST API.
-- Enabling RLS with no policies blocks the anon/authenticated API keys
-- from reading or writing customer data until you add explicit policies.
-- The SQL Editor (postgres role) and the service_role key bypass RLS,
-- so the seed script still loads normally.
-- =====================================================================

ALTER TABLE employee                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE account                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions             ENABLE ROW LEVEL SECURITY;
ALTER TABLE fee                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE service_request          ENABLE ROW LEVEL SECURITY;
ALTER TABLE complaint                ENABLE ROW LEVEL SECURITY;
ALTER TABLE complaint_status_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE investigation            ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendation           ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_request           ENABLE ROW LEVEL SECURITY;
ALTER TABLE review_decision          ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_response        ENABLE ROW LEVEL SECURITY;
ALTER TABLE policy_document          ENABLE ROW LEVEL SECURITY;
ALTER TABLE policy_section           ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log                ENABLE ROW LEVEL SECURITY;