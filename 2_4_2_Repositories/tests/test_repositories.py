import os
import sys
import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import psycopg2
from psycopg2 import errors

from data.account_repository import Account, AccountRepository
from data.complaint_repository import Complaint, ComplaintRepository
from data.customer_repository import Customer, CustomerRepository
from data.database_manager import ConfigError, DatabaseManager

ENV = {"DB_HOST": "localhost", "DB_PORT": "5432", "DB_NAME": "x", "DB_USER": "u", "DB_PASSWORD": "secret-pw"}
DB_CONFIGURED = all(os.environ.get(k) for k in ENV)


class ConfigTests(unittest.TestCase):
    def test_loads_settings_from_environment(self):
        with mock.patch.dict(os.environ, ENV):
            db = DatabaseManager.from_env()
        self.assertEqual(repr(db), "DatabaseManager(u@localhost:5432/x, password=***)")

    def test_missing_setting_is_named_without_exposing_values(self):
        env = {**ENV, "DB_NAME": ""}
        with mock.patch.dict(os.environ, env, clear=True):
            with self.assertRaises(ConfigError) as ctx:
                DatabaseManager.from_env()
        self.assertIn("DB_NAME", str(ctx.exception))
        self.assertNotIn("secret-pw", str(ctx.exception))

    def test_password_not_in_repr(self):
        db = DatabaseManager("localhost", 5432, "x", "u", "secret-pw")
        self.assertNotIn("secret-pw", repr(db))

    def test_unreachable_database_raises_and_leaves_nothing_open(self):
        db = DatabaseManager("127.0.0.1", 1, "x", "u", "secret-pw")
        with self.assertRaises(psycopg2.OperationalError) as ctx:
            CustomerRepository(db).get_by_id("CUS001")
        self.assertFalse(db.is_open)
        self.assertNotIn("secret-pw", str(ctx.exception))


@unittest.skipUnless(DB_CONFIGURED, "set DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD to run database tests")
class RepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseManager.from_env()
        cls.remove_test_data()
        with cls.db.transaction() as cur:
            cur.execute("INSERT INTO customer VALUES ('TST_CUS1', 'Test', 'One', 't1@example.com', NULL, 'Retail'), "
                        "('TST_CUS2', 'Test', 'Two', NULL, NULL, 'Premier')")
            cur.execute("INSERT INTO account VALUES ('TST_ACC1', 'TST_CUS1', 'TST-0001', 'Checking', 'ACTIVE', "
                        "125.50, '2025-01-01')")
            cur.execute("INSERT INTO complaint VALUES ('TST_CMP1', 'TST_CUS1', 'TST_ACC1', 'Web', 'Fee Dispute', "
                        "'Test complaint', 'High', 'OPEN', '2025-01-02 09:00', NULL)")
        cls.customers = CustomerRepository(cls.db)
        cls.accounts = AccountRepository(cls.db)
        cls.complaints = ComplaintRepository(cls.db)

    @classmethod
    def tearDownClass(cls):
        cls.remove_test_data()
        cls.db.close()

    @classmethod
    def remove_test_data(cls):
        with cls.db.transaction() as cur:
            for table in ("complaint", "account", "customer"):
                cur.execute(f"DELETE FROM {table} WHERE {table}_id LIKE %s", ("TST\\_%",))

    def new_complaint(self, complaint_id, **overrides):
        values = dict(complaint_id=complaint_id, customer_id="TST_CUS1", channel="Phone",
                      category="Fee Dispute", customer_narrative="Created by test", priority="Low")
        values.update(overrides)
        return self.complaints.create(**values)

    # Valid
    def test_get_customer_by_id(self):
        self.assertEqual(self.customers.get_by_id("TST_CUS1"),
                         Customer("TST_CUS1", "Test", "One", "t1@example.com", None, "Retail"))

    def test_get_accounts_for_customer(self):
        self.assertEqual(self.accounts.get_for_customer("TST_CUS1"),
                         [Account("TST_ACC1", "TST_CUS1", "TST-0001", "Checking", "ACTIVE",
                                  Decimal("125.50"), date(2025, 1, 1))])

    def test_get_complaint_by_id(self):
        complaint = self.complaints.get_by_id("TST_CMP1")
        self.assertIsInstance(complaint, Complaint)
        self.assertEqual((complaint.customer_id, complaint.priority, complaint.created_at),
                         ("TST_CUS1", "High", datetime(2025, 1, 2, 9, 0)))

    def test_get_complaints_for_customer(self):
        ids = [c.complaint_id for c in self.complaints.get_for_customer("TST_CUS1")]
        self.assertIn("TST_CMP1", ids)

    def test_create_complaint_and_read_it_back(self):
        created = self.new_complaint("TST_CMP2", account_id="TST_ACC1")
        self.assertEqual(created.status, "OPEN")
        self.assertIsNotNone(created.created_at)
        self.assertEqual(self.complaints.get_by_id("TST_CMP2"), created)

    def test_create_complaint_without_account(self):
        self.assertIsNone(self.new_complaint("TST_CMP3").account_id)

    # Missing
    def test_missing_customer_returns_none(self):
        self.assertIsNone(self.customers.get_by_id("NOPE"))

    def test_customer_without_accounts_returns_empty_list(self):
        self.assertEqual(self.accounts.get_for_customer("TST_CUS2"), [])
        self.assertEqual(self.accounts.get_for_customer("NOPE"), [])

    def test_missing_complaint_returns_none(self):
        self.assertIsNone(self.complaints.get_by_id("NOPE"))

    def test_customer_without_complaints_returns_empty_list(self):
        self.assertEqual(self.complaints.get_for_customer("TST_CUS2"), [])

    def test_sql_injection_text_is_treated_as_a_value(self):
        self.assertIsNone(self.customers.get_by_id("x' OR '1'='1"))
        self.assertIsNotNone(self.customers.get_by_id("TST_CUS1"))

    # Failure
    def test_invalid_priority_is_rolled_back(self):
        with self.assertRaises(errors.CheckViolation):
            self.new_complaint("TST_BAD1", priority="Urgent")
        self.assertIsNone(self.complaints.get_by_id("TST_BAD1"))

    def test_duplicate_complaint_id_is_rejected(self):
        with self.assertRaises(errors.UniqueViolation):
            self.new_complaint("TST_CMP1")

    def test_account_of_another_customer_is_rejected(self):
        with self.assertRaises(errors.ForeignKeyViolation):
            self.new_complaint("TST_BAD2", customer_id="TST_CUS2", account_id="TST_ACC1")
        self.assertIsNone(self.complaints.get_by_id("TST_BAD2"))

    def test_cursor_closes_and_connection_recovers_after_error(self):
        with self.assertRaises(errors.UndefinedTable):
            with self.db.transaction() as cur:
                cur.execute("SELECT * FROM no_such_table")
        self.assertTrue(cur.closed)
        self.assertTrue(self.db.is_open)
        self.assertIsNotNone(self.customers.get_by_id("TST_CUS1"))

    def test_connection_closes_after_error_in_with_block(self):
        with self.assertRaises(RuntimeError):
            with DatabaseManager.from_env() as db:
                CustomerRepository(db).get_by_id("TST_CUS1")
                raise RuntimeError("boom")
        self.assertFalse(db.is_open)


if __name__ == "__main__":
    unittest.main(verbosity=2)
