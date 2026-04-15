"""TRIZBENCH 5-dimension scorer.

Scoring dimensions and weights:
  CI  (Contradiction Identification) — 25%
  PS  (Principle Selection)          — 20%
  SN  (Solution Novelty)             — 20%
  CR  (Contradiction Resolution)     — 25%
  IFR (Ideal Final Result)           — 10%

SN and CR support LLM-as-judge scoring via Claude CLI (--print mode).
Position-swap bias mitigation: each judgment runs twice with solution order
swapped, then the worse (more conservative) classification is used.
Falls back to deterministic string-mapping when Claude CLI is unavailable.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import logging

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
    raw_lower = raw.lower()
    for level in reversed(valid_levels):
        if level in raw_lower:
            return level
    return None


def _judge_cr_once(problem: str, solution: str, ground_truth: str) -> str:
    prompt = (
        "You are a TRIZ evaluation judge. Classify how well the solution resolves "
        "the stated contradiction.\n\n"
        f"PROBLEM:\n{problem}\n\n"
        f"GROUND TRUTH CONTRADICTION:\n{ground_truth}\n\n"
        f"SOLUTION:\n{solution}\n\n"
        "Respond with EXACTLY ONE of these classifications:\n"
        "- eliminates: The contradiction is fully eliminated, not traded off\n"
        "- reduces: The contradiction is significantly reduced but not eliminated\n"
        "- manages: The contradiction is managed through compromise or trade-off\n"
        "- fails: The solution does not address the contradiction\n\n"
        "Reply with only the classification word, nothing else."
    )
    raw = _call_claude_judge(prompt)
    level = _extract_level(raw, CR_LEVELS)
    if level is None:
        raise ValueError(f"Could not parse CR level from: {raw[:100]}")
    return level


def _judge_sn_once(problem: str, solution: str, ground_truth: str) -> str:
    prompt = (
        "You are a TRIZ evaluation judge. Classify the novelty of the solution "
        "relative to the stated problem.\n\n"
        f"PROBLEM:\n{problem}\n\n"
        f"GROUND TRUTH PRINCIPLES:\n{ground_truth}\n\n"
        f"SOLUTION:\n{solution}\n\n"
        "Respond with EXACTLY ONE of these classifications:\n"
        "- non_obvious: Solution applies TRIZ principles in a surprising, inventive way\n"
        "- novel_combination: Solution combines known techniques in a new way\n"
        "- standard: Solution uses a well-known approach for this type of problem\n"
        "- restatement: Solution merely restates the problem or describes the obvious\n\n"
        "Reply with only the classification word, nothing else."
    )
    raw = _call_claude_judge(prompt)
    level = _extract_level(raw, SN_LEVELS)
    if level is None:
        raise ValueError(f"Could not parse SN level from: {raw[:100]}")
    return level


def _conservative_level(a: str, b: str, ordered_levels: list[str]) -> str:
    """Position-swap bias mitigation: return the lower (more conservative) of two levels."""
    idx_a = ordered_levels.index(a)
    idx_b = ordered_levels.index(b)
    return ordered_levels[min(idx_a, idx_b)]


def score_cr_llm(problem: str, solution: str, ground_truth: str) -> tuple[float, str]:
    """Score CR via LLM-as-judge with position-swap debiasing.

    Returns (score, level). Falls back to deterministic if Claude unavailable.
    """
    if not _claude_available():
        logger.warning("Claude CLI not found, falling back to deterministic CR scoring")
        return CR_RUBRIC.get("manages", 32.0), "manages"

    try:
        level_forward = _judge_cr_once(problem, solution, ground_truth)
        level_reverse = _judge_cr_once(problem, ground_truth, solution)
        level = _conservative_level(level_forward, level_reverse, CR_LEVELS)
        return CR_RUBRIC[level], level
    except Exception as e:
        logger.warning(f"LLM CR judge failed, falling back: {e}")
        return CR_RUBRIC.get("manages", 32.0), "manages"


def score_sn_llm(problem: str, solution: str, ground_truth: str) -> tuple[float, str]:
    """Score SN via LLM-as-judge with position-swap debiasing.

    Returns (score, level). Falls back to deterministic if Claude unavailable.
    """
    if not _claude_available():
        logger.warning("Claude CLI not found, falling back to deterministic SN scoring")
        return SN_RUBRIC.get("standard", 32.0), "standard"

    try:
        level_forward = _judge_sn_once(problem, solution, ground_truth)
        level_reverse = _judge_sn_once(problem, ground_truth, solution)
        level = _conservative_level(level_forward, level_reverse, SN_LEVELS)
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
    if submission["contradiction_type"] != ground_truth["contradiction_type"]:
        return 0.0

    sub_params = {submission["triz_param_a"], submission["triz_param_b"]}
    gt_params = {ground_truth["triz_param_a"], ground_truth["triz_param_b"]}

    if sub_params == gt_params:
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
