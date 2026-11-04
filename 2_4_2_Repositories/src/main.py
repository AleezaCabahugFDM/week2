from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from psycopg2 import OperationalError, errors
from pydantic import BaseModel

from data.account_repository import AccountRepository
from data.complaint_repository import ComplaintRepository
from data.customer_repository import CustomerRepository
from data.database_manager import ConfigError, DatabaseManager

app = FastAPI(title="Complaint Data API")


class NewComplaint(BaseModel):
    complaint_id: str
    customer_id: str
    channel: str
    category: str
    customer_narrative: str
    priority: str
    account_id: Optional[str] = None
    status: str = "OPEN"
    created_at: Optional[datetime] = None
    assigned_employee_id: Optional[str] = None


def get_db():
    try:
        db = DatabaseManager.from_env()
    except ConfigError as exc:
        raise HTTPException(500, str(exc))
    try:
        yield db
    except OperationalError:
        raise HTTPException(503, "Database unavailable.")
    finally:
        db.close()


@app.get("/customers/{customer_id}")
def get_customer(customer_id: str, db=Depends(get_db)):
    customer = CustomerRepository(db).get_by_id(customer_id)
    if customer is None:
        raise HTTPException(404, f"Customer {customer_id} not found.")
    return customer


@app.get("/customers/{customer_id}/accounts")
def get_accounts(customer_id: str, db=Depends(get_db)):
    return AccountRepository(db).get_for_customer(customer_id)


@app.get("/customers/{customer_id}/complaints")
def get_customer_complaints(customer_id: str, db=Depends(get_db)):
    return ComplaintRepository(db).get_for_customer(customer_id)


@app.get("/complaints/{complaint_id}")
def get_complaint(complaint_id: str, db=Depends(get_db)):
    complaint = ComplaintRepository(db).get_by_id(complaint_id)
    if complaint is None:
        raise HTTPException(404, f"Complaint {complaint_id} not found.")
    return complaint


@app.post("/complaints", status_code=201)
def create_complaint(body: NewComplaint, db=Depends(get_db)):
    try:
        return ComplaintRepository(db).create(**body.model_dump())
    except errors.UniqueViolation:
        raise HTTPException(409, f"Complaint {body.complaint_id} already exists.")
    except errors.ForeignKeyViolation:
        raise HTTPException(422, "Unknown customer, account or employee, or the account belongs to another customer.")
    except errors.CheckViolation:
        raise HTTPException(422, "Invalid priority or status.")
