"""TRIZBENCH 5-dimension scorer.

Scoring dimensions and weights:
  CI  (Contradiction Identification) — 25%
  PS  (Principle Selection)          — 20%
  SN  (Solution Novelty)             — 20%
  CR  (Contradiction Resolution)     — 25%
  IFR (Ideal Final Result)           — 10%

SN and CR support LLM-as-judge scoring via Claude CLI (--print mode).
Single rubric prompt per dimension with classification + rationale.
Falls back to deterministic string-mapping when Claude CLI is unavailable.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess

logger = logging.getLogger(__name__)


WEIGHTS = {"ci": 0.25, "ps": 0.20, "sn": 0.20, "cr": 0.25, "ifr": 0.10}


CR_RUBRIC = {
    "eliminates": 100.0,
    "reduces": 60.0,
    "manages": 32.0,
    "fails": 0.0,
}

SN_RUBRIC = {
    "non_obvious": 100.0,
    "novel_combination": 60.0,
    "standard": 32.0,
    "restatement": 0.0,
}

CR_LEVELS = ["fails", "manages", "reduces", "eliminates"]
SN_LEVELS = ["restatement", "standard", "novel_combination", "non_obvious"]

CR_CALIBRATION = [
    {
        "problem": "A web cache must serve stale data during backend outages but also serve fresh data for real-time dashboards.",
        "solution": "Implement a dual-channel architecture where the cache automatically routes time-sensitive dashboard queries to a hot-standby backend while serving stale data for non-critical pages, eliminating the freshness vs availability contradiction.",
        "expected": "eliminates",
    },
    {
        "problem": "An API needs backward compatibility while adding new features.",
        "solution": "Version the API endpoints and maintain both v1 and v2 simultaneously, accepting the maintenance overhead as a trade-off.",
        "expected": "manages",
    },
    {
        "problem": "A search engine needs both high recall and high precision.",
        "solution": "Use a two-stage retrieval: a broad recall-oriented first pass followed by a precision-focused reranker, significantly reducing the precision-recall tension.",
        "expected": "reduces",
    },
]

SN_CALIBRATION = [
    {
        "problem": "IoT sensors need continuous data but have limited battery.",
        "solution": "Apply TRIZ Principle 19 (Periodic Action): transmit data only when values change beyond a threshold, making the sensor self-regulating and eliminating continuous transmission without losing information fidelity.",
        "expected": "non_obvious",
    },
    {
        "problem": "A database needs ACID transactions and horizontal scaling.",
        "solution": "Use a distributed database with eventual consistency for reads and strong consistency for writes.",
        "expected": "standard",
    },
    {
        "problem": "Authentication must be secure but also user-friendly.",
        "solution": "The system should be more secure and more user-friendly.",
        "expected": "restatement",
    },
]


def _claude_available() -> bool:
    return shutil.which("claude") is not None


def _call_claude_judge(prompt: str, budget: float = 0.20, retries: int = 2) -> str:
    """Invoke Claude Code CLI as LLM-as-judge using Sonnet for quality."""
    import time as _time

    cmd = [
        "claude", "-p", prompt,
        "--model", "sonnet",
        "--output-format", "json",
        "--max-budget-usd", str(budget),
        "--dangerously-skip-permissions",
    ]

    for attempt in range(retries + 1):
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=90,
            stdin=subprocess.DEVNULL,
        )
        stdout = result.stdout.strip()
        if result.returncode == 0 and stdout:
            try:
                envelope = json.loads(stdout)
                if envelope.get("is_error"):
                    error_text = envelope.get("result", "")
                    if "out of" in error_text.lower() and "usage" in error_text.lower():
                        raise RuntimeError(f"Claude quota exhausted: {error_text}")
                text = envelope.get("result", "")
                if text:
                    return text
            except json.JSONDecodeError:
                if "error" not in stdout.lower()[:30]:
                    return stdout
        if attempt < retries:
            _time.sleep(2 ** attempt)

    raise RuntimeError(
        f"Claude judge failed after {retries + 1} attempts: "
        f"rc={result.returncode} stdout={stdout[:200]}"
    )


def _extract_level(raw: str, valid_levels: list[str]) -> str | None:
    """Extract a classification level from judge output.

    Matches whole words to avoid substring collisions
    (e.g., 'novel_combination' should not match 'standard').
    """
    raw_lower = raw.lower()
    for level in reversed(valid_levels):
        pattern = r'\b' + re.escape(level) + r'\b'
        if re.search(pattern, raw_lower):
            return level
    return None


def _judge_cr(problem: str, solution: str, ground_truth: str) -> str:
    """Judge contradiction resolution quality with a single rubric prompt."""
    prompt = (
        "You are a TRIZ evaluation judge. Classify how well the SOLUTION "
        "resolves the stated contradiction in the PROBLEM.\n\n"
        f"PROBLEM:\n{problem}\n\n"
        f"GROUND TRUTH CONTRADICTION:\n{ground_truth}\n\n"
        f"SOLUTION:\n{solution}\n\n"
        "Classification rubric:\n"
        "- eliminates: The contradiction is fully eliminated — both requirements "
        "are simultaneously satisfied without any trade-off.\n"
        "- reduces: The contradiction is significantly reduced but a minor "
        "residual tension remains.\n"
        "- manages: The contradiction is managed through compromise, trade-off, "
        "or accepting degradation on one dimension.\n"
        "- fails: The solution does not meaningfully address the contradiction, "
        "or merely restates the problem.\n\n"
        "Reply in this exact format:\n"
        "CLASSIFICATION: <one of: eliminates, reduces, manages, fails>\n"
        "RATIONALE: <one sentence explaining why>"
    )
    raw = _call_claude_judge(prompt)
    level = _extract_level(raw, CR_LEVELS)
    if level is None:
        raise ValueError(f"Could not parse CR level from: {raw[:200]}")
    return level


def _judge_sn(problem: str, solution: str, ground_truth: str) -> str:
    """Judge solution novelty with a single rubric prompt."""
    prompt = (
        "You are a TRIZ evaluation judge. Classify the novelty and inventiveness "
        "of the SOLUTION relative to the PROBLEM.\n\n"
        f"PROBLEM:\n{problem}\n\n"
        f"GROUND TRUTH PRINCIPLES:\n{ground_truth}\n\n"
        f"SOLUTION:\n{solution}\n\n"
        "Classification rubric:\n"
        "- non_obvious: The solution applies TRIZ principles in a surprising, "
        "inventive way that a domain expert would not immediately think of.\n"
        "- novel_combination: The solution combines known techniques in a new "
        "or creative way, showing insight beyond standard practice.\n"
        "- standard: The solution uses a well-known, established approach for "
        "this type of problem — competent but not inventive.\n"
        "- restatement: The solution merely restates the problem, describes "
        "the obvious, or provides a vague aspiration without concrete mechanism.\n\n"
        "Reply in this exact format:\n"
        "CLASSIFICATION: <one of: non_obvious, novel_combination, standard, restatement>\n"
        "RATIONALE: <one sentence explaining why>"
    )
    raw = _call_claude_judge(prompt)
    level = _extract_level(raw, SN_LEVELS)
    if level is None:
        raise ValueError(f"Could not parse SN level from: {raw[:200]}")
    return level


def validate_judge_calibration(dimension: str = "both") -> dict:
    """Run calibration set and return agreement metrics.

    Returns dict with 'cr' and/or 'sn' keys, each containing
    'total', 'correct', 'accuracy', and per-sample results.
    """
    results = {}

    if dimension in ("both", "cr"):
        cr_results = []
        for cal in CR_CALIBRATION:
            try:
                predicted = _judge_cr(cal["problem"], cal["solution"], "")
                cr_results.append({
                    "expected": cal["expected"],
                    "predicted": predicted,
                    "correct": predicted == cal["expected"],
                })
            except Exception as e:
                cr_results.append({
                    "expected": cal["expected"],
                    "predicted": None,
                    "error": str(e),
                    "correct": False,
                })
        correct = sum(1 for r in cr_results if r["correct"])
        results["cr"] = {
            "total": len(cr_results),
            "correct": correct,
            "accuracy": correct / len(cr_results) if cr_results else 0,
            "details": cr_results,
        }

    if dimension in ("both", "sn"):
        sn_results = []
        for cal in SN_CALIBRATION:
            try:
                predicted = _judge_sn(cal["problem"], cal["solution"], "")
                sn_results.append({
                    "expected": cal["expected"],
                    "predicted": predicted,
                    "correct": predicted == cal["expected"],
                })
            except Exception as e:
                sn_results.append({
                    "expected": cal["expected"],
                    "predicted": None,
                    "error": str(e),
                    "correct": False,
                })
        correct = sum(1 for r in sn_results if r["correct"])
        results["sn"] = {
            "total": len(sn_results),
            "correct": correct,
            "accuracy": correct / len(sn_results) if sn_results else 0,
            "details": sn_results,
        }

    return results


def score_cr_llm(problem: str, solution: str, ground_truth: str) -> tuple[float, str]:
    """Score CR via LLM-as-judge with single rubric prompt.

    Returns (score, level). Falls back to deterministic if Claude unavailable.
    """
    if not _claude_available():
        logger.warning("Claude CLI not found, falling back to deterministic CR scoring")
        return CR_RUBRIC.get("manages", 32.0), "manages"

    try:
        level = _judge_cr(problem, solution, ground_truth)
        return CR_RUBRIC[level], level
    except Exception as e:
        logger.warning(f"LLM CR judge failed, falling back: {e}")
        return CR_RUBRIC.get("manages", 32.0), "manages"


def score_sn_llm(problem: str, solution: str, ground_truth: str) -> tuple[float, str]:
    """Score SN via LLM-as-judge with single rubric prompt.

    Returns (score, level). Falls back to deterministic if Claude unavailable.
    """
    if not _claude_available():
        logger.warning("Claude CLI not found, falling back to deterministic SN scoring")
        return SN_RUBRIC.get("standard", 32.0), "standard"

    try:
        level = _judge_sn(problem, solution, ground_truth)
        return SN_RUBRIC[level], level
    except Exception as e:
        logger.warning(f"LLM SN judge failed, falling back: {e}")
        return SN_RUBRIC.get("standard", 32.0), "standard"


def score_ci(submission: dict, ground_truth: dict) -> float:
    """Score contradiction identification.

    Full marks for exact type + both params match (order-independent).
    Partial credit for type match + partial param match.
    Zero for wrong contradiction type.
    """
    sub_type = submission.get("contradiction_type")
    gt_type = ground_truth.get("contradiction_type")
    if sub_type != gt_type:
        return 0.0

    sub_params = {
        submission.get("triz_param_a"),
        submission.get("triz_param_b"),
    }
    gt_params = {
        ground_truth.get("triz_param_a"),
        ground_truth.get("triz_param_b"),
    }

    sub_params.discard(None)
    gt_params.discard(None)

    if sub_params == gt_params and len(sub_params) == 2:
        return 100.0

    overlap = len(sub_params & gt_params)
    if overlap == 1:
        return 65.0

    return 30.0


def score_ps(submitted: list[int], target: list[int]) -> float:
    """Score principle selection using Jaccard similarity."""
    if not submitted and not target:
        return 100.0
    if not submitted or not target:
        return 0.0

    s_set = set(submitted)
    t_set = set(target)
    intersection = len(s_set & t_set)
    union = len(s_set | t_set)

    return (intersection / union) * 100.0 if union > 0 else 0.0


def score_cr(level: str) -> float:
    """Score contradiction resolution quality.

    Levels: eliminates (100), reduces (60), manages (32), fails (0).
    """
    return CR_RUBRIC.get(level.lower().strip(), 0.0)


def score_sn(level: str) -> float:
    """Score solution novelty.

    Levels: non_obvious (100), novel_combination (60), standard (32), restatement (0).
    """
    return SN_RUBRIC.get(level.lower().strip(), 0.0)


def score_ifr(ifr_value: int) -> float:
    """Score IFR proximity. Maps 0-4 scale to 0-100."""
    return max(0.0, min(100.0, ifr_value * 25.0))


def compute_final_score(
    ci: float, ps: float, sn: float, cr: float, ifr: float
) -> float:
    """Compute weighted final TRIZBENCH score.

    CI 25% + PS 20% + SN 20% + CR 25% + IFR 10% = 0-100.
    """
    return (
        WEIGHTS["ci"] * ci
        + WEIGHTS["ps"] * ps
        + WEIGHTS["sn"] * sn
        + WEIGHTS["cr"] * cr
        + WEIGHTS["ifr"] * ifr
    )
