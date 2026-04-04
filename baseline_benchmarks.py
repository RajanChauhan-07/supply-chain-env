import json
import os
import random
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from contextlib import contextmanager

import httpx

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from inference import choose_fallback_action


ENV_BASE_URL = os.environ.get("ENV_URL", "http://127.0.0.1:7860")
TASK_IDS = ["task_easy", "task_medium", "task_hard"]
DEFAULT_RANDOM_SEEDS = [7, 21, 42, 84, 1337]
TASK_SEED_OFFSETS = {"task_easy": 11, "task_medium": 29, "task_hard": 53}
LOCK_PATH = Path("/tmp/supply_chain_env_benchmark.lock")


@contextmanager
def benchmark_lock(timeout_seconds: float = 30.0):
    deadline = time.time() + timeout_seconds
    lock_fd = None

    while True:
        try:
            lock_fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(lock_fd, str(os.getpid()).encode("utf-8"))
            break
        except FileExistsError:
            if time.time() >= deadline:
                raise RuntimeError(
                    f"Benchmark lock already held at {LOCK_PATH}. "
                    "Run benchmark scripts sequentially against the same environment."
                )
            time.sleep(0.2)

    try:
        yield
    finally:
        if lock_fd is not None:
            os.close(lock_fd)
        try:
            LOCK_PATH.unlink()
        except FileNotFoundError:
            pass


def env_reset(task_id: str) -> dict:
    response = httpx.post(
        f"{ENV_BASE_URL}/reset",
        params={"task_id": task_id},
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()["observation"]


def env_step(action: dict) -> dict:
    response = httpx.post(
        f"{ENV_BASE_URL}/step",
        json=action,
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


def env_grade() -> dict:
    response = httpx.get(f"{ENV_BASE_URL}/grade", timeout=30.0)
    response.raise_for_status()
    return response.json()


@dataclass
class RunResult:
    task_id: str
    steps: int
    score: float
    passed: bool
    total_reward: float


class HeuristicPolicy:
    name = "heuristic"

    def __init__(self) -> None:
        self.escalated_ids: set[str] = set()

    def act(self, observation: dict) -> dict:
        action = choose_fallback_action(observation, self.escalated_ids)
        if action.get("action_type") == "escalate" and action.get("disruption_id"):
            self.escalated_ids.add(action["disruption_id"])
        return action


class RandomPolicy:
    name = "random"

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)

    def act(self, observation: dict) -> dict:
        at_risk_orders = [
            order for order in observation.get("orders", [])
            if order.get("status") == "at_risk"
        ]
        active_disruptions = [
            disruption for disruption in observation.get("disruptions", [])
            if not disruption.get("is_resolved")
        ]
        suppliers = observation.get("available_suppliers", [])

        actions = []

        if active_disruptions:
            disruption = self.rng.choice(active_disruptions)
            actions.append({
                "action_type": "escalate",
                "disruption_id": disruption["id"],
                "escalation_priority": self.rng.choice(["low", "medium", "high", "critical"]),
                "escalation_message": "Random baseline escalation.",
            })
            actions.append({
                "action_type": "investigate",
                "target_id": disruption["id"],
                "investigation_type": self.rng.choice(["reliability", "capacity", "cost"]),
            })

        if suppliers:
            supplier = self.rng.choice(suppliers)
            actions.append({
                "action_type": "investigate",
                "target_id": supplier["id"],
                "investigation_type": self.rng.choice(["reliability", "capacity", "cost"]),
            })

        if at_risk_orders:
            order = self.rng.choice(at_risk_orders)
            if suppliers:
                supplier = self.rng.choice(suppliers)
                actions.append({
                    "action_type": "reroute",
                    "order_id": order["id"],
                    "new_supplier_id": supplier["id"],
                    "shipping_method": self.rng.choice(["air", "sea", "rail", "truck"]),
                })
            actions.append({
                "action_type": "delay",
                "order_id": order["id"],
                "delay_days": self.rng.choice([3, 7, 14]),
                "reason": "Random baseline delay.",
            })
            actions.append({
                "action_type": "cancel",
                "order_id": order["id"],
                "reason": "Random baseline cancellation.",
            })

        if not actions:
            return {
                "action_type": "investigate",
                "target_id": "D001",
                "investigation_type": "reliability",
            }

        return self.rng.choice(actions)


def run_policy_on_task(policy, task_id: str, max_steps: int) -> RunResult:
    observation = env_reset(task_id)
    total_reward = 0.0
    done = False
    step = 0

    while not done and step < max_steps:
        step += 1
        action = policy.act(observation)
        result = env_step(action)
        observation = result["observation"]
        total_reward += result["reward"]["value"]
        done = result["done"]

    grade = env_grade()
    return RunResult(
        task_id=task_id,
        steps=step,
        score=grade["score"],
        passed=grade["passed"],
        total_reward=round(total_reward, 4),
    )


def summarize_runs(results: list[RunResult]) -> dict:
    per_task: dict[str, list[float]] = {}
    for result in results:
        per_task.setdefault(result.task_id, []).append(result.score)

    task_stats = {
        task_id: {
            "mean": round(statistics.mean(scores), 4),
            "std": round(statistics.pstdev(scores), 4),
            "runs": len(scores),
        }
        for task_id, scores in per_task.items()
    }

    overall_scores = [result.score for result in results]
    return {
        "task_stats": task_stats,
        "overall_mean": round(statistics.mean(overall_scores), 4),
        "overall_std": round(statistics.pstdev(overall_scores), 4),
        "total_runs": len(results),
    }


def print_summary(name: str, summary: dict) -> None:
    print(f"\n{name.upper()} BASELINE")
    print("-" * 52)
    print(f"{'Task':<14}{'Mean':>8}{'Std':>8}{'Runs':>8}")
    for task_id in TASK_IDS:
        stats = summary["task_stats"][task_id]
        print(f"{task_id:<14}{stats['mean']:>8.3f}{stats['std']:>8.3f}{stats['runs']:>8}")
    print("-" * 52)
    print(f"{'OVERALL':<14}{summary['overall_mean']:>8.3f}{summary['overall_std']:>8.3f}{summary['total_runs']:>8}")


def main() -> None:
    with benchmark_lock():
        print(f"ENV URL: {ENV_BASE_URL}")

        heuristic_results = [
            run_policy_on_task(HeuristicPolicy(), task_id, max_steps={"task_easy": 10, "task_medium": 20, "task_hard": 30}[task_id])
            for task_id in TASK_IDS
        ]
        heuristic_summary = summarize_runs(heuristic_results)
        print_summary("heuristic", heuristic_summary)

        random_results: list[RunResult] = []
        for seed in DEFAULT_RANDOM_SEEDS:
            for task_id in TASK_IDS:
                random_results.append(
                    run_policy_on_task(
                        RandomPolicy(seed + TASK_SEED_OFFSETS[task_id]),
                        task_id,
                        max_steps={"task_easy": 10, "task_medium": 20, "task_hard": 30}[task_id],
                    )
                )
        random_summary = summarize_runs(random_results)
        print_summary("random", random_summary)

        print("\nJSON Results:")
        print(json.dumps({
            "heuristic": heuristic_summary,
            "random": random_summary,
        }, indent=2))


if __name__ == "__main__":
    main()
