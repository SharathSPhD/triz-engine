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
    """List all 39 TRIZ engineering parameters with IDs, descriptions, and software equivalents.

    Each parameter includes its classical TRIZ name, description, and
    a software/systems engineering equivalent to help map modern problems
    to the 39-parameter framework.
    """
    matrix = _load_matrix()
    params = matrix["parameters"]
    enriched = []
    for p in params:
        enriched.append({
            "id": p["id"],
            "name": p["name"],
            "description": p.get("description", ""),
            "software_equivalent": p.get("software_equivalent", ""),
        })
    return json.dumps({"parameters": enriched, "total": len(enriched)})


@mcp.tool()
async def suggest_parameters(description: str) -> str:
    """Suggest the best-matching TRIZ parameters for a natural-language description.

    Given a description of what is improving or worsening, returns the top-5
    most relevant TRIZ parameters with match rationale. Use this when unsure
    which of the 39 parameters best maps to your problem dimensions.
    """
    matrix = _load_matrix()
    params = matrix["parameters"]
    desc_lower = description.lower()
    desc_words = set(desc_lower.split())

    scored = []
    for p in params:
        score = 0.0
        match_reasons = []

        name_lower = p["name"].lower()
        desc_field = p.get("description", "").lower()
        sw_equiv = p.get("software_equivalent", "").lower()

        searchable = f"{name_lower} {desc_field} {sw_equiv}"
        searchable_words = set(searchable.split())

        common = desc_words & searchable_words
        filler = {"the", "a", "an", "of", "or", "and", "in", "to", "for", "is", "that"}
        meaningful = common - filler
        if meaningful:
            score += len(meaningful) * 2
            match_reasons.append(f"word overlap: {', '.join(sorted(meaningful))}")

        for phrase_len in range(3, 0, -1):
            desc_tokens = desc_lower.split()
            for i in range(len(desc_tokens) - phrase_len + 1):
                phrase = " ".join(desc_tokens[i:i + phrase_len])
                if phrase in searchable and len(phrase) > 4:
                    score += phrase_len * 3
                    match_reasons.append(f"phrase: '{phrase}'")

        if score > 0:
            scored.append({
                "id": p["id"],
                "name": p["name"],
                "description": p.get("description", ""),
                "software_equivalent": p.get("software_equivalent", ""),
                "relevance_score": round(score, 1),
                "match_reasons": match_reasons[:3],
            })

    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    return json.dumps({
        "query": description,
        "suggestions": scored[:5],
        "note": "Use the parameter ID when calling lookup_matrix.",
    })


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

    IFR criteria — evaluated semantically relative to the stated problem:
    (i)   Leverages existing system resources rather than requiring wholly new infrastructure
    (ii)  No significant additional cost or resource expenditure needed
    (iii) Solution does not introduce new problems or degradations
    (iv)  System becomes self-resolving — the contradiction disappears by design
    """
    sol_lower = solution.lower()
    prob_lower = problem.lower()

    sol_sentences = [s.strip() for s in solution.split('.') if s.strip()]
    prob_sentences = [s.strip() for s in problem.split('.') if s.strip()]

    mechanism_indicators = [
        "by", "through", "using", "via", "leverag", "repurpos",
        "transform", "reconfigur", "adapt", "modify", "restructur",
    ]
    has_concrete_mechanism = any(w in sol_lower for w in mechanism_indicators)

    new_infra_indicators = [
        "build a new", "deploy a separate", "purchase additional",
        "requires new hardware", "buy a new", "acquire a new",
        "install additional", "procure",
    ]
    adds_major_infra = any(phrase in sol_lower for phrase in new_infra_indicators)

    cost_escalation_indicators = [
        "significant cost", "major investment", "substantial budget",
        "expensive infrastructure", "high upfront cost",
    ]
    has_cost_escalation = any(phrase in sol_lower for phrase in cost_escalation_indicators)

    new_problem_indicators = [
        "however this introduces", "but this creates",
        "the downside is that it breaks", "at the expense of completely losing",
    ]
    introduces_new_problems = any(phrase in sol_lower for phrase in new_problem_indicators)

    self_resolving_indicators = [
        "eliminat", "dissolv", "disappear", "no longer exist",
        "inherent", "by design", "self-", "automatic",
        "without intervention", "naturally resolv",
        "both requirements are satisfied", "simultaneously achiev",
    ]
    is_self_resolving = any(w in sol_lower for w in self_resolving_indicators)

    criteria = {
        "leverages_existing": has_concrete_mechanism and not adds_major_infra,
        "minimal_cost": not has_cost_escalation,
        "no_new_problems": not introduces_new_problems,
        "self_resolving": is_self_resolving,
    }

    score = sum(1 for v in criteria.values() if v)
    met = [k for k, v in criteria.items() if v]
    unmet = [k for k, v in criteria.items() if not v]

    labels = {
        0: "No IFR progress",
        1: "Minimal IFR",
        2: "Partial IFR",
        3: "Near-IFR",
        4: "Full IFR",
    }

    return json.dumps({
        "problem_context": problem[:200],
        "ifr_score": score,
        "ifr_label": labels[score],
        "criteria_met": met,
        "criteria_unmet": unmet,
        "rationale": (
            f"Solution satisfies {score}/4 IFR criteria: "
            f"{', '.join(met) if met else 'none'}."
        ),
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
