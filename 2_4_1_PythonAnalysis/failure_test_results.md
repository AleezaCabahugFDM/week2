# Failure Test Results

Week 2 | Exercise 2.4.1 · Step 4

**Script:** `complaint_analysis.py` · **Python:** 3.9.6, standard library only · **Run on:** 2026-11-05

Each case below was run from the command line, inside this folder (the output files are written to the folder you run it from). The output is copied from the real run.

## How it behaves

| Situation | What happens |
|---|---|
| File missing or unusable | Prints `ERROR: ...` and stops (exit code 1). No output files are written. |
| Some rows incomplete | Bad rows are skipped with a `WARNING`. The run carries on and writes the outputs. |

## 1. Missing and unusable files (the run stops)

```text
$ python3 complaint_analysis.py does_not_exist.csv
ERROR: file not found: does_not_exist.csv

$ python3 complaint_analysis.py missing_column.csv        # no date_closed / resolved_date column
ERROR: missing required column(s): resolved_date

$ python3 complaint_analysis.py header_only.csv           # header line, no rows
ERROR: the file has no data rows
```

All three: **PASS**. Clear message, exit code 1, no Python error dump.

## 2. Incomplete rows (the run continues)

Test file `incomplete_rows.csv`: the header from the shared file plus these 8 rows.

```text
T001,C0001,A0001,Fees,Open,2026-01-01,,Web,Low
T002,C0002,,Fees,Closed,2026-01-01,2026-01-05,Phone,High
T003,C0003,A0003,,Open,2026-01-02,,Email,Low
T004,,A0004,Fees,,2026-01-02,,Email,Low
T005,C0005,A0005,Fees,Open,31/01/2026,,Web,Medium
T006,C0006,A0006,Fees,Closed,2026-01-04,,Branch,Medium
T007,C0007,A0007,Card,Closed,2026-02-10,2026-02-01,Phone,High
T008,C0008,A0008,Card,Resolved,2026-03-01,2026-03-11,Web,Low
```

```text
$ python3 complaint_analysis.py incomplete_rows.csv
Rows read: 8  valid: 5  skipped: 3
Missing values: {'complaint_id': 0, 'customer_id': 1, 'account_id': 1, 'category': 1, 'status': 1, 'created_date': 0, 'resolved_date': 5, 'channel': 0, 'priority': 0}
WARNING line 4 skipped: missing category
WARNING line 5 skipped: missing customer_id, status
WARNING line 6 skipped: bad created_date '31/01/2026'
WARNING line 7 (T006): closed but no usable resolved_date, not used for resolution time
WARNING line 8 (T007): closed but no usable resolved_date, not used for resolution time
Complaints: 5  open: 1  closed: 4
Highest-volume category: Fees 3 60.0%
Wrote complaint_analysis_output.csv and complaint_analysis_summary.md
```

| Row | Problem | Expected | Result |
|---|---|---|---|
| T001, T002 | None | Analysed (T002 closed in 4 days) | PASS |
| T003 | Blank category | Skipped | PASS |
| T004 | Blank customer_id and status | Skipped, both named | PASS |
| T005 | Date `31/01/2026` | Skipped (the date is not guessed) | PASS |
| T006 | Closed, no closed date | Counted as closed, not measured | PASS |
| T007 | Closed before it was opened | Counted as closed, not measured | PASS |
| T008 | `Resolved`, 10 days | Counted as closed (same rule as 2.2.2) | PASS |

**Numbers checked:** closed = 4, average resolution = **7.0** days ((4 + 10) ÷ 2, only T002 and T008 can be measured), Fees average = 4.0. All matched.

## 3. Real data

```text
$ python3 complaint_analysis.py complaints.csv
Rows read: 120  valid: 120  skipped: 0
Missing values: {'complaint_id': 0, 'customer_id': 0, 'account_id': 39, 'category': 0, 'status': 0, 'created_date': 0, 'resolved_date': 86, 'channel': 0, 'priority': 0}
Complaints: 120  open: 86  closed: 34
Highest-volume category: Mortgage Servicing 31 25.8%
```

## Known limitations

- The shared file uses `date_opened` / `date_closed`. The script reads them as `created_date` / `resolved_date`.
- CSV only. Save an Excel file as CSV first.
- Dates must be `YYYY-MM-DD` or `M/D/YYYY`. Other formats are rejected, not guessed.
- Duplicate complaint IDs are not checked.
- Any status other than `Closed`/`Resolved` counts as open, so a typo like `Closd` would count as open.
- The test files are not kept in the repo. To repeat a test, make the file shown above and run the command.

**Handover:** 2.4.2 reuses the same idea (check the input, give a clear error, never hide a problem) but gets its data from the database.
