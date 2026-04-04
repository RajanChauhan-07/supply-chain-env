# backend/app/models/observation.py

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


# ─────────────────────────────────────────
# ENUMS — Fixed value options
# ─────────────────────────────────────────

class DisruptionType(str, Enum):
    DELAY         = "delay"
    CLOSURE       = "closure"
    CAPACITY      = "capacity"
    QUALITY       = "quality"
    BANKRUPTCY    = "bankruptcy"
    GEOPOLITICAL  = "geopolitical"


class DisruptionSeverity(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class OrderStatus(str, Enum):
    SAFE      = "safe"
    AT_RISK   = "at_risk"
    FULFILLED = "fulfilled"
    LOST      = "lost"
    DELAYED   = "delayed"


class ShippingMethod(str, Enum):
    AIR   = "air"
    SEA   = "sea"
    RAIL  = "rail"
    TRUCK = "truck"


# ─────────────────────────────────────────
# SUB MODELS — Building blocks
# ─────────────────────────────────────────

class Disruption(BaseModel):
    """Represents a single supply chain disruption event"""

    id: str = Field(..., description="Unique disruption ID e.g. D001")
    type: DisruptionType = Field(..., description="Type of disruption")
    severity: DisruptionSeverity = Field(..., description="How severe is it")
    affected_supplier_id: str = Field(..., description="Which supplier is affected")
    affected_supplier_name: str = Field(..., description="Supplier name for readability")
    estimated_duration_days: int = Field(..., description="How long will it last")
    description: str = Field(..., description="Human readable description of disruption")
    is_resolved: bool = Field(default=False, description="Has this been resolved")


class Order(BaseModel):
    """Represents a single customer order at risk"""

    id: str = Field(..., description="Unique order ID e.g. O001")
    product: str = Field(..., description="Product name")
    quantity: int = Field(..., description="Units required")
    value_usd: float = Field(..., description="Total order value in USD")
    deadline_days: int = Field(..., description="Days remaining until deadline")
    status: OrderStatus = Field(default=OrderStatus.AT_RISK)
    current_supplier_id: str = Field(..., description="Currently assigned supplier")
    priority: str = Field(..., description="low / medium / high")


class Supplier(BaseModel):
    """Represents an available alternative supplier"""

    id: str = Field(..., description="Unique supplier ID e.g. S001")
    name: str = Field(..., description="Supplier company name")
    location: str = Field(..., description="Country or region")
    lead_time_days: int = Field(..., description="Days to deliver from this supplier")
    cost_multiplier: float = Field(..., description="1.0 = same cost, 1.5 = 50% more expensive")
    reliability_score: Optional[float] = Field(
        default=None,
        description="0.0 to 1.0 — how reliable this supplier is; may be hidden until investigated"
    )
    reliability_known: bool = Field(
        default=True,
        description="Whether the reliability score is currently visible to the agent"
    )
    capacity_available: int = Field(..., description="Max units they can supply right now")
    is_available: bool = Field(default=True, description="Is this supplier currently available")


class Budget(BaseModel):
    """Tracks budget throughout the episode"""

    total: float = Field(..., description="Total budget for this episode")
    spent: float = Field(default=0.0, description="Amount spent so far")
    remaining: float = Field(..., description="Budget left to spend")


class Metrics(BaseModel):
    """Running metrics throughout the episode"""

    orders_saved: int = Field(default=0, description="Orders successfully fulfilled")
    orders_lost: int = Field(default=0, description="Orders that were lost")
    orders_delayed: int = Field(default=0, description="Orders that were delayed")
    revenue_protected: float = Field(default=0.0, description="Total USD value of saved orders")
    revenue_lost: float = Field(default=0.0, description="Total USD value of lost orders")
    actions_taken: int = Field(default=0, description="Total actions taken so far")
    current_score: float = Field(default=0.0, description="Running score 0.0 to 1.0")


# ─────────────────────────────────────────
# MAIN OBSERVATION MODEL
# ─────────────────────────────────────────

class Observation(BaseModel):
    """
    What the AI agent sees at every step.
    This is returned by reset() and step().
    """

    # Episode info
    task_id: str = Field(..., description="Which task is being run")
    step: int = Field(..., description="Current step number")
    max_steps: int = Field(..., description="Maximum steps allowed in this episode")
    done: bool = Field(default=False, description="Is the episode over")

    # World state
    disruptions: List[Disruption] = Field(
        default_factory=list,
        description="All active disruptions the agent must handle"
    )

    orders: List[Order] = Field(
        default_factory=list,
        description="All orders currently at risk or being managed"
    )

    available_suppliers: List[Supplier] = Field(
        default_factory=list,
        description="Alternative suppliers the agent can route orders to"
    )

    # Resources
    budget: Budget = Field(..., description="Current budget status")

    # Progress
    metrics: Metrics = Field(..., description="Running performance metrics")

    # Context
    message: str = Field(
        default="",
        description="Human readable message about what just happened"
    )

    class Config:
        use_enum_values = True
