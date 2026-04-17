"""Targeted re-run of a single MacGyver problem's VANILLA side with the plugin disabled.

Used to regenerate clean vanilla traces for live-demo result JSONs that were
contaminated by the auto-activating triz-engine plugin skill firing during
what was supposed to be a plugin-free baseline invocation.

Usage:
    uv run --script scripts/rerun_vanilla_demo.py MG-008 [MG-013 ...]
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRIZ_ROOT = REPO_ROOT / "triz-engine"
sys.path.insert(0, str(TRIZ_ROOT))

from benchmark._plugin_toggle import plugin_disabled  # noqa: E402
from benchmark.external.macgyver_adapter import (  # noqa: E402
    RESULTS_DIR,
    format_prompt,
    load_problems,
    score_macgyver_solution,
)
from benchmark.external.run_external import make_judge_fn  # noqa: E402
from benchmark.runner import invoke_claude  # noqa: E402


def rerun_mg_vanilla(problem_id: str) -> None:
    result_path = RESULTS_DIR / f"{problem_id}.json"
    if not result_path.exists():
        print(f"ERROR: {result_path} not found", file=sys.stderr)
        return

    existing = json.loads(result_path.read_text())

    all_probs = load_problems(limit=10_000, skip_completed=False)
    match = next((p for p in all_probs if p["id"] == problem_id), None)
    if match is None:
        print(f"ERROR: problem {problem_id} not found in dataset", file=sys.stderr)
        return

    prompt = format_prompt(match)
    print(f"\n== Re-running {problem_id} VANILLA side with plugin disabled ==", flush=True)
    print(f"   prompt[:80]: {prompt[:80]!r}", flush=True)

    t0 = time.time()
    with plugin_disabled():
        result = invoke_claude(
            prompt,
            use_mcp=False,
            system_prompt=None,
            model="haiku",
            budget_usd=1.00,
            timeout_seconds=180,
            retries=2,
            capture_trace=True,
        )
    elapsed = time.time() - t0

    if isinstance(result, tuple):
        v_text, v_trace, v_status = result
    else:
        v_text, v_trace, v_status = (result or "", [], "disabled")

    print(f"   output len: {len(v_text)} chars, {len(v_trace)} trace events, {elapsed:.1f}s ({v_status})", flush=True)

    skill_fired = any(
        "triz-engine:analyze" in json.dumps(e) for e in v_trace
    )
    if skill_fired:
        print(
            "   WARNING: vanilla trace still references triz-engine:analyze — plugin toggle may have failed",
            file=sys.stderr,
        )

    judge_fn = make_judge_fn()
    v_judge = score_macgyver_solution(
        match["problem"], v_text, match["reference_solution"], judge_fn=judge_fn,
    )

    existing["vanilla_output"] = v_text
    existing["vanilla_trace"] = v_trace
    existing["vanilla_trace_status"] = v_status
    existing["vanilla"] = {
        "level": v_judge["level"],
        "score": v_judge["score"],
    }
    existing["vanilla_revalidated"] = True
    existing["vanilla_elapsed_seconds"] = round(elapsed, 1)

    result_path.write_text(json.dumps(existing, indent=2))
    print(f"   wrote {result_path}", flush=True)
    print(
        f"   vanilla judge: level={v_judge['level']} score={v_judge['score']:.2f}",
        flush=True,
    )


def main() -> int:
    ids = sys.argv[1:]
    if not ids:
        print("usage: rerun_vanilla_demo.py MG-008 [MG-xxx ...]", file=sys.stderr)
        return 2
    for pid in ids:
        rerun_mg_vanilla(pid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
