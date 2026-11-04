from dataclasses import dataclass
from datetime import datetime
from typing import Optional

COLUMNS = ("complaint_id, customer_id, account_id, channel, category, customer_narrative, "
           "priority, status, created_at, assigned_employee_id")


@dataclass
class Complaint:
    complaint_id: str
    customer_id: str
    account_id: Optional[str]
    channel: str
    category: str
    customer_narrative: str
    priority: str
    status: str
    created_at: datetime
    assigned_employee_id: Optional[str]


class ComplaintRepository:
    def __init__(self, db):
        self.db = db

    def get_by_id(self, complaint_id):
        with self.db.transaction() as cur:
            cur.execute(f"SELECT {COLUMNS} FROM complaint WHERE complaint_id = %s", (complaint_id,))
            row = cur.fetchone()
        return Complaint(*row) if row else None

    def get_for_customer(self, customer_id):
        with self.db.transaction() as cur:
            cur.execute(
                f"SELECT {COLUMNS} FROM complaint WHERE customer_id = %s ORDER BY created_at, complaint_id",
                (customer_id,),
            )
            rows = cur.fetchall()
        return [Complaint(*row) for row in rows]

    def create(self, complaint_id, customer_id, channel, category, customer_narrative, priority,
               account_id=None, status="OPEN", created_at=None, assigned_employee_id=None):
        with self.db.transaction() as cur:
            cur.execute(
                f"INSERT INTO complaint ({COLUMNS}) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, CURRENT_TIMESTAMP), %s) "
                f"RETURNING {COLUMNS}",
                (complaint_id, customer_id, account_id, channel, category, customer_narrative,
                 priority, status, created_at, assigned_employee_id),
            )
            row = cur.fetchone()
        return Complaint(*row)
