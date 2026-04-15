# TRIZ Arena Leaderboard

*Updated: 2026-04-15 15:22 UTC*

## Rankings

| Rank | Participant | ELO Rating | 95% CI | Matches |
|------|------------|------------|--------|---------|
| 1 | vanilla-claude | 1030 | 1030–1030 | 3 |
| 2 | triz-engine | 970 | 970–970 | 3 |

## Per-Problem Scores

| Participant |TB-01 | TB-06 | TB-12 | Mean |
|------------|---- | ---- | ---- | ---- |
| vanilla-claude | 41.7 | 54.9 | 34.5 | **43.7** |
| triz-engine | 23.5 | 10.0 | 26.9 | **20.1** |

## Methodology

- **Scoring**: TRIZBENCH 5-dimension weighted rubric (CI 25% + PS 20% + SN 20% + CR 25% + IFR 10%)
- **ELO**: Bradley-Terry model with K=32 initial, K=16 subsequent
- **CI**: 95% bootstrap confidence intervals from 1000 permutations
- **Problems**: 12 canonical TRIZBENCH problems (TB-01 through TB-12)
