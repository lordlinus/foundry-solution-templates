"""Medical underwriting copilot: drafts a grounded report from an OCR'd medical record.

Tools: a paged reader for the record in the session's $HOME, the underwriting guidelines in
Azure AI Search (hosted tool), optional ICD-10 and PubMed MCP servers (hosted tools), and
submit_report, which has a second model review the draft before it is released.
"""

import logging
import os
from pathlib import Path

from agent_framework import Agent, SkillsProvider
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from report import read_case_record, submit_report

# About 210 tokens per turn (850 characters). The report format and decision policy live in skills
# (about 100 tokens each until loaded), not here.
INSTRUCTIONS = """You draft medical underwriting reports for a human underwriter. You draft; you never decide.

For "Underwrite case <id>":
1. Load the underwriting-report-format and underwriting-decision skills.
2. Read the record with read_case_record, page range by page range, until you have read every page.
3. Search the underwriting guidelines once per condition before you assess it. Never state a
   decision without citing the guideline passages you used.
4. Use the ICD-10 and PubMed tools, when available, only to interpret findings. Report every
   code exactly as the record states it.
5. Call submit_report once with the complete report. If it returns "revise", fix every issue and
   call it again. If it returns a failed review, say so plainly in your reply.
Never invent a clinical value. Reply with one short paragraph after the report is submitted."""

# The public ICD-10 and PubMed MCP servers sit behind a CDN that rejects some default user agents.
MCP_HEADERS = {"User-Agent": "foundry-hosted-agent/1.0"}
MCP_SERVERS = {
    "icd10_codes": "https://hcls.mcp.claude.com/icd10_codes/mcp",
    "pubmed": "https://pubmed.mcp.claude.com/mcp",
}


def build_agent() -> Agent:
    # Called per request, so /readiness answers even when configuration is missing.
    client = FoundryChatClient(
        project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
        model=os.environ["AZURE_AI_MODEL_DEPLOYMENT_NAME"],
        credential=DefaultAzureCredential(),
    )
    tools = [
        read_case_record,
        submit_report,
        client.get_azure_ai_search_tool(
            index_connection_id=os.environ["SEARCH_CONNECTION_ID"],
            index_name=os.environ["SEARCH_INDEX_NAME"],
            query_type="simple",
            top_k=5,
        ),
    ]
    if os.environ.get("MEDICAL_MCP_ENABLED", "true").lower() == "true":
        tools += [
            client.get_mcp_tool(name=name, url=url, headers=MCP_HEADERS, approval_mode="never_require")
            for name, url in MCP_SERVERS.items()
        ]
    skills = SkillsProvider.from_paths(
        Path(__file__).parent / "skills",
        # Trusted, read-only skills in this folder. Approval would stall a background run.
        disable_load_skill_approval=True,
        disable_read_skill_resource_approval=True,
    )
    return Agent(
        client=client,
        instructions=INSTRUCTIONS,
        tools=tools,
        context_providers=[skills],
        default_options={"store": False},  # The hosting layer owns conversation history.
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ResponsesHostServer(build_agent).run()
