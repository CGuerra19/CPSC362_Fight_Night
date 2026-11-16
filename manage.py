"""Fighter database tool. Edit fighters.json without opening it by hand.

  python manage.py list
  python manage.py show islam-makhachev
  python manage.py add                                        (asks for each field)
  python manage.py result islam-makhachev win submission    (after an event)
  python manage.py set islam-makhachev striking.slpm 2.41
  python manage.py validate

Every change is checked with the same rules as `validate` before it is
saved, so a typo can't break the file the app reads.
"""

import argparse
import json
import sys
from datetime import date

from app.data import load_fighters
from app.pipeline.stage2 import WEIGHT_LIMITS

METHODS = ("ko_tko", "submission", "decision")

# Every fighter needs these, and each one must be a number.
REQUIRED_NUMBERS = {
    "record": ("wins", "losses", "draws", "no_contests"),
    "wins_by": METHODS,
    "losses_by": METHODS,
    "physical": ("height_in", "reach_in", "age"),
    "striking": ("slpm", "str_acc_pct", "sapm", "str_def_pct"),
    "grappling": ("td_avg_per15", "td_acc_pct", "td_def_pct", "sub_avg_per15"),
}


# ---- Commands ----------------------------------------------------------------

def cmd_list(data, args):
    for f in data["fighters"]:
        r = f["record"]
        check = "verified" if f.get("verified") else "UNVERIFIED"
        print(f"{f['id']:22} {f['name']:20} {f['division']:18} {r['wins']}-{r['losses']}-{r['draws']}  {check}")


def cmd_show(data, args):
    print(json.dumps(_find(data, args.id), indent=2, ensure_ascii=False))


def cmd_result(data, args):
    """Record one fight: bumps the record and the win/loss method count."""
    f = _find(data, args.id)
    if args.outcome in ("win", "loss"):
        if args.method not in METHODS:
            sys.exit(f"A {args.outcome} needs a method: {', '.join(METHODS)}")
        f["record"]["wins" if args.outcome == "win" else "losses"] += 1
        f["wins_by" if args.outcome == "win" else "losses_by"][args.method] += 1
    else:
        f["record"]["draws" if args.outcome == "draw" else "no_contests"] += 1
    _save(data)
    r = f["record"]
    print(f"{f['name']} is now {r['wins']}-{r['losses']}-{r['draws']}")


def cmd_add(data, args):
    """Add a new fighter by answering one question per field."""
    print("New fighter. Numbers only for stats; press Enter to skip optional fields.\n")
    name = _ask("Name")
    fighter_id = _slug(name)
    if any(f["id"] == fighter_id for f in data["fighters"]):
        sys.exit(f"'{fighter_id}' is already in the database. Use `set` to change it.")

    f = {
        "id": fighter_id,
        "name": name,
        "nickname": _ask("Nickname", optional=True),
        "division": _ask("Division (e.g. Lightweight, Women's Flyweight)"),
        "ranking": _parse_value(_ask("Ranking (e.g. 3, Champion)", optional=True) or "null"),
        # A new entry starts unverified until its stats are checked
        # against ufcstats.com.
        "verified": False,
    }
    for group, keys in REQUIRED_NUMBERS.items():
        f[group] = {key: _ask_number(f"{group}.{key}") for key in keys}
    f["physical"]["stance"] = _ask("Stance (Orthodox, Southpaw, Switch)", optional=True)
    f["style"] = _ask("Style, in one sentence", optional=True)
    f["notable_wins"] = []
    f["scheduled_bout"] = None

    data["fighters"].append(f)
    data["_meta"]["fighter_count"] = len(data["fighters"])
    _save(data)
    print(f"\nAdded {name} as '{fighter_id}'.")


def cmd_set(data, args):
    """Change one existing field, e.g. striking.slpm. New fields aren't
    allowed, so a misspelled name fails instead of quietly adding a key."""
    f = _find(data, args.id)
    *path, last = args.field.split(".")
    target = f
    for key in path:
        target = target.get(key) if isinstance(target, dict) else None
    if not isinstance(target, dict) or last not in target:
        sys.exit(f"{args.id} has no field '{args.field}'")

    old, target[last] = target[last], _parse_value(args.value)
    _save(data)
    print(f"{args.id} {args.field}: {old} -> {target[last]}")


def cmd_validate(data, args):
    problems = validate(data)
    for p in problems:
        print("-", p)
    print(f"{len(data['fighters'])} fighters, {len(problems)} problem(s)")
    sys.exit(1 if problems else 0)


# ---- Validation --------------------------------------------------------------

def validate(data):
    """Every rule the app and the eval rely on. Returns a list of problems."""
    problems, seen = [], set()

    for i, f in enumerate(data.get("fighters", [])):
        who = f.get("id") or f"fighter #{i + 1}"
        for key in ("id", "name", "division"):
            if not f.get(key):
                problems.append(f"{who}: missing {key}")
        if f.get("id") in seen:
            problems.append(f"{who}: duplicate id")
        seen.add(f.get("id"))

        division = (f.get("division") or "").replace("Women's ", "")
        if division and division not in WEIGHT_LIMITS:
            problems.append(f"{who}: unknown division '{f['division']}'")

        for group, keys in REQUIRED_NUMBERS.items():
            for key in keys:
                value = (f.get(group) or {}).get(key)
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    problems.append(f"{who}: {group}.{key} must be a number")
                elif value < 0:
                    problems.append(f"{who}: {group}.{key} can't be negative")
                elif key.endswith("_pct") and value > 100:
                    problems.append(f"{who}: {group}.{key} is a percent, can't be over 100")

        # The method counts have to add up to the record.
        for outcome, group in (("wins", "wins_by"), ("losses", "losses_by")):
            total = (f.get("record") or {}).get(outcome)
            counts = [(f.get(group) or {}).get(m) for m in METHODS]
            if all(isinstance(c, int) for c in counts) and isinstance(total, int) and sum(counts) != total:
                problems.append(f"{who}: {group} adds up to {sum(counts)} but record says {total} {outcome}")

    count = data.get("_meta", {}).get("fighter_count")
    if count != len(data.get("fighters", [])):
        problems.append(f"_meta.fighter_count is {count} but the file has {len(data.get('fighters', []))} fighters")
    return problems


# ---- Helpers -----------------------------------------------------------------

def _find(data, fighter_id):
    for f in data["fighters"]:
        if f["id"] == fighter_id:
            return f
    sys.exit(f"No fighter with id '{fighter_id}'. Try: python manage.py list")


def _ask(label, optional=False):
    while True:
        answer = input(f"{label}: ").strip()
        if answer or optional:
            return answer or None
        print("  This one is required.")


def _ask_number(label):
    while True:
        answer = input(f"{label}: ").strip()
        try:
            number = float(answer)
        except ValueError:
            print("  Enter a number.")
            continue
        return int(number) if number.is_integer() else number


def _slug(name):
    """'Sean O'Malley' -> 'sean-omalley', the same style as the existing ids."""
    cleaned = "".join(c for c in name.lower() if c.isalnum() or c in " -")
    return "-".join(cleaned.split())


def _parse_value(text):
    """'2.41' -> 2.41, 'true' -> True, 'null' -> None, anything else stays text."""
    try:
        return json.loads(text)
    except ValueError:
        return text


def _save(data):
    problems = validate(data)
    if problems:
        sys.exit("Not saved, the change would break these rules:\n- " + "\n- ".join(problems))
    data["_meta"]["last_updated"] = date.today().isoformat()
    load_fighters.save_raw(data)


def main():
    parser = argparse.ArgumentParser(description="Manage the fighter database.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="one line per fighter").set_defaults(run=cmd_list)

    p = sub.add_parser("show", help="print one fighter's full record")
    p.add_argument("id")
    p.set_defaults(run=cmd_show)

    sub.add_parser("add", help="add a new fighter (asks for each field)").set_defaults(run=cmd_add)

    p = sub.add_parser("result", help="record a fight result")
    p.add_argument("id")
    p.add_argument("outcome", choices=("win", "loss", "draw", "nc"))
    p.add_argument("method", nargs="?", help=" | ".join(METHODS) + " (for a win or loss)")
    p.set_defaults(run=cmd_result)

    p = sub.add_parser("set", help="change one field, e.g. striking.slpm 2.41")
    p.add_argument("id")
    p.add_argument("field")
    p.add_argument("value")
    p.set_defaults(run=cmd_set)

    sub.add_parser("validate", help="check the whole file").set_defaults(run=cmd_validate)

    args = parser.parse_args()
    args.run(load_fighters.read_raw(), args)


if __name__ == "__main__":
    main()
