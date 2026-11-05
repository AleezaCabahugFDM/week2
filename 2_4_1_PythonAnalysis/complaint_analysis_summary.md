# Complaint Analysis Summary

Week 2 | Exercise 2.4.1 · made by `complaint_analysis.py`, do not edit by hand.

**Input:** `complaints.csv` · **Rows read:** 120 · **Rows analysed:** 120 · **Rows skipped:** 0
**Complaints opened between:** 2026-01-02 and 2026-08-29

## Headlines

- **120 complaints** from **69 customers**. **86 (71.7%) are still open** and 34 (28.3%) are closed.
- **Highest-volume category: Mortgage Servicing** with 31 complaints (25.8% of all complaints).
- **Closed cases took 10.1 days on average**, based on 34 closed complaints.

## Definitions

Same rules as the SQL metrics in Exercise 2.2.2.

| Term | Meaning |
|---|---|
| Open | Status is not `Closed` or `Resolved` (Open, In Review and Escalated are all open). |
| Closed | Status is `Closed` or `Resolved`. |
| Percentage | Count ÷ complaints analysed × 100, to 1 decimal place. |
| Resolution days | `resolved_date` − `created_date` in days, for **closed complaints only**. |
| Unknown | There is no closed complaint to measure. Shown as 'unknown', **never as 0**. |

## Load evidence

Columns found: `complaint_id, customer_id, account_id, category, status, created_date, resolved_date, channel, priority` (`date_opened` and `date_closed` are read as `created_date` and `resolved_date`).

| Column | Missing values |
|---|---:|
| complaint_id | 0 |
| customer_id | 0 |
| account_id | 39 |
| category | 0 |
| status | 0 |
| created_date | 0 |
| resolved_date | 86 |
| channel | 0 |
| priority | 0 |

Missing `resolved_date` is expected for open complaints. Missing `account_id` is allowed.

No rows were skipped and there were no warnings.

## Complaints by status

| Status | Complaints | % |
|---|---:|---:|
| Closed | 34 | 28.3 |
| In Review | 32 | 26.7 |
| Escalated | 30 | 25.0 |
| Open | 24 | 20.0 |

## Complaints by category

| Category | Complaints | % |
|---|---:|---:|
| Mortgage Servicing | 31 | 25.8 |
| Card or Transaction Dispute | 25 | 20.8 |
| Service Quality | 21 | 17.5 |
| Digital Banking | 19 | 15.8 |
| Fees | 15 | 12.5 |
| Account Access | 9 | 7.5 |

## Closed-case resolution by category

| Category | Closed | Avg days |
|---|---:|---:|
| Account Access | 5 | 16.2 |
| Card or Transaction Dispute | 4 | 11.2 |
| Digital Banking | 4 | 8.2 |
| Fees | 6 | 10.3 |
| Mortgage Servicing | 9 | 9.4 |
| Service Quality | 6 | 6.2 |
| **All** | 34 | 10.1 |

## Observations

1. Mortgage Servicing is the largest category at 25.8% of complaints.
2. Most complaints are still open (86 of 120).
3. Among closed cases, Account Access took longest on average (16.2 days) and Service Quality was quickest (6.2 days).

## What this analysis does not show

- **No trends.** This is one snapshot, so it says nothing about whether things are getting better or worse.
- **No causes.** The counts do not explain *why* customers complained.
- **Resolution time only covers closed cases.** The 86 open complaints are not included.
- Some categories have only a few closed cases, so their averages are not reliable.
- The data is synthetic training data.
