# Metric Definitions

Week 2 | Exercise 2.2.2 · Step 4

**Files:** `complaint_metrics.sql` (metric queries M1–M7, checks V01–V06, summary S) and `complaint_metrics.csv` (the summary S, one row per metric value).
**Source:** `complaint_analyst_view` from 2.2.1, one row per complaint (30 complaints, 10 customers), plus `investigation` for closed dates and `review_request` / `review_decision` for escalations.
**As-of date:** 2025-02-24, the newest complaint. It is used for backlog age so the numbers don't change with today's date.
**Calculation date:** the date the summary was run (`calculation_date` column in the CSV).

## Definitions

| Metric (CSV `metric_name`) | What is counted | Grain | Filter | Query |
|---|---|---|---|---|
| `complaint_count` | `COUNT(*)` of complaints | One row per complaint | None | M1–M4 |
| `distinct_customers` | `COUNT(DISTINCT customer_id)` | Customers, not complaints | None | M1–M4 |
| `backlog_count` | Complaints still open | One row per complaint | `is_open = true` (status not RESOLVED/CLOSED) | M1, M5 |
| `customers_with_open_complaint` | Distinct customers with at least one open complaint | Customers | Open only | M1 |
| `closed_count` | Complaints closed | One row per complaint | `is_open = false` | M1, M7 |
| `backlog_avg_age_days` | Average of (as-of date − opened date) | Open complaints | Open only | M5 |
| `escalated_backlog_count` | Open complaints with status `ESCALATED` **or** a review decision `ESCALATED` | One row per complaint | Open only | M6 |
| `escalated_by_status_only` | Open complaints with status `ESCALATED` | One row per complaint | Open only | V04 |
| `avg_resolution_days` | Average of (investigation end date − opened date) | Closed complaints with an end date | Closed only | M7 |

**Closed date** = `investigation.end_date`. The complaint table has no closed date. The status-history timestamps are set when the data is loaded (not real 2025 dates), so they can't be used.

**Resolution days** = closed date − `created_at` date, in whole days.

## Unresolved cases

- Open, In Progress, Under Review, Pending Approval, Changes Requested and Escalated all count as **unresolved (backlog)**. Only `RESOLVED` and `CLOSED` count as closed.
- Unresolved cases are **left out** of resolution time, because they have not finished. CMP001 is a good test: its investigation has an end date but it is still OPEN, so it is not counted (V05).
- A category with no closed cases shows `closed_count` 0 and a **blank** `avg_resolution_days`. Blank means unknown, **not** zero days.

## Distinct counts

- Complaint counts add up across groups: the categories, statuses and months each sum to 30.
- Distinct customer counts **do not** add up. A customer with complaints in three categories is counted once in each category. The per-category numbers sum to 22, but there are only 10 customers (V03). Use `distinct_customers` with grouping `overall` for the real total.

## Checks

All 6 checks at the end of `complaint_metrics.sql` give the expected answer on the 2.1.1 seed data.

| Check | What it shows | Expected |
|---|---|---|
| V01 | The view has every complaint | 30 |
| V02 | Backlog + closed = total | 29 + 1 = 30 |
| V03 | Distinct customers overall | 10 |
| V04 | Escalated by status alone | 0 (why review decisions are also used) |
| V05 | Open CMP001 is not in the resolution numbers | 0 |
| V06 | CMP005 resolution days (2025-01-15 → 2025-01-18) | 3 |

## Caveats

- **Tiny closed sample.** Only 1 of 30 complaints is closed (CMP005), so `avg_resolution_days` = 3.0 rests on one case.
- **Escalation is under-recorded in status.** CMP009 was escalated by a reviewer but its status is still UNDER_REVIEW. Using status alone gives 0 escalated (V04), which is why review decisions are also checked.
- **Only two months.** Complaints were opened in Jan–Feb 2025, which is too short to show a trend.
- **Backlog age depends on the as-of date.** Changing 2025-02-24 changes `backlog_avg_age_days`.
- **One investigation per complaint.** The resolution queries join `investigation` directly. If a complaint ever had two investigations, it would be counted twice.
- **Seed-data inconsistencies** (2.1.1, section 5 of `seed_validation.txt`) can affect status-based metrics.

**Handover:** 2.3.1 reuses these definitions (open = not RESOLVED/CLOSED, as-of date 2025-02-24). 2.4.1 uses the same rules in Python.
