# test_repositories.py
# Week 2 | Exercise 2.4.2 - Valid, missing and failure tests for the repositories.
#
# Run from the 2_4_2_Repositories folder:
#   python3 -m unittest discover -s tests -v
#
# The 4 settings tests always run. The 16 database tests need the DB_* settings,
# and are skipped without them. They add their own TST_ rows and delete them at the end.

import os
import sys
import unittest
from datetime import date, datetime
from decimal import Decimal

# Let Python find the files in src/data
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import psycopg2
from psycopg2 import errors

from data.account_repository import AccountRepository
from data.complaint_repository import ComplaintRepository
from data.customer_repository import CustomerRepository
from data.database_manager import ConfigError, DatabaseManager, load_settings

FAKE_SETTINGS = {"DB_HOST": "127.0.0.1", "DB_PORT": "1", "DB_NAME": "x",
                 "DB_USER": "u", "DB_PASSWORD": "secret-pw"}


class SettingsTests(unittest.TestCase):
    def test_loads_all_settings(self):
        settings = load_settings(FAKE_SETTINGS)
        self.assertEqual(settings["DB_NAME"], "x")

    def test_missing_setting_is_named_without_showing_values(self):
        settings = dict(FAKE_SETTINGS)
        settings["DB_NAME"] = ""
        with self.assertRaises(ConfigError) as error:
            load_settings(settings)
        self.assertIn("DB_NAME", str(error.exception))
        self.assertNotIn("secret-pw", str(error.exception))

    def test_password_not_shown_when_printed(self):
        db = DatabaseManager(FAKE_SETTINGS)
        self.assertNotIn("secret-pw", str(db))

    def test_unreachable_database_gives_error_and_nothing_left_open(self):
        db = DatabaseManager(FAKE_SETTINGS)       # port 1, so nothing is there
        with self.assertRaises(psycopg2.OperationalError) as error:
            CustomerRepository(db).get_by_id("CUS001")
        self.assertFalse(db.is_open())
        self.assertNotIn("secret-pw", str(error.exception))


class RepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.db = DatabaseManager()
        except ConfigError:
            raise unittest.SkipTest("set DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD to run database tests")
        remove_test_data(cls.db)
        cls.db.run("INSERT INTO customer VALUES ('TST_CUS1', 'Test', 'One', 't1@example.com', NULL, 'Retail')", ())
        cls.db.run("INSERT INTO customer VALUES ('TST_CUS2', 'Test', 'Two', NULL, NULL, 'Premier')", ())
        cls.db.run("INSERT INTO account VALUES ('TST_ACC1', 'TST_CUS1', 'TST-0001', 'Checking', 'ACTIVE', "
                   "125.50, '2025-01-01')", ())
        cls.db.run("INSERT INTO complaint VALUES ('TST_CMP1', 'TST_CUS1', 'TST_ACC1', 'Web', 'Fee Dispute', "
                   "'Test complaint', 'High', 'OPEN', '2025-01-02 09:00', NULL)", ())
        cls.customers = CustomerRepository(cls.db)
        cls.accounts = AccountRepository(cls.db)
        cls.complaints = ComplaintRepository(cls.db)

    @classmethod
    def tearDownClass(cls):
        remove_test_data(cls.db)
        cls.db.close()

    def new_complaint(self, complaint_id, customer_id="TST_CUS1", account_id=None, priority="Low"):
        return self.complaints.create(complaint_id, customer_id, "Phone", "Fee Dispute",
                                      "Created by test", priority, account_id)

    # ----- Valid -----

    def test_get_customer_by_id(self):
        customer = self.customers.get_by_id("TST_CUS1")
        self.assertEqual(customer.first_name, "Test")
        self.assertEqual(customer.email, "t1@example.com")
        self.assertIsNone(customer.phone_number)
        self.assertEqual(customer.segment, "Retail")

    def test_get_accounts_for_customer(self):
        accounts = self.accounts.get_for_customer("TST_CUS1")
        self.assertEqual(len(accounts), 1)
        self.assertEqual(accounts[0].account_id, "TST_ACC1")
        self.assertEqual(accounts[0].balance, Decimal("125.50"))
        self.assertEqual(accounts[0].open_date, date(2025, 1, 1))

    def test_get_complaint_by_id(self):
        complaint = self.complaints.get_by_id("TST_CMP1")
        self.assertEqual(complaint.customer_id, "TST_CUS1")
        self.assertEqual(complaint.priority, "High")
        self.assertEqual(complaint.created_at, datetime(2025, 1, 2, 9, 0))

    def test_get_complaints_for_customer(self):
        ids = []
        for complaint in self.complaints.get_for_customer("TST_CUS1"):
            ids.append(complaint.complaint_id)
        self.assertIn("TST_CMP1", ids)

    def test_create_complaint_and_read_it_back(self):
        created = self.new_complaint("TST_CMP2", account_id="TST_ACC1")
        self.assertEqual(created.status, "OPEN")
        self.assertIsNotNone(created.created_at)
        saved = self.complaints.get_by_id("TST_CMP2")
        self.assertEqual(saved.account_id, "TST_ACC1")
        self.assertEqual(saved.created_at, created.created_at)

    def test_create_complaint_without_account(self):
        created = self.new_complaint("TST_CMP3")
        self.assertIsNone(created.account_id)

    # ----- Missing -----

    def test_missing_customer_gives_none(self):
        self.assertIsNone(self.customers.get_by_id("NOPE"))

    def test_customer_without_accounts_gives_empty_list(self):
        self.assertEqual(self.accounts.get_for_customer("TST_CUS2"), [])
        self.assertEqual(self.accounts.get_for_customer("NOPE"), [])

    def test_missing_complaint_gives_none(self):
        self.assertIsNone(self.complaints.get_by_id("NOPE"))

    def test_customer_without_complaints_gives_empty_list(self):
        self.assertEqual(self.complaints.get_for_customer("TST_CUS2"), [])

    def test_sql_injection_text_is_just_a_value(self):
        self.assertIsNone(self.customers.get_by_id("x' OR '1'='1"))

    # ----- Failure -----

    def test_invalid_priority_is_rejected_and_not_saved(self):
        with self.assertRaises(errors.CheckViolation):
            self.new_complaint("TST_BAD1", priority="Urgent")
        self.assertIsNone(self.complaints.get_by_id("TST_BAD1"))

    def test_duplicate_complaint_id_is_rejected(self):
        with self.assertRaises(errors.UniqueViolation):
            self.new_complaint("TST_CMP1")

    def test_another_customers_account_is_rejected_and_not_saved(self):
        with self.assertRaises(errors.ForeignKeyViolation):
            self.new_complaint("TST_BAD2", customer_id="TST_CUS2", account_id="TST_ACC1")
        self.assertIsNone(self.complaints.get_by_id("TST_BAD2"))

    def test_connection_still_works_after_an_error(self):
        with self.assertRaises(errors.UndefinedTable):
            self.db.run("SELECT * FROM no_such_table", (), fetch="all")
        self.assertTrue(self.db.is_open())
        self.assertIsNotNone(self.customers.get_by_id("TST_CUS1"))

    def test_connection_closes_after_an_error(self):
        db = DatabaseManager()
        with self.assertRaises(RuntimeError):
            try:
                CustomerRepository(db).get_by_id("TST_CUS1")
                raise RuntimeError("something went wrong")
            finally:
                db.close()
        self.assertFalse(db.is_open())


def remove_test_data(db):
    # Children first, because a complaint points at an account and an account points at a customer.
    db.run("DELETE FROM complaint WHERE complaint_id LIKE %s", ("TST\\_%",))
    db.run("DELETE FROM account WHERE account_id LIKE %s", ("TST\\_%",))
    db.run("DELETE FROM customer WHERE customer_id LIKE %s", ("TST\\_%",))


if __name__ == "__main__":
    unittest.main(verbosity=2)
