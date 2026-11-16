"""Automatic checks on one matchup result (FNA-35, FNA-37).

Both take a result from dispatcher.run_matchup() plus its test case, and
look the real numbers up in fighters.json at run time. No AI calls, so
they're free, fast, and give the same answer every time.
"""

import re

# Where each citable stat lives in a fighter record.
STAT_GROUP = {
    "wins": "record", "losses": "record",
    "height_in": "physical", "reach_in": "physical", "age": "physical",
    "slpm": "striking", "str_acc_pct": "striking", "sapm": "striking", "str_def_pct": "striking",
    "td_avg_per15": "grappling", "td_acc_pct": "grappling", "td_def_pct": "grappling", "sub_avg_per15": "grappling",
}


def true_value(fighter, stat):
    return fighter[STAT_GROUP[stat]][stat]


def citations(result):
    """Every (fighter_id, stat, value) the output cites: the Stage 1
    key_stats, plus the v4 evidence on each key factor."""
    cited = []
    for profile in result["profiles"].values():
        cited += [(profile["fighter_id"], ks["stat"], ks["value"]) for ks in profile["key_stats"]]
    for kf in result["analysis"]["key_factors"]:
        cited += [(ev["fighter_id"], ev["stat"], ev["value"]) for ev in kf.get("evidence", [])]
    return cited


# ---- FNA-35: fact coverage ---------------------------------------------------------

def fact_coverage(result, case, fighters):
    """Two numbers between 0 and 1:

    accuracy: of all the stats the output cites, how many have the right value
    coverage: of the stats this case expects, how many were cited correctly

    fighters maps id -> fighter record.
    """
    cited = citations(result)
    # Judge every citation on its own: a stat quoted right in one place and
    # wrong in another still counts as one wrong value.
    is_right = [abs(true_value(fighters[fid], stat) - value) <= 0.01 for fid, stat, value in cited]
    wrong = [
        f"{fid} {stat}: said {value}, actual {true_value(fighters[fid], stat)}"
        for (fid, stat, value), ok in zip(cited, is_right)
        if not ok
    ]
    correct = {(fid, stat) for (fid, stat, _), ok in zip(cited, is_right) if ok}

    expected = [(fid, stat) for fid, stats in case["expected_stats"].items() for stat in stats]
    missed = [f"{fid} {stat}" for fid, stat in expected if (fid, stat) not in correct]

    return {
        "accuracy": round(1 - len(wrong) / len(cited), 3) if cited else 0.0,
        "coverage": round(1 - len(missed) / len(expected), 3) if expected else 1.0,
        "wrong_values": wrong,
        "missed_stats": missed,
    }


# ---- FNA-37: forbidden claims --------------------------------------------------------

# A defense stat explained without any defense word is almost always the
# v1 mistake: reading "str_def_pct 60" as "opponents land 60%".
DEFENSE_STATS = ("str_def_pct", "td_def_pct")
DEFENSE_WORDS = re.compile(r"avoid|defen|stop|block|prevent|evade|den(y|ies)|stuff|slip|neutraliz", re.I)


def all_text(result):
    """Every free-text field in the output, as one string per field."""
    texts = []
    for p in result["profiles"].values():
        texts += p["strengths"] + p["weaknesses"] + [p["striking_summary"], p["grappling_summary"]]
        texts += [ks["meaning"] for ks in p["key_stats"]]
    a = result["analysis"]
    texts += [a["fighter_a_path_to_victory"], a["fighter_b_path_to_victory"], a["summary"]]
    for kf in a["key_factors"]:
        texts += [kf["factor"], kf["reasoning"]]
    return texts


def forbidden_claims(result, case, fighters):
    """A list of claims the output got wrong. Empty means a clean pass."""
    problems = []
    rules = case["forbidden"]

    # 1. Style labels that contradict the data
    for profile in result["profiles"].values():
        if profile["style"] in rules["styles"].get(profile["fighter_id"], []):
            problems.append(f"style: {profile['name']} labeled {profile['style']}")

    # 2. Key factors credited to the wrong fighter
    for kf in result["analysis"]["key_factors"]:
        name = kf["factor"].lower()
        for rule in rules["favors"]:
            if kf["favors"] == rule["not"] and any(k in name for k in rule["keywords"]):
                problems.append(f"favors: '{kf['factor']}' given to {rule['not']} ({rule['why']})")

    # 3. Case-specific phrases
    for text in all_text(result):
        for rule in rules["phrases"]:
            if re.search(rule["pattern"], text, re.I):
                problems.append(f"phrase: '{text[:80]}' ({rule['why']})")

    # 4. General rules that apply to every case
    problems += _undefeated_claims(result, fighters)
    problems += _defense_misreads(result)
    return problems


def _undefeated_claims(result, fighters):
    """Calling a fighter with losses undefeated. Checked per sentence: the
    sentence is fine if anyone it could be about really is undefeated, so
    "Makhachev faces the undefeated Topuria" passes."""
    problems = []
    ids = [result["fighter_a"]["id"], result["fighter_b"]["id"]]
    for text in all_text(result):
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if not re.search(r"undefeated|unbeaten|never (been )?(lost|beaten)", sentence, re.I):
                continue
            # Who the sentence names (by last name); if nobody, it's about either fighter.
            about = [i for i in ids if fighters[i]["name"].split()[-1].lower() in sentence.lower()] or ids
            if all(fighters[i]["record"]["losses"] > 0 for i in about):
                problems.append(f"undefeated: '{sentence[:80]}', but nobody it names is undefeated")
    return problems


def _defense_misreads(result):
    problems = []
    for p in result["profiles"].values():
        for ks in p["key_stats"]:
            if ks["stat"] in DEFENSE_STATS and not DEFENSE_WORDS.search(ks["meaning"]):
                problems.append(f"defense misread: {p['name']} {ks['stat']} explained as '{ks['meaning'][:60]}'")
    return problems
