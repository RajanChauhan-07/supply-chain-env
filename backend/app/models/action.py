# backend/app/models/action.py

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# ─────────────────────────────────────────
# ENUM — All possible action types
# ─────────────────────────────────────────

class ActionType(str, Enum):
    REROUTE        = "reroute"         # Send order to different supplier
    SUBSTITUTE     = "substitute"      # Replace product with alternative
    DELAY          = "delay"           # Push deadline back
    CANCEL         = "cancel"          # Cancel the order entirely
    ESCALATE       = "escalate"        # Escalate disruption to management
    INVESTIGATE    = "investigate"      # Gather more info about a disruption
    # V2: Advanced logistics actions
    HEDGE_FX       = "hedge_fx"         # Buy forward contract on a currency pair
    SELECT_CARRIER = "select_carrier"   # Choose specific carrier for a lane
    REBALANCE_DC   = "rebalance_dc"     # Transfer inventory between DCs
    EXPEDITE       = "expedite"         # Pay premium for faster shipping
    INSURE         = "insure"           # Buy additional cargo insurance
    PRE_CLEAR      = "pre_clear"        # Pre-file customs documentation


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

    # ═══════════════════════════════════════
    # V2: Advanced logistics action fields
    # ═══════════════════════════════════════

    # FOR: hedge_fx
    fx_pair: Optional[str] = Field(
        default=None,
        description="Currency pair to hedge, e.g. 'USD_CNY' (required for hedge_fx)"
    )
    hedge_coverage: Optional[float] = Field(
        default=None,
        description="Target hedge coverage 0.0-1.0 (required for hedge_fx)"
    )

    # FOR: select_carrier
    lane_id: Optional[str] = Field(
        default=None,
        description="Shipping lane ID (required for select_carrier, expedite)"
    )
    carrier_id: Optional[str] = Field(
        default=None,
        description="Carrier ID to assign (required for select_carrier)"
    )

    # FOR: rebalance_dc
    source_dc: Optional[str] = Field(
        default=None,
        description="Source DC ID for inventory transfer (required for rebalance_dc)"
    )
    destination_dc: Optional[str] = Field(
        default=None,
        description="Destination DC ID for inventory transfer (required for rebalance_dc)"
    )
    sku: Optional[str] = Field(
        default=None,
        description="SKU to transfer (required for rebalance_dc)"
    )
    transfer_units: Optional[int] = Field(
        default=None,
        description="Number of units to transfer (required for rebalance_dc)"
    )

    # FOR: expedite
    premium_pct: Optional[float] = Field(
        default=None,
        description="Premium percentage willing to pay for faster shipping (for expedite)"
    )

    # FOR: insure
    insure_shipment_id: Optional[str] = Field(
        default=None,
        description="Shipment ID to insure (required for insure)"
    )

    # FOR: pre_clear
    destination_country: Optional[str] = Field(
        default=None,
        description="Destination country for pre-clearance (required for pre_clear)"
    )

    class Config:
        use_enum_values = True