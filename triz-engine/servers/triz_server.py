#!/usr/bin/env python3
"""TRIZ Knowledge Base MCP Server.

Exposes the 40 Inventive Principles, 39x39 Contradiction Matrix,
and supporting tools via the FastMCP protocol over stdio.
"""

import json
import os
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

DATA_DIR = Path(__file__).parent.parent / "data"

_kb_cache: Optional[dict] = None
_matrix_cache: Optional[dict] = None


def _load_kb() -> dict:
    global _kb_cache
    if _kb_cache is None:
        with open(DATA_DIR / "triz-knowledge-base.json") as f:
            _kb_cache = json.load(f)
    return _kb_cache


def _load_matrix() -> dict:
    global _matrix_cache
    if _matrix_cache is None:
        with open(DATA_DIR / "triz-matrix.json") as f:
            _matrix_cache = json.load(f)
    return _matrix_cache


def _principles_by_id() -> dict[int, dict]:
    kb = _load_kb()
    return {p["id"]: p for p in kb["principles"]}


mcp = FastMCP("triz-knowledge", instructions="TRIZ 40 Inventive Principles knowledge base server")


@mcp.tool()
async def get_principle(id: int) -> str:
    """Retrieve a single TRIZ inventive principle by ID (1-40)."""
    if id < 1 or id > 40:
        return json.dumps({"error": f"Invalid principle ID {id}. Must be 1-40."})
    by_id = _principles_by_id()
    principle = by_id.get(id)
    if principle is None:
        return json.dumps({"error": f"Principle {id} not found."})
    return json.dumps(principle)


@mcp.tool()
async def search_principles(query: str, domain: str = "") -> str:
    """Search TRIZ principles by keyword and optional domain filter. Returns max 5 results."""
    kb = _load_kb()
    results = []
    q = query.lower().strip()

    for p in kb["principles"]:
        if domain and domain.lower() not in [d.lower() for d in p["domains"]]:
            continue

        if not q:
            if domain:
                results.append(p)
            continue

        searchable = f"{p['name']} {p['description']} {' '.join(p.get('software_patterns', []))}".lower()
        if q in searchable:
            results.append(p)

    return json.dumps({"results": results[:5], "total": len(results)})


@mcp.tool()
async def lookup_matrix(param_a: int, param_b: int) -> str:
    """Look up the TRIZ Contradiction Matrix for a parameter pair.

    param_a: improving parameter ID (1-39)
    param_b: worsening parameter ID (1-39)
    Returns recommended principle IDs.
    """
    if param_a < 1 or param_a > 39 or param_b < 1 or param_b > 39:
        return json.dumps({"error": f"Parameter IDs must be 1-39. Got {param_a}, {param_b}."})
    if param_a == param_b:
        return json.dumps({"error": "Improving and worsening parameters must be different."})

    matrix = _load_matrix()
    key = f"{param_a}_{param_b}"
    principles = matrix["matrix"].get(key, [])

    param_names = {p["id"]: p["name"] for p in matrix["parameters"]}
    return json.dumps({
        "improving": {"id": param_a, "name": param_names.get(param_a, "Unknown")},
        "worsening": {"id": param_b, "name": param_names.get(param_b, "Unknown")},
        "principles": principles,
        "cell_key": key,
    })


@mcp.tool()
async def list_parameters() -> str:
    """List all 39 TRIZ engineering parameters with IDs and descriptions."""
    matrix = _load_matrix()
    return json.dumps({"parameters": matrix["parameters"]})


@mcp.tool()
async def get_separation_principles(contradiction: str) -> str:
    """Get separation principle recommendations for a physical contradiction.

    Physical contradictions require a parameter to have opposite values simultaneously.
    Resolution uses four separation approaches.
    """
    approaches = [
        {
            "type": "time",
            "description": "Separate contradictory requirements in time. "
            "The system satisfies one requirement at one time and the opposite at another.",
            "examples": [
                "Retractable landing gear: extended during takeoff/landing, retracted during flight",
                "Feature flags: enabled during testing, disabled in production",
            ],
        },
        {
            "type": "space",
            "description": "Separate contradictory requirements in space. "
            "Different parts of the system satisfy different requirements.",
            "examples": [
                "Aircraft wing: thick at root for strength, thin at tip for aerodynamics",
                "Microservices: each service optimized for its specific requirement",
            ],
        },
        {
            "type": "condition",
            "description": "Separate contradictory requirements upon condition. "
            "The system behaves differently under different conditions.",
            "examples": [
                "Shape-memory alloy: rigid below transition temperature, flexible above",
                "Adaptive bitrate: high quality on fast connections, lower on slow",
            ],
        },
        {
            "type": "system_level",
            "description": "Separate contradictory requirements between system levels. "
            "The whole system has one property, parts have the opposite.",
            "examples": [
                "Chain: flexible as whole, rigid individual links",
                "Distributed system: eventually consistent globally, strongly consistent locally",
            ],
        },
    ]

    contradiction_lower = contradiction.lower()
    scored = []
    for approach in approaches:
        relevance = 0.5
        if approach["type"] == "time" and any(
            w in contradiction_lower for w in ("when", "during", "before", "after", "phase")
        ):
            relevance = 0.9
        elif approach["type"] == "space" and any(
            w in contradiction_lower for w in ("part", "section", "area", "region", "local")
        ):
            relevance = 0.9
        elif approach["type"] == "condition" and any(
            w in contradiction_lower for w in ("if", "when", "condition", "mode", "state")
        ):
            relevance = 0.85
        elif approach["type"] == "system_level" and any(
            w in contradiction_lower for w in ("whole", "system", "component", "level", "global")
        ):
            relevance = 0.85
        scored.append({**approach, "relevance": relevance})

    scored.sort(key=lambda x: x["relevance"], reverse=True)
    return json.dumps({
        "contradiction": contradiction,
        "approaches": scored,
    })


@mcp.tool()
async def score_solution(problem: str, solution: str) -> str:
    """Score a solution against the Ideal Final Result (IFR) on a 0-4 scale.

    IFR criteria:
    (i)   No additional components needed
    (ii)  No additional cost
    (iii) No side-effects introduced
    (iv)  System solves itself
    """
    sol_lower = solution.lower()

    criteria = {
        "no_additional_components": not any(
            w in sol_lower for w in ("add new", "additional component", "extra layer", "new service")
        ),
        "no_additional_cost": not any(
            w in sol_lower for w in ("expensive", "costly", "budget", "purchase", "buy")
        ),
        "no_side_effects": not any(
            w in sol_lower for w in ("trade-off", "tradeoff", "downside", "drawback", "side effect")
        ),
        "self_solving": any(
            w in sol_lower
            for w in ("self-", "automatic", "inherent", "eliminat", "without intervention")
        ),
    }

    score = sum(1 for v in criteria.values() if v)
    met = [k for k, v in criteria.items() if v]
    unmet = [k for k, v in criteria.items() if not v]

    labels = {0: "No IFR progress", 1: "Minimal IFR", 2: "Partial IFR", 3: "Near-IFR", 4: "Full IFR"}

    return json.dumps({
        "ifr_score": score,
        "ifr_label": labels[score],
        "criteria_met": met,
        "criteria_unmet": unmet,
        "rationale": f"Solution satisfies {score}/4 IFR criteria: {', '.join(met) if met else 'none'}.",
    })


@mcp.tool()
async def log_session_entry(entry: dict) -> str:
    """Append a TRIZ analysis entry to the session innovation ledger (.triz/session.jsonl)."""
    session_dir = os.environ.get("TRIZ_SESSION_DIR", ".")
    log_dir = Path(session_dir) / ".triz"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "session.jsonl"

    with open(log_path, "a") as f:
        f.write(json.dumps(entry) + "\n")

    return json.dumps({"logged": True, "path": str(log_path)})


if __name__ == "__main__":
    mcp.run(transport="stdio")
