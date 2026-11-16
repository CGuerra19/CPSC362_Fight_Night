"""Pipeline versions (FNA-14).

Each version adds one change on top of the one before it, so the eval
(FNA-4) can tie a score change to a single cause:

  v1  plain prompts (the baseline)
  v2  + explain what each stat means, + give Stage 2 both divisions
  v3  + Groq strict schema mode, + temperature 0
  v4  + every key factor must cite the stats it rests on

The web app runs whichever version PIPELINE_VERSION names. The eval runs
the same matchups through every version and compares the scores.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Version:
    name: str
    explain_stats: bool = False  # v2: stat glossary in the Stage 1 prompt
    divisions: bool = False      # v2: Stage 2 knows each fighter's weight class
    strict: bool = False         # v3: Groq enforces the schema while generating
    temperature: float = 0.2     # v3: 0 makes runs more repeatable
    evidence: bool = False       # v4: key factors must cite stats


VERSIONS = {
    "v1": Version("v1"),
    "v2": Version("v2", explain_stats=True, divisions=True),
    "v3": Version("v3", explain_stats=True, divisions=True, strict=True, temperature=0.0),
    "v4": Version("v4", explain_stats=True, divisions=True, strict=True, temperature=0.0, evidence=True),
}


def get_version(name):
    """Look up a version by name ("v1".."v4"). Raises ValueError if unknown."""
    version = VERSIONS.get((name or "").strip().lower())
    if version is None:
        raise ValueError(f"Unknown pipeline version '{name}'. Choose one of: {', '.join(VERSIONS)}")
    return version
