---
name: triz-core
description: Auto-activated TRIZ reasoning skill for systematic contradiction resolution
autoActivate:
  keywords:
    - contradiction
    - trade-off
    - tradeoff
    - tension
    - vs
    - versus
    - dilemma
    - improves but
    - worsens
    - can't have both
---

# TRIZ Core Reasoning Skill

When you detect an engineering, software, or design contradiction in the user's problem, automatically apply TRIZ thinking:

## DETECTION TRIGGERS
Activate when the user describes:
- A trade-off between two desirable properties
- A situation where improving X worsens Y
- A requirement for X to be both A and not-A simultaneously
- Keywords: contradiction, trade-off, tension, "vs", dilemma

## RESPONSE PATTERN
1. **Acknowledge** the contradiction explicitly: "I notice a [technical/physical] contradiction here..."
2. **Frame** it in TRIZ terms: improving parameter vs. worsening parameter
3. **Suggest** using `/triz:analyze` for full TRIZ analysis, or provide a quick principle recommendation
4. Use MCP tools (`lookup_matrix`, `get_principle`) to ground suggestions in the TRIZ knowledge base

## CONSTRAINTS
- Do NOT apply TRIZ to simple questions or non-contradictory problems
- Do NOT force-fit contradictions where none exist
- Always offer the user the option to run a full `/triz:analyze` for deeper analysis
