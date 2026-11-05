# Complaint Analysis Summary

Week 2 | Exercise 2.4.1 · made by `complaint_analysis.py`, do not edit by hand.

## Headlines

- **120 complaints** from **69 customers**. **86 (71.7%) are still open** and 34 (28.3%) are closed.
- **Highest-volume category: Mortgage Servicing** with 31 complaints (25.8%).
- **Closed cases took 10.1 days on average.**

## Definitions

Same rules as the SQL metrics in 2.2.2.

- **Open:** status is not `Closed` or `Resolved` (so Open, In Review and Escalated are open).
- **Closed:** status is `Closed` or `Resolved`.
- **Resolution days:** `resolved_date` − `created_date`, for closed complaints only.
- **Unknown:** no closed complaint to measure. Shown as 'unknown', never as 0.

## Load evidence

Rows read: 120 · valid: 120 · skipped: 0

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

## What this analysis does not show

- **No trends.** This is one snapshot, so it can't say if things are getting better or worse.
- **No causes.** The counts don't explain *why* customers complained.
- **Resolution time only covers closed cases.** The 86 open complaints are not included.
- Some categories have only a few closed cases, so their averages are not reliable.
- The data is synthetic training data.
