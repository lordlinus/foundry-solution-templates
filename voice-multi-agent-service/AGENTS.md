# Contributor guidance

This template is a Microsoft Foundry **voice agent** (`kind: voice`, preview) with three
inline stages, fronted by a small web relay. Read `docs/architecture.md` before changing the
agent definition, the relay, or the audio path.

Preserve these invariants:

- **The browser never holds an Azure token.** It talks only to `/realtime` on the web app; the
  relay opens the Foundry session with the web app's managed identity.
- **The relay is the trust boundary.** It forwards only audio, interruption, and plain user-text
  events from the browser (`filterClientEvent` in `src/web/relay.mjs`). Never forward
  `session.update`, `function_call_output` items, or response overrides from the browser.
- **Card tools run in the relay, bound to the signed-in user.** The model never chooses whose
  cards it touches. Tool code runs only after the response that requested it completes.
- **Every change is two steps.** `request_card_action` stages; `confirm_card_action` executes
  once per `action_id`. Keep this in code, not only in instructions.
- **Fraud and theft go to urgent support from every customer-facing stage.**
- **No transcripts or audio in the relay's logs.** `store` stays `false`; the relay logs tool calls only. The voice service's own traces do contain transcripts when Application Insights is connected; don't claim otherwise (see `docs/architecture.md`).
- **Synthetic data only.** Contoso Bank and every card, customer, and reference are fictional.
- **Every function tool in `agent/voice-agent.json` is implemented in `src/web/tools.mjs`.**
  `tests/test_contracts.py` checks this.

Voice agents are a gated preview. The agent definition is published by
`scripts/publish_voice_agent.py` (azd `postprovision` hook) because the azd agent extension
can't deploy `kind: voice` yet. Each publish creates a new agent version.

Validate offline before you open a pull request:

```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check . && pytest
cd src/web && npm ci && npm test
az bicep build --file infra/app.bicep --stdout > /dev/null
```

A change to the agent, relay, or audio path is done only when a real spoken conversation
works in a browser (see the README's validation section) and the simulation eval in
`evals/` still passes its rubric.

Known tooling behaviors (azd 1.37.3, `azure.ai.projects` 1.1.0, `azure.ai.evaluations` 1.0.0-beta.2):

- The `microsoft.foundry` layer saves the project's model deployments in `AI_PROJECT_DEPLOYMENTS`
  on first provision and reuses it. If you add a deployment to `azure.yaml` later, remove that key
  from `.azure/<env>/.env` before `azd provision`, or the new deployment is never created.
- `azd ai eval init` rewrites `azure.yaml` and drops comments. Restore them afterwards.
- Publishing an unchanged voice-agent definition returns the existing version; only changes create a
  new one.
