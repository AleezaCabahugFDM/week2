"""FastAPI app for the complaint analysis.

    python3 -m pip install --user fastapi uvicorn python-multipart
    python3 -m uvicorn main:app --reload        # then open http://127.0.0.1:8000/docs
"""

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile

from complaint_analysis import AnalysisError, load_complaints, measures, summarise, summary_markdown

app = FastAPI(title="Complaint Analysis")

STATUS_FOR_EXIT_CODE = {2: 400, 3: 422}


@app.post("/analysis")
def analyse(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".csv", ".xlsx"):
        raise HTTPException(415, "Upload a .csv or .xlsx file.")

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"upload{suffix}"
        path.write_bytes(file.file.read())
        try:
            rows, evidence = load_complaints(path)
        except AnalysisError as exc:
            raise HTTPException(STATUS_FOR_EXIT_CODE[exc.exit_code], str(exc).replace(str(path), file.filename))

    s = summarise(rows)
    return {
        "file": file.filename,
        "rows_read": evidence["rows_read"],
        "rows_valid": len(rows),
        "excluded": [{"line": line, "complaint_id": cid, "reason": why} for line, cid, why in evidence["excluded"]],
        "warnings": [{"line": line, "complaint_id": cid, "message": msg} for line, cid, msg in evidence["warnings"]],
        "measures": measures(s, evidence),
        "summary_markdown": summary_markdown(s, evidence, file.filename),
    }
