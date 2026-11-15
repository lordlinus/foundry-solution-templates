# Contributor guidance

Preserve these invariants:

- **Synthetic data only.** Sample records, guidelines, and test fixtures are
  fictional. Never add real or masked medical records, customer documents,
  customer names, or case identifiers. Regenerate the sample PDFs with
  `data/sample-records/generate.py`.
- **The agent drafts; it does not decide.** Keep the decision a recommendation
  and keep the human underwriter in the UI copy and the skills.
- **Every stated fact cites a page.** The schema requires `page` on evidence,
  visits, and labs. Do not remove it.
- **A different model reviews every draft.** `submit_report` calls the reviewer;
  one revision, then release with the failed review attached. Never report a
  failed review as passed.
- **Pending results are not interpreted.** Keep the `Not interpreted` rule in
  the schema, the skill, and the reviewer rubric.
- **Foundry owns the files.** Records, PDFs, and reports live in the user's
  agent session (`$HOME/cases`), reached through the session files API. Do not
  add a storage account or a database for them.
- **Per-user isolation.** The web app derives the session and
  `x-ms-user-identity` from the signed-in principal only, and reads run IDs from
  the user's own session, never from the browser.
- **Keyless.** Search has local auth disabled; the web app and the project use
  managed identities. No client secrets.
- **No record text in traces.** `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT`
  stays `false`.
- **Long rules go in skills, not instructions.** State the per-turn token cost of
  anything you add to `INSTRUCTIONS` or a tool schema.

Validate offline before a pull request:

```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check . && pytest
cd src/web && npm ci && npm run typecheck && npm test && npm run build
az bicep build --file infra/app.bicep --stdout > /dev/null
```
