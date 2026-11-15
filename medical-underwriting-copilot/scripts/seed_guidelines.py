"""Create the guidelines search index and upload data/guidelines/*.md, one document per section.

Runs as the azd postprovision hook with the deploying user's Azure CLI sign-in, which the
Bicep layer grants Search Index Data Contributor. Idempotent: re-running replaces the documents.
Needs only the Python standard library and the Azure CLI.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_VERSION = "2024-07-01"
GUIDELINES = Path(__file__).resolve().parents[1] / "data" / "guidelines"
INDEX = {
    "fields": [
        {"name": "id", "type": "Edm.String", "key": True, "filterable": True},
        {"name": "title", "type": "Edm.String", "searchable": True, "retrievable": True},
        {"name": "content", "type": "Edm.String", "searchable": True, "retrievable": True},
        {"name": "source", "type": "Edm.String", "filterable": True, "retrievable": True},
    ]
}


def sections(path: Path) -> list[dict]:
    """One search document per '## ' section, titled with the section heading."""
    text = path.read_text(encoding="utf-8")
    docs = []
    for block in re.split(r"^## ", text, flags=re.MULTILINE)[1:]:
        title, _, body = block.partition("\n")
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        docs.append({"id": f"{path.stem}-{slug}", "title": title.strip(), "content": body.strip(), "source": path.name})
    return docs


def token() -> str:
    az = shutil.which("az") or shutil.which("az.cmd")
    if not az:
        sys.exit("Azure CLI (az) is required to seed the guidelines index.")
    out = subprocess.run(
        [az, "account", "get-access-token", "--resource", "https://search.azure.com", "-o", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(out.stdout)["accessToken"]


def call(method: str, url: str, body: dict, bearer: str) -> None:
    request = urllib.request.Request(
        f"{url}?api-version={API_VERSION}",
        method=method,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {bearer}", "Content-Type": "application/json"},
    )
    # New role assignments can take a few minutes to apply; retry on 403.
    for attempt in range(20):
        try:
            with urllib.request.urlopen(request) as response:
                response.read()
                return
        except urllib.error.HTTPError as err:
            if err.code != 403 or attempt == 19:
                raise SystemExit(f"{method} {url} failed: {err.code} {err.read().decode()[:300]}") from err
            time.sleep(15)


def main() -> None:
    endpoint = os.environ["SEARCH_ENDPOINT"].rstrip("/")
    index = os.environ["SEARCH_INDEX_NAME"]
    docs = [d for f in sorted(GUIDELINES.glob("*.md")) for d in sections(f)]
    bearer = token()
    call("PUT", f"{endpoint}/indexes/{index}", {"name": index, **INDEX}, bearer)
    call(
        "POST",
        f"{endpoint}/indexes/{index}/docs/index",
        {"value": [{"@search.action": "mergeOrUpload", **d} for d in docs]},
        bearer,
    )
    print(f"Seeded {len(docs)} guideline sections into {index}.")


if __name__ == "__main__":
    main()
