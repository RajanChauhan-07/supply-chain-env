import json
import os
from statistics import mean, pstdev

import httpx

from baseline_benchmarks import (
    DEFAULT_RANDOM_SEEDS,
    HeuristicPolicy,
    RandomPolicy,
    TASK_IDS,
    TASK_SEED_OFFSETS,
    env_grade,
    env_reset,
    env_step,
    run_policy_on_task,
)


ENV_BASE_URL = os.environ.get("ENV_URL", "http://127.0.0.1:7860")
MAX_STEPS = {"task_easy": 10, "task_medium": 20, "task_hard": 30}


def validate_endpoint() -> dict:
    response = httpx.get(f"{ENV_BASE_URL}/validate", timeout=30.0)
    response.raise_for_status()
    return response.json()


def burst_reset_check(iterations: int = 10) -> dict:
    results = []
    for index in range(iterations):
        task_id = TASK_IDS[index % len(TASK_IDS)]
        observation = env_reset(task_id)
        results.append({
            "task_id": task_id,
            "orders": len(observation["orders"]),
            "disruptions": len(observation["disruptions"]),
        })
    return {
        "iterations": iterations,
        "all_successful": len(results) == iterations,
        "results": results,
    }


def heuristic_repeatability_check(runs: int = 3) -> dict:
    scores_by_task = {task_id: [] for task_id in TASK_IDS}

    for _ in range(runs):
        for task_id in TASK_IDS:
            result = run_policy_on_task(HeuristicPolicy(), task_id, MAX_STEPS[task_id])
            scores_by_task[task_id].append(result.score)

    return {
        task_id: {
            "scores": scores,
            "mean": round(mean(scores), 4),
            "std": round(pstdev(scores), 4),
            "stable": len(set(scores)) == 1,
        }
        for task_id, scores in scores_by_task.items()
    }


def random_hierarchy_check() -> dict:
    scores_by_task = {task_id: [] for task_id in TASK_IDS}

    for seed in DEFAULT_RANDOM_SEEDS:
        for task_id in TASK_IDS:
            result = run_policy_on_task(
                RandomPolicy(seed + TASK_SEED_OFFSETS[task_id]),
                task_id,
                MAX_STEPS[task_id],
            )
            scores_by_task[task_id].append(result.score)

    means = {
        task_id: round(mean(scores), 4)
        for task_id, scores in scores_by_task.items()
    }
    hierarchy_ok = means["task_easy"] > means["task_medium"] > means["task_hard"]

    return {
        "means": means,
        "hierarchy_ok": hierarchy_ok,
        "scores_by_task": scores_by_task,
    }


def invalid_action_penalty_check() -> dict:
    env_reset("task_easy")
    env_step({"action_type": "reroute", "order_id": "O001", "new_supplier_id": "INVALID"})
    grade = env_grade()
    return {
        "score_after_invalid_action": grade["score"],
        "still_in_range": 0.0 <= grade["score"] <= 1.0,
        "passed": grade["passed"],
    }


def main() -> None:
    report = {
        "environment_url": ENV_BASE_URL,
        "validate": validate_endpoint(),
        "burst_reset": burst_reset_check(),
        "heuristic_repeatability": heuristic_repeatability_check(),
        "random_hierarchy": random_hierarchy_check(),
        "invalid_action_penalty": invalid_action_penalty_check(),
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
