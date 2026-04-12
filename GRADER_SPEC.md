# GRADER_SPEC.md — Formal Grading Specification

> This document is the canonical reference for how every task is scored.
> Judges: use this to verify grading fairness and normalization.

## Scoring Architecture

Every task returns a score in the **open interval (0.001, 0.999)**.
- `0.0` is never returned — even total failure yields `0.001` (environment ran, agent failed).
- `1.0` is never returned — there's always room for improvement.
- Scores are **deterministic** given the same seed and action sequence.

---

## V2 Tasks (Primary Evaluation Suite)

### task_foundational
| Property | Value |
|----------|-------|
| **Difficulty** | Easy |
| **Max Steps** | 10 |
| **Pass Threshold** | 0.40 |
| **0.0 Anchor** | Agent does nothing — all orders remain `at_risk` |
| **1.0 Anchor** | All 3 orders fulfilled on-time, budget under 50%, all disruptions escalated |

| Pillar | Weight | Metric |
|--------|--------|--------|
| Revenue Protection | 0.40 | `(saved + delayed×0.5) / total_value` |
| Budget Efficiency | 0.25 | `max(0, 1 - spent/total × 1.5)` |
| Investigation Depth | 0.20 | `investigated / hidden_suppliers` |
| Escalation Coverage | 0.15 | `acted_disruptions / total_disruptions` |

---

### task_multi_tier
| Property | Value |
|----------|-------|
| **Difficulty** | Medium |
| **Max Steps** | 20 |
| **Pass Threshold** | 0.35 |
| **Partial Observability** | Yes — Tier 3 hidden until investigated |
| **0.0 Anchor** | Agent ignores root cause, reroutes at Tier 1 only |
| **1.0 Anchor** | Investigates T3 root cause, diversifies across tiers, all orders saved |

| Pillar | Weight | Metric |
|--------|--------|--------|
| Revenue Protection | 0.40 | `(saved + delayed×0.4) / total_value` |
| Budget Efficiency | 0.25 | `max(0, 1 - spent/total × 1.5)` |
| Investigation Depth | 0.20 | `investigated / hidden_suppliers` |
| Escalation Coverage | 0.15 | `acted_disruptions / total_disruptions` |

---

### task_stochastic
| Property | Value |
|----------|-------|
| **Difficulty** | Hard |
| **Max Steps** | 25 |
| **Pass Threshold** | 0.35 |
| **0.0 Anchor** | Random actions, ignores FX/insurance signals |
| **1.0 Anchor** | Hedges FX optimally, manages insurance, all orders on-time pre-launch |

| Pillar | Weight | Metric |
|--------|--------|--------|
| Cost Efficiency | 0.30 | `max(0, 1 - spent/total)` |
| Service Level | 0.30 | `on_time_value / total_value` |
| Launch Precision | 0.25 | `1.0 if countdown ≤ 0 and loss = 0, else 0.5` |
| ESG | 0.15 | `0.5` (baseline — no carbon tracking in this task) |
| **Coordination Penalty** | Deducted | -0.02 per sea route without pre_clear (capped at 0.10) |

---

### task_adversarial_v2
| Property | Value |
|----------|-------|
| **Difficulty** | Hard |
| **Max Steps** | 20 |
| **Pass Threshold** | 0.30 |
| **0.0 Anchor** | Routes to all 3 traps, all fail — zero revenue, budget wasted |
| **1.0 Anchor** | Investigates all 5 unknowns, avoids all traps, 0 failures |

| Pillar | Weight | Metric |
|--------|--------|--------|
| Revenue After Traps | 0.25 | `saved / total_value` (after trap failures resolve) |
| Trap Detection | 0.25 | `traps_investigated / total_traps` |
| Zero Trap Failures | 0.20 | `1.0 if 0 failures, else 0.0` |
| Budget Efficiency | 0.15 | `max(0, 1 - spent/total)` |
| Investigation Depth | 0.15 | `investigated / hidden_suppliers` |

---

### task_full_sim
| Property | Value |
|----------|-------|
| **Difficulty** | Expert |
| **Max Steps** | 30 |
| **Pass Threshold** | 0.30 |
| **0.0 Anchor** | Agent does nothing — all orders at_risk, launch missed, traps hit |
| **1.0 Anchor** | All criticals on-time, budget efficient, sea freight, 0 traps, ITAR clean |

| Pillar | Weight | Metric |
|--------|--------|--------|
| Cost Efficiency | 0.30 | `max(0, 1 - spent/total)` |
| Service Level | 0.30 | `(saved + delayed×0.3) / total_value` |
| Launch Precision | 0.25 | `critical_fulfilled / total_critical_orders` |
| ESG/Carbon | 0.15 | `sea_units / (sea_units + air_units)` |

**Bonuses/Penalties (applied to raw score):**
| Modifier | Value |
|----------|-------|
| Trap failure | -0.05 per occurrence |
| Regional cascade (≥4 reroutes) | -0.05 per region |
| Investigation bonus | +0.02 per investigated (capped at +0.10) |
| **Coordination penalty** | Up to -0.15 (sea without pre_clear, hedge without exposure, etc.) |

---

## V1 Tasks (Legacy, Still Functional)

| Task | Difficulty | Steps | Threshold | Pillars |
|------|-----------|-------|-----------|---------|
| task_easy | Easy | 10 | 0.40 | Revenue(0.50), Budget(0.30), Escalation(0.20) |
| task_medium | Medium | 20 | 0.35 | Revenue(0.40), Budget(0.25), Investigation(0.20), Escalation(0.15) |
| task_hard | Hard | 30 | 0.30 | Revenue(0.40), Budget(0.25), Investigation(0.20), Escalation(0.15) |
| task_expert | Expert | 25 | 0.25 | Revenue(0.35), Budget(0.25), Region Diversity(0.20), Investigation(0.10), Escalation(0.10) |
| task_adversarial | Hard | 20 | 0.30 | Revenue Post-Trap(0.25), Trap Detection(0.25), Zero Failures(0.20), Budget(0.15), Investigation(0.15) |

---

## Reward Normalization

All per-step rewards are in `[-0.20, +0.30]`:
- Successful on-time reroute: `+0.25`
- Good supplier choice bonus: `+0.05`
- Successful escalation: `+0.10`
- Investigation reveal: `+0.10`
- Redundant action: `-0.05`
- Budget exceeded: `-0.10`
- Bad supplier (known unreliable): `-0.15`
- Trap supplier reroute (uninvestigated): `+0.15` initially, then `-0.15` when it fails

Final task score is computed from the **terminal state** (not sum of rewards).
