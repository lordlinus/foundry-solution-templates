"""Second-model review: a different model audits the draft against the OCR source."""

import os
from typing import Literal

from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from azure.identity import DefaultAzureCredential
from pydantic import BaseModel, Field

MAX_SOURCE_CHARS = 300_000

RUBRIC = """You check a draft medical underwriting report against the OCR text of the record it was drafted from.
A human underwriter will rely on the report, so be strict about facts and lenient about style.

Fail the draft when:
- it states a clinical fact (date, value, medication, dose, diagnosis) that the record does not support;
- it interprets a test the record shows as ordered or pending, instead of saying "Not interpreted";
- a stated fact cites no page, or a page that does not contain it;
- a visit in the record is missing from the draft;
- the decision cites no guideline passage, or contradicts its own rationale.

Do not fail the draft for:
- guideline content that is not in the record (it comes from the guidelines search);
- wording, order, or formatting;
- clinical inference that is labelled as inference.

Quote the draft text behind each issue so it can be fixed."""


class Issue(BaseModel):
    severity: Literal["critical", "major", "minor"]
    detail: str = Field(description="What is wrong, quoting the draft, and how to fix it.")


class Verdict(BaseModel):
    passed: bool
    summary: str = Field(description="One sentence.")
    issues: list[Issue]
    missing_visits: list[str]
    unsupported_claims: list[str]


async def review(source: str, draft: str) -> Verdict:
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["JUDGE_MODEL_DEPLOYMENT_NAME"],
        credential=DefaultAzureCredential(),
    )
    reviewer = Agent(client=client, instructions=RUBRIC, default_options={"store": False})
    response = await reviewer.run(
        f"RECORD (OCR):\n{source[:MAX_SOURCE_CHARS]}\n\nDRAFT REPORT (JSON):\n{draft}",
        options={"response_format": Verdict},
    )
    if isinstance(response.value, Verdict):
        return response.value
    return Verdict.model_validate_json(response.text)
