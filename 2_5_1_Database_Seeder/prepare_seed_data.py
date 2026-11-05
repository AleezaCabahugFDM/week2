#!/usr/bin/env python3
"""Convert the project's synthetic source data into seed-ready CSVs.

    python3 prepare_seed_data.py

Reads   data/source/{customers,accounts,complaints,service_requests}.csv
        (the project's synthetic data, unchanged except that the Excel
        accounts sheet was saved as CSV with balances rounded to cents)
Writes  data/{customers,accounts,complaints,service_requests}.csv
        with the column names and allowed values of 2_1_1_schema/database_schema.sql

The schema (the 2.1.1 contract) is not changed. Where the source data uses
different names or values, they are mapped here. Every mapping is listed in
MAPPINGS below and in README_setup.md ("Where the seed data comes from").
data/employees.csv is not produced here: the source set has no staff file, so
the 10 employees from the 2.1.1 seed are kept as they are.

The script refuses to write anything if a source value has no mapping, so a
new value in the source data is noticed instead of being loaded silently.
"""

import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / "data" / "source"
OUT = HERE / "data"

# ---------------------------------------------------------------------------
# Value mappings: source value -> schema value
# ---------------------------------------------------------------------------
CUSTOMER_SEGMENT = {"Standard": "Retail", "Premium": "Premier", "Small Business": "Business"}
ACCOUNT_STATUS = {"Active": "ACTIVE", "Inactive": "INACTIVE", "Closed": "CLOSED", "Restricted": "RESTRICTED"}
COMPLAINT_STATUS = {"Open": "OPEN", "In Progress": "IN_PROGRESS", "In Review": "UNDER_REVIEW",
                    "Escalated": "ESCALATED", "Resolved": "RESOLVED", "Closed": "CLOSED"}
REQUEST_STATUS = {"Open": "OPEN", "In Progress": "IN_PROGRESS", "Completed": "CLOSED"}

# Placeholders for columns the schema requires but the source does not supply.
ACCOUNT_NUMBER_BASE = 100000000   # A00042 -> 100000042 (same 9-digit style as the 2.1.1 seed)
ACCOUNT_OPEN_DATE = "2025-01-01"  # before the earliest complaint (2026-01-02)
NARRATIVE = ("[Placeholder] {category} complaint received by {channel}. "
             "The source data has no complaint text.")

MAPPINGS = {
    "customer.segment": CUSTOMER_SEGMENT,
    "account.status": ACCOUNT_STATUS,
    "complaint.status": COMPLAINT_STATUS,
    "service_request.status": REQUEST_STATUS,
}


class MappingError(Exception):
    pass


def read(name):
    with (SOURCE / name).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write(name, columns, rows):
    with (OUT / name).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def mapped(table_col, value, where):
    table = MAPPINGS[table_col]
    if value not in table:
        raise MappingError(f"{where}: no mapping for {table_col} value '{value}'")
    return table[value]


def iso_date(us_date):
    """Source dates are M/D/YYYY. The schema uses ISO dates."""
    return datetime.strptime(us_date, "%m/%d/%Y").strftime("%Y-%m-%d")


def convert():
    customers = read("customers.csv")
    accounts = read("accounts.csv")
    complaints = read("complaints.csv")
    requests = read("service_requests.csv")
    complaint_by_id = {c["complaint_id"]: c for c in complaints}

    out_customers = [{
        "customer_id": c["customer_id"],
        "first_name": c["first_name"],
        "last_name": c["last_name"],
        "email": c["email"],
        "phone_number": "",
        "segment": mapped("customer.segment", c["segment"], c["customer_id"]),
    } for c in customers]

    out_accounts = [{
        "account_id": a["account_id"],
        "customer_id": a["customer_id"],
        "account_number": str(ACCOUNT_NUMBER_BASE + int(a["account_id"].lstrip("A"))),
        "account_type": a["account_type"],
        "status": mapped("account.status", a["status"], a["account_id"]),
        "balance": f"{float(a['current_balance']):.2f}",
        "open_date": ACCOUNT_OPEN_DATE,
    } for a in accounts]

    out_complaints = [{
        "complaint_id": c["complaint_id"],
        "customer_id": c["customer_id"],
        "account_id": c["account_id"],
        "channel": c["channel"],
        "category": c["category"],
        "customer_narrative": NARRATIVE.format(category=c["category"], channel=c["channel"]),
        "priority": c["priority"],
        "status": mapped("complaint.status", c["status"], c["complaint_id"]),
        "created_at": iso_date(c["date_opened"]) + " 00:00:00",
        "assigned_employee_id": "",
    } for c in complaints]

    out_requests = []
    for r in requests:
        status = mapped("service_request.status", r["status"], r["request_id"])
        created = iso_date(r["created_date"])
        parent = complaint_by_id.get(r["complaint_id"])
        out_requests.append({
            "request_id": r["request_id"],
            "customer_id": r["customer_id"],
            # The schema has no complaint_id on service_request. The account is
            # taken from the linked complaint so the request keeps its account context.
            "account_id": parent["account_id"] if parent else "",
            "request_type": r["request_type"],
            "status": status,
            "created_date": created,
            # The schema requires a closed_date for CLOSED requests and the source has none.
            "closed_date": created if status == "CLOSED" else "",
        })

    return {
        "customers.csv": (list(out_customers[0]), out_customers),
        "accounts.csv": (list(out_accounts[0]), out_accounts),
        "complaints.csv": (list(out_complaints[0]), out_complaints),
        "service_requests.csv": (list(out_requests[0]), out_requests),
    }, data_quality_notes(complaints, requests, complaint_by_id)


def data_quality_notes(complaints, requests, complaint_by_id):
    """Source issues that are reported, not changed."""
    notes = []
    early = [r["request_id"] for r in requests
             if r["complaint_id"] in complaint_by_id
             and datetime.strptime(r["created_date"], "%m/%d/%Y")
             < datetime.strptime(complaint_by_id[r["complaint_id"]]["date_opened"], "%m/%d/%Y")]
    if early:
        notes.append(f"{len(early)} of {len(requests)} service requests are dated before their linked "
                     f"complaint was opened (e.g. {', '.join(early[:3])}). Dates are kept as given.")
    mismatch = [r["request_id"] for r in requests
                if r["complaint_id"] in complaint_by_id
                and complaint_by_id[r["complaint_id"]]["customer_id"] != r["customer_id"]]
    if mismatch:
        notes.append(f"service requests whose customer differs from their complaint's customer: "
                     f"{', '.join(mismatch)}")
    no_account = sum(1 for c in complaints if not c["account_id"])
    notes.append(f"{no_account} complaints have no account_id. That is valid: general complaints are allowed.")
    return notes


def main():
    try:
        outputs, notes = convert()
    except (MappingError, KeyError, ValueError) as exc:
        print(f"ERROR: {exc}. Nothing was written.", file=sys.stderr)
        return 1
    for name, (columns, rows) in outputs.items():
        write(name, columns, rows)
        print(f"wrote data/{name:<22} {len(rows):>4} rows")
    statuses = Counter(r["status"] for r in outputs["complaints.csv"][1])
    print("complaint statuses:", dict(sorted(statuses.items())))
    for note in notes:
        print("NOTE:", note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
