# backend/app/models/action.py

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# ─────────────────────────────────────────
# ENUM — All possible action types
# ─────────────────────────────────────────

class ActionType(str, Enum):
    REROUTE     = "reroute"      # Send order to different supplier
    SUBSTITUTE  = "substitute"   # Replace product with alternative
    DELAY       = "delay"        # Push deadline back
    CANCEL      = "cancel"       # Cancel the order entirely
    ESCALATE    = "escalate"     # Escalate disruption to management
    INVESTIGATE = "investigate"  # Gather more info about a disruption


class EscalationPriority(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class InvestigationType(str, Enum):
    RELIABILITY = "reliability"  # Check how reliable a supplier is
    CAPACITY    = "capacity"     # Check supplier capacity
    COST        = "cost"         # Check cost implications


# ─────────────────────────────────────────
# MAIN ACTION MODEL
# ─────────────────────────────────────────

class Action(BaseModel):
    """
    What the AI agent does each step.
    This is sent to step().

    Only fill in fields relevant to your action_type.
    Other fields can be left as None.
    """

    # REQUIRED — always
    action_type: ActionType = Field(
        ...,
        description="What type of action to take"
    )

    # FOR: reroute, substitute, delay, cancel
    order_id: Optional[str] = Field(
        default=None,
        description="Which order to act on (required for reroute/substitute/delay/cancel)"
    )

    # FOR: reroute
    new_supplier_id: Optional[str] = Field(
        default=None,
        description="Which supplier to reroute to (required for reroute)"
    )

    shipping_method: Optional[str] = Field(
        default=None,
        description="Shipping method: air / sea / rail / truck (optional for reroute)"
    )

    # FOR: substitute
    alternative_product: Optional[str] = Field(
        default=None,
        description="Alternative product name (required for substitute)"
    )

    notify_customer: Optional[bool] = Field(
        default=True,
        description="Whether to notify customer of change (for substitute/delay)"
    )

    # FOR: delay
    delay_days: Optional[int] = Field(
        default=None,
        description="How many days to push the deadline back (required for delay)"
    )

    reason: Optional[str] = Field(
        default=None,
        description="Reason for delay or cancel action"
    )

    # FOR: escalate
    disruption_id: Optional[str] = Field(
        default=None,
        description="Which disruption to escalate (required for escalate)"
    )

    escalation_priority: Optional[EscalationPriority] = Field(
        default=None,
        description="Priority level for escalation"
    )

    escalation_message: Optional[str] = Field(
        default=None,
        description="Message to send with escalation"
    )

    # FOR: investigate
    target_id: Optional[str] = Field(
        default=None,
        description="ID of supplier or disruption to investigate"
    )

    investigation_type: Optional[InvestigationType] = Field(
        default=None,
        description="What aspect to investigate"
    )

    class Config:
        use_enum_values = True