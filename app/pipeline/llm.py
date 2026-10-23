"""LLM provider client (FNA-12, retries FNA-16).

One function, complete(), hides which provider is behind it. The stages
call complete() and never talk to an API directly, so swapping Groq for
another provider (or for the demo cache) touches only this file.
"""

import os
import re
import time

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"

# Transient failures (rate limit, Groq overloaded, network blip) are retried.
# The free tier allows 8k tokens a minute and one matchup uses ~7.4k, so a
# second matchup inside the same minute is expected to wait, not fail.
MAX_ATTEMPTS = 4
MAX_WAIT = 30  # seconds; a longer wait than this means give up and say so

_sleep = time.sleep  # swapped out in tests so they don't actually wait


class LLMError(RuntimeError):
    """The provider call itself failed: no key, network error, bad status.
    Different from ContractError, which means the call worked but the
    answer was the wrong shape.

    kind is one of: config, auth, rate_limit, unavailable, bad_request.
    The endpoint (FNA-15) turns it into a message a user can act on.
    """

    def __init__(self, message, kind):
        super().__init__(message)
        self.kind = kind


def complete(system, user, *, provider=None, api_key=None, model=None, temperature=0.2, timeout=60):
    """Send one system + user prompt and return the model's raw text reply."""
    provider = provider or os.getenv("LLM_PROVIDER", "demo")

    if provider == "groq":
        return _groq(system, user, api_key, model, temperature, timeout)
    if provider == "demo":
        # Demo mode serves saved answers from the response cache, which
        # doesn't exist yet. Until then there is nothing to serve.
        raise LLMError("Demo mode has no saved answers yet. Set LLM_PROVIDER=groq and a GROQ_API_KEY.", "config")
    raise LLMError(f"Unknown LLM provider '{provider}'", "config")


def _groq(system, user, api_key, model, temperature, timeout):
    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        raise LLMError("GROQ_API_KEY is not set", "config")

    body = {
        "model": model or os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        # JSON mode: the reply is guaranteed to be valid JSON, but not
        # guaranteed to match our schema. That's what parse_profile checks.
        "response_format": {"type": "json_object"},
    }

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {key}"},
                json=body,
                timeout=timeout,
            )
        except requests.RequestException as e:
            err, wait = LLMError(f"Could not reach Groq: {e}", "unavailable"), 2 ** attempt
        else:
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            err, wait = _classify(resp, attempt)
            if wait is None:
                raise err  # retrying won't fix a bad key or a bad request

        if attempt == MAX_ATTEMPTS or wait > MAX_WAIT:
            raise err
        _sleep(wait)


def _classify(resp, attempt):
    """Turn a non-200 reply into (error, seconds to wait), wait None = don't retry."""
    code, text = resp.status_code, resp.text[:300]
    msg = f"Groq returned {code}: {text}"

    if code == 429:
        return LLMError(msg, "rate_limit"), _retry_after(resp, 2 ** attempt)
    if code >= 500:
        return LLMError(msg, "unavailable"), 2 ** attempt
    if code == 400 and "json_validate_failed" in text:
        # JSON mode caught the model producing broken JSON. A fresh
        # attempt usually comes back clean.
        return LLMError(msg, "unavailable"), 1
    if code in (401, 403):
        return LLMError(msg, "auth"), None
    return LLMError(msg, "bad_request"), None


def _retry_after(resp, default):
    """Seconds Groq asked us to wait: the retry-after header, else the
    "try again in 9.57s" text in the error message, else the default."""
    header = resp.headers.get("retry-after")
    if header:
        try:
            return float(header) + 0.5
        except ValueError:
            pass
    m = re.search(r"try again in ([\d.]+)s", resp.text)
    return float(m.group(1)) + 0.5 if m else default
