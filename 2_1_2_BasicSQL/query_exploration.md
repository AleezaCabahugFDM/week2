# Query Exploration: Banking Complaint Database

Week 2 | Exercise 2.1.2 · Step 1

**Database:** the one built by `database_schema.sql` in Exercise 2.1.1 (PostgreSQL 16; also loaded in Supabase).
**Purpose:** before writing the queries in `basic_query_questions.md`, check what is in the database: row counts, data types, NULL patterns, and anything unexpected that would change the answers.

---

## 1. Row counts

| Table | Rows | Notes |
|---|---|---|
| employee | 10 | 4 Analysts, 3 Reviewers, 2 Managers, 1 Supervisor |
| customer | 10 | |
| account | 10 | One account per customer |
| **complaint** | **30** | Main table for every question |
| complaint_status_history | 30 | One row per complaint |
| transactions | 10 | |
| fee | 10 | |
| service_request | 10 | |
| policy_document | 10 | |
| policy_section | 10 | |
| investigation | 10 | Only for CMP001–CMP010 |
| recommendation | 10 | |
| review_request | 10 | |
| review_decision | 10 | |
| customer_response | 10 | |
| audit_log | 10 | |

## 2. Columns the questions depend on

| Question | Column(s) used | Type | What it means for the query |
|---|---|---|---|
| Q1, Q2, Q3, Q7 | `complaint.status` | `VARCHAR`, CHECK-constrained | Exact, case-sensitive values: `OPEN`, `IN_PROGRESS`, `UNDER_REVIEW`, `PENDING_APPROVAL`, `CHANGES_REQUESTED`, `ESCALATED`, `RESOLVED`, `CLOSED`. |
| Q2 | `complaint.priority` | `VARCHAR`, CHECK-constrained | `Low`, `Medium`, `High`, `Critical`. `'high'` matches nothing. Alphabetical sort is wrong (Critical, High, Low, Medium). |
| Q4 | `complaint.category` | `VARCHAR` | Free text, not constrained; 7 distinct values in the data. |
| Q5 | `complaint.customer_id` | `VARCHAR(20)` | A text ID (`'CUS001'`), compared with quotes. |
| Q6, Q8 | `complaint.created_at` | `TIMESTAMP` (no time zone) | Has a time of day, so a date range must cover the whole last day. |
| Q7 | *`date_closed`* | **does not exist** | See observation 1 below. |
| Q7 | `complaint_status_history.new_status`, `status_timestamp` | `VARCHAR`, `TIMESTAMP` | The only record of when a complaint was closed. |

## 3. Complaint table profile

| Field | Values (count) |
|---|---|
| status | OPEN 19 · UNDER_REVIEW 6 · IN_PROGRESS 4 · CLOSED 1 · RESOLVED 0 |
| priority | Medium 10 · High 9 · Low 8 · Critical 3 |
| category | Fee Dispute 7 · Customer Service 5 · Service Delay 5 · Transaction Error 5 · Fraud Claim 3 · Online Banking 3 · Card Issue 2 |
| channel | Web 9 · Email 8 · Phone 8 · Branch 5 |
| created_at range | 2025-01-01 09:00 → 2025-02-24 13:15 (January 10, February 20) |
| assigned_employee_id | EMP001 8 · EMP002 8 · EMP006 8 · EMP007 6 |
| complaints per customer | 2 to 4 each; CUS001, CUS003 and CUS007 have 4 |
| duplicate created_at values | none, so Q8's "ten most recent" has no ties at the cut-off |

## 4. NULL patterns

| Column | NULLs | Out of | Meaning |
|---|---|---|---|
| `complaint.account_id` | **3** | 30 | CMP023, CMP029, CMP030: general or identity-fraud complaints not tied to one account. By design. Q5 must still return them. |
| `complaint.assigned_employee_id` | 0 | 30 | Allowed to be NULL, but every complaint is assigned. |
| `complaint_status_history.old_status` | 19 | 30 | NULL means "this was the first status". |
| `fee.transaction_id` | 6 | 10 | Periodic fees not tied to a transaction. |
| `service_request.closed_date` | 6 | 10 | NULL means the request is still open; matches status exactly (6 OPEN, 4 CLOSED). |
| `investigation.end_date` | 8 | 10 | NULL means the investigation is still running. |
| `customer.email`, `phone_number` | 0 | 10 | Allowed to be NULL, but all filled in. |

## 5. Observations and unexpected data

1. **There is no `date_closed` column on `complaint`.** Q7 asks for closed complaints "where date_closed is missing". The schema records closure only as a status-history row (`new_status = 'CLOSED'` or `'RESOLVED'`). Q7 therefore treats that row's `status_timestamp` as the closed date. The schema was not changed, so the 2.1.1 contract still holds. (`service_request` does have a `closed_date`, but it belongs to a different entity.)
2. **Only one complaint is closed (CMP005) and none are RESOLVED.** 29 of 30 complaints are open, so Q1 returns almost the whole table. CMP005 has its closure history row, so Q7 returns zero, as the question expects.
3. **Status-history timestamps are load time, not 2025.** `status_timestamp` was defaulted when the setup script ran. CMP005's closure "date" is therefore real as a record but not as a date. It is fine for Q7 (present vs missing) but must not be used to measure how long complaints took to close.
4. **The data is old.** All complaints are from January–February 2025, so date ranges must be supplied explicitly (Q6); "the last N days from today" would return nothing.
5. **Workflow data covers only a third of complaints.** CMP011–CMP030 have no investigation, recommendation, review or response. It does not affect Q1–Q8, which use only `complaint` and its status history.
6. **Cross-table status disagreements exist** (e.g. RR001 is `PENDING` but its decision is `APPROVED`; CMP001 is `OPEN` although the customer was told the fee was reversed). These are seed-data issues documented in 2.1.1; the queries report the data as it is.

---

## Appendix: exploration SQL used

All plain SQL; runs in psql or the Supabase SQL Editor.

```sql
-- Row counts per table (repeat the UNION ALL line for each table)
SELECT 'complaint' AS table_name, COUNT(*) AS row_count FROM complaint
UNION ALL SELECT 'complaint_status_history', COUNT(*) FROM complaint_status_history;

-- Column types and nullability
SELECT table_name, column_name, data_type, is_nullable
FROM   information_schema.columns
WHERE  table_schema = 'public'
ORDER  BY table_name, ordinal_position;

-- Is there a closed-date column on complaint?  (returns only service_request.closed_date)
SELECT table_name, column_name
FROM   information_schema.columns
WHERE  table_schema = 'public' AND column_name ILIKE '%clos%';

-- Value distributions
SELECT status,   COUNT(*) AS n FROM complaint GROUP BY status   ORDER BY n DESC;
SELECT priority, COUNT(*) AS n FROM complaint GROUP BY priority ORDER BY n DESC;
SELECT category, COUNT(*) AS n FROM complaint GROUP BY category ORDER BY n DESC;
SELECT MIN(created_at) AS first_complaint, MAX(created_at) AS last_complaint FROM complaint;

-- Ties on created_at (matters for "ten most recent")
SELECT created_at, COUNT(*) AS n FROM complaint GROUP BY created_at HAVING COUNT(*) > 1;

-- NULL counts (COUNT(col) skips NULLs; COUNT(*) does not)
SELECT COUNT(*) - COUNT(account_id)           AS null_account_ids FROM complaint;
SELECT COUNT(*) - COUNT(assigned_employee_id) AS unassigned       FROM complaint;

-- Closure records for closed complaints
SELECT h.complaint_id, h.old_status, h.new_status, h.status_timestamp
FROM   complaint_status_history AS h
WHERE  h.new_status IN ('RESOLVED', 'CLOSED');

-- Status-history timestamps (all equal the load time)
SELECT MIN(status_timestamp), MAX(status_timestamp) FROM complaint_status_history;
```