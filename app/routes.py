"""HTTP routes. Thin layer: parse the request, call into a module, return JSON."""

from flask import Blueprint, current_app, jsonify, render_template, request

from .data import load_fighters

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
    """Matchup analysis. Implemented in FNA-15 once the pipeline exists."""
    return jsonify({"error": "Not implemented yet - see FNA-15"}), 501
