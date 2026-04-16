#!/usr/bin/env python3
"""Build TRIZ Arena dashboard data and write docs/index.html (stdlib only)."""

from __future__ import annotations

import json
import math
import random
import re
from datetime import datetime, timezone
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "triz-engine" / "results"
PROBLEMS = ROOT / "triz-engine" / "benchmark" / "problems"
DOCS = ROOT / "docs"
OUTPUT_HTML = DOCS / "index.html"

PARTICIPANTS = ("triz-engine", "vanilla-claude")
RAW_OUTPUT_MAX = 3000
BOOTSTRAP_ITERS = 1000
BOOTSTRAP_SEED = 42

TEMPLATE_PATH = Path(__file__).resolve().parent / "dashboard_template.html"


def load_html_template() -> str:
    if TEMPLATE_PATH.exists():
        return TEMPLATE_PATH.read_text(encoding="utf-8")
    return (
        '<!DOCTYPE html><html><head><title>TRIZ Arena</title></head>'
        '<body><script>const ARENA_DATA = __DASHBOARD_DATA__;</script>'
        '<div id="app">Loading...</div></body></html>'
    )


def expected_score(rating_a: float, rating_b: float) -> float:
    """Bradley-Terry expected score for player A against player B."""
    return 1.0 / (1.0 + math.pow(10.0, (rating_b - rating_a) / 400.0))


def update_ratings(
    rating_a: float, rating_b: float, score_a: float, k: float = 32
) -> tuple[float, float]:
    """Update ratings after a single match (score_a: 1 win, 0 loss, 0.5 draw)."""
    ea = expected_score(rating_a, rating_b)
    eb = 1.0 - ea
    score_b = 1.0 - score_a
    new_a = rating_a + k * (score_a - ea)
    new_b = rating_b + k * (score_b - eb)
    return new_a, new_b


@dataclass
class EloCalculator:
    """ELO ratings for multiple participants (matches triz-engine/benchmark/elo.py)."""

    participants: list[str]
    initial_rating: float = 1000.0
    k_initial: float = 32.0
    k_subsequent: float = 16.0
    ratings: dict[str, float] = field(default_factory=dict)
    match_counts: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.ratings:
            self.ratings = {p: self.initial_rating for p in self.participants}
        if not self.match_counts:
            self.match_counts = {p: 0 for p in self.participants}

    def _k_for(self, participant: str) -> float:
        if self.match_counts[participant] == 0:
            return self.k_initial
        return self.k_subsequent

    def record_match(
        self, participant_a: str, participant_b: str, score_a: float
    ) -> None:
        k = max(self._k_for(participant_a), self._k_for(participant_b))
        old_a = self.ratings[participant_a]
        old_b = self.ratings[participant_b]
        new_a, new_b = update_ratings(old_a, old_b, score_a, k)
        self.ratings[participant_a] = new_a
        self.ratings[participant_b] = new_b
        self.match_counts[participant_a] += 1
        self.match_counts[participant_b] += 1


def bootstrap_confidence_intervals(
    participants: list[str],
    results: list[dict[str, Any]],
    n_bootstrap: int = BOOTSTRAP_ITERS,
    confidence: float = 0.95,
) -> dict[str, dict[str, float]]:
    """Bootstrap lower/upper ELO per participant (same structure as benchmark/elo.py)."""
    all_ratings: dict[str, list[float]] = {p: [] for p in participants}
    rng_state = random.getstate()
    random.seed(BOOTSTRAP_SEED)
    try:
        for _ in range(n_bootstrap):
            sample = random.choices(results, k=len(results))
            calc = EloCalculator(participants=list(participants))
            for match in sample:
                calc.record_match(
                    match["winner"], match["loser"], match["score_a"]
                )
            for p in participants:
                all_ratings[p].append(calc.ratings[p])
    finally:
        random.setstate(rng_state)

    alpha = (1 - confidence) / 2
    ci: dict[str, dict[str, float]] = {}
    for p in participants:
        sorted_ratings = sorted(all_ratings[p])
        n = len(sorted_ratings)
        ci[p] = {
            "lower": sorted_ratings[int(alpha * n)],
            "upper": sorted_ratings[int((1 - alpha) * n)],
        }
    return ci


def sort_problem_id(pid: str) -> tuple[int, int | str]:
    """Stable ordering: TB, then EXT-TB, then MG, then CO, then fallback."""
    m = re.match(r"^TB-(\d+)$", pid)
    if m:
        return (0, int(m.group(1)))
    m = re.match(r"^EXT-TB-(\d+)$", pid)
    if m:
        return (1, int(m.group(1)))
    m = re.match(r"^MG-(\d+)$", pid)
    if m:
        return (2, int(m.group(1)))
    m = re.match(r"^CO-(\d+)$", pid)
    if m:
        return (3, int(m.group(1)))
    return (4, pid)


def truncate_str(value: Any, max_len: int = RAW_OUTPUT_MAX) -> str:
    if value is None:
        return ""
    s = value if isinstance(value, str) else str(value)
    if len(s) <= max_len:
        return s
    return s[:max_len]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_pattern(directory: Path, pattern: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted(directory.glob(pattern)):
        data = load_json(path)
        pid = data.get("problem_id") or path.stem
        out[str(pid)] = data
    return out


def load_problem_definitions() -> dict[str, dict[str, Any]]:
    defs: dict[str, dict[str, Any]] = {}
    for path in PROBLEMS.glob("TB-*.json"):
        data = load_json(path)
        pid = str(data.get("id") or path.stem)
        defs[pid] = data
    return defs


def final_score_from_result(data: dict[str, Any]) -> float | None:
    scores = data.get("scores")
    if isinstance(scores, dict) and scores.get("final_score") is not None:
        return float(scores["final_score"])
    if data.get("final_score") is not None:
        return float(data["final_score"])
    return None


def external_derived_score(data: dict[str, Any]) -> float:
    cs = data.get("contradiction_score") or {}
    ps = data.get("principle_score") or {}
    type_correct = bool(cs.get("type_correct"))
    params_exact = bool(cs.get("params_exact"))
    params_partial = bool(cs.get("params_partial"))
    ct_score = (20 if type_correct else 0) + (
        30 if params_exact else (15 if params_partial else 0)
    )
    f1 = float(ps.get("f1") or 0.0)
    f1_score = f1 * 50.0
    return ct_score + f1_score


def build_internal_side(data: dict[str, Any]) -> dict[str, Any]:
    scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    return {
        "final_score": final_score_from_result(data),
        "scores": scores,
        "submission": data.get("submission") or {},
        "raw_output": truncate_str(data.get("raw_output")),
    }


def build_external_side(data: dict[str, Any]) -> dict[str, Any]:
    cs = data.get("contradiction_score") or {}
    ps = data.get("principle_score") or {}
    return {
        "f1": float(ps.get("f1") or 0.0),
        "params_exact": bool(cs.get("params_exact")),
        "principles_predicted": list(ps.get("predicted") or []),
        "principles_gt": list(ps.get("ground_truth") or []),
    }


def run_elo_tournament(
    participants: list[str],
    problem_ids: list[str],
    scores: dict[tuple[str, str], float],
) -> tuple[dict[str, float], dict[str, dict[str, float]], int, list[dict[str, Any]], int, int, int]:
    """Pairwise matches per problem; returns ratings, CI, match count, bootstrap input, W/L/T."""
    calc = EloCalculator(participants=participants)
    match_results: list[dict[str, Any]] = []
    skipped_pairs = 0
    triz_wins = vanilla_wins = ties = 0

    for pid in problem_ids:
        for i, p_a in enumerate(participants):
            for p_b in participants[i + 1 :]:
                key_a = (p_a, pid)
                key_b = (p_b, pid)
                if key_a not in scores or key_b not in scores:
                    skipped_pairs += 1
                    continue
                s_a = scores[key_a]
                s_b = scores[key_b]
                if s_a > s_b:
                    outcome = 1.0
                elif s_a < s_b:
                    outcome = 0.0
                else:
                    outcome = 0.5

                calc.record_match(p_a, p_b, outcome)
                match_results.append(
                    {
                        "winner": p_a,
                        "loser": p_b,
                        "score_a": outcome,
                        "problem": pid,
                        "scores": {"a": s_a, "b": s_b},
                    }
                )

                if p_a == "triz-engine" and p_b == "vanilla-claude":
                    if outcome == 1.0:
                        triz_wins += 1
                    elif outcome == 0.0:
                        vanilla_wins += 1
                    else:
                        ties += 1

    ci = bootstrap_confidence_intervals(participants, match_results)
    return (
        dict(calc.ratings),
        ci,
        len(match_results),
        match_results,
        triz_wins,
        vanilla_wins,
        ties,
    )


def json_for_script_embed(data: Any) -> str:
    """Serialize to JSON and escape '<' so </script> cannot break the HTML script tag."""
    s = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return s.replace("<", "\\u003c")


def build_dashboard_data() -> dict[str, Any]:
    problem_defs = load_problem_definitions()

    triz_tb = load_pattern(RESULTS / "triz-engine", "TB-*.json")
    vanilla_tb = load_pattern(RESULTS / "vanilla-claude", "TB-*.json")

    internal: list[dict[str, Any]] = []
    internal_ids = sorted(
        set(triz_tb) & set(vanilla_tb), key=sort_problem_id
    )
    for pid in internal_ids:
        t = triz_tb[pid]
        v = vanilla_tb[pid]
        pdef = problem_defs.get(pid, {})
        internal.append(
            {
                "problem_id": pid,
                "domain": pdef.get("domain") or t.get("domain") or "",
                "title": pdef.get("title") or t.get("problem_title") or "",
                "problem_statement": pdef.get("problem_statement") or "",
                "ground_truth": pdef.get("ground_truth") or {},
                "triz": build_internal_side(t),
                "vanilla": build_internal_side(v),
            }
        )

    ext_triz = load_pattern(
        RESULTS / "external-trizbench" / "triz-engine", "EXT-TB-*.json"
    )
    ext_vanilla = load_pattern(
        RESULTS / "external-trizbench" / "vanilla-claude", "EXT-TB-*.json"
    )
    external_trizbench: list[dict[str, Any]] = []
    ext_ids = sorted(set(ext_triz) & set(ext_vanilla), key=sort_problem_id)
    for pid in ext_ids:
        t = ext_triz[pid]
        v = ext_vanilla[pid]
        external_trizbench.append(
            {
                "problem_id": pid,
                "patent_id": str(t.get("patent_id") or v.get("patent_id") or ""),
                "triz": build_external_side(t),
                "vanilla": build_external_side(v),
            }
        )

    macgyver: list[dict[str, Any]] = []
    for path in sorted((RESULTS / "external-macgyver").glob("MG-*.json")):
        data = load_json(path)
        pid = str(data.get("problem_id") or path.stem)
        triz_block = data.get("triz") or {}
        van_block = data.get("vanilla") or {}
        macgyver.append(
            {
                "problem_id": pid,
                "triz_score": float(triz_block.get("score") or 0.0),
                "vanilla_score": float(van_block.get("score") or 0.0),
                "triz_level": str(triz_block.get("level") or ""),
                "vanilla_level": str(van_block.get("level") or ""),
                "triz_output": truncate_str(data.get("triz_output")),
                "vanilla_output": truncate_str(data.get("vanilla_output")),
                "reference": truncate_str(data.get("reference")),
            }
        )
    macgyver.sort(key=lambda r: sort_problem_id(r["problem_id"]))

    cresowlve: list[dict[str, Any]] = []
    for path in sorted((RESULTS / "external-cresowlve").glob("CO-*.json")):
        data = load_json(path)
        pid = str(data.get("problem_id") or path.stem)
        cresowlve.append(
            {
                "problem_id": pid,
                "difficulty": int(data.get("difficulty") or 0),
                "question": str(data.get("question") or ""),
                "correct_answer": str(data.get("correct_answer") or ""),
                "triz_correct": bool(data.get("triz_correct")),
                "vanilla_correct": bool(data.get("vanilla_correct")),
                "triz_answer": truncate_str(data.get("triz_answer")),
                "vanilla_answer": truncate_str(data.get("vanilla_answer")),
            }
        )
    cresowlve.sort(key=lambda r: sort_problem_id(r["problem_id"]))

    scores: dict[tuple[str, str], float] = {}
    for pid in internal_ids:
        st = final_score_from_result(triz_tb[pid])
        sv = final_score_from_result(vanilla_tb[pid])
        if st is not None:
            scores[("triz-engine", pid)] = st
        if sv is not None:
            scores[("vanilla-claude", pid)] = sv

    for pid in ext_ids:
        scores[("triz-engine", pid)] = external_derived_score(ext_triz[pid])
        scores[("vanilla-claude", pid)] = external_derived_score(ext_vanilla[pid])

    for row in macgyver:
        pid = row["problem_id"]
        scores[("triz-engine", pid)] = float(row["triz_score"])
        scores[("vanilla-claude", pid)] = float(row["vanilla_score"])

    for row in cresowlve:
        pid = row["problem_id"]
        scores[("triz-engine", pid)] = 100.0 if row["triz_correct"] else 0.0
        scores[("vanilla-claude", pid)] = 100.0 if row["vanilla_correct"] else 0.0

    ordered_pids = sorted(
        [
            pid
            for pid in {k[1] for k in scores}
            if ("triz-engine", pid) in scores
            and ("vanilla-claude", pid) in scores
        ],
        key=sort_problem_id,
    )

    ratings, elo_ci, match_count, _mr, triz_wins, vanilla_wins, ties = (
        run_elo_tournament(list(PARTICIPANTS), ordered_pids, scores)
    )

    triz_scores_int = [
        float(x)
        for x in (final_score_from_result(triz_tb[p]) for p in internal_ids)
        if x is not None
    ]
    van_scores_int = [
        float(x)
        for x in (final_score_from_result(vanilla_tb[p]) for p in internal_ids)
        if x is not None
    ]

    ext_f1_triz = [row["triz"]["f1"] for row in external_trizbench]
    ext_f1_van = [row["vanilla"]["f1"] for row in external_trizbench]

    def mean(vals: list[float]) -> float | None:
        return sum(vals) / len(vals) if vals else None

    summary = {
        "total_problems": len(internal)
        + len(external_trizbench)
        + len(macgyver)
        + len(cresowlve),
        "triz_mean": mean(triz_scores_int),
        "vanilla_mean": mean(van_scores_int),
        "ext_triz_f1": mean(ext_f1_triz),
        "ext_vanilla_f1": mean(ext_f1_van),
        "mg_triz_mean": mean([row["triz_score"] for row in macgyver]),
        "mg_vanilla_mean": mean([row["vanilla_score"] for row in macgyver]),
        "triz_wins": triz_wins,
        "vanilla_wins": vanilla_wins,
        "ties": ties,
    }

    generated_at = datetime.now(timezone.utc).isoformat()

    return {
        "generated_at": generated_at,
        "elo": {p: ratings[p] for p in PARTICIPANTS},
        "elo_ci": {p: elo_ci[p] for p in PARTICIPANTS},
        "match_count": match_count,
        "internal": internal,
        "external_trizbench": external_trizbench,
        "macgyver": macgyver,
        "cresowlve": cresowlve,
        "summary": summary,
    }


def write_dashboard_html(dashboard_data: dict[str, Any]) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    payload = json_for_script_embed(dashboard_data)
    template = load_html_template()
    html = template.replace("__DASHBOARD_DATA__", payload)
    OUTPUT_HTML.write_text(html, encoding="utf-8")


def main() -> None:
    dashboard_data = build_dashboard_data()
    write_dashboard_html(dashboard_data)

    internal_n = len(dashboard_data["internal"])
    ext_n = len(dashboard_data["external_trizbench"])
    mg_n = len(dashboard_data["macgyver"])
    co_n = len(dashboard_data["cresowlve"])

    print("TRIZ Arena dashboard build")
    print(f"  Repo root: {ROOT}")
    print(
        f"  Loaded internal TRIZBENCH pairs: {internal_n}, "
        f"external TRIZBENCH pairs: {ext_n}, "
        f"MacGyver: {mg_n}, CresOWLve: {co_n}"
    )
    print(f"  ELO matches: {dashboard_data['match_count']}")
    for p in PARTICIPANTS:
        r = dashboard_data["elo"][p]
        lo = dashboard_data["elo_ci"][p]["lower"]
        hi = dashboard_data["elo_ci"][p]["upper"]
        print(f"  ELO {p}: {r:.2f} (95% bootstrap CI {lo:.2f}–{hi:.2f})")
    print(f"  W/L/T (triz / vanilla / ties): "
          f"{dashboard_data['summary']['triz_wins']} / "
          f"{dashboard_data['summary']['vanilla_wins']} / "
          f"{dashboard_data['summary']['ties']}")
    print(f"  Wrote {OUTPUT_HTML}")


if __name__ == "__main__":
    main()
