import unittest

from fastapi.testclient import TestClient

from complaint_analysis import FIXTURES
from main import app

client = TestClient(app)


def upload(name, content):
    return client.post("/analysis", files={"file": (name, content.encode())})


def measure(body, metric, dimension="overall", value="all"):
    return next(m["value"] for m in body["measures"]
                if (m["metric"], m["dimension"], m["dimension_value"]) == (metric, dimension, value))


class AnalysisApiTests(unittest.TestCase):
    def test_incomplete_rows_are_reported_not_fatal(self):
        response = upload("incomplete_rows.csv", FIXTURES["incomplete_rows.csv"])
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual((body["rows_read"], body["rows_valid"]), (12, 7))
        self.assertEqual(len(body["excluded"]), 5)
        self.assertEqual(len(body["warnings"]), 4)
        self.assertEqual(measure(body, "avg_resolution_days"), 7.0)
        self.assertEqual(measure(body, "avg_resolution_days", "category", "Card or Transaction Dispute"), "")
        self.assertIn("# Complaint Analysis Summary", body["summary_markdown"])

    def test_missing_column_returns_422(self):
        response = upload("missing_column.csv", FIXTURES["missing_column.csv"])
        self.assertEqual(response.status_code, 422)
        self.assertIn("missing required column(s): resolved_date", response.json()["detail"])

    def test_header_only_returns_422(self):
        response = upload("header_only.csv", FIXTURES["header_only.csv"])
        self.assertEqual(response.status_code, 422)
        self.assertIn("no data rows", response.json()["detail"])

    def test_empty_file_returns_422(self):
        self.assertEqual(upload("empty.csv", "").status_code, 422)

    def test_all_rows_invalid_returns_422(self):
        response = upload("all_rows_invalid.csv", FIXTURES["all_rows_invalid.csv"])
        self.assertEqual(response.status_code, 422)
        self.assertIn("No valid rows", response.json()["detail"])

    def test_corrupt_xlsx_returns_400_without_server_paths(self):
        response = upload("not_really.xlsx", FIXTURES["not_really.xlsx"])
        self.assertEqual(response.status_code, 400)
        self.assertIn("Could not read not_really.xlsx", response.json()["detail"])
        self.assertNotIn("/tmp", response.json()["detail"])

    def test_wrong_file_type_returns_415(self):
        self.assertEqual(upload("notes.txt", "hello").status_code, 415)

    def test_no_file_returns_422(self):
        self.assertEqual(client.post("/analysis").status_code, 422)


if __name__ == "__main__":
    unittest.main(verbosity=2)
