"""The report schema, the paged record reader, and submit_report with one revision round."""

import json
import re
from pathlib import Path
from typing import Annotated, Literal

import judge
from agent_framework import tool
from pydantic import BaseModel, Field

MAX_REVISIONS = 1
CASE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
PAGE_MARKER = re.compile(r"<!-- page (\d+) -->")
NOT_DOCUMENTED = "Not documented"


def cases_dir() -> Path:
    return Path.home() / "cases"


def case_path(case_id: str, suffix: str) -> Path:
    if not CASE_ID.match(case_id):
        raise ValueError("case_id must contain only letters, digits, '-' and '_'.")
    return cases_dir() / f"{case_id}{suffix}"


class Evidence(BaseModel):
    fact: str = Field(description="One fact, worded as the record states it.")
    page: int = Field(ge=1, description="Record page that states the fact.")


class Condition(BaseModel):
    name: str
    icd10: str = Field(description=f"Code exactly as the record states it, or '{NOT_DOCUMENTED}'.")
    status: Literal["active", "resolved", "unknown"]
    first_documented: str = Field(description=f"Date as written in the record, or '{NOT_DOCUMENTED}'.")
    evidence: list[Evidence] = Field(min_length=1)
    guideline_refs: list[str] = Field(description="Titles of the guideline passages used to assess it.")


class Visit(BaseModel):
    date: str
    setting: str = Field(description="For example clinic, hospital, laboratory.")
    reason: str
    findings: str
    page: int = Field(ge=1)


class LabResult(BaseModel):
    test: str
    value: str = Field(description="Reported value, or 'Pending' when ordered but not reported.")
    unit: str
    date: str
    interpretation: Literal["Normal", "Abnormal", "Not interpreted"] = Field(
        description="'Not interpreted' when no result was reported."
    )
    page: int = Field(ge=1)


class Recommendation(BaseModel):
    decision: Literal["Standard", "Rated", "Postpone", "Decline", "Refer to underwriter"]
    rationale: str
    guideline_refs: list[str] = Field(min_length=1, description="Guideline passages behind the decision.")


class UnderwritingReport(BaseModel):
    case_id: str
    summary: str = Field(description="Three to five sentences for the underwriter.")
    conditions: list[Condition]
    visits: list[Visit]
    labs: list[LabResult]
    discrepancies: list[str] = Field(description="Conflicts within the record, quoted with page numbers.")
    ocr_attention: list[str] = Field(description="Low-confidence values from the OCR notes that affect the report.")
    recommendation: Recommendation


@tool
def read_case_record(
    case_id: Annotated[str, Field(description="The case to read.")],
    first_page: Annotated[int, Field(ge=1, description="First page to return.")] = 1,
    last_page: Annotated[int | None, Field(description="Last page to return; omit for the next five.")] = None,
) -> str:
    """Return pages of the OCR'd medical record with page markers, plus the page count."""
    path = case_path(case_id, ".md")
    if not path.is_file():
        return f"No record for case {case_id}."
    text = path.read_text(encoding="utf-8")
    # Split on page markers; parts alternate between page number and page text.
    parts = PAGE_MARKER.split(text)
    pages = {int(parts[i]): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    notes = parts[0].strip()
    last = min(last_page or first_page + 4, max(pages, default=0))
    body = "\n\n".join(f"<!-- page {n} -->\n{pages[n]}" for n in range(first_page, last + 1) if n in pages)
    header = f"Case {case_id}: {len(pages)} pages. Showing {first_page}-{last}."
    return "\n\n".join(x for x in (header, notes if first_page == 1 else "", body) if x)


@tool
async def submit_report(report: UnderwritingReport) -> dict:
    """Submit the complete report. A second model reviews it against the record before release."""
    # Agent Framework 1.26 passes nested model arguments as plain dicts; validate explicitly.
    report = UnderwritingReport.model_validate(report)
    source_path = case_path(report.case_id, ".md")
    if not source_path.is_file():
        return {"status": "error", "message": f"No record for case {report.case_id}."}
    revisions_path = case_path(report.case_id, ".revisions")
    revisions = int(revisions_path.read_text()) if revisions_path.is_file() else 0

    verdict = await judge.review(source_path.read_text(encoding="utf-8"), report.model_dump_json())
    if not verdict.passed and revisions < MAX_REVISIONS:
        revisions_path.write_text(str(revisions + 1))
        return {"status": "revise", **verdict.model_dump(exclude={"passed"})}

    case_path(report.case_id, ".report.json").write_text(
        json.dumps({"report": report.model_dump(), "review": verdict.model_dump(), "revisions": revisions}, indent=2)
    )
    revisions_path.unlink(missing_ok=True)
    result: dict = {"status": "submitted", "review_passed": verdict.passed}
    if not verdict.passed:
        result["instruction"] = "The review still fails. Tell the user which issues remain; never say it passed."
    return result
