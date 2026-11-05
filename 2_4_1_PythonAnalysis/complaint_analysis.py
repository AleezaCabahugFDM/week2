# complaint_analysis.py
# Week 2 | Exercise 2.4.1 - Read and analyse complaint data
#
# How to run:
#   python3 complaint_analysis.py complaints.csv
#
# It makes two files:
#   complaint_analysis_output.csv
#   complaint_analysis_summary.md

import csv
import sys
from datetime import datetime


# A date in the file can look like 2026-04-28 or 4/28/2026.
# This gives back a date, or None if the text is not a date.
def read_date(text):
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        pass
    try:
        return datetime.strptime(text, "%m/%d/%Y").date()
    except ValueError:
        return None


# ----- Step 1: open the file and check it -----

if len(sys.argv) < 2:
    print("Usage: python3 complaint_analysis.py complaints.csv")
    sys.exit(1)

file_name = sys.argv[1]

try:
    file = open(file_name, newline="", encoding="utf-8-sig")
except FileNotFoundError:
    print("ERROR: file not found:", file_name)
    sys.exit(1)

reader = csv.DictReader(file)
rows = list(reader)
file.close()

columns = reader.fieldnames or []

# The shared file calls the dates date_opened and date_closed.
# The exercise calls them created_date and resolved_date, so rename them.
for row in rows:
    if "date_opened" in row:
        row["created_date"] = row.pop("date_opened")
    if "date_closed" in row:
        row["resolved_date"] = row.pop("date_closed")
new_columns = []
for column in columns:
    if column == "date_opened":
        column = "created_date"
    if column == "date_closed":
        column = "resolved_date"
    new_columns.append(column)
columns = new_columns

required = ["complaint_id", "customer_id", "category", "status", "created_date", "resolved_date"]
for column in required:
    if column not in columns:
        print("ERROR: missing required column(s):", column)
        sys.exit(1)

if len(rows) == 0:
    print("ERROR: the file has no data rows")
    sys.exit(1)

# Count the empty cells in every column.
missing = {}
for column in columns:
    missing[column] = 0
for row in rows:
    for column in columns:
        if row[column] is None or row[column].strip() == "":
            missing[column] = missing[column] + 1

# Keep the good rows. Skip a row if something important is missing.
good_rows = []
warnings = []
line = 1                     # line 1 is the header
for row in rows:
    line = line + 1

    empty = []
    for column in ["complaint_id", "customer_id", "category", "status", "created_date"]:
        if row[column] is None or row[column].strip() == "":
            empty.append(column)
    if len(empty) > 0:
        warnings.append("line " + str(line) + " skipped: missing " + ", ".join(empty))
        continue

    created = read_date(row["created_date"].strip())
    if created is None:
        warnings.append("line " + str(line) + " skipped: bad created_date '" + row["created_date"] + "'")
        continue

    # Closed means the status is Closed or Resolved (same rule as the SQL in 2.2.2).
    closed = row["status"].strip() in ["Closed", "Resolved"]

    # How many days it took to close. Only for closed complaints with a good date.
    days = None
    if closed:
        resolved = read_date((row["resolved_date"] or "").strip())
        if resolved is not None and resolved >= created:
            days = (resolved - created).days
        else:
            warnings.append("line " + str(line) + " (" + row["complaint_id"] + "): closed but no usable "
                            "resolved_date, not used for resolution time")

    good_rows.append({
        "customer_id": row["customer_id"].strip(),
        "category": row["category"].strip(),
        "status": row["status"].strip(),
        "closed": closed,
        "days": days,
    })

if len(good_rows) == 0:
    print("ERROR: no valid rows, every row was skipped")
    sys.exit(1)

skipped = len(rows) - len(good_rows)
print("Rows read:", len(rows), " valid:", len(good_rows), " skipped:", skipped)
print("Missing values:", missing)
for warning in warnings:
    print("WARNING", warning)


# ----- Step 2: calculate -----

total = len(good_rows)

closed_count = 0
customers = []
status_counts = {}
category_counts = {}
for row in good_rows:
    if row["closed"]:
        closed_count = closed_count + 1
    if row["customer_id"] not in customers:
        customers.append(row["customer_id"])
    status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    category_counts[row["category"]] = category_counts.get(row["category"], 0) + 1

open_count = total - closed_count

# The category with the most complaints.
top_category = max(category_counts, key=category_counts.get)
top_count = category_counts[top_category]
top_percent = round(top_count / total * 100, 1)

# Average days to close, overall and for each category. None means unknown (not 0).
all_days = []
for row in good_rows:
    if row["days"] is not None:
        all_days.append(row["days"])
average_days = None
if len(all_days) > 0:
    average_days = round(sum(all_days) / len(all_days), 1)

closed_by_category = {}
average_by_category = {}
for category in sorted(category_counts):
    days_list = []
    closed_here = 0
    for row in good_rows:
        if row["category"] == category and row["closed"]:
            closed_here = closed_here + 1
            if row["days"] is not None:
                days_list.append(row["days"])
    closed_by_category[category] = closed_here
    if len(days_list) > 0:
        average_by_category[category] = round(sum(days_list) / len(days_list), 1)
    else:
        average_by_category[category] = None


# ----- Step 3: write the output files -----

# The CSV file with all the numbers.
out = open("complaint_analysis_output.csv", "w", newline="", encoding="utf-8")
writer = csv.writer(out)
writer.writerow(["metric", "group", "value"])
writer.writerow(["rows_read", "all", len(rows)])
writer.writerow(["rows_skipped", "all", skipped])
writer.writerow(["complaint_count", "all", total])
writer.writerow(["distinct_customers", "all", len(customers)])
writer.writerow(["open_count", "all", open_count])
writer.writerow(["closed_count", "all", closed_count])
writer.writerow(["highest_volume_category", top_category, top_count])
writer.writerow(["highest_volume_category_pct", top_category, top_percent])
writer.writerow(["avg_resolution_days", "all", average_days])
for status in sorted(status_counts, key=status_counts.get, reverse=True):     # biggest first
    writer.writerow(["complaint_count_by_status", status, status_counts[status]])
for category in sorted(category_counts, key=category_counts.get, reverse=True):     # biggest first
    writer.writerow(["complaint_count_by_category", category, category_counts[category]])
for category in closed_by_category:
    writer.writerow(["closed_count_by_category", category, closed_by_category[category]])
    writer.writerow(["avg_resolution_days_by_category", category, average_by_category[category]])
out.close()


# The Markdown summary for managers.
def show(value):
    if value is None:
        return "unknown"
    return value


md = open("complaint_analysis_summary.md", "w", encoding="utf-8")
md.write("# Complaint Analysis Summary\n\n")
md.write("Week 2 | Exercise 2.4.1 · made by `complaint_analysis.py`, do not edit by hand.\n\n")

md.write("## Headlines\n\n")
md.write(f"- **{total} complaints** from **{len(customers)} customers**. "
         f"**{open_count} ({round(open_count / total * 100, 1)}%) are still open** and "
         f"{closed_count} ({round(closed_count / total * 100, 1)}%) are closed.\n")
md.write(f"- **Highest-volume category: {top_category}** with {top_count} complaints ({top_percent}%).\n")
md.write(f"- **Closed cases took {show(average_days)} days on average.**\n\n")

md.write("## Definitions\n\n")
md.write("Same rules as the SQL metrics in 2.2.2.\n\n")
md.write("- **Open:** status is not `Closed` or `Resolved` (so Open, In Review and Escalated are open).\n")
md.write("- **Closed:** status is `Closed` or `Resolved`.\n")
md.write("- **Resolution days:** `resolved_date` − `created_date`, for closed complaints only.\n")
md.write("- **Unknown:** no closed complaint to measure. Shown as 'unknown', never as 0.\n\n")

md.write("## Load evidence\n\n")
md.write(f"Rows read: {len(rows)} · valid: {total} · skipped: {skipped}\n\n")
md.write("| Column | Missing values |\n|---|---:|\n")
for column in missing:
    md.write(f"| {column} | {missing[column]} |\n")
md.write("\nMissing `resolved_date` is expected for open complaints. Missing `account_id` is allowed.\n\n")
if len(warnings) > 0:
    md.write("**Warnings:**\n\n")
    for warning in warnings:
        md.write(f"- {warning}\n")
    md.write("\n")
else:
    md.write("No rows were skipped and there were no warnings.\n\n")

md.write("## Complaints by status\n\n| Status | Complaints | % |\n|---|---:|---:|\n")
for status in sorted(status_counts, key=status_counts.get, reverse=True):     # biggest first
    md.write(f"| {status} | {status_counts[status]} | {round(status_counts[status] / total * 100, 1)} |\n")

md.write("\n## Complaints by category\n\n| Category | Complaints | % |\n|---|---:|---:|\n")
for category in sorted(category_counts, key=category_counts.get, reverse=True):     # biggest first
    md.write(f"| {category} | {category_counts[category]} | {round(category_counts[category] / total * 100, 1)} |\n")

md.write("\n## Closed-case resolution by category\n\n| Category | Closed | Avg days |\n|---|---:|---:|\n")
for category in closed_by_category:
    md.write(f"| {category} | {closed_by_category[category]} | {show(average_by_category[category])} |\n")
md.write(f"| **All** | {closed_count} | {show(average_days)} |\n\n")

md.write("## Observations\n\n")
md.write(f"1. {top_category} is the largest category at {top_percent}% of complaints.\n")
md.write(f"2. Most complaints are still open ({open_count} of {total}).\n\n")

md.write("## What this analysis does not show\n\n")
md.write("- **No trends.** This is one snapshot, so it can't say if things are getting better or worse.\n")
md.write("- **No causes.** The counts don't explain *why* customers complained.\n")
md.write(f"- **Resolution time only covers closed cases.** The {open_count} open complaints are not included.\n")
md.write("- Some categories have only a few closed cases, so their averages are not reliable.\n")
md.write("- The data is synthetic training data.\n")
md.close()

print("Complaints:", total, " open:", open_count, " closed:", closed_count)
print("Highest-volume category:", top_category, top_count, str(top_percent) + "%")
print("Wrote complaint_analysis_output.csv and complaint_analysis_summary.md")
