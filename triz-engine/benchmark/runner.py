"""TRIZBENCH runner — invokes participants on problems and scores results.

Supports two participant modes:
  - triz-engine: Claude CLI with TRIZ MCP tools and system prompt
  - vanilla-claude: Claude CLI with no system prompt or tools

Outputs per-problem result JSON to triz-engine/results/{participant}/{problem_id}.json.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from benchmark.scorer import compute_final_score, score_ci, score_ifr, score_ps

ROOT = Path(__file__).parent.parent
PROBLEMS_DIR = ROOT / "benchmark" / "problems"
RESULTS_DIR = ROOT / "results"
MCP_CONFIG = ROOT / "mcp-standalone.json"
SYSTEM_PROMPT_PATH = ROOT / "commands" / "analyze.md"


def load_problem(problem_id: str) -> dict:
    path = PROBLEMS_DIR / f"{problem_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Problem {problem_id} not found at {path}")
    return json.loads(path.read_text())


def format_prompt(problem: dict) -> str:
    return (
        f"Analyze this problem using TRIZ methodology. "
        f"You MUST return your analysis in the following JSON format at the end of your response, "
        f"enclosed in ```json code fences:\n\n"
        f"```json\n"
        f'{{"contradiction_type": "technical|physical",\n'
        f' "triz_param_a": <int 1-39>,\n'
        f' "triz_param_b": <int 1-39>,\n'
        f' "principles_applied": [<list of int principle IDs>],\n'
        f' "solution_summary": "<2-3 sentence solution>",\n'
        f' "ifr_score": <int 0-4>,\n'
        f' "contradiction_resolution": "eliminates|reduces|manages|fails",\n'
        f' "solution_novelty": "non_obvious|novel_combination|standard|restatement"}}\n'
        f"```\n\n"
        f"PROBLEM ({problem['domain']}: {problem['title']}):\n\n"
        f"{problem['problem_statement']}"
    )


def invoke_claude(
    prompt: str,
    *,
    use_mcp: bool = False,
    system_prompt: str | None = None,
    model: str = "haiku",
    budget_usd: float = 2.00,
    timeout_seconds: int = 180,
    retries: int = 3,
) -> str:
    """Call Claude Code CLI in print mode and return the text result.

    Uses --output-format json for reliable parsing.
    Retries on transient API errors with exponential backoff.
    """
    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        "--output-format", "json",
        "--max-budget-usd", str(budget_usd),
        "--dangerously-skip-permissions",
    ]

    if use_mcp and MCP_CONFIG.exists():
        cmd.extend(["--mcp-config", str(MCP_CONFIG)])

    if system_prompt:
        cmd.extend(["--append-system-prompt", system_prompt])

    last_error = None
    for attempt in range(retries + 1):
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
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
                if "API Error:" not in stdout[:50]:
                    return stdout

        last_error = result.stderr.strip() or stdout[:500]
        if attempt < retries:
            wait = 3 * (2 ** attempt)
            print(
                f"    Attempt {attempt + 1}/{retries + 1} failed, retrying in {wait}s...",
                file=sys.stderr,
            )
            time.sleep(wait)

    raise RuntimeError(
        f"Claude CLI failed after {retries + 1} attempts: {last_error}"
    )


def parse_submission(raw_output: str) -> dict:
    """Extract the JSON submission block from Claude's output."""
    json_match = re.search(r"```json\s*\n(.*?)\n```", raw_output, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))

    json_match = re.search(r"\{[^{}]*\"contradiction_type\"[^{}]*\}", raw_output, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(0))

    raise ValueError("Could not extract JSON submission from Claude output")


def score_submission(
    submission: dict,
    ground_truth: dict,
    problem_statement: str = "",
    use_llm_judge: bool = True,
) -> dict:
    """Score a parsed submission against ground truth.

    When use_llm_judge is True, SN and CR use LLM-as-judge via Claude CLI.
    Falls back to deterministic scoring on failure or when disabled.
    """
    ci = score_ci(submission, ground_truth)
    ps = score_ps(
        submission.get("principles_applied", []),
        ground_truth.get("target_principles", []),
    )

    solution_text = submission.get("solution_summary", "")
    ifr_val = submission.get("ifr_score", 0)

    from benchmark.scorer import score_cr, score_sn, score_cr_llm, score_sn_llm

    gt_description = json.dumps({
        "contradiction_type": ground_truth.get("contradiction_type"),
        "parameter_a": ground_truth.get("parameter_a"),
        "parameter_b": ground_truth.get("parameter_b"),
        "target_principles": ground_truth.get("target_principles"),
    })

    if use_llm_judge and problem_statement:
        sn, sn_level = score_sn_llm(problem_statement, solution_text, gt_description)
        cr, cr_level = score_cr_llm(problem_statement, solution_text, gt_description)
        judge_mode = "llm"
    else:
        cr_level = submission.get("contradiction_resolution", "fails")
        sn_level = submission.get("solution_novelty", "restatement")
        sn = score_sn(sn_level)
        cr = score_cr(cr_level)
        judge_mode = "deterministic"

    ifr = score_ifr(ifr_val)
    final = compute_final_score(ci, ps, sn, cr, ifr)

    return {
        "ci": ci,
        "ps": ps,
        "sn": sn,
        "cr": cr,
        "ifr": ifr,
        "final_score": final,
        "judge_mode": judge_mode,
        "dimensions": {
            "ci_raw": ci,
            "ps_raw": ps,
            "sn_raw": sn,
            "sn_level": sn_level,
            "cr_raw": cr,
            "cr_level": cr_level,
            "ifr_raw": ifr,
            "ifr_value": ifr_val,
        },
    }


def run_problem(
    problem_id: str,
    participant: str,
    *,
    use_mcp: bool = True,
    system_prompt: str | None = None,
    budget_usd: float = 2.00,
) -> dict:
    """Run a single problem for a participant and return scored result."""
    problem = load_problem(problem_id)
    prompt = format_prompt(problem)

    t0 = time.time()
    raw_output = invoke_claude(
        prompt,
        use_mcp=use_mcp,
        system_prompt=system_prompt,
        budget_usd=budget_usd,
    )
    elapsed = time.time() - t0

    submission = parse_submission(raw_output)
    scores = score_submission(
        submission,
        problem["ground_truth"],
        problem_statement=problem["problem_statement"],
        use_llm_judge=use_mcp,
    )

    result = {
        "participant": participant,
        "problem_id": problem_id,
        "problem_title": problem["title"],
        "domain": problem["domain"],
        "submission": submission,
        "scores": scores,
        "final_score": scores["final_score"],
        "raw_output": raw_output,
        "elapsed_seconds": round(elapsed, 1),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    out_dir = RESULTS_DIR / participant
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{problem_id}.json"
    out_path.write_text(json.dumps(result, indent=2))

    return result


def load_system_prompt() -> str:
    """Load the analyze.md system prompt, stripping YAML frontmatter."""
    text = SYSTEM_PROMPT_PATH.read_text()
    if text.startswith("---"):
        _, _, text = text.split("---", 2)
    return text.strip()


PARTICIPANTS = {
    "triz-engine": {"use_mcp": True, "system_prompt_fn": load_system_prompt},
    "vanilla-claude": {"use_mcp": False, "system_prompt_fn": lambda: None},
}


def run_benchmark(
    problem_ids: list[str] | None = None,
    participant_names: list[str] | None = None,
    budget_usd: float = 2.00,
) -> dict[tuple[str, str], float]:
    """Run benchmark for specified problems and participants.

    Returns dict mapping (participant, problem_id) -> final_score.
    """
    if problem_ids is None:
        problem_ids = sorted(
            p.stem for p in PROBLEMS_DIR.glob("TB-*.json")
        )
    if participant_names is None:
        participant_names = list(PARTICIPANTS.keys())

    all_scores: dict[tuple[str, str], float] = {}

    for pname in participant_names:
        cfg = PARTICIPANTS.get(pname)
        if cfg is None:
            print(f"Unknown participant: {pname}, skipping", file=sys.stderr)
            continue

        sys_prompt = cfg["system_prompt_fn"]()

        for pid in problem_ids:
            print(f"  Running {pname} on {pid}...", file=sys.stderr)
            try:
                result = run_problem(
                    pid,
                    pname,
                    use_mcp=cfg["use_mcp"],
                    system_prompt=sys_prompt,
                    budget_usd=budget_usd,
                )
                all_scores[(pname, pid)] = result["final_score"]
                print(
                    f"    Score: {result['final_score']:.1f} "
                    f"(CI={result['scores']['ci']:.0f} PS={result['scores']['ps']:.0f} "
                    f"SN={result['scores']['sn']:.0f} CR={result['scores']['cr']:.0f} "
                    f"IFR={result['scores']['ifr']:.0f}) "
                    f"[{result['elapsed_seconds']:.0f}s]",
                    file=sys.stderr,
                )
            except Exception as e:
                print(f"    FAILED: {e}", file=sys.stderr)
                all_scores[(pname, pid)] = 0.0

    return all_scores


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TRIZBENCH runner")
    parser.add_argument(
        "--problems", nargs="+", default=None,
        help="Problem IDs to run (default: all)",
    )
    parser.add_argument(
        "--participants", nargs="+", default=None,
        help="Participant names to run (default: all)",
    )
    parser.add_argument(
        "--budget", type=float, default=2.00,
        help="Max USD budget per problem (default: 2.00)",
    )
    args = parser.parse_args()

    scores = run_benchmark(
        problem_ids=args.problems,
        participant_names=args.participants,
        budget_usd=args.budget,
    )

    print("\n=== RESULTS ===")
    for (participant, problem_id), score in sorted(scores.items()):
        print(f"  {participant:20s} | {problem_id} | {score:.1f}")
