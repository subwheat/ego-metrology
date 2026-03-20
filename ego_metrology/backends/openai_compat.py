"""
ego_metrology.backends.openai_compat
=====================================
Backend compatible OpenAI pour vLLM, Scaleway, ou tout endpoint /v1/chat/completions.
"""

from __future__ import annotations

import time
from typing import Optional
from urllib.request import Request, urlopen
import json

from ego_metrology.backends.base import BackendResult, GenerationBackend


class OpenAICompatBackend(GenerationBackend):
    """
    Backend pour tout endpoint compatible OpenAI (/v1/chat/completions).

    Compatible avec vLLM, Scaleway Generative APIs, OpenAI, etc.
    """

    def __init__(
        self,
        base_url: str,
        model_name: Optional[str] = None,
        api_key: str = "no-key",
        max_tokens: int = 512,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
        timeout: int = 120,
    ) -> None:
        """
        Args:
            base_url:      URL de base, ex: "http://51.159.139.27:8000"
            model_name:    Nom du modèle servi. Si None, utilise celui passé à generate().
            api_key:       Clé API (optionnelle pour vLLM local).
            max_tokens:    Limite de tokens en sortie.
            temperature:   Température de sampling.
            system_prompt: System prompt injecté si fourni.
            timeout:       Timeout HTTP en secondes.
        """
        self.base_url = base_url.rstrip("/")
        self._model_name = model_name
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.system_prompt = system_prompt
        self.timeout = timeout

    def generate(
        self,
        *,
        prompt: str,
        model_name: str,
        policy_id: str,
        seed: Optional[int] = None,
    ) -> BackendResult:
        """Appelle /v1/chat/completions et retourne un BackendResult."""

        effective_model = self._model_name or model_name

        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": effective_model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if seed is not None:
            payload["seed"] = seed

        body = json.dumps(payload).encode("utf-8")
        req = Request(
            f"{self.base_url}/v1/chat/completions",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        t0 = time.perf_counter()
        with urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read()
        latency_ms = (time.perf_counter() - t0) * 1000

        data = json.loads(raw)

        choice = data["choices"][0]
        response_text = choice["message"]["content"]
        usage = data.get("usage", {})

        return BackendResult(
            response_text=response_text,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
            latency_ms=round(latency_ms, 2),
            backend_meta={
                "backend": "openai_compat",
                "model_name": effective_model,
                "policy_id": policy_id,
                "finish_reason": choice.get("finish_reason"),
                "vllm_id": data.get("id"),
            },
        )
