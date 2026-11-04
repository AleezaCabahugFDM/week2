# Failure Test Results

Week 2 | Exercise 2.4.1 · Step 4

**Script:** `complaint_analysis.py` · **Python:** 3.9.6, standard library only · **Run on:** 2026-11-04

## How to reproduce

```bash
python3 complaint_analysis.py --self-test
```

The self-test writes its test files to a temporary folder, runs each case through the same `main()` a user would call, checks the exit code and messages, and deletes the folder afterwards. No test files are kept in the repo, and the real outputs in this folder are not touched.

**Result: 8/8 passed, exit code 0.** The output below is from the real run. Temporary-folder paths are shortened to `<tmp>`.

## Exit codes

| Code | Meaning | Behaviour |
|---|---|---|
| 0 | Success | Outputs written. Incomplete rows are excluded with a warning, and the run continues. |
| 2 | File missing or unreadable | Clear `ERROR:` message on stderr, no outputs written, no Python traceback. |
| 3 | File readable but unusable | Missing required column, no data rows, or no valid rows. `ERROR:` message, no outputs. |

## 1. Missing-file and unusable-file cases (run stops)

| # | Case | Input | Expected | Exit | Message (stderr) | Result |
|---|---|---|---|---|---|---|
| 1 | Missing file | `does_not_exist.csv` | Stop with a clear error | 2 | `ERROR: Input file not found: <tmp>/does_not_exist.csv` | PASS |
| 2 | Path is a folder | `<tmp>` | Stop with a clear error | 2 | `ERROR: Input path is not a file: <tmp>` | PASS |
| 3 | Empty file | 0 bytes | Stop | 3 | `ERROR: <tmp>/empty.csv is empty (no header row).` | PASS |
| 4 | Corrupt .xlsx | Text file named `.xlsx` | Stop, no traceback | 2 | `ERROR: Could not read <tmp>/not_really.xlsx: File is not a zip file` | PASS |
| 5 | Missing required column | No `resolved_date` / `date_closed` | Stop and name the column | 3 | `ERROR: ... is missing required column(s): resolved_date. Found: complaint_id, customer_id, category, status, date_opened` | PASS |
| 6 | Header but no rows | Header line only | Stop | 3 | `ERROR: <tmp>/header_only.csv has a header but no data rows.` | PASS |
| 7 | Every row incomplete | 2 rows, both missing category | Stop rather than report zeros | 3 | `ERROR: No valid rows in <tmp>/all_rows_invalid.csv: all 2 row(s) were excluded (first reason: missing category).` | PASS |

The script also stops with exit 2 when it is run with no argument and there is no `complaints.csv` next to it (checked by hand):

```text
$ python3 complaint_analysis.py
ERROR: Input file not found: /Users/aleeza/Documents/GitHub/week2/2_4_1_PythonAnalysis/complaints.csv
```

## 2. Incomplete-row case (run continues)

**Test 8: PASS, exit 0.** The test file has 13 lines after the header: 12 data rows and 1 blank line. Each data row exercises one problem.

| Line | complaint_id | Problem | Expected handling | Actual message |
|---|---|---|---|---|
| 2 | T001 | None (Fees, Open) | Analysed | — |
| 3 | T002 | None (Fees, Closed, 4 days) | Analysed and measured | — |
| 4 | T003 | Blank category | **Excluded** | `excluded: missing category` |
| 5 | T004 | Blank customer_id and status | **Excluded**, every blank named | `excluded: missing customer_id, status` |
| 6 | T005 | Date `31/01/2026` | **Excluded** (date not guessed) | `excluded: invalid created_date '31/01/2026' (expected YYYY-MM-DD)` |
| 7 | T001 | Duplicate ID | **Excluded**, first kept | `excluded: duplicate complaint_id (first occurrence kept)` |
| 8 | T007 | Closed, no closed date | Counted as closed, not measured | `closed with no resolved_date; counted as closed, resolution time unmeasurable` |
| 9 | T008 | Closed before opened | Counted, not measured | `resolved_date 2026-02-01 is before created_date 2026-02-10; row counted, excluded from resolution time` |
| 10 | T009 | In Review with a closed date | Counted as open, date ignored | `status 'In Review' is not closed but has a resolved_date; date ignored` |
| 11 | T010 | Closed date `not a date` | Counted, not measured | `invalid resolved_date 'not a date'; row counted, excluded from resolution time` |
| 12 | T011 | Row cut off after 3 cells | **Excluded** | `excluded: missing category, status, created_date` |
| 13 | — | Blank line | Ignored, not counted | — |
| 14 | T013 | `Resolved` status (10 days) | Treated as closed (2.2.2 rule) | — |

**Calculated output checked by the test** (from `complaint_analysis_output.csv`):

| Measure | Expected | Why |
|---|---|---|
| rows_read | 12 | The blank line is not a row |
| rows_excluded | 5 | T003, T004, T005, duplicate T001, T011 |
| rows_with_warnings | 4 | T007, T008, T009, T010 |
| complaint_count | 7 | Only valid rows are counted |
| closed_count | 5 | T002, T007, T008, T010, T013 (Resolved counts as closed) |
| resolution_measured_count | 2 | Only T002 (4 days) and T013 (10 days) have usable dates |
| resolution_unmeasurable_count | 3 | Closed but no usable date. Reported, not dropped. |
| avg_resolution_days (overall) | 7.0 | (4 + 10) ÷ 2 |
| avg_resolution_days (Card or Transaction Dispute) | blank | 2 closed cases, 0 measurable, so **unknown, not 0** |
| highest_volume_category | Fees **and** Card or Transaction Dispute, 3 each | A tie: both are reported and marked `tie` |

All values matched.

## 3. Real data check

```bash
python3 complaint_analysis.py ~/Downloads/complaints.xlsx
```

```text
Column aliases applied: date_opened -> created_date, date_closed -> resolved_date
Rows read: 120  valid: 120  excluded: 0  warnings: 0
Missing values: complaint_id=0, customer_id=0, account_id=39, category=0, status=0, created_date=0, resolved_date=86, channel=0, priority=0
Complaints analysed: 120  open: 86  closed: 34
Highest-volume category: Mortgage Servicing (31, 25.8%)
```

The totals, highest-volume category, and resolution averages (overall 10.1 days, and each category) were recalculated independently from the raw rows and matched the script's output.

## Bug found by these tests

The first run failed test 8. The overall average printed as `7` instead of `7.0`, because the mean of two whole numbers came back as an integer, so the CSV would have mixed `7` and `10.1` styles. Fixed by always rounding to a one-decimal float. Medians were fixed the same way.

## Known limitations

- **Column names differ from the requirement.** The shared file uses `date_opened` / `date_closed`. The script maps them to `created_date` / `resolved_date` and records this in the load evidence. A file that has neither name fails test 5.
- **Dates must be ISO `YYYY-MM-DD`** in CSV, or real date cells / Excel serial numbers in .xlsx. Other formats are rejected, not guessed, because `01/02/2026` is ambiguous.
- **.xlsx reads the first worksheet only.**
- **Status values are not checked against a fixed list.** An unexpected status (for example `Pending`) is counted as open, because only `Closed`/`Resolved` count as closed. This matches 2.2.2, but a typo such as `Closd` would be counted as open without a warning.
- **The definition of "closed" differs from 2.2.2's source.** In SQL, the closed date came from `investigation.end_date`. Here it comes from the file's own `date_closed`. The formula (closed date − opened date, closed cases only) is the same.

**Handover:** 2.4.2 reuses `load_complaints()` validation, `AnalysisError` with exit codes, and the excluded/warning evidence pattern, but gets its rows from a repository instead of a file.
