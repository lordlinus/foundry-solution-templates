# Contributor guidance

This template publishes the same claims-triage hosted agent as
`ag-ui-hosted-agent` to Microsoft Teams and Microsoft 365 Copilot. Keep the two
agents identical so the catalog tells one story: one agent, several clients.

Preserve these invariants:

- **Use Foundry's native publishing.** `scripts/publish_m365.py` calls the
  Microsoft 365 publish API with `performBotRegistration: true`. Do not add an
  Azure Bot Service resource, an API Management gateway, or a Teams manifest of
  your own; Foundry generates and owns them. Read `docs/architecture.md` before
  changing this.
- **Publish as a signed-in user.** The publish API acts on behalf of the
  caller. A service principal or managed identity gets an opaque 502, so the
  script skips publishing instead of failing the deploy.
- **The agent speaks Responses only.** Foundry bridges it to the Activity
  protocol when it is published; don't add an Activity handler.
- **Default to `Shared` scope.** `Tenant` needs Microsoft 365 admin approval and
  exposes the agent to everyone in the organization.
- **Prompt and response text stays out of traces.**
  `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT` stays `false`.
- **Dependencies are pinned with `==`.** The agent is built remotely.

A change is done only when the agent answers in Teams or Microsoft 365 Copilot
after `azd up`. A successful publish call proves only that the package was
accepted.

Validate offline before you open a pull request:

```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check . && pytest
```

Sample data is synthetic. Do not add real customer, policy, or claim data.
