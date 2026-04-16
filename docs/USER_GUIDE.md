# TRIZ Engine User Guide

Comprehensive reference for every feature of the TRIZ Engine Claude Code plugin.

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Commands](#commands)
   - [/triz-engine:analyze](#trizanalyze)
   - [/triz-engine:principles](#trizprinciples)
   - [/triz-engine:matrix](#trizmatrix)
   - [/triz-engine:ifr](#trizifr)
   - [/triz-engine:ariz](#trizariz)
   - [/triz-engine:benchmark](#trizbenchmark)
4. [MCP Tools](#mcp-tools)
5. [Agent Pipeline](#agent-pipeline)
6. [Auto-Activation Skill](#auto-activation-skill)
7. [Hooks](#hooks)
8. [Running Benchmarks](#running-benchmarks)
   - [Internal TRIZBENCH](#internal-trizbench)
   - [External Benchmarks](#external-benchmarks)
   - [Adding Participants](#adding-participants)
9. [TRIZ Arena and ELO](#triz-arena-and-elo)
10. [Standalone MCP Server](#standalone-mcp-server)
11. [Troubleshooting](#troubleshooting)

---

## Overview

TRIZ Engine is a Claude Code plugin that brings Altshuller's Theory of Inventive Problem Solving into your development workflow. It provides:

- **6 slash commands** for different levels of TRIZ analysis
- **8 MCP tools** exposing the full TRIZ knowledge base (40 principles, 39x39 contradiction matrix, separation strategies)
- **3-agent pipeline** that automates contradiction identification, solution generation, and evaluation
- **Auto-activation skill** that detects contradictions in natural conversation
- **Benchmark suite** (TRIZBENCH) with 12 internal problems and adapters for 3 external creative benchmarks
- **TRIZ Arena** with Bradley-Terry ELO rankings

## Installation

### Requirements

| For | You need |
|-----|----------|
| Using the plugin in Claude Code | [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) (`claude --version`) |
| Running the bundled MCP server (auto on plugin install) | [`uv`](https://docs.astral.sh/uv/) (PEP 723 inline-deps launcher) |
| Running benchmarks / editing code | Python 3.11+, `git` |
| CresOWLve dataset (optional) | `pip install datasets` |

The plugin launches its `triz-knowledge` MCP server via
`uv run --script servers/triz_server.py` &mdash; `uv` auto-provisions `fastmcp`
and other deps declared in a PEP 723 script header, so you don't need a
pre-configured Python environment. Install `uv` via
`curl -LsSf https://astral.sh/uv/install.sh | sh`.

### Models used

Every benchmark run in TRIZ Arena uses:

- **Participants** (both TRIZ Engine plugin and Vanilla Claude baseline) &mdash;
  `claude -p --model haiku` (Claude **Haiku 4.5**). Same model on both sides so
  the only variable is the plugin itself.
- **LLM-as-judge** for Solution Novelty, Contradiction Resolution, and the
  MacGyver 4-level rubric &mdash; `claude -p --model sonnet`
  (Claude **Sonnet 4.6**, the stronger reasoning model).
- Trace capture (`--output-format stream-json --verbose`) is used selectively
  on representative problems to record the full MCP-call timeline shown in the
  "Live Demos" and "Applied" sections of the dashboard.

### 1. Install as a Claude Code plugin (primary path)

This is how end-users should install TRIZ Engine. The plugin ships slash
commands, the 3-agent pipeline, the `triz-knowledge` MCP server, and hooks —
all auto-loaded in every Claude Code session.

```bash
git clone https://github.com/SharathSPhD/triz-engine.git
cd triz-engine

# Register the local marketplace (the .claude-plugin/marketplace.json at repo root)
claude plugin marketplace add ./

# Install the plugin (scope defaults to "user")
claude plugin install triz-engine@triz-arena
```

Or, once the marketplace is published upstream:

```bash
claude plugin marketplace add SharathSPhD/triz-engine
claude plugin install triz-engine@triz-arena
```

### 2. Verifying installation

A quick checklist to confirm the plugin is fully active:

```bash
# A. Plugin registered and enabled
claude plugin list | grep -A2 triz-engine
# Expected: Status: ✔ enabled

# B. Slash command fires the full agent pipeline
claude -p "/triz-engine:analyze How do we reduce drone weight without losing flight time?" \
  --model haiku --dangerously-skip-permissions --output-format json \
  | jq '{turns: .num_turns, ok: (.is_error | not)}'
# Expected: {"turns": 3+, "ok": true}   <- multiple turns = multi-agent pipeline fired

# C. Validate manifests (optional)
claude plugin validate ./            # marketplace.json
claude plugin validate triz-engine/  # plugin.json
```

If the slash command isn't found, run `claude plugin enable triz-engine@triz-arena`.

### 3. Dev setup (only needed for benchmarks or plugin editing)

```bash
cd triz-engine
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pip install -e ".[benchmark]"   # optional: external benchmarks
pip install datasets            # optional: CresOWLve

pytest tests/ --ignore=tests/test_mcp_live.py --ignore=tests/test_server.py
# Expected: 295 passed (plugin + benchmark suites; mcp live tests need fastmcp)
```

---

## Commands

### /triz-engine:analyze

**The primary entry point.** Runs a complete TRIZ analysis cycle on any problem.

**What it does:**
1. Extracts the core contradiction from your problem description
2. Classifies it as technical (improving X worsens Y) or physical (X must be both A and not-A)
3. Maps both sides to TRIZ engineering parameters (1-39)
4. Looks up the Contradiction Matrix for recommended principles
5. Retrieves full principle definitions with domain-specific examples
6. Generates concrete solution sketches
7. Scores solutions against the Ideal Final Result

**Input formats accepted:**
- Free-form text describing a trade-off
- Structured contradiction: "Improving A worsens B"
- Code diff or architecture description with a tension

**Example:**

```
/triz-engine:analyze "Our distributed cache reduces API latency by 10x,
but cache invalidation causes stale reads and the cache nodes
add operational complexity and memory costs"
```

**Output:** A structured analysis including contradiction type, TRIZ parameters, recommended principles, solution sketches ranked by IFR score, and a top recommendation.

**Software domain mappings:**

| Software concept | TRIZ Parameter |
|-----------------|---------------|
| Speed / throughput / performance | #9 Speed |
| Reliability / uptime / availability | #27 Reliability |
| Accuracy / quality / precision | #28 Measurement accuracy |
| Complexity / maintainability | #36 Device complexity |
| Memory / storage | #23 Loss of substance |
| Security / compliance | #30 External harm |

---

### /triz-engine:principles

Browse, search, and explore the 40 Inventive Principles.

**Modes:**
- **By ID:** `/triz-engine:principles 1` — full details for Principle #1 (Segmentation)
- **By keyword:** `/triz-engine:principles "feedback"` — search for principles involving feedback
- **By domain:** `/triz-engine:principles domain:software` — filter to software-relevant principles
- **Browse all:** `/triz-engine:principles` — overview of all 40 principles

**Output for each principle includes:**
- ID, name, and full description
- Numbered sub-actions (specific techniques)
- Software/systems engineering patterns
- Classical and modern examples
- Category classification (structural, temporal, behavioral, etc.)

---

### /triz-engine:matrix

Navigate the 39x39 Contradiction Matrix interactively.

**Workflow:**
1. Specify the parameter you want to **improve** (e.g. "Speed")
2. Specify the parameter that **worsens** (e.g. "Reliability")
3. The command looks up the matrix cell and retrieves recommended principles
4. Each principle is displayed with full details and domain-specific applications

**Example:**

```
/triz-engine:matrix
> Improving: Speed (#9)
> Worsening: Reliability (#27)
> Recommended principles: #11 (Beforehand Cushioning), #35 (Parameter Changes), ...
```

---

### /triz-engine:ifr

Formulate the Ideal Final Result for your problem.

The IFR is Altshuller's technique for defining the theoretically perfect solution before accepting compromises. A good IFR satisfies four criteria:

1. **No additional components** — uses only existing system elements
2. **No additional cost** — zero incremental expense
3. **No side-effects** — creates no new problems
4. **Self-solving** — the system resolves its contradiction automatically

**Workflow:**
1. Describe your system and its contradiction
2. The command guides you to fill in: *"The ideal system would [function] by itself, without [harm], using only [existing resources]."*
3. Reality gap analysis identifies what prevents the IFR
4. Gaps map directly to where inventive principles should be applied

**When to use:** Before or after `/triz-engine:analyze`. Using IFR first prevents premature compromise. Using it after analysis validates whether solutions approach the ideal.

---

### /triz-engine:ariz

Full ARIZ-85C step-by-step analysis for deeply intractable problems.

**When to use ARIZ instead of `/triz-engine:analyze`:**
- Direct matrix lookup yields no satisfying principles
- The problem has nested or compound contradictions
- Standard analysis produces only incremental improvements
- You need structured guidance through problem reformulation

**The 9 parts of ARIZ-85C:**

| Part | Purpose |
|------|---------|
| 1. Problem Analysis | State the mini-problem, identify conflicting pair, formulate technical contradiction |
| 2. Problem Model | Identify operational zone and time, formulate physical contradiction |
| 3. IFR and Physical Contradiction | Apply the IFR to the physical contradiction |
| 4. Mobilization of Resources | Catalog substance-field resources available in the system and supersystem |
| 5. Apply Knowledge Base | Systematically apply inventive standards, principles, and effects |
| 6. Change or Replace Problem | If unsolved, reformulate and re-enter from Part 1 |
| 7. Analysis of Solution | Verify the solution resolves both technical and physical contradictions |
| 8. Application of Solution | Plan implementation and identify secondary problems |
| 9. Analysis of Problem-Solving Process | Reflect on the process for future improvement |

The command guides you through each part sequentially. It waits for your response at each step.

---

### /triz-engine:benchmark

Run the TRIZBENCH evaluation suite.

**Workflow:**
1. Select problems (TB-01 to TB-12 or a subset)
2. Run the full analysis pipeline on each
3. Score against ground truth on 5 dimensions
4. Generate an aggregate report

See [Running Benchmarks](#running-benchmarks) for detailed CLI usage.

---

## MCP Tools

The `triz-knowledge` MCP server exposes 8 tools. These are called automatically by commands and agents, but you can also use them directly.

### get_principle

Fetch a single inventive principle by ID (1-40).

**Parameters:** `id` (integer, 1-40)

**Returns:** Name, description, sub-actions, software patterns, examples, categories.

### search_principles

Keyword search across all 40 principles.

**Parameters:** `query` (string), `domain` (optional: "software", "hardware", "process", "business")

**Returns:** List of matching principles with relevance scores.

### lookup_matrix

Look up the Contradiction Matrix for a parameter pair.

**Parameters:** `improving` (integer, 1-39), `worsening` (integer, 1-39)

**Returns:** List of recommended principle IDs for that matrix cell.

### list_parameters

List all 39 TRIZ engineering parameters.

**Returns:** Array of `{id, name, description}` for parameters 1-39.

### get_separation_principles

Get separation strategies for physical contradictions.

**Returns:** Four separation approaches:
- **Separation in Time** — the property has value A at time T1 and value not-A at time T2
- **Separation in Space** — the property has value A in zone Z1 and not-A in zone Z2
- **Separation by Condition** — the property has value A under condition C and not-A otherwise
- **Separation by System Level** — the part has value A, the whole has value not-A (or vice versa)

### suggest_parameters

Map a natural-language description to candidate TRIZ parameters.

**Parameters:** `description` (string, e.g. "how fast data is processed")

**Returns:** Ranked list of matching TRIZ parameter IDs with confidence scores.

### score_solution

Score a proposed solution against IFR criteria (0-4 scale).

**Parameters:** `solution` (string), `problem_context` (string)

**Returns:** Score (0-4) with per-criterion breakdown.

### log_session_entry

Append a structured entry to the session innovation ledger at `.triz/session.jsonl`.

**Parameters:** `entry` (object with type, data, and optional metadata)

---

## Agent Pipeline

The plugin includes three specialized agents that form a pipeline:

### contradiction-agent

**Purpose:** Extract, classify, and structure contradictions.

**Process:**
1. Extracts the core tension from the problem statement
2. Classifies as technical or physical contradiction
3. Maps both sides to TRIZ parameters using `list_parameters` and `suggest_parameters`
4. For technical: looks up the matrix via `lookup_matrix`
5. For physical: retrieves separation principles via `get_separation_principles`
6. Outputs a structured **contradiction card** (JSON)

### solution-agent

**Purpose:** Generate concrete, domain-adapted solution sketches.

**Input:** A contradiction card from contradiction-agent.

**Process:**
1. Retrieves full principle definitions via `get_principle`
2. For each recommended principle, generates a domain-specific solution sketch
3. Scores each sketch against IFR criteria via `score_solution`
4. Ranks solutions by IFR score
5. Outputs a **solution portfolio** with the top recommendation highlighted

### evaluator-agent

**Purpose:** Score solutions on a strict 4x25-point quality rubric.

**Rubric:**

| Dimension | 25 pts | 17 pts | 8 pts | 0 pts |
|-----------|--------|--------|-------|-------|
| Contradiction Resolution | Eliminates contradiction | Significantly reduces | Manages/mitigates | Fails to address |
| Novelty | Non-obvious inventive insight | Novel combination of known elements | Standard application | Restates the problem |
| Feasibility | Immediately implementable | Needs minor research | Major unknowns | Physically impossible |
| IFR Alignment | Meets all 4 IFR criteria | Meets 3 criteria | Meets 1-2 criteria | Meets none |

---

## Auto-Activation Skill

The `triz-core` skill automatically activates when it detects contradiction-related language in your conversation. Trigger keywords include:

`contradiction`, `trade-off`, `tradeoff`, `tension`, `vs`, `versus`, `dilemma`, `improves but`, `worsens`, `can't have both`

When triggered, the skill:
1. Acknowledges the contradiction explicitly
2. Frames it in TRIZ terms
3. Suggests running `/triz-engine:analyze` for full analysis
4. Provides a quick principle recommendation using MCP tools

The skill will not activate for simple questions or non-contradictory problems.

---

## Hooks

### PreToolUse

Before each tool call, the hook validates parameters and ensures the tool is being used in a TRIZ-appropriate context.

### PostToolUse

After tool calls, the hook enriches responses with additional context (e.g. related principles, domain examples) and logs tool usage to the session ledger.

---

## Running Benchmarks

### Internal TRIZBENCH

The internal benchmark includes 12 problems (TB-01 to TB-12) spanning diverse engineering domains.

**Run from the command line:**

```bash
cd triz-engine

# Run specific problems for specific participants
python -m benchmark.runner --problems TB-01 TB-02 TB-03 \
  --participants triz-engine vanilla-claude

# Run all 12 problems for triz-engine
python -m benchmark.runner --problems TB-01 TB-02 TB-03 TB-04 TB-05 TB-06 \
  TB-07 TB-08 TB-09 TB-10 TB-11 TB-12 --participants triz-engine
```

**Participants** are configured in `benchmark/participants/*.json`. Available participants:
- `triz-engine` — Full plugin with MCP tools
- `vanilla-claude` — Baseline Claude without TRIZ tools
- `triz-prompt-only` — TRIZ system prompt but no MCP tools
- `cot-augmented` — Chain-of-thought enhanced
- `tot-augmented` — Tree-of-thought enhanced

**Results** are saved to `results/{participant}/{problem_id}.json`.

### External Benchmarks

Three external benchmarks test creative and inventive reasoning:

```bash
cd triz-engine

# Run all three
python -m benchmark.external.run_external --limit 10

# Run specific benchmarks
python -m benchmark.external.run_external --benchmarks trizbench --limit 20
python -m benchmark.external.run_external --benchmarks macgyver --limit 10
python -m benchmark.external.run_external --benchmarks cresowlve --limit 10
```

**Published TRIZBENCH** tests patent contradiction analysis using real patent data with ground-truth TRIZ parameters and inventive principles. Scoring is based on:
- Contradiction type accuracy (technical vs physical)
- Parameter identification accuracy (exact match of TRIZ parameter IDs)
- Principle F1 score (precision and recall against ground-truth principles)

**MacGyver** tests constrained creative problem-solving. Problems describe everyday situations where you must solve a problem using only available objects. Scoring uses an LLM judge (Sonnet) to evaluate solution quality.

**CresOWLve** tests lateral and divergent thinking with creative reasoning questions. Scoring checks if the candidate answer matches the correct answer (via LLM judge or substring matching).

### Adding Participants

Create a JSON file in `benchmark/participants/`:

```json
{
  "name": "my-participant",
  "type": "baseline",
  "description": "Custom participant description",
  "invocation": {
    "command": "claude",
    "args": ["--model", "haiku"]
  },
  "features": []
}
```

Participant types:
- `plugin` — Uses MCP tools (sets `use_mcp: true` automatically)
- `baseline` — Plain Claude invocation
- `ablation` — Plugin variant for ablation studies
- `external` — Non-Claude model (e.g. GPT-4o, Gemini)

---

## TRIZ Arena and ELO

The TRIZ Arena ranks participants using a Bradley-Terry ELO system:

- **Initial rating:** 1000 for all participants
- **K-factor:** K=32 for first match, K=16 for subsequent
- **Match outcomes:** Each problem creates pairwise matchups; higher score wins (1.0), lower loses (0.0), equal draws (0.5)
- **Confidence intervals:** 95% bootstrap CI from 1000 resamples

The leaderboard at `LEADERBOARD.md` shows:
- Rankings with ELO ratings and confidence intervals
- Per-problem score heatmap (with `—` for missing scores)
- Coverage column (scored problems / total problems)
- Per-dimension averages (CI, PS, SN, CR, IFR)

---

## Standalone MCP Server

Run the TRIZ MCP server independently of Claude Code:

```bash
cd triz-engine
python servers/triz_server.py
```

Connect from any MCP-compatible client. The server exposes the same 8 tools listed in [MCP Tools](#mcp-tools).

For Claude CLI usage with the MCP server:

```bash
claude --mcp-config path/to/mcp-config.json \
  -p "Analyze this contradiction using TRIZ..."
```

Example `mcp-config.json`:

```json
{
  "mcpServers": {
    "triz-knowledge": {
      "command": "python",
      "args": ["path/to/triz-engine/servers/triz_server.py"],
      "env": {
        "TRIZ_MODE": "full"
      }
    }
  }
}
```

---

## Troubleshooting

### "Command not found: claude"

The benchmark runner requires the Claude CLI. Install it from [docs.anthropic.com](https://docs.anthropic.com/en/docs/claude-code).

### "You're out of extra usage"

Claude CLI quota is exhausted. The benchmark runner will detect this and stop gracefully with a `QuotaExhaustedError`. Wait for your quota to reset and re-run — results from completed problems are saved and won't be re-run.

### "MCP server script not found"

The benchmark runner generates an MCP config at runtime with absolute paths. Ensure you're running from the `triz-engine/` directory.

### Tests fail with import errors

Ensure you installed with editable mode: `pip install -e ".[dev]"`. The `pyproject.toml` configures `pythonpath = ["."]` for pytest.

### CresOWLve dataset download fails

Install the `datasets` library: `pip install datasets`. The adapter downloads from HuggingFace and requires the `en` config.

### MacGyver dataset download fails

The adapter downloads an Excel file from the MacGyver GitHub repository. If the URL changes, update `xlsx_url` in `benchmark/external/macgyver_adapter.py`.
