"""Offline contracts between the voice agent definition, the relay, infrastructure and evals."""

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
AGENT = json.loads((ROOT / "agent/voice-agent.json").read_text())
DEFINITION = AGENT["definition"]
STAGES = {s["id"]: s for s in DEFINITION["subagent_config"]["subagents"]}
MANIFEST = yaml.safe_load((ROOT / "azure.yaml").read_text())
RELAY_TOOLS = re.search(r"TOOL_NAMES = \[(.*?)\]", (ROOT / "src/web/tools.mjs").read_text()).group(1)


def tools(stage):
    return {t["name"]: t for t in stage.get("tools", [])}


def test_entrypoint_is_first_and_every_handoff_target_exists():
    assert DEFINITION["subagent_config"]["subagents"][0]["id"] == "$entrypoint"
    for stage in STAGES.values():
        for handoff in stage.get("handoff_conditions", []):
            assert handoff["target"] in STAGES, handoff["id"]


def test_fraud_reaches_urgent_support_from_every_stage_that_talks_to_customers():
    for stage_id in ("$entrypoint", "card_services"):
        targets = {h["target"] for h in STAGES[stage_id]["handoff_conditions"]}
        assert "urgent_support" in targets, stage_id


def test_side_effects_are_two_step_everywhere():
    for stage in STAGES.values():
        names = set(tools(stage))
        if "request_card_action" in names:
            assert "confirm_card_action" in names, stage["id"]


def test_every_function_tool_is_implemented_by_the_relay():
    for stage in STAGES.values():
        for name, tool in tools(stage).items():
            assert tool["type"] in ("function", "system"), name
            if tool["type"] == "function":
                assert f'"{name}"' in RELAY_TOOLS, f"{name} is declared but the relay does not run it"


def test_conversations_are_not_stored_and_the_model_is_configurable():
    assert DEFINITION["store"] is False
    assert DEFINITION["model_type"] == "managed"
    assert DEFINITION["model"] == "${VOICE_AGENT_MODEL}"


def test_agent_name_matches_infrastructure():
    assert f"param voiceAgentName string = '{AGENT['name']}'" in (ROOT / "infra/app.bicep").read_text()
    assert f"agentName = '{AGENT['name']}'" not in (ROOT / "infra/app.bicep").read_text()


def test_manifest_has_no_custom_up_workflow_and_requires_the_projects_extension():
    assert "workflows" not in MANIFEST
    assert "azure.ai.projects" in MANIFEST["requiredVersions"]["extensions"]


def test_web_identity_is_least_privilege_and_sign_in_has_no_secret():
    bicep = (ROOT / "infra/resources.bicep").read_text()
    assert "scope: foundryProject\n  name: guid(foundryProject.id, webIdentity.id, foundryUserRole)" in bicep
    assert "unauthenticatedClientAction: 'RedirectToLoginPage'" in bicep
    assert "clientSecretSettingName: 'override-use-mi-fic-assertion-client-id'" in bicep


def test_eval_scenarios_and_evals_target_this_agent():
    rows = [
        json.loads(line) for line in (ROOT / "evals/caller-scenarios.jsonl").read_text().splitlines() if line.strip()
    ]
    assert len({r["test_case_id"] for r in rows}) == len(rows)
    assert all(r["test_case_description"] for r in rows)
    config = yaml.safe_load((ROOT / "evals/azure.eval.yaml").read_text())
    rubric = {e["name"]: e for e in config["evaluators"]}["card-service-voice-rubric"]["definition"]
    assert rubric["type"] == "rubric"
    ids = {d["id"] for d in rubric["dimensions"]}
    assert {"urgent_routing", "confirm_before_change", "sensitive_data"} <= ids
    for ev in config["evals"]:
        names = {e["evaluator"] for e in ev["evaluators"]}
        assert "card-service-voice-rubric" in names, ev["name"]
    simulation = {e["name"]: e for e in config["evals"]}["card-service-voice-simulation"]
    assert simulation["target"]["name"] == AGENT["name"]
    traces = {e["name"]: e for e in config["evals"]}["card-service-voice-traces"]
    assert traces["source"]["agentName"] == AGENT["name"]


def test_project_identity_can_read_traces_for_evaluation():
    bicep = (ROOT / "infra/resources.bicep").read_text()
    for role in ("readerRole", "logAnalyticsReaderRole", "privilegedMonitoringDataReaderRole"):
        assert role in bicep
