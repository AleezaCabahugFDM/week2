# Hybrid Flow Designs

Week 2 | Exercise 2.3.2 · Step 2

**Inputs:** `sql_rag_decision_matrix.csv` (cases 3, H2, H3, H4, H5), the schema from 2.1.1, `complaint_analyst_view` from 2.2.1, and the metric rules from 2.2.2 ("open" means status is not `RESOLVED` or `CLOSED`).

The question set has only one hybrid question (Q3). The other four flows use realistic hybrid cases added to the matrix (`source = added_for_step2`). H5 is the safe version of Q5.

## Pattern used by every flow

| Stage | Who does it | What it returns | Rule |
|---|---|---|---|
| 0. Validate input | Code | Checked IDs, or a clarifying question | IDs must match `^CUS\d{3}$` / `^CMP\d{3}$` and exist. Otherwise stop. |
| 1. Structured query | Parameterised SQL (read-only role) | Rows with IDs | All numbers, dates and counts come from here. |
| 2. Document retrieval | Policy retrieval (`policy_section` joined to `policy_document`, `status = 'ACTIVE'` only) | Section IDs + text + policy version | No section above the threshold → "no policy found". Never guess. |
| 3. Synthesis | LLM | Answer that cites `complaint_id`, `fee_id`, `section_id` | Uses only stage 1–2 evidence. Never recalculates numbers. |
| 4. Approval | Named human | Decision written to `review_decision` / `audit_log` | Required before any state change or customer-facing message. |

Until the Week 4 vector service exists, stage 2 can run as the keyword SQL shown below (the policy text is short). The flow contract stays the same either way.

---

## Flow 1 — Customer history and fee policy (Q3)

**Question:** "Show customer history and explain the fee policy." Example: `CUS001`.

**Stage 0 — Validate.** The question names no customer, so the assistant asks for an ID and runs nothing. With `CUS001`, it confirms the customer exists.

**Stage 1 — Structured query.**

```sql
-- 1a. Complaint history
SELECT complaint_id, created_at::date AS opened, category, priority, status, is_open
FROM   complaint_analyst_view
WHERE  customer_id = :customer_id
ORDER  BY created_at;

-- 1b. Fees on the customer's accounts
SELECT f.fee_id, f.account_id, f.fee_type, f.amount, f.fee_date, f.reversed
FROM   fee AS f
JOIN   account AS a ON a.account_id = f.account_id
WHERE  a.customer_id = :customer_id
ORDER  BY f.fee_date;
```

*Evidence returned (verified):* four complaints for CUS001, all open: CMP001 Fee Dispute, CMP011 Service Delay, CMP012 Fee Dispute (UNDER_REVIEW) and CMP013 Customer Service. There is one fee row: FEE001 Overdraft 35.00, `reversed = FALSE`.

**Stage 2 — Document retrieval.** The query is "fee policy" plus the fee types found in 1b (`Overdraft`).

```sql
SELECT ps.section_id, pd.policy_id, pd.title, pd.version, ps.section_title, ps.section_text
FROM   policy_section  AS ps
JOIN   policy_document AS pd ON pd.policy_id = ps.policy_id
WHERE  pd.status = 'ACTIVE'
  AND  (pd.title ILIKE '%fee%' OR pd.title ILIKE '%refund%' OR ps.section_text ILIKE '%fee%');
```

*Evidence returned:* SEC002 (POL002 Fee Reversal Policy v1.1, "Fees reviewed within 5 days") and SEC009 (POL009 Refund Policy v1.3, "Manager approval required").

**Stage 3 — Synthesis.** A short history table taken directly from 1a, a fee list taken from 1b, and a plain explanation of the fee policy with each sentence citing SEC002 or SEC009. The model says that the policy does not list fee amounts or eligibility criteria. It does not fill that gap.

**Stage 4 — Approval.** None for an internal, read-only view. If the explanation will be sent to the customer, a Reviewer approves it before it is written to `customer_response`.

---

## Flow 2 — Fee reversal eligibility for CMP001 (H2)

**Stage 0 — Validate.** `CMP001` exists. Its fee is linked through `account_id` and `transaction_id`.

**Stage 1 — Structured query.**

```sql
SELECT c.complaint_id, c.status, c.created_at,
       f.fee_id, f.fee_type, f.amount, f.fee_date, f.reversed,
       t.transaction_id, t.amount AS txn_amount, t.description,
       rr.status  AS review_status,
       rd.decision, rd.decision_reason,
       r.response_text, r.sent_date
FROM   complaint AS c
JOIN   fee AS f               ON f.account_id = c.account_id
LEFT   JOIN transactions AS t ON t.transaction_id = f.transaction_id
LEFT   JOIN review_request AS rr  ON rr.complaint_id = c.complaint_id
LEFT   JOIN review_decision AS rd ON rd.review_request_id = rr.review_request_id
LEFT   JOIN customer_response AS r ON r.complaint_id = c.complaint_id
WHERE  c.complaint_id = :complaint_id
  AND  f.fee_type = 'Overdraft';
```

*Evidence returned:* FEE001 (35.00, `reversed = FALSE`), TXN001, RR001 `PENDING` with DEC001 `APPROVED` ("Valid fee dispute"), and RES001 "Your fee has been reversed." sent 2025-01-05.

**Stage 2 — Document retrieval.** SEC002 (fees reviewed within 5 days) and SEC009 (manager approval required for refunds).

**Stage 3 — Synthesis.** States the facts and the applicable sections. It **flags the conflict**: the customer was told the fee was reversed, but `fee.reversed` is still FALSE and the review request is still `PENDING` even though a decision exists. It does not decide which record is correct.

**Stage 4 — Approval.** A Manager approves the reversal (SEC009). Only then can the allowlisted `reverse_fee(fee_id, approver_id)` tool run. That tool writes `fee.reversed = TRUE` and an `audit_log` row with `action_type = 'APPROVE'`.

---

## Flow 3 — Response SLA check for CMP006 (H3)

**Stage 1 — Structured query.** The business-day count happens in SQL, not in the model.

```sql
WITH first_resp AS (
    SELECT c.complaint_id,
           c.created_at::date  AS opened_date,
           MIN(r.sent_date)    AS first_response_date
    FROM   complaint AS c
    LEFT   JOIN customer_response AS r ON r.complaint_id = c.complaint_id
    WHERE  c.complaint_id = :complaint_id
    GROUP  BY c.complaint_id, c.created_at
)
SELECT f.*,
       CASE WHEN f.first_response_date IS NULL THEN NULL   -- no response yet: unknown, not 0
            ELSE (SELECT COUNT(*)
                  FROM   generate_series(f.opened_date + 1, f.first_response_date,
                                         INTERVAL '1 day') AS g(d)
                  WHERE  EXTRACT(ISODOW FROM g.d) < 6)      -- Mon–Fri only
       END AS business_days_to_respond
FROM   first_resp AS f;
```

*Evidence returned (verified):* opened 2025-01-18 (a Saturday), first response 2025-01-20 (a Monday), so `business_days_to_respond = 1`.

*Boundary (verified):* CMP011 has no response, and the query returns `first_response_date = NULL` and `business_days_to_respond = NULL`, not 0. Complaints CMP011–CMP030 (20 of 30) have no `customer_response` row at all, so their SLA status is "no response recorded" and needs follow-up. It is not a pass.

**Stage 2 — Document retrieval.** SEC004 (POL004 Customer Service Policy, "Respond within 2 business days").

**Stage 3 — Synthesis.** "CMP006 was answered in 1 business day, within the 2-day SLA (SEC004)." It says that bank holidays are not counted.

**Stage 4 — Approval.** None, because this is read-only. If a breach is found and reported outside the team, a Supervisor signs it off.

---

## Flow 4 — Fraud complaints missing escalation (H4)

**Stage 1 — Structured query.** This finds candidates only.

```sql
SELECT v.complaint_id, v.category, v.priority, v.status, v.customer_narrative,
       EXISTS (SELECT 1 FROM complaint_status_history h
               WHERE  h.complaint_id = v.complaint_id
                 AND  h.new_status = 'ESCALATED')               AS escalated_in_history,
       EXISTS (SELECT 1 FROM review_request rr
               JOIN   review_decision rd ON rd.review_request_id = rr.review_request_id
               WHERE  rr.complaint_id = v.complaint_id
                 AND  rd.decision = 'ESCALATED')                 AS escalated_by_reviewer
FROM   complaint_analyst_view AS v
WHERE  v.is_open
  AND  (v.category = 'Fraud Claim'
        OR v.customer_narrative ILIKE ANY (ARRAY['%fraud%', '%unauthori%']));
```

*Evidence returned (verified):* three open candidates.

| complaint_id | priority | status | narrative | escalated_in_history | escalated_by_reviewer |
|---|---|---|---|---|---|
| CMP009 | Critical | UNDER_REVIEW | Unauthorized transfer | f | **t** (DEC009) |
| CMP028 | Critical | UNDER_REVIEW | Suspicious transaction detected | f | f |
| CMP029 | Critical | OPEN | Potential identity theft concern | f | f |

CMP009 is not a gap. **CMP028 and CMP029 are gaps:** they are Critical fraud claims from the same customer as CMP009 (CUS009) with no escalation recorded. CMP029 also has no `account_id`.

**Stage 2 — Document retrieval.** SEC003 ("Escalate suspected fraud") and SEC007 (AML monitoring).

**Stage 3 — Synthesis.** Lists candidates where both flags are FALSE, with the reason each one matched (category or keyword). Narrative text is quoted as data. Any instruction-like text inside a narrative is ignored.

**Stage 4 — Approval.** An Analyst or Supervisor confirms each case before the allowlisted `escalate_complaint(complaint_id, employee_id, reason)` tool runs. That tool writes `complaint_status_history` and `audit_log` (`ESCALATE`). The assistant never escalates on a keyword match alone.

---

## Flow 5 — Review pack for high-risk CMP009 (H5, the safe form of Q5)

**Stage 1 — Structured query.**

```sql
SELECT v.complaint_id, v.category, v.priority, v.status, v.customer_segment,
       a.account_id, a.status AS account_status,
       i.investigation_id, i.start_date, i.end_date, i.findings,
       rec.recommendation_id, rec.recommendation_text, rec.confidence_score,
       rr.review_request_id, rr.reviewer_id, rr.status AS review_status,
       rd.decision, rd.decision_reason
FROM   complaint_analyst_view AS v
LEFT   JOIN account        AS a   ON a.account_id = v.account_id
LEFT   JOIN investigation  AS i   ON i.complaint_id = v.complaint_id
LEFT   JOIN recommendation AS rec ON rec.investigation_id = i.investigation_id
LEFT   JOIN review_request AS rr  ON rr.recommendation_id = rec.recommendation_id
LEFT   JOIN review_decision AS rd ON rd.review_request_id = rr.review_request_id
WHERE  v.complaint_id = :complaint_id;

-- Recent transactions on the account (last 30 days before the complaint)
SELECT t.transaction_id, t.transaction_type, t.amount, t.transaction_date, t.description
FROM   transactions AS t
JOIN   complaint    AS c ON c.account_id = t.account_id
WHERE  c.complaint_id = :complaint_id
  AND  t.transaction_date >= c.created_at - INTERVAL '30 days'
ORDER  BY t.transaction_date;
```

*Evidence returned (verified):* CMP009 is a Fraud Claim, Critical, `UNDER_REVIEW`, on a Business customer's account ACC009, which is still `ACTIVE`. INV009 is open ("Fraud analysis underway", no end date). REC009 is "Freeze account and investigate", confidence 99.00. RR009 is `UNDER_REVIEW` with reviewer EMP003, and DEC009 is `ESCALATED` ("Potential fraud case"). There is one transaction in the window: TXN009, a DEBIT of 4,999.50 on 2025-01-14 ("Business transfer"). The pack also notes that the same customer later opened CMP028 and CMP029 (see Flow 4).

**Stage 2 — Document retrieval.** SEC003 (fraud escalation), SEC007 (AML monitoring), and SEC006 (verify identity before account changes, because a freeze is an account change).

**Stage 3 — Synthesis.** A one-page evidence pack: facts, applicable policy, open questions (the investigation is not finished and there is no documented risk-scoring rule), and the options available to the reviewer. It says **no** to automatic approval and explains that a 99.0 confidence score is the model's estimate, not authority.

**Stage 4 — Approval.** Reviewer EMP003 or a Manager makes the decision. It is written to `review_decision` with their ID and to `audit_log` (`APPROVE` / `REJECT` / `ESCALATE`). The assistant has no tool that can write a decision.

---

## How these flows were checked

- Every SQL block above was run on a local PostgreSQL 18 database built from `2_1_1_schema/database_schema.sql` (which loads the seed data) and `2_2_1_SQLJoins/complaint_analyst_view.sql`, using the example IDs. All blocks ran without errors, and the evidence quoted under each flow is the real output.
- Boundary behaviour was tested: missing ID (Flow 1), conflicting records (Flow 2), NULL response date with CMP011 (Flow 3), an already-escalated case versus unescalated ones (Flow 4), and an open investigation with a high confidence score (Flow 5).
- Negative ID test for Q1: `customer_id = 'C0001'` returns a count of **0 with no error**, which looks the same as "customer has no open complaints". This is why stage 0 must check that the ID exists before stage 1 runs. CUS001 returns 4.

**Limitations:** this was not run on the Supabase instance itself. Stage 2 uses keyword SQL, not vector search, until Week 4. The `reverse_fee` and `escalate_complaint` tools are designs and are not built yet.
