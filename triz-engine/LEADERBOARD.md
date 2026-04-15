# TRIZ Arena Leaderboard

*Updated: 2026-04-15 19:21 UTC*

## Rankings

| Rank | Participant | ELO Rating | 95% CI | Matches |
|------|------------|------------|--------|---------|
| 1 | triz-engine | 1015 | 969–1054 | 9 |
| 2 | vanilla-claude | 985 | 946–1031 | 9 |

## Per-Problem Scores

| Participant |EXT-TB-001 | EXT-TB-002 | EXT-TB-003 | TB-01 | TB-02 | TB-03 | TB-04 | TB-05 | TB-06 | TB-07 | TB-08 | TB-12 | Mean | Coverage |
|------------|---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- |
| triz-engine | 100.0 | 100.0 | 92.9 | 34.5 | 47.6 | 60.8 | 28.9 | 76.0 | 33.9 | 28.9 | 32.2 | 31.4 | **55.6** | 12/12 |
| vanilla-claude | 50.0 | 50.0 | 62.5 | 29.7 | 63.1 | — | 42.9 | 60.8 | — | 28.9 | 45.6 | — | **48.2** | 9/12 |

## Per-Dimension Averages

| Participant | CI | PS | SN | CR | IFR |
|------------|-----|-----|-----|-----|-----|
| triz-engine | 26 | 5 | 41 | 69 | 86 |
| vanilla-claude | 22 | 17 | 41 | 82 | 75 |

## Methodology

- **Scoring**: TRIZBENCH 5-dimension weighted rubric (CI 25% + PS 20% + SN 20% + CR 25% + IFR 10%)
- **ELO**: Bradley-Terry model with K=32 initial, K=16 subsequent
- **CI**: 95% bootstrap confidence intervals from 1000 resamples
- **Problems**: 12 TRIZBENCH problems evaluated
