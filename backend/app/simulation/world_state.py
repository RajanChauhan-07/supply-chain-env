# backend/app/simulation/world_state.py
"""
Master world state — the single source of truth for the simulation.

Combines:
- Supply network (multi-tier suppliers, lanes, carriers)
- Market dynamics (FX, freight, insurance)
- Risk engine (stochastic disruption injection)
- Constraint engine (ITAR, SLA, capacity, budget)
- Inventory state (6 global DCs)
- Demand signals (forecasts, launch proximity)
"""

import random
from dataclasses import dataclass, field
from typing import Optional

from .supply_network import SupplyNetwork
from .market_dynamics import MarketDynamics
from .risk_engine import RiskEngine, DisruptionEvent
from .constraints import ConstraintEngine


@dataclass
class Shipment:
    """An in-transit shipment."""
    id: str
    order_id: str
    supplier_id: str
    lane_id: str
    carrier_id: str
    units: int
    value_usd: float
    departed_step: int
    eta_steps: int               # Steps until arrival
    insured: bool = False
    status: str = "in_transit"   # in_transit, delivered, failed


@dataclass
class DCInventory:
    """Inventory at a distribution center."""
    dc_id: str
    dc_name: str
    region: str
    sku_stock: dict = field(default_factory=dict)  # sku_id → units
    target_weeks_cover: float = 4.0  # Safety stock target


@dataclass
class DemandForecast:
    """Demand forecast for a region."""
    region: str
    forecast_30d: float = 0.0
    forecast_60d: float = 0.0
    forecast_90d: float = 0.0
    uncertainty_pct: float = 10.0  # ±% uncertainty


class WorldState:
    """
    The master state of the supply chain simulation.
    Updated every step. Provides the observation to the agent.
    """

    def __init__(self, seed: int = 42, difficulty: float = 1.0):
        self.seed = seed
        self.rng = random.Random(seed)
        self.difficulty = difficulty
        self.step_count = 0

        # ── Core simulation components ──
        self.network = SupplyNetwork(seed=seed)
        self.market = MarketDynamics(seed=seed + 1)
        self.risk = RiskEngine(seed=seed + 2, difficulty=difficulty)
        self.constraints = ConstraintEngine()

        # ── Inventory at 6 global DCs ──
        self.dc_inventory: dict[str, DCInventory] = {
            "DC_LAX": DCInventory(dc_id="DC_LAX", dc_name="Los Angeles DC",
                                  region="americas",
                                  sku_stock={"iPhone": 25000, "MacBook": 8000, "iPad": 12000}),
            "DC_AMS": DCInventory(dc_id="DC_AMS", dc_name="Amsterdam DC",
                                  region="europe",
                                  sku_stock={"iPhone": 18000, "MacBook": 6000, "iPad": 9000}),
            "DC_SH": DCInventory(dc_id="DC_SH", dc_name="Shanghai DC",
                                 region="asia",
                                 sku_stock={"iPhone": 30000, "MacBook": 10000, "iPad": 15000}),
            "DC_SIN": DCInventory(dc_id="DC_SIN", dc_name="Singapore DC",
                                  region="asia",
                                  sku_stock={"iPhone": 12000, "MacBook": 4000, "iPad": 6000}),
            "DC_FRA": DCInventory(dc_id="DC_FRA", dc_name="Frankfurt DC",
                                  region="europe",
                                  sku_stock={"iPhone": 15000, "MacBook": 5000, "iPad": 8000}),
            "DC_CHI": DCInventory(dc_id="DC_CHI", dc_name="Chicago DC",
                                  region="americas",
                                  sku_stock={"iPhone": 20000, "MacBook": 7000, "iPad": 10000}),
        }

        # ── In-transit shipments ──
        self.in_transit: list[Shipment] = []
        self.shipment_counter = 0

        # ── Demand signals ──
        self.demand_forecasts: dict[str, DemandForecast] = {
            "americas": DemandForecast(region="americas",
                                       forecast_30d=45000, forecast_60d=42000,
                                       forecast_90d=40000, uncertainty_pct=12),
            "europe": DemandForecast(region="europe",
                                     forecast_30d=33000, forecast_60d=35000,
                                     forecast_90d=32000, uncertainty_pct=15),
            "asia": DemandForecast(region="asia",
                                   forecast_30d=55000, forecast_60d=50000,
                                   forecast_90d=48000, uncertainty_pct=10),
        }
        self.launch_countdown: int = -1  # -1 = no launch, >0 = days until launch

        # ── Bullwhip tracking ──
        self.bullwhip_state: dict[int, float] = {1: 0.0, 2: 0.0, 3: 0.0}

        # ── Scoring accumulators ──
        self.total_freight_cost: float = 0.0
        self.total_hedging_cost: float = 0.0
        self.total_insurance_cost: float = 0.0
        self.total_duty_cost: float = 0.0
        self.orders_delivered_on_time: int = 0
        self.orders_delivered_late: int = 0
        self.orders_lost: int = 0
        self.stockouts: int = 0
        self.sla_breaches: int = 0
        self.itar_violations_blocked: int = 0
        self.carbon_units_sea: float = 0.0
        self.carbon_units_air: float = 0.0
        self.launch_shipments_on_time: int = 0
        self.launch_shipments_late: int = 0
        self.total_insurance_payouts: float = 0.0

    def advance_step(self) -> list[DisruptionEvent]:
        """
        Advance the world by one step. Returns new disruption events.
        
        This is called at the START of each step, before the agent acts.
        """
        self.step_count += 1

        # Reset per-step counters
        self.constraints.reset_step_counters()

        # Evolve market dynamics (FX, freight, insurance, hedge P&L)
        self.market.step()

        # Credit resolved insurance payouts back to budget
        payouts = self.market.get_resolved_payouts()
        if payouts > 0:
            self.constraints.budget_spent = max(0, self.constraints.budget_spent - payouts)
            self.total_insurance_payouts += payouts

        # Update lane congestion
        self.network.update_congestion(self.step_count)

        # Inject stochastic disruptions
        new_events = self.risk.step(self.step_count, self.network)

        # Apply disruption effects to the supply network
        for event in new_events:
            for sup_id in event.affected_suppliers:
                sup = self.network.get_supplier(sup_id)
                if sup:
                    sup.is_disrupted = True
                    sup.disruption_id = event.id
                    # Cascade to dependents
                    self.network.propagate_disruption_down(sup_id, self.step_count)

            for lane_id in event.affected_lanes:
                lane = self.network.get_lane(lane_id)
                if lane:
                    if event.severity_score > 0.8:
                        lane.is_available = False
                    lane.congestion_score = min(1.0,
                        lane.congestion_score + event.severity_score * 0.3)
                    # Surge freight rates
                    self.market.apply_disruption_freight_surge(
                        lane_id, event.severity_score)

        # Advance in-transit shipments
        self._advance_shipments()

        # Update bullwhip state
        self._update_bullwhip()

        # Update demand forecasts (small random walk)
        self._evolve_demand()

        return new_events

    def _advance_shipments(self):
        """Move in-transit shipments forward. Deliver those that arrive."""
        still_transit = []
        for shipment in self.in_transit:
            elapsed = self.step_count - shipment.departed_step
            if elapsed >= shipment.eta_steps:
                shipment.status = "delivered"
                # Determine which DC receives it
                lane = self.network.get_lane(shipment.lane_id)
                if lane:
                    dc = self._find_dc_for_destination(lane.destination)
                    if dc:
                        for sku in dc.sku_stock:
                            dc.sku_stock[sku] = dc.sku_stock.get(sku, 0) + \
                                                shipment.units // len(dc.sku_stock)
                self.orders_delivered_on_time += 1
            else:
                # Check if lane is disrupted mid-transit
                lane = self.network.get_lane(shipment.lane_id)
                if lane and not lane.is_available:
                    shipment.eta_steps += 2  # Delay by 2 steps
                    if shipment.insured:
                        self.market.file_insurance_claim(
                            shipment.lane_id, shipment.value_usd * 0.1)
                still_transit.append(shipment)
        self.in_transit = still_transit

    def _find_dc_for_destination(self, destination: str) -> Optional[DCInventory]:
        """Map a lane destination to the nearest DC."""
        dest_dc_map = {
            "los_angeles": "DC_LAX",
            "amsterdam": "DC_AMS",
            "shanghai": "DC_SH",
            "tel_aviv": "DC_SIN",  # Closest
        }
        dc_id = dest_dc_map.get(destination)
        return self.dc_inventory.get(dc_id) if dc_id else None

    def _update_bullwhip(self):
        """
        Update bullwhip amplification state.
        Small demand perturbation at retail amplifies up the tiers.
        """
        # Simulate a small demand change from retail
        retail_change = self.rng.gauss(0, 0.03)  # ±3% noise
        for tier_level, tier in self.network.tiers.items():
            amplified = self.network.compute_bullwhip(retail_change, tier_level)
            self.bullwhip_state[tier_level] = round(amplified * 100, 1)  # as %

    def _evolve_demand(self):
        """Small random walk on demand forecasts."""
        for forecast in self.demand_forecasts.values():
            pct = forecast.uncertainty_pct / 100
            noise = self.rng.gauss(0, pct * 0.1)
            forecast.forecast_30d *= (1 + noise)
            forecast.forecast_60d *= (1 + noise * 0.7)
            forecast.forecast_90d *= (1 + noise * 0.5)

    def create_shipment(self, order_id: str, supplier_id: str,
                        lane_id: str, carrier_id: str,
                        units: int, value_usd: float,
                        insured: bool = False) -> Optional[Shipment]:
        """Create a new shipment. Returns None if blocked by constraints."""
        lane = self.network.get_lane(lane_id)
        supplier = self.network.get_supplier(supplier_id)
        if not lane or not supplier:
            return None

        # Check ITAR
        allowed, reason = self.constraints.check_itar(
            lane.origin, lane.destination)
        if not allowed:
            self.itar_violations_blocked += 1
            return None

        # Check capacity
        # (simplified: check throughput at destination port)
        facility_id = f"PORT_{lane.destination[:3].upper()}"
        cap_ok, cap_reason = self.constraints.check_capacity(facility_id, units)
        if not cap_ok:
            return None

        # Calculate costs
        carrier = next((c for c in self.network.carriers if c.id == carrier_id), None)
        freight_cost = lane.base_cost_per_unit * units
        if carrier:
            freight_cost *= carrier.get_cost(lane_id)
        freight_cost *= self.market.fuel_surcharge_index

        # Add spot freight adjustment
        spot_rate = self.market.spot_freight.get(lane_id, lane.base_cost_per_unit)
        freight_cost = spot_rate * units / 1000  # Normalize

        insurance_cost = 0.0
        if insured and lane_id in self.market.insurance:
            insurance_cost = self.market.insurance[lane_id].get_premium(value_usd)

        # Check budget
        total_cost = freight_cost + insurance_cost
        budget_ok, budget_reason = self.constraints.check_budget(total_cost)
        if not budget_ok:
            return None

        # Record costs
        self.constraints.record_spend(total_cost)
        self.constraints.record_throughput(facility_id, units)
        self.total_freight_cost += freight_cost
        self.total_insurance_cost += insurance_cost

        # Carbon tracking
        if lane.mode == "air":
            self.carbon_units_air += units
        else:
            self.carbon_units_sea += units

        # Create shipment
        self.shipment_counter += 1
        eta = lane.effective_transit_days
        if carrier:
            # Reliability affects ETA variance
            reliability = carrier.get_reliability(lane_id, self.step_count)
            if self.rng.random() > reliability:
                eta += self.rng.randint(1, 3)  # Late

        # Record carrier usage for reliability degradation
        if carrier:
            carrier.record_usage(lane_id)

        shipment = Shipment(
            id=f"SHIP_{self.shipment_counter:04d}",
            order_id=order_id,
            supplier_id=supplier_id,
            lane_id=lane_id,
            carrier_id=carrier_id,
            units=units,
            value_usd=value_usd,
            departed_step=self.step_count,
            eta_steps=eta,
            insured=insured,
        )
        self.in_transit.append(shipment)
        return shipment

    def to_full_observation(self) -> dict:
        """
        Build the complete observation dict for the agent.
        This is the observation the agent sees every step.
        """
        network_obs = self.network.to_observation_dict(self.step_count)
        market_obs = self.market.to_observation_dict()
        risk_obs = self.risk.get_risk_context()
        disruption_obs = self.risk.to_observation_list()

        return {
            # Supply network
            **network_obs,

            # Market dynamics
            **market_obs,

            # Risk context
            "weather_severity": risk_obs.get("weather_severity", {}),
            "geopolitical_tension": risk_obs.get("geopolitical_tension", {}),
            "bullwhip_state": {
                f"tier{k}": f"{v:+.1f}%" for k, v in self.bullwhip_state.items()
            },

            # Disruptions
            "disruptions": disruption_obs,

            # Demand signals
            "demand_forecast": {
                region: {
                    "30d": round(f.forecast_30d),
                    "60d": round(f.forecast_60d),
                    "90d": round(f.forecast_90d),
                    "uncertainty_pct": f.uncertainty_pct,
                }
                for region, f in self.demand_forecasts.items()
            },
            "launch_countdown": self.launch_countdown,

            # Inventory
            "dc_inventory": {
                dc_id: {
                    "name": dc.dc_name,
                    "region": dc.region,
                    "stock": dict(dc.sku_stock),
                    "weeks_cover": dc.target_weeks_cover,
                }
                for dc_id, dc in self.dc_inventory.items()
            },

            # In-transit
            "in_transit_shipments": [
                {
                    "id": s.id,
                    "order_id": s.order_id,
                    "lane": s.lane_id,
                    "carrier": s.carrier_id,
                    "units": s.units,
                    "eta_steps": s.eta_steps - (self.step_count - s.departed_step),
                    "insured": s.insured,
                }
                for s in self.in_transit
            ],

            # Constraints
            "legal_constraints": self.constraints.get_legal_constraints_list(),
            "sla_status": self.constraints.get_sla_status(),
            "capacity_utilization": self.constraints.get_capacity_utilization(),
            "budget_remaining": round(
                self.constraints.budget_envelope - self.constraints.budget_spent, 2),

            # Insurance payouts credited
            "insurance_payouts_credited": round(self.total_insurance_payouts, 2),
        }
