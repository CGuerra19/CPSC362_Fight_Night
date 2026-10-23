"""Output contracts for the two pipeline stages (FNA-10, FNA-11).

Stage 1 distills one fighter's raw stats into a FighterProfile.
Stage 2 compares two profiles into a MatchupAnalysis.

Every LLM response goes through parse_profile / parse_matchup before
anything else touches it. extra="forbid" makes an unexpected key a failure
instead of a silent pass, so a prompt change that drifts the output shape
shows up right away rather than as a mystery drop in the eval numbers.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

Style = Literal["Striker", "Wrestler", "Grappler", "All-rounder"]
Method = Literal["KO/TKO", "Submission", "Decision"]
Confidence = Literal["Low", "Medium", "High"]

# Stat names a profile is allowed to cite. They match the keys in
# fighters.json, so the eval harness can look each cited value up and flag
# any number the model made up (FNA-29 fact-coverage / forbidden-claim).
StatName = Literal[
    "wins", "losses", "height_in", "reach_in", "age",
    "slpm", "str_acc_pct", "sapm", "str_def_pct",
    "td_avg_per15", "td_acc_pct", "td_def_pct", "sub_avg_per15",
]

# Short free-text fields. The caps keep the model from padding answers.
Point = Annotated[str, Field(min_length=1, max_length=200)]
Paragraph = Annotated[str, Field(min_length=1, max_length=800)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---- Stage 1 ---------------------------------------------------------------

class StatCitation(_Strict):
    """One number the profile leans on, tied back to its source field."""
    stat: StatName
    value: float
    meaning: Point


class FighterProfile(_Strict):
    fighter_id: str
    name: str
    style: Style
    strengths: list[Point] = Field(min_length=2, max_length=5)
    weaknesses: list[Point] = Field(min_length=1, max_length=4)
    striking_summary: Paragraph
    grappling_summary: Paragraph
    key_stats: list[StatCitation] = Field(min_length=3, max_length=8)


# ---- Stage 2 ---------------------------------------------------------------

class KeyFactor(_Strict):
    factor: Point
    favors: str  # a fighter_id from this matchup, or "even"
    reasoning: Paragraph


class MatchupAnalysis(_Strict):
    # Field order matters: models tend to fill a schema top to bottom, so the
    # factors and paths come before the verdict. The reasoning gets written
    # first and the pick follows from it, not the other way round.
    fighter_a_id: str
    fighter_b_id: str
    key_factors: list[KeyFactor] = Field(min_length=2, max_length=5)
    fighter_a_path_to_victory: Paragraph
    fighter_b_path_to_victory: Paragraph
    predicted_winner_id: str
    method: Method
    confidence: Confidence
    summary: Paragraph

    @model_validator(mode="after")
    def _ids_line_up(self):
        ids = {self.fighter_a_id, self.fighter_b_id}
        if len(ids) != 2:
            raise ValueError("fighter_a_id and fighter_b_id must be different fighters")
        if self.predicted_winner_id not in ids:
            raise ValueError("predicted_winner_id must be fighter_a_id or fighter_b_id")
        for kf in self.key_factors:
            if kf.favors not in ids | {"even"}:
                raise ValueError(f"key factor '{kf.factor}' favors unknown id '{kf.favors}'")
        return self


# ---- Parsing ---------------------------------------------------------------

class ContractError(ValueError):
    """An LLM response did not match its stage's contract.

    Keeps the raw text so error handling (FNA-16) can log or retry with it.
    """

    def __init__(self, stage, problems, raw):
        self.stage = stage
        self.problems = problems
        self.raw = raw
        super().__init__(f"{stage} output broke its contract: " + "; ".join(problems))


def _strip_fences(raw):
    """Models often wrap JSON in ```json fences even when told not to.
    That's packaging, not content, so peel it off before validating."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    return text.strip()


def _problems(err):
    return [
        f"{'.'.join(str(p) for p in e['loc']) or '(root)'}: {e['msg']}"
        for e in err.errors()
    ]


def parse_profile(raw, fighter_id=None):
    """Validate a Stage 1 response. Pass fighter_id to also catch the model
    profiling the wrong fighter."""
    try:
        profile = FighterProfile.model_validate_json(_strip_fences(raw))
    except ValidationError as e:
        raise ContractError("stage1", _problems(e), raw) from e

    if fighter_id and profile.fighter_id != fighter_id:
        raise ContractError(
            "stage1", [f"fighter_id: expected '{fighter_id}', got '{profile.fighter_id}'"], raw
        )
    return profile


def parse_matchup(raw, fighter_a_id=None, fighter_b_id=None):
    """Validate a Stage 2 response. Pass the two ids to also catch the model
    swapping or inventing fighters."""
    try:
        analysis = MatchupAnalysis.model_validate_json(_strip_fences(raw))
    except ValidationError as e:
        raise ContractError("stage2", _problems(e), raw) from e

    expected = (fighter_a_id, fighter_b_id)
    got = (analysis.fighter_a_id, analysis.fighter_b_id)
    if all(expected) and got != expected:
        raise ContractError("stage2", [f"fighter ids: expected {expected}, got {got}"], raw)
    return analysis
