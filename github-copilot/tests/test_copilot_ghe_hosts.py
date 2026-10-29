"""GHE.com data-residency tenants: the Copilot API lives on ``copilot-api.<tenant>.ghe.com`` and rejects a
request without the editor headers (raw ``ghu_`` → 403 Terms of Service, exchanged token → 400 "missing
Editor-Version header for IDE auth"), so that host gets the same headers as githubcopilot.com. The token
exchange and the ``/models`` catalog go to the tenant's hosts, not github.com's."""

from __future__ import annotations

import pytest

GHE = "https://copilot-api.acme.ghe.com"


@pytest.mark.parametrize("url, owned", [
    (GHE, True),
    ("https://copilot-api.acme.ghe.com/v1", True),
    ("https://api.acme.ghe.com", False),  # REST host, not the Copilot API
    ("https://copilot-api.ghe.com", False),
    ("https://copilot-api.a.b.ghe.com", False),
    ("https://copilot-api.acme.ghe.com.evil.test", False),
    ("https://evil.test/copilot-api.acme.ghe.com", False),
])
def test_ghe_copilot_api_host_is_exact(url, owned):
    from github_copilot_plugin.copilot.helpers import is_ghe_copilot_api_host

    assert is_ghe_copilot_api_host(url) is owned


def test_ghe_host_gets_editor_headers_and_max_completion_tokens():
    from agent.provider_route_hooks import route_answer

    headers = route_answer("client_headers", provider="copilot", base_url=GHE, api_key="ghu_x")
    assert headers["Editor-Version"].startswith("vscode/")
    assert headers["Copilot-Integration-Id"] == "vscode-chat"
    assert route_answer("max_tokens_param", provider="copilot", base_url=GHE, model="gpt-4.1") == "max_completion_tokens"


def test_ghe_lookalike_gets_no_editor_headers():
    from agent.provider_route_hooks import route_answer

    assert not route_answer("client_headers", provider="copilot", base_url="https://copilot-api.acme.ghe.com.evil.test")


def test_editor_headers_on_the_wire_of_a_ghe_turn():
    from conftest import offline_chat_turn

    requests = offline_chat_turn(GHE, model="gpt-4.1")
    assert requests, "the turn sent no chat request"
    assert requests[0].headers.get("editor-version", "").startswith("vscode/")
    assert requests[0].headers.get("copilot-integration-id") == "vscode-chat"


@pytest.mark.parametrize("configured, expected", [
    ("", "https://api.github.com/copilot_internal/v2/token"),
    ("https://api.githubcopilot.com", "https://api.github.com/copilot_internal/v2/token"),
    (GHE, "https://api.acme.ghe.com/copilot_internal/v2/token"),
    ("https://api.acme.ghe.com", "https://api.acme.ghe.com/copilot_internal/v2/token"),
])
def test_token_exchange_goes_to_the_tenant(configured, expected, monkeypatch):
    from github_copilot_plugin.copilot import credentials

    monkeypatch.setattr(credentials, "get_secret", lambda name: configured if name == "COPILOT_API_BASE_URL" else "")
    assert credentials._token_exchange_url() == expected


@pytest.mark.parametrize("configured, expected", [
    ("", "https://api.githubcopilot.com/models"),
    (GHE + "/", GHE + "/models"),
    ("https://example.test", "https://api.githubcopilot.com/models"),
])
def test_models_catalog_reads_the_tenant_host(configured, expected, monkeypatch):
    import agent.secret_scope as secret_scope
    from github_copilot_plugin.copilot import catalog

    monkeypatch.setattr(secret_scope, "get_secret", lambda name: configured if name == "COPILOT_API_BASE_URL" else "")
    assert catalog.copilot_models_url() == expected
