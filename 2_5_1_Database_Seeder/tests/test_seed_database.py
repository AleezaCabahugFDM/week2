"""Tests for seed_database.py.

Unit tests need no database. Integration tests run against a throwaway
database (complaints_seed_test) and are skipped when DB_* settings are absent.

    ../.venv/bin/python -m unittest discover -s tests -v
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEEDER_DIR = HERE.parent
sys.path.insert(0, str(SEEDER_DIR))

import prepare_seed_data as prep  # noqa: E402
import seed_database as sd  # noqa: E402

for env in (Path.cwd() / ".env", sd.REPO_ROOT / ".env"):
    sd.load_dotenv(env)

TEST_DB = "complaints_seed_test"
DB_CONFIGURED = all(os.environ.get(k) for k in sd.REQUIRED_SETTINGS)
SPECS = {s.table: s for s in sd.SEED_SPECS}


def complaint_row(**overrides):
    row = {"complaint_id": "CMP900", "customer_id": "CUS001", "account_id": "ACC001", "channel": "Web",
           "category": "Fee Dispute", "customer_narrative": "text", "priority": "High", "status": "OPEN",
           "created_at": "2025-01-01 09:00:00", "assigned_employee_id": "EMP001"}
    row.update(overrides)
    return row


ACCEPTED = {"employee": {"EMP001"}, "customer": {"CUS001", "CUS002"},
            "account": {"ACC001": "CUS001", "ACC002": "CUS002"}}


class ValidationRuleTests(unittest.TestCase):
    def test_valid_row_passes(self):
        self.assertIsNone(sd.validate_row(SPECS["complaint"], complaint_row(), ACCEPTED, set()))

    def test_complaint_without_account_is_allowed(self):
        row = complaint_row(account_id=None)
        self.assertIsNone(sd.validate_row(SPECS["complaint"], row, ACCEPTED, set()))

    def test_account_must_belong_to_complaint_customer(self):
        row = complaint_row(account_id="ACC002")
        reason = sd.validate_row(SPECS["complaint"], row, ACCEPTED, set())
        self.assertIn("belongs to customer 'CUS002'", reason)

    def test_unknown_customer_rejected(self):
        reason = sd.validate_row(SPECS["complaint"], complaint_row(customer_id="CUS999"), ACCEPTED, set())
        self.assertIn("CUS999", reason)

    def test_unknown_account_rejected(self):
        reason = sd.validate_row(SPECS["complaint"], complaint_row(account_id="ACC999"), ACCEPTED, set())
        self.assertIn("ACC999", reason)

    def test_unknown_employee_rejected(self):
        reason = sd.validate_row(SPECS["complaint"], complaint_row(assigned_employee_id="EMP999"), ACCEPTED, set())
        self.assertIn("EMP999", reason)

    def test_required_value_rejected(self):
        reason = sd.validate_row(SPECS["complaint"], complaint_row(customer_narrative=None), ACCEPTED, set())
        self.assertIn("customer_narrative", reason)

    def test_duplicate_key_rejected(self):
        reason = sd.validate_row(SPECS["complaint"], complaint_row(), ACCEPTED, {"CMP900"})
        self.assertIn("duplicate", reason)


class CsvAndSchemaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_missing_header_is_critical(self):
        path = self.tmp / "customers.csv"
        path.write_text("customer_id,first_name,last_name,email,phone_number\nCUS001,A,B,,,\n")
        with self.assertRaisesRegex(sd.SeedError, "missing required header.*segment"):
            sd.read_csv(path, SPECS["customer"])

    def test_missing_file_is_critical(self):
        with self.assertRaisesRegex(sd.SeedError, "not found"):
            sd.read_csv(self.tmp / "nope.csv", SPECS["customer"])

    def test_blank_values_become_null(self):
        rows = sd.read_csv(SEEDER_DIR / "data" / "complaints.csv", SPECS["complaint"])
        no_account = [r for _, r in rows if r["account_id"] is None]
        self.assertEqual(len(no_account), 39)

    def test_schema_ddl_only_in_dependency_order(self):
        statements = sd.read_schema_statements(sd.DEFAULT_SCHEMA)
        self.assertFalse(any(s.upper().startswith("INSERT") for s in statements))
        tables = sd.schema_tables(statements)
        self.assertEqual(len(tables), 16)
        for parent, child in [("customer", "account"), ("account", "complaint"),
                              ("customer", "service_request"), ("employee", "complaint")]:
            self.assertLess(tables.index(parent), tables.index(child))


@unittest.skipUnless(DB_CONFIGURED, "DB_* environment variables not set")
class SeederIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg2
        cls.psycopg2 = psycopg2
        cls.tmp = Path(tempfile.mkdtemp())
        cls.settings = sd.db_settings(TEST_DB)
        cls._drop_db()

    @classmethod
    def tearDownClass(cls):
        cls._drop_db()
        shutil.rmtree(cls.tmp)

    @classmethod
    def _drop_db(cls):
        conn = cls.psycopg2.connect(**dict(cls.settings, dbname="postgres"))
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
        conn.close()

    def seed(self, *args):
        return sd.main(["--dbname", TEST_DB, "--log", str(self.tmp / "log.txt"),
                        "--report", str(self.tmp / "report.txt"), *args])

    def counts(self):
        conn = self.psycopg2.connect(**self.settings)
        try:
            with conn.cursor() as cur:
                out = {}
                for t in SPECS:
                    cur.execute(f"SELECT COUNT(*) FROM {t}")
                    out[t] = cur.fetchone()[0]
                return out
        finally:
            conn.close()

    def test_full_lifecycle(self):
        expected = {"employee": 10, "customer": 100, "account": 150, "complaint": 120, "service_request": 60}

        # Fresh database: one command creates and seeds it.
        self.assertEqual(self.seed("--create-db"), 0)
        self.assertEqual(self.counts(), expected)
        self.assertIn("PASSED", (self.tmp / "report.txt").read_text())

        # Re-run without --reset refuses and changes nothing.
        self.assertEqual(self.seed(), 2)
        self.assertEqual(self.counts(), expected)

        # Missing header aborts before insert; previous data survives the reset attempt.
        self.assertEqual(self.seed("--reset", "--data-dir", str(SEEDER_DIR / "test_data" / "missing_header")), 2)
        self.assertEqual(self.counts(), expected)

        # Strict mode with invalid rows rolls back everything, including the reset.
        self.assertEqual(self.seed("--reset", "--strict",
                                   "--data-dir", str(SEEDER_DIR / "test_data" / "invalid_rows")), 1)
        self.assertEqual(self.counts(), expected)
        self.assertIn("rolled back", (self.tmp / "report.txt").read_text())

        # Default mode rejects the 11 bad rows with reasons and loads the rest.
        self.assertEqual(self.seed("--reset", "--data-dir", str(SEEDER_DIR / "test_data" / "invalid_rows")), 0)
        self.assertEqual(self.counts(), expected)
        report = (self.tmp / "report.txt").read_text()
        self.assertIn("11 row(s) rejected", report)
        self.assertIn("CP00121", report)  # account belongs to another customer

        # Controlled reset back to the clean dataset.
        self.assertEqual(self.seed("--reset"), 0)
        self.assertEqual(self.counts(), expected)


if __name__ == "__main__":
    unittest.main()



class PrepareSeedDataTests(unittest.TestCase):
    def test_committed_seed_files_match_conversion(self):
        """data/*.csv must be exactly what prepare_seed_data.py produces from data/source/."""
        outputs, _ = prep.convert()
        for name, (columns, rows) in outputs.items():
            committed = sd.read_csv(SEEDER_DIR / "data" / name, SPECS[{
                "customers.csv": "customer", "accounts.csv": "account",
                "complaints.csv": "complaint", "service_requests.csv": "service_request"}[name]])
            self.assertEqual(len(committed), len(rows), name)
            for (_, got), want in zip(committed, rows):
                self.assertEqual(got, {k: (v or None) for k, v in want.items()}, name)

    def test_status_mapping(self):
        outputs, _ = prep.convert()
        statuses = {r["status"] for r in outputs["complaints.csv"][1]}
        self.assertEqual(statuses, {"OPEN", "UNDER_REVIEW", "ESCALATED", "CLOSED"})

    def test_closed_requests_have_closed_date(self):
        outputs, _ = prep.convert()
        for r in outputs["service_requests.csv"][1]:
            self.assertEqual(r["status"] == "CLOSED", bool(r["closed_date"]), r["request_id"])

    def test_unknown_source_value_is_refused(self):
        with self.assertRaisesRegex(prep.MappingError, "VIP"):
            prep.mapped("customer.segment", "VIP", "C0999")
