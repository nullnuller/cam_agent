"""
Model invocation utilities for CAM.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import urlparse, urlunparse

import requests


def ensure_ollama_endpoint(endpoint: str, default_path: str) -> str:
    """
    Normalise a user-supplied Ollama endpoint.

    Accepts bare hosts (e.g. http://localhost:11434) or `/api` roots and ensures
    the required path suffix is present. Custom paths (e.g. reverse proxies that
    already point at `/api/generate`) are preserved as-is.
    """
    if not endpoint:
        return endpoint

    target_suffix = "/" + default_path.strip("/")
    parsed = urlparse(endpoint.strip())
    path = (parsed.path or "").rstrip("/")

    if not path:
        new_path = target_suffix
    elif path.endswith(target_suffix):
        new_path = path
    elif path == "/api" and target_suffix.startswith("/api/"):
        new_path = "/api" + target_suffix[len("/api") :]
    else:
        new_path = path

    normalised = parsed._replace(path=new_path or "/")
    return urlunparse(normalised).rstrip("/")


def _ollama_request(
    *,
    endpoint: str,
    payload: Dict[str, object],
    headers: Dict[str, str],
    timeout: int,
    model: str,
) -> Dict[str, object]:
    try:
        response = requests.post(endpoint, json=payload, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        raise RuntimeError(f"Ollama request failed for model '{model}' at {endpoint}: {exc}") from exc

    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        body = (response.text or "").strip()
        preview = body[:1000]
        if len(body) > len(preview):
            preview += "…"
        raise RuntimeError(
            f"Ollama HTTP {response.status_code} for model '{model}' at {endpoint}: {preview}"
        ) from exc

    try:
        return response.json()
    except ValueError as exc:
        body = (response.text or "").strip()
        preview = body[:500]
        if len(body) > len(preview):
            preview += "…"
        raise RuntimeError(
            f"Ollama returned non-JSON payload for model '{model}' at {endpoint}: {preview}"
        ) from exc


@dataclass(slots=True)
class LLMResponse:
    """Container for raw LLM output and metadata."""

    text: str
    model: str
    prompt: str
    temperature: float
    num_ctx: int
    num_predict: Optional[int]
    seed: Optional[int]


class LLMClient:
    """Thin wrapper around local (Ollama) or OpenAI-compatible HTTP APIs."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        auth_token: Optional[str] = None,
        api_mode: Optional[str] = None,
    ):
        mode = api_mode or os.getenv("LLM_API_MODE", "ollama")
        self.api_mode = mode.lower()
        if self.api_mode not in {"ollama", "ollama_chat", "openai"}:
            raise ValueError(
                f"Unsupported LLM_API_MODE '{self.api_mode}'. Expected 'ollama', 'ollama_chat', or 'openai'."
            )

        if self.api_mode == "openai":
            default_endpoint = "http://localhost:8000/v1/chat/completions"
            self.endpoint = endpoint or os.getenv("OPENAI_ENDPOINT", default_endpoint)
            self.auth_token = auth_token or os.getenv("OPENAI_API_KEY")
        elif self.api_mode == "ollama_chat":
            raw_endpoint = endpoint or os.getenv("OLLAMA_CHAT_ENDPOINT", "http://localhost:11434/api/chat")
            self.endpoint = ensure_ollama_endpoint(raw_endpoint, "api/chat")
            self.auth_token = auth_token or os.getenv("OLLAMA_BEARER")
        else:
            raw_endpoint = endpoint or os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434/api/generate")
            self.endpoint = ensure_ollama_endpoint(raw_endpoint, "api/generate")
            self.auth_token = auth_token or os.getenv("OLLAMA_BEARER")

    def call(
        self,
        model: str,
        prompt: str,
        *,
        temperature: float = 0.2,
        num_ctx: int = 8192,
        num_predict: Optional[int] = None,
        seed: Optional[int] = None,
        timeout: int = 600,
    ) -> LLMResponse:
        if self.api_mode == "openai":
            return self._call_openai(model, prompt, temperature, num_ctx, num_predict, seed, timeout)
        if self.api_mode == "ollama_chat":
            return self._call_ollama_chat(model, prompt, temperature, num_ctx, num_predict, seed, timeout)
        return self._call_ollama(model, prompt, temperature, num_ctx, num_predict, seed, timeout)

    def _call_ollama(
        self,
        model: str,
        prompt: str,
        temperature: float,
        num_ctx: int,
        num_predict: Optional[int],
        seed: Optional[int],
        timeout: int,
    ) -> LLMResponse:
        headers: Dict[str, str] = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        headers["Content-Type"] = "application/json"

        options: Dict[str, int | float] = {"temperature": temperature, "num_ctx": num_ctx}
        if num_predict is not None:
            options["num_predict"] = int(num_predict)
        if seed is not None:
            options["seed"] = int(seed)

        payload = _ollama_request(
            endpoint=self.endpoint,
            payload={"model": model, "prompt": prompt, "stream": False, "options": options},
            headers=headers,
            timeout=timeout,
            model=model,
        )
        text = payload.get("response", "")
        return LLMResponse(
            text=text,
            model=model,
            prompt=prompt,
            temperature=temperature,
            num_ctx=num_ctx,
            num_predict=num_predict,
            seed=seed,
        )

    def _call_ollama_chat(
        self,
        model: str,
        prompt: str,
        temperature: float,
        num_ctx: int,
        num_predict: Optional[int],
        seed: Optional[int],
        timeout: int,
    ) -> LLMResponse:
        headers: Dict[str, str] = {}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        headers["Content-Type"] = "application/json"

        options: Dict[str, int | float] = {"temperature": temperature, "num_ctx": num_ctx}
        if num_predict is not None:
            options["num_predict"] = int(num_predict)
        if seed is not None:
            options["seed"] = int(seed)

        payload = _ollama_request(
            endpoint=self.endpoint,
            payload={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": options,
            },
            headers=headers,
            timeout=timeout,
            model=model,
        )
        message = payload.get("message") or {}
        text = message.get("content", "")

        return LLMResponse(
            text=text,
            model=model,
            prompt=prompt,
            temperature=temperature,
            num_ctx=num_ctx,
            num_predict=num_predict,
            seed=seed,
        )

    def _call_openai(
        self,
        model: str,
        prompt: str,
        temperature: float,
        num_ctx: int,
        num_predict: Optional[int],
        seed: Optional[int],
        timeout: int,
    ) -> LLMResponse:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if num_predict is not None:
            payload["max_tokens"] = int(num_predict)
        if seed is not None:
            payload["seed"] = int(seed)

        response = requests.post(
            self.endpoint,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            text = ""
        else:
            choice = choices[0]
            message = choice.get("message") or {}
            text = message.get("content", "") or choice.get("text", "")

        return LLMResponse(
            text=text,
            model=model,
            prompt=prompt,
            temperature=temperature,
            num_ctx=num_ctx,
            num_predict=num_predict,
            seed=seed,
        )


__all__ = ["LLMClient", "LLMResponse"]
