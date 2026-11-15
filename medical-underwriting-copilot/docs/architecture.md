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
| Web app → Foundry | Managed identity with **Azure AI User** on the Foundry account (sessions, session files, responses, Content Understanding). |
| Agent → guidelines | Hosted search tool through a project connection with Entra ID auth; the project identity has **Search Index Data Reader**. Search has local (key) auth disabled. |
| Agent → MCP servers | Public third-party endpoints, called by the Foundry service. Disable with `MEDICAL_MCP_ENABLED=false`. |
| Telemetry | `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false` keeps record text out of traces. |

## Token cost per turn

Estimated at about 4 characters per token: instructions about 210 tokens, the
`submit_report` schema about 1,000, `read_case_record` about 140, and the two skill
descriptions about 100 each. The skill bodies (about 870 tokens together) load
only when the agent asks for them. The reviewer's rubric (about 220 tokens) is
sent once per review.

## Verify on first deployment

These depend on live service behavior that offline checks cannot prove:

- The hosted Azure AI Search tool authenticates with the **project** managed
  identity through the `AAD` connection (the Bicep grants that identity
  Search Index Data Reader). If the hosted agent's own identity is used
  instead, grant it the same role.
- The hosted MCP tools accept the custom `User-Agent` header, and the
  third-party ICD-10 and PubMed endpoints are reachable from Foundry.
- `AZURE_PRINCIPAL_ID` is populated by azd for the Bicep layer (otherwise set it
  as the README describes).
- **Azure AI User** at account scope is enough for Content Understanding
  `prebuilt-layout` and for the session files API with `x-ms-user-identity`.
- `prebuilt-layout` needs no default model deployments on the account in the
  chosen region.
- The background response output lists tool calls while the run is in
  progress (the progress list may stay empty until completion).
- Agent Framework's `SkillsProvider` works inside the hosted runtime with
  approvals disabled, and the drafter fits the full report in one
  `submit_report` call for a 3-page record.
