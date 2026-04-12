# Baseline Comparison Results

| Task | Qwen-72B Agent | CostGreedy | SLAPriority | ITARBreaker |
|------|-----------|------------|-------------|-------------|
| task_foundational | 0.582 | 0.528 | 0.443 | 0.176 |
| task_multi_tier | 0.613 | 0.312 | 0.455 | 0.001 |
| task_stochastic | 0.686 | 0.428 | 0.509 | 0.001 |
| task_adversarial_v2 | 0.560 | 0.111 | 0.287 | 0.001 |
| task_full_sim | 0.710 | 0.395 | 0.522 | 0.001 |
| **Average** | **0.630** | **0.355** | **0.443** | **0.036** |

## Key Observations
- **LLM Agent** (Qwen-72B-Instruct): Best overall with multi-objective reasoning, handling phase 1 (inventory), phase 2 (routing cost vs reliability), and phase 3 (constraints).
- **CostGreedy**: Falls into trap suppliers on adversarial tasks (score ~0.11), prioritizing nominal routing cost over supplier stability and triggering cascade failure.
- **SLAPriority**: High service score but budget blowout reduces cost pillar. Always pays premium air freight.
- **ITARBreaker**: Constraint mask blocks all illegal actions (score ≈ 0.001). Demonstrates deterministic restriction engine works perfectly.
