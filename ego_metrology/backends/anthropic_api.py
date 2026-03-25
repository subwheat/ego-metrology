"""
ego_metrology.backends.anthropic_api
=====================================
Backend Anthropic API (claude-haiku, claude-sonnet, etc.)
"""

from __future__ import annotations

import json
import os
import ssl
import time
from typing import Optional
from urllib.request import Request, urlopen

from ego_metrology.backends.base import BackendResult, GenerationBackend


class AnthropicBackend(GenerationBackend):
    """
    Backend pour l'API Anthropic (/v1/messages).

    Par défaut, la vérification SSL est activée.
    Un mode permissif est disponible uniquement via verify_ssl=False,
    pour du debug explicite en environnement de développement.
    """

    def __init__(
        self,
        model_name: str = "claude-haiku-4-5-20251001",
        api_key: Optional[str] = None,
        max_tokens: int = 512,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        timeout: int = 120,
        verify_ssl: bool = True,
    ) -> None:
        self._model_name = model_name
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.system_prompt = system_prompt
        self.timeout = timeout
        self.verify_ssl = verify_ssl

    def generate(
        self,
        *,
        prompt: str,
        model_name: str,
        policy_id: str,
        seed: Optional[int] = None,
    ) -> BackendResult:
        effective_model = self._model_name or model_name

        payload: dict = {
            "model": effective_model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.system_prompt:
            payload["system"] = self.system_prompt

        body = json.dumps(payload).encode("utf-8")
        req = Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )

        t0 = time.perf_counter()
        ctx = ssl.create_default_context()
        if not self.verify_ssl:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        with urlopen(req, timeout=self.timeout, context=ctx) as resp:
            raw = resp.read()
        latency_ms = (time.perf_counter() - t0) * 1000

        data = json.loads(raw)
        response_text = data["content"][0]["text"]
        usage = data.get("usage", {})

        return BackendResult(
            response_text=response_text,
            prompt_tokens=usage.get("input_tokens"),
            completion_tokens=usage.get("output_tokens"),
            latency_ms=round(latency_ms, 2),
            backend_meta={
                "backend": "anthropic_api",
                "model_name": effective_model,
                "policy_id": policy_id,
                "stop_reason": data.get("stop_reason"),
                "anthropic_id": data.get("id"),
                "verify_ssl": self.verify_ssl,
            },
        )
