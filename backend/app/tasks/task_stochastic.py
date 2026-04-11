# backend/app/tasks/task_stochastic.py
"""
Task 3: Stochastic Dynamic Risk
Difficulty: Hard | Max Steps: 25

Stochastic disruption injection + FX volatility + freight surges.
The environment is NON-DETERMINISTIC each episode (but seeded).
Agent must handle evolving FX rates and rising insurance premiums.
"""

from typing import Optional
from .base import BaseTask
from ..models import (
    Observation, Disruption, Order, Supplier, Budget, Metrics,
    OrderStatus, RewardBreakdown
)
from ..simulation.world_state import WorldState


class TaskStochastic(BaseTask):
    task_id = "task_stochastic"
    task_name = "Stochastic Dynamic Risk"
    task_difficulty = "hard"
    task_description = (
        "Real-time market dynamics: FX rates fluctuate, freight costs surge, "
        "insurance premiums rise after claims, and stochastic disruptions fire "
        "from historical distributions. Agent must optimize across cost, "
        "service level, and timing under genuine uncertainty."
    )
    max_steps = 25

    def reset(self, seed: Optional[int] = None) -> Observation:
        import random

        self.current_step = 0
        self.done = False
        self.episode_id = f"stochastic_{seed or 42}"
        self.action_history = []
        self.acted_order_ids = set()
        self.acted_disruption_ids = set()
        self.investigated_ids = set()
        self.hidden_supplier_ids = {"S005", "S008"}
        self.metrics = Metrics()

        # Full world sim with medium difficulty
        self.world = WorldState(seed=seed or 42, difficulty=0.8)

        # Initial disruptions (more will be injected stochastically)
        self.disruptions = [
            Disruption(
                id="D001", type="port_closure", severity="high",
                affected_supplier_id="S001",
                affected_supplier_name="Shanghai Port Operations",
                estimated_duration_days=10,
                description="Port congestion at Shanghai. Vessel queues "
                            "extending to 5+ days. Emergency surcharges active.",
            ),
            Disruption(
                id="D002", type="cyber_attack", severity="critical",
                affected_supplier_id="S003",
                affected_supplier_name="TSMC Wafer Division",
                estimated_duration_days=7,
                description="Ransomware attack on TSMC logistics systems. "
                            "Wafer shipments halted pending security audit.",
            ),
        ]

        # 8 orders with varied urgency
        self.orders = [
            Order(id="O001", product="A-Series Chip Wafer",
                  quantity=15000, value_usd=750000, deadline_days=5,
                  status=OrderStatus.AT_RISK, current_supplier_id="S003",
                  priority="critical", region="asia"),
            Order(id="O002", product="OLED Display Panel",
                  quantity=10000, value_usd=400000, deadline_days=8,
                  status=OrderStatus.AT_RISK, current_supplier_id="S001",
                  priority="high", region="asia"),
            Order(id="O003", product="Camera Sensor Module",
                  quantity=8000, value_usd=320000, deadline_days=10,
                  status=OrderStatus.AT_RISK, current_supplier_id="S001",
                  priority="high", region="americas"),
            Order(id="O004", product="Battery Cell Pack",
                  quantity=12000, value_usd=240000, deadline_days=12,
                  status=OrderStatus.AT_RISK, current_supplier_id="S002",
                  priority="medium", region="europe"),
            Order(id="O005", product="Titanium Frame",
                  quantity=6000, value_usd=180000, deadline_days=7,
                  status=OrderStatus.AT_RISK, current_supplier_id="S001",
                  priority="high", region="americas"),
            Order(id="O006", product="Haptic Engine",
                  quantity=20000, value_usd=100000, deadline_days=15,
                  status=OrderStatus.AT_RISK, current_supplier_id="S002",
                  priority="medium", region="asia"),
            Order(id="O007", product="Ceramic Shield Glass",
                  quantity=25000, value_usd=125000, deadline_days=18,
                  status=OrderStatus.AT_RISK, current_supplier_id="S002",
                  priority="low", region="europe"),
            Order(id="O008", product="USB-C Connector",
                  quantity=50000, value_usd=50000, deadline_days=21,
                  status=OrderStatus.AT_RISK, current_supplier_id="S001",
                  priority="low", region="americas"),
        ]

        # 8 suppliers including hidden reliability
        self.available_suppliers = [
            Supplier(id="S004", name="Samsung Display",
                     location="Asan, South Korea", lead_time_days=6,
                     cost_multiplier=1.15, reliability_score=0.93,
                     capacity_available=15000, region="asia"),
            Supplier(id="S005", name="BOE Technology",  # Unknown reliability
                     location="Beijing, China", lead_time_days=4,
                     cost_multiplier=0.85, reliability_score=0.65,
                     capacity_available=20000, region="asia"),
            Supplier(id="S006", name="Infineon Munich",
                     location="Munich, Germany", lead_time_days=10,
                     cost_multiplier=1.20, reliability_score=0.90,
                     capacity_available=10000, region="europe"),
            Supplier(id="S007", name="Texas Instruments",
                     location="Dallas, USA", lead_time_days=5,
                     cost_multiplier=1.30, reliability_score=0.95,
                     capacity_available=8000, region="americas"),
            Supplier(id="S008", name="Shantou Electronics",  # Unknown (trap?)
                     location="Shantou, China", lead_time_days=3,
                     cost_multiplier=0.70, reliability_score=0.40,
                     capacity_available=30000, region="asia"),
            Supplier(id="S009", name="Flex Guadalajara",
                     location="Guadalajara, Mexico", lead_time_days=4,
                     cost_multiplier=1.25, reliability_score=0.92,
                     capacity_available=7000, region="americas"),
            Supplier(id="S010", name="Corning Glass",
                     location="Kentucky, USA", lead_time_days=8,
                     cost_multiplier=1.10, reliability_score=0.96,
                     capacity_available=12000, region="americas"),
            Supplier(id="S011", name="GlobalExpress Premium",
                     location="Singapore", lead_time_days=2,
                     cost_multiplier=1.60, reliability_score=0.97,
                     capacity_available=5000, region="asia"),
        ]

        self.budget = Budget(total=400000, spent=0, remaining=400000, currency="USD")

        # Set launch countdown (urgent!)
        self.world.launch_countdown = 12

        return self._build_rich_observation()

    def _build_rich_observation(self) -> Observation:
        """Build observation with full v2 market and risk data."""
        world_obs = self.world.to_full_observation()
        obs = self.get_observation()

        # Inject ALL v2 fields
        obs.supply_tiers = world_obs.get("supply_tiers")
        obs.shipping_lanes = world_obs.get("shipping_lanes")
        obs.carrier_options = world_obs.get("carrier_options")
        obs.fx_rates = world_obs.get("fx_rates")
        obs.fx_hedge_coverage = world_obs.get("fx_hedge_coverage")
        obs.spot_freight_rates = world_obs.get("spot_freight_rates")
        obs.fuel_surcharge = world_obs.get("fuel_surcharge")
        obs.insurance_premiums = world_obs.get("insurance_premiums")
        obs.weather_severity = world_obs.get("weather_severity")
        obs.geopolitical_tension = world_obs.get("geopolitical_tension")
        obs.bullwhip_state = world_obs.get("bullwhip_state")
        obs.demand_forecast = world_obs.get("demand_forecast")
        obs.launch_countdown = world_obs.get("launch_countdown", -1)
        obs.dc_inventory = world_obs.get("dc_inventory")
        obs.in_transit_shipments = world_obs.get("in_transit_shipments")
        obs.legal_constraints = world_obs.get("legal_constraints")
        obs.sla_status = world_obs.get("sla_status")
        obs.capacity_utilization = world_obs.get("capacity_utilization")

        return obs

    def step(self, action):
        """Override step to advance world state + inject dynamic disruptions."""
        # Advance world (may inject new disruptions!)
        new_events = self.world.advance_step()

        # Convert new risk engine events into Disruption model objects
        for event in new_events:
            d = Disruption(
                id=event.id,
                type=event.event_type,
                severity=event.severity,
                affected_supplier_id=event.affected_suppliers[0] if event.affected_suppliers else "UNKNOWN",
                affected_supplier_name=f"Affected by {event.event_type}",
                estimated_duration_days=event.duration_days,
                description=event.description,
            )
            self.disruptions.append(d)

        # Decrement launch countdown
        if self.world.launch_countdown > 0:
            self.world.launch_countdown -= 1

        # Delegate to parent step logic
        obs, reward, done, info = super().step(action)

        # Enrich observation
        if not done:
            obs = self._build_rich_observation()
            obs.step = self.current_step
            obs.done = self.done

        return obs, reward, done, info

    def get_final_score(self) -> float:
        total_value = sum(o.value_usd for o in self.orders)
        saved = sum(o.value_usd for o in self.orders if o.status == OrderStatus.FULFILLED)
        delayed = sum(o.value_usd for o in self.orders if o.status == OrderStatus.DELAYED)
        lost = sum(o.value_usd for o in self.orders if o.status == OrderStatus.LOST)

        # Multi-objective scoring
        # 1. Cost minimization (30%)
        budget_efficiency = max(0, 1.0 - self.budget.spent / self.budget.total)
        cost_score = budget_efficiency

        # 2. Service level (30%)
        on_time_rate = saved / total_value if total_value > 0 else 0
        service_score = on_time_rate

        # 3. Launch precision (25%)
        # If launch countdown ran out, penalize any unfulfilled orders
        launch_score = 1.0 if self.world.launch_countdown <= 0 and lost == 0 else 0.5

        # 4. ESG (15%)  — simple: ratio of sea vs air shipments
        esg_score = 0.5  # Baseline

        score = (0.30 * cost_score +
                 0.30 * service_score +
                 0.25 * launch_score +
                 0.15 * esg_score)
        return max(0.01, min(0.99, score))
