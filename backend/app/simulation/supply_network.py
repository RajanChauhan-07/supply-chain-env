# backend/app/simulation/supply_network.py
"""
Multi-tier supply network model with lane-specific carrier reliability.

Models:
  Tier 1 — Assembly (Foxconn, Pegatron) — finished product assembly
  Tier 2 — Components (Corning glass, Samsung displays) — sub-components
  Tier 3 — Raw materials (rare earth, lithium) — geological/geopolitical risk

Disruptions cascade DOWN: Tier 3 → Tier 2 → Tier 1 with stochastic delay.
Bullwhip effect: 5% demand shift at retail → 15% at Tier 2 → 40% at Tier 3.
"""

from dataclasses import dataclass, field
from typing import Optional
import random
import math


@dataclass
class Carrier:
    """A shipping carrier with lane-specific reliability."""
    id: str
    name: str
    # lane_id → reliability (0.0-1.0), time-variant
    lane_reliability: dict = field(default_factory=dict)
    # lane_id → base cost multiplier
    lane_cost: dict = field(default_factory=dict)
    # Global base reliability (fallback when no lane-specific data)
    base_reliability: float = 0.90
    base_cost: float = 1.0

    def get_reliability(self, lane_id: str, step: int = 0) -> float:
        """Get time-variant, lane-specific reliability."""
        base = self.lane_reliability.get(lane_id, self.base_reliability)
        # Add small time-variant noise (±5%)
        noise = 0.05 * math.sin(step * 0.3 + hash(lane_id) % 100)
        return max(0.1, min(1.0, base + noise))

    def get_cost(self, lane_id: str) -> float:
        return self.lane_cost.get(lane_id, self.base_cost)


@dataclass
class Lane:
    """A shipping lane between two locations with carrier options."""
    id: str
    origin: str          # e.g., "shanghai"
    destination: str     # e.g., "los_angeles"
    mode: str            # "air", "sea", "rail", "truck"
    base_transit_days: int
    base_cost_per_unit: float
    congestion_score: float = 0.0   # 0.0 (clear) to 1.0 (jammed)
    is_available: bool = True
    itar_restricted: bool = False   # Hard legal constraint

    @property
    def effective_transit_days(self) -> int:
        """Transit time adjusted for congestion."""
        congestion_add = int(self.congestion_score * self.base_transit_days * 0.5)
        return self.base_transit_days + congestion_add


@dataclass
class TierSupplier:
    """A supplier within a specific tier of the supply network."""
    id: str
    name: str
    tier: int                    # 1, 2, or 3
    region: str                  # "asia", "europe", "americas"
    location: str                # "shenzhen", "rotterdam", etc.
    capacity: int                # Max units per period
    capacity_used: int = 0
    lead_time_days: int = 5
    cost_multiplier: float = 1.0
    reliability: float = 0.90
    reliability_known: bool = True
    is_disrupted: bool = False
    disruption_id: Optional[str] = None
    # Sub-component dependencies (Tier 1 depends on Tier 2 suppliers, etc.)
    depends_on: list = field(default_factory=list)

    @property
    def capacity_available(self) -> int:
        return max(0, self.capacity - self.capacity_used)


@dataclass
class Tier:
    """A tier of the supply network."""
    level: int              # 1, 2, or 3
    name: str               # "Assembly", "Components", "Raw Materials"
    suppliers: list = field(default_factory=list)  # list[TierSupplier]
    bullwhip_gain: float = 1.0  # Demand amplification factor


class SupplyNetwork:
    """
    Complete multi-tier supply network.
    Manages suppliers across 3 tiers, shipping lanes, and carriers.
    """

    BULLWHIP_GAINS = {1: 1.0, 2: 3.0, 3: 8.0}  # Demand amplification per tier

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.tiers: dict[int, Tier] = {}
        self.lanes: list[Lane] = []
        self.carriers: list[Carrier] = []
        self._build_default_network()

    def _build_default_network(self):
        """Build a realistic multi-tier supply network."""
        # ── TIER 1: Assembly ──────────────────────────
        tier1 = Tier(level=1, name="Assembly", bullwhip_gain=self.BULLWHIP_GAINS[1])
        tier1.suppliers = [
            TierSupplier(id="T1_FOX", name="Foxconn Shenzhen", tier=1,
                         region="asia", location="shenzhen",
                         capacity=50000, lead_time_days=3, cost_multiplier=1.0,
                         reliability=0.94, depends_on=["T2_CRN", "T2_SAM"]),
            TierSupplier(id="T1_PEG", name="Pegatron Shanghai", tier=1,
                         region="asia", location="shanghai",
                         capacity=35000, lead_time_days=4, cost_multiplier=1.05,
                         reliability=0.91, depends_on=["T2_CRN", "T2_LGD"]),
            TierSupplier(id="T1_JAB", name="Jabil Penang", tier=1,
                         region="asia", location="penang",
                         capacity=20000, lead_time_days=5, cost_multiplier=1.12,
                         reliability=0.88, depends_on=["T2_SAM"]),
            TierSupplier(id="T1_FLX", name="Flex Guadalajara", tier=1,
                         region="americas", location="guadalajara",
                         capacity=15000, lead_time_days=2, cost_multiplier=1.20,
                         reliability=0.92, depends_on=["T2_TSM"]),
        ]

        # ── TIER 2: Components ────────────────────────
        tier2 = Tier(level=2, name="Components", bullwhip_gain=self.BULLWHIP_GAINS[2])
        tier2.suppliers = [
            TierSupplier(id="T2_CRN", name="Corning Glass", tier=2,
                         region="americas", location="kentucky",
                         capacity=80000, lead_time_days=7, cost_multiplier=1.0,
                         reliability=0.96, depends_on=["T3_SIL"]),
            TierSupplier(id="T2_SAM", name="Samsung Display", tier=2,
                         region="asia", location="asan",
                         capacity=60000, lead_time_days=6, cost_multiplier=1.10,
                         reliability=0.93, depends_on=["T3_REE"]),
            TierSupplier(id="T2_LGD", name="LG Display", tier=2,
                         region="asia", location="paju",
                         capacity=40000, lead_time_days=8, cost_multiplier=1.15,
                         reliability=0.89, depends_on=["T3_REE"]),
            TierSupplier(id="T2_TSM", name="TSMC Wafers", tier=2,
                         region="asia", location="hsinchu",
                         capacity=30000, lead_time_days=14, cost_multiplier=1.30,
                         reliability=0.97, depends_on=["T3_SIL", "T3_REE"]),
            TierSupplier(id="T2_INF", name="Infineon Sensors", tier=2,
                         region="europe", location="munich",
                         capacity=25000, lead_time_days=10, cost_multiplier=1.08,
                         reliability=0.90, depends_on=["T3_SIL"]),
        ]

        # ── TIER 3: Raw Materials ─────────────────────
        tier3 = Tier(level=3, name="Raw Materials", bullwhip_gain=self.BULLWHIP_GAINS[3])
        tier3.suppliers = [
            TierSupplier(id="T3_SIL", name="Shin-Etsu Silicon", tier=3,
                         region="asia", location="niigata",
                         capacity=200000, lead_time_days=21, cost_multiplier=1.0,
                         reliability=0.95),
            TierSupplier(id="T3_REE", name="MP Materials Rare Earth", tier=3,
                         region="americas", location="mountain_pass",
                         capacity=100000, lead_time_days=28, cost_multiplier=1.0,
                         reliability=0.85),
            TierSupplier(id="T3_LIT", name="Albemarle Lithium", tier=3,
                         region="americas", location="chile",
                         capacity=150000, lead_time_days=30, cost_multiplier=1.0,
                         reliability=0.80),
            TierSupplier(id="T3_COB", name="Glencore Cobalt", tier=3,
                         region="africa", location="drc",
                         capacity=80000, lead_time_days=35, cost_multiplier=1.0,
                         reliability=0.70),
        ]

        self.tiers = {1: tier1, 2: tier2, 3: tier3}

        # ── SHIPPING LANES ───────────────────────────
        self.lanes = [
            Lane(id="SH_LAX", origin="shanghai", destination="los_angeles",
                 mode="sea", base_transit_days=14, base_cost_per_unit=2.50),
            Lane(id="SH_LAX_AIR", origin="shanghai", destination="los_angeles",
                 mode="air", base_transit_days=2, base_cost_per_unit=12.00),
            Lane(id="SH_AMS", origin="shanghai", destination="amsterdam",
                 mode="sea", base_transit_days=28, base_cost_per_unit=3.00),
            Lane(id="SH_AMS_SUEZ", origin="shanghai", destination="amsterdam",
                 mode="sea", base_transit_days=22, base_cost_per_unit=3.50),
            Lane(id="GDL_LAX", origin="guadalajara", destination="los_angeles",
                 mode="truck", base_transit_days=2, base_cost_per_unit=1.80),
            Lane(id="KY_LAX", origin="kentucky", destination="los_angeles",
                 mode="rail", base_transit_days=4, base_cost_per_unit=1.20),
            Lane(id="MUN_AMS", origin="munich", destination="amsterdam",
                 mode="truck", base_transit_days=1, base_cost_per_unit=0.90),
            Lane(id="HSC_SH", origin="hsinchu", destination="shanghai",
                 mode="sea", base_transit_days=3, base_cost_per_unit=1.50),
            # ITAR restricted lane
            Lane(id="SH_TLV", origin="shanghai", destination="tel_aviv",
                 mode="air", base_transit_days=4, base_cost_per_unit=15.00,
                 itar_restricted=True),
        ]

        # ── CARRIERS ──────────────────────────────────
        self.carriers = [
            Carrier(id="MAERSK", name="Maersk Line",
                    lane_reliability={"SH_LAX": 0.92, "SH_AMS": 0.88, "SH_AMS_SUEZ": 0.85},
                    lane_cost={"SH_LAX": 1.0, "SH_AMS": 1.0, "SH_AMS_SUEZ": 1.10},
                    base_reliability=0.90),
            Carrier(id="FEDEX", name="FedEx Express",
                    lane_reliability={"SH_LAX_AIR": 0.96, "SH_LAX": 0.80, "GDL_LAX": 0.94},
                    lane_cost={"SH_LAX_AIR": 1.0, "GDL_LAX": 1.05},
                    base_reliability=0.93, base_cost=1.15),
            Carrier(id="DHL", name="DHL Global",
                    lane_reliability={"MUN_AMS": 0.97, "SH_AMS": 0.91, "SH_LAX_AIR": 0.94},
                    lane_cost={"MUN_AMS": 0.95, "SH_AMS": 1.05},
                    base_reliability=0.91, base_cost=1.10),
            Carrier(id="COSCO", name="COSCO Shipping",
                    lane_reliability={"SH_LAX": 0.89, "SH_AMS": 0.86, "HSC_SH": 0.93},
                    lane_cost={"SH_LAX": 0.85, "SH_AMS": 0.88},
                    base_reliability=0.87, base_cost=0.85),
        ]

    def get_all_suppliers_flat(self) -> list[TierSupplier]:
        """Return all suppliers across all tiers as a flat list."""
        result = []
        for tier in self.tiers.values():
            result.extend(tier.suppliers)
        return result

    def get_supplier(self, supplier_id: str) -> Optional[TierSupplier]:
        for tier in self.tiers.values():
            for s in tier.suppliers:
                if s.id == supplier_id:
                    return s
        return None

    def get_lane(self, lane_id: str) -> Optional[Lane]:
        for lane in self.lanes:
            if lane.id == lane_id:
                return lane
        return None

    def propagate_disruption_down(self, supplier_id: str, step: int):
        """
        When a supplier is disrupted, propagate to dependents in lower tiers.
        Tier 3 disruption → affects Tier 2 → affects Tier 1.
        """
        affected = []
        for tier in self.tiers.values():
            for s in tier.suppliers:
                if supplier_id in s.depends_on and not s.is_disrupted:
                    # Stochastic delay before propagation
                    if self.rng.random() < 0.7:  # 70% chance it propagates
                        s.is_disrupted = True
                        s.disruption_id = f"CASCADE_{supplier_id}_{s.id}"
                        affected.append(s)
        return affected

    def compute_bullwhip(self, demand_change_pct: float, tier_level: int) -> float:
        """
        Compute demand amplification at a given tier.
        5% retail change → 15% at Tier 2 → 40% at Tier 3.
        """
        gain = self.BULLWHIP_GAINS.get(tier_level, 1.0)
        return demand_change_pct * gain

    def update_congestion(self, step: int):
        """Update lane congestion scores based on step and randomness."""
        for lane in self.lanes:
            if not lane.is_available:
                lane.congestion_score = 1.0
                continue
            # Seasonal pattern + noise
            seasonal = 0.3 * math.sin(step * 0.2 + hash(lane.id) % 10)
            noise = self.rng.gauss(0, 0.1)
            lane.congestion_score = max(0.0, min(1.0, 0.3 + seasonal + noise))

    def to_observation_dict(self, step: int = 0) -> dict:
        """Convert network state to observation-friendly dict."""
        tiers_dict = {}
        for level, tier in self.tiers.items():
            tiers_dict[f"tier{level}"] = {
                "name": tier.name,
                "bullwhip_gain": tier.bullwhip_gain,
                "suppliers": [
                    {
                        "id": s.id, "name": s.name, "region": s.region,
                        "location": s.location, "capacity_available": s.capacity_available,
                        "lead_time_days": s.lead_time_days,
                        "cost_multiplier": s.cost_multiplier,
                        "reliability": s.reliability if s.reliability_known else None,
                        "reliability_known": s.reliability_known,
                        "is_disrupted": s.is_disrupted,
                        "depends_on": s.depends_on,
                    }
                    for s in tier.suppliers
                ],
            }

        lanes_list = [
            {
                "id": l.id, "origin": l.origin, "destination": l.destination,
                "mode": l.mode, "transit_days": l.effective_transit_days,
                "base_cost": l.base_cost_per_unit,
                "congestion": round(l.congestion_score, 2),
                "available": l.is_available,
                "itar_restricted": l.itar_restricted,
            }
            for l in self.lanes
        ]

        carriers_list = [
            {
                "id": c.id, "name": c.name,
                "lanes": {
                    lid: {"reliability": round(c.get_reliability(lid, step), 3),
                          "cost": c.get_cost(lid)}
                    for lid in c.lane_reliability
                },
            }
            for c in self.carriers
        ]

        return {
            "supply_tiers": tiers_dict,
            "shipping_lanes": lanes_list,
            "carrier_options": carriers_list,
        }
