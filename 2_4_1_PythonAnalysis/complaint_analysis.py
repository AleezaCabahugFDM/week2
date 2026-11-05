"""Complaint analysis - Week 2, Exercise 2.4.1.

Reads a complaints CSV, checks it, and writes two files:
    complaint_analysis_output.csv   the calculated numbers
    complaint_analysis_summary.md   a short summary for managers

Run it:
    python3 complaint_analysis.py                  (uses complaints.csv in this folder)
    python3 complaint_analysis.py other_file.csv
"""

import csv
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent

REQUIRED_COLUMNS = ["complaint_id", "customer_id", "category", "status", "created_date", "resolved_date"]

# The shared file uses different names for the two date columns.
RENAMED_COLUMNS = {"date_opened": "created_date", "date_closed": "resolved_date"}

# Same rule as the SQL metrics (2.2.2): only Closed and Resolved count as closed.
CLOSED_STATUSES = ["Closed", "Resolved"]


class AnalysisError(Exception):
    """A problem that stops the analysis (missing file, missing column, no valid rows)."""


def parse_date(text):
    """Turn '2026-04-28' or '4/28/2026' into a date. Returns None if it is not a date."""
    for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            pass
    return None


# ---------- Step 1: load and validate ----------

def load_complaints(path):
    """Read the CSV. Returns (good_rows, evidence). Bad rows are skipped with a warning."""
    path = Path(path)
    if not path.is_file():
        raise AnalysisError(f"Input file not found: {path}")

    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        columns = [RENAMED_COLUMNS.get(name, name) for name in (reader.fieldnames or [])]
        reader.fieldnames = columns
        raw_rows = list(reader)

    missing_columns = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing_columns:
        raise AnalysisError(f"Missing required column(s): {', '.join(missing_columns)}")
    if not raw_rows:
        raise AnalysisError("The file has a header but no data rows.")

    missing_values = {c: 0 for c in columns}
    warnings = []
    good_rows = []

    for line_number, row in enumerate(raw_rows, start=2):   # line 1 is the header
        for column in columns:
            if not (row.get(column) or "").strip():
                missing_values[column] += 1

        complaint_id = (row.get("complaint_id") or "").strip() or "(blank)"
        blanks = [c for c in REQUIRED_COLUMNS if c != "resolved_date" and not (row.get(c) or "").strip()]
        if blanks:
            warnings.append(f"line {line_number} ({complaint_id}) skipped: missing {', '.join(blanks)}")
            continue

        created = parse_date(row["created_date"].strip())
        if created is None:
            warnings.append(f"line {line_number} ({complaint_id}) skipped: bad created_date '{row['created_date']}'")
            continue

        is_closed = row["status"].strip() in CLOSED_STATUSES
        resolved = parse_date((row["resolved_date"] or "").strip())
        if is_closed and resolved is None:
            warnings.append(f"line {line_number} ({complaint_id}): closed but no valid resolved_date, "
                            "so it is not used for resolution time")
        if resolved is not None and resolved < created:
            warnings.append(f"line {line_number} ({complaint_id}): resolved before created, "
                            "so it is not used for resolution time")
            resolved = None

        good_rows.append({
            "complaint_id": complaint_id,
            "customer_id": row["customer_id"].strip(),
            "category": row["category"].strip(),
            "status": row["status"].strip(),
            "is_closed": is_closed,
            "created_date": created,
            "resolved_date": resolved if is_closed else None,
        })

    if not good_rows:
        raise AnalysisError(f"No valid rows: all {len(raw_rows)} row(s) were skipped.")

    evidence = {
        "file": path.name,
        "columns": columns,
        "rows_read": len(raw_rows),
        "rows_skipped": len(raw_rows) - len(good_rows),
        "missing_values": missing_values,
        "warnings": warnings,
    }
    return good_rows, evidence


# ---------- Step 2: calculate ----------

def percent(part, whole):
    return round(100 * part / whole, 1)


def count_by(rows, column):
    """Count rows per value, biggest first. Example: {'Open': 24, 'Closed': 34}."""
    counts = {}
    for row in rows:
        counts[row[column]] = counts.get(row[column], 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def average_resolution_days(rows):
    """Average days from created to resolved, for closed rows with a resolved date. None if there are none."""
    days = [(r["resolved_date"] - r["created_date"]).days for r in rows if r["resolved_date"]]
    if not days:
        return None, 0
    return round(sum(days) / len(days), 1), len(days)


def summarise(rows):
    total = len(rows)
    closed = [r for r in rows if r["is_closed"]]
    categories = count_by(rows, "category")
    top_category = list(categories)[0]

    resolution_by_category = {}
    for category in sorted(categories):
        closed_in_category = [r for r in closed if r["category"] == category]
        avg, measured = average_resolution_days(closed_in_category)
        resolution_by_category[category] = {"closed": len(closed_in_category), "measured": measured, "avg": avg}

    overall_avg, overall_measured = average_resolution_days(closed)
    return {
        "total": total,
        "customers": len({r["customer_id"] for r in rows}),
        "open": total - len(closed),
        "closed": len(closed),
        "statuses": count_by(rows, "status"),
        "categories": categories,
        "top_category": top_category,
        "top_count": categories[top_category],
        "top_pct": percent(categories[top_category], total),
        "avg_resolution": overall_avg,
        "measured": overall_measured,
        "resolution_by_category": resolution_by_category,
        "first_date": min(r["created_date"] for r in rows),
        "last_date": max(r["created_date"] for r in rows),
    }


# ---------- Step 3: write outputs ----------

def measures(s, evidence):
    """All the numbers as rows for the output CSV."""
    rows = [
        ["rows_read", "load", "all", evidence["rows_read"], "rows"],
        ["rows_skipped", "load", "all", evidence["rows_skipped"], "rows"],
        ["complaint_count", "overall", "all", s["total"], "complaints"],
        ["distinct_customers", "overall", "all", s["customers"], "customers"],
        ["open_count", "overall", "all", s["open"], "complaints"],
        ["closed_count", "overall", "all", s["closed"], "complaints"],
        ["highest_volume_category_count", "category", s["top_category"], s["top_count"], "complaints"],
        ["highest_volume_category_pct", "category", s["top_category"], s["top_pct"], "percent"],
        ["avg_resolution_days", "overall", "all", s["avg_resolution"], "days"],
    ]
    for status, n in s["statuses"].items():
        rows.append(["complaint_count", "status", status, n, "complaints"])
    for category, n in s["categories"].items():
        rows.append(["complaint_count", "category", category, n, "complaints"])
        rows.append(["complaint_pct", "category", category, percent(n, s["total"]), "percent"])
    for category, r in s["resolution_by_category"].items():
        rows.append(["closed_count", "category", category, r["closed"], "complaints"])
        rows.append(["avg_resolution_days", "category", category, r["avg"], "days"])

    # A missing average is written as a blank cell: it means "unknown", not 0 days.
    for row in rows:
        if row[3] is None:
            row[3] = ""
    return rows


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "dimension", "dimension_value", "value", "unit"])
        writer.writerows(rows)


def show(value):
    return "unknown" if value is None else value


def summary_markdown(s, evidence):
    lines = [
        "# Complaint Analysis Summary",
        "",
        "Week 2 | Exercise 2.4.1 · made by `complaint_analysis.py`, do not edit by hand.",
        "",
        f"**Input:** `{evidence['file']}` · **Rows read:** {evidence['rows_read']} · "
        f"**Rows analysed:** {s['total']} · **Rows skipped:** {evidence['rows_skipped']}",
        f"**Complaints opened between:** {s['first_date']} and {s['last_date']}",
        "",
        "## Headlines",
        "",
        f"- **{s['total']} complaints** from **{s['customers']} customers**. "
        f"**{s['open']} ({percent(s['open'], s['total'])}%) are still open** and "
        f"{s['closed']} ({percent(s['closed'], s['total'])}%) are closed.",
        f"- **Highest-volume category: {s['top_category']}** with {s['top_count']} complaints "
        f"({s['top_pct']}% of all complaints).",
        f"- **Closed cases took {show(s['avg_resolution'])} days on average**, "
        f"based on {s['measured']} closed complaints.",
        "",
        "## Definitions",
        "",
        "Same rules as the SQL metrics in Exercise 2.2.2.",
        "",
        "| Term | Meaning |",
        "|---|---|",
        "| Open | Status is not `Closed` or `Resolved` (Open, In Review and Escalated are all open). |",
        "| Closed | Status is `Closed` or `Resolved`. |",
        "| Percentage | Count ÷ complaints analysed × 100, to 1 decimal place. |",
        "| Resolution days | `resolved_date` − `created_date` in days, for **closed complaints only**. |",
        "| Unknown | There is no closed complaint to measure. Shown as 'unknown', **never as 0**. |",
        "",
        "## Load evidence",
        "",
        f"Columns found: `{', '.join(evidence['columns'])}` "
        "(`date_opened` and `date_closed` are read as `created_date` and `resolved_date`).",
        "",
        "| Column | Missing values |",
        "|---|---:|",
    ]
    for column, n in evidence["missing_values"].items():
        lines.append(f"| {column} | {n} |")
    lines += ["", "Missing `resolved_date` is expected for open complaints. Missing `account_id` is allowed.", ""]
    if evidence["warnings"]:
        lines += ["**Warnings:**", ""] + [f"- {w}" for w in evidence["warnings"]] + [""]
    else:
        lines += ["No rows were skipped and there were no warnings.", ""]

    lines += ["## Complaints by status", "", "| Status | Complaints | % |", "|---|---:|---:|"]
    for status, n in s["statuses"].items():
        lines.append(f"| {status} | {n} | {percent(n, s['total'])} |")

    lines += ["", "## Complaints by category", "", "| Category | Complaints | % |", "|---|---:|---:|"]
    for category, n in s["categories"].items():
        lines.append(f"| {category} | {n} | {percent(n, s['total'])} |")

    lines += ["", "## Closed-case resolution by category", "",
              "| Category | Closed | Avg days |", "|---|---:|---:|"]
    for category, r in s["resolution_by_category"].items():
        lines.append(f"| {category} | {r['closed']} | {show(r['avg'])} |")
    lines.append(f"| **All** | {s['closed']} | {show(s['avg_resolution'])} |")

    measured = {c: r for c, r in s["resolution_by_category"].items() if r["avg"] is not None}
    lines += ["", "## Observations", "",
              f"1. {s['top_category']} is the largest category at {s['top_pct']}% of complaints.",
              f"2. Most complaints are still open ({s['open']} of {s['total']})."]
    if measured:
        slowest = max(measured, key=lambda c: measured[c]["avg"])
        fastest = min(measured, key=lambda c: measured[c]["avg"])
        lines.append(f"3. Among closed cases, {slowest} took longest on average "
                     f"({measured[slowest]['avg']} days) and {fastest} was quickest ({measured[fastest]['avg']} days).")
    lines += [
        "",
        "## What this analysis does not show",
        "",
        "- **No trends.** This is one snapshot, so it says nothing about whether things are getting better or worse.",
        "- **No causes.** The counts do not explain *why* customers complained.",
        f"- **Resolution time only covers closed cases.** The {s['open']} open complaints are not included.",
        "- Some categories have only a few closed cases, so their averages are not reliable.",
        "- The data is synthetic training data.",
        "",
    ]
    return "\n".join(lines)


# ---------- Run ----------

def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    input_path = Path(args[0]) if args else HERE / "complaints.csv"
    out_dir = Path(args[1]) if len(args) > 1 else HERE

    try:
        rows, evidence = load_complaints(input_path)
    except AnalysisError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Loaded {evidence['file']}: {evidence['rows_read']} rows read, "
          f"{len(rows)} valid, {evidence['rows_skipped']} skipped")
    print("Missing values: " + ", ".join(f"{c}={n}" for c, n in evidence["missing_values"].items()))
    for warning in evidence["warnings"]:
        print(f"WARNING {warning}", file=sys.stderr)

    s = summarise(rows)
    write_csv(out_dir / "complaint_analysis_output.csv", measures(s, evidence))
    (out_dir / "complaint_analysis_summary.md").write_text(summary_markdown(s, evidence), encoding="utf-8")

    print(f"Complaints: {s['total']}  open: {s['open']}  closed: {s['closed']}")
    print(f"Highest-volume category: {s['top_category']} ({s['top_count']}, {s['top_pct']}%)")
    print(f"Wrote {out_dir / 'complaint_analysis_output.csv'}")
    print(f"Wrote {out_dir / 'complaint_analysis_summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
