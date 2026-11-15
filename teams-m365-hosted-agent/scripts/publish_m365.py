"""Publish the hosted agent to Microsoft Teams and Microsoft 365 Copilot.

Calls Foundry's Microsoft 365 publish API, which registers the agent with Teams (no Azure Bot
Service resource), builds the Teams app package, submits it to the Teams and Microsoft 365 Copilot
agent stores, and turns on the Activity protocol plus a Bot Service authorization scheme on the
agent endpoint. Runs as azd's postdeploy hook; run it directly to republish or to download the
package:

    python scripts/publish_m365.py               # publish (idempotent per TEAMS_APP_VERSION)
    python scripts/publish_m365.py --download    # save appPackage.zip instead of publishing

Settings come from the azd environment (azd passes them to hooks as environment variables):
    FOUNDRY_PROJECT_ENDPOINT   set by the Foundry layer
    TEAMS_PUBLISH              "false" skips publishing (default "true")
    TEAMS_PUBLISH_SCOPE        "Shared" (only you, no approval; default) or "Tenant"
                               (whole organization, needs Microsoft 365 admin approval)
    TEAMS_APP_VERSION          app package version (default "1.0.0"); increase it to update
                               the name, descriptions or URLs shown in Teams

The publish API exchanges the caller's own delegated token on behalf of the user, so it must run
as a signed-in user (az login). A service principal or managed identity gets an opaque 502.
Standard library only, so the hook needs no extra installs.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

AGENT_NAME = "claims-triage"
API_VERSION = "v1"
REPO_URL = "https://github.com/lordlinus/foundry-solution-templates"


def publish_body() -> dict:
    scope = os.environ.get("TEAMS_PUBLISH_SCOPE", "Shared")
    if scope not in ("Shared", "Tenant"):
        sys.exit(f"TEAMS_PUBLISH_SCOPE must be Shared or Tenant, not {scope!r}.")
    return {
        "agentDisplayName": "Claims Triage",
        "performBotRegistration": True,
        "publishScope": scope,
        "publishAsAutopilot": False,
        "appVersion": os.environ.get("TEAMS_APP_VERSION", "1.0.0"),
        "shortDescription": "Triage synthetic insurance claims.",
        "fullDescription": (
            "A Microsoft Foundry hosted agent that lists flagged insurance claims, looks up a claim, "
            "and escalates a claim to investigators. Sample data is synthetic."
        ),
        "developerName": "Foundry solution templates",
        "developerWebsiteUrl": REPO_URL,
        "privacyUrl": os.environ.get("TEAMS_PRIVACY_URL", "https://privacy.microsoft.com"),
        "termsOfUseUrl": os.environ.get("TEAMS_TERMS_URL", "https://www.microsoft.com/legal/terms-of-use"),
    }


def az_token() -> str:
    az = shutil.which("az")
    if not az:
        sys.exit("Azure CLI (az) is required. Install it and run az login.")
    out = subprocess.run(
        [
            az,
            "account",
            "get-access-token",
            "--resource",
            "https://ai.azure.com",
            "--query",
            "accessToken",
            "-o",
            "tsv",
        ],
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        sys.exit(f"az could not get a token for https://ai.azure.com: {out.stderr.strip()}")
    return out.stdout.strip()


def is_user_token(token: str) -> bool:
    payload = token.split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    return claims.get("idtyp") == "user" or "upn" in claims or "unique_name" in claims


def call(url: str, token: str, body: dict) -> tuple[int, bytes]:
    data = json.dumps(body).encode()
    for attempt in range(5):
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as err:
            if err.code in (429, 500, 503) and attempt < 4:
                time.sleep(int(err.headers.get("Retry-After", 2**attempt * 5)))
                continue
            return err.code, err.read()
    raise AssertionError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--download", action="store_true", help="Save the app package as appPackage.zip.")
    args = parser.parse_args()

    if os.environ.get("TEAMS_PUBLISH", "true").lower() == "false" and not args.download:
        print("TEAMS_PUBLISH is false: skipping Teams and Microsoft 365 publishing.")
        return 0
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "").rstrip("/")
    if not endpoint:
        sys.exit("FOUNDRY_PROJECT_ENDPOINT is not set. Run this from the template folder after azd provision.")

    token = az_token()
    if not is_user_token(token):
        # Not an error for azd: the agent is deployed; publishing just has to happen as a user.
        print(
            "Skipping publish: az is signed in as a service principal or managed identity. The Microsoft 365 "
            "publish API acts on behalf of a signed-in user. Run az login as a user, then "
            "python scripts/publish_m365.py."
        )
        return 0

    body = publish_body()
    action = "zip" if args.download else "publish"
    status, payload = call(
        f"{endpoint}/agents/{AGENT_NAME}/microsoft365/{action}?api-version={API_VERSION}", token, body
    )
    text = payload.decode("utf-8", "replace") if action == "publish" or status >= 300 else ""

    if args.download:
        if status != 200:
            sys.exit(f"Package download failed ({status}): {text[:600]}")
        with open("appPackage.zip", "wb") as handle:
            handle.write(payload)
        print("Saved appPackage.zip. Upload it in Teams: Apps > Manage your apps > Upload an app.")
        return 0

    if status >= 300 and "already exists" in text.lower():
        print(
            f"Version {body['appVersion']} is already published. New agent versions reach Teams automatically; "
            "to change the name or descriptions there, set TEAMS_APP_VERSION to a higher version and rerun."
        )
        return 0
    if status >= 300:
        sys.exit(f"Publishing to Teams and Microsoft 365 failed ({status}): {text[:800]}")

    print(
        f"Published '{body['agentDisplayName']}' version {body['appVersion']} ({body['publishScope']} scope): {text[:300]}"
    )
    if body["publishScope"] == "Shared":
        print(
            "Find it in Teams or Microsoft 365 Copilot under Agents > Your agents (the store cache can take up to an hour)."
        )
    else:
        print(
            "A Microsoft 365 admin must approve it: https://admin.cloud.microsoft/?#/agents/all/requested . "
            "After approval it appears under Built by your org."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
