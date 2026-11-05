# Join Validation

Week 2 | Exercise 2.2.1

**Files:** `join_queries.sql` (J1–J3) and `complaint_analyst_view.sql` (question 4).

## Join rules

| Join | Type | Why |
|---|---|---|
| complaint → customer | `JOIN` (inner) | Every complaint has a customer, so none are lost. |
| complaint → account | `LEFT JOIN` | 3 complaints (CMP023, CMP029, CMP030) have no account. An inner join would drop them. |

Each complaint has one customer and at most one account, so the joins never repeat a complaint. The result is **one row per complaint**.

## J3: complaint count before and after the joins

| Step | Query | Expected | Actual | Result |
|---|---|---|---|---|
| 1 | `complaint` only | 30 | 30 | PASS |
| 2 | + `JOIN customer` | 30 | 30 | PASS |
| 3 | + `LEFT JOIN account` | 30 | 30 | PASS |
| 4 | + `JOIN account` instead (the wrong join) | 27 | 27 | PASS (shows the problem) |

Steps 1–3 keep all 30 complaints, so nothing is lost or repeated. Step 4 shows that an inner join to `account` silently drops the 3 complaints with no account.

## complaint_analyst_view checks

| Check | Expected | Actual | Result |
|---|---|---|---|
| C01 View rows | 30 | 30 | PASS |
| C02 Distinct complaints (no duplicates) | 30 | 30 | PASS |
| C03 Complaints with no account are kept | 3 | 3 | PASS |
| C04 Open complaints | 29 | 29 | PASS |

The view leaves out customer names, email, phone, account number and balance.

## How to run

```bash
psql -d complaints -f join_queries.sql
psql -d complaints -f complaint_analyst_view.sql
```
