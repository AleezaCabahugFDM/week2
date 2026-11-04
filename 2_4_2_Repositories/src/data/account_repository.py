from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass
class Account:
    account_id: str
    customer_id: str
    account_number: str
    account_type: str
    status: str
    balance: Decimal
    open_date: date


class AccountRepository:
    def __init__(self, db):
        self.db = db

    def get_for_customer(self, customer_id):
        with self.db.transaction() as cur:
            cur.execute(
                "SELECT account_id, customer_id, account_number, account_type, status, balance, open_date "
                "FROM account WHERE customer_id = %s ORDER BY account_id",
                (customer_id,),
            )
            rows = cur.fetchall()
        return [Account(*row) for row in rows]
