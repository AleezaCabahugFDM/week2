# Advanced SQL Explanation

Week 2 | Exercise 2.3.1 · Step 4

**Files:** `advanced_queries.sql` (the queries), `advanced_query_results.csv` (the results).
**Source:** `complaint_analyst_view` from 2.2.1 (one row per complaint) and `complaint_status_history`.
**Same rules as 2.2.2:** "unresolved" = status is not `RESOLVED` or `CLOSED`; the as-of date is **2025-02-24** (the newest complaint).

| # | Question | Query | Grain (one row per…) | Rows |
|---|---|---|---|---|
| 1 | Use CASE for unresolved age buckets 0-7, 8-30 and 31+ days | Q1a (list), Q1b (counts) | unresolved complaint / bucket | 29 / 3 |
| 2 | Use a CTE to identify repeat complainants | Q2 | customer | 10 |
| 3 | Use ROW_NUMBER to select latest status per complaint | Q3 | complaint | 30 |
| 4 | Rank customers by complaint count | Q4 | customer | 10 |

---

## Q1. Age buckets with CASE

**Age** = as-of date − the date the complaint was opened, in whole days.

```sql
CASE
    WHEN age_days < 0              THEN 'Invalid: opened after as-of date'
    WHEN age_days BETWEEN 0 AND 7  THEN '0-7 days'
    WHEN age_days BETWEEN 8 AND 30 THEN '8-30 days'
    ELSE                                '31+ days'
END
```

**Boundaries:** each age lands in exactly one bucket, with no gaps and no overlaps.

| Age | Bucket | Tested with a real complaint |
|---|---|---|
| 0 | 0-7 | CMP030 (opened on the as-of date) |
| 7 | 0-7 | CMP023 |
| 8 | 8-30 | CMP022 |
| 30 | 8-30 | CMP010 |
| 31 | 31+ | CMP009 |
| −1 | **Invalid** | test value only (opened after the as-of date) |

The data happens to have a real complaint at every edge, so the boundaries are tested on real rows (V02–V06), not just on test values (V07). A negative age is flagged instead of being quietly put in a bucket (V08).

**Result (Q1b):**

| Bucket | Unresolved | of which High/Critical |
|---|---|---|
| 0-7 days | 8 | 3 |
| 8-30 days | 13 | 4 |
| 31+ days | 8 | 5 |
| **Total** | **29** | 12 |

All three buckets are always listed, so an empty bucket shows 0 instead of disappearing.

---

## Q2. Repeat complainants with a CTE

**Repeat complainant** = a customer with **2 or more** complaints, open or closed.

The query is built from named steps. Each one answers one business question:

| CTE | What it answers |
|---|---|
| `complaints_per_customer` | How many complaints has each customer made, and when? |
| `same_category_repeaters` | Did the customer complain about the **same category** more than once? |
| `escalated_customers` | Does the customer have an escalated complaint? |
| `repeat_complainants` | Put it together: one labelled row per customer. |

**Result:** **all 10 customers** are repeat complainants. Every customer in the data has 2–4 complaints.

That answer is correct but doesn't separate anyone, so Q2 adds two more columns:

| Column | Meaning | Customers |
|---|---|---|
| `has_same_category_repeat` | Complained about the same thing again | **7** (CUS001, 003, 005, 006, 007, 008, 009) |
| `has_escalated_complaint` | Has an open escalated complaint (same rule as 2.2.2) | **1** (CUS009, fraud) |

The rows are sorted so the most important customers come first: CUS009 (escalated, 3 fraud claims), then the same-category repeaters, then the rest.

**Is the rule really working?** Because all 10 real customers qualify, it is not obvious the query can say "no". Two test customers, held in memory and not inserted, prove it:
- **1 complaint** → **not** a repeat complainant (V12).
- **exactly 2 complaints** → **is** a repeat complainant (V13). This is the boundary.

---

## Q3. Latest status per complaint with ROW_NUMBER

A window function looks at a group of rows **without collapsing them** into one.

- **`PARTITION BY`** splits the rows into groups. The numbering restarts for each group.
- **`ORDER BY`** (inside `OVER`) sets the order within each group.

```sql
ROW_NUMBER() OVER (
    PARTITION BY complaint_id                              -- a separate count per complaint
    ORDER BY status_timestamp DESC, status_history_id DESC -- newest first
)
```

Row number 1 is the newest history row for each complaint. Then we keep only rows where it is `1`.

**Ties:** all 30 history rows have the **same** timestamp (the time the setup script ran). Ordering by timestamp alone would pick the "latest" row at random. `status_history_id` is unique and always increases, so it breaks the tie the same way on every run.

**Result:** 30 complaints, each with exactly one latest row (V14). The latest status matches `complaint.status` for all 30 (V15).

---

## Q4. Rank customers by complaint count

There is no `PARTITION BY` here, so all customers are ranked together, ordered by `total_complaints DESC`.

CUS001, CUS003 and CUS007 are **tied** at 4 complaints. Three functions handle the tie differently:

| Customer | Complaints | `RANK` | `DENSE_RANK` | `ROW_NUMBER` |
|---|---|---|---|---|
| CUS001 | 4 | 1 | 1 | 1 |
| CUS003 | 4 | 1 | 1 | 2 |
| CUS007 | 4 | 1 | 1 | 3 |
| CUS002 | 3 | **4** | **2** | 4 |
| CUS005 | 3 | 4 | 2 | 5 |
| … | | | | |
| CUS010 | 2 | 8 | 3 | 10 |

- **`RANK`:** ties share a rank, then the next rank skips (1, 1, 1, **4**). Use it for "how many are ahead of me?"
- **`DENSE_RANK`:** ties share a rank, with no skip (1, 1, 1, **2**). Use it for "which level am I in?"
- **`ROW_NUMBER`:** every row gets a unique number. Ties are broken by `customer_id`, so the order is **deterministic**, the same on every run (V16). Use it for a "top N" list.

`open_rank_in_segment` adds `PARTITION BY customer_segment`, so the ranking restarts in each segment (Retail, Premier, Business).

---

## Checks (all 16 PASS)

| Checks | What they prove |
|---|---|
| V01 | The buckets add up to all 29 unresolved complaints |
| V02–V06 | Real complaints at ages 0, 7, 8, 30 and 31 land in the right bucket |
| V07 | Test ages 0, 7, 8, 30, 31 and 365 land in the right bucket |
| V08 | A negative age is flagged as Invalid |
| V09 | Q2 has one row per customer (10) |
| V10–V11 | 10 repeat complainants; 7 repeat the same category |
| V12–V13 | 1 complaint is **not** a repeat; exactly 2 **is** |
| V14–V15 | One latest status per complaint, and it matches `complaint.status` |
| V16 | Ties share a rank, `RANK` skips to 4, `DENSE_RANK` goes to 2, and `ROW_NUMBER` gives 10 unique positions |

The test values are held only inside the query. Nothing is inserted into the database.

## Limitations

1. **Everyone is a repeat complainant** in this data (min 2 complaints per customer), so the 2+ rule alone can't tell customers apart. The same-category and escalation columns do.
2. **Ages use the as-of date.** Using today's date would make every complaint 600+ days old. In a live system, use today's date.
3. **Status history has one row per complaint** and identical timestamps, so Q3 can't show a real change over time. The query is built for many rows per complaint, and the tie-breaker keeps it correct.
4. **Tiny data set:** 30 complaints and 10 customers, so the buckets and ranks are examples, not trends.

## How to reproduce

```bash
psql -d complaints -f advanced_queries.sql     # Q1a, Q1b, Q2, Q3, Q4, then the V01–V16 check table
```

In PostgreSQL run `complaint_analyst_view.sql` (2.2.1) first, then highlight a query and press **Run**.