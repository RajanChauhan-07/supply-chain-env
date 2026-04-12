# EVAL.md — Evaluation Guide for Judges

> Single-command evaluation guide. Follow these steps to reproduce all results.

## Quick Start (< 5 minutes)

### 1. Start the Environment
```bash
# Option A: Docker (recommended)
docker build -t supply-chain . && docker run -p 7860:7860 supply-chain

# Option B: Direct (requires Python 3.10+)
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 7860
```

### 2. Verify Environment
```bash
curl http://localhost:7860/validate
# Expected: {"status": "valid", "checks_passed": 15, "checks_failed": 0}
```

### 3. Run LLM Inference
```bash
export HF_TOKEN="your-huggingface-token"
export ENV_URL="http://localhost:7860"
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"

python inference.py
```

### 4. Run All Baselines + Comparison
```bash
python inference.py --run-all-baselines
# Generates BASELINE_RESULTS.md with comparison table
```

### 5. Run Individual Baselines
```bash
python inference.py --baseline cost_greedy      # Cheapest-first (fails on traps)
python inference.py --baseline sla_priority      # Fastest-first (blows budget)
python inference.py --baseline itar_breaker      # Adversarial (proves constraint mask)
```

---

## Expected Results

| Agent | Avg Score | Notable Behavior |
|-------|-----------|-----------------|
| LLM (Qwen-72B) | ~0.630 | Best multi-objective reasoning |
| CostGreedy | ~0.350 | Falls into traps on adversarial tasks |
| SLAPriority | ~0.450 | High service but terrible cost efficiency |
| ITARBreaker | ~0.001 | All actions blocked by constraint mask |

---

## What to Look For

### 1. Environment Robustness
- ✅ All 10 tasks complete without errors
- ✅ ITAR constraint mask blocks all illegal actions (verify with `itar_breaker`)
- ✅ Trap suppliers fail after 2 steps (verify `task_adversarial_v2` logs)
- ✅ Insurance claims resolve after 3 steps and credit budget

### 2. Simulation Fidelity
- ✅ FX hedge positions carry across steps (check `hedge_book` in observation)
- ✅ Carrier reliability degrades with overuse (check `usage_count` in carrier lanes)
- ✅ Correlated disruptions fire (e.g., typhoon triggers port_strike)
- ✅ Partial observability in `task_multi_tier` (Tier 3 is hidden)

### 3. Grading Integrity
- ✅ Scores in open interval (0.001, 0.999)
- ✅ Coordination penalties applied for incoherent cross-layer decisions
- ✅ Multi-objective breakdown shown in grade response

### 4. Inference Quality
- ✅ Three-phase reasoning (Inventory → Routing → Compliance)
- ✅ Self-correction loop (repair rate logged)
- ✅ Deterministic baselines prove environment difficulty stratification

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/reset` | POST | Reset environment with `?task_id=<id>` |
| `/step` | POST | Take action (JSON body) |
| `/state` | GET | Get current state |
| `/grade` | GET | Get final grade |
| `/tasks` | GET | List all available tasks |
| `/validate` | GET | Run all validation checks |
| `/docs` | GET | Swagger UI |

---

## Live Deployment

The environment is live at: `https://rajanchauhan-supply-chain-env.hf.space`

To run inference against the live deployment:
```bash
export ENV_URL="https://rajanchauhan-supply-chain-env.hf.space"
python inference.py
```
