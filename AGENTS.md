# Contributor guidance

This repository holds Microsoft Foundry solution templates in the same shape as
microsoft/Foundry-Agent-Solution-Templates. Each template must work when the
Foundry Toolkit downloads only its folder.

Every template must:

- **Be self-contained.** Nothing outside its folder is needed to build, test, or
  deploy it. Link to other templates with absolute GitHub URLs.
- **Contain no symlinks.** The extension rejects archives that contain them.
- **Use synthetic data only.** No customer names, documents, records, or
  identifiers, masked or not. State in the README that the data is synthetic.
- **Deploy with one `azd up`.** Use the `microsoft.foundry` layer (from the
  `azure.ai.projects` azd extension) for the Foundry account, project, and
  model. Do not add a custom `workflows.up` block: azd 1.37.3 stops extension
  hosts before the nested provision step.
- **Be keyless by default.** Managed identities and Entra ID; no client secrets
  or API keys in source, parameters, or outputs.
- **Pin dependencies** with `==` (Python) and a lockfile (Node).
- **Include** `README.md` (with "What this template is for / not for"),
  `AGENTS.md`, `docs/architecture.md`, `docs/cost.md`, and offline tests.
- **Have a catalog entry** in `solution-template-catalog.json` that passes
  `python scripts/validate_catalog.py`.

Before marking a template validated, deploy it live with `azd up`, verify the
user-facing behavior (not a proxy for it), tear it down, and record the date,
region, and tool versions in the template's README or pull request.

Do not publish a template that depends on a private-preview feature until it
is cleared for public documentation.
