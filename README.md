---
title: Supply Chain Env
emoji: 📦
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# 🔥 God-Level Supply Chain Simulation Environment

> A stochastic, multi-tier, multi-objective RL environment modeling Apple-scale global logistics complexity.

[![OpenEnv Compatible](https://img.shields.io/badge/OpenEnv-Compatible-brightgreen)](https://huggingface.co/openenv)

**Documentation Suite (Judges Start Here):**
- 🚀 **[EVAL.md](EVAL.md)** — Single-command evaluation guide to reproduce all results.
- ⚖️ **[GRADER_SPEC.md](GRADER_SPEC.md)** — Formal grading specification (pillars, weights, thresholds).
- 🎮 **[ACTION_REFERENCE.md](ACTION_REFERENCE.md)** — All 12 actions (FX, insurance, routing) detailed.

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      OpenEnv HTTP API Layer                          │
│          POST /reset  ·  POST /step  ·  GET /grade  ·  GET /validate │
├──────────────────────────────────────────────────────────────────────┤
│                    SupplyChainEngine v2.0                            │
├──────────────────────────────────────────────────────────────────────┤
│ WorldState                                                           │
│ ┌──────────────┐ ┌───────────────┐ ┌──────────────┐ ┌────────────┐ │
│ │SupplyNetwork │ │MarketDynamics │ │  RiskEngine  │ │Constraints │ │
│ │Tier 1/2/3    │ │FX rates       │ │Stochastic    │ │ITAR/EAR    │ │
│ │Lanes+Routes  │ │Spot freight   │ │10 event types│ │SLA floors  │ │
│ │4 Carriers    │ │Insurance loop │ │Correlated    │ │Capacity    │ │
│ │Bullwhip      │ │Hedge P&L      │ │shocks        │ │Budget cap  │ │
│ └──────────────┘ └───────────────┘ └──────────────┘ └────────────┘ │
├──────────────────────────────────────────────────────────────────────┤
│ 10 Tasks: foundational → multi_tier → stochastic → adversarial     │
│           → full_simulation + 5 legacy tasks                       │
├──────────────────────────────────────────────────────────────────────┤
│ Multi-Objective Grading: Cost · Service · Launch · Carbon/ESG      │
└──────────────────────────────────────────────────────────────────────┘
```

## 🚀 What Makes This "God-Level"

Unlike academic benchmarks that focus solely on inventory equations, this environment models the chaotic reality of global trade operations:

| Feature | Academic Baselines | This Environment |
|---|---|---|
| **Supply Tiers** | Single | **3 Tiers** with partial observability (Tier 3 hidden until researched). |
| **Market Volatility** | Static costs | **FX Hedging** required to protect budget; spot freight surges during crises. |
| **Risk & Insurance** | Fixed events | **Insurance feedback loops** — claims raise future route premiums. |
| **Adversarial Traps** | None | **Trap suppliers** look cheap but fail 2 steps later if uninvestigated. |
| **Legal/Compliance** | Soft penalties | **ITAR/EAR Hard Constraints** — geopolitical action masks block routes. |
| **Disruption Model** | Independent | **Correlated Shocks** —e.g. Typhoon has 60% chance to trigger Port Strike. |
| **Coordination Penalties**| None | **Cross-layer coherence** — e.g. selecting a sea route without customs pre-clearance reduces score. |

## 📋 Evaluation Tasks

| Task ID | Difficulty | Description |
|---|---|---|
| `task_foundational` | Easy | Single-tier rerouting under budget and capacity constraints. |
| `task_multi_tier` | Medium | Tier 1/2/3 cascading failures. **Root causes hidden** until investigated. |
| `task_stochastic` | Hard | **FX hedging** and **insurance** required to survive a barrage of correlated disruptions. |
| `task_adversarial_v2`| Hard | Trap suppliers everywhere. Investigate first or lose budget to catastrophic secondary failures. |
| `task_full_sim` | Expert | Everything active simultaneously. Apple-scale launch pressure. Multi-objective balancing. |

## 🧪 Baseline Agent Performance

We provide 4 complete inference baselines in `inference.py` to prove environment stratification and utility.

Run with: `python inference.py --run-all-baselines`

| Task | Qwen-72B Agent | CostGreedy Baseline | SLAPriority Baseline | ITARBreaker Baseline |
|------|-----------|------------|-------------|-------------|
| task_foundational | **0.582** | 0.528 | 0.443 | 0.176 |
| task_multi_tier | **0.613** | 0.312 | 0.455 | 0.001 |
| task_stochastic | **0.686** | 0.428 | 0.509 | 0.001 |
| task_adversarial_v2 | **0.560** | 0.111 | 0.287 | 0.001 |
| task_full_sim | **0.710** | 0.395 | 0.522 | 0.001 |
| **Average** | **0.630** | **0.355** | **0.443** | **0.036** |

**Observations:**
- **CostGreedy** fails `task_adversarial_v2` explicitly. It routes to the cheapest "trap" suppliers, resulting in catastrophic failures 2 steps later.
- **SLAPriority** fails the Cost pillar globally. It routes everything via premium Air freight to hit deadlines, blowing past the $5M budget limit.
- **ITARBreaker** demonstrates the robustness of the constraint engine. It continually attempts forbidden routes and gets a near 0.0 score.
- **LLM Agent** is using a structured 3-phase reasoning prompt (Inventory → Routing → Compliance) and handles partial observability perfectly.

## 🏃 Quick Start

### 1. Docker
```bash
docker build -t supply-chain-env .
docker run -p 7860:7860 supply-chain-env
```

### 2. Verify
```bash
curl http://localhost:7860/validate
# {"status": "valid", "checks_passed": 15, "checks_failed": 0}
```

### 3. Run Universal Inference
The agent works with **any OpenAI-compatible API** (HuggingFace, Together, local vLLM).
It automatically detects reasoning models (DeepSeek-R1, Sarvam) and adapts.

```bash
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export HF_TOKEN="your-hf-token"

python inference.py
```

## 📐 Full API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/reset?task_id=...` | Reset into a specific scenario |
| POST | `/step` | Execute an action |
| GET | `/grade` | Complete multi-objective summary |
| GET | `/state` | Full world state |
| GET | `/validate` | OpenEnv self-validation |
| GET | `/docs` | Swagger UI |

## 📄 License

MIT
