# Foundry Solution Templates

End-to-end solution templates for Microsoft Foundry Hosted Agents. Each template
is a self-contained folder that deploys with one `azd up`.

The layout and catalog format match
[microsoft/Foundry-Agent-Solution-Templates](https://github.com/microsoft/Foundry-Agent-Solution-Templates),
so every template here can be listed in the Foundry Toolkit for VS Code
(**Create Agent → Solution templates**) or contributed upstream unchanged.

## Templates

| Template | What it demonstrates | Status |
|---|---|---|
| [AG-UI Web Client for a Hosted Agent](ag-ui-hosted-agent/) | A CopilotKit browser chat for a Hosted Agent over AG-UI, with Entra sign-in, per-user threads, and human approval of agent actions. | Validated live. Proposed upstream in [microsoft/Foundry-Agent-Solution-Templates#20](https://github.com/microsoft/Foundry-Agent-Solution-Templates/pull/20). |
| [Medical underwriting copilot](medical-underwriting-copilot/) | Scanned medical records → OCR → a grounded draft underwriting report, audited by a second model and reviewed beside the source. Synthetic data. | Validated live (2026-11-15). |
| Claims analyst on BYO-AKS | A hosted agent on your own AKS cluster with Kata-isolated sessions, plus its CopilotKit web app. | Planned; BYO-AKS is in private preview |

## Use a template

From VS Code, once a template is in the Foundry Toolkit catalog: **Create Agent →
Solution templates**, pick it, and follow its README.

From the command line:

```bash
git clone https://github.com/lordlinus/foundry-solution-templates
cd foundry-solution-templates/<template>
# follow the template's README; usually: azd env new, azd up
```

## How the VS Code catalog works

The Foundry Toolkit reads its list of solution templates from
`samples/hosted-agent/solution-template-catalog.json` in
[microsoft/foundry-dev-tools](https://github.com/microsoft/foundry-dev-tools)
(branch `template/stable`, `template/pre-release`, or `template/dev`, depending on
the extension build). "Create" downloads the entry's `repo` at `ref` from
`codeload.github.com` and extracts `path`.

This repository keeps its own [`solution-template-catalog.json`](solution-template-catalog.json)
in the same schema. To list a template in VS Code, copy its entry into a pull
request to `microsoft/foundry-dev-tools` (base `template/dev`); see
[microsoft/foundry-dev-tools#960](https://github.com/microsoft/foundry-dev-tools/pull/960)
for an example. Because the download is anonymous, this repository must stay
public.

## See these templates in VS Code now

Until a template is in Microsoft's catalog, you can point your own Foundry
Toolkit at this repository's catalog. It lists Microsoft's templates and the
ones here:

```bash
scripts/use-this-catalog-in-vscode.sh          # then: Developer: Reload Window
scripts/use-this-catalog-in-vscode.sh --undo   # back to Microsoft's catalog
```

The script edits the installed extension on the machine where it runs; for WSL
or Remote-SSH, run it on that host. It is unsupported: it checks that the
catalog is valid and that the extension version matches what it expects, and it
keeps a backup. An extension update replaces the patched files, so run it again
after updating. Microsoft's entries in this catalog are copied from
`microsoft/foundry-dev-tools` (`template/stable`) and don't update automatically.

## Contributing a template

Read [AGENTS.md](AGENTS.md). In short: one self-contained folder, synthetic data
only, no symlinks, offline checks in CI, a live `azd up` before release, and a
catalog entry that passes `python scripts/validate_catalog.py`.

## License

[MIT](LICENSE)
