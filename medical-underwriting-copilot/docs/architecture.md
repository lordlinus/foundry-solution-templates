# Architecture

## Request flow

1. **Sign-in.** Container Apps built-in authentication signs the underwriter in
   with Microsoft Entra ID and adds `x-ms-client-principal-id` to every request.
2. **Upload and OCR.** `POST /api/cases` sends the PDF to Content Understanding
   (`prebuilt-layout`) with the web app's managed identity. The result is
   markdown with page breaks plus a confidence score for every word.
3. **Low-confidence numbers.** Only tokens that contain a digit and score below
   0.8 are flagged. A misread number (a lab value, a date, a dose) changes a
   decision silently; a misread word is obvious on the page, and flagging every
   word produces noise reviewers learn to ignore.
4. **Case files in the user's session.** The web app ensures one agent session
   per user (`u-<principal id>`), passing the user's principal ID in
   `x-ms-user-identity`, and uploads through the session files API:
   - `cases/<id>.md`: OCR notes, then the record with `<!-- page N -->` markers;
   - `cases/<id>.pdf`: the original, for the viewer;
   - `cases/<id>.json`: file name, page count, flags, and the run ID.
5. **Background run.** The web app starts a Responses run on the hosted agent
   with `background: true` and the user's `agent_session_id`, so the run
   continues if the browser leaves. The browser polls `GET /api/cases/<id>`,
   which reads the run ID from the user's own session file, never from the
   browser.
6. **Drafting.** The agent loads its two skills, reads the record a few pages
   at a time with `read_case_record`, searches the guidelines (hosted Azure AI
   Search tool, through a project connection), optionally consults the ICD-10
   and PubMed MCP servers (hosted MCP tools), and calls `submit_report`.
7. **Second-model review.** `submit_report` sends the full OCR source and the
   draft to a different model with a strict rubric (`judge.py`). A failing draft
   returns `revise` with the issues; after one revision the report is released
   with the review attached, passed or not. The released report is written to
   `cases/<id>.report.json` in the session.
8. **Review in the UI.** When the run completes, the web app downloads the
   report and shows it beside the PDF. Each `p.N` citation reloads the viewer
   at that page.

## State

| Data | Where | Why |
|---|---|---|
| Record, PDF, report, case metadata | The user's Foundry agent session (`$HOME/cases`) | Foundry persists `$HOME` per session and isolates sessions; no extra storage service. |
| Run status and tool steps | The Foundry response (`store: true`) | Survives browser disconnects and web app restarts. |
| Revision count during a run | `cases/<id>.revisions` in the session | The agent is built per request, so the count cannot live in memory. |
| Underwriting guidelines | Azure AI Search index `underwriting-guidelines` | Searchable passages with titles the report can cite. |

Foundry syncs files the agent writes in `$HOME` to the session files API when a
turn ends. That is why the report is read after the run completes, and why the
page shows coarse status rather than live per-step progress while it runs.

## Security model

| Boundary | Control |
|---|---|
| Internet → web app | Entra sign-in; the app registration has no client secret (the web app's managed identity is its federated credential). |
| User → user | One agent session per signed-in user; every session call carries that user's `x-ms-user-identity`. Case and run IDs are resolved inside the user's own session. |
| Web app → Foundry | Managed identity with **Azure AI User** on the Foundry account (sessions, session files, responses, Content Understanding), plus a custom role with the `.../agents/endpoints/UserIdentityImpersonation/action` data action. No built-in role has it, and without it every call that carries `x-ms-user-identity` fails with 403. |
| Agent → guidelines | Hosted search tool through a project connection with Entra ID auth. The project and account identities have **Search Index Data Contributor** and **Search Service Contributor**, as Microsoft Learn requires; Index Data Reader alone fails with `tool_user_error`. Search has local (key) auth disabled. |
| Agent → MCP servers | Public third-party endpoints, called by the Foundry service. Disable with `MEDICAL_MCP_ENABLED=false`. |
| Telemetry | `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false` keeps record text out of the agent container's spans. The Foundry service's own spans still record prompts and replies, which include record text, whenever the project has Application Insights; see [Trace content](#trace-content). Before using real records, protect the Log Analytics tables or disconnect Application Insights. |

## Token cost per turn

Estimated at about 4 characters per token: instructions about 210 tokens, the
`submit_report` schema about 1,000, `read_case_record` about 140, and the two skill
descriptions about 100 each. The skill bodies (about 870 tokens together) load
only when the agent asks for them. The reviewer's rubric (about 220 tokens) is
sent once per review.

## Live validation findings

Deployed on 2026-11-15 to East US 2 (Search in West US 2), with azd 1.37.3,
`azure.ai.projects` 1.1.0 and `azure.ai.agents` 1.1.0. The live run used `gpt-5`
as the drafter because the test subscription had no `gpt-5.4-mini` quota.

- **Delegating users needs a custom role.** `x-ms-user-identity` calls failed
  with 403 "Caller is not authorized to delegate to another user" until the web
  identity (and, for local runs, the deployer) had the `UserIdentityImpersonation`
  data action. The Bicep now creates and assigns it.
- **The hosted Search tool needs contributor roles.** With Index Data Reader
  only, every search failed with `tool_user_error`. It worked once the
  documented roles propagated, which took about a minute.
- **Search capacity can run out per region.** East US 2 returned
  `InsufficientResourcesAvailable`; set `AZURE_SEARCH_LOCATION` to place Search
  elsewhere.
- **These worked as designed:** Content Understanding `prebuilt-layout` with
  Azure AI User and no default model deployments; skills loading on demand in the
  hosted runtime; the public ICD-10 and PubMed MCP servers with the custom
  `User-Agent`; the full report in one `submit_report` call; and the review loop
  (one draft was rejected and its revision passed).
- **Progress is coarse.** The background response lists no tool steps until the
  run completes, so the page shows only the run status while it works.
- **Still unverified:** whether azd fills `AZURE_PRINCIPAL_ID` on its own. The
  test set it explicitly, as the README describes.

## Trace content

Verified live on 2026-11-15: with `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false`,
no span from the agent container carried message content, but the Foundry service's own
`invoke_agent` and `chat` spans (`cloud_RoleName` `responsesapi`, `sdkVersion` `aifoundry-v1.0`)
contained the full `gen_ai.input.messages` and `gen_ai.output.messages`. `ENABLE_SENSITIVE_DATA`
and `AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED` did not change that.

According to [Foundry tracing and data handling](https://learn.microsoft.com/azure/foundry/observability/concepts/trace-data),
tracing records prompts and model inputs and outputs whenever the project is connected to
Application Insights, and disconnecting Application Insights is the only way to stop it. Control
who can read it instead: grant Log Analytics Reader sparingly, set the Log Analytics tables to
[protected](https://learn.microsoft.com/azure/azure-monitor/logs/protected-tables-configure) so
reading them needs Privileged Monitoring Data Reader, and set retention to what you need.

Check what your project records:

```kusto
dependencies
| where timestamp > ago(1h)
| summarize spans = count(), with_content = countif(isnotempty(customDimensions["gen_ai.input.messages"])) by cloud_RoleName
```
