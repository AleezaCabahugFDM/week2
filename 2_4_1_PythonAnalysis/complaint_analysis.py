"""Complaint analysis - Week 2 | Exercise 2.4.1.

Validates complaint data and produces evidence-based summaries.
Standard library only (Python 3.9+), no pandas needed.

    python3 complaint_analysis.py ~/Downloads/complaints.xlsx   # the shared file (.xlsx or .csv)
    python3 complaint_analysis.py complaints.csv --out-dir results/
    python3 complaint_analysis.py --self-test                   # missing-file / incomplete-row tests

Input may be .csv or .xlsx (first worksheet; Excel date serials become ISO dates).
With no input argument the script looks for complaints.csv next to this file.

Outputs (in --out-dir, default: this folder):
    complaint_analysis_output.csv   calculated measures (one row per measure)
    complaint_analysis_summary.md   management summary with definitions and load evidence

Exit codes:
    0  success (warnings about incomplete rows may still be printed)
    2  input file missing or unreadable
    3  file readable but unusable (missing required columns, no data rows,
       or no valid rows after validation)

Definitions follow Exercise 2.2.2 (complaint_metrics.sql):
    open / backlog  = status is NOT Closed or Resolved
    closed          = status is Closed or Resolved
    resolution days = resolved_date - created_date, closed complaints ONLY
    a category with no measurable closed case has resolution = blank (unknown), NOT 0
    closed complaints with no usable resolved_date are counted separately, not dropped
"""

import argparse
import contextlib
import csv
import io
import re
import statistics
import sys
import tempfile
import zipfile
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent

REQUIRED_COLUMNS = [
    "complaint_id",
    "customer_id",
    "category",
    "status",
    "created_date",
    "resolved_date",
]

# The shared file names the two date columns differently from the requirement.
# The mapping is explicit and reported in the load evidence, never silent.
COLUMN_ALIASES = {
    "date_opened": "created_date",
    "date_closed": "resolved_date",
}

# Columns that must have a value for a row to be analysed.
# resolved_date may be blank: open complaints have not been resolved.
REQUIRED_VALUES = ["complaint_id", "customer_id", "category", "status", "created_date"]

CLOSED_STATUSES = {"closed", "resolved"}
SMALL_SAMPLE = 5  # fewer measured closed cases than this -> flagged in the summary

OUTPUT_CSV = "complaint_analysis_output.csv"
OUTPUT_MD = "complaint_analysis_summary.md"


class AnalysisError(Exception):
    """A controlled failure: printed as a clear message, mapped to an exit code."""

    def __init__(self, message, exit_code):
        super().__init__(message)
        self.exit_code = exit_code


# ---------------------------------------------------------------------------
# Step 1 - load and validate
# ---------------------------------------------------------------------------

def parse_date(text):
    """ISO YYYY-MM-DD -> date, or None if blank/invalid."""
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


XLSX_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
EXCEL_EPOCH = date(1899, 12, 30)  # Excel day 0 (allows for Excel's 1900 leap-year bug)
DATE_COLUMNS = {"created_date", "resolved_date", "date_opened", "date_closed"}


def read_xlsx_rows(path):
    """First worksheet of an .xlsx as a list of string lists (header first).

    Blank cells stay blank. Excel serial numbers in date columns become YYYY-MM-DD;
    anything else is passed through unchanged so validation can reject it.
    """
    def col_index(ref):
        n = 0
        for ch in re.match(r"[A-Z]+", ref).group(0):
            n = n * 26 + ord(ch) - 64
        return n - 1

    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            for si in ET.fromstring(zf.read("xl/sharedStrings.xml")).iter(f"{XLSX_NS}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{XLSX_NS}t")))
        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))

    rows = []
    for row in sheet.iter(f"{XLSX_NS}row"):
        cells = {}
        for c in row.iter(f"{XLSX_NS}c"):
            v = c.find(f"{XLSX_NS}v")
            if c.get("t") == "s" and v is not None:
                text = shared[int(v.text)]
            elif c.get("t") == "inlineStr":
                text = "".join(t.text or "" for t in c.iter(f"{XLSX_NS}t"))
            else:
                text = v.text if v is not None and v.text is not None else ""
            cells[col_index(c.get("r"))] = text
        rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])

    if rows:
        date_idx = {i for i, h in enumerate(rows[0]) if h.strip().lower() in DATE_COLUMNS}
        for r in rows[1:]:
            for i in date_idx:
                if i < len(r) and re.fullmatch(r"\d+(\.0+)?", r[i]):
                    r[i] = (EXCEL_EPOCH + timedelta(days=int(float(r[i])))).isoformat()
    return rows


def load_complaints(path):
    """Read and validate a complaint .csv or .xlsx. Returns (valid_rows, evidence).

    Raises AnalysisError for a missing/unreadable file or unusable structure.
    Incomplete rows are excluded with a recorded reason; they do not stop the run.
    """
    path = Path(path)
    if not path.exists():
        raise AnalysisError(f"Input file not found: {path}", 2)
    if not path.is_file():
        raise AnalysisError(f"Input path is not a file: {path}", 2)

    try:
        if path.suffix.lower() == ".xlsx":
            all_rows = read_xlsx_rows(path)
        else:
            with path.open(newline="", encoding="utf-8-sig") as fh:
                all_rows = list(csv.reader(fh))
    except (OSError, UnicodeDecodeError, csv.Error, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise AnalysisError(f"Could not read {path}: {exc}", 2) from exc
    raw_header = all_rows[0] if all_rows else None
    raw_rows = all_rows[1:]

    if not raw_header:
        raise AnalysisError(f"{path} is empty (no header row).", 3)

    header = [h.strip() for h in raw_header]
    aliases_applied = {}
    normalised = []
    for name in header:
        key = name.lower()
        if key in COLUMN_ALIASES and COLUMN_ALIASES[key] not in [h.lower() for h in header]:
            aliases_applied[name] = COLUMN_ALIASES[key]
            normalised.append(COLUMN_ALIASES[key])
        else:
            normalised.append(key)

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in normalised]
    if missing_cols:
        raise AnalysisError(
            f"{path} is missing required column(s): {', '.join(missing_cols)}. "
            f"Found: {', '.join(header)}",
            3,
        )

    # Blank lines in a CSV are ignored rather than counted as incomplete rows.
    # Keep the real file line number (header = line 1) so warnings point to the right line.
    raw_rows = [(i + 2, r) for i, r in enumerate(raw_rows) if any(cell.strip() for cell in r)]
    if not raw_rows:
        raise AnalysisError(f"{path} has a header but no data rows.", 3)

    evidence = {
        "path": str(path),
        "columns": header,
        "aliases_applied": aliases_applied,
        "rows_read": len(raw_rows),
        "missing_values": Counter({c: 0 for c in normalised}),
        "excluded": [],   # (line_no, complaint_id, reason)
        "warnings": [],   # (line_no, complaint_id, message) - row kept
    }

    seen_ids = set()
    valid = []
    for line_no, cells in raw_rows:
        if len(cells) != len(normalised):
            # Short rows are padded so their missing fields are counted;
            # extra cells cannot be attributed to a column, so they are dropped and flagged.
            if len(cells) > len(normalised):
                evidence["warnings"].append(
                    (line_no, cells[0].strip() if cells else "",
                     f"{len(cells) - len(normalised)} extra cell(s) ignored")
                )
            cells = (cells + [""] * len(normalised))[: len(normalised)]
        row = {name: value.strip() for name, value in zip(normalised, cells)}
        cid = row["complaint_id"] or "(blank)"

        for name, value in row.items():
            if value == "":
                evidence["missing_values"][name] += 1

        blanks = [c for c in REQUIRED_VALUES if row[c] == ""]
        if blanks:
            evidence["excluded"].append((line_no, cid, f"missing {', '.join(blanks)}"))
            continue

        created = parse_date(row["created_date"])
        if created is None:
            evidence["excluded"].append(
                (line_no, cid, f"invalid created_date '{row['created_date']}' (expected YYYY-MM-DD)")
            )
            continue

        if row["complaint_id"] in seen_ids:
            evidence["excluded"].append((line_no, cid, "duplicate complaint_id (first occurrence kept)"))
            continue
        seen_ids.add(row["complaint_id"])

        is_closed = row["status"].lower() in CLOSED_STATUSES
        resolved = None
        if row["resolved_date"]:
            resolved = parse_date(row["resolved_date"])
            if resolved is None:
                evidence["warnings"].append(
                    (line_no, cid, f"invalid resolved_date '{row['resolved_date']}'; "
                                   "row counted, excluded from resolution time")
                )
            elif resolved < created:
                evidence["warnings"].append(
                    (line_no, cid, f"resolved_date {resolved} is before created_date {created}; "
                                   "row counted, excluded from resolution time")
                )
                resolved = None
            elif not is_closed:
                evidence["warnings"].append(
                    (line_no, cid, f"status '{row['status']}' is not closed but has a resolved_date; "
                                   "date ignored")
                )
                resolved = None
        elif is_closed:
            evidence["warnings"].append(
                (line_no, cid, "closed with no resolved_date; counted as closed, "
                               "resolution time unmeasurable")
            )

        valid.append({
            "complaint_id": row["complaint_id"],
            "customer_id": row["customer_id"],
            "category": row["category"],
            "status": row["status"],
            "created_date": created,
            "resolved_date": resolved,
            "is_closed": is_closed,
        })

    evidence["rows_valid"] = len(valid)
    if not valid:
        raise AnalysisError(
            f"No valid rows in {path}: all {len(raw_rows)} row(s) were excluded "
            f"(first reason: {evidence['excluded'][0][2]}).",
            3,
        )
    return valid, evidence


# ---------------------------------------------------------------------------
# Step 2 - calculate summaries
# ---------------------------------------------------------------------------

def pct(part, whole):
    return round(100.0 * part / whole, 1) if whole else None


def summarise(rows):
    total = len(rows)
    status_counts = Counter(r["status"] for r in rows)
    category_counts = Counter(r["category"] for r in rows)
    closed = [r for r in rows if r["is_closed"]]

    top_count = max(category_counts.values())
    top_categories = sorted(c for c, n in category_counts.items() if n == top_count)

    def resolution_stats(group):
        measured = [(r["resolved_date"] - r["created_date"]).days
                    for r in group if r["resolved_date"] is not None]
        return {
            "closed_count": len(group),
            "measured_count": len(measured),
            "unmeasurable_count": len(group) - len(measured),
            "avg": round(float(statistics.mean(measured)), 1) if measured else None,
            "median": round(float(statistics.median(measured)), 1) if measured else None,
            "min": min(measured) if measured else None,
            "max": max(measured) if measured else None,
        }

    resolution_by_category = {
        cat: resolution_stats([r for r in closed if r["category"] == cat])
        for cat in sorted(category_counts)
    }

    return {
        "total": total,
        "distinct_customers": len({r["customer_id"] for r in rows}),
        "open_count": total - len(closed),
        "closed_count": len(closed),
        "status_counts": status_counts,
        "category_counts": category_counts,
        "top_categories": top_categories,
        "top_count": top_count,
        "top_pct": pct(top_count, total),
        "resolution_overall": resolution_stats(closed),
        "resolution_by_category": resolution_by_category,
        "created_min": min(r["created_date"] for r in rows),
        "created_max": max(r["created_date"] for r in rows),
    }


def ordered(counter):
    """Largest first, ties alphabetical - stable, reproducible output."""
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


# ---------------------------------------------------------------------------
# Step 3 - write outputs
# ---------------------------------------------------------------------------

def measure_rows(s, evidence):
    """Long format, same shape as the 2.2.2 SQL summary: metric/dimension/value/unit."""
    out = []

    def add(metric, dimension, value_of, value, unit, note=""):
        out.append({
            "metric": metric, "dimension": dimension, "dimension_value": value_of,
            "value": "" if value is None else value, "unit": unit, "note": note,
        })

    add("rows_read", "load", "all", evidence["rows_read"], "rows")
    add("rows_excluded", "load", "all", len(evidence["excluded"]), "rows",
        "incomplete or invalid; see summary")
    add("rows_with_warnings", "load", "all", len({w[0] for w in evidence["warnings"]}), "rows")
    add("complaint_count", "overall", "all", s["total"], "complaints", "valid rows only")
    add("distinct_customers", "overall", "all", s["distinct_customers"], "customers")
    add("open_count", "overall", "all", s["open_count"], "complaints", "status not Closed/Resolved")
    add("open_pct", "overall", "all", pct(s["open_count"], s["total"]), "percent")
    add("closed_count", "overall", "all", s["closed_count"], "complaints")
    add("closed_pct", "overall", "all", pct(s["closed_count"], s["total"]), "percent")

    for status, n in ordered(s["status_counts"]):
        add("complaint_count", "status", status, n, "complaints")
        add("complaint_pct", "status", status, pct(n, s["total"]), "percent")

    for cat, n in ordered(s["category_counts"]):
        add("complaint_count", "category", cat, n, "complaints")
        add("complaint_pct", "category", cat, pct(n, s["total"]), "percent")

    tie = "tie" if len(s["top_categories"]) > 1 else ""
    for cat in s["top_categories"]:
        add("highest_volume_category_count", "category", cat, s["top_count"], "complaints", tie)
        add("highest_volume_category_pct", "category", cat, s["top_pct"], "percent", tie)

    def add_resolution(dimension, value_of, r):
        note = ""
        if r["measured_count"] == 0:
            note = "no measured closed cases: unknown, not 0"
        elif r["measured_count"] < SMALL_SAMPLE:
            note = f"small sample (n={r['measured_count']})"
        add("closed_count", dimension, value_of, r["closed_count"], "complaints")
        add("resolution_measured_count", dimension, value_of, r["measured_count"], "complaints")
        add("resolution_unmeasurable_count", dimension, value_of, r["unmeasurable_count"], "complaints",
            "closed but no usable resolved_date" if r["unmeasurable_count"] else "")
        add("avg_resolution_days", dimension, value_of, r["avg"], "days", note)
        add("median_resolution_days", dimension, value_of, r["median"], "days", note)
        add("min_resolution_days", dimension, value_of, r["min"], "days")
        add("max_resolution_days", dimension, value_of, r["max"], "days")

    add_resolution("overall", "all", s["resolution_overall"])
    for cat, r in s["resolution_by_category"].items():
        add_resolution("category", cat, r)
    return out


def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fmt(value, suffix=""):
    return "unknown" if value is None else f"{value}{suffix}"


def build_markdown(s, evidence, input_name):
    ro = s["resolution_overall"]
    top = " and ".join(s["top_categories"])
    lines = [
        "# Complaint Analysis Summary",
        "",
        "Week 2 | Exercise 2.4.1 · generated by `complaint_analysis.py`, do not edit by hand.",
        "",
        f"**Input:** `{input_name}` · **Rows read:** {evidence['rows_read']} · "
        f"**Rows analysed:** {s['total']} · **Rows excluded:** {len(evidence['excluded'])}",
        f"**Complaints opened between:** {s['created_min']} and {s['created_max']} (one snapshot)",
        "",
        "## Headlines",
        "",
        f"- **{s['total']} complaints** from **{s['distinct_customers']} customers**. "
        f"**{s['open_count']} ({pct(s['open_count'], s['total'])}%) are still open** and "
        f"{s['closed_count']} ({pct(s['closed_count'], s['total'])}%) are closed.",
        f"- **Highest-volume category: {top}** with {s['top_count']} complaints "
        f"({s['top_pct']}% of analysed complaints)"
        + (" (tied)." if len(s["top_categories"]) > 1 else "."),
        f"- **Closed cases took {fmt(ro['avg'])} days on average** "
        f"(median {fmt(ro['median'])}, range {fmt(ro['min'])}–{fmt(ro['max'])}) "
        f"across {ro['measured_count']} measured closed complaints.",
        "",
        "## Definitions",
        "",
        "Same rules as the SQL metrics in Exercise 2.2.2.",
        "",
        "| Term | Definition |",
        "|---|---|",
        "| Complaint count | Number of valid rows (one row per complaint). Excluded rows are not counted. |",
        "| Open | Status is not `Closed` or `Resolved` (so Open, In Review and Escalated are all open). |",
        "| Closed | Status is `Closed` or `Resolved`. |",
        "| Percentage | Count ÷ complaints analysed × 100, to 1 decimal place. |",
        "| Resolution days | `resolved_date` − `created_date` in whole calendar days, **closed complaints only**. |",
        "| Unknown | No measurable closed case. This is shown as blank or 'unknown', **never as 0**. |",
        f"| Small sample | Fewer than {SMALL_SAMPLE} measured closed cases. The average is shown but should not be relied on. |",
        "",
        "## Load evidence",
        "",
        f"Columns found: `{', '.join(evidence['columns'])}`",
        "",
    ]
    if evidence["aliases_applied"]:
        mapped = ", ".join(f"`{k}` → `{v}`" for k, v in evidence["aliases_applied"].items())
        lines += [f"Column names mapped to the required names: {mapped}.", ""]

    lines += ["| Column | Missing values | Meaning |", "|---|---|---|"]
    meaning = {
        "resolved_date": "Expected for open complaints",
        "account_id": "Optional (not every complaint is tied to an account)",
    }
    for col, n in evidence["missing_values"].items():
        req = "Required" if col in REQUIRED_VALUES else meaning.get(col, "Optional")
        lines.append(f"| {col} | {n} | {req} |")
    lines.append("")

    if evidence["excluded"]:
        lines += ["**Excluded rows:**", "", "| Line | complaint_id | Reason |", "|---|---|---|"]
        lines += [f"| {ln} | {cid} | {why} |" for ln, cid, why in evidence["excluded"]]
        lines.append("")
    else:
        lines += ["No rows were excluded: every row has all required values and a valid created_date.", ""]
    if evidence["warnings"]:
        lines += ["**Warnings (row kept):**", "", "| Line | complaint_id | Warning |", "|---|---|---|"]
        lines += [f"| {ln} | {cid} | {msg} |" for ln, cid, msg in evidence["warnings"]]
        lines.append("")
    else:
        lines += ["No data-consistency warnings: every closed complaint has a valid resolved_date "
                  "on or after its created_date, and no open complaint has a resolved_date.", ""]

    lines += ["## Status", "", "| Status | Complaints | % |", "|---|---:|---:|"]
    lines += [f"| {k} | {n} | {pct(n, s['total'])} |" for k, n in ordered(s["status_counts"])]
    lines += ["", "## Category", "", "| Category | Complaints | % |", "|---|---:|---:|"]
    lines += [f"| {k} | {n} | {pct(n, s['total'])} |" for k, n in ordered(s["category_counts"])]

    lines += [
        "",
        "## Closed-case resolution by category",
        "",
        "| Category | Closed | Measured | Avg days | Median | Min | Max | Note |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    small = []
    for cat, r in sorted(s["resolution_by_category"].items(),
                         key=lambda kv: (kv[1]["avg"] is None, -(kv[1]["avg"] or 0), kv[0])):
        note = ""
        if r["measured_count"] == 0:
            note = "No closed cases: unknown"
        elif r["measured_count"] < SMALL_SAMPLE:
            note = "Small sample"
            small.append(cat)
        lines.append(
            f"| {cat} | {r['closed_count']} | {r['measured_count']} | {fmt(r['avg'])} | "
            f"{fmt(r['median'])} | {fmt(r['min'])} | {fmt(r['max'])} | {note} |"
        )
    lines.append(
        f"| **All** | {ro['closed_count']} | {ro['measured_count']} | {fmt(ro['avg'])} | "
        f"{fmt(ro['median'])} | {fmt(ro['min'])} | {fmt(ro['max'])} | |"
    )

    with_avg = {c: r for c, r in s["resolution_by_category"].items() if r["avg"] is not None}
    obs = [
        "",
        "## Observations",
        "",
        "These statements are supported directly by the figures above.",
        "",
        f"1. {top} is the largest category at {s['top_pct']}% of complaints.",
        f"2. Most complaints are still open ({s['open_count']} of {s['total']}). "
        f"Escalated and In Review together make up "
        f"{s['status_counts'].get('Escalated', 0) + s['status_counts'].get('In Review', 0)} complaints.",
    ]
    if with_avg:
        slow = max(with_avg, key=lambda c: (with_avg[c]["avg"], c))
        fast = min(with_avg, key=lambda c: (with_avg[c]["avg"], c))
        obs.append(
            f"3. Among closed cases, {slow} had the longest average resolution "
            f"({with_avg[slow]['avg']} days, n={with_avg[slow]['measured_count']}) and {fast} the shortest "
            f"({with_avg[fast]['avg']} days, n={with_avg[fast]['measured_count']})."
        )
    if small:
        obs.append(
            f"4. Resolution averages for {' and '.join([', '.join(small[:-1]), small[-1]] if len(small) > 1 else small)} "
            f"rest on fewer than {SMALL_SAMPLE} closed cases. "
            "Treat them as indicative only."
        )
    obs += [
        "",
        "## What this analysis does not show",
        "",
        "- **No trends.** This is a single snapshot. The numbers say nothing about whether volume or "
        "resolution time is rising or falling.",
        "- **No causes.** Category volume does not explain *why* customers complained.",
        "- **Resolution time covers closed cases only.** It says nothing about how long the open "
        f"complaints ({s['open_count']}) will take, and the averages may change as those cases close.",
        "- The source data is synthetic training data.",
        "",
    ]
    return "\n".join(lines + obs)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def print_load_evidence(evidence):
    print(f"Loaded {evidence['path']}")
    if evidence["aliases_applied"]:
        print("  Column aliases applied: "
              + ", ".join(f"{k} -> {v}" for k, v in evidence["aliases_applied"].items()))
    print(f"  Rows read: {evidence['rows_read']}  valid: {evidence['rows_valid']}  "
          f"excluded: {len(evidence['excluded'])}  warnings: {len(evidence['warnings'])}")
    print("  Missing values: " + ", ".join(f"{k}={v}" for k, v in evidence["missing_values"].items()))
    for ln, cid, why in evidence["excluded"]:
        print(f"  WARNING line {ln} ({cid}) excluded: {why}", file=sys.stderr)
    for ln, cid, msg in evidence["warnings"]:
        print(f"  WARNING line {ln} ({cid}): {msg}", file=sys.stderr)


def run(input_path, out_dir):
    rows, evidence = load_complaints(input_path)
    print_load_evidence(evidence)

    summary = summarise(rows)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(measure_rows(summary, evidence), out_dir / OUTPUT_CSV)
    (out_dir / OUTPUT_MD).write_text(build_markdown(summary, evidence, Path(input_path).name),
                                     encoding="utf-8")

    print(f"Complaints analysed: {summary['total']}  open: {summary['open_count']}  "
          f"closed: {summary['closed_count']}")
    print(f"Highest-volume category: {' / '.join(summary['top_categories'])} "
          f"({summary['top_count']}, {summary['top_pct']}%)")
    print(f"Wrote {out_dir / OUTPUT_CSV}")
    print(f"Wrote {out_dir / OUTPUT_MD}")
    return summary, evidence


# ---------------------------------------------------------------------------
# Step 4 - failure tests (python3 complaint_analysis.py --self-test)
# Fixtures are written to a temporary folder, so no test files live in the repo
# and the real outputs in this folder are never overwritten.
# ---------------------------------------------------------------------------

HEADER = "complaint_id,customer_id,account_id,category,status,date_opened,date_closed,channel,priority\n"
FIXTURES = {
    "incomplete_rows.csv": HEADER + (
        "T001,C0001,A0001,Fees,Open,2026-01-01,,Web,Low\n"                          # valid, open
        "T002,C0002,,Fees,Closed,2026-01-01,2026-01-05,Phone,High\n"                # valid, closed, 4 days
        "T003,C0003,A0003,,Open,2026-01-02,,Email,Low\n"                            # missing category
        "T004,,A0004,Fees,,2026-01-02,,Email,Low\n"                                 # missing customer_id + status
        "T005,C0005,A0005,Fees,Open,31/01/2026,,Web,Medium\n"                       # bad date format
        "T001,C0006,A0006,Card or Transaction Dispute,Open,2026-01-03,,Web,Low\n"   # duplicate id
        "T007,C0007,A0007,Fees,Closed,2026-01-04,,Branch,Medium\n"                  # closed, no date
        "T008,C0008,A0008,Card or Transaction Dispute,Closed,2026-02-10,2026-02-01,Phone,High\n"  # closed before opened
        "T009,C0009,A0009,Card or Transaction Dispute,In Review,2026-02-11,2026-02-12,Web,Low\n"  # open with closed date
        "T010,C0010,A0010,Card or Transaction Dispute,Closed,2026-02-12,not a date,Email,Low\n"   # bad closed date
        "T011,C0011,A0011\n"                                                        # truncated row
        "\n"                                                                        # blank line (ignored)
        "T013,C0013,A0013,Mortgage Servicing,Resolved,2026-03-01,2026-03-11,Branch,Medium\n"      # Resolved = closed, 10 days
    ),
    "missing_column.csv": "complaint_id,customer_id,category,status,date_opened\nT001,C0001,Fees,Open,2026-01-01\n",
    "header_only.csv": "complaint_id,customer_id,category,status,created_date,resolved_date\n",
    "all_rows_invalid.csv": ("complaint_id,customer_id,category,status,created_date,resolved_date\n"
                             "T001,C0001,,Open,2026-01-01,\nT002,C0002,,Closed,2026-01-01,2026-01-03\n"),
    "empty.csv": "",
    "not_really.xlsx": "this is plain text, not a spreadsheet\n",
}


def run_self_tests():
    results = []

    def case(name, args, expect_code, expect_in, check=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(args)
        text = out.getvalue() + err.getvalue()
        ok = code == expect_code and all(s in text for s in expect_in)
        detail = ""
        if ok and check:
            ok, detail = check()
        results.append((name, expect_code, code, ok, err.getvalue().strip().splitlines(), detail))

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for name, content in FIXTURES.items():
            (tmp / name).write_text(content, encoding="utf-8")
        out = tmp / "out"

        case("Missing file", [str(tmp / "does_not_exist.csv"), "--out-dir", str(out)],
             2, ["ERROR: Input file not found"])
        case("Path is a folder", [str(tmp), "--out-dir", str(out)],
             2, ["ERROR: Input path is not a file"])
        case("Empty file", [str(tmp / "empty.csv"), "--out-dir", str(out)],
             3, ["ERROR:", "is empty"])
        case("Corrupt .xlsx", [str(tmp / "not_really.xlsx"), "--out-dir", str(out)],
             2, ["ERROR: Could not read"])
        case("Missing required column", [str(tmp / "missing_column.csv"), "--out-dir", str(out)],
             3, ["missing required column(s): resolved_date"])
        case("Header but no rows", [str(tmp / "header_only.csv"), "--out-dir", str(out)],
             3, ["has a header but no data rows"])
        case("Every row incomplete", [str(tmp / "all_rows_invalid.csv"), "--out-dir", str(out)],
             3, ["No valid rows", "missing category"])

        def check_incomplete():
            got = {(r["metric"], r["dimension"], r["dimension_value"]): r["value"]
                   for r in csv.DictReader(open(out / OUTPUT_CSV, encoding="utf-8"))}
            expected = {
                ("rows_read", "load", "all"): "12",
                ("rows_excluded", "load", "all"): "5",
                ("rows_with_warnings", "load", "all"): "4",
                ("complaint_count", "overall", "all"): "7",
                ("closed_count", "overall", "all"): "5",
                ("resolution_measured_count", "overall", "all"): "2",
                ("resolution_unmeasurable_count", "overall", "all"): "3",
                ("avg_resolution_days", "overall", "all"): "7.0",
                ("avg_resolution_days", "category", "Card or Transaction Dispute"): "",
                ("highest_volume_category_count", "category", "Fees"): "3",
                ("highest_volume_category_count", "category", "Card or Transaction Dispute"): "3",
            }
            wrong = [f"{k}: expected '{v}', got '{got.get(k)}'" for k, v in expected.items() if got.get(k) != v]
            return (not wrong), ("; ".join(wrong) if wrong else
                                 "7 analysed, 5 excluded, 4 warnings, Card resolution blank (unknown), Fees/Card tie")

        case("Incomplete rows (run continues)", [str(tmp / "incomplete_rows.csv"), "--out-dir", str(out)],
             0, ["excluded: missing category", "excluded: missing customer_id, status",
                 "invalid created_date '31/01/2026'", "duplicate complaint_id",
                 "closed with no resolved_date", "is before created_date",
                 "is not closed but has a resolved_date", "invalid resolved_date 'not a date'",
                 "excluded: missing category, status, created_date"],
             check_incomplete)

    passed = sum(1 for r in results if r[3])
    for name, want, got, ok, err_lines, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}: expected exit {want}, got {got}")
        for line in err_lines:
            print(f"        {line.strip()}")
        if detail:
            print(f"        check: {detail}")
    print(f"\n{passed}/{len(results)} failure tests passed")
    return 0 if passed == len(results) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate and summarise complaint data (.csv or .xlsx).")
    parser.add_argument("input", nargs="?", default=str(HERE / "complaints.csv"),
                        help="complaint .csv or .xlsx (default: complaints.csv next to this script)")
    parser.add_argument("--out-dir", default=str(HERE),
                        help="folder for the output CSV and Markdown (default: this folder)")
    parser.add_argument("--self-test", action="store_true",
                        help="run the missing-file and incomplete-row tests, then exit")
    args = parser.parse_args(argv)
    if args.self_test:
        return run_self_tests()
    try:
        run(args.input, args.out_dir)
    except AnalysisError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    return 0


if __name__ == "__main__":
    sys.exit(main())
