"""TRIZBENCH runner — invokes participants on problems and scores results.

Dynamically loads participant configs from benchmark/participants/*.json.
Generates portable MCP config at runtime. Structured failure handling.

Outputs per-problem result JSON to triz-engine/results/{participant}/{problem_id}.json.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from enum import Enum
from pathlib import Path

from benchmark.scorer import (
    compute_final_score,
    score_ci,
    score_cr,
    score_cr_llm,
    score_ifr,
    score_ps,
    score_sn,
    score_sn_llm,
)

ROOT = Path(__file__).parent.parent
PROBLEMS_DIR = ROOT / "benchmark" / "problems"
RESULTS_DIR = ROOT / "results"
PARTICIPANTS_DIR = ROOT / "benchmark" / "participants"
SYSTEM_PROMPT_PATH = ROOT / "commands" / "analyze.md"


class RunStatus(str, Enum):
    SUCCESS = "success"
    INFRA_FAILURE = "infra_failure"
    PARSE_FAILURE = "parse_failure"
    TIMEOUT_FAILURE = "timeout_failure"
    QUOTA_EXHAUSTED = "quota_exhausted"


class QuotaExhaustedError(RuntimeError):
    """Raised when Claude CLI reports usage quota is exhausted."""
    pass


def _generate_mcp_config() -> Path:
    """Generate a portable MCP config at runtime with resolved paths."""
    python_bin = sys.executable
    server_script = str(ROOT / "servers" / "triz_server.py")

    if not Path(python_bin).exists():
        raise RuntimeError(f"Python binary not found: {python_bin}")
    if not Path(server_script).exists():
        raise RuntimeError(f"MCP server script not found: {server_script}")

    config = {
        "mcpServers": {
            "triz-knowledge": {
                "command": python_bin,
                "args": [server_script],
                "env": {
                    "TRIZ_MODE": "full",
                    "TRIZ_SESSION_DIR": str(ROOT),
                },
            }
        }
    }

    config_dir = RESULTS_DIR
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / ".mcp-runtime.json"
    config_path.write_text(json.dumps(config, indent=2))
    return config_path


def load_participant_configs() -> dict[str, dict]:
    """Load all participant configs from benchmark/participants/*.json.

    Returns dict mapping participant name to its parsed config.
    Each config includes: name, type, invocation, features, and derived
    fields use_mcp, system_prompt_source, runner_module.
    """
    configs = {}
    for path in sorted(PARTICIPANTS_DIR.glob("*.json")):
        with open(path) as f:
            cfg = json.load(f)

        name = cfg["name"]
        ptype = cfg.get("type", "baseline")
        features = cfg.get("features", [])
        invocation = cfg.get("invocation", {})

        use_mcp = "mcp_tools" in features
        system_prompt_source = None
        runner_module = None

        if ptype == "plugin":
            system_prompt_source = "commands/analyze.md"
            use_mcp = True
        elif ptype == "ablation":
            args = invocation.get("args", [])
            for i, arg in enumerate(args):
                if arg in ("--system-prompt-file", "--system-prompt") and i + 1 < len(args):
                    system_prompt_source = args[i + 1]
                    break
        elif ptype == "baseline":
            args = invocation.get("args", [])
            for i, arg in enumerate(args):
                if arg == "--system-prompt" and i + 1 < len(args):
                    system_prompt_source = args[i + 1]
                    break
        elif ptype == "external":
            args = invocation.get("args", [])
            if args:
                runner_module = args[0]

        configs[name] = {
            **cfg,
            "use_mcp": use_mcp,
            "system_prompt_source": system_prompt_source,
            "runner_module": runner_module,
            "config_path": str(path),
        }

    return configs


def is_participant_available(cfg: dict) -> tuple[bool, str]:
    """Check if a participant can run in the current environment."""
    ptype = cfg.get("type", "baseline")
    invocation = cfg.get("invocation", {})

    if ptype == "external":
        required_env = invocation.get("requires_env", [])
        missing = [e for e in required_env if not os.environ.get(e)]
        if missing:
            return False, f"Missing env vars: {', '.join(missing)}"
        if cfg.get("runner_module"):
            runner_path = ROOT / cfg["runner_module"]
            if not runner_path.exists():
                return False, f"Runner script not found: {runner_path}"
    else:
        command = invocation.get("command", "claude")
        from shutil import which
        if not which(command):
            return False, f"Command not found: {command}"

    return True, "available"


def load_system_prompt(source: str | None = None) -> str | None:
    """Load a system prompt from file or return inline text.

    If source is a file path (contains / or ends with .md), load from file.
    Otherwise return the string as-is (inline system prompt).
    """
    if source is None:
        return None

    if "/" in source or source.endswith(".md"):
        path = ROOT / source
        if not path.exists():
            return None
        text = path.read_text()
        if text.startswith("---"):
            _, _, text = text.split("---", 2)
        return text.strip()

    return source


def load_problem(problem_id: str) -> dict:
    path = PROBLEMS_DIR / f"{problem_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Problem {problem_id} not found at {path}")
    return json.loads(path.read_text())


def format_prompt(problem: dict) -> str:
    return (
        f"Analyze this problem using TRIZ methodology.\n\n"
        f"## TRIZ Analysis Framework\n"
        f"1. **Identify the contradiction**: Is it technical (improving X worsens Y) "
        f"or physical (X must be both A and not-A)?\n"
        f"2. **Map to TRIZ parameters**: Select the best-matching parameter IDs (1-39) "
        f"for both the improving and worsening dimensions.\n"
        f"3. **Apply inventive principles**: Use the contradiction matrix or separation "
        f"principles to find the most relevant TRIZ principles.\n"
        f"4. **Generate a concrete solution**: Not generic TRIZ language — a domain-specific "
        f"solution that eliminates (not manages) the contradiction.\n"
        f"5. **Evaluate against IFR**: Does the solution minimize new components, cost, "
        f"and side-effects while being self-resolving?\n\n"
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
    mcp_config_path: Path | None = None,
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

    if use_mcp and mcp_config_path and mcp_config_path.exists():
        cmd.extend(["--mcp-config", str(mcp_config_path)])

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

                if envelope.get("is_error"):
                    error_text = envelope.get("result", "")
                    if "out of" in error_text.lower() and "usage" in error_text.lower():
                        raise QuotaExhaustedError(
                            f"Claude quota exhausted: {error_text}"
                        )

                text = envelope.get("result", "")
                if text:
                    return text
            except json.JSONDecodeError:
                if "API Error:" not in stdout[:50]:
                    return stdout

        last_error = result.stderr.strip() or stdout[:500]

        combined = (stdout + " " + result.stderr).lower()
        if "out of" in combined and "usage" in combined:
            raise QuotaExhaustedError(
                f"Claude quota exhausted (exit {result.returncode}): {last_error[:200]}"
            )

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


def invoke_external_runner(
    cfg: dict,
    prompt: str,
    system_prompt: str | None = None,
) -> str:
    """Invoke an external runner module (OpenAI, Gemini, etc.)."""
    runner_module = cfg.get("runner_module")
    if not runner_module:
        raise RuntimeError(f"No runner_module for external participant {cfg['name']}")

    module_path = ROOT / runner_module
    module_name = module_path.stem

    import importlib.util
    spec = importlib.util.spec_from_file_location(module_name, str(module_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load runner module: {module_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    if not hasattr(mod, "invoke"):
        raise RuntimeError(f"Runner module {module_path} has no invoke() function")

    return mod.invoke(prompt, system_prompt=system_prompt)


def parse_submission(raw_output: str) -> dict:
    """Extract the JSON submission block from model output."""
    json_match = re.search(r"```json\s*\n(.*?)\n```", raw_output, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(1))

    json_match = re.search(
        r"\{[^{}]*\"contradiction_type\"[^{}]*\}", raw_output, re.DOTALL
    )
    if json_match:
        return json.loads(json_match.group(0))

    raise ValueError("Could not extract JSON submission from model output")


def validate_submission(submission: dict) -> list[str]:
    """Validate submission against expected schema. Returns list of issues."""
    issues = []
    required_fields = [
        "contradiction_type", "triz_param_a", "triz_param_b",
        "principles_applied", "solution_summary",
    ]
    for field in required_fields:
        if field not in submission:
            issues.append(f"Missing required field: {field}")

    ct = submission.get("contradiction_type")
    if ct and ct not in ("technical", "physical"):
        issues.append(f"Invalid contradiction_type: {ct}")

    for param in ("triz_param_a", "triz_param_b"):
        val = submission.get(param)
        if val is not None and (not isinstance(val, int) or val < 1 or val > 39):
            issues.append(f"Invalid {param}: {val} (must be int 1-39)")

    principles = submission.get("principles_applied")
    if principles is not None and not isinstance(principles, list):
        issues.append(f"principles_applied must be a list, got {type(principles).__name__}")

    return issues


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
    cfg: dict,
    *,
    mcp_config_path: Path | None = None,
    budget_usd: float = 2.00,
    use_llm_judge: bool = True,
) -> dict:
    """Run a single problem for a participant and return scored result.

    Returns a result dict with 'status' field indicating success or failure type.
    Never raises — all errors are captured in the result.
    """
    problem = load_problem(problem_id)
    prompt = format_prompt(problem)
    sys_prompt = load_system_prompt(cfg.get("system_prompt_source"))

    t0 = time.time()

    try:
        if cfg.get("type") == "external":
            raw_output = invoke_external_runner(cfg, prompt, system_prompt=sys_prompt)
        else:
            raw_output = invoke_claude(
                prompt,
                use_mcp=cfg.get("use_mcp", False),
                mcp_config_path=mcp_config_path,
                system_prompt=sys_prompt,
                budget_usd=budget_usd,
            )
    except subprocess.TimeoutExpired as e:
        elapsed = time.time() - t0
        return _failure_result(
            problem, participant, RunStatus.TIMEOUT_FAILURE,
            f"Timed out after {elapsed:.0f}s", elapsed,
        )
    except QuotaExhaustedError:
        elapsed = time.time() - t0
        raise
    except RuntimeError as e:
        elapsed = time.time() - t0
        return _failure_result(
            problem, participant, RunStatus.INFRA_FAILURE,
            str(e), elapsed,
        )
    except Exception as e:
        elapsed = time.time() - t0
        return _failure_result(
            problem, participant, RunStatus.INFRA_FAILURE,
            f"{type(e).__name__}: {e}", elapsed,
        )

    elapsed = time.time() - t0

    try:
        submission = parse_submission(raw_output)
    except (ValueError, json.JSONDecodeError) as e:
        return _failure_result(
            problem, participant, RunStatus.PARSE_FAILURE,
            f"Parse error: {e}", elapsed, raw_output=raw_output,
        )

    validation_issues = validate_submission(submission)
    scores = score_submission(
        submission,
        problem["ground_truth"],
        problem_statement=problem["problem_statement"],
        use_llm_judge=use_llm_judge,
    )

    result = {
        "status": RunStatus.SUCCESS,
        "participant": participant,
        "problem_id": problem_id,
        "problem_title": problem["title"],
        "domain": problem["domain"],
        "submission": submission,
        "validation_issues": validation_issues,
        "scores": scores,
        "final_score": scores["final_score"],
        "raw_output": raw_output,
        "elapsed_seconds": round(elapsed, 1),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    _save_result(result)
    return result


def _failure_result(
    problem: dict,
    participant: str,
    status: RunStatus,
    error: str,
    elapsed: float,
    raw_output: str = "",
) -> dict:
    """Build a failure result dict."""
    result = {
        "status": status,
        "participant": participant,
        "problem_id": problem["id"],
        "problem_title": problem["title"],
        "domain": problem["domain"],
        "error": error,
        "final_score": None,
        "raw_output": raw_output,
        "elapsed_seconds": round(elapsed, 1),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _save_result(result)
    return result


def _save_result(result: dict) -> None:
    """Write result JSON to disk."""
    out_dir = RESULTS_DIR / result["participant"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{result['problem_id']}.json"
    serializable = {
        k: (v.value if isinstance(v, RunStatus) else v)
        for k, v in result.items()
    }
    out_path.write_text(json.dumps(serializable, indent=2))


def run_benchmark(
    problem_ids: list[str] | None = None,
    participant_names: list[str] | None = None,
    budget_usd: float = 2.00,
    use_llm_judge: bool = True,
) -> dict[tuple[str, str], dict]:
    """Run benchmark for specified problems and participants.

    Returns dict mapping (participant, problem_id) -> result dict.
    Results include 'status' and 'final_score' (None for failures).
    """
    all_configs = load_participant_configs()

    if problem_ids is None:
        problem_ids = sorted(p.stem for p in PROBLEMS_DIR.glob("TB-*.json"))

    if participant_names is None:
        participant_names = [
            name for name, cfg in all_configs.items()
            if cfg.get("type") != "external"
        ]

    mcp_config_path = None
    needs_mcp = any(
        all_configs.get(name, {}).get("use_mcp", False) for name in participant_names
    )
    if needs_mcp:
        mcp_config_path = _generate_mcp_config()
        print(f"  MCP config generated: {mcp_config_path}", file=sys.stderr)

    all_results: dict[tuple[str, str], dict] = {}
    skipped = []

    for pname in participant_names:
        cfg = all_configs.get(pname)
        if cfg is None:
            raise ValueError(
                f"Unknown participant: {pname}. "
                f"Available: {', '.join(sorted(all_configs.keys()))}"
            )

        available, reason = is_participant_available(cfg)
        if not available:
            skipped.append((pname, reason))
            print(f"  Skipping {pname}: {reason}", file=sys.stderr)
            continue

        quota_hit = False
        for pid in problem_ids:
            if quota_hit:
                break
            print(f"  Running {pname} on {pid}...", file=sys.stderr)
            try:
                result = run_problem(
                    pid, pname, cfg,
                    mcp_config_path=mcp_config_path,
                    budget_usd=budget_usd,
                    use_llm_judge=use_llm_judge,
                )
            except QuotaExhaustedError as e:
                print(f"    QUOTA EXHAUSTED: {e}", file=sys.stderr)
                print("    Stopping benchmark — quota needs to reset.", file=sys.stderr)
                quota_hit = True
                break

            all_results[(pname, pid)] = result

            status = result["status"]
            if isinstance(status, RunStatus):
                status = status.value

            if status == RunStatus.SUCCESS.value:
                scores = result["scores"]
                print(
                    f"    Score: {result['final_score']:.1f} "
                    f"(CI={scores['ci']:.0f} PS={scores['ps']:.0f} "
                    f"SN={scores['sn']:.0f} CR={scores['cr']:.0f} "
                    f"IFR={scores['ifr']:.0f}) "
                    f"[{result['elapsed_seconds']:.0f}s]",
                    file=sys.stderr,
                )
            else:
                print(
                    f"    {status}: {result.get('error', 'unknown')}",
                    file=sys.stderr,
                )
        if quota_hit:
            break

    if skipped:
        print(f"\n  Skipped {len(skipped)} participant(s):", file=sys.stderr)
        for name, reason in skipped:
            print(f"    - {name}: {reason}", file=sys.stderr)

    return all_results


def extract_scores(
    results: dict[tuple[str, str], dict],
) -> dict[tuple[str, str], float]:
    """Extract final scores from results, excluding non-success runs."""
    return {
        key: r["final_score"]
        for key, r in results.items()
        if r.get("status") in (RunStatus.SUCCESS, RunStatus.SUCCESS.value)
        and r.get("final_score") is not None
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TRIZBENCH runner")
    parser.add_argument(
        "--problems", nargs="+", default=None,
        help="Problem IDs to run (default: all TB-*)",
    )
    parser.add_argument(
        "--participants", nargs="+", default=None,
        help="Participant names to run (default: all non-external)",
    )
    parser.add_argument(
        "--budget", type=float, default=2.00,
        help="Max USD budget per problem (default: 2.00)",
    )
    parser.add_argument(
        "--no-llm-judge", action="store_true",
        help="Disable LLM-as-judge for SN/CR (use deterministic scoring)",
    )
    args = parser.parse_args()

    results = run_benchmark(
        problem_ids=args.problems,
        participant_names=args.participants,
        budget_usd=args.budget,
        use_llm_judge=not args.no_llm_judge,
    )

    scores = extract_scores(results)

    print("\n=== RESULTS ===")
    for (participant, problem_id), score in sorted(scores.items()):
        print(f"  {participant:20s} | {problem_id} | {score:.1f}")

    failures = {
        k: v for k, v in results.items()
        if v.get("status") not in (RunStatus.SUCCESS, RunStatus.SUCCESS.value)
    }
    if failures:
        print(f"\n=== FAILURES ({len(failures)}) ===")
        for (participant, problem_id), result in sorted(failures.items()):
            status = result.get("status", "unknown")
            if isinstance(status, RunStatus):
                status = status.value
            print(f"  {participant:20s} | {problem_id} | {status}: {result.get('error', '')}")
