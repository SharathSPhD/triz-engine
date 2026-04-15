# Contributing to TRIZ Arena

## Submission Protocol

### 1. Fork this repository

### 2. Create your participant directory
```
benchmark/participants/{your-name}/
├── participant.json    # Metadata and invocation config
└── system_prompt.md    # Your system prompt (if prompt-based)
```

Or for plugin-based participants:
```
benchmark/participants/{your-name}/
├── participant.json    # Metadata and invocation config
└── plugin.json         # Plugin manifest
```

### 3. Define your participant config

Your `participant.json` must follow this schema:
```json
{
  "name": "your-participant-name",
  "version": "1.0.0",
  "description": "Brief description of your approach",
  "type": "community",
  "invocation": {
    "command": "claude",
    "args": ["--headless", ...],
    "timeout_seconds": 120
  },
  "features": ["list", "of", "features"]
}
```

### 4. Open a Pull Request
- CI runs a 3-problem qualification test on TB-01, TB-06, and TB-12
- Your submission must produce valid JSON output matching the TRIZBENCH submission schema
- Passing submissions are merged and added to the next nightly run

### 5. Results
- Results appear in `LEADERBOARD.md` within 24 hours of merge
- ELO ratings include 95% bootstrap confidence intervals

## Submission Schema

Your participant must output JSON matching this schema for each problem:
```json
{
  "problem_id": "TB-XX",
  "participant": "your-name@version",
  "contradiction_type": "technical|physical",
  "parameter_a": "description",
  "parameter_b": "description",
  "triz_param_a": 1-39,
  "triz_param_b": 1-39,
  "principles_applied": [1, 15, 35],
  "solutions": [
    {
      "principle_id": 1,
      "principle_name": "Segmentation",
      "solution_sketch": "...",
      "ifr_score": 0-4,
      "ifr_rationale": "..."
    }
  ],
  "recommended_solution": {
    "principle_id": 15,
    "rationale": "..."
  },
  "run_timestamp": "ISO 8601",
  "latency_ms": 18240
}
```

## Code of Conduct
- No gaming: participant configs are reviewed on PR
- Evaluation runs in a sandboxed environment with network isolation
- Output format is validated before scoring
