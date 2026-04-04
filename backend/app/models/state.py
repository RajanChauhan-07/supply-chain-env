# backend/app/models/state.py

from pydantic import BaseModel, Field
from typing import List, Optional
from .observation import Observation, Disruption, Order, Supplier, Budget, Metrics


# ─────────────────────────────────────────
# ACTION HISTORY — Track what agent did
# ─────────────────────────────────────────

class ActionRecord(BaseModel):
    """Records a single action taken during the episode"""

    step: int = Field(..., description="Which step this action was taken")
    action_type: str = Field(..., description="Type of action taken")
    action_summary: str = Field(..., description="Human readable summary")
    reward_received: float = Field(..., description="Reward received for this action")
    was_valid: bool = Field(..., description="Was the action valid")


# ─────────────────────────────────────────
# FULL STATE MODEL
# ─────────────────────────────────────────

class State(BaseModel):
    """
    Complete internal state of the environment.
    Returned by state() endpoint.
    Includes everything — current observation + history.
    """

    # Current task info
    task_id: str = Field(..., description="Current task being run")
    task_name: str = Field(..., description="Human readable task name")
    task_difficulty: str = Field(..., description="easy / medium / hard")

    # Episode progress
    step: int = Field(..., description="Current step number")
    max_steps: int = Field(..., description="Max steps for this episode")
    done: bool = Field(default=False, description="Is episode complete")
    episode_id: str = Field(..., description="Unique ID for this episode run")

    # Full world state
    disruptions: List[Disruption] = Field(default_factory=list)
    orders: List[Order] = Field(default_factory=list)
    available_suppliers: List[Supplier] = Field(default_factory=list)
    budget: Budget = Field(..., description="Budget status")
    metrics: Metrics = Field(..., description="Current metrics")

    # History
    action_history: List[ActionRecord] = Field(
        default_factory=list,
        description="All actions taken so far this episode"
    )

    # Final score (only set when done=True)
    final_score: Optional[float] = Field(
        default=None,
        description="Final graded score 0.0 to 1.0 (set when episode ends)"
    )

    # Score breakdown (only set when done=True)
    score_breakdown: Optional[dict] = Field(
        default=None,
        description="Detailed breakdown of final score components"
    )