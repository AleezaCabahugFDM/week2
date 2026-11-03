# Query Exploration: Banking Complaint Database

Week 2 | Exercise 2.1.2 · Step 1

**Database:** the one built by `database_schema.sql` in Exercise 2.1.1 (PostgreSQL 16).
**Purpose:** before writing any business queries, check what is in the database: how many rows, what data types, where NULLs appear, and anything unexpected.

---

## 1. Row counts

| Table | Rows | Notes |
|---|---|---|
| employee | 10 | 4 Analysts, 3 Reviewers, 2 Managers, 1 Supervisor |
| customer | 10 | |
| account | 10 | One account per customer |
| **complaint** | **30** | Main table for this exercise |
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

## 2. Data types that affect how queries are written

| Column(s) | Type | What it means for queries |
|---|---|---|
| All IDs (`complaint_id`, `customer_id`, ...) | `VARCHAR` | Text, not numbers. Compare as `'CUS001'`, with quotes. |
| `complaint.status`, `priority`, `category`, `channel` | `VARCHAR` | Exact, case-sensitive matching: `'High'` works, `'high'` returns nothing. |
| `complaint.customer_narrative` | `TEXT` | Free text; search it with `ILIKE` (case-insensitive). |
| `complaint.created_at` | `TIMESTAMP` (no time zone) | Has a time of day, so date filters must account for it (see `query_notes.md`). |
| `fee.amount`, `account.balance` | `NUMERIC(15,2)` | Exact money values; safe to `SUM`. |
| `fee.reversed` | `BOOLEAN` | Filter with `= FALSE` / `= TRUE`. |
| `service_request.created_date`, `closed_date` | `DATE` | No time part; subtracting two dates gives whole days. |

## 3. Complaint table profile

| Field | Values (count) |
|---|---|
| status | OPEN 19 · UNDER_REVIEW 6 · IN_PROGRESS 4 · CLOSED 1 |
| priority | Medium 10 · High 9 · Low 8 · Critical 3 |
| category | Fee Dispute 7 · Service Delay 5 · Transaction Error 5 · Customer Service 5 · Online Banking 3 · Fraud Claim 3 · Card Issue 2 |
| channel | Web 9 · Phone 8 · Email 8 · Branch 5 |
| created_at range | 2025-01-01 09:00 → 2025-02-24 13:15 (January: 10, February: 20) |
| assigned_employee_id | EMP001 8 · EMP002 8 · EMP006 8 · EMP007 6 |
| complaints per customer | 2 to 4 each; CUS001, CUS003 and CUS007 have 4 |

## 4. NULL patterns

| Column | NULLs | Out of | Meaning |
|---|---|---|---|
| `complaint.account_id` | **3** | 30 | CMP023, CMP029, CMP030: general or identity-fraud complaints with no single account. **This is by design.** |
| `complaint.assigned_employee_id` | 0 | 30 | Allowed to be NULL, but every complaint is assigned. |
| `complaint_status_history.old_status` | 19 | 30 | NULL means "this was the first status". |
| `fee.transaction_id` | 6 | 10 | Monthly or wire fees not tied to a transaction. |
| `service_request.closed_date` | 6 | 10 | NULL means the request is still open. Matches status exactly (6 OPEN, 4 CLOSED). |
| `investigation.end_date` | 8 | 10 | NULL means the investigation is still running. |
| `customer.email`, `phone_number` | 0 | 10 | Allowed to be NULL, but all filled in. |

## 5. Observations and unexpected data

1. **No RESOLVED complaints, and only one CLOSED (CMP005).** 29 of 30 complaints are still open. Any "open cases" report will include almost everything.
2. **The data is old.** All complaints are from January–February 2025. A "last 7 days" query based on today's date returns **nothing**, so the date queries use an `as_of_date` parameter (default `2025-02-24`, the newest complaint).
3. **Status-history timestamps are not real.** `status_timestamp` is the same for all 30 rows: the moment the setup script ran, not 2025. **Do not use it for "recent activity";** use `complaint.created_at` instead.
4. **Only a third of complaints have workflow data.** CMP011–CMP030 have no investigation, recommendation, review or response.
5. **Statuses disagree between tables.** For example, review request RR001 is `PENDING` but its decision DEC001 is `APPROVED`. CMP001 is still `OPEN` even though the customer was told "Your fee has been reversed", and FEE001 is not marked reversed. These are seed-data issues; the queries report the data as it is.
6. **No fees are reversed.** `fee.reversed` is `FALSE` for all 10 fees, so "unreversed fees" (Q22) returns every fee.
7. **Every narrative is unique and short** (one line each), so keyword search works but returns few matches.

---

## Appendix: exploration SQL used

```sql
-- Row counts per table
SELECT 'complaint' AS table_name, COUNT(*) FROM complaint
UNION ALL SELECT 'customer', COUNT(*) FROM customer;          -- ...repeat for each table

-- Column types and nullability
SELECT table_name, column_name, data_type, is_nullable
FROM   information_schema.columns
WHERE  table_schema = 'public'
ORDER  BY table_name, ordinal_position;

-- Value distributions
SELECT status,   COUNT(*) FROM complaint GROUP BY status;
SELECT priority, COUNT(*) FROM complaint GROUP BY priority;
SELECT category, COUNT(*) FROM complaint GROUP BY category;
SELECT MIN(created_at), MAX(created_at) FROM complaint;

-- NULL counts (COUNT(col) skips NULLs; COUNT(*) does not)
SELECT COUNT(*) - COUNT(account_id) AS null_account_ids FROM complaint;
SELECT COUNT(*) - COUNT(closed_date) AS open_requests  FROM service_request;

-- Check the status-history timestamps
SELECT MIN(status_timestamp), MAX(status_timestamp) FROM complaint_status_history;
```