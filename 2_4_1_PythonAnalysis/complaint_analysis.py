"""Complaint analysis - Week 2, Exercise 2.4.1.

Usage:
    python3 complaint_analysis.py ~/Downloads/complaints.xlsx
    python3 complaint_analysis.py complaints.csv --out-dir results/
    python3 complaint_analysis.py --self-test

Exit codes: 0 = success, 2 = file missing or unreadable, 3 = file unusable.
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
OUTPUT_CSV = "complaint_analysis_output.csv"
OUTPUT_MD = "complaint_analysis_summary.md"

REQUIRED_COLUMNS = ["complaint_id", "customer_id", "category", "status", "created_date", "resolved_date"]
REQUIRED_VALUES = ["complaint_id", "customer_id", "category", "status", "created_date"]
COLUMN_ALIASES = {"date_opened": "created_date", "date_closed": "resolved_date"}
CLOSED_STATUSES = {"closed", "resolved"}
SMALL_SAMPLE = 5


class AnalysisError(Exception):
    def __init__(self, message, exit_code):
        super().__init__(message)
        self.exit_code = exit_code


# ---------- Load and validate ----------

def parse_date(text):
    try:
        return date.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def read_xlsx(path):
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            for si in ET.fromstring(zf.read("xl/sharedStrings.xml")).iter(f"{ns}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{ns}t")))
        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))

    rows = []
    for row in sheet.iter(f"{ns}row"):
        cells = {}
        for c in row.iter(f"{ns}c"):
            col = 0
            for ch in re.match(r"[A-Z]+", c.get("r")).group(0):
                col = col * 26 + ord(ch) - 64
            v = c.find(f"{ns}v")
            text = v.text if v is not None and v.text else ""
            if c.get("t") == "s" and text:
                text = shared[int(text)]
            cells[col - 1] = text
        rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])

    # Excel stores dates as day numbers counted from 1899-12-30.
    date_cols = [i for i, h in enumerate(rows[0]) if h.strip().lower() in {*COLUMN_ALIASES, *COLUMN_ALIASES.values()}]
    for row in rows[1:]:
        for i in date_cols:
            if i < len(row) and row[i].isdigit():
                row[i] = (date(1899, 12, 30) + timedelta(days=int(row[i]))).isoformat()
    return rows


def read_rows(path):
    path = Path(path)
    if not path.exists():
        raise AnalysisError(f"Input file not found: {path}", 2)
    if not path.is_file():
        raise AnalysisError(f"Input path is not a file: {path}", 2)
    try:
        if path.suffix.lower() == ".xlsx":
            return read_xlsx(path)
        with path.open(newline="", encoding="utf-8-sig") as fh:
            return list(csv.reader(fh))
    except (OSError, UnicodeDecodeError, csv.Error, zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise AnalysisError(f"Could not read {path}: {exc}", 2) from exc


def load_complaints(path):
    all_rows = read_rows(path)
    if not all_rows:
        raise AnalysisError(f"{path} is empty (no header row).", 3)

    header = [h.strip() for h in all_rows[0]]
    lower = [h.lower() for h in header]
    columns, aliases = [], {}
    for name, key in zip(header, lower):
        if key in COLUMN_ALIASES and COLUMN_ALIASES[key] not in lower:
            aliases[name] = COLUMN_ALIASES[key]
            key = COLUMN_ALIASES[key]
        columns.append(key)

    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        raise AnalysisError(f"{path} is missing required column(s): {', '.join(missing)}. "
                            f"Found: {', '.join(header)}", 3)

    data = [(i + 2, r) for i, r in enumerate(all_rows[1:]) if any(cell.strip() for cell in r)]
    if not data:
        raise AnalysisError(f"{path} has a header but no data rows.", 3)

    evidence = {
        "path": str(path), "columns": header, "aliases": aliases, "rows_read": len(data),
        "missing": Counter({c: 0 for c in columns}), "excluded": [], "warnings": [],
    }
    excluded, warnings = evidence["excluded"], evidence["warnings"]

    seen, valid = set(), []
    for line, cells in data:
        if len(cells) > len(columns):
            warnings.append((line, cells[0].strip(), f"{len(cells) - len(columns)} extra cell(s) ignored"))
        cells = (cells + [""] * len(columns))[:len(columns)]
        row = {name: value.strip() for name, value in zip(columns, cells)}
        cid = row["complaint_id"] or "(blank)"

        for name, value in row.items():
            if not value:
                evidence["missing"][name] += 1

        blanks = [c for c in REQUIRED_VALUES if not row[c]]
        created = parse_date(row["created_date"])
        if blanks:
            excluded.append((line, cid, f"missing {', '.join(blanks)}"))
            continue
        if created is None:
            excluded.append((line, cid, f"invalid created_date '{row['created_date']}' (expected YYYY-MM-DD)"))
            continue
        if row["complaint_id"] in seen:
            excluded.append((line, cid, "duplicate complaint_id (first occurrence kept)"))
            continue
        seen.add(row["complaint_id"])

        is_closed = row["status"].lower() in CLOSED_STATUSES
        resolved = parse_date(row["resolved_date"])
        if row["resolved_date"] and resolved is None:
            warnings.append((line, cid, f"invalid resolved_date '{row['resolved_date']}'; "
                                        "row counted, excluded from resolution time"))
        elif resolved and resolved < created:
            warnings.append((line, cid, f"resolved_date {resolved} is before created_date {created}; "
                                        "row counted, excluded from resolution time"))
            resolved = None
        elif resolved and not is_closed:
            warnings.append((line, cid, f"status '{row['status']}' is not closed but has a resolved_date; "
                                        "date ignored"))
            resolved = None
        elif not resolved and is_closed:
            warnings.append((line, cid, "closed with no resolved_date; counted as closed, "
                                        "resolution time unmeasurable"))

        valid.append({**row, "created_date": created, "resolved_date": resolved, "is_closed": is_closed})

    if not valid:
        raise AnalysisError(f"No valid rows in {path}: all {len(data)} row(s) were excluded "
                            f"(first reason: {excluded[0][2]}).", 3)
    return valid, evidence


# ---------- Calculate ----------

def pct(part, whole):
    return round(100.0 * part / whole, 1) if whole else None


def largest_first(counter):
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))


def resolution(closed_rows):
    days = [(r["resolved_date"] - r["created_date"]).days for r in closed_rows if r["resolved_date"]]
    return {
        "closed": len(closed_rows),
        "measured": len(days),
        "unmeasurable": len(closed_rows) - len(days),
        "avg": round(float(statistics.mean(days)), 1) if days else None,
        "median": round(float(statistics.median(days)), 1) if days else None,
        "min": min(days) if days else None,
        "max": max(days) if days else None,
    }


def summarise(rows):
    total = len(rows)
    closed = [r for r in rows if r["is_closed"]]
    categories = Counter(r["category"] for r in rows)
    top_count = max(categories.values())
    return {
        "total": total,
        "customers": len({r["customer_id"] for r in rows}),
        "open": total - len(closed),
        "closed": len(closed),
        "statuses": Counter(r["status"] for r in rows),
        "categories": categories,
        "top": sorted(c for c, n in categories.items() if n == top_count),
        "top_count": top_count,
        "top_pct": pct(top_count, total),
        "res_all": resolution(closed),
        "res_by_cat": {c: resolution([r for r in closed if r["category"] == c]) for c in sorted(categories)},
        "first_date": min(r["created_date"] for r in rows),
        "last_date": max(r["created_date"] for r in rows),
    }


# ---------- Write outputs ----------

def measures(s, ev):
    out = []

    def add(metric, dim, dim_value, value, unit, note=""):
        out.append({"metric": metric, "dimension": dim, "dimension_value": dim_value,
                    "value": "" if value is None else value, "unit": unit, "note": note})

    add("rows_read", "load", "all", ev["rows_read"], "rows")
    add("rows_excluded", "load", "all", len(ev["excluded"]), "rows", "incomplete or invalid; see summary")
    add("rows_with_warnings", "load", "all", len({w[0] for w in ev["warnings"]}), "rows")
    add("complaint_count", "overall", "all", s["total"], "complaints", "valid rows only")
    add("distinct_customers", "overall", "all", s["customers"], "customers")
    add("open_count", "overall", "all", s["open"], "complaints", "status not Closed/Resolved")
    add("open_pct", "overall", "all", pct(s["open"], s["total"]), "percent")
    add("closed_count", "overall", "all", s["closed"], "complaints")
    add("closed_pct", "overall", "all", pct(s["closed"], s["total"]), "percent")

    for dim, counter in (("status", s["statuses"]), ("category", s["categories"])):
        for name, n in largest_first(counter):
            add("complaint_count", dim, name, n, "complaints")
            add("complaint_pct", dim, name, pct(n, s["total"]), "percent")

    tie = "tie" if len(s["top"]) > 1 else ""
    for cat in s["top"]:
        add("highest_volume_category_count", "category", cat, s["top_count"], "complaints", tie)
        add("highest_volume_category_pct", "category", cat, s["top_pct"], "percent", tie)

    for dim, name, r in [("overall", "all", s["res_all"])] + [("category", c, r) for c, r in s["res_by_cat"].items()]:
        note = ""
        if r["measured"] == 0:
            note = "no measured closed cases: unknown, not 0"
        elif r["measured"] < SMALL_SAMPLE:
            note = f"small sample (n={r['measured']})"
        add("closed_count", dim, name, r["closed"], "complaints")
        add("resolution_measured_count", dim, name, r["measured"], "complaints")
        add("resolution_unmeasurable_count", dim, name, r["unmeasurable"], "complaints",
            "closed but no usable resolved_date" if r["unmeasurable"] else "")
        add("avg_resolution_days", dim, name, r["avg"], "days", note)
        add("median_resolution_days", dim, name, r["median"], "days", note)
        add("min_resolution_days", dim, name, r["min"], "days")
        add("max_resolution_days", dim, name, r["max"], "days")
    return out


def show(value):
    return "unknown" if value is None else value


def table(headers, rows, numeric=()):
    align = "".join("---:|" if i in numeric else "---|" for i in range(len(headers)))
    lines = ["| " + " | ".join(headers) + " |", "|" + align]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in rows]
    return lines + [""]


def summary_markdown(s, ev, input_name):
    ra = s["res_all"]
    top = " and ".join(s["top"])
    md = [
        "# Complaint Analysis Summary", "",
        "Week 2 | Exercise 2.4.1 · generated by `complaint_analysis.py`, do not edit by hand.", "",
        f"**Input:** `{input_name}` · **Rows read:** {ev['rows_read']} · "
        f"**Rows analysed:** {s['total']} · **Rows excluded:** {len(ev['excluded'])}",
        f"**Complaints opened between:** {s['first_date']} and {s['last_date']} (one snapshot)", "",
        "## Headlines", "",
        f"- **{s['total']} complaints** from **{s['customers']} customers**. "
        f"**{s['open']} ({pct(s['open'], s['total'])}%) are still open** and "
        f"{s['closed']} ({pct(s['closed'], s['total'])}%) are closed.",
        f"- **Highest-volume category: {top}** with {s['top_count']} complaints "
        f"({s['top_pct']}% of analysed complaints){' (tied)' if len(s['top']) > 1 else ''}.",
        f"- **Closed cases took {show(ra['avg'])} days on average** (median {show(ra['median'])}, "
        f"range {show(ra['min'])}–{show(ra['max'])}) across {ra['measured']} measured closed complaints.", "",
        "## Definitions", "",
        "Same rules as the SQL metrics in Exercise 2.2.2.", "",
    ]
    md += table(["Term", "Definition"], [
        ["Complaint count", "Number of valid rows (one row per complaint). Excluded rows are not counted."],
        ["Open", "Status is not `Closed` or `Resolved` (so Open, In Review and Escalated are all open)."],
        ["Closed", "Status is `Closed` or `Resolved`."],
        ["Percentage", "Count ÷ complaints analysed × 100, to 1 decimal place."],
        ["Resolution days", "`resolved_date` − `created_date` in whole calendar days, **closed complaints only**."],
        ["Unknown", "No measurable closed case. This is shown as blank or 'unknown', **never as 0**."],
        ["Small sample", f"Fewer than {SMALL_SAMPLE} measured closed cases. "
                         "The average is shown but should not be relied on."],
    ])

    md += ["## Load evidence", "", f"Columns found: `{', '.join(ev['columns'])}`", ""]
    if ev["aliases"]:
        mapped = ", ".join(f"`{k}` → `{v}`" for k, v in ev["aliases"].items())
        md += [f"Column names mapped to the required names: {mapped}.", ""]
    notes = {"resolved_date": "Expected for open complaints",
             "account_id": "Optional (not every complaint is tied to an account)"}
    md += table(["Column", "Missing values", "Meaning"],
                [[c, n, "Required" if c in REQUIRED_VALUES else notes.get(c, "Optional")]
                 for c, n in ev["missing"].items()])
    if ev["excluded"]:
        md += ["**Excluded rows:**", ""] + table(["Line", "complaint_id", "Reason"], ev["excluded"])
    else:
        md += ["No rows were excluded: every row has all required values and a valid created_date.", ""]
    if ev["warnings"]:
        md += ["**Warnings (row kept):**", ""] + table(["Line", "complaint_id", "Warning"], ev["warnings"])
    else:
        md += ["No data-consistency warnings: every closed complaint has a valid resolved_date "
               "on or after its created_date, and no open complaint has a resolved_date.", ""]

    md += ["## Status", ""] + table(["Status", "Complaints", "%"],
                                    [[k, n, pct(n, s["total"])] for k, n in largest_first(s["statuses"])], (1, 2))
    md += ["## Category", ""] + table(["Category", "Complaints", "%"],
                                      [[k, n, pct(n, s["total"])] for k, n in largest_first(s["categories"])], (1, 2))

    by_avg = sorted(s["res_by_cat"].items(), key=lambda kv: (kv[1]["avg"] is None, -(kv[1]["avg"] or 0), kv[0]))
    small = [c for c, r in by_avg if 0 < r["measured"] < SMALL_SAMPLE]
    res_rows = []
    for cat, r in by_avg:
        note = "No closed cases: unknown" if r["measured"] == 0 else "Small sample" if cat in small else ""
        res_rows.append([cat, r["closed"], r["measured"], show(r["avg"]), show(r["median"]),
                         show(r["min"]), show(r["max"]), note])
    res_rows.append(["**All**", ra["closed"], ra["measured"], show(ra["avg"]), show(ra["median"]),
                     show(ra["min"]), show(ra["max"]), ""])
    md += ["## Closed-case resolution by category", ""]
    md += table(["Category", "Closed", "Measured", "Avg days", "Median", "Min", "Max", "Note"], res_rows, range(1, 7))

    in_progress = s["statuses"].get("Escalated", 0) + s["statuses"].get("In Review", 0)
    md += ["## Observations", "", "These statements are supported directly by the figures above.", "",
           f"1. {top} is the largest category at {s['top_pct']}% of complaints.",
           f"2. Most complaints are still open ({s['open']} of {s['total']}). "
           f"Escalated and In Review together make up {in_progress} complaints."]
    measured = [(c, r) for c, r in by_avg if r["avg"] is not None]
    if measured:
        (slow, rs), (fast, rf) = measured[0], measured[-1]
        md.append(f"3. Among closed cases, {slow} had the longest average resolution "
                  f"({rs['avg']} days, n={rs['measured']}) and {fast} the shortest "
                  f"({rf['avg']} days, n={rf['measured']}).")
    if small:
        names = small[0] if len(small) == 1 else ", ".join(small[:-1]) + " and " + small[-1]
        md.append(f"4. Resolution averages for {names} rest on fewer than {SMALL_SAMPLE} closed cases. "
                  "Treat them as indicative only.")
    md += ["", "## What this analysis does not show", "",
           "- **No trends.** This is a single snapshot. The numbers say nothing about whether volume or "
           "resolution time is rising or falling.",
           "- **No causes.** Category volume does not explain *why* customers complained.",
           "- **Resolution time covers closed cases only.** It says nothing about how long the open "
           f"complaints ({s['open']}) will take, and the averages may change as those cases close.",
           "- The source data is synthetic training data.", ""]
    return "\n".join(md)


def run(input_path, out_dir):
    rows, ev = load_complaints(input_path)

    print(f"Loaded {ev['path']}")
    if ev["aliases"]:
        print("  Column aliases applied: " + ", ".join(f"{k} -> {v}" for k, v in ev["aliases"].items()))
    print(f"  Rows read: {ev['rows_read']}  valid: {len(rows)}  "
          f"excluded: {len(ev['excluded'])}  warnings: {len(ev['warnings'])}")
    print("  Missing values: " + ", ".join(f"{k}={v}" for k, v in ev["missing"].items()))
    for line, cid, reason in ev["excluded"]:
        print(f"  WARNING line {line} ({cid}) excluded: {reason}", file=sys.stderr)
    for line, cid, message in ev["warnings"]:
        print(f"  WARNING line {line} ({cid}): {message}", file=sys.stderr)

    s = summarise(rows)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    rows_out = measures(s, ev)
    with open(out_dir / OUTPUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows_out[0]))
        writer.writeheader()
        writer.writerows(rows_out)
    (out_dir / OUTPUT_MD).write_text(summary_markdown(s, ev, Path(input_path).name), encoding="utf-8")

    print(f"Complaints analysed: {s['total']}  open: {s['open']}  closed: {s['closed']}")
    print(f"Highest-volume category: {' / '.join(s['top'])} ({s['top_count']}, {s['top_pct']}%)")
    print(f"Wrote {out_dir / OUTPUT_CSV}")
    print(f"Wrote {out_dir / OUTPUT_MD}")


# ---------- Failure tests (--self-test) ----------

HEADER = "complaint_id,customer_id,account_id,category,status,date_opened,date_closed,channel,priority\n"
FIXTURES = {
    "incomplete_rows.csv": HEADER
    + "T001,C0001,A0001,Fees,Open,2026-01-01,,Web,Low\n"
    + "T002,C0002,,Fees,Closed,2026-01-01,2026-01-05,Phone,High\n"
    + "T003,C0003,A0003,,Open,2026-01-02,,Email,Low\n"
    + "T004,,A0004,Fees,,2026-01-02,,Email,Low\n"
    + "T005,C0005,A0005,Fees,Open,31/01/2026,,Web,Medium\n"
    + "T001,C0006,A0006,Card or Transaction Dispute,Open,2026-01-03,,Web,Low\n"
    + "T007,C0007,A0007,Fees,Closed,2026-01-04,,Branch,Medium\n"
    + "T008,C0008,A0008,Card or Transaction Dispute,Closed,2026-02-10,2026-02-01,Phone,High\n"
    + "T009,C0009,A0009,Card or Transaction Dispute,In Review,2026-02-11,2026-02-12,Web,Low\n"
    + "T010,C0010,A0010,Card or Transaction Dispute,Closed,2026-02-12,not a date,Email,Low\n"
    + "T011,C0011,A0011\n"
    + "\n"
    + "T013,C0013,A0013,Mortgage Servicing,Resolved,2026-03-01,2026-03-11,Branch,Medium\n",
    "missing_column.csv": "complaint_id,customer_id,category,status,date_opened\nT001,C0001,Fees,Open,2026-01-01\n",
    "header_only.csv": "complaint_id,customer_id,category,status,created_date,resolved_date\n",
    "all_rows_invalid.csv": "complaint_id,customer_id,category,status,created_date,resolved_date\n"
                            "T001,C0001,,Open,2026-01-01,\nT002,C0002,,Closed,2026-01-01,2026-01-03\n",
    "empty.csv": "",
    "not_really.xlsx": "this is plain text, not a spreadsheet\n",
}

EXPECTED_INCOMPLETE = {
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


def run_self_tests():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for name, content in FIXTURES.items():
            (tmp / name).write_text(content, encoding="utf-8")
        out = tmp / "out"

        cases = [
            ("Missing file", tmp / "does_not_exist.csv", 2, ["ERROR: Input file not found"]),
            ("Path is a folder", tmp, 2, ["ERROR: Input path is not a file"]),
            ("Empty file", tmp / "empty.csv", 3, ["ERROR:", "is empty"]),
            ("Corrupt .xlsx", tmp / "not_really.xlsx", 2, ["ERROR: Could not read"]),
            ("Missing required column", tmp / "missing_column.csv", 3,
             ["missing required column(s): resolved_date"]),
            ("Header but no rows", tmp / "header_only.csv", 3, ["has a header but no data rows"]),
            ("Every row incomplete", tmp / "all_rows_invalid.csv", 3, ["No valid rows", "missing category"]),
            ("Incomplete rows (run continues)", tmp / "incomplete_rows.csv", 0,
             ["excluded: missing category", "excluded: missing customer_id, status",
              "invalid created_date '31/01/2026'", "duplicate complaint_id",
              "closed with no resolved_date", "is before created_date",
              "is not closed but has a resolved_date", "invalid resolved_date 'not a date'",
              "excluded: missing category, status, created_date"]),
        ]

        passed = 0
        for name, path, want_code, want_text in cases:
            stdout, stderr = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = main([str(path), "--out-dir", str(out)])
            ok = code == want_code and all(t in stdout.getvalue() + stderr.getvalue() for t in want_text)

            detail = ""
            if ok and want_code == 0:
                with open(out / OUTPUT_CSV, encoding="utf-8") as fh:
                    got = {(r["metric"], r["dimension"], r["dimension_value"]): r["value"] for r in csv.DictReader(fh)}
                wrong = [f"{k}: expected '{v}', got '{got.get(k)}'"
                         for k, v in EXPECTED_INCOMPLETE.items() if got.get(k) != v]
                ok = not wrong
                detail = "; ".join(wrong) or \
                    "7 analysed, 5 excluded, 4 warnings, Card resolution blank (unknown), Fees/Card tie"

            passed += ok
            print(f"[{'PASS' if ok else 'FAIL'}] {name}: expected exit {want_code}, got {code}")
            for line in stderr.getvalue().strip().splitlines():
                print(f"        {line.strip()}")
            if detail:
                print(f"        check: {detail}")

    print(f"\n{passed}/{len(cases)} failure tests passed")
    return 0 if passed == len(cases) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate and summarise complaint data (.csv or .xlsx).")
    parser.add_argument("input", nargs="?", default=str(HERE / "complaints.csv"))
    parser.add_argument("--out-dir", default=str(HERE))
    parser.add_argument("--self-test", action="store_true")
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
