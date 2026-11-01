"""One LLM client with an ordered provider chain (Groq -> NVIDIA -> local Ollama)."""
import json
import re
import time
from typing import Any, Callable, List, Optional, Tuple

import requests

from .config import Settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class LLMError(RuntimeError):
    pass


class _Hard(Exception):
    """Endpoint is unusable for this session (bad key, quota gone).
    provider_wide=True means every key of the provider is affected (e.g. model removed)."""

    def __init__(self, msg, provider_wide=False, cooldown=3600):
        super().__init__(msg)
        self.provider_wide = provider_wide
        self.cooldown = cooldown


def strip_think(text: str) -> str:
    text = THINK_RE.sub("", text or "")
    return re.sub(r"^.*?</think>", "", text, flags=re.DOTALL).strip()  # unmatched closing tag


def extract_json(text: str) -> Any:
    """Pull the first JSON object/array out of an LLM reply (tolerates fences and chatter)."""
    text = strip_think(text).replace("```json", "```")
    text = re.sub(r"```", "", text)
    pairs = sorted((("{", "}"), ("[", "]")), key=lambda p: text.find(p[0]) if p[0] in text else len(text))
    for opener, closer in pairs:          # whichever bracket opens first is the outer value
        start = text.find(opener)
        # try the longest balanced candidate, then progressively shorter ones
        end = text.rfind(closer)
        while start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                end = text.rfind(closer, start, end)
    raise ValueError("no JSON found in LLM reply")


class LLMClient:
    def __init__(self, settings: Settings, log: Callable[[str], None] = print):
        self.s = settings
        self.log = log
        self._cooldown = {}          # endpoint name -> time when usable again
        self._ollama_model: Optional[str] = None
        self.last_endpoint = ""

    # ---- public API -------------------------------------------------------
    def complete(self, prompt: str, system: str = "", max_tokens: Optional[int] = None,
                 temperature: float = 0.7) -> str:
        max_tokens = max_tokens or self.s.max_tokens
        errors = []
        for name, call in self._endpoints():
            if self._cooldown.get(name, 0) > time.time():
                continue
            for attempt in range(3):
                try:
                    # a truncated reply is retried with a bigger budget (reasoning models burn tokens silently)
                    text = strip_think(call(system, prompt, max_tokens * (attempt + 1), temperature))
                    if not text:
                        raise RuntimeError("empty response")
                    self.last_endpoint = name
                    return text
                except _Hard as exc:
                    errors.append(f"{name}: {exc}")
                    self.log(f"[llm] {name} disabled for this session: {exc}")
                    names = [n for n, _ in self._endpoints() if n.split("#")[0] == name.split("#")[0]] \
                        if exc.provider_wide else [name]
                    for n in names:
                        self._cooldown[n] = time.time() + exc.cooldown
                    break
                except Exception as exc:  # transient: back off, retry, then move on
                    msg = f"{name}: {type(exc).__name__}: {str(exc)[:160]}"
                    self.log(f"[llm] {msg} (attempt {attempt + 1}/3)")
                    if attempt == 2:
                        errors.append(msg)
                        self._cooldown[name] = time.time() + 300   # skip a flaky provider for a while
                    else:
                        time.sleep(2 ** (attempt + 1))
        raise LLMError("all LLM endpoints failed -> " + " | ".join(errors[-6:]))

    def complete_json(self, prompt: str, system: str = "", max_tokens: Optional[int] = None,
                      temperature: float = 0.3, tries: int = 2) -> Any:
        last = None
        for _ in range(tries):
            reply = self.complete(prompt + "\n\nReply with valid JSON only, no commentary.",
                                  system, max_tokens, temperature)
            try:
                return extract_json(reply)
            except ValueError as exc:
                last = exc
        raise LLMError(f"model did not return valid JSON: {last}")

    # ---- provider plumbing ------------------------------------------------
    def _endpoints(self) -> List[Tuple[str, Callable]]:
        out = []
        for provider in self.s.providers:
            if provider == "groq":
                for i, key in enumerate(self.s.groq_keys):
                    out.append((f"groq#{i + 1}", self._openai_compat(GROQ_URL, key, self.s.groq_model, 120, headroom=1500,
                        extra={"reasoning_effort": "low"} if "gpt-oss" in self.s.groq_model else None)))
            elif provider == "nvidia":
                for model in self.s.nvidia_models:       # fast model first, on every key, then the slow one
                    # Mistral Large 4 only answers reliably with reasoning_effort=high (~100 s per call)
                    slow = "mistral-large-4" in model
                    for i, key in enumerate(self.s.nvidia_keys):
                        # "#" separates the key index: a 404 disables just this model across keys
                        out.append((f"nvidia:{model.split('/')[-1]}#{i + 1}", self._openai_compat(
                            NVIDIA_URL, key, model, 240 if slow else 90, headroom=3000,
                            extra={"reasoning_effort": "high"} if slow else None)))
            elif provider == "ollama":
                out.append(("ollama", self._ollama))
        return out

    def _openai_compat(self, url, key, model, timeout, headroom=0, extra=None):
        extra = extra or {}
        # headroom: extra tokens for models that spend hidden "reasoning" tokens inside max_tokens
        def call(system, prompt, max_tokens, temperature):
            messages = ([{"role": "system", "content": system}] if system else []) + \
                       [{"role": "user", "content": prompt}]
            try:
                r = requests.post(url, timeout=timeout,
                                  headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                                  json={"model": model, "messages": messages,
                                        "temperature": temperature, "max_tokens": max_tokens + headroom, **extra})
            except requests.Timeout:         # too slow right now: skip this endpoint for a while, don't retry
                raise _Hard(f"timed out after {timeout}s", cooldown=300)
            if r.status_code == 404:       # model removed / not served: same for every key
                raise _Hard(f"HTTP 404 model '{model}' unavailable: {r.text[:100]}", provider_wide=True)
            if r.status_code == 429:        # rate limited: park this key briefly and try the next one
                raise _Hard(f"HTTP 429 rate limited: {r.text[:90]}", cooldown=90)
            if r.status_code in (401, 402, 403) or "free-models-per-day" in r.text:
                raise _Hard(f"HTTP {r.status_code}")
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
            choice = r.json()["choices"][0]
            if choice.get("finish_reason") == "length":
                raise RuntimeError("truncated (max_tokens too small)")
            return choice["message"].get("content") or ""
        return call

    def _resolve_ollama_model(self) -> str:
        if self._ollama_model:
            return self._ollama_model
        r = requests.get(f"{self.s.ollama_url}/api/tags", timeout=5)
        r.raise_for_status()
        names = [m["name"] for m in r.json().get("models", [])]
        chat = [n for n in names if not re.search(r"embed|bge|minilm", n, re.I)]
        wanted = self.s.ollama_model
        if wanted in names or f"{wanted}:latest" in names:
            self._ollama_model = wanted
        elif chat:
            self._ollama_model = chat[0]
            self.log(f"[llm] Ollama model '{wanted}' not installed, using '{chat[0]}'")
        else:
            raise _Hard("no Ollama chat model installed")
        return self._ollama_model

    def _ollama(self, system, prompt, max_tokens, temperature):
        try:
            model = self._resolve_ollama_model()
        except requests.ConnectionError:
            raise _Hard("Ollama not running")
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        r = requests.post(f"{self.s.ollama_url}/api/chat", timeout=1200, json={
            "model": model, "messages": messages, "stream": False, "think": False,
            "options": {"temperature": temperature, "num_predict": max_tokens, "num_ctx": self.s.ollama_ctx}})
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
        data = r.json()
        if data.get("done_reason") == "length":
            raise RuntimeError("truncated (max_tokens too small)")
        return data.get("message", {}).get("content", "")
