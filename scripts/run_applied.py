"""Run the two "Applied" inventive problems with trace capture.

Demonstrates the installed triz-engine plugin solving real, open-ended creative
problems (not patents, not benchmarks) side-by-side with vanilla Claude.

Vanilla invocation: `claude -p <problem>` (plain Haiku 4.5, no plugin).
TRIZ invocation:    `claude -p "/triz-engine:analyze <problem>"` — routes
                    through the installed plugin's slash command, which
                    auto-loads the contradiction-/solution-/evaluator-agent
                    pipeline and the triz-knowledge MCP server.

Results are written to triz-engine/results/applied/APP-XX.json with full
stream-json traces for the dashboard "Applied" section.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TRIZ_ROOT = REPO_ROOT / "triz-engine"
sys.path.insert(0, str(TRIZ_ROOT))

from benchmark.runner import (  # noqa: E402
    QuotaExhaustedError,
    invoke_claude,
)

APPLIED_DIR = TRIZ_ROOT / "benchmark" / "applied"
RESULTS_DIR = TRIZ_ROOT / "results" / "applied"
PROBLEMS_FILE = APPLIED_DIR / "problems.json"

VANILLA_TIMEOUT = 180
TRIZ_TIMEOUT = 420
BUDGET_USD = 1.00
PLUGIN_SLUG = "triz-engine@triz-arena"


def _cli(*args: str) -> None:
    """Run a claude CLI command and swallow its output (best effort)."""
    try:
        subprocess.run(
            ["claude", *args],
            capture_output=True,
            text=True,
            timeout=30,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except Exception:  # noqa: BLE001
        pass


@contextlib.contextmanager
def plugin_disabled():
    """Temporarily disable the TRIZ plugin so vanilla runs are truly plugin-free."""
    print("    (disabling triz-engine plugin for vanilla run)", flush=True)
    _cli("plugin", "disable", PLUGIN_SLUG)
    try:
        yield
    finally:
        print("    (re-enabling triz-engine plugin)", flush=True)
        _cli("plugin", "enable", PLUGIN_SLUG)


def load_problems() -> list[dict]:
    data = json.loads(PROBLEMS_FILE.read_text(encoding="utf-8"))
    return data.get("problems") or []


def build_prompt(problem: dict) -> str:
    return (
        f"Solve this inventive problem. Identify the core contradiction,"
        f" apply the most relevant TRIZ principles, and propose a concrete"
        f" engineering solution that eliminates (not merely reduces) the"
        f" contradiction.\n\n"
        f"PROBLEM ({problem['domain']}: {problem['title']}):\n\n"
        f"{problem['problem_statement']}"
    )


def run_vanilla(prompt: str) -> tuple[str, list[dict], str, float]:
    t0 = time.time()
    result = invoke_claude(
        prompt,
        use_mcp=False,
        system_prompt=None,
        model="haiku",
        budget_usd=BUDGET_USD,
        timeout_seconds=VANILLA_TIMEOUT,
        capture_trace=True,
    )
    elapsed = time.time() - t0
    text, trace, status = result
    return text, trace, status, elapsed


def run_triz(prompt: str) -> tuple[str, list[dict], str, float]:
    slash_prompt = f"/triz-engine:analyze {prompt}"
    t0 = time.time()
    result = invoke_claude(
        slash_prompt,
        use_mcp=False,
        system_prompt=None,
        model="haiku",
        budget_usd=BUDGET_USD,
        timeout_seconds=TRIZ_TIMEOUT,
        capture_trace=True,
    )
    elapsed = time.time() - t0
    text, trace, status = result
    return text, trace, status, elapsed


def run_one(problem: dict) -> dict:
    print(f"\n== {problem['id']} — {problem['title']} ==", flush=True)
    prompt = build_prompt(problem)

    print("  [vanilla] invoking claude -p ...", flush=True)
    try:
        with plugin_disabled():
            v_text, v_trace, v_status, v_elapsed = run_vanilla(prompt)
        print(f"  [vanilla] done: {len(v_text)} chars, {len(v_trace)} trace events, {v_elapsed:.1f}s ({v_status})")
    except QuotaExhaustedError:
        raise
    except Exception as exc:
        print(f"  [vanilla] FAILED: {exc}", file=sys.stderr)
        v_text, v_trace, v_status, v_elapsed = f"ERROR: {exc}", [], "error", 0.0

    print("  [triz]    invoking /triz-engine:analyze ...", flush=True)
    try:
        t_text, t_trace, t_status, t_elapsed = run_triz(prompt)
        print(f"  [triz]    done: {len(t_text)} chars, {len(t_trace)} trace events, {t_elapsed:.1f}s ({t_status})")
    except QuotaExhaustedError:
        raise
    except Exception as exc:
        print(f"  [triz]    FAILED: {exc}", file=sys.stderr)
        t_text, t_trace, t_status, t_elapsed = f"ERROR: {exc}", [], "error", 0.0

    return {
        "problem_id": problem["id"],
        "title": problem["title"],
        "domain": problem["domain"],
        "problem_statement": problem["problem_statement"],
        "invocation": {
            "vanilla": "claude -p --model haiku",
            "triz": "claude -p \"/triz-engine:analyze ...\" --model haiku",
            "models": {"participants": "claude-haiku-4-5", "judge": "n/a (qualitative)"},
        },
        "vanilla_output": v_text,
        "vanilla_trace": v_trace,
        "vanilla_trace_status": v_status,
        "vanilla_elapsed_seconds": v_elapsed,
        "triz_output": t_text,
        "triz_trace": t_trace,
        "triz_trace_status": t_status,
        "triz_elapsed_seconds": t_elapsed,
    }


def main() -> int:
    if not PROBLEMS_FILE.exists():
        print(f"FATAL: missing {PROBLEMS_FILE}", file=sys.stderr)
        return 2
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    problems = load_problems()
    print("=" * 64)
    print(f"TRIZ Arena — Applied runs ({len(problems)} problems)")
    print("=" * 64)

    completed = 0
    for problem in problems:
        out_path = RESULTS_DIR / f"{problem['id']}.json"
        try:
            record = run_one(problem)
        except QuotaExhaustedError as exc:
            print(f"\n!! Quota exhausted: {exc}", file=sys.stderr)
            print(f"!! Stopping after {completed} problem(s).", file=sys.stderr)
            return 1
        out_path.write_text(
            json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        completed += 1
        print(f"  Wrote {out_path}")

    print(f"\nDone. Completed {completed}/{len(problems)} applied problems.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
