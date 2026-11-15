"""Offline tests for the record reader and submit_report's single revision round."""

import asyncio
import json

import judge
import pytest
import report
from pydantic import ValidationError

RECORD = "OCR notes: none.\n\n<!-- page 1 -->\nVisit 1\n\n<!-- page 2 -->\nVisit 2\n\n<!-- page 3 -->\nLab"


def draft(case_id: str = "c-1") -> dict:
    return {
        "case_id": case_id,
        "summary": "s",
        "conditions": [
            {
                "name": "Hypertension",
                "icd10": "I10",
                "status": "active",
                "first_documented": "02 Feb 2025",
                "evidence": [{"fact": "BP 152/96 mmHg", "page": 2}],
                "guideline_refs": ["Hypertension: mildly elevated"],
            }
        ],
        "visits": [],
        "labs": [],
        "discrepancies": [],
        "ocr_attention": [],
        "recommendation": {"decision": "Rated", "rationale": "r", "guideline_refs": ["Hypertension: mildly elevated"]},
    }


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(report.Path, "home", lambda: tmp_path)
    (tmp_path / "cases").mkdir()
    (tmp_path / "cases" / "c-1.md").write_text(RECORD)
    return tmp_path / "cases"


def verdicts(monkeypatch, *passed: bool) -> list[str]:
    seen: list[str] = []
    queue = list(passed)

    async def fake_review(source: str, draft_json: str) -> judge.Verdict:
        seen.append(source)
        ok = queue.pop(0)
        issues = [] if ok else [{"severity": "major", "detail": "missing visit"}]
        return judge.Verdict(passed=ok, summary="x", issues=issues, missing_visits=[], unsupported_claims=[])

    monkeypatch.setattr(judge, "review", fake_review)
    return seen


def submit(payload: dict) -> dict:
    result = asyncio.run(report.submit_report.invoke(arguments={"report": payload}))
    return json.loads(result[0].text)


def test_reader_returns_requested_pages_with_notes_first(home):
    out = asyncio.run(report.read_case_record.invoke(arguments={"case_id": "c-1", "first_page": 1, "last_page": 2}))
    text = out[0].text
    assert "3 pages" in text and "OCR notes" in text and "Visit 2" in text and "Lab" not in text


def test_reader_rejects_path_traversal(home):
    with pytest.raises(ValueError):
        report.case_path("../etc", ".md")


def test_passing_review_releases_the_report(home, monkeypatch):
    verdicts(monkeypatch, True)
    assert submit(draft())["status"] == "submitted"
    saved = json.loads((home / "c-1.report.json").read_text())
    assert saved["review"]["passed"] is True and saved["revisions"] == 0


def test_failing_review_gets_one_revision_then_releases_with_the_failure(home, monkeypatch):
    seen = verdicts(monkeypatch, False, False)
    first = submit(draft())
    assert first["status"] == "revise" and first["issues"][0]["detail"] == "missing visit"
    assert not (home / "c-1.report.json").exists()
    second = submit(draft())
    assert (
        second["status"] == "submitted"
        and second["review_passed"] is False
        and "never say it passed" in second["instruction"]
    )
    saved = json.loads((home / "c-1.report.json").read_text())
    assert saved["review"]["passed"] is False and saved["revisions"] == 1
    assert seen == [RECORD, RECORD]  # The reviewer sees the full OCR source each time.


def test_unknown_case_is_an_error_not_a_report(home, monkeypatch):
    verdicts(monkeypatch, True)
    assert submit(draft("c-2"))["status"] == "error"


def test_decision_without_a_guideline_is_rejected_by_the_schema():
    payload = draft()
    payload["recommendation"]["guideline_refs"] = []
    with pytest.raises(ValidationError):
        report.UnderwritingReport.model_validate(payload)


def test_framework_rejects_an_invalid_report_before_the_tool_runs(home, monkeypatch):
    seen = verdicts(monkeypatch, True)
    payload = draft()
    payload["recommendation"]["guideline_refs"] = []
    with pytest.raises(Exception, match="guideline_refs"):
        asyncio.run(report.submit_report.invoke(arguments={"report": payload}))
    assert seen == []  # The reviewer is never called for a malformed report.
