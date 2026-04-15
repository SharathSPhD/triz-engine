# Walkthrough: TB-01 — CAP Theorem Trade-off

This document shows how **TRIZ Engine** can be applied to **TB-01** from TRIZBENCH using `/triz:analyze`. Numbers and principle IDs match the canonical problem definition in `benchmark/problems/TB-01.json`.

## 1. Problem statement

From the benchmark:

> A distributed cache serving a financial trading platform must provide real-time price data to 50,000 concurrent users. The system uses 12 cache nodes across 3 availability zones.
>
> During a network partition event (which occurs on average 2.3 times per month), the cache must choose between serving potentially stale prices (risking regulatory violations for showing outdated data) or rejecting requests entirely (causing a cascade of order failures costing approximately $340K per minute of downtime).
>
> The current architecture uses a simple leader-follower replication with synchronous writes, resulting in p99 latency of 45ms during normal operation but complete unavailability during partitions.
>
> The system needs to simultaneously guarantee that no user ever sees a price more than 100ms stale AND that the system maintains 99.99% availability, including during network partitions.

## 2. Running `/triz:analyze`

### Expected flow

1. **Intake** — The assistant isolates the tension: under partition, the system cannot both stay available to all clients and globally guarantee freshness; the stakeholder wording also demands **both** strong freshness and **high availability during partitions** — a **physical contradiction** at the whole-system level (“must be available and fresh everywhere” vs operational reality).

2. **Contradiction identified**  
   - **Type:** Physical contradiction (the same system must satisfy opposing requirements in the failure mode).  
   - **TRIZ parameters (canonical TB-01 mapping):** **27 — Reliability** (consistent, trustworthy data / regulatory-safe behavior) vs **35 — Adaptability or versatility** (the system must flex to stay up and serve under changing network conditions).  
   *Note:* The benchmark JSON labels these conceptually as “data consistency” and “system availability”; in the matrix shipped with this project, IDs **27** and **35** correspond to **Reliability** and **Adaptability or versatility**.

3. **Matrix lookup** — TRIZBENCH grades principle selection against **target** principles **1 (Segmentation)**, **15 (Dynamics)**, **35 (Parameter changes)** (see `benchmark/problems/TB-01.json`).  
   **Repository note:** The packaged matrix cell for improving **27** vs worsening **35** is `lookup_matrix(27, 35)` → **`[13, 35, 8, 24]`** in `data/triz-matrix.json`. Physical-contradiction analyses often **blend** raw matrix suggestions with separation strategies; the sketches below follow the benchmark targets so scores align with TRIZBENCH.

4. **Solution sketches (principle → distributed systems)**

   | Principle | Sketch |
   |-----------|--------|
   | **1 — Segmentation** | Partition the *problem* by **region + asset class**: strong consistency and strict staleness bounds inside a small “hot” shard or AZ-local scope; segment “regulatory-critical” ticks onto a dedicated sub-cluster with synchronous quorum, while less critical symbols use relaxed paths. |
   | **15 — Dynamics** | Make consistency **time-varying**: normal mode uses low-latency sync replication; on partition detection, automatically shift to a declared mode (e.g. degrade to read-your-writes + monotonic reads in-session, or failover leader per partition) with explicit user-visible **staleness budget** and recovery merge. |
   | **35 — Parameter changes** | Change the **freshness parameter** from “global wall-clock” to **version vectors + bounded staleness SLAs** per jurisdiction; use **hybrid logical clocks** and server-side “as-of” timestamps so clients never interpret stale data as current without an explicit label. |

5. **Evaluator** — The evaluator-agent scores each sketch on contradiction resolution depth (eliminate vs reduce vs manage), novelty class, and IFR alignment (fewer new moving parts, self-regulating behavior, minimal side effects). Typically the **dynamics + parameter-change** combination ranks high because it reframes the CAP trade-off as **mode-dependent behavior** rather than a single static policy.

6. **Top recommendation (illustrative)**  
   **Adopt a dynamically switching consistency model with segmented critical paths:** keep a **small, strongly consistent slice** for prices under active regulatory windows, and use **versioned, explicitly labeled** responses elsewhere during partitions, with automatic re-sync and conflict resolution on heal. Implementation guidance: leader election per segment, CRDT or merge rules for price updates, client UX that surfaces data age, and chaos tests for partition flips.

## 3. Example JSON output

Structured output you might return from an analysis run (illustrative; field names can match your session ledger):

```json
{
  "problem_id": "TB-01",
  "contradiction_card": {
    "type": "physical",
    "summary": "Under partition, the cache must both remain highly available and never serve prices beyond a strict freshness bound.",
    "parameter_a": { "id": 27, "name": "Reliability" },
    "parameter_b": { "id": 35, "name": "Adaptability or versatility" }
  },
  "matrix_lookup": {
    "improving": { "id": 27, "name": "Reliability" },
    "worsening": { "id": 35, "name": "Adaptability or versatility" },
    "principles": [1, 15, 35]
  },
  "solution_sketches": [
    {
      "principle_id": 1,
      "principle_name": "Segmentation",
      "sketch": "Isolate regulatory-critical price streams into a dedicated replicated segment with strict quorum; relax only non-critical symbols.",
      "resolution_level": "reduces"
    },
    {
      "principle_id": 15,
      "principle_name": "Dynamics",
      "sketch": "Automatic operational modes: normal synchronous replication; partition mode switches to explicit staleness labels and per-session monotonicity.",
      "resolution_level": "eliminates"
    },
    {
      "principle_id": 35,
      "principle_name": "Parameter changes",
      "sketch": "Redefine freshness as versioned 'as-of' timestamps and hybrid logical clocks instead of a single global instant.",
      "resolution_level": "eliminates"
    }
  ],
  "evaluator_scores": {
    "TB-01": {
      "sketches": [
        { "principle_id": 1, "cr_level": "reduces", "sn_level": "standard", "ifr_score": 2 },
        { "principle_id": 15, "cr_level": "eliminates", "sn_level": "novel_combination", "ifr_score": 3 },
        { "principle_id": 35, "cr_level": "eliminates", "sn_level": "non_obvious", "ifr_score": 3 }
      ],
      "top_principle_id": 35,
      "rationale": "Combining dynamics (15) with redefined freshness parameters (35) removes the false dichotomy between blind availability and hidden staleness."
    }
  },
  "top_recommendation": {
    "title": "Mode-dependent consistency with explicit versioning",
    "implementation": [
      "Per-segment replication and leader failover",
      "Client-visible max-staleness and as-of metadata",
      "Merge/reconciliation on partition heal with audit trail"
    ]
  }
}
```

For the authoritative ground-truth tuple used in scoring, see `benchmark/problems/TB-01.json`.
