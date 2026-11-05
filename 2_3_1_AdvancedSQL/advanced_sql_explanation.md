# Advanced SQL Explanation

Week 2 | Exercise 2.3.1 · Step 4

**Files:** `advanced_queries.sql` (the queries), `advanced_query_results.csv` (the check results).
**Source:** `complaint_analyst_view` from 2.2.1 (one row per complaint) and `complaint_status_history`.
**Same rules as 2.2.2:** "unresolved" = status is not `RESOLVED` or `CLOSED` (`is_open = true`); the as-of date is **2025-02-24** (the newest complaint).

| # | Question | Query | One row per… | Rows |
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
    WHEN age <= 7  THEN '0-7 days'
    WHEN age <= 30 THEN '8-30 days'
    ELSE '31+ days'
END
```

`CASE` stops at the first `WHEN` that is true, so an age of 8 skips the first line and lands in `8-30 days`. Every age lands in exactly one bucket.

| Age | Bucket | Real complaint | Check |
|---|---|---|---|
| 7 | 0-7 | CMP023 | V02 |
| 8 | 8-30 | CMP022 | V03 |
| 30 | 8-30 | CMP010 | V04 |
| 31 | 31+ | CMP009 | V05 |

**Result (Q1b):**

| Bucket | Unresolved | of which High/Critical |
|---|---|---|
| 0-7 days | 8 | 3 |
| 8-30 days | 13 | 4 |
| 31+ days | 8 | 5 |
| **Total** | **29** (V01) | 12 |

---

## Q2. Repeat complainants with a CTE

**Repeat complainant** = a customer with **2 or more** complaints, open or closed.

```sql
WITH customer_counts AS (
    SELECT customer_id, COUNT(*) AS total_complaints
    FROM complaint_analyst_view
    GROUP BY customer_id
)
SELECT customer_id, total_complaints
FROM customer_counts
WHERE total_complaints >= 2;
```

The CTE counts complaints per customer first, then the main query keeps the customers with 2 or more.

**Result:** **all 10 customers** are repeat complainants (V06). Every customer in the data has 2–4 complaints.

---

## Q3. Latest status per complaint with ROW_NUMBER

```sql
ROW_NUMBER() OVER (
    PARTITION BY complaint_id                               -- start counting again for each complaint
    ORDER BY status_timestamp DESC, status_history_id DESC  -- newest first
)
```

Row number 1 is the newest history row for each complaint, so the query keeps `row_num = 1`.

**Ties:** all 30 history rows have the **same** timestamp (the time the data was loaded). `status_history_id` is added to the `ORDER BY` so the same row is picked every time.

**Result:** 30 complaints, each with one latest status (V07).

---

## Q4. Rank customers by complaint count

All customers are ranked together, most complaints first. CUS001, CUS003 and CUS007 are **tied** at 4 complaints (V08):

| Customer | Complaints | `RANK` | `DENSE_RANK` | `ROW_NUMBER` |
|---|---|---|---|---|
| CUS001 | 4 | 1 | 1 | 1 |
| CUS003 | 4 | 1 | 1 | 2 |
| CUS007 | 4 | 1 | 1 | 3 |
| CUS002 | 3 | **4** | **2** | 4 |
| CUS005 | 3 | 4 | 2 | 5 |
| … | | | | |
| CUS010 | 2 | 8 | 3 | 10 |

- **`RANK`:** ties share a rank, then the next rank skips (1, 1, 1, **4**).
- **`DENSE_RANK`:** ties share a rank, with no skip (1, 1, 1, **2**).
- **`ROW_NUMBER`:** every row gets its own number. Ties are broken by `customer_id`, so the order is the same every time.

---

## Checks (all 8 PASS)

| Check | What it shows | Expected |
|---|---|---|
| V01 | Unresolved complaints (the buckets add up to this) | 29 |
| V02–V05 | Real complaints at the bucket edges have ages 7, 8, 30 and 31 | 7, 8, 30, 31 |
| V06 | Customers who have complained | 10 |
| V07 | Complaints with status history (rows Q3 returns) | 30 |
| V08 | Customers tied for most complaints | 3 |

## Limitations

1. **Everyone is a repeat complainant** in this data (min 2 complaints per customer), so the 2+ rule can't tell customers apart.
2. **Ages use the as-of date.** Using today's date would make every complaint 600+ days old. A live system would use today's date.
3. **Status history has one row per complaint** with identical timestamps, so Q3 can't show a real change over time. The query still works when there are many rows per complaint.
4. **Tiny data set:** 30 complaints and 10 customers, so the buckets and ranks are examples, not trends.

## How to run

```bash
psql -d complaints -f advanced_queries.sql
```

Run `complaint_analyst_view.sql` (2.2.1) first so the view exists.
