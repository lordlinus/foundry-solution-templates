"""Offline contracts between azure.yaml, the infrastructure layer, and the code."""

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = yaml.safe_load((ROOT / "azure.yaml").read_text())
SERVICES = MANIFEST["services"]
AGENT = SERVICES["underwriting-agent"]
BICEP = (ROOT / "infra" / "resources.bicep").read_text()


def test_agent_name_matches_infra():
    assert f"param agentName string = '{AGENT['name']}'" in (ROOT / "infra" / "app.bicep").read_text()


def test_model_defaults_match_deployments():
    deployed = {d["name"] for d in SERVICES["ai-project"]["deployments"]}
    env = {e["name"]: e["value"] for e in AGENT["environmentVariables"]}
    for name in ("AZURE_AI_MODEL_DEPLOYMENT_NAME", "JUDGE_MODEL_DEPLOYMENT_NAME"):
        default = re.search(r"=([^}]+)\}", env[name]).group(1)
        assert default in deployed
    assert len(deployed) == 2  # The reviewer must be a different model from the drafter.


def test_agent_env_vars_are_produced_by_the_app_layer():
    outputs = set(re.findall(r"^output (\w+) ", (ROOT / "infra" / "app.bicep").read_text(), re.MULTILINE))
    for e in AGENT["environmentVariables"]:
        for var, default in re.findall(r"\$\{(\w+)(=[^}]*)?\}", e["value"]):
            assert var in outputs or default, f"{var} has no producer"


def test_every_parameter_has_a_producer():
    params = json.loads((ROOT / "infra" / "app.parameters.json").read_text())["parameters"]
    produced = {
        "AZURE_ENV_NAME",
        "AZURE_LOCATION",
        "AZURE_FOUNDRY_RESOURCE_GROUP",
        "AZURE_AI_ACCOUNT_NAME",
        "AZURE_AI_PROJECT_NAME",
        "FOUNDRY_PROJECT_ENDPOINT",
        "AZURE_PRINCIPAL_ID",
    }
    for value in params.values():
        for var, default in re.findall(r"\$\{(\w+)(=[^}]*)?\}", value["value"]):
            assert var in produced or default, f"{var} has no producer or default"


def test_dependencies_are_pinned():
    for line in (ROOT / "src" / "agent" / "requirements.txt").read_text().split():
        assert "==" in line


def test_records_stay_out_of_telemetry_and_search_is_keyless():
    env = {e["name"]: e["value"] for e in AGENT["environmentVariables"]}
    assert env["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] == "false"
    assert "disableLocalAuth: true" in BICEP and "authType: 'AAD'" in BICEP


def test_web_requires_sign_in_without_a_client_secret():
    assert "unauthenticatedClientAction: 'RedirectToLoginPage'" in BICEP
    assert "clientSecretSettingName: 'override-use-mi-fic-assertion-client-id'" in BICEP
    assert "'azd-service-name': 'web'" in BICEP and SERVICES["web"]["host"] == "containerapp"


def test_no_custom_up_workflow_and_hook_scripts_exist():
    assert "workflows" not in MANIFEST
    for hook in MANIFEST["hooks"]["postprovision"].values():
        assert (ROOT / hook["run"].split()[-1]).is_file()


def test_requires_projects_extension_not_standalone_foundry():
    extensions = MANIFEST["requiredVersions"]["extensions"]
    assert "azure.ai.projects" in extensions and "microsoft.foundry" not in extensions
