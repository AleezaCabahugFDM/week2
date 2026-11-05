# Failure Test Results

Week 2 | Exercise 2.4.1 · Step 4

**Script:** `complaint_analysis.py` · **Tests:** `test_complaint_analysis.py` · **Python:** 3.9.6, standard library only · **Run on:** 2026-11-05

## How to reproduce

```bash
python3 -m unittest -v test_complaint_analysis
```

Each test writes its own small CSV to a temporary folder, runs the script's code on it, and deletes the folder afterwards. The real outputs in this folder are not touched.

**Result: 9/9 passed.**

## What happens on an error

| Situation | Behaviour |
|---|---|
| File missing or unusable | Prints `ERROR: ...` and stops with exit code 1. No output files are written. No Python traceback. |
| Some rows incomplete | Each bad row is skipped with a `WARNING`. The run carries on and writes the outputs. |

## 1. Missing file and unusable files (the run stops)

| Test | Input | Message | Result |
|---|---|---|---|
| `test_missing_file` | A file that does not exist | `Input file not found: .../does_not_exist.csv` | PASS |
| `test_missing_file_returns_error_code_and_writes_nothing` | Same, run through `main()` | Exit code 1, no output CSV written | PASS |
| `test_missing_required_column` | No `resolved_date` / `date_closed` column | `Missing required column(s): resolved_date` | PASS |
| `test_header_only` | Header line, no rows | `The file has a header but no data rows.` | PASS |
| `test_every_row_invalid` | One row, missing category and status | `No valid rows: all 1 row(s) were skipped.` | PASS |

From the command line:

```text
$ python3 complaint_analysis.py nope.csv
ERROR: Input file not found: nope.csv
```

## 2. Incomplete rows (the run continues)

The test file has 8 rows. Each row has one problem, or none:

| Row | Problem | What happens | Message |
|---|---|---|---|
| T001 | None (Fees, Open) | Analysed | — |
| T002 | None (Fees, Closed in 4 days) | Analysed and measured | — |
| T003 | Blank category | **Skipped** | `skipped: missing category` |
| T004 | Blank customer_id and status | **Skipped**, both blanks named | `skipped: missing customer_id, status` |
| T005 | Date `31/01/2026` | **Skipped** (the date is not guessed) | `skipped: bad created_date '31/01/2026'` |
| T006 | Closed, no resolved date | Counted as closed, not used for resolution time | `closed but no valid resolved_date` |
| T007 | Resolved before it was created | Counted as closed, not used for resolution time | `resolved before created` |
| T008 | Status `Resolved`, 10 days | Counted as closed (same rule as 2.2.2) | — |

**Numbers checked by the tests:**

| Measure | Expected | Why |
|---|---|---|
| rows read | 8 | |
| rows skipped | 3 | T003, T004, T005 |
| rows analysed | 5 | |
| closed | 4 | T002, T006, T007, T008 |
| average resolution days | 7.0 | (4 + 10) ÷ 2. Only T002 and T008 can be measured |
| Fees average | 4.0 | Only T002 |
| A category with no closed cases | blank (unknown) | **Not 0** (`test_category_with_no_measurable_case_is_unknown_not_zero`) |
| Outputs written | yes | `test_incomplete_rows_still_write_outputs` |

All values matched.

## 3. Real data check

```bash
python3 complaint_analysis.py
```

```text
Loaded complaints.csv: 120 rows read, 120 valid, 0 skipped
Missing values: complaint_id=0, customer_id=0, account_id=39, category=0, status=0, created_date=0, resolved_date=86, channel=0, priority=0
Complaints: 120  open: 86  closed: 34
Highest-volume category: Mortgage Servicing (31, 25.8%)
```

These match the earlier run on the Excel copy of the same data (same totals, same category averages, overall 10.1 days). `complaints.csv` is the shared data file, kept in this folder so the run can be repeated.

## Known limitations

- **Column names differ from the requirement.** The shared file uses `date_opened` / `date_closed`. The script reads them as `created_date` / `resolved_date`.
- **CSV only.** Save an Excel file as CSV first.
- **Dates must be `YYYY-MM-DD` or `M/D/YYYY`** (the format in the shared file). Other formats, such as `31/01/2026`, are rejected, not guessed.
- **Duplicate complaint IDs are not checked.** A repeated ID would be counted twice.
- **Status values are not checked against a list.** Anything other than `Closed`/`Resolved` counts as open, so a typo like `Closd` would count as open without a warning.
- **The closed date comes from a different place than in 2.2.2.** SQL used `investigation.end_date`; this script uses the file's own `date_closed`. The formula (closed date − opened date, closed cases only) is the same.

**Handover:** 2.4.2 reuses the same idea (check the input, raise a clear error, never hide a problem) but gets its data from repositories instead of a file.
