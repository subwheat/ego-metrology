"""
tests/test_anthropic_backend.py
===============================
Tests ciblés pour le backend Anthropic.

Couvre :
1. SSL vérifié par défaut
2. mode permissif seulement en opt-in explicite
3. retour BackendResult minimalement cohérent
"""

import json
import ssl

from ego_metrology.backends.anthropic_api import AnthropicBackend


class DummySSLContext:
    def __init__(self):
        self.check_hostname = True
        self.verify_mode = ssl.CERT_REQUIRED


class DummyResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_ssl_verified_by_default(monkeypatch):
    captured = {}

    def fake_create_default_context():
        ctx = DummySSLContext()
        captured["context"] = ctx
        return ctx

    def fake_urlopen(req, timeout, context):
        captured["timeout"] = timeout
        captured["context_passed"] = context
        return DummyResponse(
            {
                "id": "msg_default",
                "stop_reason": "end_turn",
                "content": [{"text": "Secure default response"}],
                "usage": {"input_tokens": 11, "output_tokens": 7},
            }
        )

    monkeypatch.setattr(
        "ego_metrology.backends.anthropic_api.ssl.create_default_context",
        fake_create_default_context,
    )
    monkeypatch.setattr("ego_metrology.backends.anthropic_api.urlopen", fake_urlopen)

    backend = AnthropicBackend(api_key="test-key")
    result = backend.generate(
        prompt="hello",
        model_name="ignored-model",
        policy_id="single_pass",
    )

    ctx = captured["context"]
    assert captured["context_passed"] is ctx
    assert ctx.check_hostname is True
    assert ctx.verify_mode == ssl.CERT_REQUIRED

    assert result.response_text == "Secure default response"
    assert result.prompt_tokens == 11
    assert result.completion_tokens == 7
    assert result.backend_meta["verify_ssl"] is True


def test_ssl_bypass_requires_explicit_opt_in(monkeypatch):
    captured = {}

    def fake_create_default_context():
        ctx = DummySSLContext()
        captured["context"] = ctx
        return ctx

    def fake_urlopen(req, timeout, context):
        captured["context_passed"] = context
        return DummyResponse(
            {
                "id": "msg_insecure",
                "stop_reason": "end_turn",
                "content": [{"text": "Insecure opt-in response"}],
                "usage": {"input_tokens": 5, "output_tokens": 3},
            }
        )

    monkeypatch.setattr(
        "ego_metrology.backends.anthropic_api.ssl.create_default_context",
        fake_create_default_context,
    )
    monkeypatch.setattr("ego_metrology.backends.anthropic_api.urlopen", fake_urlopen)

    backend = AnthropicBackend(api_key="test-key", verify_ssl=False)
    result = backend.generate(
        prompt="hello",
        model_name="ignored-model",
        policy_id="single_pass",
    )

    ctx = captured["context"]
    assert captured["context_passed"] is ctx
    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_NONE

    assert result.response_text == "Insecure opt-in response"
    assert result.prompt_tokens == 5
    assert result.completion_tokens == 3
    assert result.backend_meta["verify_ssl"] is False
