# Walkthrough: TB-12 — AI Safety (Helpfulness vs Safety)

Illustrative **`/triz:analyze`** path for **TB-12**. Canonical IDs match `benchmark/problems/TB-12.json`.

## 1. Problem statement

From the benchmark:

> A general-purpose AI assistant deployed to 180 million users must be maximally helpful — answering complex questions, generating creative content, assisting with code, and providing advice across all domains. Simultaneously, it must be maximally safe — never producing harmful content, never assisting with dangerous activities, never generating misinformation, and never violating user privacy.
>
> These goals conflict fundamentally: over-filtering for safety causes the system to refuse legitimate requests (current false refusal rate: 4.7%, affecting 8.5 million user interactions daily), while relaxing safety constraints to improve helpfulness increases harmful content (estimated 0.03% of unfiltered responses contain actionable harmful content, affecting 54,000 responses daily at scale).
>
> Each percentage point reduction in false refusals increases harmful content by approximately 0.008%.
>
> The system must simultaneously achieve near-zero harmful outputs AND near-zero false refusals — a challenge complicated by the context-dependent nature of harm (medical information that saves lives in one context enables self-harm in another).

## 2. Contradiction framing

**Physical contradiction:** the system must be **maximally capable and responsive** in every domain **and** **maximally constrained** against harm — including cases where the *same* capability is benign or harmful depending on context.

**TRIZ parameters (TB-12 ground truth):**

- **35 — Adaptability or versatility** (breadth of helpful behavior, context-tailored responses)  
- **30 — Harmful factors acting on the system** (unsafe outputs, policy violations, misuse)

## 3. Matrix-backed principles

TRIZBENCH **target** principles for TB-12: **3 (Local quality)**, **15 (Dynamics)**, **23 (Feedback)**.

**Repository note:** `lookup_matrix(35, 30)` in `data/triz-matrix.json` returns **`[35, 11, 32, 31]`**. As with other problems, scoring uses benchmark targets; analysis may combine matrix output, separation, and domain-specific refinement.

## 4. Solution directions (AI safety)

| Principle | Application |
|-----------|-------------|
| **3 — Local quality** | **Different policies in different “neighborhoods”** of the problem space: medical advice routes through a clinical-information mode with citations and crisis resources; code help uses sandboxed execution and secret scanning; creative writing uses a separate style and harm classifier. Uniform global strictness is replaced by **fit-for-context** quality. |
| **15 — Dynamics** | **Policies that move over time** within a session: start broad and safe; after verified user intent, risk tier, or domain clearance, **expand capability** (tool access, detail level). Conversely, escalate constraints when signals indicate jailbreak or self-harm. |
| **23 — Feedback** | **Closed-loop monitoring**: human and automatic reviewers, user reports, and runtime classifiers feed **continuous model and policy updates**; shadow deployments and canaries adjust thresholds without a single static refusal rate for all traffic. |

## 5. Top recommendation (illustrative)

**Context-local policy layers with dynamic capability expansion and tight feedback loops:** build explicit **domain routers** and **risk tiers**, use **session-state-aware** safety (dynamics), and invest in **measurement-driven** threshold tuning (feedback) so “helpful” and “safe” are not traded off on one global dial. Near-zero harm and near-zero false refusals are pursued as **jointly optimized operating points** per segment, not as a single scalar compromise.

---

**Ground truth reference:** `benchmark/problems/TB-12.json` (`physical`, parameters **35** / **30**, principles **3, 15, 23**).
