"""Stage 2 (FNA-13): two validated FighterProfiles in, a MatchupAnalysis out.

Stage 2 never sees the raw stats, only the Stage 1 profiles. Each stage
has one small job, which keeps both prompts short and their output easy
to check. Like stage1.py, this is the plain V1 baseline.
"""

import json

from . import llm
from .schemas import MatchupAnalysis, parse_matchup

SYSTEM_V1 = (
    "You are an MMA analyst. Compare two fighters using only the profiles "
    "you are given. Reply with a single JSON object and nothing else."
)


def build_prompt(profile_a, profile_b):
    schema = json.dumps(MatchupAnalysis.model_json_schema())

    return (
        f"Fighter A profile:\n{profile_a.model_dump_json(indent=2)}\n\n"
        f"Fighter B profile:\n{profile_b.model_dump_json(indent=2)}\n\n"
        f"Analyze this matchup as JSON matching this schema:\n{schema}\n\n"
        f'Use fighter_a_id "{profile_a.fighter_id}" and fighter_b_id "{profile_b.fighter_id}". '
        f"predicted_winner_id must be one of those two ids, and each key factor's "
        f'"favors" must be one of those two ids or "even".'
    )


def compare(profile_a, profile_b, complete=llm.complete):
    """Run Stage 2 on two profiles from stage1.build_profile."""
    raw = complete(SYSTEM_V1, build_prompt(profile_a, profile_b))
    return parse_matchup(raw, profile_a.fighter_id, profile_b.fighter_id)
