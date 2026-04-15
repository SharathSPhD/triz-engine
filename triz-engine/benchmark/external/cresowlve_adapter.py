"""Adapter for CresOWLve benchmark (HuggingFace).

Tests lateral thinking, analogy, abstraction, and divergent creative reasoning.

Source: https://huggingface.co/datasets/mismayil/cresowlve (~4,122 samples)
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
DATA_DIR = ROOT / "benchmark" / "external" / "data"
RESULTS_DIR = ROOT / "results" / "external-cresowlve"

TRIZ_SYSTEM_PROMPT = """You are a creative problem solver using TRIZ (Theory of Inventive Problem Solving) thinking.

Apply inventive reasoning to this question:
1. **Identify the apparent paradox**: What seems contradictory or impossible in this question?
2. **Apply TRIZ thinking patterns**:
   - Principle 13 (Inversion): What if you reverse the expected approach?
   - Principle 40 (Composite materials / Analogy): What analogies from other domains apply?
   - Separation by system level: Consider parts vs whole, micro vs macro.
   - Principle 22 (Blessing in disguise): What hidden resource does the constraint itself provide?
3. **Make creative connections**: Look for the non-obvious link between seemingly unrelated concepts.
4. **Give a clear, concise answer**.

Think inventively — the answer usually requires seeing something familiar in a completely new way."""

VANILLA_SYSTEM_PROMPT = """Think carefully about this question. Consider multiple angles and possibilities before answering. Give a clear, concise answer."""


def download_dataset() -> Path:
    """Download CresOWLve dataset from HuggingFace."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    target = DATA_DIR / "cresowlve.json"
    if target.exists():
        return target

    try:
        from datasets import load_dataset
        ds = load_dataset("mismayil/cresowlve", "en", split="test")
        records = [dict(row) for row in ds]
        target.write_text(json.dumps(records, indent=2, ensure_ascii=False))
        print(f"Downloaded {len(records)} CresOWLve problems to {target}", file=sys.stderr)
        return target
    except ImportError:
        pass

    import urllib.request
    url = "https://huggingface.co/api/datasets/mismayil/cresowlve/parquet/default/test/0.parquet"
    parquet_path = DATA_DIR / "cresowlve.parquet"

    try:
        print("Downloading CresOWLve dataset...", file=sys.stderr)
        urllib.request.urlretrieve(url, parquet_path)

        try:
            import pandas as pd
            df = pd.read_parquet(parquet_path)
            records = df.to_dict(orient="records")
            target.write_text(json.dumps(records, indent=2, ensure_ascii=False, default=str))
            print(f"Converted {len(records)} problems to {target}", file=sys.stderr)
            return target
        except ImportError:
            print("pandas required for parquet parsing. Install: pip install pandas pyarrow", file=sys.stderr)
            raise

    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)
        print("Please manually download and place dataset at:", file=sys.stderr)
        print(f"  {target}", file=sys.stderr)
        raise


def load_problems(
    limit: int = 100,
    difficulty_range: tuple[int, int] | None = None,
    creative_domains: list[str] | None = None,
    seed: int = 42,
) -> list[dict]:
    """Load CresOWLve problems with optional stratified sampling.

    Returns list of dicts with: id, question, answer, difficulty,
    explanation, other_answers, creative_domains.
    """
    data_path = DATA_DIR / "cresowlve.json"
    if not data_path.exists():
        data_path = download_dataset()

    with open(data_path, encoding="utf-8") as f:
        all_problems = json.load(f)

    if difficulty_range:
        lo, hi = difficulty_range
        all_problems = [
            p for p in all_problems
            if lo <= (p.get("difficulty") or 3) <= hi
        ]

    if creative_domains:
        cd_lower = {c.lower() for c in creative_domains}
        all_problems = [
            p for p in all_problems
            if any(
                d.lower() in cd_lower
                for d in (p.get("creative_domains") or [])
            )
        ]

    rng = random.Random(seed)
    rng.shuffle(all_problems)
    selected = all_problems[:limit]

    return [
        {
            "id": f"CO-{i+1:03d}",
            "question": p.get("question", ""),
            "answer": p.get("answer", ""),
            "difficulty": p.get("difficulty", 3),
            "explanation": p.get("explanation", ""),
            "other_answers": p.get("other_answers") or [],
            "creative_domains": p.get("creative_domains") or [],
        }
        for i, p in enumerate(selected)
    ]


def score_answer(
    question: str,
    candidate: str,
    correct_answer: str,
    other_answers: list[str] | None = None,
    judge_fn=None,
) -> dict:
    """Score a CresOWLve answer.

    Uses LLM-as-judge to determine if the candidate matches the correct
    answer (accounting for paraphrasing and alternative answers).
    """
    if judge_fn:
        alts = ""
        if other_answers:
            alt_list = "; ".join(str(a) for a in other_answers[:5])
            alts = f"\nACCEPTABLE ALTERNATIVES: {alt_list}"

        prompt = (
            "You are evaluating an answer to a creative reasoning question.\n\n"
            f"QUESTION: {question}\n\n"
            f"CORRECT ANSWER: {correct_answer}{alts}\n\n"
            f"CANDIDATE ANSWER: {candidate}\n\n"
            "Is the candidate answer correct? It counts as correct if it:\n"
            "- Matches the correct answer in meaning (not necessarily exact wording)\n"
            "- Matches any of the acceptable alternatives\n"
            "- Captures the key insight even if expressed differently\n\n"
            "Reply: CORRECT or INCORRECT (then one sentence rationale)"
        )
        try:
            raw = judge_fn(prompt)
            raw_lower = raw.lower()
            if "incorrect" in raw_lower:
                return {"correct": False, "method": "llm_judge"}
            if "correct" in raw_lower:
                return {"correct": True, "method": "llm_judge"}
        except Exception:
            pass

    import re
    def _normalize(s: str) -> str:
        return re.sub(r"[^\w\s]", "", s.lower()).strip()

    candidate_norm = _normalize(candidate)
    answer_norm = _normalize(correct_answer)
    if answer_norm and (answer_norm in candidate_norm or candidate_norm in answer_norm):
        return {"correct": True, "method": "substring_match"}

    if other_answers:
        for alt in other_answers:
            alt_norm = _normalize(str(alt))
            if alt_norm and (alt_norm in candidate_norm or candidate_norm in alt_norm):
                return {"correct": True, "method": "alternative_match"}

    return {"correct": False, "method": "no_match"}


def run_cresowlve_benchmark(
    triz_fn,
    vanilla_fn,
    judge_fn=None,
    limit: int = 100,
    seed: int = 42,
) -> dict:
    """Run CresOWLve benchmark comparing TRIZ-augmented vs vanilla.

    triz_fn: callable(prompt: str, system_prompt: str) -> str
    vanilla_fn: callable(prompt: str, system_prompt: str) -> str
    judge_fn: callable(prompt: str) -> str (for scoring)

    Returns comparison report with per-difficulty breakdown.
    """
    problems = load_problems(limit=limit, seed=seed)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    triz_correct = 0
    vanilla_correct = 0
    by_difficulty = {}
    by_domain = {}
    results = []

    from benchmark.runner import QuotaExhaustedError

    for problem in problems:
        prompt = f"QUESTION: {problem['question']}\n\nGive your answer concisely."
        diff = problem["difficulty"]

        print(f"  {problem['id']} (d={diff}): {problem['question'][:60]}...", file=sys.stderr)

        try:
            triz_raw = triz_fn(prompt, TRIZ_SYSTEM_PROMPT)
            triz_score = score_answer(
                problem["question"], triz_raw, problem["answer"],
                problem.get("other_answers"), judge_fn,
            )
        except QuotaExhaustedError:
            print(f"  QUOTA EXHAUSTED — stopping benchmark.", file=sys.stderr)
            break
        except Exception:
            triz_raw = ""
            triz_score = {"correct": False, "method": "error"}

        try:
            vanilla_raw = vanilla_fn(prompt, VANILLA_SYSTEM_PROMPT)
            vanilla_score = score_answer(
                problem["question"], vanilla_raw, problem["answer"],
                problem.get("other_answers"), judge_fn,
            )
        except QuotaExhaustedError:
            print(f"  QUOTA EXHAUSTED — stopping benchmark.", file=sys.stderr)
            break
        except Exception:
            vanilla_raw = ""
            vanilla_score = {"correct": False, "method": "error"}

        if triz_score["correct"]:
            triz_correct += 1
        if vanilla_score["correct"]:
            vanilla_correct += 1

        if diff not in by_difficulty:
            by_difficulty[diff] = {"triz": 0, "vanilla": 0, "total": 0}
        by_difficulty[diff]["total"] += 1
        if triz_score["correct"]:
            by_difficulty[diff]["triz"] += 1
        if vanilla_score["correct"]:
            by_difficulty[diff]["vanilla"] += 1

        for domain in problem.get("creative_domains", []):
            if domain not in by_domain:
                by_domain[domain] = {"triz": 0, "vanilla": 0, "total": 0}
            by_domain[domain]["total"] += 1
            if triz_score["correct"]:
                by_domain[domain]["triz"] += 1
            if vanilla_score["correct"]:
                by_domain[domain]["vanilla"] += 1

        result = {
            "problem_id": problem["id"],
            "difficulty": diff,
            "creative_domains": problem.get("creative_domains", []),
            "triz_correct": triz_score["correct"],
            "vanilla_correct": vanilla_score["correct"],
        }
        results.append(result)

        result_path = RESULTS_DIR / f"{problem['id']}.json"
        result_path.write_text(json.dumps({
            **result,
            "question": problem["question"],
            "correct_answer": problem["answer"],
            "triz_answer": triz_raw[:1000],
            "vanilla_answer": vanilla_raw[:1000],
        }, indent=2, ensure_ascii=False))

    total = len(results)
    difficulty_breakdown = {
        str(d): {
            "total": v["total"],
            "triz_accuracy": v["triz"] / v["total"] if v["total"] else 0,
            "vanilla_accuracy": v["vanilla"] / v["total"] if v["total"] else 0,
        }
        for d, v in sorted(by_difficulty.items())
    }

    domain_breakdown = {
        d: {
            "total": v["total"],
            "triz_accuracy": v["triz"] / v["total"] if v["total"] else 0,
            "vanilla_accuracy": v["vanilla"] / v["total"] if v["total"] else 0,
        }
        for d, v in sorted(by_domain.items(), key=lambda x: x[1]["total"], reverse=True)
    }

    return {
        "benchmark": "CresOWLve",
        "total_problems": total,
        "triz_correct": triz_correct,
        "vanilla_correct": vanilla_correct,
        "triz_accuracy": triz_correct / total if total else 0,
        "vanilla_accuracy": vanilla_correct / total if total else 0,
        "accuracy_delta": (triz_correct - vanilla_correct) / total if total else 0,
        "by_difficulty": difficulty_breakdown,
        "by_domain": domain_breakdown,
    }


if __name__ == "__main__":
    print("CresOWLve adapter ready")
    try:
        problems = load_problems(limit=3)
        print(f"Loaded {len(problems)} problems:")
        for p in problems:
            print(f"  {p['id']} (d={p['difficulty']}): {p['question'][:80]}...")
    except Exception as e:
        print(f"Dataset not available: {e}")
        print("Install: pip install datasets (or pandas pyarrow)")
