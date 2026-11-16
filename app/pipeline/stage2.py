"""Stage 2 (FNA-13): two validated FighterProfiles in, a MatchupAnalysis out.

Stage 2 never sees the raw stats, only the Stage 1 profiles. Each stage
has one small job, which keeps both prompts short and their output easy
to check. The v1 prompt is the plain baseline; FNA-14 adds the rest.
"""

import json

from . import llm
from .guard import ask
from .schemas import ContractError, MatchupAnalysis, MatchupAnalysisV4, parse_matchup
from .versions import VERSIONS

SYSTEM_V1 = (
    "You are an MMA analyst. Compare two fighters using only the profiles "
    "you are given. Reply with a single JSON object and nothing else."
)

# v2: upper weight limit of each UFC division, in pounds.
WEIGHT_LIMITS = {
    "Strawweight": 115, "Flyweight": 125, "Bantamweight": 135, "Featherweight": 145,
    "Lightweight": 155, "Welterweight": 170, "Middleweight": 185,
    "Light Heavyweight": 205, "Heavyweight": 265,
}


def _division_note(profile_a, profile_b, divisions):
    """v2: tell Stage 2 where each fighter competes, and flag a size gap."""
    lines = []
    for profile, division in zip((profile_a, profile_b), divisions):
        limit = WEIGHT_LIMITS.get(division.replace("Women's ", ""))
        weight = f" ({limit} lb limit)" if limit else ""
        lines.append(f"- {profile.name} competes at {division}{weight}.")
    if divisions[0] != divisions[1]:
        lines.append(
            "These fighters are in different divisions. Account for the size and "
            "weight difference; it can outweigh small differences in skill."
        )
    return "Divisions:\n" + "\n".join(lines) + "\n\n"


EVIDENCE_RULE = (
    "Each key factor must include evidence: the stats it rests on, copied "
    "from the key_stats of the fighter they belong to, with that fighter's "
    "fighter_id, the stat name, and the exact value."
)


def build_prompt(profile_a, profile_b, version=VERSIONS["v1"], divisions=None):
    model = MatchupAnalysisV4 if version.evidence else MatchupAnalysis
    schema = json.dumps(model.model_json_schema())
    divs = _division_note(profile_a, profile_b, divisions) if version.divisions and divisions else ""
    evidence = f" {EVIDENCE_RULE}" if version.evidence else ""

    return (
        f"Fighter A profile:\n{profile_a.model_dump_json(indent=2)}\n\n"
        f"Fighter B profile:\n{profile_b.model_dump_json(indent=2)}\n\n"
        f"{divs}"
        f"Analyze this matchup as JSON matching this schema:\n{schema}\n\n"
        f'Use fighter_a_id "{profile_a.fighter_id}" and fighter_b_id "{profile_b.fighter_id}". '
        f"predicted_winner_id must be one of those two ids, and each key factor's "
        f'"favors" must be one of those two ids or "even".{evidence}'
    )


def check_evidence(analysis, profile_a, profile_b, raw):
    """v4: every cited stat must be one the fighter's profile actually lists,
    with the same value. Catches the model inventing or misquoting numbers."""
    cited = {
        p.fighter_id: {ks.stat: ks.value for ks in p.key_stats}
        for p in (profile_a, profile_b)
    }
    problems = []
    for kf in analysis.key_factors:
        for ev in kf.evidence:
            known = cited[ev.fighter_id]
            if ev.stat not in known:
                problems.append(f"'{kf.factor}' cites {ev.stat} for {ev.fighter_id}, which is not in that profile's key_stats")
            elif abs(known[ev.stat] - ev.value) > 0.01:
                problems.append(f"'{kf.factor}' cites {ev.stat}={ev.value} for {ev.fighter_id}, but the profile says {known[ev.stat]}")
    if problems:
        raise ContractError("stage2", problems, raw)
    return analysis


def compare(profile_a, profile_b, version=VERSIONS["v1"], complete=llm.complete, repairs=1, divisions=None):
    """Run Stage 2 on two profiles from stage1.build_profile.

    divisions is (division_a, division_b) from the fighter records; v2+
    uses it to account for size.
    """
    model = MatchupAnalysisV4 if version.evidence else MatchupAnalysis

    def call(system, user):
        schema = model if version.strict else None
        return complete(system, user, temperature=version.temperature, schema=schema)

    def parse(raw):
        analysis = parse_matchup(raw, profile_a.fighter_id, profile_b.fighter_id, model)
        if version.evidence:
            check_evidence(analysis, profile_a, profile_b, raw)
        return analysis

    return ask(SYSTEM_V1, build_prompt(profile_a, profile_b, version, divisions), parse, call, repairs)
