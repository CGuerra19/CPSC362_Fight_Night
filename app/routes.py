"""HTTP routes. Thin layer: parse the request, call into a module, return JSON."""

from functools import partial

from flask import Blueprint, current_app, jsonify, render_template, request

from .data import load_fighters
from .pipeline import guard, llm
from .pipeline.dispatcher import run_matchup
from .pipeline.schemas import ContractError
from .pipeline.versions import VERSIONS

bp = Blueprint("main", __name__)


@bp.get("/")
def index():
    """Serve the single-page UI. Real markup lands in FNA-17."""
    return render_template("index.html")


@bp.get("/api/fighters")
def api_fighters():
    """Autocomplete endpoint (FNA-7).

    GET /api/fighters?q=hol&limit=8
    Returns [] for a blank query rather than the whole roster, so an empty
    input box does not trigger a dropdown.
    """
    q = request.args.get("q", "")

    try:
        limit = int(request.args.get("limit", 8))
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400

    limit = max(1, min(limit, 25))
    return jsonify({"results": load_fighters.search_names(q, limit=limit)})


@bp.get("/api/health")
def api_health():
    """Status probe. Surfaces the data-verification state so a stale seed
    database is visible without digging through the JSON."""
    return jsonify(
        {
            "ok": True,
            "provider": current_app.config["LLM_PROVIDER"],
            "pipeline_version": current_app.config["PIPELINE_VERSION"],
            "data": load_fighters.data_status(),
        }
    )


@bp.post("/api/matchup")
def api_matchup():
    """Matchup analysis (FNA-15).

    POST /api/matchup
    {"fighter_a": "<id>", "fighter_b": "<id>",
     "version": "v1".."v4"   optional, defaults to PIPELINE_VERSION
     "api_key": "..."}       optional, the user's own Groq key

    Errors come back as {"error": "<one plain sentence>"} with a status
    code, never a stack trace or raw provider text.
    """
    body = request.get_json(silent=True) or {}
    id_a, id_b = body.get("fighter_a"), body.get("fighter_b")

    if not id_a or not id_b:
        return jsonify({"error": "Choose two fighters."}), 400
    if id_a == id_b:
        return jsonify({"error": "Choose two different fighters."}), 400

    fighter_a, fighter_b = load_fighters.get_fighter(id_a), load_fighters.get_fighter(id_b)
    missing = [i for i, f in ((id_a, fighter_a), (id_b, fighter_b)) if f is None]
    if missing:
        return jsonify({"error": f"Unknown fighter: {', '.join(missing)}"}), 404

    version = body.get("version") or current_app.config["PIPELINE_VERSION"]
    if version not in VERSIONS:
        return jsonify({"error": f"Unknown version. Choose one of: {', '.join(VERSIONS)}"}), 400

    # A key typed into the page is used for this one request only. It is
    # never stored or logged.
    complete = llm.complete
    api_key = (body.get("api_key") or "").strip()
    if api_key:
        complete = partial(llm.complete, provider="groq", api_key=api_key)

    try:
        return jsonify(run_matchup(fighter_a, fighter_b, version, complete))
    except (llm.LLMError, ContractError) as e:
        current_app.logger.warning("matchup %s vs %s failed: %s", id_a, id_b, e)
        return jsonify({"error": guard.user_message(e)}), _status(e)


def _status(err):
    """HTTP status for a pipeline failure."""
    if isinstance(err, llm.LLMError):
        return {"rate_limit": 429, "auth": 401, "config": 503, "unavailable": 503}.get(err.kind, 502)
    return 502  # ContractError: the AI answered, but not usefully
