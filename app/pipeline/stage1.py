"""Stage 1 (FNA-12): one fighter's raw stats in, a validated FighterProfile out.

The v1 prompt is deliberately plain, so later versions (FNA-14) have a
baseline to beat in the eval (FNA-4).
"""

import json

from . import llm
from .guard import ask
from .schemas import FighterProfile, parse_profile
from .versions import VERSIONS

SYSTEM_V1 = (
    "You are an MMA analyst. Describe a fighter using only the statistics "
    "you are given. Reply with a single JSON object and nothing else."
)

# v2: what each stat actually measures. v1 misread str_def_pct 60 as
# "opponents land 60%", when it means this fighter avoids 60%.
STAT_GLOSSARY = """What each statistic means:
- wins, losses: professional MMA record
- height_in, reach_in: height and arm reach in inches
- age: age in years
- slpm: significant strikes this fighter LANDS per minute
- str_acc_pct: percent of this fighter's significant strike attempts that land
- sapm: significant strikes this fighter ABSORBS (gets hit with) per minute
- str_def_pct: percent of opponents' significant strike attempts this fighter AVOIDS (higher is better)
- td_avg_per15: takedowns this fighter lands per 15 minutes
- td_acc_pct: percent of this fighter's takedown attempts that succeed
- td_def_pct: percent of opponents' takedown attempts this fighter STOPS (higher is better)
- sub_avg_per15: submission attempts this fighter makes per 15 minutes"""

# Bookkeeping fields that say nothing about how the fighter fights.
_SKIP = ("verified", "scheduled_bout")


def build_prompt(fighter, version=VERSIONS["v1"]):
    data = {k: v for k, v in fighter.items() if k not in _SKIP}
    schema = json.dumps(FighterProfile.model_json_schema())
    glossary = f"{STAT_GLOSSARY}\n\n" if version.explain_stats else ""

    return (
        f"Fighter data:\n{json.dumps(data, indent=2)}\n\n"
        f"{glossary}"
        f"Write a profile of this fighter as JSON matching this schema:\n{schema}\n\n"
        f'Use fighter_id "{fighter["id"]}". Each key_stats entry must use one of '
        f"the stat names allowed by the schema and the exact value from the data."
    )


def build_profile(fighter, version=VERSIONS["v1"], complete=llm.complete, repairs=1):
    """Run Stage 1 for one fighter record from load_fighters.

    complete is swappable so tests can pass a fake model instead of
    calling the real API. repairs is how many times a wrong-shaped answer
    gets re-asked (FNA-16).
    """
    def call(system, user):
        schema = FighterProfile if version.strict else None
        return complete(system, user, temperature=version.temperature, schema=schema)

    return ask(
        SYSTEM_V1,
        build_prompt(fighter, version),
        lambda raw: parse_profile(raw, fighter_id=fighter["id"]),
        call,
        repairs,
    )
