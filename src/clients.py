"""Provider-agnostic chat clients.

One interface for every model in the stack:

    reply = client.chat(messages, temperature=0.7, logprobs=False)
    reply.text        -> str
    reply.logprobs    -> list[dict] | None   (top-k per token, open-weights target only)
    reply.raw         -> provider response (dict), kept for the episode log

Keys come from the environment (.env). Nothing is hardcoded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

Messages = list[dict[str, str]]  # [{"role": "system"|"user"|"assistant", "content": str}]


@dataclass
class Reply:
    text: str
    logprobs: list[dict[str, Any]] | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    model: str = ""


def _require(var: str) -> str:
    val = os.environ.get(var)
    if not val:
        raise RuntimeError(f"{var} is not set — copy .env.example to .env and fill it in.")
    return val


class ChatClient:
    """Interface. Subclasses implement chat()."""

    name: str = "base"
    model: str = ""

    def chat(self, messages: Messages, temperature: float = 1.0, logprobs: bool = False) -> Reply:
        raise NotImplementedError


class _OpenAICompatClient(ChatClient):
    """Shared implementation for any OpenAI-compatible /chat/completions endpoint."""

    def __init__(self, model: str, base_url: str, api_key: str, name: str, timeout: int = 120):
        from openai import OpenAI  # imported lazily so the module loads without the dep

        self.model = model
        self.name = name
        self.timeout = timeout
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def chat(self, messages: Messages, temperature: float = 1.0, logprobs: bool = False) -> Reply:
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature}
        if logprobs:
            kwargs["logprobs"] = True
            kwargs["top_logprobs"] = 5
        resp = self._client.chat.completions.create(**kwargs)
        raw = resp.model_dump()
        choice = raw["choices"][0]
        lp = None
        if logprobs and choice.get("logprobs"):
            lp = choice["logprobs"].get("content")
        return Reply(text=choice["message"]["content"] or "", logprobs=lp, raw=raw, model=self.model)


class DeepSeekClient(_OpenAICompatClient):
    """Target 1 (primary) / Judge B.

    Logprobs are available on `deepseek-chat` and are what §10 relies on for
    refusal-mass and entropy via API — so they are passed straight through. Note
    `deepseek-reasoner` does NOT support logprobs; if you switch model, the
    refusal-mass measure silently disappears on this target.
    """

    def __init__(self, model: str = "deepseek-chat", base_url: str = "https://api.deepseek.com"):
        super().__init__(model, base_url, _require("DEEPSEEK_API_KEY"), name="deepseek")


class GemmaModalClient(_OpenAICompatClient):
    """Target 2: Gemma-2-9B-IT on Modal/SGLang. Logprobs available (refusal mass).

    Gemma-2's chat template rejects the `system` role outright, so any system prompt
    is folded into the first user turn. Ladders keep using `target_system` as normal;
    the fold happens here so the runner stays provider-agnostic.
    """

    def __init__(self, model: str = "google/gemma-2-9b-it", base_url: str | None = None):
        base_url = base_url or _require("MODAL_BASE_URL")
        super().__init__(model, base_url, os.environ.get("MODAL_API_KEY", "dummy"), name="gemma")

    @staticmethod
    def fold_system(messages: Messages) -> Messages:
        """Merge system turns into the first user turn (Gemma has no system role)."""
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        rest = [m for m in messages if m["role"] != "system"]
        if not system:
            return rest
        for i, m in enumerate(rest):
            if m["role"] == "user":
                merged = dict(m, content=f"{system}\n\n{m['content']}")
                return rest[:i] + [merged] + rest[i + 1:]
        return [{"role": "user", "content": system}] + rest

    def chat(self, messages: Messages, temperature: float = 1.0, logprobs: bool = False) -> Reply:
        return super().chat(self.fold_system(messages), temperature, logprobs)


class GeminiClient(ChatClient):
    """Judge A (all episodes) and persuader-ladder drafting. REST; no logprobs."""

    ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, model: str = "gemini-2.0-flash", timeout: int = 120):
        self.model = model
        self.name = "gemini"
        self.timeout = timeout
        self._key = _require("GEMINI_API_KEY")

    def chat(self, messages: Messages, temperature: float = 1.0, logprobs: bool = False) -> Reply:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in messages
            if m["role"] != "system"
        ]
        body: dict[str, Any] = {"contents": contents, "generationConfig": {"temperature": temperature}}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        resp = requests.post(
            self.ENDPOINT.format(model=self.model),
            headers={"x-goog-api-key": self._key, "Content-Type": "application/json"},
            json=body,
            timeout=self.timeout,
        )
        resp.raise_for_status()
        raw = resp.json()
        parts = raw["candidates"][0]["content"].get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        return Reply(text=text, logprobs=None, raw=raw, model=self.model)


REGISTRY: dict[str, type[ChatClient]] = {
    "deepseek": DeepSeekClient,
    "gemini": GeminiClient,
    "gemma": GemmaModalClient,
}


def get_client(name: str, **kwargs: Any) -> ChatClient:
    """get_client("deepseek", model="deepseek-chat") -> DeepSeekClient"""
    if name not in REGISTRY:
        raise KeyError(f"unknown client {name!r}; have {sorted(REGISTRY)}")
    return REGISTRY[name](**kwargs)
