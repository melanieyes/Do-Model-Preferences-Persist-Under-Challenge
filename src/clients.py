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

# override=True on purpose. CLAUDE.md puts the keys in .env, so .env is the source of
# truth and must win over anything already exported in the shell. Without it a stale
# placeholder in the environment silently shadows a correct key in .env and the failure
# surfaces as a 401 from the provider, which reads like a bad key rather than a bad
# precedence rule.
load_dotenv(override=True)

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

    # Set on providers that accept per-call reasoning control. Verified by probe, not
    # assumed: on deepseek-v4-pro `reasoning_effort="none"` removes reasoning tokens
    # entirely, while `enable_thinking=False` is silently ignored.
    supports_reasoning_control: bool = False

    def chat(self, messages: Messages, temperature: float = 1.0, logprobs: bool = False,
             reasoning: bool = True) -> Reply:
        raise NotImplementedError


class _OpenAICompatClient(ChatClient):
    """Shared implementation for any OpenAI-compatible /chat/completions endpoint."""

    def __init__(self, model: str, base_url: str, api_key: str, name: str, timeout: int = 120):
        from openai import OpenAI  # imported lazily so the module loads without the dep

        self.model = model
        self.name = name
        self.timeout = timeout
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)

    def chat(self, messages: Messages, temperature: float = 1.0, logprobs: bool = False,
             reasoning: bool = True) -> Reply:
        kwargs: dict[str, Any] = {"model": self.model, "messages": messages, "temperature": temperature}
        if logprobs:
            kwargs["logprobs"] = True
            kwargs["top_logprobs"] = 5
        if not reasoning and self.supports_reasoning_control:
            kwargs["reasoning_effort"] = "none"
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

    supports_reasoning_control = True

    def __init__(self, model: str = "deepseek-chat", base_url: str = "https://api.deepseek.com"):
        super().__init__(model, base_url, _require("DEEPSEEK_API_KEY"), name="deepseek")


class OpenAIClient(_OpenAICompatClient):
    """OpenAI chat models, used only where a NON-REASONING model is required.

    `supports_reasoning_control` is False deliberately. The OpenAI models that expose
    a reasoning control are reasoning models, and the roster requires a model that
    spends no reasoning tokens at all -- verified by effect from
    `usage.completion_tokens_details.reasoning_tokens`, not from the model name.
    Leaving the flag False keeps the persistence runner's control-1 assertion honest:
    it will refuse to start on this client rather than pretend reasoning was asserted.
    """

    supports_reasoning_control = False

    def __init__(self, model: str = "gpt-5.4-nano", base_url: str | None = None):
        super().__init__(model, base_url or "https://api.openai.com/v1",
                         _require("OPENAI_API_KEY").strip(), name="openai")


# ARCHIVED: pressure study only (docs/archive/prereg-v1/). The Modal app that served
# this endpoint was deleted with that study's code, so the endpoint is undeployable;
# nothing in the persistence pipeline uses this class. Kept, not removed.
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

    def chat(self, messages: Messages, temperature: float = 1.0, logprobs: bool = False,
             reasoning: bool = True) -> Reply:
        return super().chat(self.fold_system(messages), temperature, logprobs, reasoning)


class GeminiClient(ChatClient):
    """Gemini over REST. No logprobs on this API, so scoring is the discrete choice.

    Per-call reasoning is controlled by `thinkingConfig.thinkingBudget`: -1 lets the
    model think, 0 suppresses it. This is the same control
    `scripts/run_gemini_replication.py` validated BY EFFECT, reading
    `usageMetadata.thoughtsTokenCount` back rather than trusting that the parameter
    was honoured. Some models reject a budget of 0 while spending no thought tokens
    anyway; for those the config is omitted instead (OFF_BY_DEFAULT).
    """

    ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    # thinkingBudget is a genuine per-call reasoning control, so the persistence
    # runner's control-1 assertion can be satisfied on this client.
    supports_reasoning_control = True

    # Reject `thinkingBudget: 0` but spend no thought tokens by default.
    OFF_BY_DEFAULT = {"gemini-3.5-flash-lite"}

    def __init__(self, model: str = "gemini-2.0-flash", timeout: int = 120):
        self.model = model
        self.name = "gemini"
        self.timeout = timeout
        self._key = _require("GEMINI_API_KEY")

    def _think_cfg(self, reasoning: bool) -> dict[str, Any]:
        if reasoning:
            return {"thinkingConfig": {"thinkingBudget": -1}}
        if self.model in self.OFF_BY_DEFAULT:
            return {}
        return {"thinkingConfig": {"thinkingBudget": 0}}

    def chat(self, messages: Messages, temperature: float = 1.0, logprobs: bool = False,
             reasoning: bool = True) -> Reply:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        contents = [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in messages
            if m["role"] != "system"
        ]
        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {"temperature": temperature, **self._think_cfg(reasoning)},
        }
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
    "openai": OpenAIClient,
    "gemma": GemmaModalClient,
}


def get_client(name: str, **kwargs: Any) -> ChatClient:
    """get_client("deepseek", model="deepseek-chat") -> DeepSeekClient"""
    if name not in REGISTRY:
        raise KeyError(f"unknown client {name!r}; have {sorted(REGISTRY)}")
    return REGISTRY[name](**kwargs)
