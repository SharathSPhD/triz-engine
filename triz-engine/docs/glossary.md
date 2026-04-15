# TRIZ Glossary

Short definitions for terms used throughout **TRIZ Engine** and TRIZBENCH.

## ARIZ (Algorithm of Inventive Problem Solving)

A structured, stepwise procedure (historically several versions, e.g. ARIZ-85) for reformulating a messy situation into a solvable contradiction, applying separation ideas or the matrix, and iterating toward an inventive solution. In this plugin, `/triz:ariz` guides a Claude Code–native variant of that workflow.

## Contradiction (Technical and Physical)

A **contradiction** is the core TRIZ unit of analysis.

- **Technical contradiction:** Improving one engineering parameter or quality metric tends to **worsen** another (e.g. stronger security vs easier operation). Often mapped to the **Contradiction Matrix**.
- **Physical contradiction:** The same parameter must take **opposing values** at once in the same context from a naive viewpoint (e.g. “must be rigid and flexible”). Often addressed with **separation principles** and inventive moves that **dissolve** the conflict rather than averaging it.

## Contradiction Matrix

A 39×39 table associating pairs of **engineering parameters** with historically effective **Inventive Principles**. When you know which parameter improves and which worsens, the matrix suggests candidate principles. Exposed via the `lookup_matrix` MCP tool and `/triz:matrix`.

## Engineering Parameters (39)

Standardized dimensions of system behavior (e.g. strength, speed, reliability, ease of operation). They provide a **shared vocabulary** for contradictions and matrix lookup. Listed by `list_parameters` in the MCP server.

## Ideal Final Result (IFR)

A target vision: the useful function is delivered **without** added cost, harm, complexity, or secondary problems — ideally the system **resolves the contradiction by itself**. Used to rank whether a sketch truly eliminates a trade-off or merely negotiates it. `/triz:ifr` helps formulate IFRs; `score_solution` gives a coarse IFR-oriented score.

## Inventive Principles (40)

Abstract solution patterns distilled from patent and design analysis (e.g. segmentation, preliminary action, feedback). Each principle has sub-actions and examples; in software projects they are often instantiated as architectural or process moves. Stored in `data/triz-knowledge-base.json` and accessed with `get_principle` / `search_principles`.

## Physical Contradiction

See **Contradiction**. Emphasizes the “**both A and not-A**” formulation; resolution classically involves **separation in time, space, condition, or system level**, or principles that make the opposition illusory at the redesigned system.

## Separation Principles (Time, Space, Condition, System Level)

Ways to satisfy opposing requirements **without** compromise:

- **Time** — Opposite requirements at different moments (modes, phases).
- **Space** — Opposite requirements in different regions or components.
- **Condition** — Behavior switches on context (load, environment, user tier).
- **System level** — Property at the whole differs from properties of parts (e.g. flexible chain of rigid links).

Surfaced for brainstorming via `get_separation_principles`.

## Substance-Field Analysis

A TRIZ modeling approach (Su-Field) describing interactions between substances and “fields” (energy/information). Less central to this plugin than contradictions and the 40 principles, but part of the broader TRIZ toolkit for functional modeling.

## Technical Contradiction

See **Contradiction** — the parameter A up, parameter B down pattern, typically matrix-driven.

## TRIZBENCH

The **12-problem** benchmark suite (TB-01 … TB-12) in `benchmark/problems/`, each with structured ground truth for automated scoring across contradiction identification, principle selection, solution quality, and IFR alignment.

## TRIZ Arena

A **Bradley–Terry ELO** leaderboard that compares participants (models, prompts, or configurations) on TRIZBENCH-style outcomes, implemented under `benchmark/` (see `elo.py`, `leaderboard.py`, and CI workflows). Useful for regression tracking and comparative evaluation.
