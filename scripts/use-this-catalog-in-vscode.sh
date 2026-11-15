#!/usr/bin/env bash
# Point the Foundry Toolkit for VS Code at this repository's solution-template catalog.
#
# The extension reads its "Solution templates" list from a fixed location in
# microsoft/foundry-dev-tools. This script patches the installed extension so it
# reads solution-template-catalog.json from this repository instead. The catalog
# here includes Microsoft's templates too, so nothing disappears.
#
# Local and unsupported: it edits installed extension files. An extension update
# installs a fresh, unpatched copy, so run this again after updating. --undo
# restores the original files.
#
# Usage:
#   scripts/use-this-catalog-in-vscode.sh            # patch every installed copy
#   scripts/use-this-catalog-in-vscode.sh --undo     # restore the original files
#   scripts/use-this-catalog-in-vscode.sh --repo owner/name --ref branch
set -euo pipefail

REPO="lordlinus/foundry-solution-templates"
REF="main"
CATALOG_PATH="solution-template-catalog.json"
UNDO=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --undo) UNDO=true ;;
    --repo) REPO="$2"; shift ;;
    --ref) REF="$2"; shift ;;
    --path) CATALOG_PATH="$2"; shift ;;
    -h | --help) sed -n '2,17p' "$0"; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

# VS Code, VS Code Insiders, and their remote servers (WSL, SSH, containers).
shopt -s nullglob
bundles=()
for base in "$HOME/.vscode" "$HOME/.vscode-insiders" "$HOME/.vscode-server" "$HOME/.vscode-server-insiders"; do
  for dir in "$base"/extensions/ms-windows-ai-studio.windows-ai-studio-*; do
    [[ -f "$dir/dist/extension.js" ]] && bundles+=("$dir/dist/extension.js")
  done
done
if [[ ${#bundles[@]} -eq 0 ]]; then
  echo "Foundry Toolkit (ms-windows-ai-studio.windows-ai-studio) is not installed in this environment." >&2
  echo "On WSL or a remote host, run this script on that host." >&2
  exit 1
fi

if [[ "$UNDO" == true ]]; then
  for bundle in "${bundles[@]}"; do
    bundled="$(dirname "$(dirname "$bundle")")/ai-foundry/templates/solution/solution-template-catalog.json"
    for file in "$bundle" "$bundled"; do
      if [[ -f "$file.orig" ]]; then
        mv "$file.orig" "$file"
        echo "Restored: $file"
      else
        echo "Not patched: $file"
      fi
    done
  done
  echo "Reload VS Code (Developer: Reload Window) to use Microsoft's catalog again."
  exit 0
fi

URL="https://raw.githubusercontent.com/$REPO/$REF/$CATALOG_PATH"
# Check the catalog first: if the extension cannot fetch or validate it, it silently falls back
# to its bundled list and you would not see your templates.
CATALOG_COPY="$(mktemp)"
trap 'rm -f "$CATALOG_COPY"' EXIT
python3 -I - "$URL" "$CATALOG_COPY" <<'PY'
import json, re, sys, urllib.request

url, copy = sys.argv[1], sys.argv[2]
try:
    catalog = json.load(urllib.request.urlopen(url, timeout=15))
except Exception as exc:  # noqa: BLE001 - report any fetch or parse failure plainly
    sys.exit(f"Cannot use {url}: {exc}")
ids = [t.get("id") for t in catalog.get("templates", [])]
repo = re.compile(r"^https://github[.]com/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+/?$")
for t in catalog["templates"]:
    if not repo.match(t.get("repo", "")) or not t.get("githubUrl", "").startswith(t["repo"].rstrip("/") + "/tree/"):
        sys.exit(f"Catalog entry {t.get('id')} would be rejected by the extension.")
json.dump(catalog, open(copy, "w", encoding="utf-8"), indent=4, ensure_ascii=False)
print(f"Catalog OK: {len(ids)} templates ({', '.join(ids)})")
PY

for bundle in "${bundles[@]}"; do
  [[ -f "$bundle.orig" ]] || cp "$bundle" "$bundle.orig"
  # Always patch from the pristine copy, so running again with other values is safe.
  python3 -I - "$bundle.orig" "$bundle" "$REPO" "$CATALOG_PATH" "$REF" <<'PY'
import sys

source, target, repo, path, ref = sys.argv[1:]
text = open(source, encoding="utf-8").read()
replacements = [
    ('"microsoft/foundry-dev-tools"', f'"{repo}"'),
    ('"samples/hosted-agent/solution-template-catalog.json"', f'"{path}"'),
    (
        '{local:"template/dev","pre-release":"template/pre-release",stable:"template/stable"}',
        f'{{local:"{ref}","pre-release":"{ref}",stable:"{ref}"}}',
    ),
]
for old, new in replacements:
    count = text.count(old)
    if count != 1:
        sys.exit(f"{source}: expected exactly one {old}, found {count}. This extension version is not supported.")
    text = text.replace(old, new)
open(target, "w", encoding="utf-8").write(text)
PY
  echo "Patched: $bundle"
  # The extension shows its bundled catalog on the first open after each reload and swaps in the
  # remote one only on a later open (the fetch runs in the background). Replace the bundled copy
  # too, so the first open already lists these templates.
  bundled="$(dirname "$(dirname "$bundle")")/ai-foundry/templates/solution/solution-template-catalog.json"
  if [[ -f "$bundled" ]]; then
    [[ -f "$bundled.orig" ]] || cp "$bundled" "$bundled.orig"
    cp "$CATALOG_COPY" "$bundled"
    echo "Replaced bundled catalog: $bundled"
  fi
done

echo "Reload VS Code (Developer: Reload Window), then open Create Agent > Solution templates."
echo "Catalog: $URL"
