"""Complaint analysis - Week 2, Exercise 2.4.1.

Run it with the complaints file:
    python3 complaint_analysis.py complaints.csv

Writes complaint_analysis_output.csv and complaint_analysis_summary.md next to this script.
"""

import csv
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

REQUIRED_COLUMNS = ["complaint_id", "customer_id", "category", "status", "created_date", "resolved_date"]
CLOSED_STATUSES = ["Closed", "Resolved"]      # same rule as the SQL metrics in 2.2.2
OUT_FOLDER = Path(__file__).parent


def parse_date(text):
    """Turn '2026-04-28' or '4/28/2026' into a date. Returns None if it is not a date."""
    for date_format in ["%Y-%m-%d", "%m/%d/%Y"]:
        try:
            return datetime.strptime(text.strip(), date_format).date()
        except ValueError:
            pass
    return None


def percent(part, whole):
    return round(100 * part / whole, 1)


def average(numbers):
    """Average to 1 decimal place, or None if there are no numbers (unknown, not 0)."""
    if not numbers:
        return None
    return round(sum(numbers) / len(numbers), 1)


# ---------- Step 1: load and validate ----------

if len(sys.argv) < 2:
    print("Usage: python3 complaint_analysis.py complaints.csv")
    sys.exit(1)
input_file = Path(sys.argv[1])

if not input_file.is_file():
    print(f"ERROR: file not found: {input_file}")
    sys.exit(1)

with open(input_file, newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    # The shared file calls the date columns date_opened and date_closed.
    reader.fieldnames = [{"date_opened": "created_date", "date_closed": "resolved_date"}.get(name, name)
                         for name in reader.fieldnames or []]
    columns = reader.fieldnames
    rows = list(reader)

missing_columns = [c for c in REQUIRED_COLUMNS if c not in columns]
if missing_columns:
    print(f"ERROR: missing required column(s): {', '.join(missing_columns)}")
    sys.exit(1)
if not rows:
    print("ERROR: the file has no data rows")
    sys.exit(1)

missing_values = {c: 0 for c in columns}
warnings = []
complaints = []

for line, row in enumerate(rows, start=2):      # line 1 is the header
    for c in columns:
        if not (row[c] or "").strip():
            missing_values[c] += 1

    blank = [c for c in REQUIRED_COLUMNS if c != "resolved_date" and not (row[c] or "").strip()]
    created = parse_date(row["created_date"] or "")
    if blank:
        warnings.append(f"line {line} skipped: missing {', '.join(blank)}")
        continue
    if created is None:
        warnings.append(f"line {line} skipped: bad created_date '{row['created_date']}'")
        continue

    is_closed = row["status"].strip() in CLOSED_STATUSES
    resolved = parse_date(row["resolved_date"] or "")
    days = None
    if is_closed and resolved and resolved >= created:
        days = (resolved - created).days
    elif is_closed:
        warnings.append(f"line {line} ({row['complaint_id']}): closed but no usable resolved_date, "
                        "not used for resolution time")

    complaints.append({"customer_id": row["customer_id"].strip(), "category": row["category"].strip(),
                       "status": row["status"].strip(), "is_closed": is_closed,
                       "created": created, "days": days})

if not complaints:
    print("ERROR: no valid rows, every row was skipped")
    sys.exit(1)

print(f"Rows read: {len(rows)}  valid: {len(complaints)}  skipped: {len(rows) - len(complaints)}")
print("Missing values: " + ", ".join(f"{c}={n}" for c, n in missing_values.items()))
for w in warnings:
    print("WARNING", w)


# ---------- Step 2: calculate ----------

total = len(complaints)
closed = [c for c in complaints if c["is_closed"]]
open_count = total - len(closed)
customers = len({c["customer_id"] for c in complaints})
by_status = Counter(c["status"] for c in complaints).most_common()
by_category = Counter(c["category"] for c in complaints).most_common()
top_category, top_count = by_category[0]
top_pct = percent(top_count, total)
avg_days = average([c["days"] for c in closed if c["days"] is not None])

resolution = {}       # category -> (closed count, average days)
for category, _ in sorted(by_category):
    closed_here = [c for c in closed if c["category"] == category]
    resolution[category] = (len(closed_here), average([c["days"] for c in closed_here if c["days"] is not None]))


# ---------- Step 3: write outputs ----------

with open(OUT_FOLDER / "complaint_analysis_output.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["metric", "group", "value"])
    writer.writerow(["rows_read", "all", len(rows)])
    writer.writerow(["rows_skipped", "all", len(rows) - total])
    writer.writerow(["complaint_count", "all", total])
    writer.writerow(["distinct_customers", "all", customers])
    writer.writerow(["open_count", "all", open_count])
    writer.writerow(["closed_count", "all", len(closed)])
    writer.writerow(["highest_volume_category", top_category, top_count])
    writer.writerow(["highest_volume_category_pct", top_category, top_pct])
    writer.writerow(["avg_resolution_days", "all", avg_days])
    for status, n in by_status:
        writer.writerow(["complaint_count_by_status", status, n])
    for category, n in by_category:
        writer.writerow(["complaint_count_by_category", category, n])
    for category, (n, avg) in resolution.items():
        writer.writerow(["closed_count_by_category", category, n])
        writer.writerow(["avg_resolution_days_by_category", category, "" if avg is None else avg])


def show(value):
    return "unknown" if value is None else value


md = [
    "# Complaint Analysis Summary",
    "",
    f"Week 2 | Exercise 2.4.1 · made by `complaint_analysis.py` from `{input_file.name}`, do not edit by hand.",
    "",
    "## Headlines",
    "",
    f"- **{total} complaints** from **{customers} customers**. **{open_count} ({percent(open_count, total)}%) are "
    f"still open** and {len(closed)} ({percent(len(closed), total)}%) are closed.",
    f"- **Highest-volume category: {top_category}** with {top_count} complaints ({top_pct}%).",
    f"- **Closed cases took {show(avg_days)} days on average.**",
    "",
    "## Definitions",
    "",
    "Same rules as the SQL metrics in 2.2.2.",
    "",
    "- **Open:** status is not `Closed` or `Resolved` (so Open, In Review and Escalated are open).",
    "- **Closed:** status is `Closed` or `Resolved`.",
    "- **Resolution days:** `resolved_date` − `created_date`, for closed complaints only.",
    "- **Unknown:** no closed complaint to measure. Shown as 'unknown', never as 0.",
    "",
    "## Load evidence",
    "",
    f"Rows read: {len(rows)} · valid: {total} · skipped: {len(rows) - total}",
    "",
    "| Column | Missing values |",
    "|---|---:|",
]
md += [f"| {c} | {n} |" for c, n in missing_values.items()]
md += ["", "Missing `resolved_date` is expected for open complaints. Missing `account_id` is allowed.", ""]
if warnings:
    md += ["**Warnings:**", ""] + [f"- {w}" for w in warnings] + [""]
else:
    md += ["No rows were skipped and there were no warnings.", ""]

md += ["## Complaints by status", "", "| Status | Complaints | % |", "|---|---:|---:|"]
md += [f"| {s} | {n} | {percent(n, total)} |" for s, n in by_status]
md += ["", "## Complaints by category", "", "| Category | Complaints | % |", "|---|---:|---:|"]
md += [f"| {c} | {n} | {percent(n, total)} |" for c, n in by_category]
md += ["", "## Closed-case resolution by category", "", "| Category | Closed | Avg days |", "|---|---:|---:|"]
md += [f"| {c} | {n} | {show(avg)} |" for c, (n, avg) in resolution.items()]
md += [f"| **All** | {len(closed)} | {show(avg_days)} |"]

md += [
    "",
    "## Observations",
    "",
    f"1. {top_category} is the largest category at {top_pct}% of complaints.",
    f"2. Most complaints are still open ({open_count} of {total}).",
    "",
    "## What this analysis does not show",
    "",
    "- **No trends.** This is one snapshot, so it can't say if things are getting better or worse.",
    "- **No causes.** The counts don't explain *why* customers complained.",
    f"- **Resolution time only covers closed cases.** The {open_count} open complaints are not included.",
    "- Some categories have only a few closed cases, so their averages are not reliable.",
    "- The data is synthetic training data.",
    "",
]
(OUT_FOLDER / "complaint_analysis_summary.md").write_text("\n".join(md), encoding="utf-8")

print(f"Complaints: {total}  open: {open_count}  closed: {len(closed)}")
print(f"Highest-volume category: {top_category} ({top_count}, {top_pct}%)")
print("Wrote complaint_analysis_output.csv and complaint_analysis_summary.md")
