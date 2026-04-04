# backend/app/graders/base.py

from abc import ABC, abstractmethod
from typing import Optional
from ..tasks.base import BaseTask


class BaseGrader(ABC):
    """
    Base class for all graders.
    Each grader evaluates a completed episode
    and returns a final score 0.0 to 1.0.
    """

    task_id: str = ""

    def __init__(self, task: BaseTask):
        self.task = task

    @abstractmethod
    def grade(self) -> dict:
        """
        Grade the completed episode.
        Returns a dict with:
            score         → float 0.0 to 1.0
            breakdown     → dict of component scores
            passed        → bool (score >= passing threshold)
            summary       → human readable summary
        """
        pass

    def _safe_ratio(self, numerator: float, denominator: float) -> float:
        """Safe division — returns 0.0 if denominator is 0"""
        if denominator == 0:
            return 0.0
        return round(numerator / denominator, 4)

    def _clamp(self, value: float) -> float:
        """Clamp value between 0.0 and 1.0"""
        return round(min(max(value, 0.0), 1.0), 4)