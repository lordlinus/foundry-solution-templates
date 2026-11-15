"""Publish agent/voice-agent.json as a new version of the Foundry voice agent.

Runs as the azd postprovision hook. Standard library only: it calls the agents REST API with an
Entra token from the Azure CLI. azd passes its environment (FOUNDRY_PROJECT_ENDPOINT, and
optionally VOICE_AGENT_MODEL) to hooks as environment variables.

Voice agents are a preview: the request carries the Foundry-Features opt-in header.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DEFINITION = ROOT / "agent" / "voice-agent.json"
PREVIEW_HEADER = {"Foundry-Features": "VoiceAgents=V1Preview"}
# Managed identifiers differ by project and region. Microsoft's voice-agent samples start with
# gpt-realtime-2.1 and fall back to gpt-realtime-1.5, then gpt-realtime-2.1-mini.
DEFAULT_MODELS = "gpt-realtime-2.1,gpt-realtime-1.5,gpt-realtime-2.1-mini"


def token() -> str:
    az = shutil.which("az") or "az"
    result = subprocess.run(
        [
            az,
            "account",
            "get-access-token",
            "--resource",
            "https://ai.azure.com",
            "--query",
            "accessToken",
            "-o",
            "tsv",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        sys.exit(f"Could not get an Entra token from the Azure CLI. Run 'az login'.\n{result.stderr}")
    return result.stdout.strip()


def render(model: str) -> dict:
    return json.loads(DEFINITION.read_text(encoding="utf-8").replace("${VOICE_AGENT_MODEL}", model))


def publish(endpoint: str, agent: dict, bearer: str) -> tuple[int, dict]:
    url = f"{endpoint.rstrip('/')}/agents/{quote(agent['name'], safe='')}/versions?api-version=v1"
    body = json.dumps({"description": agent.get("description", ""), "definition": agent["definition"]}).encode()
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json", **PREVIEW_HEADER},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        text = error.read().decode(errors="replace")
        try:
            return error.code, json.loads(text)
        except json.JSONDecodeError:
            return error.code, {"error": {"message": text[:500]}}


def main() -> None:
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").strip()
    if not endpoint:
        sys.exit("FOUNDRY_PROJECT_ENDPOINT is not set. Run this from azd (postprovision) or set it.")
    models = [m.strip() for m in (os.environ.get("VOICE_AGENT_MODEL") or DEFAULT_MODELS).split(",") if m.strip()]
    bearer = token()
    failures = []
    for model in models:
        status, body = publish(endpoint, render(model), bearer)
        if 200 <= status < 300:
            print(f"Published voice agent {body.get('name')} version {body.get('version')} with model {model}.")
            return
        message = (body.get("error") or {}).get("message", json.dumps(body)[:300])
        failures.append(f"{model}: HTTP {status}: {message}")
        if status in (401, 403):
            break
    sys.exit(
        "Could not publish the voice agent.\n  "
        + "\n  ".join(failures)
        + "\nVoice agents are a preview gated by subscription and region. Check that this project's region "
        "supports them, or set VOICE_AGENT_MODEL to a managed model identifier enabled for your project."
    )


if __name__ == "__main__":
    main()
