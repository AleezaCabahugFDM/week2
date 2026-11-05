"""Tests for seed_database.py and prepare_seed_data.py.

The rule tests need no database. The full-run test uses a throwaway database
(complaints_seed_test) that it creates and drops, and is skipped when DB_* settings are missing.

    ../.venv/bin/python -m unittest discover -s tests -v
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SEEDER_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(SEEDER_DIR))

import psycopg2  # noqa: E402

import prepare_seed_data as prep  # noqa: E402
import seed_database as sd  # noqa: E402

sd.load_dotenv(sd.REPO_ROOT / ".env")
DB_CONFIGURED = all(os.environ.get(name) for name in sd.REQUIRED_SETTINGS)
TEST_DB = "complaints_seed_test"
SPECS = {spec["table"]: spec for spec in sd.TABLES}

# IDs that are already "loaded" for the rule tests. ACC001 belongs to CUS001, ACC002 to CUS002.
LOADED = {"employee": {"EMP001"}, "customer": {"CUS001", "CUS002"},
          "account": {"ACC001": "CUS001", "ACC002": "CUS002"}}


def check_complaint(**changes):
    row = {"complaint_id": "CMP900", "customer_id": "CUS001", "account_id": "ACC001", "channel": "Web",
           "category": "Fee Dispute", "customer_narrative": "text", "priority": "High", "status": "OPEN",
           "created_at": "2025-01-01 09:00:00", "assigned_employee_id": "EMP001"}
    row.update(changes)
    return sd.check_row("complaint", row, SPECS["complaint"]["required"], set(), "complaint_id", LOADED)


class RuleTests(unittest.TestCase):
    def test_valid_row_passes(self):
        self.assertIsNone(check_complaint())

    def test_complaint_without_account_is_allowed(self):
        self.assertIsNone(check_complaint(account_id=None))

    def test_account_must_belong_to_complaint_customer(self):
        self.assertIn("belongs to customer 'CUS002'", check_complaint(account_id="ACC002"))

    def test_unknown_customer_account_and_employee_are_rejected(self):
        self.assertIn("CUS999", check_complaint(customer_id="CUS999"))
        self.assertIn("ACC999", check_complaint(account_id="ACC999"))
        self.assertIn("EMP999", check_complaint(assigned_employee_id="EMP999"))

    def test_empty_required_value_is_rejected(self):
        self.assertIn("customer_narrative", check_complaint(customer_narrative=None))

    def test_duplicate_key_is_rejected(self):
        row = {c: "x" for c in SPECS["customer"]["columns"]}
        reason = sd.check_row("customer", row, SPECS["customer"]["required"], {"x"}, "customer_id", LOADED)
        self.assertIn("duplicate", reason)


class FileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_missing_header_is_critical(self):
        path = self.tmp / "customers.csv"
        path.write_text("customer_id,first_name,last_name,email,phone_number\nCUS001,A,B,,\n")
        with self.assertRaisesRegex(sd.SeedError, "missing required header.*segment"):
            sd.read_csv(path, SPECS["customer"])

    def test_missing_file_is_critical(self):
        with self.assertRaisesRegex(sd.SeedError, "not found"):
            sd.read_csv(self.tmp / "nope.csv", SPECS["customer"])

    def test_blank_cells_become_null(self):
        rows = sd.read_csv(SEEDER_DIR / "data" / "complaints.csv", SPECS["complaint"])
        self.assertEqual(len([r for _, r in rows if r["account_id"] is None]), 39)

    def test_schema_has_only_table_creation_and_16_tables(self):
        ddl, tables = sd.read_schema()
        self.assertNotIn("INSERT INTO", ddl)
        self.assertEqual(len(tables), 16)
        self.assertLess(tables.index("customer"), tables.index("account"))
        self.assertLess(tables.index("account"), tables.index("complaint"))

    def test_seed_files_match_prepare_seed_data(self):
        """data/*.csv must be exactly what prepare_seed_data.py makes from data/source/."""
        names = {"customers.csv": "customer", "accounts.csv": "account",
                 "complaints.csv": "complaint", "service_requests.csv": "service_request"}
        for name, rows in prep.convert().items():
            saved = [row for _, row in sd.read_csv(SEEDER_DIR / "data" / name, SPECS[names[name]])]
            expected = [{k: (v or None) for k, v in row.items()} for row in rows]
            self.assertEqual(saved, expected, name)

    def test_unknown_source_value_is_refused(self):
        with self.assertRaisesRegex(prep.MappingError, "VIP"):
            prep.mapped(prep.CUSTOMER_SEGMENT, "VIP", "C0999")


@unittest.skipUnless(DB_CONFIGURED, "DB_* environment variables not set")
class FullRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.settings = sd.db_settings(TEST_DB)
        cls.drop_test_database()

    @classmethod
    def tearDownClass(cls):
        cls.drop_test_database()
        shutil.rmtree(cls.tmp)

    @classmethod
    def drop_test_database(cls):
        connection = psycopg2.connect(**dict(cls.settings, dbname="postgres"))
        connection.autocommit = True
        with connection.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
        connection.close()

    def seed(self, *options):
        return sd.main(["--dbname", TEST_DB, "--log", str(self.tmp / "log.txt"),
                        "--report", str(self.tmp / "report.txt"), *options])

    def counts(self):
        connection = psycopg2.connect(**self.settings)
        with connection.cursor() as cur:
            result = {}
            for table in SPECS:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                result[table] = cur.fetchone()[0]
        connection.close()
        return result

    def report(self):
        return (self.tmp / "report.txt").read_text()

    def test_full_lifecycle(self):
        expected = {"employee": 10, "customer": 100, "account": 150, "complaint": 120, "service_request": 60}

        # A new database: one command creates and seeds it.
        self.assertEqual(self.seed("--create-db"), 0)
        self.assertEqual(self.counts(), expected)
        self.assertIn("PASSED", self.report())

        # Running again without --reset refuses and changes nothing.
        self.assertEqual(self.seed(), 1)
        self.assertEqual(self.counts(), expected)

        # A missing header stops the run before any insert. The data from before is still there.
        self.assertEqual(self.seed("--reset", "--data-dir", str(SEEDER_DIR / "test_data" / "missing_header")), 1)
        self.assertEqual(self.counts(), expected)

        # --strict with bad rows rolls back everything, including the reset.
        self.assertEqual(self.seed("--reset", "--strict",
                                   "--data-dir", str(SEEDER_DIR / "test_data" / "invalid_rows")), 1)
        self.assertEqual(self.counts(), expected)
        self.assertIn("rolled back", self.report())

        # Without --strict the 11 bad rows are rejected with a reason and the rest are loaded.
        self.assertEqual(self.seed("--reset", "--data-dir", str(SEEDER_DIR / "test_data" / "invalid_rows")), 0)
        self.assertEqual(self.counts(), expected)
        self.assertIn("11 row(s) rejected", self.report())
        self.assertIn("CP00121", self.report())      # its account belongs to another customer

        # Reset back to the clean data.
        self.assertEqual(self.seed("--reset"), 0)
        self.assertEqual(self.counts(), expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
