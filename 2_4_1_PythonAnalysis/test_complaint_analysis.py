"""Failure tests for complaint_analysis.py (Step 4).

    python3 -m unittest -v test_complaint_analysis
"""

import tempfile
import unittest
from pathlib import Path

from complaint_analysis import AnalysisError, load_complaints, main, summarise

HEADER = "complaint_id,customer_id,account_id,category,status,date_opened,date_closed,channel,priority\n"

# Each row has one problem (or none). The comment says what should happen.
INCOMPLETE_ROWS = (
    HEADER
    + "T001,C0001,A0001,Fees,Open,2026-01-01,,Web,Low\n"              # fine
    + "T002,C0002,,Fees,Closed,2026-01-01,2026-01-05,Phone,High\n"    # fine, closed in 4 days
    + "T003,C0003,A0003,,Open,2026-01-02,,Email,Low\n"                # skipped: no category
    + "T004,,A0004,Fees,,2026-01-02,,Email,Low\n"                     # skipped: no customer_id or status
    + "T005,C0005,A0005,Fees,Open,31/01/2026,,Web,Medium\n"           # skipped: bad date
    + "T006,C0006,A0006,Fees,Closed,2026-01-04,,Branch,Medium\n"      # closed, no resolved date
    + "T007,C0007,A0007,Card,Closed,2026-02-10,2026-02-01,Phone,High\n"  # resolved before created
    + "T008,C0008,A0008,Card,Resolved,2026-03-01,2026-03-11,Web,Low\n"   # Resolved counts as closed, 10 days
)


class FailureTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.tmp = Path(self.folder.name)

    def tearDown(self):
        self.folder.cleanup()

    def write(self, name, text):
        path = self.tmp / name
        path.write_text(text, encoding="utf-8")
        return path

    # Missing file and unusable files: the run stops with a clear error.

    def test_missing_file(self):
        with self.assertRaisesRegex(AnalysisError, "Input file not found"):
            load_complaints(self.tmp / "does_not_exist.csv")

    def test_missing_file_returns_error_code_and_writes_nothing(self):
        self.assertEqual(main([str(self.tmp / "does_not_exist.csv"), str(self.tmp)]), 1)
        self.assertFalse((self.tmp / "complaint_analysis_output.csv").exists())

    def test_missing_required_column(self):
        path = self.write("no_resolved.csv", "complaint_id,customer_id,category,status,date_opened\n"
                                             "T001,C0001,Fees,Open,2026-01-01\n")
        with self.assertRaisesRegex(AnalysisError, "Missing required column.*resolved_date"):
            load_complaints(path)

    def test_header_only(self):
        path = self.write("header_only.csv", HEADER)
        with self.assertRaisesRegex(AnalysisError, "no data rows"):
            load_complaints(path)

    def test_every_row_invalid(self):
        path = self.write("all_bad.csv", HEADER + "T001,C0001,,,Open,2026-01-01,,Web,Low\n")
        with self.assertRaisesRegex(AnalysisError, "No valid rows"):
            load_complaints(path)

    # Incomplete rows: bad rows are skipped with a warning and the run continues.

    def test_incomplete_rows_are_skipped_with_warnings(self):
        rows, evidence = load_complaints(self.write("incomplete.csv", INCOMPLETE_ROWS))
        self.assertEqual(evidence["rows_read"], 8)
        self.assertEqual(evidence["rows_skipped"], 3)
        self.assertEqual(len(rows), 5)
        warnings = " | ".join(evidence["warnings"])
        self.assertIn("(T003) skipped: missing category", warnings)
        self.assertIn("(T004) skipped: missing customer_id, status", warnings)
        self.assertIn("(T005) skipped: bad created_date '31/01/2026'", warnings)
        self.assertIn("(T006): closed but no valid resolved_date", warnings)
        self.assertIn("(T007): resolved before created", warnings)

    def test_incomplete_rows_calculations(self):
        rows, _ = load_complaints(self.write("incomplete.csv", INCOMPLETE_ROWS))
        s = summarise(rows)
        self.assertEqual(s["closed"], 4)               # T002, T006, T007, T008
        self.assertEqual(s["avg_resolution"], 7.0)     # (4 + 10) / 2: only T002 and T008 can be measured
        self.assertEqual(s["resolution_by_category"]["Fees"]["avg"], 4.0)

    def test_category_with_no_measurable_case_is_unknown_not_zero(self):
        text = HEADER + "T001,C0001,,Fees,Open,2026-01-01,,Web,Low\n"
        rows, _ = load_complaints(self.write("open_only.csv", text))
        self.assertIsNone(summarise(rows)["resolution_by_category"]["Fees"]["avg"])

    def test_incomplete_rows_still_write_outputs(self):
        path = self.write("incomplete.csv", INCOMPLETE_ROWS)
        self.assertEqual(main([str(path), str(self.tmp)]), 0)
        self.assertTrue((self.tmp / "complaint_analysis_output.csv").exists())
        self.assertTrue((self.tmp / "complaint_analysis_summary.md").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
