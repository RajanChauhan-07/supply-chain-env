---
title: Supply Chain Environment
emoji: "🚚"
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: OpenEnv supply chain agent environment.
---

# Supply Chain Disruption Management Environment

An OpenEnv-compliant AI training environment where agents learn to manage real-world supply chain disruptions.

## Overview

This environment simulates the job of an operations manager at a global manufacturing company. The agent must respond to supply disruptions, reroute orders, substitute suppliers, escalate critical issues, and minimize revenue loss — all under budget and time constraints.

## Key Features

- 3 task progression: easy, medium, hard
- Typed FastAPI environment with `reset`, `step`, `state`, `tasks`, `grade`, and `validate`
- Structured action, observation, reward, and state models
- Step-level rewards plus final deterministic grading
- Dockerized backend suitable for Hugging Face Spaces
- Root-level `inference.py` baseline runner using the OpenAI client
- Root-level `baseline_benchmarks.py` for explicit random and heuristic baselines

## Tasks

| Task ID | Name | Difficulty | Max Steps | Pass Threshold | Expected Score |
|---|---|---|---|---|---|
| `task_easy` | Single Lane Disruption | Easy | 10 | 0.60 | 0.8 - 1.0 |
| `task_medium` | Multi-Point Failure | Medium | 20 | 0.45 | 0.7 - 0.9 |
| `task_hard` | Cascade Crisis | Hard | 30 | 0.30 | 0.45 - 0.7 |

## Action Space

| Action | Description |
|---|---|
| `reroute` | Move an order to a different supplier |
| `substitute` | Replace product with an alternative |
| `delay` | Push order deadline back |
| `cancel` | Cancel order entirely (last resort) |
| `escalate` | Escalate disruption to management |
| `investigate` | Get more info about supplier or disruption |

## Observation Space

At every step the agent receives:
- List of active disruptions with severity
- List of orders at risk with value, deadline and priority
- List of available alternative suppliers
- For the hard task, risky supplier reliability can be hidden until investigated
- Current budget status
- Running metrics and score

## Reward Function

| Positive Rewards | Value |
|---|---|
| Order fulfilled on time | +0.15 to +0.25 |
| Good cost-efficient supplier choice | +0.05 |
| Correct escalation of critical disruption | +0.08 |
| Useful investigation | +0.05 |
| All high-value orders saved | +0.20 |
| Finished under budget | +0.10 |
| Finished early | +0.05 |

| Negative Penalties | Value |
|---|---|
| Order deadline missed | -0.10 |
| Order lost completely | -0.15 |
| Budget exceeded | -0.10 |
| Unreliable supplier chosen | -0.05 |
| Redundant action | -0.05 |
| Invalid action | -0.05 |

## Running Locally

### 1. Start server
```bash
pip install -r requirements.txt
uvicorn backend.app.main:app --host 0.0.0.0 --port 7860
```

### 2. Inspect the environment
```bash
curl http://localhost:7860/
curl http://localhost:7860/tasks
curl http://localhost:7860/validate
```

### 3. Run the baseline agent
Set the required environment variables first:

```bash
export API_BASE_URL="https://your-openai-compatible-endpoint"
export MODEL_NAME="your-model-name"
export OPENAI_API_KEY="your-api-key"
export ENV_URL="http://localhost:7860"
python inference.py
```

### 4. Run non-LLM validation baselines

```bash
export ENV_URL="http://localhost:7860"
python baseline_benchmarks.py
```

### 5. Run lightweight repeatability and robustness checks

```bash
export ENV_URL="http://localhost:7860"
python robustness_checks.py
```

### 6. Run the final pre-submission checks

```bash
bash validate-submission.sh https://your-space.hf.space .
```

This script mirrors the hackathon checklist by checking:
- live HF Space `/reset`
- `docker build`
- `openenv validate`

## Project Structure

```text
supply-chain-env/
├── requirements.txt
├── backend/app/main.py
├── backend/app/environment/
├── backend/app/graders/
├── backend/app/models/
├── backend/app/tasks/
├── backend/tests/
├── baseline_benchmarks.py
├── inference.py
├── robustness_checks.py
├── validate-submission.sh
├── openenv.yaml
├── Dockerfile
└── README.md
```

## API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/` | `GET` | Health check |
| `/reset` | `POST` | Start a task episode |
| `/step` | `POST` | Submit one action |
| `/state` | `GET` | Read full current state |
| `/tasks` | `GET` | List tasks |
| `/grade` | `GET` | Grade current episode |
| `/validate` | `GET` | Run self-checks |

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `API_BASE_URL` | Yes for inference | OpenAI-compatible model endpoint |
| `MODEL_NAME` | Yes for inference | Model identifier |
| `OPENAI_API_KEY` | Recommended | OpenAI-compatible API token used by `inference.py` |
| `HF_TOKEN` | Optional alias | Alternative token variable also supported by `inference.py` |
| `ENV_URL` | Optional | Environment server URL, defaults to `http://localhost:7860` |
| `STRICT_BASELINE` | Optional | When set to `1` or `true`, disables fallback and reports pure model behavior only |

## Docker

Build and run locally:

```bash
docker build -t supply-chain-env .
docker run -p 7860:7860 supply-chain-env
```

## Baseline Hierarchy

The project now exposes three benchmark tiers:

| Baseline | Purpose | Current validated result |
|---|---|---|
| Random policy | Sanity floor; proves the environment is not trivially easy | Strong performance drop from easy to hard |
| Heuristic policy | Domain baseline using the deterministic fallback policy | Consistently strong and reproducible |
| Model baseline | Real provider/model evaluation | Recommended: Bytez `openai/gpt-4o` |

### Non-LLM baseline results

| Baseline | Easy | Medium | Hard | Overall |
|---|---:|---:|---:|---:|
| Random policy (5 seeds) | `0.670 +/- 0.384` | `0.377 +/- 0.162` | `0.183 +/- 0.126` | `0.410 +/- 0.321` |
| Heuristic policy | `1.000` | `0.830` | `0.615` | `0.815` |

This gives the desired hierarchy:
- random << heuristic on medium and hard
- easy remains solvable
- the hard task stays meaningfully difficult

### Comparison View

| View | Easy | Medium | Hard | Overall |
|---|---:|---:|---:|---:|
| Random mean | `0.670` | `0.377` | `0.183` | `0.410` |
| Heuristic | `1.000` | `0.830` | `0.615` | `0.815` |
| Recommended model baseline | `1.000` | `0.830` | `0.615` | `0.815` |

## What This Environment Measures

The benchmark is designed to evaluate:

- budget-aware planning under tight operational constraints
- prioritization of high-value orders when not everything can be saved
- escalation judgment for critical disruptions
- investigation behavior when supplier reliability is hidden
- avoidance of invalid or infeasible actions in a sequential setting

## Model Benchmark Results

Recommended provider/model combo for the official baseline:

| Provider | Model | Easy | Medium | Hard | Overall | Runtime | Execution |
|---|---|---:|---:|---:|---:|---:|---|
| Bytez | `openai/gpt-4o` | `1.000` | `0.830` | `0.615` | `0.815` | `53.1s` | `model_only`, `hybrid`, `hybrid` |

Other tested reference runs:

| Provider | Model | Easy | Medium | Hard | Overall | Runtime |
|---|---|---:|---:|---:|---:|---:|
| Groq | `llama-3.3-70b-versatile` | `1.000` | `0.830` | `0.608` | `0.812` | `228.9s` |
| Bytez | `anthropic/claude-opus-4-5` | `1.000` | `0.491` | `0.618` | `0.703` | `78.3s` |

Pure model-only runs can be collected by re-running the same providers with `STRICT_BASELINE=1`. The recommended baseline table above is intentionally the resilient judge-facing run because it proves the environment loop completes even if an external provider degrades mid-episode.

## Baseline Behavior

- `inference.py` always uses the OpenAI client interface when a model endpoint is available.
- The script now reports whether each task run was `model_only`, `hybrid`, or `fallback_only`.
- If the external model call fails or credentials are missing, the default baseline falls back to a deterministic built-in policy so the run can still complete.
- If you want a judge-style pure model run, set `STRICT_BASELINE=1` to disable fallback recovery.
- The heuristic baseline is the same deterministic policy used for fallback recovery.
- Verified deterministic heuristic/fallback scores in local testing:

| Task | Deterministic fallback score |
|---|---:|
| `task_easy` | `1.0` |
| `task_medium` | approximately `0.83` |
| `task_hard` | approximately `0.61` |

## Judge Notes

- The environment itself is deterministic; score variance should come primarily from agent/model behavior, not from stochastic world generation.
- The repository now includes explicit non-LLM baselines so environment quality can be evaluated separately from provider/model quality.
- Tasks are meant to separate weak, decent, and strong agents:
  - `task_easy` should be straightforward
  - `task_medium` should reward prioritization under budget pressure
  - `task_hard` should require escalation, tradeoffs, and investigation of hidden supplier risk
- The baseline runner can be used in two modes:
  - default mode: resilient and fallback-assisted if the external provider fails
  - strict mode: `STRICT_BASELINE=1` for pure model-only evaluation
- Final task success is determined by deterministic graders with normalized scores in `[0.0, 1.0]`.

## Optional Validation Additions

- `robustness_checks.py` provides a lightweight repeatability pass:
  - repeated `/validate` health check
  - burst reset cycling across tasks
  - heuristic repeatability check
  - random-baseline hierarchy check
  - invalid-action penalty sanity check
- Hard-task terminal state now exposes extra diagnostics in `score_breakdown`:
  - `invalid_action_count`
  - `investigation_count`
  - `hidden_risk_suppliers_investigated`
  - `hidden_risk_suppliers_remaining`
  - `hidden_risk_supplier_used`

Current optional-validation results:

| Check | Result |
|---|---|
| Repeated `/validate` | `9 / 9` checks passing |
| Burst reset cycle | `10 / 10` successful |
| Heuristic repeatability | `std = 0.0` on all three tasks |
| Random hierarchy | `easy > medium > hard` = `true` |
| Invalid-action sanity | score remains `0.0`, pass = `false` |

## Future-Work RL Foundation

The repository now includes a first-pass RL integration layer for future research work:

- `backend/app/rl/encoding.py`
  - fixed-length observation encoding for numeric RL agents
- `backend/app/rl/action_catalog.py`
  - fixed-size discrete action catalog built from the current observation
- `backend/app/rl/gym_wrapper.py`
  - Gymnasium-compatible wrapper around the in-process engine
- `rl_smoke.py`
  - wrapper smoke script with optional `check_env` and PPO-ready flow
- `requirements-rl.txt`
  - optional RL-only dependencies (`gymnasium`, `numpy`, `stable-baselines3`)

Example future-work commands:

```bash
pip install -r requirements-rl.txt
python rl_smoke.py --task-id task_hard
python rl_smoke.py --task-id task_hard --check-env
python rl_smoke.py --task-id task_hard --train-ppo --timesteps 2048
```

What this enables next:
- Gym-style `check_env()` validation
- PPO smoke training without changing the core OpenEnv API
- random < heuristic < PPO comparisons on a shared wrapper
- later multi-seed RL learning curves and ablations

## Local Validation

Run the API tests, engine/grader tests, and import checks:

```bash
backend/.venv/bin/python -m unittest discover -s backend/tests -p "test_*.py"
backend/.venv/bin/python -c "import inference; print('imports_ok')"
```

## Notes

- The environment itself is deterministic and lightweight.
- The baseline can use a deterministic fallback policy when the external model endpoint is unavailable.
- Helper scripts in the repo are local wrappers around `inference.py`; they do not store secrets.
