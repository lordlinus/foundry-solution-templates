"""Offline contracts between azure.yaml, the agent and the publish script."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = yaml.safe_load((ROOT / "azure.yaml").read_text())
AGENT = MANIFEST["services"]["claims-triage"]


def test_publish_script_targets_the_deployed_agent():
    script = (ROOT / "scripts/publish_m365.py").read_text()
    assert f'AGENT_NAME = "{AGENT["name"]}"' in script


def test_publish_hook_is_a_project_hook_pointing_at_the_script():
    # Verified live: the project-level postdeploy hook runs on azd deploy for the azure.ai.agent host.
    assert "hooks" not in AGENT
    for variant in MANIFEST["hooks"]["postdeploy"].values():
        assert (ROOT / variant["run"].split()[-1]).resolve() == ROOT / "scripts/publish_m365.py"


def test_no_custom_up_workflow_and_projects_extension_required():
    # azd 1.37 stops extension hosts before a nested provision step in a custom workflow.
    assert "workflows" not in MANIFEST
    assert "azure.ai.projects" in MANIFEST["requiredVersions"]["extensions"]


def test_agent_speaks_responses_for_the_activity_bridge():
    # Foundry bridges Responses to the Activity protocol when the agent is published.
    assert [p["protocol"] for p in AGENT["protocols"]] == ["responses"]


def test_agent_entry_point_and_pinned_dependencies():
    assert (ROOT / AGENT["project"] / AGENT["codeConfiguration"]["entryPoint"]).is_file()
    for line in (ROOT / "src/agent/requirements.txt").read_text().split():
        assert "==" in line, f"pin {line}: remote builds resolve dependencies on their own"


def test_prompt_capture_is_off():
    env = {e["name"]: e["value"] for e in AGENT["environmentVariables"]}
    assert env["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] == "false"


def test_model_default_matches_a_deployment():
    env = {e["name"]: e["value"] for e in AGENT["environmentVariables"]}
    default = re.search(r"=([^}]+)\}", env["AZURE_AI_MODEL_DEPLOYMENT_NAME"]).group(1)
    assert default in [d["name"] for d in MANIFEST["services"]["ai-project"]["deployments"]]


def test_escalation_requires_approval():
    source = (ROOT / "src/agent/main.py").read_text()
    assert '@tool(approval_mode="always_require")\ndef escalate_claim' in source
