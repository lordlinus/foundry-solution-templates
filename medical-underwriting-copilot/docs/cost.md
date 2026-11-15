# Cost planning

This template does not have a fixed monthly price. As of **November 15, 2026**, a
low-usage deployment is approximately **USD 108 per 730-hour month** at Azure
public retail rates in East US 2. This is a planning example, not a quote.

The estimate assumes 100 cases a month of about 10 pages each, 100 Hosted Agent
session-hours at 1 vCPU and 2 GiB, and per case about 60,000 input and 8,000
output tokens for drafting and 30,000 input and 2,000 output tokens for review.

| Item | Example calculation | Estimated USD/month | Source |
|---|---:|---:|---|
| Azure AI Search Basic | `730 h × $0.101/h` | $73.73 | Retail Prices API |
| Azure Container Registry Basic | `730 h × $0.1666/day ÷ 24` | $5.07 | Retail Prices API |
| Container Apps (web) | within the monthly free grant at this usage | $0.00 | Retail Prices API |
| Hosted Agent session compute | `100 h × (1 × $0.10 + 2 × $0.01)` | $12.00 | Unverified: rates from the upstream templates' cost notes |
| Content Understanding, layout | `1,000 pages × $7.50/1,000` | $7.50 | Unverified: the meter that applies to `prebuilt-layout` is assumed |
| gpt-5.4-mini (drafting) | `6M input × $0.75/M + 0.8M output × $4.50/M` | $8.10 | Unverified: rates from the upstream templates' cost notes |
| gpt-5-mini (review) | `3M input × $0.25/M + 0.2M output × $2.00/M` | $1.15 | Unverified |
| **Illustrative total** | | **$107.55 (about $108)** | |

Azure AI Search Basic is the main always-on cost. Everything else is usage
based, and the web app scales to zero. The Container Apps free grant applies once
per subscription. The estimate excludes taxes, discounts, data transfer,
Application Insights and Log Analytics ingestion, and the MCP servers (free
public endpoints today).

Use the [Azure Pricing Calculator](https://azure.microsoft.com/pricing/calculator/)
with your region and volumes before deployment, and remove disposable
environments with `azd down --purge`.

Official references: [Foundry Agent Service pricing](https://azure.microsoft.com/pricing/details/foundry-agent-service/),
[Azure OpenAI pricing](https://azure.microsoft.com/pricing/details/azure-openai/),
[Content Understanding pricing](https://azure.microsoft.com/pricing/details/content-understanding/),
[Azure AI Search pricing](https://azure.microsoft.com/pricing/details/search/),
[Azure Container Apps pricing](https://azure.microsoft.com/pricing/details/container-apps/),
and the [Azure Retail Prices API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices).
