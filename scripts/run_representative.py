"""Temporary orchestrator for the TRIZ Arena v2 trace-capture batch.

Runs 8 new MacGyver problems (MG-007..MG-014) and 2 re-runs of internal TB
problems with the new stream-json trace capture enabled. Stops gracefully on
QuotaExhaustedError so the dashboard can still be rebuilt with partial data.
"""

from __future__ import annotations

import sys
from pathlib import Path

TRIZ_ROOT = Path(__file__).resolve().parent.parent / "triz-engine"
sys.path.insert(0, str(TRIZ_ROOT))

from benchmark.external.run_external import run_macgyver  # noqa: E402
from benchmark.runner import QuotaExhaustedError, run_benchmark  # noqa: E402


def main() -> int:
    completed = {"macgyver": 0, "internal": 0}
    errors = []

    print("=" * 60)
    print("TRIZ Arena v2 — representative batch (trace capture ON)")
    print("=" * 60)

    print("\n[1/2] MacGyver (8 problems, MG-007..MG-014) with trace")
    try:
        mg = run_macgyver(limit=8, capture_trace=True, start_offset=6)
        completed["macgyver"] = mg.get("total_problems", 0)
    except QuotaExhaustedError as e:
        errors.append(f"MacGyver quota exhausted: {e}")
        print(f"  STOPPED: {e}", file=sys.stderr)
    except Exception as e:
        errors.append(f"MacGyver error: {e}")
        print(f"  ERROR: {e}", file=sys.stderr)

    print("\n[2/2] Internal TRIZBENCH re-runs (TB-07, TB-10) with trace")
    try:
        results = run_benchmark(
            problem_ids=["TB-07", "TB-10"],
            participant_names=["triz-engine", "vanilla-claude"],
            budget_usd=0.50,
            use_llm_judge=True,
            capture_trace=True,
        )
        completed["internal"] = len(
            [k for k, r in results.items() if r.get("status") == "success"]
        )
    except QuotaExhaustedError as e:
        errors.append(f"Internal quota exhausted: {e}")
        print(f"  STOPPED: {e}", file=sys.stderr)
    except Exception as e:
        errors.append(f"Internal error: {e}")
        print(f"  ERROR: {e}", file=sys.stderr)

    print("\n" + "=" * 60)
    print("Batch complete")
    print(f"  MacGyver problems completed: {completed['macgyver']}")
    print(f"  Internal TB results:         {completed['internal']}")
    if errors:
        print("\nErrors:")
        for e in errors:
            print(f"  - {e}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
