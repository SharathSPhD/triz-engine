# Quick Start Guide

Get TRIZ Engine running in Claude Code in under 5 minutes.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI installed (`claude --version`)
- Python 3.11+ (only required if you want to run benchmarks or edit the plugin code)
- Git

## Install as a Claude Code plugin

TRIZ Engine is distributed as a plugin. Install once; every Claude Code session
gets slash commands, MCP tools, and the specialized agent pipeline.

### Option A — from this repo (local marketplace)

```bash
git clone https://github.com/SharathSPhD/triz-engine.git
cd triz-engine                       # repo root (contains .claude-plugin/marketplace.json)

claude plugin marketplace add ./
claude plugin install triz-engine@triz-arena
```

### Option B — from GitHub (once published)

```bash
claude plugin marketplace add SharathSPhD/triz-engine
claude plugin install triz-engine@triz-arena
```

## Verify the plugin is live

Run this verification checklist before first use:

```bash
# 1. Plugin is listed and enabled
claude plugin list | grep triz-engine
# → triz-engine@triz-arena  Version: 1.0.0  Scope: user  Status: ✔ enabled

# 2. Slash command reaches the plugin pipeline
claude -p "/triz-engine:analyze How do we reduce drone weight without sacrificing flight time?" \
  --model haiku --dangerously-skip-permissions --output-format json | jq '.num_turns, .result | @text'
# → multiple turns (agent pipeline fired) + a structured TRIZ answer

# 3. MCP knowledge server is healthy
# (This happens automatically when the plugin runs — no manual startup needed.)
```

If `claude plugin list` shows `triz-engine` as disabled, enable it:

```bash
claude plugin enable triz-engine@triz-arena
```

## Your first TRIZ analysis

In any Claude Code session:

```
/triz-engine:analyze Our API needs lower latency but adding caching increases memory usage and stale-data risk.
```

Behind the scenes the plugin:

1. Loads the `commands/analyze.md` system prompt
2. Invokes the **contradiction-agent** to classify technical vs physical
3. Invokes the **solution-agent** to retrieve principles from the `triz-knowledge` MCP server and the Contradiction Matrix
4. Invokes the **evaluator-agent** to score candidates on the TRIZBENCH 5-dimension rubric (CI, PS, SN, CR, IFR)
5. Returns a structured recommendation

## Other slash commands

| Command | Use for |
|---------|---------|
| `/triz-engine:principles <query>` | Browse / search the 40 Inventive Principles |
| `/triz-engine:matrix <improving> <worsening>` | Look up the Contradiction Matrix |
| `/triz-engine:ifr <problem>` | Formulate the Ideal Final Result |
| `/triz-engine:ariz <problem>` | Full ARIZ-85C step-by-step analysis |
| `/triz-engine:benchmark` | Run TRIZBENCH evaluation on the current conversation |

## Dev setup (optional — only for running benchmarks)

If you want to run the benchmark suite or extend the plugin:

```bash
cd triz-engine
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                                      # 295 passing tests

# Run one problem with the live plugin via the benchmark runner
python -m benchmark.runner \
  --problems TB-01 \
  --participants triz-engine vanilla-claude \
  --capture-trace
```

Results land in `triz-engine/results/` and include full stream-json traces
(tool_use / tool_result / agent turns) when `--capture-trace` is set.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Slash command '/triz-engine:analyze' not found` | Run `claude plugin list` — reinstall if missing. Restart Claude Code if needed. |
| MCP server fails to start | Verify the plugin copy has `servers/triz_server.py` executable: `ls -la $(dirname $(claude plugin list --json 2>/dev/null \| jq -r '.[] \| select(.name==\"triz-engine\") .path' ))/servers/*.py` |
| "out of extra usage" error | Claude Pro/Max daily usage exhausted — wait for the 5-hour reset. The benchmark runner raises `QuotaExhaustedError` and stops cleanly. |
| Python 3.9 import errors during tests | Use Python 3.11+. `python3 -m pytest tests/ --ignore=tests/test_server.py --ignore=tests/test_mcp_live.py` for tests that don't need `fastmcp`. |

## Next

- Read the [User Guide](USER_GUIDE.md) for a deeper walk-through
- Explore the [TRIZ Arena leaderboard](https://sharathsphd.github.io/triz-engine/)
- See [CONTRIBUTING.md](../CONTRIBUTING.md) to extend the knowledge base
