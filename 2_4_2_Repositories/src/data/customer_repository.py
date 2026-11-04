from dataclasses import dataclass
from typing import Optional


@dataclass
class Customer:
    customer_id: str
    first_name: str
    last_name: str
    email: Optional[str]
    phone_number: Optional[str]
    segment: str


class CustomerRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, customer_id):
        with self.db.transaction() as cur:
            cur.execute(
                "SELECT customer_id, first_name, last_name, email, phone_number, segment "
                "FROM customer WHERE customer_id = %s",
                (customer_id,),
            )
            row = cur.fetchone()
        return Customer(*row) if row else None
