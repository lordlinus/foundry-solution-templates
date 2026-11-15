# Cost planning

This template does not have a fixed monthly price. A low-usage deployment is
approximately **USD 8 per 730-hour month**. This is a planning example, not a
quote.

The estimate assumes 100 aggregate Hosted Agent session-hours at 0.5 vCPU and
1 GiB, and 1 million `gpt-5.4-mini` Global Standard input tokens and 0.2 million
output tokens.

| Item | Example calculation | Estimated USD/month |
|---|---:|---:|
| Hosted Agent session compute | `100 h × (0.5 × $0.10 + 1 × $0.01)` | $6.00 |
| GPT-5.4 mini Global Standard | `1M input × $0.75/M + 0.2M output × $4.50/M` | $1.65 |
| Teams and Microsoft 365 channel | Foundry registers the agent with Teams; no Azure Bot Service resource is created | $0.00 |
| **Illustrative total** | | **$7.65 (about $8)** |

The hosted-agent and model rates are taken from the upstream
[Enterprise Knowledge Agent cost plan](https://github.com/microsoft/Foundry-Agent-Solution-Templates/blob/main/enterprise-knowledge-agent/docs/cost.md)
(September 2026) and were **not re-verified** for this template; check the
pricing pages below. Nothing here is always on: hosted-agent compute runs only
during active sessions, and the model is billed per token.

The estimate excludes taxes, discounts, data transfer, and the Application
Insights and Log Analytics ingestion the Foundry layer enables for tracing.

Users don't need a Microsoft 365 Copilot license to use the agent in Microsoft
365 Copilot Chat or Teams. Without one, features that read shared tenant data
can incur usage-based charges; this agent reads no tenant data. See
[Licensing and cost considerations for Copilot extensibility](https://learn.microsoft.com/microsoft-365/copilot/extensibility/cost-considerations).

Official references: [Foundry Agent Service pricing](https://azure.microsoft.com/pricing/details/foundry-agent-service/)
and [Azure OpenAI pricing](https://azure.microsoft.com/pricing/details/azure-openai/).
Remove a disposable environment with `azd down --purge` (see the README for the
Teams app).
