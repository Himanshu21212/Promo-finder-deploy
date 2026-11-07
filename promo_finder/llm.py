"""Optional AI judge. One string picks the model:

    rules                          no AI, pure rules (default, free, offline)
    sarvam:sarvam-105b              Sarvam credits                (SARVAM_API_KEY)
    gemini:gemini-3.8-flash        Google AI Studio, free tier   (GEMINI_API_KEY)
    gemini:gemini-3.5-flash-lite   cheaper / faster Gemini       (GEMINI_API_KEY)
    groq:openai/gpt-oss-120b       Groq, free tier               (GROQ_API_KEY)
    openai:<model>                 OpenAI                        (OPENAI_API_KEY)
    anthropic:<model>              Anthropic                     (ANTHROPIC_API_KEY)
    openrouter:<model>             OpenRouter                    (OPENROUTER_API_KEY)
    ollama:llama3.1                local Ollama, no key
    custom:<model>                 any OpenAI-compatible URL      (LLM_BASE_URL, LLM_API_KEY)
    mock                           fake judge for tests only, never a real model

What the model is allowed to do:
  * rate a shortlisted cut 1-10 on hook, cliffhanger, new-viewer clarity and overall
  * point at beat NUMBERS (which line hooks, which line it cuts on, an optional tighter start/end)
  * write one 'why' line and one 'risk' line
What it is NOT allowed to do: write a timestamp or a quote. Code looks every time and line up in
the script, and a suggested trim is applied only if it still passes every hard rule.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path

import requests

from .candidates import HOOK_WINDOW, MAX_LEN, MIN_LEN, Promo, Segment, _inside, _utterances
from .parser import Episode, fmt

OPENAI_COMPAT = {
    "sarvam": ("https://api.sarvam.ai/v1", "SARVAM_API_KEY", "sarvam-105b"),
    "openai": ("https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4o-mini"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "openai/gpt-oss-120b"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "meta-llama/llama-3.3-70b-instruct"),
    "ollama": ("http://localhost:11434/v1", "", "llama3.1"),
    "custom": ("", "LLM_API_KEY", "default"),
}
KEY_ENV = {"gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY", **{k: v[1] for k, v in OPENAI_COMPAT.items()}}
DEFAULTS = {"gemini": "gemini-3.8-flash", "anthropic": "claude-sonnet-4-5", "mock": "mock"}
# Conservative pacing for short candidate prompts; account token limits still apply.
PACING = {"sarvam": 1.0, "gemini": 4.0, "groq": 30.0}
JSON_MODE = {"sarvam", "openai", "groq", "openrouter"}

SYSTEM = """You are a promo editor for vertical microdrama apps (ReelShort / DramaBox style).
You judge 20-60 second clips cut from a show to run as ads on TikTok, Reels and Shorts.
A good promo: (1) the first 3 seconds stop a scrolling viewer, (2) it ends on an unresolved
moment so the viewer must tap to find out, (3) someone who has never seen the show can follow it.
Be strict and specific. Use only what is in the transcript. Reply with one JSON object only."""

PROMPT = """SHOW: {title}
PREMISE (from the first episode): {premise}

CANDIDATE PROMO: {dur:.0f} s, {nseg} segment(s). Beats are numbered; times are seconds from the start of the promo.
{transcript}

WHAT HAPPENS RIGHT AFTER THE LAST CUT (the viewer does NOT see this; use it only to judge whether the ending is unresolved):
{after}

Score each 1-10 using these anchors:
  hook:        10 = a slap, a reveal or a shocking line inside 3 s;  5 = mildly interesting;  1 = nothing happens
  cliffhanger: 10 = cuts right before the answer / the blow / the reveal;  5 = tension but partly resolved;  1 = ends on a resolved or calm moment
  standalone:  10 = a stranger understands who wants what;  5 = some names or objects need context;  1 = confusing without earlier episodes
  overall:     how likely this clip makes a new viewer tap through

Return exactly these keys:
{{"hook": <1-10>, "cliffhanger": <1-10>, "standalone": <1-10>, "overall": <1-10>,
  "hook_beat": <beat number that hooks in the first 3 s>,
  "cliff_beat": <beat number of the unresolved final moment>,
  "trim_start_beat": <beat number to start on, or null>,
  "trim_end_beat": <beat number to end on, or null>,
  "why": "<max 25 words: why it works as an ad>",
  "risk": "<max 12 words: what could confuse or bore a new viewer, or empty>"}}"""


class JudgeError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, *, kind: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.kind = kind


class Judge:
    def __init__(self, spec: str = "rules", api_key: str | None = None, base_url: str | None = None,
                 use_cache: bool = True, cache_dir: str | Path | None = None, min_interval: float | None = None,
                 transport=None):
        """api_key / base_url are passed in directly (never written to os.environ), so a hosted app
        can't leak one user's key to another session. `transport` replaces the HTTP call in tests."""
        self.spec = spec or "rules"
        prov, _, model = self.spec.partition(":")
        self.provider = prov.lower().strip()
        if self.provider not in OPENAI_COMPAT and self.provider not in ("gemini", "anthropic", "mock", "rules"):
            raise ValueError(f"Unknown model provider '{prov}'. Options: rules, sarvam, gemini, groq, openai, anthropic, "
                             f"openrouter, ollama, custom, mock")
        self.model = model or (OPENAI_COMPAT[self.provider][2] if self.provider in OPENAI_COMPAT
                               else DEFAULTS.get(self.provider, ""))
        env = KEY_ENV.get(self.provider, "")
        self.api_key = api_key or (os.getenv(env) if env else None)
        self.base_url = base_url or (os.getenv("LLM_BASE_URL", "") if self.provider == "custom" else
                                     OPENAI_COMPAT.get(self.provider, ("",))[0])
        if self.provider == "sarvam" and self.model == "sarvam-105b-conversations" and not base_url:
            self.base_url = "https://api.sarvam.ai/v1"
        self.use_cache = use_cache
        self.cache_dir = Path(cache_dir or os.getenv("PROMO_CACHE", ".llm_cache"))
        env_gap = os.getenv("PROMO_LLM_MIN_INTERVAL")
        self.min_interval = float(env_gap) if env_gap else (min_interval if min_interval is not None
                                                            else PACING.get(self.provider, 0.0))
        self.transport = transport
        self.stats = {"calls": 0, "cached": 0, "failed": 0, "trims_applied": 0, "trims_rejected": 0}
        self.stats.update(usage_calls=0, prompt_tokens=0, completion_tokens=0, cached_tokens=0, reasoning_tokens=0)
        self._last_call = 0.0
        self._consecutive_fail = 0
        self.tripped = ""

    @property
    def active(self) -> bool:
        return self.provider != "rules"

    @property
    def is_mock(self) -> bool:
        return self.provider == "mock"

    def ready(self) -> tuple[bool, str]:
        """Can we call the model at all? Checked once before the run instead of failing 50 times."""
        if not self.active or self.is_mock or self.transport:
            return True, ""
        env = KEY_ENV.get(self.provider, "")
        if env and not self.api_key and self.provider != "ollama":
            return False, f"no {env} set"
        if self.provider == "custom" and not self.base_url:
            return False, "no LLM_BASE_URL set"
        return True, ""

    # ------------------------------------------------------------ transport
    def _call(self, prompt: str) -> str:
        key = hashlib.sha1(f"{self.spec}|{SYSTEM}|{prompt}".encode()).hexdigest()
        cf = self.cache_dir / f"{key}.txt"
        if self.use_cache and cf.exists():
            self.stats["cached"] += 1
            return cf.read_text()
        last_err: Exception | None = None
        for attempt in range(2):
            wait = self.min_interval - (time.time() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.time()
            try:
                self.stats["calls"] += 1
                out = self.transport(prompt) if self.transport else self._raw(prompt)
                if self.use_cache:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    cf.write_text(out)
                return out
            except requests.HTTPError as e:
                code = e.response.status_code if e.response is not None else 0
                detail = e.response.text if e.response is not None else ""
                if self.api_key:
                    detail = detail.replace(self.api_key, "[redacted]")
                last_err = JudgeError(f"HTTP {code}: {detail[:160]}", status_code=code)
                if code in (429, 500, 502, 503, 504) and attempt < 1:
                    retry_after = e.response.headers.get("Retry-After") if e.response is not None else None
                    delay = float(retry_after) if retry_after and retry_after.isdigit() else 3
                    if delay > 5:
                        raise last_err
                    time.sleep(delay)
                    continue
                raise last_err
            except requests.Timeout:
                raise JudgeError("API request timed out; review stopped without retry", kind="timeout")
            except requests.ConnectionError as e:
                last_err = JudgeError(f"network: {type(e).__name__}")
                if attempt < 1:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise last_err
        raise last_err or JudgeError("LLM call failed")

    def _raw(self, prompt: str) -> str:
        p, m = self.provider, self.model
        if p == "mock":
            return _mock(prompt)
        if p == "gemini":
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                headers={"x-goog-api-key": self.api_key or ""},
                json={"systemInstruction": {"parts": [{"text": SYSTEM}]},
                      "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                      "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}},
                timeout=(5, 20))
            r.raise_for_status()
            data = r.json()
            try:
                return "".join(part.get("text", "") for part in data["candidates"][0]["content"]["parts"])
            except (KeyError, IndexError):
                raise JudgeError(f"empty Gemini reply: {str(data)[:160]}")
        if p == "anthropic":
            r = requests.post("https://api.anthropic.com/v1/messages",
                              headers={"x-api-key": self.api_key or "", "anthropic-version": "2023-06-01"},
                              json={"model": m, "max_tokens": 600, "temperature": 0, "system": SYSTEM,
                                    "messages": [{"role": "user", "content": prompt}]}, timeout=(5, 20))
            r.raise_for_status()
            return "".join(c.get("text", "") for c in r.json().get("content", []))
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        body = {"model": m, "temperature": 0,
                "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}
        if p == "sarvam":
            body["max_tokens"] = 768  # a short rating object, not a long reasoning job
            if self.base_url.rstrip("/") == "https://api.sarvam.ai/v1":
                body["reasoning_effort"] = None  # documented V1 switch to disable thinking
        elif p == "groq" and m.startswith("openai/gpt-oss-"):
            body.update(max_completion_tokens=2048, reasoning_effort="low")
        if p in JSON_MODE:
            body["response_format"] = {"type": "json_object"}
        r = requests.post(f"{self.base_url.rstrip('/')}/chat/completions", headers=headers, json=body,
                          timeout=(5, 35 if p == "sarvam" else 20))
        r.raise_for_status()
        data = r.json()
        usage = data.get("usage") or {}
        if isinstance(usage, dict) and all(isinstance(usage.get(k), int) and not isinstance(usage[k], bool)
                                          and usage[k] >= 0 for k in ("prompt_tokens", "completion_tokens")):
            def count(value):
                return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0
            self.stats["usage_calls"] += 1
            for k in ("prompt_tokens", "completion_tokens"):
                self.stats[k] += count(usage.get(k))
            prompt_details = usage.get("prompt_tokens_details")
            completion_details = usage.get("completion_tokens_details")
            if isinstance(prompt_details, dict):
                self.stats["cached_tokens"] += min(count(prompt_details.get("cached_tokens")), usage["prompt_tokens"])
            if isinstance(completion_details, dict):
                self.stats["reasoning_tokens"] += min(count(completion_details.get("reasoning_tokens")), usage["completion_tokens"])
            if p == "sarvam" and m in ("sarvam-105b", "sarvam-105b-conversations"):
                # Published INR / 1M tokens: input 15, cached input 5, output 60; excludes tax.
                s = self.stats
                cached = min(s["cached_tokens"], s["prompt_tokens"])
                s["estimated_cost_inr"] = round(((s["prompt_tokens"] - cached) * 15 + cached * 5
                                                  + s["completion_tokens"] * 60) / 1_000_000, 6)
        try:
            choice = data["choices"][0]
            content = choice["message"].get("content")
        except (KeyError, IndexError, TypeError):
            raise JudgeError("API returned no assistant message")
        if choice.get("finish_reason") == "length":
            raise JudgeError("API reached its output-token limit; rating discarded")
        if not isinstance(content, str) or not content.strip():
            raise JudgeError("API returned no final answer (possibly a reasoning-only response); rating discarded")
        return content

    def _failed(self, p: Promo, error: Exception, prefix: str = "") -> Promo:
        self.stats["failed"] += 1
        self._consecutive_fail += 1
        detail = str(error)
        if self.api_key:
            detail = detail.replace(self.api_key, "[redacted]")
        p.llm = {"error": (prefix + detail)[:200]}
        if getattr(error, "status_code", None):
            self.stats["last_error_code"] = error.status_code
        if getattr(error, "kind", "") == "timeout":
            self.stats["error_kind"] = "timeout"
            self.tripped = "stopped because the AI service request timed out"
        elif getattr(error, "status_code", None) in (401, 402, 403, 404):
            self.tripped = f"stopped after HTTP {error.status_code}; check the key, credits, model and access"
        elif self._consecutive_fail >= 3:
            self.tripped = f"stopped after 3 failed calls in a row ({detail[:80]})"
        return p

    # ------------------------------------------------------------ judging
    def judge(self, p: Promo, title: str, premise: str, eps: dict[int, Episode], rescore=None) -> Promo:
        """Rate one candidate. On any failure the promo keeps its rules score and records the error."""
        if self.tripped:
            p.llm = {"error": f"skipped: {self.tripped}"}
            return p
        beats, lines, t0 = [], [], 0.0
        for si, s in enumerate(p.segments):
            if len(p.segments) > 1:
                lines.append(f"--- segment {si + 1}: Episode {s.ep} ---")
            for b in s.beats:
                if b.kind == "camera":
                    continue
                beats.append((b, t0 + b.start - s.start))
                lines.append(f"[{len(beats)}] {beats[-1][1]:5.1f}s  {b.short(160)}")
            t0 += s.dur
        last = p.segments[-1]
        after = [b for b in eps[last.ep].beats if b.start >= last.end - 0.05 and b.kind != "camera"][:3]
        prompt = PROMPT.format(title=title, premise=premise or "(not given)", dur=p.duration, nseg=len(p.segments),
                               transcript="\n".join(lines),
                               after="\n".join(f"- {b.short(140)}" for b in after) or "- (end of episode)")
        try:
            reply = self._call(prompt)
        except Exception as e:  # transport failure (bad key, network, provider down)
            return self._failed(p, e)
        try:
            data = _json(reply)
            res = {k: _score(data.get(k)) for k in ("hook", "cliffhanger", "standalone", "overall")}
            if any(v is None for v in res.values()):
                raise JudgeError(f"missing or non-numeric scores: {json.dumps(data)[:160]}")
        except Exception as e:  # malformed reply: keep the rules score for this one
            return self._failed(p, e, "bad reply: ")
        self._consecutive_fail = 0
        res["why"] = str(data.get("why") or "")[:220]
        res["risk"] = str(data.get("risk") or "")[:120]

        def pick(k):
            n = _int(data.get(k))
            return beats[n - 1][0] if n and 1 <= n <= len(beats) else None

        res["trim"] = _apply_trim(p, pick("trim_start_beat"), pick("trim_end_beat"), eps)
        if res["trim"].startswith("applied"):
            self.stats["trims_applied"] += 1
            if rescore:
                rescore(p)      # rules scores, hook and cliffhanger beats follow the new cut
        elif res["trim"].startswith("rejected"):
            self.stats["trims_rejected"] += 1
        in_cut = {id(b) for b in p.beats}
        hb, cb = pick("hook_beat"), pick("cliff_beat")
        if hb and id(hb) in in_cut and hb.start - p.segments[0].start <= HOOK_WINDOW and hb.ep == p.segments[0].ep:
            p.hook_beat = hb
        if cb and id(cb) in in_cut and cb.ep == p.segments[-1].ep:
            p.cliff_beat = cb
        p.llm = res
        llm_total = (0.3 * res["hook"] + 0.25 * res["cliffhanger"] + 0.15 * res["standalone"] + 0.3 * res["overall"]) / 10
        p.scores["rules_total"] = p.scores["total"]
        p.scores["llm_total"] = round(llm_total, 4)
        p.scores["total"] = round(0.5 * p.scores["rules_total"] + 0.5 * llm_total, 4)
        if res["why"]:
            p.why = res["why"]
        if res["risk"]:
            p.flags = p.flags + [f"AI judge: {res['risk']}"]
        return p


def _apply_trim(p: Promo, sb, eb, eps) -> str:
    """Accept a trim only if it keeps every hard rule. Otherwise keep the original cut."""
    if not sb and not eb:
        return "none"
    if len(p.segments) > 1:
        return "rejected: trims only for single clips"
    seg = p.segments[0]
    ep = eps[seg.ep]
    if (sb and sb.ep != seg.ep) or (eb and eb.ep != seg.ep):
        return "rejected: beat from another episode"
    s = sb.start if sb else seg.start
    e = eb.end if eb else seg.end
    if (s, e) == (seg.start, seg.end):
        return "none"
    if not (MIN_LEN <= e - s <= MAX_LEN):
        return f"rejected: {fmt(s)}-{fmt(e)} is {e - s:.1f} s, outside 20-60 s"
    if s < seg.start - 0.01 or e > seg.end + 0.01:
        return "rejected: trims may only shorten the cut"
    lines = _utterances(ep)
    if any(l.start < s - 0.05 and l.end > s + 0.05 or l.start < e - 0.05 and l.end > e + 0.05 for l in lines):
        return "rejected: would cut inside a spoken line"
    new = _inside(ep, s, e)
    hooks = [b for b in new if b.kind != "camera" and b.start - s <= HOOK_WINDOW]
    if not hooks:
        return "rejected: nothing to hook within 3 s of the new start"
    p.segments = [Segment(seg.ep, s, e, new)]
    return f"applied: {fmt(s)}-{fmt(e)}"


def _json(text: str) -> dict:
    """First JSON object in the reply (tolerates code fences and chatter around it)."""
    text = re.sub(r"```(?:json)?", "", text or "")
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start:i + 1])
                        if isinstance(obj, dict):
                            return obj
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise JudgeError("no JSON object in model reply")


def _score(v) -> float | None:
    """'8', 8, 8.0, '8/10', '8 out of 10', '80%' -> 8.0 (clamped to 1-10). Anything else -> None."""
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        x = float(v)
    else:
        m = re.search(r"-?\d+(?:\.\d+)?", str(v))
        if not m:
            return None
        x = float(m.group(0))
        if "%" in str(v) or (x > 10 and x <= 100 and "/100" in str(v)):
            x = x / 10
    if x > 10 and x <= 100:
        x = x / 10
    return max(1.0, min(10.0, x))


def _int(v) -> int | None:
    if isinstance(v, bool) or v is None:
        return None
    try:
        f = float(str(v).strip().lstrip("#[").rstrip("]"))
    except ValueError:
        return None
    return int(f) if f == int(f) else None


def _mock(prompt: str) -> str:
    """Deterministic FAKE judge for offline tests of the AI code path. Not a model; never use for results."""
    n = len(re.findall(r"^\[\d+\]", prompt, re.M))
    h = int(hashlib.md5(prompt.encode()).hexdigest(), 16)
    return json.dumps({"hook": 5 + h % 5, "cliffhanger": 4 + h % 6, "standalone": 6, "overall": 5 + h % 4,
                       "hook_beat": 1, "cliff_beat": n, "trim_start_beat": None, "trim_end_beat": None,
                       "why": "MOCK judge output (test only, not a model).", "risk": ""})
