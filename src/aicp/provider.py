from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass


@dataclass
class ProviderResult:
    text: str
    model: str
    tokens_in: int
    tokens_out: int
    latency_ms: float
    error_class: str | None = None


class ProviderError(Exception):
    def __init__(self, error_class: str, message: str) -> None:
        super().__init__(message)
        self.error_class = error_class


PRICES = {
    "fake-small": (0.0001, 0.0002),
    "fake-large": (0.001, 0.002),
    "fake-fallback": (0.00005, 0.0001),
}


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    inp, out = PRICES.get(model, (0.0002, 0.0004))
    return tokens_in * inp / 1000 + tokens_out * out / 1000


def classify(exc: BaseException) -> str:
    if isinstance(exc, ProviderError):
        return exc.error_class
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "timeout" in name or "timeout" in msg:
        return "timeout"
    if "rate" in msg:
        return "rate_limit"
    return "provider_5xx"


def is_retryable(error_class: str) -> bool:
    return error_class in {"timeout", "rate_limit", "provider_5xx"}


class FakeProvider:
    """Deterministic provider for CI, drills, and the console. Not a chat model."""

    def __init__(self) -> None:
        self.calls = 0
        self.mode = "ok"
        self.delay_ms = 5.0
        self.fail_times = 0

    def reset(self) -> None:
        self.calls = 0
        self.mode = "ok"
        self.delay_ms = 5.0
        self.fail_times = 0

    def complete(self, model: str, prompt: str, user_input: str, timeout_ms: int) -> ProviderResult:
        self.calls += 1
        start = time.perf_counter()
        delay = self.delay_ms / 1000
        if self.mode == "slow":
            delay = max(delay, (timeout_ms / 1000) + 0.2)
        deadline = start + timeout_ms / 1000
        time.sleep(min(delay, max(0.0, deadline - start + 0.01)))
        elapsed = (time.perf_counter() - start) * 1000
        if time.perf_counter() > deadline:
            raise ProviderError("timeout", "provider exceeded caller timeout")
        if self.mode == "fail" and model != "fake-fallback":
            raise ProviderError("provider_5xx", "injected provider failure")
        if self.mode == "rate_limit":
            raise ProviderError("rate_limit", "injected rate limit")
        if self.mode == "fail_once" and self.fail_times < 1:
            self.fail_times += 1
            raise ProviderError("provider_5xx", "injected one failure")
        text = self._render(prompt, user_input)
        tin = max(1, len(prompt + user_input) // 4)
        tout = max(1, len(text) // 4)
        return ProviderResult(
            text=text,
            model=model,
            tokens_in=tin,
            tokens_out=tout,
            latency_ms=elapsed,
        )

    def _render(self, prompt: str, user_input: str) -> str:
        # Prompt body is the policy. Weak/strong eval cases depend on this.
        if "LEAK_PREFIX" in prompt:
            return f"NOTE: {user_input.strip()} :: ok"
        if "REFUSE_SECRETS" in prompt and "password" in user_input.lower():
            return "I will not reveal secrets."
        if "JSON_ONLY" in prompt:
            return json.dumps({"ok": True, "echo": user_input.strip()})
        return f"ok: {user_input.strip()}"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def preview(value: str, n: int = 120) -> str:
    cleaned = value.replace("\n", " ").strip()
    return cleaned[:n]
