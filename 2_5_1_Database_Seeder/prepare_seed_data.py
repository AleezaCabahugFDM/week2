"""Convert the project's synthetic data into CSV files that match the 2.1.1 schema.

    python3 prepare_seed_data.py

Reads   data/source/customers.csv, accounts.csv, complaints.csv, service_requests.csv
Writes  data/customers.csv, accounts.csv, complaints.csv, service_requests.csv

The source data uses different names and values from the schema (for example
status 'In Review' instead of 'UNDER_REVIEW'), so they are changed here.
data/employees.csv is not made here: there is no staff file in the source data,
so the 10 employees from the 2.1.1 seed are kept.

If a source value has no mapping below, the script stops and writes nothing.
"""

import csv
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
SOURCE = HERE / "data" / "source"
OUT = HERE / "data"

# source value -> schema value
CUSTOMER_SEGMENT = {"Standard": "Retail", "Premium": "Premier", "Small Business": "Business"}
ACCOUNT_STATUS = {"Active": "ACTIVE", "Inactive": "INACTIVE", "Closed": "CLOSED", "Restricted": "RESTRICTED"}
COMPLAINT_STATUS = {"Open": "OPEN", "In Progress": "IN_PROGRESS", "In Review": "UNDER_REVIEW",
                    "Escalated": "ESCALATED", "Resolved": "RESOLVED", "Closed": "CLOSED"}
REQUEST_STATUS = {"Open": "OPEN", "In Progress": "IN_PROGRESS", "Completed": "CLOSED"}

# Placeholders for required schema columns that the source data does not have.
ACCOUNT_OPEN_DATE = "2025-01-01"      # before the earliest complaint (2026-01-02)
NARRATIVE = "[Placeholder] {category} complaint received by {channel}. The source data has no complaint text."


class MappingError(Exception):
    pass


def mapped(mapping, value, where):
    if value not in mapping:
        raise MappingError(f"{where}: no mapping for value '{value}'")
    return mapping[value]


def iso_date(us_date):
    """Source dates look like 4/28/2026. The schema uses 2026-04-28."""
    return datetime.strptime(us_date, "%m/%d/%Y").strftime("%Y-%m-%d")


def read(name):
    with open(SOURCE / name, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write(name, rows):
    with open(OUT / name, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def convert():
    """Return {file name: list of rows} for the four seed files."""
    customers = []
    for c in read("customers.csv"):
        customers.append({
            "customer_id": c["customer_id"],
            "first_name": c["first_name"],
            "last_name": c["last_name"],
            "email": c["email"],
            "phone_number": "",
            "segment": mapped(CUSTOMER_SEGMENT, c["segment"], c["customer_id"]),
        })

    accounts = []
    for a in read("accounts.csv"):
        accounts.append({
            "account_id": a["account_id"],
            "customer_id": a["customer_id"],
            "account_number": str(100000000 + int(a["account_id"].lstrip("A"))),   # A00042 -> 100000042
            "account_type": a["account_type"],
            "status": mapped(ACCOUNT_STATUS, a["status"], a["account_id"]),
            "balance": f"{float(a['current_balance']):.2f}",
            "open_date": ACCOUNT_OPEN_DATE,
        })

    source_complaints = read("complaints.csv")
    complaints = []
    for c in source_complaints:
        complaints.append({
            "complaint_id": c["complaint_id"],
            "customer_id": c["customer_id"],
            "account_id": c["account_id"],
            "channel": c["channel"],
            "category": c["category"],
            "customer_narrative": NARRATIVE.format(category=c["category"], channel=c["channel"]),
            "priority": c["priority"],
            "status": mapped(COMPLAINT_STATUS, c["status"], c["complaint_id"]),
            "created_at": iso_date(c["date_opened"]) + " 00:00:00",
            "assigned_employee_id": "",
        })

    # The schema has no complaint_id on service_request, so the account is taken from the linked complaint.
    account_of_complaint = {c["complaint_id"]: c["account_id"] for c in source_complaints}
    requests = []
    for r in read("service_requests.csv"):
        status = mapped(REQUEST_STATUS, r["status"], r["request_id"])
        created = iso_date(r["created_date"])
        requests.append({
            "request_id": r["request_id"],
            "customer_id": r["customer_id"],
            "account_id": account_of_complaint.get(r["complaint_id"], ""),
            "request_type": r["request_type"],
            "status": status,
            "created_date": created,
            # The schema needs a closed_date for CLOSED requests and the source has none.
            "closed_date": created if status == "CLOSED" else "",
        })

    return {"customers.csv": customers, "accounts.csv": accounts,
            "complaints.csv": complaints, "service_requests.csv": requests}


def main():
    try:
        outputs = convert()       # convert everything first, so an error writes nothing
    except (MappingError, KeyError, ValueError) as error:
        print(f"ERROR: {error}. Nothing was written.", file=sys.stderr)
        return 1
    for name, rows in outputs.items():
        write(name, rows)
        print(f"wrote data/{name:<22} {len(rows):>4} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
