import asyncio
import json
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from app.ai import FAILURE_ANSWERS, GeminiAssistant, GeminiProviderError


def test_missing_key_returns_safe_configuration_message(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assistant = GeminiAssistant()
    answer = asyncio.run(assistant.answer("hello", "en", []))
    assert answer == FAILURE_ANSWERS["not_configured"]
    assert assistant.used_fallback


def test_503_retries_with_bounded_exponential_backoff(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assistant = GeminiAssistant()
    calls = []
    delays = []

    def generate(payload, attempt):
        calls.append(attempt)
        raise GeminiProviderError("server", 503)

    async def sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(assistant, "_generate", generate)
    monkeypatch.setattr("app.ai.asyncio.sleep", sleep)
    answer = asyncio.run(assistant.answer("hello", "en", []))

    assert calls == [1, 2, 3, 4]
    assert delays == [1, 2, 4]
    assert answer == FAILURE_ANSWERS["server"]
    assert assistant.failure_category == "server"


def test_quota_failure_is_distinguished_and_retried(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assistant = GeminiAssistant()
    calls = []

    def generate(payload, attempt):
        calls.append(attempt)
        raise GeminiProviderError("quota", 429)

    async def no_wait(_delay):
        return None

    monkeypatch.setattr(assistant, "_generate", generate)
    monkeypatch.setattr("app.ai.asyncio.sleep", no_wait)
    answer = asyncio.run(assistant.answer("hello", "en", []))

    assert calls == [1, 2, 3, 4]
    assert answer == FAILURE_ANSWERS["quota"]
    assert assistant.failure_category == "quota"


def test_invalid_key_fails_without_retry(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assistant = GeminiAssistant()
    calls = []

    def generate(payload, attempt):
        calls.append(attempt)
        raise GeminiProviderError("invalid_key", 403)

    monkeypatch.setattr(assistant, "_generate", generate)
    answer = asyncio.run(assistant.answer("hello", "en", []))

    assert calls == [1]
    assert answer == FAILURE_ANSWERS["invalid_key"]


def test_gemini_http_failure_is_classified_without_logging_response_body(monkeypatch, caplog):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assistant = GeminiAssistant()
    body = json.dumps({"error": {"status": "UNAVAILABLE", "message": "private provider text"}}).encode()

    def fail_request(*_args, **_kwargs):
        raise HTTPError("https://example.invalid", 503, "Unavailable", {}, BytesIO(body))

    monkeypatch.setattr("app.ai.urlopen", fail_request)
    with pytest.raises(GeminiProviderError) as error:
        assistant._generate({"contents": []})

    assert error.value.category == "server"
    assert "private provider text" not in caplog.text


def test_malformed_gemini_response_is_safe(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    assistant = GeminiAssistant()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, _limit):
            return b'{"candidates": []}'

    monkeypatch.setattr("app.ai.urlopen", lambda *_args, **_kwargs: Response())
    with pytest.raises(GeminiProviderError) as error:
        assistant._generate({"contents": []})
    assert error.value.category == "malformed"


def test_chat_endpoint_returns_json_fallback_and_health_never_returns_key(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    fastapi_app = main.app.app
    fastapi_app.dependency_overrides[main.current_user] = lambda: SimpleNamespace(preferred_language="en")
    try:
        client = TestClient(main.app)
        response = client.post("/api/assistant/chat", json={"message": "Is this safe?"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["provider"] == "fallback"
        assert payload["provider_status"] == "not_configured"
        assert isinstance(payload["answer"], str) and payload["answer"]
        assert "api_key" not in json.dumps(client.get("/api/health").json()).lower()
    finally:
        fastapi_app.dependency_overrides.pop(main.current_user, None)
