# TRIZ Engine

> Systematic contradiction resolution using the 40 Inventive Principles — a Claude Code plugin

[![Tests](https://img.shields.io/badge/tests-passing-brightgreen?style=flat-square)](./triz-engine) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](./LICENSE)

## What is TRIZ?

**TRIZ** (Theory of Inventive Problem Solving, *Teoriya Resheniya Izobretatelskikh Zadatch*) is a structured innovation methodology developed by Genrich Altshuller and his school from the study of hundreds of thousands of patents. Instead of brainstorming in a vacuum, TRIZ treats difficult design situations as **contradictions** and uses repeatable patterns of resolution.

The **40 Inventive Principles** are abstract strategies (e.g. segmentation, dynamics, feedback) that recur across domains. The **Contradiction Matrix** (39×39 engineering parameters) suggests which principles historically helped when improving one parameter tended to worsen another. Together they turn “we can’t have both A and B” into a navigable search over known inventive moves.

## Quick Start (productive in &lt; 10 minutes)

1. **Clone the repo**

   ```bash
   git clone <your-fork-or-remote-url>
   cd TRIZ-plugin
   ```

2. **Install the Python package (editable, with dev deps)**

   ```bash
   cd triz-engine
   python3.11 -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. **Run the test suite**

   ```bash
   pytest
   ```

4. **Use the plugin in Claude Code**  
   After installing the plugin, these slash commands are available:

   | Command | Purpose |
   |---------|---------|
   | `/triz:analyze` | Full contradiction → matrix → principles → ranked solutions |
   | `/triz:principles` | Browse or search the 40 Inventive Principles |
   | `/triz:matrix` | Navigate the Contradiction Matrix |
   | `/triz:ifr` | Formulate the Ideal Final Result (IFR) |
   | `/triz:ariz` | Step through ARIZ-85C-style analysis |
   | `/triz:benchmark` | TRIZBENCH evaluation hooks for the current session |

## Commands Reference

| Command | What it does | When to use it |
|--------|----------------|----------------|
| `/triz:analyze` | Classifies technical vs physical contradictions, maps to 39 parameters, looks up the matrix (or separation strategies), pulls principle definitions, sketches solutions, scores against IFR, and recommends a top path | Default entry point for any real trade-off or “impossible” requirement |
| `/triz:principles` | Explores individual principles, examples, and software-oriented patterns | You already know the contradiction and want depth on one or more principles |
| `/triz:matrix` | Interactively explores improving/worsening parameter pairs and recommended principles | You have two competing metrics and want matrix-grounded suggestions |
| `/triz:ifr` | Sharpens the “ideal” outcome: maximum benefit with zero cost, harm, or complexity | Before or after analysis to avoid premature compromise |
| `/triz:ariz` | Guided ARIZ-style workflow for stubborn or ill-defined problems | Large, ambiguous problems needing staged refinement |
| `/triz:benchmark` | Connects to TRIZBENCH problems and scoring context | Comparing approaches, regression-testing reasoning, or Arena-style evaluation |

## Architecture

Text layout of the plugin package (under `triz-engine/`):

```
triz-engine/
├── .claude-plugin/plugin.json     # Plugin manifest
├── commands/                       # 6 slash commands
├── agents/                         # 3-agent pipeline
├── skills/triz-core.md            # Auto-activation skill
├── hooks/                          # Pre/post tool-use hooks
├── servers/triz_server.py          # FastMCP server (7 tools)
├── data/                           # Knowledge base + matrix
└── benchmark/                      # TRIZBENCH + Arena
```

### MCP tools (`triz-knowledge` server)

| Tool | Description |
|------|-------------|
| `get_principle` | Fetch one inventive principle by ID (1–40) |
| `search_principles` | Keyword search over principles, optional domain filter |
| `lookup_matrix` | Matrix lookup for an improving/worsening parameter pair (1–39) |
| `list_parameters` | List all 39 engineering parameters |
| `get_separation_principles` | Separation hints (time, space, condition, system level) for physical contradictions |
| `score_solution` | Heuristic IFR-oriented score (0–4) for a proposed solution |
| `log_session_entry` | Append a structured entry to the session innovation ledger (`.triz/session.jsonl`) |

### Agent pipeline

**contradiction-agent → solution-agent → evaluator-agent**

1. **Contradiction** — Extract and type the contradiction; map to TRIZ parameters.  
2. **Solution** — Instantiate matrix- or separation-guided principle sketches for the user’s domain.  
3. **Evaluator** — Score sketches on TRIZBENCH-style dimensions and surface the strongest recommendation.

## TRIZBENCH

**TRIZBENCH** is a benchmark of **12 canonical problems** (TB-01 … TB-12) spanning distributed systems, security/UX, ML, APIs, DevOps, privacy, IoT, search, compilers, org design, networking, and AI safety. Each problem has structured ground truth (contradiction type, parameter IDs, target principles, IFR baseline) for consistent evaluation.

**Five-dimension scoring** (weighted to a 0–100 score):

| Code | Dimension | Weight |
|------|-----------|--------|
| CI | Contradiction identification | 25% |
| PS | Principle selection | 20% |
| SN | Solution novelty | 20% |
| CR | Contradiction resolution | 25% |
| IFR | Ideal Final Result proximity | 10% |

**TRIZ Arena** ranks participants (prompts, models, or configurations) using **Bradley–Terry ELO** on head-to-head or per-problem outcomes, producing a leaderboard you can regenerate from benchmark artifacts.

## Development

- **Tests:** `pytest` — **265** tests collected in `triz-engine/`.  
- **Lint:** `ruff check .` (from `triz-engine/` with dev dependencies installed).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for workflow, CI notes, and how to extend the knowledge base or benchmark.

## License

MIT — see [LICENSE](LICENSE).
