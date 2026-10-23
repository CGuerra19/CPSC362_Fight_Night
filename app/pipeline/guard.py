"""Pipeline error handling (FNA-16).

Two kinds of failure, handled in two places:
- The call failed (LLMError): llm.complete() already retries the
  transient ones, so anything that reaches here is final.
- The answer was the wrong shape (ContractError): ask() re-asks the model
  once, telling it exactly which rules it broke.

user_message() turns either into one sentence a user can act on, so the
endpoint (FNA-15) never shows a stack trace or raw provider text.
"""

from . import llm
from .schemas import ContractError


def ask(system, user, parse, complete=llm.complete, repairs=1):
    """Call the model and validate the reply with parse().

    On a ContractError, re-ask up to `repairs` times with the problems
    listed. The eval (FNA-4) passes repairs=0 to measure how often a
    version gets the shape right on the first try.
    """
    raw = complete(system, user)
    for attempt in range(repairs + 1):
        try:
            return parse(raw)
        except ContractError as e:
            if attempt == repairs:
                raise
            raw = complete(system, user + _repair_note(e))


def _repair_note(err):
    problems = "\n".join(f"- {p}" for p in err.problems)
    return (
        f"\n\nYour previous reply was rejected for these reasons:\n{problems}\n"
        f"Reply again with the corrected JSON object only."
    )


_MESSAGES = {
    "config": "The analyzer isn't set up to reach its AI model right now.",
    "auth": "The AI service rejected the API key.",
    "rate_limit": "The AI service is busy. Please wait a minute and try again.",
    "unavailable": "The AI service isn't responding right now. Please try again shortly.",
    "bad_request": "The AI service couldn't process this request.",
}


def user_message(err):
    """One plain sentence for the UI. The full detail stays in the logs."""
    if isinstance(err, llm.LLMError):
        return _MESSAGES.get(err.kind, _MESSAGES["unavailable"])
    if isinstance(err, ContractError):
        return "The AI returned an incomplete analysis. Please try again."
    return "Something went wrong while analyzing this matchup."
