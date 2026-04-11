# backend/app/models/reward.py

from pydantic import BaseModel, Field
from typing import List, Optional


# ─────────────────────────────────────────
# REWARD BREAKDOWN — Why did I get this score?
# ─────────────────────────────────────────

class RewardBreakdown(BaseModel):
    """
    Detailed breakdown of what contributed to reward.
    Helps agent understand WHY it got that reward.
    """

    orders_saved_reward: float = Field(
        default=0.0,
        description="Reward from saving orders"
    )

    deadline_met_reward: float = Field(
        default=0.0,
        description="Reward from meeting deadlines"
    )

    budget_efficiency_reward: float = Field(
        default=0.0,
        description="Reward from staying within budget"
    )

    good_supplier_choice_reward: float = Field(
        default=0.0,
        description="Reward for choosing reliable/cheap supplier"
    )

    escalation_reward: float = Field(
        default=0.0,
        description="Reward for correct escalation decisions"
    )

    investigation_reward: float = Field(
        default=0.0,
        description="Reward for useful investigation actions"
    )

    # Penalties
    missed_deadline_penalty: float = Field(
        default=0.0,
        description="Penalty for missing deadlines (negative)"
    )

    order_lost_penalty: float = Field(
        default=0.0,
        description="Penalty for losing orders (negative)"
    )

    budget_exceeded_penalty: float = Field(
        default=0.0,
        description="Penalty for going over budget (negative)"
    )

    bad_supplier_penalty: float = Field(
        default=0.0,
        description="Penalty for choosing unreliable supplier (negative)"
    )

    redundant_action_penalty: float = Field(
        default=0.0,
        description="Penalty for useless/redundant actions (negative)"
    )

    inaction_penalty: float = Field(
        default=0.0,
        description="Penalty for doing nothing when crisis is active (negative)"
    )

    # ═══════════════════════════════════════
    # V2: Multi-Objective Breakdown
    # ═══════════════════════════════════════

    cost_score: float = Field(
        default=0.0,
        description="Cost optimization score (freight + handling + duties + FX + insurance)"
    )

    service_level_score: float = Field(
        default=0.0,
        description="Service level score (on-time rate, stockout avoidance, SLA compliance)"
    )

    launch_precision_score: float = Field(
        default=0.0,
        description="Launch precision (zero late launch shipments, global availability sync)"
    )

    esg_score: float = Field(
        default=0.0,
        description="Carbon/ESG score (sea-over-air preference, emissions per unit)"
    )

    constraint_compliance: float = Field(
        default=0.0,
        description="Hard constraint compliance (ITAR, SLA floors, capacity — should be 1.0)"
    )

    cascade_prevention: float = Field(
        default=0.0,
        description="Score for preventing bullwhip/cascade amplification"
    )

    trap_detection: float = Field(
        default=0.0,
        description="Score for detecting and avoiding supplier traps"
    )


# ─────────────────────────────────────────
# MAIN REWARD MODEL
# ─────────────────────────────────────────

class Reward(BaseModel):
    """
    Reward returned after each step().
    Provides rich signal — not just a number.
    """

    # The actual reward value
    value: float = Field(
        ...,
        description="Reward for this step. Can be negative. Range roughly -1.0 to +1.0"
    )

    # Cumulative score so far (normalized 0.0 to 1.0)
    cumulative_score: float = Field(
        ...,
        description="Total normalized score so far this episode. Always 0.0 to 1.0"
    )

    # Breakdown of what caused this reward
    breakdown: RewardBreakdown = Field(
        ...,
        description="Detailed breakdown of reward components"
    )

    # Human readable explanation
    reason: str = Field(
        ...,
        description="Human readable explanation of reward"
    )

    # Was this action valid?
    action_valid: bool = Field(
        default=True,
        description="Was the action structurally valid and executable"
    )

    # If invalid, why?
    invalid_reason: Optional[str] = Field(
        default=None,
        description="If action was invalid, explains why"
    )