# Metric Definitions

Week 2 | Exercise 2.2.2 · Step 4

**Files:** `complaint_metrics.sql` (all metric queries M1–M7, checks V01–V16, summary S) and `complaint_metrics.csv` (the summary S, one row per metric value).
**Source:** `complaint_analyst_view` from 2.2.1, one row per complaint (30 complaints, 10 customers), plus `investigation` for closed dates.
**As-of date:** 2025-02-24, the newest complaint. It is used for backlog age so the numbers don't change with today's date.
**Calculation date:** the date the summary was run (`calculation_date` column in the CSV).

## Definitions

| Metric (CSV `metric_name`) | Numerator | Denominator / grain | Filter | Query |
|---|---|---|---|---|
| `complaint_count` | `COUNT(*)` of complaints | One row per complaint | None | M1–M4 |
| `distinct_customers` | `COUNT(DISTINCT customer_id)` | Customers, not complaints | None | M1–M4 |
| `backlog_count` | Complaints still open | One row per complaint | `status NOT IN ('RESOLVED','CLOSED')` | M1, M5 |
| `customers_with_open_complaint` | Distinct customers with at least one open complaint | Customers | Open only | M1 |
| `closed_count` | Complaints closed | One row per complaint | `status IN ('RESOLVED','CLOSED')` | M1, M6 |
| `backlog_avg_age_days` | Sum of (as-of date − opened date) for open complaints | Number of open complaints | Open only | M5 |
| `escalated_backlog_count` | Open complaints that were escalated, either by status `ESCALATED` **or** by a review decision `ESCALATED` | One row per complaint | Open only | M5b |
| `escalated_by_status_only` | Open complaints with status `ESCALATED` | One row per complaint | Open only | M5b |
| `avg_resolution_days` | Sum of (closed date − opened date) | Number of **measurable** closed complaints | Closed only, with an investigation end date | M6 |

**Closed date** = the latest `investigation.end_date` for the complaint. The complaint table has no closed date. The status-history timestamps are set when the data is loaded (not real 2025 dates), so they would give roughly 650 days and change on every reload.

**Resolution days** = closed date − `created_at` date, in whole calendar days.

## Unresolved cases

- Open, In Progress, Under Review, Pending Approval, Changes Requested and Escalated all count as **unresolved (backlog)**. Only `RESOLVED` and `CLOSED` count as closed.
- Unresolved cases are **left out** of resolution time, because they have no end yet. Including them would make resolution look faster than it is. CMP001 is a negative test: its investigation has ended but it is still OPEN, so it is excluded (V11).
- A category with no closed cases shows `closed_count` 0 and a **blank** `avg_resolution_days`. That means unknown, **not** zero days (V12).
- Closed complaints with no investigation end date can't be measured. M7 lists them so they don't disappear silently (V09). Right now there are none.

## Distinct counts

- Complaint counts add up across groups: categories sum to 30 (V02), statuses sum to 30 (V03), and months sum to 30 (V04).
- Distinct customer counts **do not** add up. One customer with complaints in three categories is counted once in each category. The per-category sum is 22, but there are only 10 customers (V07). Use `distinct_customers` with grouping `overall` for the true total.

## Checks

All 16 checks in `complaint_metrics.sql` (section V) return PASS on the 2.1.1 seed data.

| Check | What it proves |
|---|---|
| V01 | The view has every complaint (30 = 30) |
| V02–V04 | Category, status and month counts each sum to the total |
| V05 | Backlog + closed = total |
| V06–V07 | Distinct customers = 10, and per-group distinct counts are not additive |
| V08–V12 | Resolution uses closed cases only: measured + unmeasurable = closed, no negative durations, open CMP001 excluded, empty category is NULL not 0 |
| V13 | Known answer: CMP005 = 3 days (2025-01-15 → 2025-01-18) |
| V14–V16 | Escalated backlog = 1 (CMP009), never more than the backlog, and status alone would miss it |

## Caveats

- **Tiny closed sample.** Only 1 of 30 complaints is closed (CMP005), so `avg_resolution_days` = 3.0 rests on one case. It is not a reliable average.
- **Escalation is under-recorded in status.** CMP009 was escalated by a reviewer but its status is still UNDER_REVIEW. Using status alone gives 0 escalated (V16), which is why review decisions are also counted.
- **Only two months.** Complaints were opened in Jan–Feb 2025, which is too short to show a trend.
- **Backlog age depends on the as-of date.** Changing 2025-02-24 changes `backlog_avg_age_days`.
- **Seed-data inconsistencies** (2.1.1, section 5 of `seed_validation.txt`) can affect status-based metrics. For example, some review requests are PENDING even though they have a decision.

**Handover:** 2.3.1 reuses these definitions (open = not RESOLVED/CLOSED, as-of date 2025-02-24). 2.4.1 uses the same rules in Python.
