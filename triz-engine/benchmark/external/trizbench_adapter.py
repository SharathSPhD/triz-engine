"""Adapter for the published TRIZBENCH dataset (ACL ARR 2026).

Converts patent_parameters.csv rows into our problem JSON format and
evaluates using the paper's metrics: contradiction prediction accuracy
and principle prediction F1.

Source: https://anonymous.4open.science/r/trizbench-E519
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "benchmark" / "external" / "data"
RESULTS_DIR = ROOT / "results" / "external-trizbench"


def download_dataset() -> Path:
    """Download patent_parameters.csv from the published TRIZBENCH repo."""
    import urllib.request

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = DATA_DIR / "patent_parameters.csv"
    if target.exists():
        return target

    url = "https://anonymous.4open.science/api/repo/trizbench-E519/file/patent_parameters.csv"
    print(f"Downloading TRIZBENCH dataset from {url}...", file=sys.stderr)
    try:
        urllib.request.urlretrieve(url, target)
        print(f"Downloaded to {target}", file=sys.stderr)
    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)
        print("Please manually download patent_parameters.csv and place it in:", file=sys.stderr)
        print(f"  {target}", file=sys.stderr)
        raise

    return target


def load_problems(csv_path: Path | None = None, limit: int = 20) -> list[dict]:
    """Load problems from patent_parameters.csv.

    Returns list of dicts with fields:
      id, domain, title, problem_statement, ground_truth
    """
    if csv_path is None:
        csv_path = DATA_DIR / "patent_parameters.csv"

    if not csv_path.exists():
        csv_path = download_dataset()

    problems = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= limit:
                break

            improving = row.get("improving_parameter", row.get("param_a", ""))
            worsening = row.get("worsening_parameter", row.get("param_b", ""))
            principles_raw = row.get("principles", row.get("target_principles", ""))

            try:
                principles = [int(p.strip()) for p in principles_raw.split(",") if p.strip()]
            except ValueError:
                principles = []

            param_a_id = _parse_param_id(row.get("param_a_id", row.get("triz_param_a", "")))
            param_b_id = _parse_param_id(row.get("param_b_id", row.get("triz_param_b", "")))

            problem_text = row.get("problem_statement", row.get("description", ""))
            if not problem_text:
                problem_text = (
                    f"A system has a technical contradiction: improving "
                    f"{improving} worsens {worsening}. "
                    f"Find a solution that resolves this contradiction."
                )

            problems.append({
                "id": f"EXT-TB-{i+1:03d}",
                "domain": row.get("domain", "Patent"),
                "title": f"{improving} vs {worsening}",
                "problem_statement": problem_text,
                "ground_truth": {
                    "contradiction_type": "technical",
                    "parameter_a": improving,
                    "parameter_b": worsening,
                    "triz_param_a": param_a_id,
                    "triz_param_b": param_b_id,
                    "target_principles": principles,
                    "ifr_baseline": "",
                },
            })

    return problems


def _parse_param_id(val: str) -> int | None:
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def score_contradiction_prediction(submission: dict, ground_truth: dict) -> dict:
    """Score using published TRIZBENCH metrics."""
    ct_match = submission.get("contradiction_type") == ground_truth.get("contradiction_type")

    sub_params = {submission.get("triz_param_a"), submission.get("triz_param_b")}
    gt_params = {ground_truth.get("triz_param_a"), ground_truth.get("triz_param_b")}
    sub_params.discard(None)
    gt_params.discard(None)

    param_match = sub_params == gt_params and len(sub_params) == 2
    param_partial = bool(sub_params & gt_params)

    return {
        "type_correct": ct_match,
        "params_exact": param_match,
        "params_partial": param_partial,
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

    return {"precision": precision, "recall": recall, "f1": f1}


def run_external_trizbench(
    participant_fn,
    problems: list[dict] | None = None,
    limit: int = 20,
) -> dict:
    """Run a participant function on TRIZBENCH problems and return aggregate metrics.

    participant_fn: callable(problem_statement: str) -> str (raw model output)
    """
    from benchmark.runner import parse_submission

    if problems is None:
        problems = load_problems(limit=limit)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    ct_correct = 0
    param_exact = 0
    principle_f1_sum = 0.0
    total = 0

    for problem in problems:
        try:
            raw = participant_fn(problem["problem_statement"])
            submission = parse_submission(raw)
        except Exception as e:
            print(f"  {problem['id']}: FAILED ({e})", file=sys.stderr)
            continue

        total += 1
        gt = problem["ground_truth"]
        ct_score = score_contradiction_prediction(submission, gt)
        ps_score = score_principle_prediction(
            submission.get("principles_applied", []),
            gt.get("target_principles", []),
        )

        if ct_score["type_correct"]:
            ct_correct += 1
        if ct_score["params_exact"]:
            param_exact += 1
        principle_f1_sum += ps_score["f1"]

        result_path = RESULTS_DIR / f"{problem['id']}.json"
        result_path.write_text(json.dumps({
            "problem_id": problem["id"],
            "submission": submission,
            "contradiction_score": ct_score,
            "principle_score": ps_score,
        }, indent=2))

    return {
        "total": total,
        "contradiction_type_accuracy": ct_correct / total if total else 0,
        "parameter_exact_accuracy": param_exact / total if total else 0,
        "principle_f1_mean": principle_f1_sum / total if total else 0,
    }


if __name__ == "__main__":
    problems = load_problems(limit=5)
    print(f"Loaded {len(problems)} problems")
    for p in problems[:3]:
        print(f"  {p['id']}: {p['title']}")
        print(f"    GT params: {p['ground_truth']['triz_param_a']} -> {p['ground_truth']['triz_param_b']}")
        print(f"    Principles: {p['ground_truth']['target_principles']}")
