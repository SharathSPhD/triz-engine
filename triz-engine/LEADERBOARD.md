# TRIZ Arena Leaderboard

*Updated: 2026-04-16 12:47 UTC*

## Rankings

| Rank | Participant | ELO Rating | 95% CI | Matches |
|------|------------|------------|--------|---------|
| 1 | triz-engine | 1076 | 1053–1128 | 30 |
| 2 | vanilla-claude | 924 | 872–948 | 30 |

## Per-Problem Scores

| Participant |EXT-TB-001 | EXT-TB-002 | EXT-TB-003 | EXT-TB-004 | EXT-TB-005 | EXT-TB-006 | EXT-TB-007 | EXT-TB-008 | EXT-TB-009 | EXT-TB-010 | EXT-TB-011 | EXT-TB-012 | EXT-TB-013 | EXT-TB-014 | EXT-TB-015 | EXT-TB-016 | EXT-TB-017 | EXT-TB-018 | EXT-TB-019 | EXT-TB-020 | TB-01 | TB-02 | TB-03 | TB-04 | TB-05 | TB-06 | TB-07 | TB-08 | TB-09 | TB-10 | TB-11 | TB-12 | Mean | Coverage |
|------------|---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- | ---- |
| triz-engine | 100.0 | 92.9 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 50.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 83.3 | 34.5 | 47.6 | 60.8 | 28.9 | 76.0 | 33.9 | 28.9 | 32.2 | 41.9 | 67.2 | 34.5 | 31.4 | **76.4** | 32/32 |
| vanilla-claude | 72.2 | 61.1 | 61.1 | 50.0 | 50.0 | 62.5 | 64.3 | 72.2 | 50.0 | 87.5 | 50.0 | 62.5 | 50.0 | 50.0 | 62.5 | 78.6 | 78.6 | 62.5 | 72.2 | 61.1 | 29.7 | 63.1 | 42.0 | 42.9 | 60.8 | — | 28.9 | 45.6 | 36.4 | 46.4 | 37.4 | — | **56.4** | 30/32 |

## Per-Dimension Averages

| Participant | CI | PS | SN | CR | IFR |
|------------|-----|-----|-----|-----|-----|
| triz-engine | 30 | 9 | 41 | 70 | 81 |
| vanilla-claude | 22 | 12 | 43 | 77 | 75 |

## Methodology

- **Scoring**: TRIZBENCH 5-dimension weighted rubric (CI 25% + PS 20% + SN 20% + CR 25% + IFR 10%)
- **ELO**: Bradley-Terry model with K=32 initial, K=16 subsequent
- **CI**: 95% bootstrap confidence intervals from 1000 resamples
- **Problems**: 32 TRIZBENCH problems evaluated
