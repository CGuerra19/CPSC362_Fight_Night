"""Stage 1 (FNA-12): one fighter's raw stats in, a validated FighterProfile out.

This is the V1 prompt: deliberately plain, so later versions (FNA-14) have
a baseline to beat in the eval (FNA-4).
"""

import json

from . import llm
from .schemas import FighterProfile, parse_profile

SYSTEM_V1 = (
    "You are an MMA analyst. Describe a fighter using only the statistics "
    "you are given. Reply with a single JSON object and nothing else."
)

# Bookkeeping fields that say nothing about how the fighter fights.
_SKIP = ("verified", "scheduled_bout")


def build_prompt(fighter):
    data = {k: v for k, v in fighter.items() if k not in _SKIP}
    schema = json.dumps(FighterProfile.model_json_schema())

    return (
        f"Fighter data:\n{json.dumps(data, indent=2)}\n\n"
        f"Write a profile of this fighter as JSON matching this schema:\n{schema}\n\n"
        f'Use fighter_id "{fighter["id"]}". Each key_stats entry must use one of '
        f"the stat names allowed by the schema and the exact value from the data."
    )


def build_profile(fighter, complete=llm.complete):
    """Run Stage 1 for one fighter record from load_fighters.

    complete is swappable so tests can pass a fake model instead of
    calling the real API.
    """
    raw = complete(SYSTEM_V1, build_prompt(fighter))
    return parse_profile(raw, fighter_id=fighter["id"])
