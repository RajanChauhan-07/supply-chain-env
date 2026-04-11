# backend/app/models/observation.py

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


# ─────────────────────────────────────────
# ENUMS — Fixed value options
# ─────────────────────────────────────────

class DisruptionType(str, Enum):
    DELAY            = "delay"
    CLOSURE          = "closure"
    CAPACITY         = "capacity"
    QUALITY          = "quality"
    BANKRUPTCY       = "bankruptcy"
    GEOPOLITICAL     = "geopolitical"
    FACTORY_FIRE     = "factory_fire"
    PORT_CLOSURE     = "port_closure"
    REGULATORY       = "regulatory"
    CYBER_ATTACK     = "cyber_attack"
    SUPPLY_SURGE     = "supply_surge"
    QUALITY_RECALL   = "quality_recall"
    EMBARGO          = "embargo"
    SUPPLIER_FAILURE = "supplier_failure"
    # V2: Risk engine event types
    PORT_STRIKE      = "port_strike"
    TYPHOON          = "typhoon"
    TARIFF_SHOCK     = "tariff_shock"
    SUEZ_BLOCKAGE    = "suez_blockage"
    CHIP_SHORTAGE    = "chip_shortage"
    PANDEMIC_WAVE    = "pandemic_wave"
    EARTHQUAKE       = "earthquake"
    SANCTIONS        = "sanctions"
    LABOR_SHORTAGE   = "labor_shortage"


class DisruptionSeverity(str, Enum):
    LOW      = "low"
    MEDIUM   = "medium"
    HIGH     = "high"
    CRITICAL = "critical"


class OrderStatus(str, Enum):
    SAFE      = "safe"
    ACTIVE    = "active"
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
    original_supplier_id: Optional[str] = Field(default=None, description="Original supplier before disruption")
    priority: str = Field(..., description="low / medium / high / critical")
    region: Optional[str] = Field(default=None, description="Geographic region: asia, europe, americas")


class Supplier(BaseModel):
    """Represents an available alternative supplier"""

    id: str = Field(..., description="Unique supplier ID e.g. S001")
    name: str = Field(..., description="Supplier company name")
    location: str = Field(default="", description="Country or region")
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
    region: Optional[str] = Field(default=None, description="Geographic region for cascade tracking")


class Budget(BaseModel):
    """Tracks budget throughout the episode"""

    total: float = Field(..., description="Total budget for this episode")
    spent: float = Field(default=0.0, description="Amount spent so far")
    remaining: float = Field(..., description="Budget left to spend")
    currency: str = Field(default="USD", description="Currency code")


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

    The v2 fields (supply_tiers, fx_rates, etc.) are Optional —
    simpler tasks leave them as None for backward compatibility.
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

    # ═══════════════════════════════════════
    # V2: Multi-Tier Supply Network
    # ═══════════════════════════════════════

    supply_tiers: Optional[dict] = Field(
        default=None,
        description="Multi-tier supplier network: tier1 (assembly), tier2 (components), tier3 (raw materials)"
    )

    shipping_lanes: Optional[list] = Field(
        default=None,
        description="Available shipping lanes with transit time, cost, congestion, ITAR restrictions"
    )

    carrier_options: Optional[list] = Field(
        default=None,
        description="Carrier profiles with lane-specific reliability and cost"
    )

    # ═══════════════════════════════════════
    # V2: Market Dynamics
    # ═══════════════════════════════════════

    fx_rates: Optional[dict] = Field(
        default=None,
        description="FX rates: USD/CNY, USD/EUR, USD/INR, USD/JPY with change % and hedge coverage"
    )

    fx_hedge_coverage: Optional[float] = Field(
        default=None,
        description="Overall FX hedge coverage fraction (0.0-1.0)"
    )

    spot_freight_rates: Optional[dict] = Field(
        default=None,
        description="Current spot freight rates per shipping lane"
    )

    fuel_surcharge: Optional[float] = Field(
        default=None,
        description="Current fuel surcharge multiplier (1.0 = normal)"
    )

    insurance_premiums: Optional[dict] = Field(
        default=None,
        description="Per-lane insurance premium rates (dynamic — rise with claims)"
    )

    # ═══════════════════════════════════════
    # V2: Risk Context
    # ═══════════════════════════════════════

    weather_severity: Optional[dict] = Field(
        default=None,
        description="Per-region weather risk index (0.0-1.0)"
    )

    geopolitical_tension: Optional[dict] = Field(
        default=None,
        description="Per-region geopolitical risk score (0.0-1.0)"
    )

    bullwhip_state: Optional[dict] = Field(
        default=None,
        description="Demand amplification per tier (bullwhip effect). E.g. tier1: +2.3%, tier3: +18.4%"
    )

    # ═══════════════════════════════════════
    # V2: Demand Signals
    # ═══════════════════════════════════════

    demand_forecast: Optional[dict] = Field(
        default=None,
        description="30/60/90 day demand forecast by region with uncertainty"
    )

    launch_countdown: Optional[int] = Field(
        default=None,
        description="Days until next product launch (-1 = no upcoming launch)"
    )

    # ═══════════════════════════════════════
    # V2: Inventory
    # ═══════════════════════════════════════

    dc_inventory: Optional[dict] = Field(
        default=None,
        description="Stock levels at 6 global distribution centers per SKU"
    )

    in_transit_shipments: Optional[list] = Field(
        default=None,
        description="Shipments currently in transit with ETA and carrier info"
    )

    # ═══════════════════════════════════════
    # V2: Hard Constraints
    # ═══════════════════════════════════════

    legal_constraints: Optional[list] = Field(
        default=None,
        description="ITAR/EAR export control restrictions — routes that are FORBIDDEN"
    )

    sla_status: Optional[dict] = Field(
        default=None,
        description="SLA fill rates at each DC vs. minimum floors"
    )

    capacity_utilization: Optional[dict] = Field(
        default=None,
        description="Current vs. max throughput at ports/warehouses"
    )

    class Config:
        use_enum_values = True

