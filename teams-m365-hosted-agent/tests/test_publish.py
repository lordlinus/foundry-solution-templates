"""Offline tests for scripts/publish_m365.py."""

import base64
import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "publish_m365.py"


@pytest.fixture
def pub(monkeypatch):
    spec = importlib.util.spec_from_file_location("publish_m365", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://x.services.ai.azure.com/api/projects/p")
    for name in ("TEAMS_PUBLISH", "TEAMS_PUBLISH_SCOPE", "TEAMS_APP_VERSION"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr("sys.argv", ["publish_m365.py"])
    return module


def token(claims: dict) -> str:
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"h.{body}.s"


USER = token({"idtyp": "user", "upn": "someone@contoso.com"})
APP = token({"idtyp": "app", "appid": "x"})


def test_default_body_is_personal_scope_with_bot_registration(pub):
    body = pub.publish_body()
    assert body["publishScope"] == "Shared" and body["performBotRegistration"] is True
    assert body["publishAsAutopilot"] is False and body["appVersion"] == "1.0.0"
    assert len(body["developerName"]) <= 32
    assert all(body[k].startswith("https://") for k in ("developerWebsiteUrl", "privacyUrl", "termsOfUseUrl"))


def test_rejects_unknown_scope(pub, monkeypatch):
    monkeypatch.setenv("TEAMS_PUBLISH_SCOPE", "Everyone")
    with pytest.raises(SystemExit):
        pub.publish_body()


def test_skips_when_not_signed_in_as_a_user(pub, monkeypatch, capsys):
    monkeypatch.setattr(pub, "az_token", lambda: APP)
    monkeypatch.setattr(pub, "call", lambda *a: pytest.fail("must not call the API as an app"))
    assert pub.main() == 0
    assert "on behalf of a signed-in user" in capsys.readouterr().out


def test_skips_when_disabled(pub, monkeypatch):
    monkeypatch.setenv("TEAMS_PUBLISH", "false")
    monkeypatch.setattr(pub, "az_token", lambda: pytest.fail("must not need a token"))
    assert pub.main() == 0


def test_publishes_to_the_agent_endpoint(pub, monkeypatch):
    seen = {}

    def call(url, tok, body):
        seen.update(url=url, body=body)
        return 200, b'{"titleId": "T1"}'

    monkeypatch.setattr(pub, "az_token", lambda: USER)
    monkeypatch.setattr(pub, "call", call)
    assert pub.main() == 0
    assert seen["url"].endswith("/agents/claims-triage/microsoft365/publish?api-version=v1")


def test_existing_version_is_not_an_error(pub, monkeypatch):
    monkeypatch.setattr(pub, "az_token", lambda: USER)
    monkeypatch.setattr(pub, "call", lambda *a: (400, b'{"error": "App version already exists"}'))
    assert pub.main() == 0


def test_other_failures_fail_the_hook(pub, monkeypatch):
    monkeypatch.setattr(pub, "az_token", lambda: USER)
    monkeypatch.setattr(pub, "call", lambda *a: (403, b'{"error": "forbidden"}'))
    with pytest.raises(SystemExit):
        pub.main()


def test_download_saves_the_package(pub, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["publish_m365.py", "--download"])
    monkeypatch.setattr(pub, "az_token", lambda: USER)
    monkeypatch.setattr(
        pub, "call", lambda url, *a: (200, b"PK\x03\x04zip") if url.split("?")[0].endswith("/zip") else pytest.fail(url)
    )
    assert pub.main() == 0
    assert (tmp_path / "appPackage.zip").read_bytes().startswith(b"PK")
