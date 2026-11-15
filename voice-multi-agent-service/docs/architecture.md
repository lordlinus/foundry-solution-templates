# Architecture

## Request flow

```text
Browser mic ─PCM16 24 kHz─▶ web app /realtime (relay, Entra sign-in) ─wss + Entra token─▶ Foundry voice agent
     ▲                         │  runs card tools for the signed-in user          triage ─▶ card_services
     └──── agent audio ◀───────┘  forwards audio; filters browser events                 └▶ urgent_support ─▶ end
```

1. The user signs in through Container Apps built-in authentication and opens the page.
2. **Start call** opens a WebSocket to `/realtime` on the same web app. The relay checks the
   signed-in principal and opens
   `wss://<account>.services.ai.azure.com/api/projects/<project>/agents/card-service-voice/endpoint/protocols/voice?api-version=v1`
   with the web app's managed-identity token and the `Foundry-Features: VoiceAgents=V1Preview`
   header.
3. The voice agent greets, transcribes, detects turns, and speaks. Its definition
   (`agent/voice-agent.json`) has four inline stages: `$entrypoint` (triage), `card_services`,
   `urgent_support`, and `end`. Stages hand off through `handoff_conditions`; the service runs
   the handoff and emits `session.handoff.completed`, which the page shows as the active
   specialist.
4. When a stage calls a card tool, the service sends `response.function_call_arguments.done`.
   The relay waits for that response's `response.done`. If the response completed, it runs the
   tool for the signed-in user, returns `function_call_output`, and sends `response.create`.
   Cancelled or failed responses never run tools.

## Why this design

Researched November 2026. Sources:

| Source | Date | What it changed |
|---|---|---|
| [Migrate from Voice Live with Foundry Agent Service to Foundry voice agents](https://learn.microsoft.com/azure/foundry/agents/how-to/migrate-from-voice-live) | 2026-10-27 | Use a `kind: voice` agent instead of Voice Live in front of a text agent: lower latency, voice and greeting in one versioned definition, voice-pipeline tracing, built-in telephony. Connect with a header token, never a token in the URL or browser code. |
| [Create a voice-based prompt agent](https://learn.microsoft.com/azure/foundry/agents/quickstarts/prompt-voice-agent) | 2026-11-10 | Managed realtime model (no deployment), preview gated by subscription and region; `azd ai agent invoke` does not support voice. |
| [How to build a voice agent (Voice Live + text agent)](https://learn.microsoft.com/azure/ai-services/speech-service/how-to-voice-agent-integration) | 2026-09-30 | The previous approach. The doc itself recommends voice agents for new work. |
| [microsoft/voice-agent](https://github.com/microsoft/voice-agent) `example1_finance_with_handoff_realtime` | 2026-11-14 | Inline stages with `handoff_conditions`, `transfer_message`, `end_conversation`; managed model ids `gpt-realtime-2.1` → `gpt-realtime-1.5` → `gpt-realtime-2.1-mini`; eligibility named for `swedencentral` and `francecentral`. |
| [Voice agent tracing, monitoring, and evaluation](https://learn.microsoft.com/azure/foundry/agents/concepts/voice-agent-observability) | 2026-09-30 | Dataset, trace, and simulation evaluation with transcript-based evaluators; time to first audio is the main latency metric. |
| [Simulate conversations](https://learn.microsoft.com/azure/foundry/observability/how-to/cloud-evaluation-simulate-conversations) | 2026-10-07 | `azure_ai_user_conversation_simulation`, `voice_model`, `audio_effects`, interruption behavior. |
| `azure-ai-projects` 2.11.0 | 2026-11 | Realtime client is `project.voice_agents.realtime` (docs still show `beta.voice_agents.realtime`); `beta.voice_agents.live` is a different protocol. |

Alternatives considered:

- **Voice Live in front of a hosted Agent Framework or LangGraph agent** (what many earlier
  demos do). Every spoken turn passes through speech recognition, a separate agent call, and
  synthesis. Hand-written orchestration replaces handoffs the service now provides. Kept as a
  documented option: a voice agent can delegate to a hosted agent with `subagent_config` when
  specialist logic must be code.
- **Separate hosted agents per specialist with A2A.** More moving parts and latency for a
  three-stage call flow; inline stages share one session and context.
- **Card tools on an MCP server.** The service would run them, but the MCP server would not know
  which signed-in customer is calling. Native function tools run in the relay, which does.

## Security model

| Boundary | Control |
|---|---|
| Internet → web app | Microsoft Entra sign-in (built-in authentication). The app registration has no client secret; the web app's managed identity is its federated credential. WebSocket upgrades are authenticated the same way. |
| Browser → relay | The relay accepts only audio, interruption, and plain user-text events. It drops `session.update`, `function_call_output` items, and response overrides, so a modified client can't change the agent's instructions or fake a tool result. |
| Relay → Foundry | Web app managed identity with **Foundry User** (formerly Azure AI User) on the project. The browser never receives a token. |
| Tools → data | Tools run in the relay against the signed-in user's state. Changes are two-step (stage, then confirm), and confirmation runs once per `action_id`. |
| Content | `store` is `false`, so the service keeps no conversation record or audio, and the relay logs tool calls only. **Transcripts still reach telemetry:** with Application Insights connected (the `microsoft.foundry` layer connects it), the voice service's own spans (`cloud_RoleName` `agentsv2`) carry the caller's words in `gen_ai.input.messages`, the agent's replies in `gen_ai.output.messages`, and the instructions in `gen_ai.system_instructions`. See [Telemetry and privacy](#telemetry-and-privacy). |

## Telemetry and privacy

Measured on a live deployment (2026-11-15, Sweden Central): in one day of test calls, 252 of the
voice service's spans carried the caller's transcript in `gen_ai.input.messages` and 330 carried
the agent's replies in `gen_ai.output.messages`, all from `cloud_RoleName` `agentsv2`
(`sdkVersion` `aifoundry-v1.0`). `store: false` doesn't change this. It controls conversation
storage on the agent endpoint, not tracing.

Per [Trace data](https://learn.microsoft.com/azure/foundry/observability/concepts/trace-data)
(updated 2026-10-19), the service-side content can't be switched off while Application Insights is
connected to the project. Your controls are:

- **Access:** reading traces needs Log Analytics Reader; protected tables also need Privileged
  Monitoring Data Reader. Grant these narrowly.
- **Retention:** set Application Insights and Log Analytics retention to your policy.
- **Disconnect:** remove the project's Application Insights connection if transcripts must not be
  stored there at all. You lose voice tracing and the Monitor tab's details.

Check your own deployment with this query in the project's Application Insights:

```kusto
union dependencies, requests
| where timestamp > ago(1d)
| extend cd = todynamic(customDimensions)
| summarize spans = count(),
    with_input = countif(isnotempty(tostring(cd['gen_ai.input.messages']))),
    with_output = countif(isnotempty(tostring(cd['gen_ai.output.messages'])))
    by cloud_RoleName
```

## State

Card data and staged actions live in the web app's memory per signed-in user. They reset when
the container restarts, which is why the app runs a single replica. Replace `tools.mjs` with
calls to your own systems to make them durable.

## Audio

The browser captures mono PCM16 at 24 kHz with an AudioWorklet in one `AudioContext` and plays
agent audio in a second one, clearing queued playback when the caller starts speaking (barge-in).
In live testing, sharing one context let queued agent audio slow the capture clock to about a fifth
of real time partway through a call, so the agent stopped hearing the caller. Every node in the
capture graph is kept referenced and connected to the output through a muted gain.
Echo cancellation and noise suppression run server-side (`server_echo_cancellation`,
`azure_deep_noise_suppression`), so the browser's versions are off; stacking both can suppress
the caller while the agent speaks.

## Evaluation

Two evals in `evals/azure.eval.yaml`, both conversation-level, both scored by
`builtin.task_completion`, `builtin.customer_satisfaction`, and the custom rubric evaluator
`card-service-voice-rubric` (defined inline):

- **Trace-based** (`card-service-voice-traces`) scores real calls from Application Insights, including
  the relay's tool calls. It needs the project identity to read traces (Reader, Log Analytics Reader,
  and Privileged Monitoring Data Reader on both Application Insights and the workspace); the Bicep
  layer grants them.
- **Simulation** (`card-service-voice-simulation`): a model plays each caller in
  `caller-scenarios.jsonl`. Voice-agent targets require a simulated-caller `voice_model`, which azd's
  eval config can't express yet, so `evals/run_voice_simulation.py` starts the run with the SDK.
  Because the service runs the simulated call without the relay, native function tools never return;
  simulation measures routing, tone, safety, and scope, not card changes.

Per-row rubrics (`builtin.task_level_rubric` with `test_case_rubric`) don't work for simulated
conversations, which carry only messages; that's why the rubric is a project evaluator.
