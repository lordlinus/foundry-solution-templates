"""Start a voice simulation run of the eval that `azd deploy` registered from evals/azure.eval.yaml.

Voice-agent targets require a voice_model for the simulated caller, which the azd eval configuration
can't express yet (azure.ai.evaluations 1.0.0-beta.2), so this script starts the run with the SDK.
The eval, dataset, and evaluators are the ones azd published; only the run is created here.

    pip install "azure-ai-projects>=2.11.0" azure-identity pyyaml
    python evals/run_voice_simulation.py            # uses FOUNDRY_PROJECT_ENDPOINT from `azd env`
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import yaml
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

HERE = Path(__file__).resolve().parent
CONFIG = yaml.safe_load((HERE / "azure.eval.yaml").read_text())
EVAL = next(e for e in CONFIG["evals"] if e["name"] == "card-service-voice-simulation")
# The simulated caller's voice and line conditions. Effects: street_traffic, crowd_chatter,
# background_tv, metro_station, telephonic_voice.
VOICE = {"type": "azure-standard", "name": "en-US-AndrewNeural", "temperature": 0.7}
AUDIO_EFFECTS = {"effects": ["telephonic_voice"], "volume_percentage": 15}


def project_endpoint() -> str:
    if os.environ.get("FOUNDRY_PROJECT_ENDPOINT"):
        return os.environ["FOUNDRY_PROJECT_ENDPOINT"]
    out = subprocess.run(
        ["azd", "env", "get-value", "FOUNDRY_PROJECT_ENDPOINT"], check=False, capture_output=True, text=True
    )
    return out.stdout.strip()


def main() -> None:
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=project_endpoint(), credential=credential, allow_preview=True) as project,
        project.get_openai_client() as openai,
    ):
        evals = [e for e in openai.evals.list(limit=100) if e.name == EVAL["name"]]
        if not evals:
            raise SystemExit(f"Eval {EVAL['name']} not found. Run `azd deploy card-service-voice-evals` first.")
        dataset = project.datasets.get(name=EVAL["dataset"], version="1.0")
        agent = project.agents.get(agent_name=EVAL["target"]["name"])
        version = agent.versions.latest.version
        run = openai.evals.runs.create(
            eval_id=evals[0].id,
            name=f"voice-simulation-{time.strftime('%Y%m%d-%H%M%S')}",
            data_source={
                "type": "azure_ai_user_conversation_simulation",
                "source": {"type": "file_id", "id": dataset.id},
                "target": {"type": "azure_ai_agent", "name": agent.name, "version": version},
                "model_configuration": {"model": EVAL["simulation"]["model"], "voice_model": VOICE},
                "default_simulation_configuration": {
                    "max_num_turns": EVAL["simulation"]["maxTurns"],
                    "conversation_repetitions": EVAL["simulation"]["numConversations"],
                    "audio_effects": AUDIO_EFFECTS,
                },
            },
            extra_body={"evaluation_level": "conversation"},
        )
        print(f"Started run {run.id} on {agent.name} version {version}. Waiting for it to finish...")
        while run.status not in ("completed", "failed", "canceled"):
            time.sleep(20)
            run = openai.evals.runs.retrieve(run_id=run.id, eval_id=evals[0].id)
        print(f"Status: {run.status}")
        print(json.dumps(run.model_dump().get("per_testing_criteria_results"), indent=2))
        if run.status != "completed":
            print(json.dumps(run.model_dump().get("error"), indent=2))
        print(f"Per-conversation results: azd ai eval run output --eval {evals[0].id} --run {run.id}")


if __name__ == "__main__":
    main()
