# Contributing to TRIZ Arena

## Submission Protocol

### 1. Fork this repository

### 2. Create your participant config

Add a single JSON file at `triz-engine/benchmark/participants/{your-name}.json`:

```json
{
  "name": "your-participant-name",
  "version": "1.0.0",
  "description": "Brief description of your approach",
  "type": "baseline|ablation|external",
  "invocation": {
    "command": "claude",
    "args": ["--headless", "--system-prompt", "Your system prompt here", "--prompt-file", "{problem_file}"],
    "timeout_seconds": 120
  },
  "features": ["list", "of", "features"]
}
```

**Participant types:**
- `baseline` — Claude with a custom system prompt (no MCP tools)
- `ablation` — Claude with a file-based system prompt (for A/B testing prompts)
- `external` — Non-Claude model requiring a custom runner script (set `requires_env` in invocation)
- `plugin` — Full plugin with MCP tools (reserved for triz-engine)

### 3. Open a Pull Request

- The nightly CI run will include your participant in the next benchmark cycle
- Your submission must produce valid JSON output matching the submission schema below
- Passing submissions are merged and scored in the next nightly run

### 4. Results

- Results appear in `LEADERBOARD.md` after the next nightly run
- ELO ratings include 95% bootstrap confidence intervals
- Per-dimension breakdowns (CI, PS, SN, CR, IFR) are included

## Submission Schema

Your participant must output JSON matching this schema for each problem (enclosed in \`\`\`json fences):

```json
{
  "contradiction_type": "technical|physical",
  "triz_param_a": 1-39,
  "triz_param_b": 1-39,
  "principles_applied": [1, 15, 35],
  "solution_summary": "2-3 sentence concrete solution",
  "ifr_score": 0-4,
  "contradiction_resolution": "eliminates|reduces|manages|fails",
  "solution_novelty": "non_obvious|novel_combination|standard|restatement"
}
```

## Scoring

Five dimensions, weighted:
- **CI** (Contradiction Identification) — 25%: type match + parameter pair match
- **PS** (Principle Selection) — 20%: Jaccard similarity with target principles
- **SN** (Solution Novelty) — 20%: LLM-as-judge classification
- **CR** (Contradiction Resolution) — 25%: LLM-as-judge classification
- **IFR** (Ideal Final Result) — 10%: 0-4 scale mapped to 0-100

## Code of Conduct

- No gaming: participant configs are reviewed on PR
- Output format is validated before scoring
- Infrastructure failures are excluded from ratings
