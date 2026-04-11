# backend/app/simulation/constraints.py
"""
Hard legal and operational constraints as action masks.

These are NOT soft penalties — they REJECT invalid actions outright.
- ITAR/EAR: Certain component+route combos are FORBIDDEN
- SLA Floors: DCs must maintain minimum fill rates
- Capacity Ceilings: Warehouse/port throughput limits
- Budget Envelope: Quarterly freight cap that cannot be exceeded
"""

from dataclasses import dataclass, field


@dataclass
class ITARRestriction:
    """An export control restriction."""
    id: str
    description: str
    restricted_origins: list = field(default_factory=list)
    restricted_destinations: list = field(default_factory=list)
    restricted_component_types: list = field(default_factory=list)
    regulation: str = "ITAR"  # ITAR, EAR, etc.


@dataclass
class SLAFloor:
    """Minimum service level at a distribution center."""
    dc_id: str
    dc_name: str
    min_fill_rate: float     # 0.0-1.0
    max_delay_days: int      # Maximum permissible delay
    current_fill_rate: float = 1.0


@dataclass
class CapacityCeiling:
    """Maximum throughput at a facility."""
    facility_id: str
    facility_name: str
    max_units_per_step: int
    current_units_this_step: int = 0


class ConstraintEngine:
    """
    Evaluates hard constraints on a proposed action.
    Returns (is_allowed, violation_reason) for each action.
    """

    def __init__(self):
        self.itar_restrictions: list[ITARRestriction] = []
        self.sla_floors: list[SLAFloor] = []
        self.capacity_ceilings: list[CapacityCeiling] = []
        self.budget_envelope: float = float("inf")
        self.budget_spent: float = 0.0
        self._build_defaults()

    def _build_defaults(self):
        """Build default constraints for a realistic environment."""
        # ── ITAR/EAR Restrictions ──
        self.itar_restrictions = [
            ITARRestriction(
                id="ITAR_001",
                description="Advanced semiconductors cannot transit through restricted jurisdictions",
                restricted_origins=["hsinchu", "asan"],   # TSMC, Samsung
                restricted_destinations=["tel_aviv", "moscow"],
                restricted_component_types=["semiconductor", "wafer"],
                regulation="EAR",
            ),
            ITARRestriction(
                id="ITAR_002",
                description="Rare earth processing equipment restricted under dual-use controls",
                restricted_origins=["mountain_pass", "drc"],
                restricted_destinations=["moscow", "tehran"],
                restricted_component_types=["rare_earth", "cobalt"],
                regulation="ITAR",
            ),
            ITARRestriction(
                id="ITAR_003",
                description="Precision optics components restricted for certain destinations",
                restricted_origins=["niigata"],
                restricted_destinations=["tehran", "pyongyang"],
                restricted_component_types=["silicon", "optics"],
                regulation="EAR",
            ),
        ]

        # ── SLA Floors ──
        self.sla_floors = [
            SLAFloor(dc_id="DC_LAX", dc_name="Los Angeles DC",
                     min_fill_rate=0.85, max_delay_days=7),
            SLAFloor(dc_id="DC_AMS", dc_name="Amsterdam DC",
                     min_fill_rate=0.80, max_delay_days=10),
            SLAFloor(dc_id="DC_SH", dc_name="Shanghai DC",
                     min_fill_rate=0.90, max_delay_days=5),
            SLAFloor(dc_id="DC_SIN", dc_name="Singapore DC",
                     min_fill_rate=0.80, max_delay_days=8),
            SLAFloor(dc_id="DC_FRA", dc_name="Frankfurt DC",
                     min_fill_rate=0.85, max_delay_days=7),
            SLAFloor(dc_id="DC_CHI", dc_name="Chicago DC",
                     min_fill_rate=0.80, max_delay_days=10),
        ]

        # ── Capacity Ceilings ──
        self.capacity_ceilings = [
            CapacityCeiling(facility_id="PORT_SH", facility_name="Shanghai Port",
                           max_units_per_step=100000),
            CapacityCeiling(facility_id="PORT_LAX", facility_name="LA Port",
                           max_units_per_step=80000),
            CapacityCeiling(facility_id="PORT_AMS", facility_name="Rotterdam/AMS Port",
                           max_units_per_step=60000),
        ]

        # ── Budget Envelope ──
        self.budget_envelope = 5_000_000.0  # $5M quarterly freight cap

    def check_itar(self, origin: str, destination: str,
                   component_type: str = "") -> tuple[bool, str]:
        """
        Check if a route violates ITAR/EAR constraints.
        Returns (allowed, reason).
        """
        for restriction in self.itar_restrictions:
            origin_match = origin in restriction.restricted_origins
            dest_match = destination in restriction.restricted_destinations
            comp_match = (not restriction.restricted_component_types or
                         component_type in restriction.restricted_component_types)
            if origin_match and dest_match and comp_match:
                return False, (
                    f"BLOCKED by {restriction.regulation} ({restriction.id}): "
                    f"{restriction.description}. "
                    f"Route {origin}→{destination} is prohibited for "
                    f"{component_type or 'this component'}."
                )
        return True, ""

    def check_sla_floor(self, dc_id: str, proposed_reduction: float = 0.0) -> tuple[bool, str]:
        """
        Check if an action would drop a DC below its SLA floor.
        """
        for sla in self.sla_floors:
            if sla.dc_id == dc_id:
                new_fill = sla.current_fill_rate - proposed_reduction
                if new_fill < sla.min_fill_rate:
                    return False, (
                        f"SLA VIOLATION: {sla.dc_name} fill rate would drop to "
                        f"{new_fill:.0%}, below floor of {sla.min_fill_rate:.0%}."
                    )
        return True, ""

    def check_capacity(self, facility_id: str, units: int) -> tuple[bool, str]:
        """Check throughput against capacity ceiling."""
        for cap in self.capacity_ceilings:
            if cap.facility_id == facility_id:
                if cap.current_units_this_step + units > cap.max_units_per_step:
                    remaining = cap.max_units_per_step - cap.current_units_this_step
                    return False, (
                        f"CAPACITY EXCEEDED: {cap.facility_name} can handle "
                        f"{remaining:,} more units this step, "
                        f"but {units:,} requested."
                    )
        return True, ""

    def check_budget(self, cost: float) -> tuple[bool, str]:
        """Check if spending would exceed budget envelope."""
        if self.budget_spent + cost > self.budget_envelope:
            remaining = self.budget_envelope - self.budget_spent
            return False, (
                f"BUDGET ENVELOPE EXCEEDED: ${remaining:,.0f} remaining "
                f"but ${cost:,.0f} required."
            )
        return True, ""

    def record_spend(self, cost: float):
        """Record spending against the budget envelope."""
        self.budget_spent += cost

    def record_throughput(self, facility_id: str, units: int):
        """Record throughput at a facility."""
        for cap in self.capacity_ceilings:
            if cap.facility_id == facility_id:
                cap.current_units_this_step += units

    def reset_step_counters(self):
        """Reset per-step counters (call at start of each step)."""
        for cap in self.capacity_ceilings:
            cap.current_units_this_step = 0

    def get_legal_constraints_list(self) -> list[dict]:
        """Return ITAR restrictions for observation."""
        return [
            {
                "id": r.id,
                "regulation": r.regulation,
                "description": r.description,
                "restricted_origins": r.restricted_origins,
                "restricted_destinations": r.restricted_destinations,
            }
            for r in self.itar_restrictions
        ]

    def get_sla_status(self) -> dict:
        """Return SLA fill rates for observation."""
        return {
            sla.dc_id: {
                "name": sla.dc_name,
                "fill_rate": round(sla.current_fill_rate, 2),
                "floor": sla.min_fill_rate,
                "healthy": sla.current_fill_rate >= sla.min_fill_rate,
            }
            for sla in self.sla_floors
        }

    def get_capacity_utilization(self) -> dict:
        """Return capacity utilization for observation."""
        return {
            cap.facility_id: {
                "name": cap.facility_name,
                "used": cap.current_units_this_step,
                "max": cap.max_units_per_step,
                "utilization_pct": round(
                    cap.current_units_this_step / cap.max_units_per_step * 100, 1
                ) if cap.max_units_per_step > 0 else 0,
            }
            for cap in self.capacity_ceilings
        }
