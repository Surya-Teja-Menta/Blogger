"""One LLM client with an ordered provider chain (Groq -> Cerebras -> Gemini -> OpenRouter -> GitHub Models ->
NVIDIA -> local Ollama); providers without keys are skipped."""
import json
import re
import time
from typing import Any, Callable, List, Optional, Tuple

import requests

from .config import Settings

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
# more OpenAI-compatible providers: name -> (url, timeout s, reasoning headroom tokens, output-token cap or None).
# Keys and model come from Settings.<name>_keys / <name>_model.
OPENAI_COMPAT = {
    "cerebras": ("https://api.cerebras.ai/v1/chat/completions", 120, 1500, None),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", 180, 3000, None),
    "openrouter": ("https://openrouter.ai/api/v1/chat/completions", 180, 1500, None),
    "github": ("https://models.github.ai/inference/chat/completions", 120, 0, 4000),   # free tier: 4k out per call
}

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


class _TooBig(Exception):
    """This request is larger than the provider accepts at all (HTTP 413, or a request over its per-minute token
    allowance): no key of that provider can serve it, so the request goes to the next provider at once. The
    provider stays available for smaller requests."""


MAX_WAIT = 120      # longest pause (seconds) worth waiting out when every endpoint is rate-limited
MAX_WAITS = 8       # how many such pauses one request may take
RETRY_IN = re.compile(r"try again in\s+(?:(\d+)h)?\s*(?:(\d+)m(?!s))?\s*(?:([\d.]+)(m?s))?", re.I)


def retry_after(body: str) -> float:
    """Seconds until a rate limit lifts, read from the provider's own message ('try again in 1m3.2s'). A daily
    quota returns a long wait, which is then not waited out. Unknown format: assume a per-minute limit."""
    m = RETRY_IN.search(body or "")
    if not m or not any(m.groups()[:3]):
        return 60.0
    h, mins, secs, unit = m.groups()
    s = float(secs or 0) / (1000 if unit and unit.lower() == "ms" else 1)
    return min(3600.0, int(h or 0) * 3600 + int(mins or 0) * 60 + s + 1)


LIMIT_RE = re.compile(r"on (tokens|requests) per (minute|day) \((\w+)\): Limit (\d+), Used (\d+), Requested (\d+)", re.I)


def limit_detail(body: str) -> str:
    """The useful part of a 429: which limit was hit and by how much ('TPM: used 7100 + requested 1900 of 8000').
    The organisation id is left out of logs on purpose."""
    m = LIMIT_RE.search(body or "")
    if not m:
        return (body or "")[:120]
    _, _, kind, limit, used, req = m.groups()
    return f"{kind}: used {used} + requested {req} of {limit}"


def _over_limit(body: str) -> bool:
    """A 429 whose request alone is over the limit ('Limit 8000, Used 0, Requested 9200'): waiting cannot help."""
    m = LIMIT_RE.search(body or "")
    return bool(m) and int(m.group(6)) > int(m.group(4))


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
        self._turn = 0               # rotates which Groq key is tried first, spreading the per-minute load
        self._ollama_model: Optional[str] = None
        self.last_endpoint = ""
        self._tokens = 0             # tokens of the last successful call, as the provider reported them
        self.usage = {}              # provider -> {"calls", "tokens"}: what a run really costs

    # ---- public API -------------------------------------------------------
    def complete(self, prompt: str, system: str = "", max_tokens: Optional[int] = None,
                 temperature: float = 0.7) -> str:
        max_tokens = max_tokens or self.s.max_tokens
        errors = []
        too_big = set()              # providers this request is too large for
        self._turn += 1
        for waits in range(MAX_WAITS + 1):
            for name, call in self._rotated(self._endpoints()):
                if self._cooldown.get(name, 0) > time.time() or name.split("#")[0] in too_big:
                    continue
                for attempt in range(3):
                    try:
                        self._tokens = 0
                        # a truncated reply is retried with a bigger budget (reasoning models burn tokens silently)
                        text = strip_think(call(system, prompt, max_tokens * (attempt + 1), temperature))
                        if not text:
                            raise RuntimeError("empty response")
                        self.last_endpoint = name
                        used = self.usage.setdefault(name.split("#")[0].split(":")[0], {"calls": 0, "tokens": 0})
                        used["calls"] += 1
                        used["tokens"] += self._tokens
                        return text
                    except _Hard as exc:
                        errors.append(f"{name}: {exc}")
                        self.log(f"[llm] {name} paused for {exc.cooldown:.0f}s: {exc}")
                        names = [n for n, _ in self._endpoints() if n.split("#")[0] == name.split("#")[0]] \
                            if exc.provider_wide else [name]
                        for n in names:
                            self._cooldown[n] = time.time() + exc.cooldown
                        break
                    except _TooBig as exc:   # no key of this provider can take it: straight to the next provider
                        provider = name.split("#")[0]
                        too_big.add(provider)
                        errors.append(f"{provider}: {exc}")
                        self.log(f"[llm] {provider}: request too large for it, trying the next provider")
                        break
                    except Exception as exc:  # transient: back off, retry, then move on
                        msg = f"{name}: {type(exc).__name__}: {str(exc)[:160]}"
                        self.log(f"[llm] {msg} (attempt {attempt + 1}/3)")
                        if attempt == 2:
                            errors.append(msg)
                            self._cooldown[name] = time.time() + 300   # skip a flaky provider for a while
                        else:
                            time.sleep(2 ** (attempt + 1))
            # Every endpoint failed or is parked. Per-minute rate limits clear within seconds, so wait for the
            # soonest one instead of losing the whole run; longer outages (bad key, daily quota) still fail.
            ready_in = min((t - time.time() for t in self._cooldown.values() if t > time.time()), default=None)
            if ready_in is None or ready_in > MAX_WAIT or waits == MAX_WAITS:
                break
            self.log(f"[llm] every endpoint is rate-limited; waiting {ready_in + 1:.0f}s")
            time.sleep(ready_in + 1)
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
    def _rotated(self, endpoints: List[Tuple[str, Callable]]) -> List[Tuple[str, Callable]]:
        """Each request starts at the next key of every provider (and model), so the per-minute load is spread
        across all keys instead of always exhausting key #1 first. Provider order is kept."""
        groups = {}
        for i, (n, _) in enumerate(endpoints):
            if "#" in n:
                groups.setdefault(n.split("#")[0], []).append(i)
        out = list(endpoints)
        for idx in groups.values():
            if len(idx) < 2:
                continue
            k = self._turn % len(idx)
            same = [endpoints[i] for i in idx]
            for i, ep in zip(idx, same[k:] + same[:k]):
                out[i] = ep
        return out

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
            elif provider in OPENAI_COMPAT:
                url, timeout, headroom, cap = OPENAI_COMPAT[provider]
                model = getattr(self.s, f"{provider}_model")
                # keep the hidden reasoning short on models that think by default
                low = "gpt-oss" in model or (provider == "gemini" and re.search(r"2\.5|-3|latest", model))
                for i, key in enumerate(getattr(self.s, f"{provider}_keys")):
                    out.append((f"{provider}#{i + 1}", self._openai_compat(
                        url, key, model, timeout, headroom=headroom, cap=cap,
                        extra={"reasoning_effort": "low"} if low else None)))
            elif provider == "ollama":
                out.append(("ollama", self._ollama))
        return out

    def _openai_compat(self, url, key, model, timeout, headroom=0, extra=None, cap=None):
        extra = extra or {}
        # headroom: extra tokens for models that spend hidden "reasoning" tokens inside max_tokens
        # cap: the provider's own ceiling on output tokens per call
        def call(system, prompt, max_tokens, temperature):
            budget = min(max_tokens + headroom, cap) if cap else max_tokens + headroom
            messages = ([{"role": "system", "content": system}] if system else []) + \
                       [{"role": "user", "content": prompt}]
            try:
                r = requests.post(url, timeout=timeout,
                                  headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                                  json={"model": model, "messages": messages,
                                        "temperature": temperature, "max_tokens": budget, **extra})
            except requests.Timeout:         # too slow right now: skip this endpoint for a while, don't retry
                raise _Hard(f"timed out after {timeout}s", cooldown=300)
            if r.status_code == 404:       # model removed / not served: same for every key
                raise _Hard(f"HTTP 404 model '{model}' unavailable: {r.text[:100]}", provider_wide=True)
            if r.status_code == 413 or (r.status_code == 429 and "requested" in r.text.lower() and
                                        _over_limit(r.text)):
                raise _TooBig(f"HTTP {r.status_code} request too large: {limit_detail(r.text)}")
            if r.status_code == 429:        # rate limited: park this key until the limit resets, try the next one
                raise _Hard(f"HTTP 429 rate limited: {limit_detail(r.text)}", cooldown=retry_after(r.text))
            if r.status_code in (401, 402, 403) or "free-models-per-day" in r.text:
                raise _Hard(f"HTTP {r.status_code}")
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
            data = r.json()
            self._tokens = (data.get("usage") or {}).get("total_tokens") or 0
            choice = data["choices"][0]
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
        self._tokens = (data.get("prompt_eval_count") or 0) + (data.get("eval_count") or 0)
        if data.get("done_reason") == "length":
            raise RuntimeError("truncated (max_tokens too small)")
        return data.get("message", {}).get("content", "")
