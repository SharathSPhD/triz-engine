# Quick Start Guide

Get TRIZ Engine running in under 5 minutes.

## Prerequisites

- Python 3.11+
- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (for plugin integration)
- Git

## Installation

### 1. Clone and install

```bash
git clone https://github.com/SharathSPhD/triz-engine.git
cd TRIZ-plugin/triz-engine
python3.11 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 2. Verify installation

```bash
pytest
# Expected: 327 passed
```

### 3. Start the MCP server (standalone)

```bash
python servers/triz_server.py
```

The server runs on stdio and exposes 8 TRIZ tools. Claude Code will start this automatically when you use the plugin.

## Using the Plugin in Claude Code

Once the plugin is installed, six slash commands become available:

### Analyze a contradiction

```
/triz:analyze "We need our microservice to handle 10x more traffic,
but scaling horizontally increases inter-service latency and data consistency issues"
```

The analyze command will:
1. Classify the contradiction (technical vs physical)
2. Map dimensions to TRIZ parameters (e.g. Speed vs Reliability)
3. Look up the Contradiction Matrix for recommended principles
4. Generate domain-specific solutions
5. Score each solution against the Ideal Final Result

### Browse principles

```
/triz:principles "segmentation"
```

Returns matching principles with definitions, classical examples, and software-domain applications.

### Look up the matrix

```
/triz:matrix
```

Interactive exploration of the 39x39 Contradiction Matrix. Specify the improving parameter (e.g. "Speed") and worsening parameter (e.g. "Reliability") to get recommended principles.

### Formulate the Ideal Final Result

```
/triz:ifr "The system should handle unlimited concurrent users
with zero additional infrastructure cost"
```

Helps you articulate the perfect outcome before compromising, following Altshuller's IFR discipline.

### Deep analysis with ARIZ

```
/triz:ariz "Our compiler optimization passes improve runtime speed
but the compilation time becomes unacceptable for developer iteration"
```

Walks you through the full ARIZ-85C algorithm (9 parts) for problems that resist standard analysis.

## Standalone MCP Usage

You can use the TRIZ tools directly without the plugin via MCP:

```python
from servers.triz_server import mcp

# Tools available:
# get_principle, search_principles, lookup_matrix,
# list_parameters, get_separation_principles,
# suggest_parameters, score_solution, log_session_entry
```

Or connect via Claude CLI:

```bash
claude --mcp-config mcp-config.json -p "Look up TRIZ principles for improving speed without worsening reliability"
```

## Running Benchmarks

Run a quick benchmark to see the scoring system in action:

```bash
cd triz-engine

# Run two problems for triz-engine vs vanilla-claude
python -m benchmark.runner --problems TB-01 TB-02 \
  --participants triz-engine vanilla-claude

# Run external benchmarks (needs Claude CLI)
python -m benchmark.external.run_external --benchmarks trizbench --limit 3
```

Results are saved to `results/` and the leaderboard is at `LEADERBOARD.md`.

## What's Next

- Read the [User Guide](USER_GUIDE.md) for detailed usage of every command, tool, and agent
- Explore the 12 TRIZBENCH problems in `benchmark/problems/`
- Check the [LEADERBOARD.md](../triz-engine/LEADERBOARD.md) for current rankings
- Add your own participant config in `benchmark/participants/`
