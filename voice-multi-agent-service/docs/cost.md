# Cost planning

Voice cost is driven by audio tokens and connected minutes, not by request count. This
template has no fixed monthly price. Figures below are Azure public retail rates in Sweden
Central as of **November 15, 2026**, from the
[Azure Retail Prices API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices).
This is a planning aid, not a quote.

| Item | Rate | Notes |
|---|---:|---|
| Voice agent, managed `gpt-realtime-2.1` — audio input | $32.00 / 1M tokens | **Unverified mapping.** Retail meter "gpt-realtime-2.1 Audio inp Gl". [Voice agent pricing](https://learn.microsoft.com/azure/foundry/agents/concepts/voice-agent-pricing) says managed models bill "as part of the voice agent" without naming the meter. |
| Voice agent, managed `gpt-realtime-2.1` — audio output | $64.00 / 1M tokens | **Unverified mapping.** Retail meter "gpt-realtime-2.1 Audio opt Gl". |
| Voice agent, cached audio input | $0.40 / 1M tokens | Instructions and earlier turns are re-sent every turn, much of it cached. |
| Container Apps (web relay) | $0.000024 / vCPU-s, $0.000003 / GiB-s active | Scales to zero; first 180,000 vCPU-s and 360,000 GiB-s per subscription each month are free. A connected call keeps the replica active. |
| Container Registry Basic | $0.1666 / day (about $5 / month) | The only always-on cost. |
| `gpt-5-mini` deployment | Pay per token | Used only for evaluation (simulated caller and judge). Idle deployments cost nothing. |

**Measure, don't estimate, tokens per minute.** Audio token counts depend on the model and how
much each side talks. Voice agent traces carry per-turn token usage and estimated cost under
`microsoft.foundry.voice.estimated_cost.*`, and the agent's **Monitor** tab shows audio tokens
per session. Run a few representative calls and multiply.

Ways to reduce cost, from the pricing doc and this template's design:

- Keep instructions short; they are re-sent every turn.
- Keep `store: false` unless you need recordings.
- End calls deliberately: the `end` stage calls `end_conversation`.
- Scope tools per stage; each attached tool adds tokens to every turn.

Remove disposable environments with `azd down --purge`, then delete the app registration
(see the README).
