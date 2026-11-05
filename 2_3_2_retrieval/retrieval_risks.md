# Retrieval Risks and Controls

Week 2 | Exercise 2.3.2 · Step 3

**Purpose:** compare the risk of the four ways the assistant can answer or act (text-to-SQL, vector retrieval, tools, and automation), and define the controls and human approval points that keep each one safe. The flows these controls apply to are in `hybrid_flow_designs.md`, and the classification of each question is in `sql_rag_decision_matrix.csv`.

## 1. Risk comparison

| | Text-to-SQL | Vector (document) retrieval | API / tool calls | Automation (no human) |
|---|---|---|---|---|
| **What it is used for** | Exact facts, counts, metrics (Q1, Q4) | Policy wording and interpretation (Q2) | Changing system state (T1) | Nothing that changes outcomes for a customer |
| **Main failure** | A valid-looking query that answers the wrong question | A confident answer built on the wrong or missing passage | The right action on the wrong record, or an action nobody approved | A judgment made without accountability |
| **Example from this data** | `customer_id = 'C0001'` returns 0 with no error, and the user reads that as "no open complaints". The real ID format is `CUS###`. | No active section covers card disputes. The nearest one (SEC003 "Escalate suspected fraud") could be stretched to an answer that is not policy. | `escalate_complaint` triggered on a keyword match in a narrative, or run twice | Auto-approving CMP009 because REC009 has confidence 99.00, while INV009 is still open |
| **Other risks** | Wrong join grain double-counts (one complaint to many reviews); wrong "open" or "closed" definition; NULLs averaged as 0; hallucinated columns; unbounded scans; returning names or contact details | A superseded policy version is retrieved; a chunk is cut mid-rule; instructions hidden in a policy or narrative (prompt injection); a weak match is returned instead of "not found"; the user sees text they are not allowed to see | Excess permissions (write access to every table); arguments built from untrusted text; no idempotency; status changes that bypass `complaint_status_history` and `audit_log` | Confidence scores treated as truth; data conflicts resolved silently (RES001 says "reversed" while FEE001 is not reversed); no named decision-maker for regulators |
| **Likelihood × impact** | Medium × High: numbers look authoritative | Medium × High: policy answers look authoritative | Low × High: actions are visible but hard to reverse | Must not happen × Very high |
| **Default stance** | Prefer **parameterised templates** over free-form text-to-SQL | Answer only from cited, active sections | Allowlist only, confirm before running | **Not allowed** for decisions. Evidence gathering only. |

## 2. Controls

### 2.1 Validation (before and after a query or tool runs)

| Control | Applies to | Detail |
|---|---|---|
| ID format and existence check | SQL, tools | Customer IDs must match `^CUS\d{3}$` and complaint IDs `^CMP\d{3}$`, **and** the row must exist. Otherwise the assistant replies "not found" and asks the user. This fixes the C0001 silent-zero case. |
| Read-only database role | SQL | The assistant's role has `SELECT` on approved views only. No `INSERT`, `UPDATE`, `DELETE` or DDL. |
| Statement check | Free text-to-SQL (if ever enabled) | Parse the statement and reject anything that is not a single `SELECT`. Reject multiple statements, comments that hide statements, and `pg_` or system catalogs. |
| Resource limits | SQL | `statement_timeout` of 5 s, a default `LIMIT 200`, no cross joins without a join condition. |
| Grain check | SQL | Aggregates read from `complaint_analyst_view` (one row per complaint). Review or investigation tables are joined only when needed, and the row count is checked so a complaint is not counted twice. |
| Definitions fixed in code | SQL | "Open" means not `RESOLVED`/`CLOSED`, and resolution days are investigation `end_date` − `created_at` (2.2.2). The model does not choose definitions. |
| NULL means unknown | SQL, synthesis | NULL is reported as "unknown / not recorded", never as 0 (for example no response date in Flow 3, or a category with no closed cases in Q4). |
| Numbers come from SQL only | Synthesis | Every number in an answer must appear in the stage 1 rows. A post-check compares numbers in the answer text with the returned values. |
| Conflict detection | Synthesis | Contradictory records (RES001 vs FEE001) are flagged for a human and never resolved by the model. |
| Tool argument schema | Tools | Typed arguments, an enum for status, and an allowed-transition table (for example `CLOSED` cannot move back to `OPEN`). An existing DB check already rejects `old_status = new_status`. |

### 2.2 Filtering (what retrieval is allowed to return)

| Control | Detail |
|---|---|
| Active policy only | `policy_document.status = 'ACTIVE'` and `effective_date <= today`. `SUPERSEDED`, `RETIRED` and `DRAFT` are never retrieved. |
| Relevance threshold | Below the similarity threshold, the reply is "no matching policy found, route to Specialist". It never answers from the nearest weak match (Q2). |
| Mandatory citation | Every policy sentence cites `section_id`, policy title and version. An answer with no citation is rejected. |
| Column filtering | The analyst view excludes names, email and phone (2.2.1 design), and synthesis receives only the columns the flow needs. |
| Row-level scope | Queries are scoped to complaints the requesting employee can see. Database permissions (for example a `security_invoker` view) enforce the caller's access. |
| Untrusted text | `customer_narrative`, `findings` and policy text are passed to the model as quoted data. Instructions inside them are ignored and logged. |

### 2.3 Allowlists

**Data the assistant can read:** `complaint_analyst_view`, `complaint_status_history`, `fee`, `transactions` (amount, date and type only), `investigation`, `recommendation`, `review_request`, `review_decision`, `customer_response`, `policy_document`, `policy_section`. Not on the list: `customer` contact columns, `employee.email`, `audit_log` writes.

**Tools the assistant can call:**

| Tool | Writes | Approval before it runs |
|---|---|---|
| `update_complaint_status(complaint_id, new_status, employee_id, comment)` | `complaint.status`, `complaint_status_history`, `audit_log` (`UPDATE`/`CLOSE`) | The analyst confirms in the UI |
| `escalate_complaint(complaint_id, employee_id, reason)` | `complaint_status_history`, `audit_log` (`ESCALATE`) | The Analyst or Supervisor confirms |
| `reverse_fee(fee_id, approver_id)` | `fee.reversed`, `audit_log` (`APPROVE`) | **Manager** approval (POL009 SEC009) |
| `draft_customer_response(complaint_id, text)` | Draft only, not sent | A Reviewer approves before it is sent |

**Not allowlisted (refuse and route to a person):** deleting any record (T2), writing to `review_decision`, sending a customer message without approval, changing account status (freeze or restrict), and any free-form SQL write.

## 3. Approval points

| # | Point | Trigger | Approver | Recorded in |
|---|---|---|---|---|
| A1 | Before a customer-facing message is sent | Any `customer_response` | Reviewer | `customer_response.sent_by`, `audit_log` (`SEND`) |
| A2 | Before a fee reversal or refund | `reverse_fee`, a refund recommendation | Manager (SEC009) | `review_decision`, `audit_log` (`APPROVE`) |
| A3 | Before an escalation | `escalate_complaint` (Flow 4 candidates such as CMP028, CMP029) | Analyst / Supervisor | `complaint_status_history`, `audit_log` (`ESCALATE`) |
| A4 | Any decision on a High or Critical case | Q5 / Flow 5 (CMP009) | Reviewer or Manager | `review_decision` with a human `decision_reason` |
| A5 | Account changes (freeze, restrict) | A recommendation such as REC009 | Manager, with identity verified first (SEC006) | Outside the assistant, logged in `audit_log` |
| A6 | Data conflict found | Flow 2 (RES001 vs FEE001) | Case owner | A comment in `complaint_status_history` |
| A7 | No policy found | Q2 and similar | Specialist | Routed, not answered |

Rule: the assistant **prepares**, a named human **decides**, and the system **records** who decided. A confidence score never replaces an approval.

## 4. Tests (negative and boundary)

| Test | Input | Expected | Result |
|---|---|---|---|
| Unknown ID | Q1 with `C0001` | "Customer not found", no count | Raw SQL returns 0 with no error, **so the existence check is required** |
| Valid ID | Q1 with `CUS001` | 4 open | 4 ✔ |
| NULL response | Flow 3 with `CMP011` | NULL, not 0 | NULL ✔ |
| Already escalated | Flow 4 | CMP009 excluded | Excluded ✔. CMP028 and CMP029 returned as gaps |
| Data conflict | Flow 2 with `CMP001` | Flagged | RES001 "reversed" vs `FEE001.reversed = f` returned ✔ |
| No policy coverage | Q2 card dispute | "No policy found" | Keyword search finds no card section ✔ (only SEC003 fraud) |
| Auto-approve request | Q5 | Refuse, build evidence pack | Covered by design (no decision tool exists) |
| Delete request | T2 | Refuse | Covered by design (not allowlisted) |

The SQL tests ran on a local PostgreSQL 18 copy of the 2.1.1 schema and seed data. The tool and refusal tests are design-level until the tools are built.

## 5. Known limitations

- The Week 1 approved spec is not in this repository. The approval roles above are taken from the schema (`employee.role`) and the policy seed (SEC009, SEC006). Check them against the spec.
- Policy text in the seed is one sentence per section, which is too thin for real interpretation. Q2 cannot be answered until fuller policy documents are loaded (Week 4 retrieval service).
- Business-day counts ignore bank holidays.
- Resolution time uses investigation `end_date` as a stand-in for closure because status-history timestamps are load-time (2.2.2).
- `2_2_2_SQLMetrics/metric_definition.md` and `complaint_metrics.csv` are empty in the repo. Q4 depends on the M6 query in `complaint_metrics.sql`, which is filled in.

**Handover:** 2.4.1 uses the SQL/CSV outputs. Week 4 implements stage 2 (document retrieval) behind the same contract: active-only, threshold, citations.
