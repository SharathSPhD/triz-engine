"""Targeted re-run of MacGyver + CresOWLve problems after the plugin fixes.

Re-runs only the diagnostic subset identified in the critique:
  MacGyver: MG-007, MG-009, MG-010, MG-012, MG-014
  CresOWLve: CO-001, CO-002, CO-005, CO-009

Each per-problem JSON in triz-engine/results/external-macgyver/ and
triz-engine/results/external-cresowlve/ is overwritten with the new outputs
so the dashboard picks up the corrected scores. Traces are not captured
(capture_trace=False) to keep quota small.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TRIZ_ROOT = ROOT / "triz-engine"
sys.path.insert(0, str(TRIZ_ROOT))

from benchmark.external.cresowlve_adapter import (  # noqa: E402
    RESULTS_DIR as CO_RESULTS_DIR,
    TRIZ_SYSTEM_PROMPT as CO_TRIZ_PROMPT,
    VANILLA_SYSTEM_PROMPT as CO_VANILLA_PROMPT,
    load_problems as co_load_problems,
    score_answer as co_score_answer,
)
from benchmark.external.macgyver_adapter import (  # noqa: E402
    RESULTS_DIR as MG_RESULTS_DIR,
    TRIZ_SYSTEM_PROMPT as MG_TRIZ_PROMPT,
    VANILLA_SYSTEM_PROMPT as MG_VANILLA_PROMPT,
    format_prompt as mg_format_prompt,
    load_problems as mg_load_problems,
    score_macgyver_solution,
)
from benchmark.external.run_external import make_claude_fn, make_judge_fn  # noqa: E402
from benchmark.runner import QuotaExhaustedError  # noqa: E402

MG_IDS = ["MG-007", "MG-009", "MG-010", "MG-012", "MG-014"]
CO_IDS = ["CO-001", "CO-002", "CO-005", "CO-009"]


def _extract_text(result) -> str:
    if isinstance(result, tuple):
        return result[0] if result else ""
    return result or ""


def run_macgyver_subset(judge_fn) -> dict:
    print("\n" + "=" * 60)
    print("Validation: MacGyver subset")
    print("=" * 60)

    problems = mg_load_problems(limit=max(int(x.split("-")[1]) for x in MG_IDS))
    by_id = {p["id"]: p for p in problems}

    triz_fn = make_claude_fn(
        use_mcp=True,
        system_prompt_path="commands/analyze.md",
        slash_command="/triz-engine:analyze",
        capture_trace=False,
    )
    vanilla_fn = make_claude_fn(use_mcp=False, capture_trace=False)

    scores = []
    for pid in MG_IDS:
        problem = by_id.get(pid)
        if not problem:
            print(f"  {pid}: not found in dataset", file=sys.stderr)
            continue

        print(f"\n  {pid}: {problem['problem'][:70]}...", file=sys.stderr)
        prompt = mg_format_prompt(problem)

        try:
            triz_raw = _extract_text(triz_fn(prompt, MG_TRIZ_PROMPT))
        except QuotaExhaustedError:
            print("  QUOTA EXHAUSTED — stopping validation", file=sys.stderr)
            return {"stopped": "quota", "scores": scores}
        except Exception as e:
            print(f"  triz error: {e}", file=sys.stderr)
            triz_raw = ""

        triz_score = score_macgyver_solution(
            problem["problem"], triz_raw, problem["reference_solution"], judge_fn,
        )

        try:
            vanilla_raw = _extract_text(vanilla_fn(prompt, MG_VANILLA_PROMPT))
        except QuotaExhaustedError:
            print("  QUOTA EXHAUSTED — stopping validation", file=sys.stderr)
            return {"stopped": "quota", "scores": scores}
        except Exception as e:
            print(f"  vanilla error: {e}", file=sys.stderr)
            vanilla_raw = ""

        vanilla_score = score_macgyver_solution(
            problem["problem"], vanilla_raw, problem["reference_solution"], judge_fn,
        )

        payload = {
            "problem_id": pid,
            "category": problem["category"],
            "triz": triz_score,
            "vanilla": vanilla_score,
            "problem": problem["problem"],
            "triz_output": triz_raw[:2000],
            "vanilla_output": vanilla_raw[:2000],
            "reference": problem["reference_solution"],
            "revalidated": True,
        }

        result_path = MG_RESULTS_DIR / f"{pid}.json"
        result_path.write_text(json.dumps(payload, indent=2))
        print(
            f"    triz={triz_score['level']} ({triz_score['score']:.2f})  "
            f"vanilla={vanilla_score['level']} ({vanilla_score['score']:.2f})",
            file=sys.stderr,
        )
        scores.append({
            "id": pid,
            "triz": triz_score["score"],
            "vanilla": vanilla_score["score"],
        })

    return {"stopped": None, "scores": scores}


def run_cresowlve_subset(judge_fn) -> dict:
    print("\n" + "=" * 60)
    print("Validation: CresOWLve subset")
    print("=" * 60)

    max_idx = max(int(x.split("-")[1]) for x in CO_IDS)
    problems = co_load_problems(limit=max_idx, seed=42)
    by_id = {p["id"]: p for p in problems}

    triz_fn = make_claude_fn(use_mcp=False, capture_trace=False)
    vanilla_fn = make_claude_fn(use_mcp=False, capture_trace=False)

    outcomes = []
    for pid in CO_IDS:
        problem = by_id.get(pid)
        if not problem:
            print(f"  {pid}: not found in dataset", file=sys.stderr)
            continue

        print(f"\n  {pid}: {problem['question'][:70]}...", file=sys.stderr)
        prompt = f"QUESTION: {problem['question']}\n\nGive your answer concisely."

        try:
            triz_raw = _extract_text(triz_fn(prompt, CO_TRIZ_PROMPT))
        except QuotaExhaustedError:
            print("  QUOTA EXHAUSTED — stopping validation", file=sys.stderr)
            return {"stopped": "quota", "outcomes": outcomes}
        except Exception as e:
            print(f"  triz error: {e}", file=sys.stderr)
            triz_raw = ""

        triz_score = co_score_answer(
            problem["question"], triz_raw, problem["answer"],
            problem.get("other_answers"), judge_fn,
        )

        try:
            vanilla_raw = _extract_text(vanilla_fn(prompt, CO_VANILLA_PROMPT))
        except QuotaExhaustedError:
            print("  QUOTA EXHAUSTED — stopping validation", file=sys.stderr)
            return {"stopped": "quota", "outcomes": outcomes}
        except Exception as e:
            print(f"  vanilla error: {e}", file=sys.stderr)
            vanilla_raw = ""

        vanilla_score = co_score_answer(
            problem["question"], vanilla_raw, problem["answer"],
            problem.get("other_answers"), judge_fn,
        )

        payload = {
            "problem_id": pid,
            "difficulty": problem["difficulty"],
            "creative_domains": problem.get("creative_domains", []),
            "triz_correct": triz_score["correct"],
            "vanilla_correct": vanilla_score["correct"],
            "question": problem["question"],
            "correct_answer": problem["answer"],
            "triz_answer": triz_raw[:1500],
            "vanilla_answer": vanilla_raw[:1500],
            "revalidated": True,
        }

        result_path = CO_RESULTS_DIR / f"{pid}.json"
        result_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        print(
            f"    triz_correct={triz_score['correct']}  "
            f"vanilla_correct={vanilla_score['correct']}",
            file=sys.stderr,
        )
        outcomes.append({
            "id": pid,
            "triz": triz_score["correct"],
            "vanilla": vanilla_score["correct"],
            "triz_answer_preview": triz_raw[:200],
        })

    return {"stopped": None, "outcomes": outcomes}


def main() -> int:
    judge_fn = make_judge_fn()

    mg = run_macgyver_subset(judge_fn)
    co = run_cresowlve_subset(judge_fn)

    print("\n" + "=" * 60)
    print("Validation summary")
    print("=" * 60)

    if mg["scores"]:
        triz_mean = sum(s["triz"] for s in mg["scores"]) / len(mg["scores"])
        vanilla_mean = sum(s["vanilla"] for s in mg["scores"]) / len(mg["scores"])
        print(f"MacGyver ({len(mg['scores'])} problems)")
        print(f"  triz mean:    {triz_mean:.3f}")
        print(f"  vanilla mean: {vanilla_mean:.3f}")
        gate = triz_mean >= 0.75
        print(f"  gate >=0.75:  {'PASS' if gate else 'FAIL'}")
    else:
        print("MacGyver: no scores recorded")

    if co["outcomes"]:
        print(f"CresOWLve ({len(co['outcomes'])} problems)")
        for o in co["outcomes"]:
            flag = "correct" if o["triz"] else ("abstained" if "don't know" in o["triz_answer_preview"].lower() else "wrong/other")
            print(f"  {o['id']}: triz={flag}, vanilla_correct={o['vanilla']}")
    else:
        print("CresOWLve: no outcomes recorded")

    if mg.get("stopped") or co.get("stopped"):
        print("\nNote: validation stopped early due to quota.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
