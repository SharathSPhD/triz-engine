# TRIZ Engine

> Systematic contradiction resolution using the 40 Inventive Principles — a Claude Code plugin

[![Tests](https://img.shields.io/badge/tests-327_passing-brightgreen?style=flat-square)](./triz-engine)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](./triz-engine/pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](./LICENSE)
[![ELO](https://img.shields.io/badge/ELO-1015-blueviolet?style=flat-square)](./triz-engine/LEADERBOARD.md)

## What is TRIZ?

**TRIZ** (Theory of Inventive Problem Solving) is a structured innovation methodology developed by Genrich Altshuller from the study of hundreds of thousands of patents. Instead of brainstorming, TRIZ treats difficult design situations as **contradictions** and uses repeatable patterns of resolution.

The **40 Inventive Principles** are abstract strategies (segmentation, dynamics, feedback, etc.) that recur across domains. The **Contradiction Matrix** (39x39 engineering parameters) suggests which principles historically resolved specific improving-vs-worsening trade-offs.

## Quick Start

```bash
git clone https://github.com/SharathSPhD/triz-engine.git
cd TRIZ-plugin/triz-engine
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                    # 327 tests
```

Then use in Claude Code:

```
/triz:analyze "Our API needs lower latency but adding caching increases memory usage and stale-data risk"
```

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for the full getting-started guide and [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for detailed usage.

## Commands

| Command | What it does |
|---------|-------------|
| `/triz:analyze` | Full contradiction analysis: classify, map parameters, look up matrix, generate solutions, score against IFR |
| `/triz:principles` | Browse or search the 40 Inventive Principles with domain-specific examples |
| `/triz:matrix` | Navigate the Contradiction Matrix for an improving/worsening parameter pair |
| `/triz:ifr` | Formulate the Ideal Final Result — maximum benefit, zero cost/harm/complexity |
| `/triz:ariz` | Full ARIZ-85C step-by-step analysis for deeply intractable contradictions |
| `/triz:benchmark` | Run TRIZBENCH evaluation on the current session |

## MCP Tools

The `triz-knowledge` server exposes 8 tools:

| Tool | Description |
|------|-------------|
| `get_principle` | Fetch one inventive principle by ID (1-40) |
| `search_principles` | Keyword search over principles with optional domain filter |
| `lookup_matrix` | Matrix lookup for an improving/worsening parameter pair (1-39) |
| `list_parameters` | List all 39 engineering parameters |
| `get_separation_principles` | Separation strategies (time, space, condition, system level) for physical contradictions |
| `suggest_parameters` | Map a natural-language description to candidate TRIZ parameters |
| `score_solution` | IFR-oriented score (0-4) for a proposed solution |
| `log_session_entry` | Append a structured entry to the session innovation ledger |

## Agent Pipeline

**contradiction-agent** &#8594; **solution-agent** &#8594; **evaluator-agent**

1. **Contradiction** — Extract and classify the contradiction; map to TRIZ parameters
2. **Solution** — Generate matrix- or separation-guided principle sketches for the user's domain
3. **Evaluator** — Score sketches on TRIZBENCH dimensions and surface the strongest recommendation

## Architecture

```
triz-engine/
├── .claude-plugin/plugin.json     # Plugin manifest
├── commands/                       # 6 slash commands (analyze, principles, matrix, ifr, ariz, benchmark)
├── agents/                         # 3-agent pipeline (contradiction, solution, evaluator)
├── skills/triz-core.md            # Auto-activation skill
├── hooks/                          # Pre/post tool-use hooks
├── servers/triz_server.py          # FastMCP server (8 tools)
├── data/                           # Knowledge base (40 principles + 39x39 matrix)
├── benchmark/                      # TRIZBENCH problems, scorer, ELO, external adapters
│   ├── problems/                   # 12 canonical problems (TB-01 to TB-12)
│   ├── participants/               # Participant configs (triz-engine, vanilla-claude, etc.)
│   ├── external/                   # External benchmark adapters (TRIZBENCH, MacGyver, CresOWLve)
│   ├── runner.py                   # Benchmark execution engine
│   ├── scorer.py                   # 5-dimension scoring with LLM-as-judge
│   ├── elo.py                      # Bradley-Terry ELO rating system
│   └── leaderboard.py              # Leaderboard generator
└── results/                        # Benchmark output artifacts
```

## Benchmarks

### Internal TRIZBENCH

12 canonical problems (TB-01 to TB-12) spanning distributed systems, security, ML, APIs, DevOps, privacy, IoT, search, compilers, org design, networking, and AI safety. Five-dimension weighted scoring:

| Dimension | Weight | Method |
|-----------|--------|--------|
| Contradiction Identification (CI) | 25% | Verified ground truth |
| Principle Selection (PS) | 20% | Verified ground truth |
| Solution Novelty (SN) | 20% | LLM-as-judge (Sonnet) |
| Contradiction Resolution (CR) | 25% | LLM-as-judge (Sonnet) |
| IFR Proximity (IFR) | 10% | Verified ground truth |

### External Benchmarks

| Benchmark | What it tests | Problems |
|-----------|--------------|----------|
| **Published TRIZBENCH** | Patent contradiction analysis with ground-truth parameters and principles | 167 classic-range patents |
| **MacGyver** | Constrained creative problem-solving with inventive object usage | 1,683 problems |
| **CresOWLve** | Lateral/divergent creative reasoning | 2,061 problems |

### Leaderboard

See [LEADERBOARD.md](triz-engine/LEADERBOARD.md) for current rankings. The TRIZ Arena ranks participants using Bradley-Terry ELO with bootstrap confidence intervals.

## Development

```bash
cd triz-engine
source .venv/bin/activate
pytest                     # Run full test suite
ruff check .               # Lint
python -m benchmark.runner --problems TB-01 TB-02 --participants triz-engine vanilla-claude
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for workflow, CI notes, and how to extend the knowledge base or benchmark.

## License

MIT — see [LICENSE](LICENSE).
