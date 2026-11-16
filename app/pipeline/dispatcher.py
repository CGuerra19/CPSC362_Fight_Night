"""Dispatcher (FNA-14): one call runs a whole matchup through any version.

The endpoint (FNA-15) and the eval harness (FNA-4) both go through
run_matchup(), so the app and the eval always run the exact same pipeline.
"""

from . import llm, stage1, stage2
from .versions import get_version


def run_matchup(fighter_a, fighter_b, version="v1", complete=llm.complete, repairs=1):
    """Two fighter records from load_fighters in, a JSON-ready result out.

    Three AI calls: a Stage 1 profile for each fighter, then Stage 2.
    Raises ValueError for an unknown version, LLMError if the AI call
    fails, ContractError if the reply is still wrong after the re-ask.
    """
    v = get_version(version)

    profile_a = stage1.build_profile(fighter_a, v, complete, repairs)
    profile_b = stage1.build_profile(fighter_b, v, complete, repairs)
    divisions = (fighter_a["division"], fighter_b["division"])
    analysis = stage2.compare(profile_a, profile_b, v, complete, repairs, divisions)

    return {
        "version": v.name,
        "fighter_a": _summary(fighter_a),
        "fighter_b": _summary(fighter_b),
        # The UI (FNA-3) shows a one-line note when this is true.
        "cross_division": divisions[0] != divisions[1],
        "profiles": {"fighter_a": profile_a.model_dump(), "fighter_b": profile_b.model_dump()},
        "analysis": analysis.model_dump(),
    }


def _summary(fighter):
    return {"id": fighter["id"], "name": fighter["name"], "division": fighter["division"]}
