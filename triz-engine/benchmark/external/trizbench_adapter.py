"""Adapter for the published TRIZBENCH dataset (ACL ARR 2026).

Evaluates parameter prediction accuracy and principle prediction F1
using real patent contradiction data (236 U.S. patents).

Dataset format: patent_id, plus (improving param ID), minus (worsening param ID)
Ground-truth principles derived from the TRIZ contradiction matrix for
classic-range (1–39) parameters.

Source: https://anonymous.4open.science/r/trizbench-E519
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "benchmark" / "external" / "data"
TRIZBENCH_CSV = ROOT.parent / "trizbench" / "patent_parameters.csv"
MATRIX_PATH = ROOT / "data" / "triz-matrix.json"
RESULTS_DIR = ROOT / "results" / "external-trizbench"


def _load_matrix() -> tuple[dict[str, list[int]], dict[int, str]]:
    """Load TRIZ contradiction matrix and parameter names."""
    with open(MATRIX_PATH) as f:
        data = json.load(f)
    params = {p["id"]: p["name"] for p in data["parameters"]}
    return data["matrix"], params


def load_problems(csv_path: Path | None = None, limit: int = 20) -> list[dict]:
    """Load problems from the real TRIZBENCH patent_parameters.csv.

    Returns list of dicts with fields:
      id, domain, title, problem_statement, ground_truth
    """
    if csv_path is None:
        csv_path = TRIZBENCH_CSV

    if not csv_path.exists():
        raise FileNotFoundError(
            f"TRIZBENCH dataset not found at {csv_path}. "
            f"Please download patent_parameters.csv from the TRIZBENCH repo."
        )

    matrix, param_names = _load_matrix()

    classic_rows = []
    extended_rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row["plus"]) <= 39 and int(row["minus"]) <= 39:
                classic_rows.append(row)
            else:
                extended_rows.append(row)

    ordered = classic_rows + extended_rows

    problems = []
    for row in ordered:
        if len(problems) >= limit:
            break

        plus_id = int(row["plus"])
        minus_id = int(row["minus"])
        patent_id = row["patent_id"]

        improving = param_names.get(plus_id, f"Parameter {plus_id}")
        worsening = param_names.get(minus_id, f"Parameter {minus_id}")

        matrix_key = f"{plus_id}_{minus_id}"
        gt_principles = matrix.get(matrix_key, [])

        problem_text = (
            f"Patent {patent_id} describes a technical system with a "
            f"contradiction: improving '{improving}' (TRIZ parameter {plus_id}) "
            f"worsens '{worsening}' (TRIZ parameter {minus_id}). "
            f"Analyze this contradiction using TRIZ methodology. "
            f"Identify the contradiction type, map the improving and worsening "
            f"parameters to their TRIZ parameter IDs, and recommend inventive "
            f"principles to resolve the contradiction."
        )

        problems.append({
            "id": f"EXT-TB-{len(problems)+1:03d}",
            "patent_id": patent_id,
            "domain": "Patent",
            "title": f"{improving} vs {worsening}",
            "problem_statement": problem_text,
            "ground_truth": {
                "contradiction_type": "technical",
                "triz_param_a": plus_id,
                "triz_param_b": minus_id,
                "parameter_a_name": improving,
                "parameter_b_name": worsening,
                "target_principles": gt_principles,
                "has_matrix_entry": len(gt_principles) > 0,
            },
        })

    return problems


def score_contradiction_prediction(submission: dict, ground_truth: dict) -> dict:
    """Score parameter prediction accuracy."""
    sub_a = submission.get("triz_param_a")
    sub_b = submission.get("triz_param_b")
    gt_a = ground_truth["triz_param_a"]
    gt_b = ground_truth["triz_param_b"]

    sub_params = {sub_a, sub_b} - {None}
    gt_params = {gt_a, gt_b}

    params_exact = sub_params == gt_params and len(sub_params) == 2
    params_partial = bool(sub_params & gt_params)

    ct_match = submission.get("contradiction_type") == ground_truth.get("contradiction_type")

    return {
        "type_correct": ct_match,
        "params_exact": params_exact,
        "params_partial": params_partial,
        "predicted_params": sorted(sub_params),
        "ground_truth_params": sorted(gt_params),
    }


def score_principle_prediction(submitted: list[int], target: list[int]) -> dict:
    """Score principle prediction using precision, recall, F1."""
    s_set = set(submitted)
    t_set = set(target)

    if not s_set and not t_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not s_set or not t_set:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    tp = len(s_set & t_set)
    precision = tp / len(s_set) if s_set else 0.0
    recall = tp / len(t_set) if t_set else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "overlap": sorted(s_set & t_set),
        "predicted": sorted(s_set),
        "ground_truth": sorted(t_set),
    }


def run_external_trizbench(
    participant_fn,
    problems: list[dict] | None = None,
    limit: int = 20,
    participant_name: str = "unknown",
) -> dict:
    """Run a participant function on TRIZBENCH problems and return aggregate metrics.

    participant_fn: callable(problem_statement: str) -> str (raw model output)
    participant_name: used to namespace result artifacts on disk.
    """
    from benchmark.runner import parse_submission, QuotaExhaustedError

    if problems is None:
        problems = load_problems(limit=limit)

    out_dir = RESULTS_DIR / participant_name
    out_dir.mkdir(parents=True, exist_ok=True)

    ct_correct = 0
    param_exact = 0
    param_partial = 0
    principle_f1_sum = 0.0
    total = 0
    failures = 0
    per_problem = []

    for problem in problems:
        gt = problem["ground_truth"]
        try:
            raw = participant_fn(problem["problem_statement"])
            submission = parse_submission(raw)
        except QuotaExhaustedError:
            print(f"  QUOTA EXHAUSTED — stopping benchmark.", file=sys.stderr)
            raise
        except Exception as e:
            print(f"  {problem['id']}: FAILED ({e})", file=sys.stderr)
            failures += 1
            continue

        total += 1
        ct_score = score_contradiction_prediction(submission, gt)
        ps_score = score_principle_prediction(
            submission.get("principles_applied", []),
            gt.get("target_principles", []),
        )

        if ct_score["type_correct"]:
            ct_correct += 1
        if ct_score["params_exact"]:
            param_exact += 1
        if ct_score["params_partial"]:
            param_partial += 1
        principle_f1_sum += ps_score["f1"]

        result_entry = {
            "problem_id": problem["id"],
            "participant": participant_name,
            "patent_id": problem.get("patent_id"),
            "submission": submission,
            "contradiction_score": ct_score,
            "principle_score": ps_score,
        }
        per_problem.append(result_entry)

        result_path = out_dir / f"{problem['id']}.json"
        result_path.write_text(json.dumps(result_entry, indent=2))

        status = "EXACT" if ct_score["params_exact"] else ("PARTIAL" if ct_score["params_partial"] else "MISS")
        f1 = ps_score["f1"]
        print(
            f"  {problem['id']} ({problem['patent_id']}): params={status} "
            f"principle_f1={f1:.2f}",
            file=sys.stderr,
        )

    return {
        "total": total,
        "failures": failures,
        "contradiction_type_accuracy": ct_correct / total if total else 0,
        "parameter_exact_accuracy": param_exact / total if total else 0,
        "parameter_partial_accuracy": param_partial / total if total else 0,
        "principle_f1_mean": principle_f1_sum / total if total else 0,
        "per_problem": per_problem,
    }


if __name__ == "__main__":
    problems = load_problems(limit=5)
    print(f"Loaded {len(problems)} problems")
    for p in problems[:5]:
        gt = p["ground_truth"]
        print(f"  {p['id']} ({p['patent_id']}): {p['title']}")
        print(f"    Params: {gt['triz_param_a']} -> {gt['triz_param_b']}")
        print(f"    GT Principles: {gt['target_principles']}")
        print(f"    Has matrix entry: {gt['has_matrix_entry']}")
