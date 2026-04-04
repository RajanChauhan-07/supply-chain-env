from __future__ import annotations

import argparse
import json

from backend.app.rl.action_catalog import build_action_catalog
from backend.app.rl.encoding import OBSERVATION_VECTOR_LENGTH, encode_observation
from inference import choose_fallback_action

try:
    from backend.app.rl.gym_wrapper import SupplyChainGymEnv
except ImportError as exc:  # pragma: no cover - optional dependency
    SupplyChainGymEnv = None
    GYM_IMPORT_ERROR = exc
else:
    GYM_IMPORT_ERROR = None


def run_discrete_heuristic(env: SupplyChainGymEnv, task_id: str) -> dict:
    _, info = env.reset(options={"task_id": task_id})
    escalated_ids: set[str] = set()
    total_reward = 0.0
    steps = 0
    done = False
    last_info = info

    while not done and steps < 64:
        steps += 1
        raw_observation = last_info["raw_observation"]
        desired = choose_fallback_action(raw_observation, escalated_ids)
        catalog = env.get_action_catalog()
        try:
            action_index = next(
                idx for idx, candidate in enumerate(catalog) if candidate == desired
            )
        except StopIteration:
            action_index = 0

        if desired.get("action_type") == "escalate" and desired.get("disruption_id"):
            escalated_ids.add(desired["disruption_id"])

        _, reward, terminated, truncated, last_info = env.step(action_index)
        total_reward += reward
        done = terminated or truncated

    return {
        "task_id": task_id,
        "steps": steps,
        "final_score": last_info.get("final_score"),
        "total_reward": round(total_reward, 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test RL wrapper readiness.")
    parser.add_argument("--task-id", default="task_hard")
    parser.add_argument("--check-env", action="store_true")
    parser.add_argument("--train-ppo", action="store_true")
    parser.add_argument("--timesteps", type=int, default=512)
    args = parser.parse_args()

    if SupplyChainGymEnv is None:
        raise SystemExit(
            "gymnasium/numpy not installed. Install requirements-rl.txt to use rl_smoke.py."
        )

    env = SupplyChainGymEnv(default_task_id=args.task_id)
    encoded, info = env.reset(options={"task_id": args.task_id})
    report = {
        "task_id": args.task_id,
        "observation_vector_length": OBSERVATION_VECTOR_LENGTH,
        "encoded_length": len(encoded),
        "action_catalog_size": len(info["action_catalog"]),
        "sample_action_catalog_head": info["action_catalog"][:5],
        "render_message": env.render(),
    }

    if args.check_env:
        from stable_baselines3.common.env_checker import check_env

        check_env(env, warn=True)
        report["check_env"] = "passed"

    report["heuristic_smoke"] = run_discrete_heuristic(env, args.task_id)

    if args.train_ppo:
        from stable_baselines3 import PPO

        model = PPO("MlpPolicy", env, verbose=0, n_steps=64, batch_size=64)
        model.learn(total_timesteps=args.timesteps)
        obs, _ = env.reset(options={"task_id": args.task_id})
        total_reward = 0.0
        final_info = {}
        for _ in range(64):
            action, _ = model.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, final_info = env.step(action)
            total_reward += reward
            if terminated or truncated:
                break
        report["ppo_smoke"] = {
            "timesteps": args.timesteps,
            "total_reward": round(total_reward, 4),
            "final_score": final_info.get("final_score"),
        }

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
