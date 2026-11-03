# Data Dictionary — Banking Complaint Resolution Database

Week 2 | Exercise 2.1.1 · PostgreSQL 16 · generated from the live database built by `database_schema.sql` (the supplied setup script, unchanged). Types, nullability, keys and examples come from the database catalog. Purpose text is written by hand.

All data is **synthetic** training data. Columns marked PII would hold personal data in a real deployment.

## Contents

- [Conventions](#conventions)
- [Table overview](#table-overview)
- [Relationships](#relationships)
- [Tables](#tables)
- [Cross-table rules not expressible as constraints](#cross-table-rules-not-expressible-as-constraints)
- [Indexes](#indexes)
- [Known limitations of the seed data](#known-limitations-of-the-seed-data)
- [How to reproduce](#how-to-reproduce)

## Conventions

| Item | Convention |
|---|---|
| Business IDs | `VARCHAR(20)` with a type prefix: `EMP`, `CUS`, `ACC`, `CMP`, `TXN`, `FEE`, `SR`, `POL`, `SEC`, `INV`, `REC`, `RR`, `DEC`, `RES`. Kept as text so IDs match the source files exactly. |
| Surrogate IDs | `BIGSERIAL` for the two append-only logs (`status_history_id`, `audit_id`) because the seed does not supply them. |
| Money | `NUMERIC(15,2)`; never floating point. |
| Status codes | Workflow statuses are UPPER_SNAKE_CASE; human-facing domains (priority, role, segment) are Title Case. Both enforced with `CHECK`. |
| Timestamps | `TIMESTAMP` without time zone, as supplied by the seed. |
| Nullable | **Y** = NULL allowed, **N** = `NOT NULL`. |
| Delete behaviour | All FKs are `NO ACTION` (restrict): a parent row cannot be deleted while children exist. Tested in seed_validation N25/N26. |

## Table overview

| # | Table | Group | Rows | Purpose |
|---|---|---|---|---|
| 1 | [`employee`](#employee) | Reference / master | 10 | Bank staff who handle, review, approve or respond to complaints. |
| 2 | [`customer`](#customer) | Reference / master | 10 | Bank customers who own accounts and raise complaints or service requests. |
| 3 | [`account`](#account) | Reference / master | 10 | A bank account owned by exactly one customer. |
| 4 | [`complaint`](#complaint) | Complaint workflow | 30 | Central workflow record: one customer complaint from intake to closure. |
| 5 | [`complaint_status_history`](#complaint_status_history) | Supporting history | 30 | Append-only log of every complaint status transition. |
| 6 | [`transactions`](#transactions) | Supporting transaction | 10 | Posted debits and credits on an account; evidence for transaction complaints. |
| 7 | [`fee`](#fee) | Supporting transaction | 10 | Fees charged to an account; the main evidence for fee-dispute complaints. |
| 8 | [`service_request`](#service_request) | Supporting history | 10 | Non-complaint customer requests (address change, PIN reset, ...); context for complaints. |
| 9 | [`policy_document`](#policy_document) | Reference / master | 10 | Bank policies that govern complaint handling; metadata for the later RAG corpus. |
| 10 | [`policy_section`](#policy_section) | Reference / master | 10 | Searchable sections of a policy, cited by recommendations and agents. |
| 11 | [`investigation`](#investigation) | Complaint workflow | 10 | An analyst's investigation of a complaint. |
| 12 | [`recommendation`](#recommendation) | Complaint workflow | 10 | Proposed resolution produced by an investigation (human- or AI-generated). |
| 13 | [`review_request`](#review_request) | Complaint workflow | 10 | Request for a reviewer to approve a recommendation (human-in-the-loop gate). |
| 14 | [`review_decision`](#review_decision) | Complaint workflow | 10 | The reviewer's decision on a review request. One-to-many so re-reviews are kept. |
| 15 | [`customer_response`](#customer_response) | Complaint workflow | 10 | Communications sent to the customer about a complaint. |
| 16 | [`audit_log`](#audit_log) | Polymorphic audit | 10 | Who did what to which record; supports regulatory audit of the workflow. |

The `#` column is also the load (dependency) order.

## Relationships

| Parent | Child | Cardinality | Required? | Enforced by |
|---|---|---|---|---|
| customer | account | 1 : 0..* | Yes | fk_account_customer |
| customer | complaint | 1 : 0..* | Yes | fk_complaint_customer |
| account | complaint | 0..1 : 0..* | Optional | fk_complaint_account (ownership match checked in validation) |
| employee | complaint (assignee) | 0..1 : 0..* | Optional | fk_complaint_assignee |
| complaint | complaint_status_history | 1 : 1..* | Yes | fk_status_history_complaint; ≥1 row checked in validation |
| employee | complaint_status_history | 1 : 0..* | Yes | fk_status_history_employee |
| account | transactions | 1 : 0..* | Yes | fk_transaction_account |
| account | fee | 1 : 0..* | Yes | fk_fee_account |
| transactions | fee | 0..1 : 0..* | Optional | fk_fee_transaction |
| customer | service_request | 1 : 0..* | Yes | fk_service_request_customer |
| account | service_request | 0..1 : 0..* | Optional | fk_service_request_account (ownership match checked in validation) |
| policy_document | policy_section | 1 : 1..* | Yes | fk_policy_section_document |
| complaint | investigation | 1 : 0..* | Yes | fk_investigation_complaint |
| employee | investigation | 1 : 0..* | Yes | fk_investigation_analyst |
| investigation | recommendation | 1 : 0..* | Yes | fk_recommendation_investigation |
| complaint | review_request | 1 : 0..* | Yes | fk_review_request_complaint |
| recommendation | review_request | 1 : 0..* | Yes | fk_review_request_recommendation |
| employee | review_request | 1 : 0..* | Yes | fk_review_request_reviewer |
| review_request | review_decision | 1 : 0..* | Yes | fk_review_decision_request |
| complaint | customer_response | 1 : 0..* | Yes | fk_customer_response_complaint |
| employee | customer_response | 1 : 0..* | Yes | fk_customer_response_employee |
| employee | audit_log | 0..1 : 0..* | Optional | fk_audit_employee |
| any entity | audit_log | 1 : 0..* | Logical | entity_name + entity_id (polymorphic, checked in validation) |

## Tables

### employee

**Purpose:** Bank staff who handle, review, approve or respond to complaints.  
**Group:** Reference / master · **Seed rows:** 10

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `employee_id` | VARCHAR(20) | N | **PK** | Stable business identifier for a staff member (EMPnnn). | Seed INSERT | `EMP001` |
| `first_name` | VARCHAR(80) | N | – | Employee given name. | Seed INSERT | `John` |
| `last_name` | VARCHAR(80) | N | – | Employee family name. | Seed INSERT | `Smith` |
| `email` | VARCHAR(255) | N | UNIQUE | Work email; unique so it can serve as a login/notification address. | Seed INSERT | `john.smith@bank.com` |
| `role` | VARCHAR(40) | N | CHECK `IN ('Analyst', 'Reviewer', 'Manager', 'Supervisor', 'Specialist')` | Job function that decides which workflow steps the person may perform. | Seed INSERT | `Analyst` |

### customer

**Purpose:** Bank customers who own accounts and raise complaints or service requests.  
**Group:** Reference / master · **Seed rows:** 10

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `customer_id` | VARCHAR(20) | N | **PK** | Stable business identifier for a customer (CUSnnn). | Seed INSERT | `CUS001` |
| `first_name` | VARCHAR(80) | N | – | Customer given name. PII. | Seed INSERT | `William` |
| `last_name` | VARCHAR(80) | N | – | Customer family name. PII. | Seed INSERT | `Johnson` |
| `email` | VARCHAR(255) | Y | – | Contact email. Optional because not every customer supplies one. PII. | Seed INSERT | `william@email.com` |
| `phone_number` | VARCHAR(30) | Y | – | Contact phone, stored as text to keep leading zeros/formatting. PII. | Seed INSERT | `4165551001` |
| `segment` | VARCHAR(40) | N | CHECK `IN ('Retail', 'Premier', 'Business')` | Customer tier; drives service levels and routing. | Seed INSERT | `Retail` |

### account

**Purpose:** A bank account owned by exactly one customer.  
**Group:** Reference / master · **Seed rows:** 10

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `account_id` | VARCHAR(20) | N | **PK** | Internal account identifier (ACCnnn). | Seed INSERT | `ACC001` |
| `customer_id` | VARCHAR(20) | N | **FK** → customer.customer_id | Owner of the account. | Seed INSERT | `CUS001` |
| `account_number` | VARCHAR(40) | N | UNIQUE | Customer-facing account number; must be unique across the bank. | Seed INSERT | `100000001` |
| `account_type` | VARCHAR(40) | N | – | Product type, e.g. Chequing, Savings, Business. | Seed INSERT | `Chequing` |
| `status` | VARCHAR(30) | N | CHECK `IN ('ACTIVE', 'INACTIVE', 'CLOSED', 'RESTRICTED')` | Lifecycle state of the account. | Seed INSERT | `ACTIVE` |
| `balance` | NUMERIC(15,2) | N | – | Current ledger balance in account currency (2 dp). Default `0`. | Seed INSERT | `2500.50` |
| `open_date` | DATE | N | – | Date the account was opened. | Seed INSERT | `2023-01-10` |

### complaint

**Purpose:** Central workflow record: one customer complaint from intake to closure.  
**Group:** Complaint workflow · **Seed rows:** 30

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `complaint_id` | VARCHAR(20) | N | **PK** | Business identifier for the complaint (CMPnnn). | Seed INSERT | `CMP001` |
| `customer_id` | VARCHAR(20) | N | **FK** → customer.customer_id | Customer who raised the complaint. | Seed INSERT | `CUS001` |
| `account_id` | VARCHAR(20) | Y | **FK** → account.account_id | Account the complaint is about. NULL for general or identity/fraud complaints that are not tied to one account (CMP023, CMP029, CMP030). | Seed INSERT | `ACC001` |
| `channel` | VARCHAR(30) | N | – | How the complaint arrived: Phone, Email, Branch, Web. | Seed INSERT | `Phone` |
| `category` | VARCHAR(80) | N | – | Complaint classification used for routing and analytics (Fee Dispute, Fraud Claim, ...). | Seed INSERT | `Fee Dispute` |
| `customer_narrative` | TEXT | N | – | The customer's own description, preserved verbatim for audit and later RAG/agent use. | Seed INSERT | `Unexpected overdraft fee` |
| `priority` | VARCHAR(20) | N | CHECK `IN ('Low', 'Medium', 'High', 'Critical')` | Urgency used for queueing and SLA. | Seed INSERT | `High` |
| `status` | VARCHAR(30) | N | CHECK `IN ('OPEN', 'IN_PROGRESS', 'UNDER_REVIEW', 'PENDING_APPROVAL', 'CHANGES_REQUESTED', 'ESCALATED', 'RESOLVED', 'CLOSED')` | Current workflow state. Must match the latest complaint_status_history.new_status. | Seed INSERT | `OPEN` |
| `created_at` | TIMESTAMP | N | – | When the complaint was received. | Seed INSERT | `2025-01-01 09:00:00` |
| `assigned_employee_id` | VARCHAR(20) | Y | **FK** → employee.employee_id | Analyst currently responsible. NULL while unassigned. | Seed INSERT | `EMP001` |

### complaint_status_history

**Purpose:** Append-only log of every complaint status transition.  
**Group:** Supporting history · **Seed rows:** 30

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `status_history_id` | BIGSERIAL | N | **PK** | Surrogate key generated by the database (seed omits it). | Generated (sequence) | `1` |
| `complaint_id` | VARCHAR(20) | N | **FK** → complaint.complaint_id | Complaint whose status changed. | Seed INSERT | `CMP001` |
| `old_status` | VARCHAR(30) | Y | – | Status before the change. NULL on the creation row. | Seed INSERT | `OPEN` |
| `new_status` | VARCHAR(30) | N | – | Status after the change. | Seed INSERT | `OPEN` |
| `changed_by` | VARCHAR(20) | N | **FK** → employee.employee_id | Employee who made the change. | Seed INSERT | `EMP001` |
| `comments` | TEXT | Y | – | Free-text reason for the change. | Seed INSERT | `Complaint created` |
| `status_timestamp` | TIMESTAMP | N | – | When the change happened. Defaults to load time because the seed does not supply it. Default `CURRENT_TIMESTAMP`. | DB default `CURRENT_TIMESTAMP` | `load-time timestamp` |

### transactions

**Purpose:** Posted debits and credits on an account; evidence for transaction complaints.  
**Group:** Supporting transaction · **Seed rows:** 10

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `transaction_id` | VARCHAR(20) | N | **PK** | Transaction identifier (TXNnnn). | Seed INSERT | `TXN001` |
| `account_id` | VARCHAR(20) | N | **FK** → account.account_id | Account the transaction posted to. | Seed INSERT | `ACC001` |
| `transaction_type` | VARCHAR(40) | N | CHECK `IN ('DEBIT', 'CREDIT')` | DEBIT reduces the balance, CREDIT increases it. | Seed INSERT | `DEBIT` |
| `amount` | NUMERIC(15,2) | N | CHECK `(amount >= 0)` | Absolute transaction amount (direction comes from transaction_type). | Seed INSERT | `35.00` |
| `transaction_date` | TIMESTAMP | N | – | When the transaction posted. | Seed INSERT | `2025-01-01 08:00:00` |
| `balance_before` | NUMERIC(15,2) | Y | – | Account balance immediately before posting. | Seed INSERT | `2535.50` |
| `balance_after` | NUMERIC(15,2) | Y | – | Account balance immediately after posting. | Seed INSERT | `2500.50` |
| `description` | VARCHAR(255) | Y | – | Narrative shown on the statement. | Seed INSERT | `ATM withdrawal` |

### fee

**Purpose:** Fees charged to an account; the main evidence for fee-dispute complaints.  
**Group:** Supporting transaction · **Seed rows:** 10

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `fee_id` | VARCHAR(20) | N | **PK** | Fee identifier (FEEnnn). | Seed INSERT | `FEE001` |
| `account_id` | VARCHAR(20) | N | **FK** → account.account_id | Account charged. | Seed INSERT | `ACC001` |
| `transaction_id` | VARCHAR(20) | Y | **FK** → transactions.transaction_id | Transaction that triggered the fee. NULL for periodic fees such as monthly maintenance. | Seed INSERT | `TXN001` |
| `fee_type` | VARCHAR(80) | N | – | Kind of fee: Overdraft, Maintenance, Wire, Business Service, Card Replacement. | Seed INSERT | `Overdraft` |
| `amount` | NUMERIC(15,2) | N | CHECK `(amount >= 0)` | Fee amount charged. | Seed INSERT | `35.00` |
| `fee_date` | TIMESTAMP | N | – | When the fee was charged. | Seed INSERT | `2025-01-01 08:01:00` |
| `reversed` | BOOLEAN | N | – | TRUE once the fee has been refunded/reversed. Default `false`. | Seed INSERT | `false` |

### service_request

**Purpose:** Non-complaint customer requests (address change, PIN reset, ...); context for complaints.  
**Group:** Supporting history · **Seed rows:** 10

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `request_id` | VARCHAR(20) | N | **PK** | Service request identifier (SRnnn). | Seed INSERT | `SR001` |
| `customer_id` | VARCHAR(20) | N | **FK** → customer.customer_id | Customer who made the request. | Seed INSERT | `CUS001` |
| `account_id` | VARCHAR(20) | Y | **FK** → account.account_id | Account the request concerns, if any. | Seed INSERT | `ACC001` |
| `request_type` | VARCHAR(100) | N | – | What the customer asked for. | Seed INSERT | `Address Change` |
| `status` | VARCHAR(30) | N | CHECK `IN ('OPEN', 'IN_PROGRESS', 'CLOSED')` | Request lifecycle state. | Seed INSERT | `CLOSED` |
| `created_date` | DATE | N | CHECK `chk_service_request_dates` | Date the request was opened. | Seed INSERT | `2025-01-01` |
| `closed_date` | DATE | Y | CHECK `chk_service_request_dates` | Date the request was closed. NULL while open. | Seed INSERT | `2025-01-02` |

**Table-level rules**

- `chk_service_request_dates`: `(closed_date IS NULL OR (closed_date >= created_date))`

### policy_document

**Purpose:** Bank policies that govern complaint handling; metadata for the later RAG corpus.  
**Group:** Reference / master · **Seed rows:** 10

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `policy_id` | VARCHAR(20) | N | **PK** | Stable policy identifier (POLnnn); used to link to the RAG document store. | Seed INSERT | `POL001` |
| `title` | VARCHAR(255) | N | – | Policy name. | Seed INSERT | `Complaint Resolution Policy` |
| `version` | VARCHAR(30) | N | – | Policy version label. | Seed INSERT | `1.0` |
| `effective_date` | DATE | N | – | Date the version took effect. | Seed INSERT | `2024-01-01` |
| `status` | VARCHAR(30) | N | CHECK `IN ('ACTIVE', 'SUPERSEDED', 'RETIRED', 'DRAFT')` | Whether the policy is in force. | Seed INSERT | `ACTIVE` |

### policy_section

**Purpose:** Searchable sections of a policy, cited by recommendations and agents.  
**Group:** Reference / master · **Seed rows:** 10

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `section_id` | VARCHAR(20) | N | **PK** | Section identifier (SECnnn). | Seed INSERT | `SEC001` |
| `policy_id` | VARCHAR(20) | N | **FK** → policy_document.policy_id | Policy the section belongs to. | Seed INSERT | `POL001` |
| `section_title` | VARCHAR(255) | N | – | Heading of the section. | Seed INSERT | `Complaint Intake` |
| `section_text` | TEXT | N | – | Section body text. | Seed INSERT | `All complaints must be recorded.` |

### investigation

**Purpose:** An analyst's investigation of a complaint.  
**Group:** Complaint workflow · **Seed rows:** 10

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `investigation_id` | VARCHAR(20) | N | **PK** | Investigation identifier (INVnnn). | Seed INSERT | `INV001` |
| `complaint_id` | VARCHAR(20) | N | **FK** → complaint.complaint_id | Complaint being investigated. | Seed INSERT | `CMP001` |
| `analyst_id` | VARCHAR(20) | N | **FK** → employee.employee_id | Analyst doing the investigation. | Seed INSERT | `EMP001` |
| `start_date` | DATE | N | CHECK `chk_investigation_dates` | Date work began. | Seed INSERT | `2025-01-02` |
| `end_date` | DATE | Y | CHECK `chk_investigation_dates` | Date work finished. NULL while in progress. | Seed INSERT | `2025-01-04` |
| `findings` | TEXT | Y | – | Summary of what the analyst found. | Seed INSERT | `Overdraft fee verified` |

**Table-level rules**

- `chk_investigation_dates`: `(end_date IS NULL OR (end_date >= start_date))`

### recommendation

**Purpose:** Proposed resolution produced by an investigation (human- or AI-generated).  
**Group:** Complaint workflow · **Seed rows:** 10

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `recommendation_id` | VARCHAR(20) | N | **PK** | Recommendation identifier (RECnnn). | Seed INSERT | `REC001` |
| `investigation_id` | VARCHAR(20) | N | **FK** → investigation.investigation_id | Investigation that produced it. | Seed INSERT | `INV001` |
| `recommendation_text` | TEXT | N | – | The proposed action. | Seed INSERT | `Reverse overdraft fee` |
| `confidence_score` | NUMERIC(5,2) | Y | CHECK `chk_confidence_score` | Confidence 0-100 in the recommendation; NULL if not scored. | Seed INSERT | `95.50` |

**Table-level rules**

- `chk_confidence_score`: `(confidence_score IS NULL OR ((confidence_score >= 0) AND (confidence_score <= 100)))`

### review_request

**Purpose:** Request for a reviewer to approve a recommendation (human-in-the-loop gate).  
**Group:** Complaint workflow · **Seed rows:** 10

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `review_request_id` | VARCHAR(20) | N | **PK** | Review request identifier (RRnnn). | Seed INSERT | `RR001` |
| `complaint_id` | VARCHAR(20) | N | **FK** → complaint.complaint_id | Complaint under review. Must match recommendation -> investigation -> complaint (checked in validation). | Seed INSERT | `CMP001` |
| `recommendation_id` | VARCHAR(20) | N | **FK** → recommendation.recommendation_id | Recommendation to be approved. | Seed INSERT | `REC001` |
| `reviewer_id` | VARCHAR(20) | N | **FK** → employee.employee_id | Employee asked to review. | Seed INSERT | `EMP003` |
| `status` | VARCHAR(30) | N | CHECK `IN ('PENDING', 'UNDER_REVIEW', 'APPROVED', 'REJECTED', 'CHANGES_REQUESTED', 'ESCALATED')` | State of the review request. | Seed INSERT | `PENDING` |

### review_decision

**Purpose:** The reviewer's decision on a review request. One-to-many so re-reviews are kept.  
**Group:** Complaint workflow · **Seed rows:** 10

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `decision_id` | VARCHAR(20) | N | **PK** | Decision identifier (DECnnn). | Seed INSERT | `DEC001` |
| `review_request_id` | VARCHAR(20) | N | **FK** → review_request.review_request_id | Review request being decided. | Seed INSERT | `RR001` |
| `decision` | VARCHAR(30) | N | CHECK `IN ('APPROVED', 'REJECTED', 'REQUEST_CHANGES', 'ESCALATED')` | Outcome of the review. | Seed INSERT | `APPROVED` |
| `decision_reason` | TEXT | N | – | Why the reviewer decided this; required for audit. | Seed INSERT | `Valid fee dispute` |
| `decision_at` | TIMESTAMP | N | – | When the decision was made. Defaults to load time because the seed does not supply it. Default `CURRENT_TIMESTAMP`. | DB default `CURRENT_TIMESTAMP` | `load-time timestamp` |

### customer_response

**Purpose:** Communications sent to the customer about a complaint.  
**Group:** Complaint workflow · **Seed rows:** 10

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `response_id` | VARCHAR(20) | N | **PK** | Response identifier (RESnnn). | Seed INSERT | `RES001` |
| `complaint_id` | VARCHAR(20) | N | **FK** → complaint.complaint_id | Complaint the message relates to. | Seed INSERT | `CMP001` |
| `response_text` | TEXT | N | – | Message sent to the customer. | Seed INSERT | `Your fee has been reversed.` |
| `sent_by` | VARCHAR(20) | N | **FK** → employee.employee_id | Employee who sent it. | Seed INSERT | `EMP003` |
| `sent_date` | DATE | N | – | Date it was sent. | Seed INSERT | `2025-01-05` |

### audit_log

**Purpose:** Who did what to which record; supports regulatory audit of the workflow.  
**Group:** Polymorphic audit · **Seed rows:** 10

| Column | Type | Null | Key / constraint | Purpose | Source | Example |
|---|---|---|---|---|---|---|
| `audit_id` | BIGSERIAL | N | **PK** | Surrogate key generated by the database (seed omits it). | Generated (sequence) | `1` |
| `entity_name` | VARCHAR(60) | N | – | Table/entity type acted on. Together with entity_id forms a logical (polymorphic) reference, so it is not a database FK; orphan check is in seed_validation.sql. | Seed INSERT | `COMPLAINT` |
| `entity_id` | VARCHAR(40) | N | – | Identifier of the record acted on, in the table named by entity_name. | Seed INSERT | `CMP001` |
| `action_type` | VARCHAR(40) | N | – | What was done. | Seed INSERT | `CREATE` |
| `performed_by` | VARCHAR(20) | Y | **FK** → employee.employee_id | Employee who acted. NULL allowed for system actions. | Seed INSERT | `EMP001` |
| `details` | TEXT | Y | – | Free-text description of the action. | Seed INSERT | `Complaint created` |
| `performed_at` | TIMESTAMP | N | – | When the action happened. Defaults to load time because the seed does not supply it. Default `CURRENT_TIMESTAMP`. | DB default `CURRENT_TIMESTAMP` | `load-time timestamp` |

## Cross-table rules not expressible as constraints

These rules are not enforced by the schema. They are verified by `seed_validation.sql` section 4 instead, and should be enforced in the API layer (Exercise 2.1.2 onward).

| Rule | Why it matters | Check |
|---|---|---|
| `complaint.status` equals the latest `complaint_status_history.new_status` | History is the source of truth for SLA and audit. | Section 4 |
| Every complaint has at least one status-history row | No complaint without an intake record. | Section 4 |
| `review_request.complaint_id` = recommendation → investigation → complaint | Prevents approving a recommendation against the wrong complaint. | Section 4 |
| `fee.transaction_id` is on the same account as the fee | Fee evidence must come from the disputed account. | Section 4 |
| `account.balance` = `balance_after` of the latest transaction | Ledger reconciliation. | Section 4 |
| Complaint / service request account belongs to the same customer | A complaint must not point at someone else's account. | Section 4 |
| Transaction balance_after = balance_before -/+ amount | Running balance must reconcile. | Section 4 |
| Status-history transitions use valid statuses | Old/new status values are not CHECK-constrained in this table. | Section 3 |
| Assignees and investigators have role Analyst; reviewers have role Reviewer | Segregation of duties. | Section 4 |
| `audit_log.entity_id` exists in the table named by `entity_name` | Polymorphic reference cannot be a database FK. | Section 2 |
| Service request `status = 'CLOSED'` if and only if `closed_date` is set | Lifecycle consistency. | Section 3 |

## Indexes

Primary keys and UNIQUE constraints create their own indexes. Additional indexes support the expected API, analytics and agent queries:

| Table | Index | Definition |
|---|---|---|
| account | `idx_account_customer` | `(customer_id)` |
| audit_log | `idx_audit_actor_time` | `(performed_by, performed_at)` |
| audit_log | `idx_audit_entity` | `(entity_name, entity_id)` |
| complaint | `idx_complaint_account` | `(account_id)` |
| complaint | `idx_complaint_assignee` | `(assigned_employee_id)` |
| complaint | `idx_complaint_created_at` | `(created_at)` |
| complaint | `idx_complaint_customer` | `(customer_id)` |
| complaint | `idx_complaint_priority` | `(priority)` |
| complaint | `idx_complaint_status` | `(status)` |
| complaint_status_history | `idx_status_history_complaint` | `(complaint_id, status_timestamp)` |
| customer_response | `idx_response_complaint` | `(complaint_id)` |
| fee | `idx_fee_account_date` | `(account_id, fee_date)` |
| investigation | `idx_investigation_complaint` | `(complaint_id)` |
| policy_section | `idx_policy_section_policy` | `(policy_id)` |
| recommendation | `idx_recommendation_investigation` | `(investigation_id)` |
| review_decision | `idx_review_decision_request` | `(review_request_id)` |
| review_request | `idx_review_request_complaint` | `(complaint_id)` |
| review_request | `idx_review_request_reviewer` | `(reviewer_id)` |
| service_request | `idx_service_request_customer` | `(customer_id)` |
| transactions | `idx_transaction_account_date` | `(account_id, transaction_date)` |

## Known limitations of the seed data

The supplied `seeddatacrs.sql` loads without errors and passes every integrity check, but it contains business-level inconsistencies. They are **reported, not fixed**, so the database stays identical to the shared source. Evidence is in `seed_validation.txt` section 7.

- **Review status vs decision disagree (7 rows).** RR001, RR004, RR007 and RR010 are `PENDING` but have an `APPROVED` decision; RR003 and RR006 are `PENDING` with `REQUEST_CHANGES`; RR009 is `UNDER_REVIEW` with `ESCALATED`. The decision row should drive the request status.
- **Refund promised but fee not reversed.** RES001 ("Your fee has been reversed"), RES005 and RES010 tell customers a fee was refunded, but every fee on those accounts has `reversed = FALSE`.
- **Overdraft fee on a positive balance.** FEE001 is an Overdraft fee on TXN001, which left ACC001 at 2,500.50.
- **CMP001 still `OPEN`** although INV001 ended on 2025-01-04 and the customer was told the fee was reversed.
- **Incomplete status history.** 11 complaints (e.g. CMP002, CMP005) have only one history row whose `old_status` is already set, so the creation (`NULL → OPEN`) step is missing.
- **Load-time timestamps.** The seed omits `status_timestamp`, `decision_at` and `performed_at`, so they default to the load time (2026) while complaints are dated 2025. Time-based SLA metrics on these columns are not meaningful until real timestamps are supplied.
- **Workflow coverage.** CMP011–CMP030 have intake and status data only, with no investigation, recommendation, review or response.
- **CSV inputs.** The brief refers to synthetic CSV files; the shared data was supplied as SQL INSERT statements (inside `database_schema.sql`, identical to `seeddatacrs.sql`), loaded as-is in dependency order.
- **Field names inferred.** Several seed INSERTs have no column list, so the column order in the CREATE TABLE statements must not change.

## How to reproduce

```bash
createdb complaints
psql -v ON_ERROR_STOP=1 -d complaints -f database_schema.sql   # creates tables + loads seed
psql -X -d complaints -f seed_validation.sql > seed_validation.txt 2>&1
```

`database_schema.sql` drops and recreates every table, so the sequence can be rerun on the same database.