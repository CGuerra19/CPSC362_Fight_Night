"""LLM provider client (FNA-12).

One function, complete(), hides which provider is behind it. The stages
call complete() and never talk to an API directly, so swapping Groq for
another provider (or for the demo cache) touches only this file.
"""

import os

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


class LLMError(RuntimeError):
    """The provider call itself failed: no key, network error, bad status.
    Different from ContractError, which means the call worked but the
    answer was the wrong shape."""


def complete(system, user, *, provider=None, api_key=None, model=None, temperature=0.2, timeout=60):
    """Send one system + user prompt and return the model's raw text reply."""
    provider = provider or os.getenv("LLM_PROVIDER", "demo")

    if provider == "groq":
        return _groq(system, user, api_key, model, temperature, timeout)
    if provider == "demo":
        # Demo mode serves saved answers from the response cache, which
        # doesn't exist yet. Until then there is nothing to serve.
        raise LLMError("Demo mode has no saved answers yet. Set LLM_PROVIDER=groq and a GROQ_API_KEY.")
    raise LLMError(f"Unknown LLM provider '{provider}'")


def _groq(system, user, api_key, model, temperature, timeout):
    key = api_key or os.getenv("GROQ_API_KEY")
    if not key:
        raise LLMError("GROQ_API_KEY is not set")

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

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}"},
            json=body,
            timeout=timeout,
        )
    except requests.RequestException as e:
        raise LLMError(f"Could not reach Groq: {e}") from e

    if resp.status_code != 200:
        raise LLMError(f"Groq returned {resp.status_code}: {resp.text[:300]}")

    return resp.json()["choices"][0]["message"]["content"]
