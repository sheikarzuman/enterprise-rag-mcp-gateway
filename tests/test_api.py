from types import SimpleNamespace

import anthropic
import httpx
import pytest

from src import main
from src.mcp_server import db_server
from src.security import redact_pii
from tests.conftest import make_token

SOLVE = "/api/v1/solve"
PROMPT = "Turbine-002 bearing hub spike detected. Contact engineer john.doe@enterprise.com"


def body(include_telemetry_tool: bool = False) -> dict:
    return {"prompt": PROMPT, "include_telemetry_tool": include_telemetry_tool}


@pytest.fixture
def mock_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "mock-key")


def fake_anthropic(create):
    class FakeClient:
        def __init__(self, api_key):
            self.messages = SimpleNamespace(create=create)

    return FakeClient


class TestHealth:
    def test_health_returns_healthy(self, client):
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "service": "mcp-rag-gateway"}


class TestAuth:
    def test_missing_token_is_rejected(self, client):
        response = client.post(SOLVE, json=body())

        assert response.status_code in (401, 403)

    def test_token_signed_with_wrong_secret_is_401(self, client):
        token = make_token("admin", secret="not-the-real-secret")

        response = client.post(SOLVE, json=body(), headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 401

    def test_unknown_role_is_403(self, client):
        token = make_token("guest")

        response = client.post(SOLVE, json=body(), headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 403

    @pytest.mark.parametrize("role", ["admin", "analyst", "viewer"])
    def test_known_roles_are_accepted(self, client, mock_key, role):
        token = make_token(role)

        response = client.post(SOLVE, json=body(), headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200


class TestSolve:
    def test_redacts_email_but_keeps_equipment_id(self, client, auth_headers, mock_key):
        response = client.post(SOLVE, json=body(), headers=auth_headers)

        sanitized = response.json()["sanitized_prompt"]
        assert "Turbine-002" in sanitized
        assert "john.doe@enterprise.com" not in sanitized
        assert "<EMAIL_ADDRESS>" in sanitized

    def test_returns_retrieved_context(self, client, auth_headers, mock_key):
        response = client.post(SOLVE, json=body(), headers=auth_headers)

        assert [doc["id"] for doc in response.json()["retrieved_context"]] == ["SOP-801", "SOP-802"]

    def test_skips_telemetry_tool_when_not_requested(self, client, auth_headers, mock_key):
        response = client.post(SOLVE, json=body(include_telemetry_tool=False), headers=auth_headers)

        assert response.json()["mcp_tool_output"] == "Tool not requested."

    def test_includes_telemetry_output_when_requested(self, client, auth_headers, mock_key, monkeypatch):
        monkeypatch.setattr(main, "query_telemetry_db", lambda sql: "Columns: ['device_id'] | Rows: [('TURBINE-002',)]")

        response = client.post(SOLVE, json=body(include_telemetry_tool=True), headers=auth_headers)

        assert "TURBINE-002" in response.json()["mcp_tool_output"]

    def test_uses_offline_response_for_mock_key(self, client, auth_headers, mock_key):
        response = client.post(SOLVE, json=body(), headers=auth_headers)

        assert response.json()["synthesized_resolution"].startswith("[OFFLINE MOCK RESPONSE]")

    def test_uses_claude_text_when_call_succeeds(self, client, auth_headers, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        reply = SimpleNamespace(content=[SimpleNamespace(text="De-rate to 50% and flush lubricant.")])
        monkeypatch.setattr(main.anthropic, "Anthropic", fake_anthropic(lambda **kwargs: reply))

        response = client.post(SOLVE, json=body(), headers=auth_headers)

        assert response.json()["synthesized_resolution"] == "De-rate to 50% and flush lubricant."

    def test_falls_back_to_offline_when_claude_call_fails(self, client, auth_headers, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

        def fail(**kwargs):
            raise anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))

        monkeypatch.setattr(main.anthropic, "Anthropic", fake_anthropic(fail))

        response = client.post(SOLVE, json=body(), headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["synthesized_resolution"].startswith("[OFFLINE MOCK RESPONSE]")

    def test_falls_back_when_real_client_raises_api_error(self, client, auth_headers, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        error = anthropic.APIError(
            message="Invalid API Key",
            request=httpx.Request("POST", "https://api.anthropic.com"),
            body={"error": {"type": "authentication_error"}},
        )

        def raise_error(*args, **kwargs):
            raise error

        monkeypatch.setattr("anthropic.resources.messages.Messages.create", raise_error)

        response = client.post(
            SOLVE,
            headers=auth_headers,
            json={"prompt": "Turbine-002 alert", "include_telemetry_tool": False},
        )

        assert response.status_code == 200
        assert "[OFFLINE MOCK RESPONSE]" in response.json()["synthesized_resolution"]


class TestRedactPii:
    def test_redacts_phone_card_and_ip(self):
        text = "Call 415-555-0123, card 4111 1111 1111 1111, host 10.0.0.5"

        redacted = redact_pii(text)

        for leaked in ("415-555-0123", "4111 1111 1111 1111", "10.0.0.5"):
            assert leaked not in redacted

    @pytest.mark.parametrize("equipment_id", ["Turbine-002", "PUMP-104", "TURBINE-003"])
    def test_keeps_equipment_ids(self, equipment_id):
        assert equipment_id in redact_pii(f"{equipment_id} bearing hub temperature spike")


class TestTelemetryDb:
    def test_rejects_non_select_queries(self):
        result = db_server.query_telemetry_db("DROP TABLE enterprise_telemetry")

        assert result.startswith("Security Violation")

    def test_readonly_session_blocks_chained_writes(self):
        result = db_server.query_telemetry_db("SELECT 1; CREATE TABLE _readonly_probe (x int)")

        assert result.startswith("Database query execution failure")
        assert "read-only" in result.lower()

    def test_select_returns_seeded_rows(self):
        result = db_server.query_telemetry_db("SELECT device_id FROM enterprise_telemetry WHERE status = 'CRITICAL'")

        assert "TURBINE-003" in result
