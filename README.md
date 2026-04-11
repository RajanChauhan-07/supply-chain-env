---
title: Supply Chain Env
emoji: 📦
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# 🔥 God-Level Supply Chain Disruption Management Environment

> A stochastic, multi-tier, multi-objective supply chain RL environment with Apple-scale logistics complexity.

[![OpenEnv Compatible](https://img.shields.io/badge/OpenEnv-Compatible-brightgreen)](https://huggingface.co/openenv)

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                      OpenEnv HTTP API Layer                          │
│          POST /reset  ·  POST /step  ·  GET /grade  ·  GET /validate│
├──────────────────────────────────────────────────────────────────────┤
│                    SupplyChainEngine v2.0                             │
├──────────────────────────────────────────────────────────────────────┤
│ WorldState                                                           │
│ ┌──────────────┐ ┌───────────────┐ ┌──────────────┐ ┌────────────┐  │
│ │SupplyNetwork │ │MarketDynamics │ │  RiskEngine  │ │Constraints │  │
│ │Tier 1/2/3    │ │FX rates       │ │Stochastic    │ │ITAR/EAR    │  │
│ │Lanes+Routes  │ │Spot freight   │ │10 event types│ │SLA floors  │  │
│ │4 Carriers    │ │Insurance loop │ │Historical    │ │Capacity    │  │
│ │Bullwhip      │ │Fuel surcharge │ │calibrated    │ │Budget cap  │  │
│ └──────────────┘ └───────────────┘ └──────────────┘ └────────────┘  │
├──────────────────────────────────────────────────────────────────────┤
│ 10 Tasks: foundational → multi_tier → stochastic → adversarial      │
│           → full_simulation + 5 legacy tasks                         │
├──────────────────────────────────────────────────────────────────────┤
│ Multi-Objective Grading: Cost · Service · Launch · Carbon/ESG        │
└──────────────────────────────────────────────────────────────────────┘
```

## 🚀 What Makes This Different

| Feature | Academic Benchmarks | This Environment |
|---|---|---|
| Supply tiers | Single (Tier 1 only) | **3 tiers** with cascade propagation |
| FX hedging | Not modeled | **4 currency pairs** with mean-reverting random walks |
| Insurance | Not modeled | **Dynamic premiums** that rise with claims (feedback loop) |
| Carrier reliability | Uniform | **Lane-specific, time-variant** per carrier × lane |
| Legal constraints | Soft penalties | **ITAR/EAR hard action masks** — violations REJECTED |
| Demand signal | Static | **Bullwhip effect** — 5% retail → 40% at Tier 3 |
| Disruptions | Pre-programmed | **Stochastic injection** from 10 historical distributions |
| Objectives | Single (cost) | **4-pillar**: cost, service, launch precision, ESG |
| Observation space | ~7 fields | **20+ fields** including DCs, shipments, lanes, carriers |
| Action space | 6 types | **12 types** including hedge_fx, rebalance_dc, insure |

## 📋 Tasks

| # | Task ID | Difficulty | Steps | Key Mechanic |
|---|---|---|---|---|
| 1 | `task_foundational` | Easy | 10 | Single-tier rerouting, basic constraints |
| 2 | `task_multi_tier` | Medium | 20 | Tier 1/2/3 cascading, bullwhip effect |
| 3 | `task_stochastic` | Hard | 25 | Dynamic FX, stochastic disruptions, launch pressure |
| 4 | `task_adversarial_v2` | Hard | 20 | Trap suppliers, insurance feedback loops |
| 5 | `task_full_sim` | Expert | 30 | Everything: multi-tier + FX + ITAR + bullwhip + traps |
| 6-10 | Legacy (v1) | Various | 10-30 | Simpler scenarios for backward compatibility |

## 🎯 Multi-Objective Grading

Every task is graded on 4 real-world objectives:

1. **Cost Minimization** (30%) — Freight + handling + duties + FX hedging + insurance
2. **Service Level** (30%) — On-time delivery, stockout avoidance, SLA compliance
3. **Launch Precision** (25%) — Zero late shipments during launch window
4. **Carbon/ESG** (15%) — Sea-over-air preference, emissions per unit

## 🔧 Simulation Core

### Multi-Tier Supply Network
- **Tier 1 (Assembly):** Foxconn, Pegatron, Jabil, Flex — 4 suppliers
- **Tier 2 (Components):** Corning, Samsung Display, LG, TSMC, Infineon — 5 suppliers
- **Tier 3 (Raw Materials):** Shin-Etsu, MP Materials, Albemarle, Glencore — 4 suppliers
- **Lanes:** 9 shipping lanes (sea, air, rail, truck) with congestion modeling
- **Carriers:** Maersk, FedEx, DHL, COSCO — lane-specific reliability

### Market Dynamics
- **FX Rates:** USD/CNY, USD/EUR, USD/INR, USD/JPY — mean-reverting random walks
- **Spot Freight:** Seasonal pattern + disruption surges
- **Insurance:** Base premium × (1 + claim_count × 0.3) — penalizes risky routing
- **Fuel Surcharge:** Stochastic drift, 0.5-2.0x multiplier

### Stochastic Risk Engine (10 Disruption Types)
```
port_strike (6%)  ·  typhoon (10%, seasonal)  ·  tariff_shock (4%)
suez_blockage (2%)  ·  chip_shortage (3%)  ·  cyber_attack (5%)
pandemic_wave (2%)  ·  earthquake (1%)  ·  sanctions (3%)  ·  labor_shortage (8%)
```

### Hard Constraints (Action Masks)
- **ITAR/EAR:** 3 export control restrictions — certain routes FORBIDDEN
- **SLA Floors:** 6 DCs with minimum fill rates (80-90%)
- **Capacity Ceilings:** Port throughput limits
- **Budget Envelope:** $5M quarterly cap

## 📊 Observation Space (20+ fields)

```json
{
  "task_id": "task_full_sim",
  "step": 5,
  "disruptions": [...],
  "orders": [...],
  "available_suppliers": [...],
  "supply_tiers": {"tier1": {...}, "tier2": {...}, "tier3": {...}},
  "fx_rates": {"USD_CNY": {"rate": 7.28, "change_pct": +0.55}},
  "insurance_premiums": {"SH_LAX": {"rate_pct": 2.60, "claims": 1}},
  "bullwhip_state": {"tier1": "+1.2%", "tier2": "+3.6%", "tier3": "+9.6%"},
  "shipping_lanes": [...],
  "carrier_options": [...],
  "demand_forecast": {"americas": {"30d": 45000, "60d": 42000}},
  "launch_countdown": 10,
  "dc_inventory": {"DC_LAX": {"stock": {"iPhone": 25000}}},
  "legal_constraints": [{"id": "ITAR_001", ...}],
  "sla_status": {"DC_LAX": {"fill_rate": 0.87, "floor": 0.85}},
  "capacity_utilization": {"PORT_SH": {"used": 0, "max": 100000}}
}
```

## 🎮 Action Space (12 Types)

```python
# Basic (v1)
"reroute", "substitute", "delay", "cancel", "escalate", "investigate"

# Advanced (v2)
"hedge_fx"         # Buy FX forward contract on a currency pair
"select_carrier"   # Choose specific carrier for a lane
"rebalance_dc"     # Transfer inventory between DCs
"expedite"         # Pay premium for faster shipping
"insure"           # Buy cargo insurance on a shipment
"pre_clear"        # Pre-file customs documentation
```

## 🏃 Quick Start

### Local Development
```bash
pip install fastapi uvicorn pydantic httpx openai
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 7860
```

### Docker
```bash
docker build -t supply-chain-env .
docker run -p 7860:7860 supply-chain-env
```

### Run Inference
```bash
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export HF_TOKEN="your-token"
python inference.py
```

### Validate
```bash
curl http://localhost:7860/validate
```

## 🧪 Baseline Scores

| Task | Baseline Score | Approach |
|---|---|---|
| `task_foundational` | 0.30 | Untouched (no action) |
| `task_multi_tier` | 0.25 | Untouched |
| `task_stochastic` | 0.50 | Untouched |
| `task_adversarial_v2` | 0.35 | Untouched |
| `task_full_sim` | 0.38 | Untouched |

## 📐 API Reference

All endpoints follow the OpenEnv standard:

| Method | Endpoint | Description |
|---|---|---|
| POST | `/reset?task_id=...&seed=...` | Reset environment for a specific task |
| POST | `/step` | Take one action (JSON body) |
| GET | `/grade` | Get current/final score with multi-objective breakdown |
| GET | `/state` | Read-only state snapshot |
| GET | `/tasks` | List all available tasks |
| GET | `/validate` | Self-validation smoke test |
| GET | `/schema` | JSON schemas for action/observation/state |
| GET | `/health` | Health check |

## 📁 Project Structure

```
supply-chain-env/
├── backend/
│   └── app/
│       ├── main.py                    # FastAPI application
│       ├── config.py                  # Settings
│       ├── environment/
│       │   ├── engine.py              # SupplyChainEngine
│       │   └── disruptions.py         # Disruption utilities
│       ├── simulation/                # ★ V2 Simulation Core
│       │   ├── world_state.py         # Master state
│       │   ├── supply_network.py      # Multi-tier network
│       │   ├── market_dynamics.py     # FX, freight, insurance
│       │   ├── risk_engine.py         # Stochastic disruptions
│       │   └── constraints.py         # ITAR, SLA, capacity
│       ├── models/
│       │   ├── observation.py         # 20+ field observation
│       │   ├── action.py              # 12 action types
│       │   ├── reward.py              # Multi-objective rewards
│       │   └── state.py               # State model
│       ├── tasks/
│       │   ├── base.py                # BaseTask
│       │   ├── task_foundational.py   # Task 1: Basic
│       │   ├── task_multi_tier.py     # Task 2: Cascading
│       │   ├── task_stochastic.py     # Task 3: Dynamic
│       │   ├── task_adversarial_v2.py # Task 4: Traps
│       │   └── task_full_sim.py       # Task 5: Everything
│       └── graders/
│           ├── base.py                # BaseGrader
│           └── grader.py              # 10 graders
├── inference.py                       # Baseline agent
├── openenv.yaml                       # Environment spec
├── Dockerfile
└── README.md
```

## 📄 License

MIT
