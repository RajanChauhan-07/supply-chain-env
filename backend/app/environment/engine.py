# backend/app/environment/engine.py

import uuid
from typing import Optional, Dict, Any
from ..tasks.base import BaseTask
from ..tasks import TASK_REGISTRY, TASK_LIST
from ..graders import get_grader
from ..models import Action, Observation, Reward, State


class SupplyChainEngine:
    """
    Core environment engine.
    Manages the active task, episode lifecycle,
    and exposes reset() / step() / state() methods.

    This is what the FastAPI layer talks to.
    One engine instance = one running environment.
    """

    def __init__(self):
        self.current_task: Optional[BaseTask] = None
        self.current_task_id: Optional[str]   = None
        self.episode_count: int                = 0
        self.is_ready: bool                    = False

    # ─────────────────────────────────────
    # CORE API METHODS
    # ─────────────────────────────────────

    def reset(self, task_id: str = "task_easy") -> Observation:
        """
        Start a fresh episode for the given task.
        Returns the initial observation.

        Args:
            task_id: One of task_easy / task_medium / task_hard

        Returns:
            Observation: Initial state of the environment
        """
        # Validate task_id
        if task_id not in TASK_REGISTRY:
            raise ValueError(
                f"Unknown task_id: '{task_id}'. "
                f"Valid options: {list(TASK_REGISTRY.keys())}"
            )

        # Instantiate fresh task
        task_class         = TASK_REGISTRY[task_id]
        self.current_task  = task_class()
        self.current_task_id = task_id
        self.episode_count += 1
        self.is_ready       = True

        # Reset and return initial observation
        observation = self.current_task.reset()
        return observation

    def step(self, action: Action) -> Dict[str, Any]:
        """
        Take one action in the current episode.

        Args:
            action: Action pydantic model

        Returns:
            dict with keys:
                observation → Observation
                reward      → Reward
                done        → bool
                info        → dict
        """
        self._check_ready()

        observation, reward, done, info = self.current_task.step(action)

        # If episode just ended — run grader
        if done:
            grader      = get_grader(self.current_task)
            grade_result = grader.grade()

            info["grader_result"] = {
                "score":     grade_result["score"],
                "passed":    grade_result["passed"],
                "breakdown": grade_result["breakdown"],
                "summary":   grade_result["summary"],
            }
            info["final_score"] = grade_result["score"]

        return {
            "observation": observation,
            "reward":      reward,
            "done":        done,
            "info":        info,
        }

    def state(self) -> State:
        """
        Return full current state of the environment.
        Read-only — does not advance the episode.

        Returns:
            State: Complete environment state including history
        """
        self._check_ready()
        return self.current_task.get_state()

    # ─────────────────────────────────────
    # GRADING
    # ─────────────────────────────────────

    def grade(self) -> Dict[str, Any]:
        """
        Manually trigger grading on current episode.
        Works even if episode is not done yet
        (returns partial score).
        """
        self._check_ready()
        grader = get_grader(self.current_task)
        return grader.grade()

    # ─────────────────────────────────────
    # TASK INFO
    # ─────────────────────────────────────

    def list_tasks(self) -> list:
        """Return list of all available tasks"""
        return TASK_LIST

    def get_task_info(self, task_id: str) -> dict:
        """Return info about a specific task"""
        for task in TASK_LIST:
            if task["id"] == task_id:
                return task
        raise ValueError(f"Task '{task_id}' not found")

    def get_engine_info(self) -> dict:
        """Return general engine status"""
        return {
            "name":            "Supply Chain Disruption Management",
            "version":         "1.0.0",
            "total_tasks":     len(TASK_REGISTRY),
            "episode_count":   self.episode_count,
            "current_task_id": self.current_task_id,
            "is_ready":        self.is_ready,
            "current_step":    self.current_task.current_step if self.current_task else None,
            "current_done":    self.current_task.done if self.current_task else None,
        }

    # ─────────────────────────────────────
    # PRIVATE HELPERS
    # ─────────────────────────────────────

    def _check_ready(self):
        """Raise error if engine not initialized"""
        if not self.is_ready or self.current_task is None:
            raise RuntimeError(
                "Environment not initialized. "
                "Call reset(task_id) first."
            )