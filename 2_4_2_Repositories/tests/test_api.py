import os
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from data.database_manager import DatabaseManager
from main import app

client = TestClient(app)
DB_CONFIGURED = all(os.environ.get(k) for k in ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"])
NEW = {"complaint_id": "TST_API2", "customer_id": "TST_API_C1", "channel": "Web",
       "category": "Fee Dispute", "customer_narrative": "Created by API test", "priority": "Low"}


class ConfigApiTests(unittest.TestCase):
    def test_missing_settings_return_500_without_values(self):
        with mock.patch.dict(os.environ, {"DB_PASSWORD": "secret-pw"}, clear=True):
            response = client.get("/customers/CUS001")
        self.assertEqual(response.status_code, 500)
        self.assertIn("DB_HOST", response.json()["detail"])
        self.assertNotIn("secret-pw", response.text)

    def test_unreachable_database_returns_503(self):
        env = {"DB_HOST": "127.0.0.1", "DB_PORT": "1", "DB_NAME": "x", "DB_USER": "u", "DB_PASSWORD": "secret-pw"}
        with mock.patch.dict(os.environ, env):
            response = client.get("/customers/CUS001")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret-pw", response.text)

    def test_invalid_body_returns_422(self):
        env = {"DB_HOST": "127.0.0.1", "DB_PORT": "1", "DB_NAME": "x", "DB_USER": "u", "DB_PASSWORD": "pw"}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(client.post("/complaints", json={"complaint_id": "X"}).status_code, 422)


@unittest.skipUnless(DB_CONFIGURED, "set DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD to run database tests")
class DataApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = DatabaseManager.from_env()
        cls.remove_test_data()
        with cls.db.transaction() as cur:
            cur.execute("INSERT INTO customer VALUES ('TST_API_C1', 'Api', 'One', NULL, NULL, 'Retail'), "
                        "('TST_API_C2', 'Api', 'Two', NULL, NULL, 'Retail')")
            cur.execute("INSERT INTO account VALUES ('TST_API_A1', 'TST_API_C1', 'TST-API-1', 'Savings', "
                        "'ACTIVE', 10.00, '2025-01-01')")
            cur.execute("INSERT INTO complaint VALUES ('TST_API1', 'TST_API_C1', 'TST_API_A1', 'Phone', "
                        "'Fee Dispute', 'Api test', 'High', 'OPEN', '2025-01-02 09:00', NULL)")

    @classmethod
    def tearDownClass(cls):
        cls.remove_test_data()
        cls.db.close()

    @classmethod
    def remove_test_data(cls):
        with cls.db.transaction() as cur:
            for table in ("complaint", "account", "customer"):
                cur.execute(f"DELETE FROM {table} WHERE {table}_id LIKE %s", ("TST\\_API%",))

    def test_get_customer(self):
        response = client.get("/customers/TST_API_C1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["segment"], "Retail")

    def test_get_accounts(self):
        self.assertEqual([a["account_id"] for a in client.get("/customers/TST_API_C1/accounts").json()],
                         ["TST_API_A1"])

    def test_get_complaint_and_customer_complaints(self):
        self.assertEqual(client.get("/complaints/TST_API1").json()["priority"], "High")
        ids = [c["complaint_id"] for c in client.get("/customers/TST_API_C1/complaints").json()]
        self.assertIn("TST_API1", ids)

    def test_missing_records(self):
        self.assertEqual(client.get("/customers/NOPE").status_code, 404)
        self.assertEqual(client.get("/complaints/NOPE").status_code, 404)
        self.assertEqual(client.get("/customers/NOPE/accounts").json(), [])
        self.assertEqual(client.get("/customers/TST_API_C2/complaints").json(), [])

    def test_create_complaint(self):
        response = client.post("/complaints", json=NEW)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["status"], "OPEN")
        self.assertEqual(client.get("/complaints/TST_API2").status_code, 200)

    def test_create_failures(self):
        self.assertEqual(client.post("/complaints", json={**NEW, "complaint_id": "TST_API1"}).status_code, 409)
        self.assertEqual(client.post("/complaints", json={**NEW, "complaint_id": "TST_API3",
                                                          "priority": "Urgent"}).status_code, 422)
        self.assertEqual(client.post("/complaints", json={**NEW, "complaint_id": "TST_API4",
                                                          "customer_id": "TST_API_C2",
                                                          "account_id": "TST_API_A1"}).status_code, 422)
        self.assertEqual(client.get("/complaints/TST_API3").status_code, 404)
        self.assertEqual(client.get("/complaints/TST_API4").status_code, 404)


if __name__ == "__main__":
    unittest.main(verbosity=2)
