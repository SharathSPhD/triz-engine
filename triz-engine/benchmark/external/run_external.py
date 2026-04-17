#!/usr/bin/env python3
"""Unified runner for all external creative benchmarks.

Runs TRIZ-augmented vs vanilla-claude on:
  1. Published TRIZBENCH (patent data)
  2. MacGyver (constrained invention)
  3. CresOWLve (lateral thinking)

Usage:
    python -m benchmark.external.run_external [--benchmarks trizbench macgyver cresowlve] [--limit 10]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
RESULTS_DIR = ROOT / "results"


def make_claude_fn(
    use_mcp: bool = False,
    system_prompt_path: str | None = None,
    slash_command: str | None = None,
    capture_trace: bool = False,
):
    """Create a callable that invokes Claude CLI.

    When capture_trace=True, returned fn yields (text, trace, trace_status).
    Otherwise returns a plain string for backward compatibility.
    When slash_command is provided (e.g. "/triz-engine:analyze"), it is
    prepended to the user prompt so the installed plugin command fires.
    """
    from benchmark.runner import invoke_claude, _generate_mcp_config, load_system_prompt

    mcp_config = None
    if use_mcp:
        mcp_config = _generate_mcp_config()

    base_sys_prompt = load_system_prompt(system_prompt_path)

    def _extract_text(result):
        if isinstance(result, tuple):
            return result[0] if result else ""
        return result or ""

    def fn(prompt: str, system_prompt: str = ""):
        combined_prompt = prompt
        if slash_command:
            combined_prompt = f"{slash_command} {combined_prompt}"
        full_sys = ""
        if base_sys_prompt:
            full_sys = base_sys_prompt
        if system_prompt:
            full_sys = (full_sys + "\n\n" + system_prompt).strip() if full_sys else system_prompt

        result = invoke_claude(
            combined_prompt,
            use_mcp=use_mcp,
            mcp_config_path=mcp_config,
            system_prompt=full_sys if full_sys else None,
            model="haiku",
            budget_usd=1.00,
            timeout_seconds=240 if (slash_command or use_mcp) else 120,
            retries=2,
            capture_trace=capture_trace,
        )

        text = _extract_text(result)
        if text.strip():
            return result

        if slash_command:
            print(
                f"  [retry] empty output with {slash_command}; retrying without slash command",
                file=sys.stderr,
            )
            retry = invoke_claude(
                prompt,
                use_mcp=use_mcp,
                mcp_config_path=mcp_config,
                system_prompt=full_sys if full_sys else None,
                model="haiku",
                budget_usd=1.00,
                timeout_seconds=180,
                retries=2,
                capture_trace=capture_trace,
            )
            retry_text = _extract_text(retry)
            if retry_text.strip():
                return retry

        return result

    return fn


def make_judge_fn():
    """Create a callable that invokes Claude Sonnet as judge."""
    from benchmark.scorer import _call_claude_judge
    return _call_claude_judge


def run_trizbench(limit: int = 20):
    """Run published TRIZBENCH evaluation."""
    from benchmark.external.trizbench_adapter import (
        load_problems, run_external_trizbench,
    )
    from benchmark.runner import invoke_claude, _generate_mcp_config, load_system_prompt

    print("\n" + "=" * 60)
    print("EXTERNAL BENCHMARK: Published TRIZBENCH (Patent Data)")
    print("=" * 60)

    mcp_config = _generate_mcp_config()
    sys_prompt = load_system_prompt("commands/analyze.md")

    def triz_participant(problem_statement: str) -> str:
        from benchmark.runner import format_prompt
        prompt = format_prompt({
            "domain": "Patent",
            "title": "Patent Contradiction",
            "problem_statement": problem_statement,
        })
        return invoke_claude(
            prompt,
            use_mcp=True,
            mcp_config_path=mcp_config,
            system_prompt=sys_prompt,
            model="haiku",
            budget_usd=1.00,
            timeout_seconds=120,
            retries=2,
        )

    def vanilla_participant(problem_statement: str) -> str:
        from benchmark.runner import format_prompt
        prompt = format_prompt({
            "domain": "Patent",
            "title": "Patent Contradiction",
            "problem_statement": problem_statement,
        })
        return invoke_claude(
            prompt,
            use_mcp=False,
            system_prompt=None,
            model="haiku",
            budget_usd=1.00,
            timeout_seconds=120,
            retries=2,
        )

    print("\n--- TRIZ-Engine ---")
    triz_results = run_external_trizbench(
        triz_participant, limit=limit, participant_name="triz-engine",
    )

    print("\n--- Vanilla Claude ---")
    vanilla_results = run_external_trizbench(
        vanilla_participant, limit=limit, participant_name="vanilla-claude",
    )

    print("\n--- Results ---")
    print(f"{'Metric':<35s} {'TRIZ':>10s} {'Vanilla':>10s}")
    print("-" * 55)
    for metric in ["contradiction_type_accuracy", "parameter_exact_accuracy", "principle_f1_mean"]:
        t = triz_results.get(metric, 0)
        v = vanilla_results.get(metric, 0)
        print(f"  {metric:<33s} {t:>9.1%} {v:>9.1%}")

    return {"triz": triz_results, "vanilla": vanilla_results}


def run_macgyver(
    limit: int = 50,
    capture_trace: bool = False,
    use_plugin: bool = True,
    start_offset: int = 0,
):
    """Run MacGyver creative problem-solving evaluation."""
    from benchmark.external.macgyver_adapter import run_macgyver_benchmark

    print("\n" + "=" * 60)
    print("EXTERNAL BENCHMARK: MacGyver (Constrained Invention)")
    print("=" * 60)

    triz_fn = make_claude_fn(
        use_mcp=True,
        system_prompt_path="commands/analyze.md",
        slash_command="/triz-engine:analyze" if use_plugin else None,
        capture_trace=capture_trace,
    )
    vanilla_fn = make_claude_fn(
        use_mcp=False,
        capture_trace=capture_trace,
    )
    judge_fn = make_judge_fn()

    results = run_macgyver_benchmark(
        triz_fn, vanilla_fn, judge_fn,
        limit=limit, start_offset=start_offset,
    )

    print(f"\n--- Results ({results['total_problems']} problems) ---")
    print(f"  TRIZ wins:    {results['triz_wins']}")
    print(f"  Vanilla wins: {results['vanilla_wins']}")
    print(f"  Ties:         {results['ties']}")
    print(f"  TRIZ win rate:    {results['triz_win_rate']:.1%}")
    print(f"  TRIZ mean score:  {results['triz_mean_score']:.3f}")
    print(f"  Vanilla mean:     {results['vanilla_mean_score']:.3f}")

    return results


def run_cresowlve(limit: int = 100):
    """Run CresOWLve lateral thinking evaluation."""
    from benchmark.external.cresowlve_adapter import run_cresowlve_benchmark

    print("\n" + "=" * 60)
    print("EXTERNAL BENCHMARK: CresOWLve (Lateral Thinking)")
    print("=" * 60)

    triz_fn = make_claude_fn(use_mcp=False)
    vanilla_fn = make_claude_fn(use_mcp=False)
    judge_fn = make_judge_fn()

    results = run_cresowlve_benchmark(triz_fn, vanilla_fn, judge_fn, limit=limit)

    print(f"\n--- Results ({results['total_problems']} problems) ---")
    print(f"  TRIZ accuracy:    {results['triz_accuracy']:.1%}")
    print(f"  Vanilla accuracy: {results['vanilla_accuracy']:.1%}")
    print(f"  Delta:            {results['accuracy_delta']:+.1%}")

    if results.get("by_difficulty"):
        print("\n  By difficulty:")
        for d, v in sorted(results["by_difficulty"].items()):
            print(
                f"    d={d}: TRIZ {v['triz_accuracy']:.0%} "
                f"vs Vanilla {v['vanilla_accuracy']:.0%} "
                f"(n={v['total']})"
            )

    return results


def main():
    parser = argparse.ArgumentParser(description="Run external creative benchmarks")
    parser.add_argument(
        "--benchmarks",
        nargs="+",
        choices=["trizbench", "macgyver", "cresowlve"],
        default=["trizbench", "macgyver", "cresowlve"],
        help="Which benchmarks to run",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Max problems per benchmark (default: 10 for cost control)",
    )
    parser.add_argument(
        "--capture-trace", action="store_true",
        help="Capture stream-json trace (tool_use / tool_result / agent turns) in each result JSON",
    )
    parser.add_argument(
        "--start-offset", type=int, default=0,
        help="Skip first N MacGyver problems before running",
    )
    args = parser.parse_args()

    all_results = {}

    if "trizbench" in args.benchmarks:
        try:
            all_results["trizbench"] = run_trizbench(limit=args.limit)
        except Exception as e:
            print(f"\nTRIZBENCH failed: {e}", file=sys.stderr)

    if "macgyver" in args.benchmarks:
        try:
            all_results["macgyver"] = run_macgyver(
                limit=args.limit,
                capture_trace=args.capture_trace,
                start_offset=args.start_offset,
            )
        except Exception as e:
            print(f"\nMacGyver failed: {e}", file=sys.stderr)

    if "cresowlve" in args.benchmarks:
        try:
            all_results["cresowlve"] = run_cresowlve(limit=args.limit)
        except Exception as e:
            print(f"\nCresOWLve failed: {e}", file=sys.stderr)

    summary_path = RESULTS_DIR / "external-benchmarks-summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    serializable = {}
    for name, data in all_results.items():
        if isinstance(data, dict):
            clean = {
                k: v for k, v in data.items()
                if k != "results"
            }
            serializable[name] = clean
    summary_path.write_text(json.dumps(serializable, indent=2))
    print(f"\nSummary saved to {summary_path}")


if __name__ == "__main__":
    main()
