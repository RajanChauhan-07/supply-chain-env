# backend/app/tasks/task_full_sim.py
"""
Task 5: Full Apple-Scale Simulation
Difficulty: Expert | Max Steps: 30

EVERYTHING combined:
- Multi-tier supply network with cascading disruptions
- Stochastic risk injection from historical distributions
- FX volatility with hedging decisions
- Lane-specific carrier reliability (time-variant)
- Insurance feedback loops
- ITAR/EAR hard legal constraints (action masks)
- Bullwhip demand amplification
- Product launch pressure
- 6 global DCs with inventory rebalancing
- Multi-objective scoring: cost, service, launch, ESG

This is the definitive test of supply chain reasoning.
"""

from typing import Optional
from .base import BaseTask
from ..models import (
    Observation, Disruption, Order, Supplier, Budget, Metrics,
    OrderStatus, RewardBreakdown, Reward, Action
)
from ..simulation.world_state import WorldState


class TaskFullSim(BaseTask):
    task_id = "task_full_sim"
    task_name = "Apple-Scale Full Simulation"
    task_difficulty = "expert"
    task_description = (
        "EVERYTHING combined: multi-tier suppliers with bullwhip effect, "
        "stochastic disruptions, FX hedging, lane-specific carriers, "
        "insurance feedback, ITAR constraints, product launch pressure, "
        "and full inventory management across 6 global DCs. "
        "Multi-objective: minimize cost, maximize service, nail the launch, "
        "reduce carbon footprint."
    )
    max_steps = 30

    def reset(self, seed: Optional[int] = None) -> Observation:
        import random

        self.current_step = 0
        self.done = False
        self.episode_id = f"full_sim_{seed or 42}"
        self.action_history = []
        self.acted_order_ids = set()
        self.acted_disruption_ids = set()
        self.investigated_ids = set()
        self.hidden_supplier_ids = {"S005", "S008", "S010", "S012"}
        self.metrics = Metrics()

        # Tracking for advanced mechanics
        self.trap_supplier_ids = {"S008", "S012"}
        self.trap_failures = []
        self.pending_trap_failures = {}
        self.hedging_actions = 0
        self.rebalance_actions = 0
        self.itar_blocks = 0
        self.insurance_claims = 0
        self.carbon_air = 0
        self.carbon_sea = 0
        self.region_reroute_count = {"asia": 0, "europe": 0, "americas": 0}

        # FULL world simulation with high difficulty
        self.world = WorldState(seed=seed or 42, difficulty=1.0)
        self.world.launch_countdown = 15  # Product launch in 15 steps!

        # Major multi-disruption scenario
        self.disruptions = [
            Disruption(
                id="D001", type="port_closure", severity="critical",
                affected_supplier_id="S001",
                affected_supplier_name="Shanghai Port Complex",
                estimated_duration_days=14,
                description="Typhoon-category storm closes Shanghai port. "
                            "All sea freight from east China halted. "
                            "Air freight surcharges at 3x normal.",
            ),
            Disruption(
                id="D002", type="cyber_attack", severity="high",
                affected_supplier_id="S002",
                affected_supplier_name="TSMC Global Logistics",
                estimated_duration_days=10,
                description="Sophisticated cyber attack on TSMC logistics network. "
                            "Wafer shipment tracking systems compromised. "
                            "Manual verification required.",
            ),
            Disruption(
                id="D003", type="geopolitical", severity="high",
                affected_supplier_id="S003",
                affected_supplier_name="Rare Earth Processing Co.",
                estimated_duration_days=60,
                description="New export controls on rare earth processing. "
                            "Tier 3 supply chain under compliance review. "
                            "ITAR implications for downstream components.",
            ),
            Disruption(
                id="D004", type="quality", severity="medium",
                affected_supplier_id="S004",
                affected_supplier_name="BatteryTech Korea",
                estimated_duration_days=21,
                description="Battery cell quality recall. All units from "
                            "batch 2024-Q4 must be reinspected.",
            ),
        ]

        # 10 orders across all priorities and regions
        self.orders = [
            Order(id="O001", product="A18 Pro Chip Wafer",
                  quantity=20000, value_usd=1200000, deadline_days=6,
                  status=OrderStatus.AT_RISK, current_supplier_id="S002",
                  priority="critical", region="asia"),
            Order(id="O002", product="LTPO OLED Display",
                  quantity=15000, value_usd=750000, deadline_days=8,
                  status=OrderStatus.AT_RISK, current_supplier_id="S001",
                  priority="critical", region="americas"),
            Order(id="O003", product="Titanium Frame Grade 5",
                  quantity=10000, value_usd=500000, deadline_days=10,
                  status=OrderStatus.AT_RISK, current_supplier_id="S001",
                  priority="high", region="europe"),
            Order(id="O004", product="Battery Cell 4680",
                  quantity=25000, value_usd=400000, deadline_days=12,
                  status=OrderStatus.AT_RISK, current_supplier_id="S004",
                  priority="high", region="asia"),
            Order(id="O005", product="Camera ISP Module",
                  quantity=12000, value_usd=360000, deadline_days=10,
                  status=OrderStatus.AT_RISK, current_supplier_id="S002",
                  priority="high", region="americas"),
            Order(id="O006", product="Ceramic Shield Glass",
                  quantity=18000, value_usd=270000, deadline_days=14,
                  status=OrderStatus.AT_RISK, current_supplier_id="S001",
                  priority="medium", region="europe"),
            Order(id="O007", product="Haptic Taptic Engine",
                  quantity=30000, value_usd=180000, deadline_days=16,
                  status=OrderStatus.AT_RISK, current_supplier_id="S004",
                  priority="medium", region="asia"),
            Order(id="O008", product="5G Modem Chip",
                  quantity=20000, value_usd=240000, deadline_days=9,
                  status=OrderStatus.AT_RISK, current_supplier_id="S002",
                  priority="high", region="americas"),
            Order(id="O009", product="USB-C MagSafe Assembly",
                  quantity=40000, value_usd=120000, deadline_days=20,
                  status=OrderStatus.AT_RISK, current_supplier_id="S003",
                  priority="low", region="europe"),
            Order(id="O010", product="Speaker Acoustic Module",
                  quantity=35000, value_usd=105000, deadline_days=21,
                  status=OrderStatus.AT_RISK, current_supplier_id="S003",
                  priority="low", region="asia"),
        ]

        # 12 suppliers: mix of reliable, hidden, and traps across tiers
        self.available_suppliers = [
            # Tier 1 — Assembly
            Supplier(id="S005", name="Pegatron Premium (T1)",
                     location="Shanghai, China", lead_time_days=4,
                     cost_multiplier=1.20, reliability_score=0.91,
                     capacity_available=15000, region="asia"),
            Supplier(id="S006", name="Flex Americas (T1)",
                     location="Guadalajara, Mexico", lead_time_days=3,
                     cost_multiplier=1.25, reliability_score=0.93,
                     capacity_available=10000, region="americas"),
            Supplier(id="S007", name="Jabil Europe (T1)",
                     location="Budapest, Hungary", lead_time_days=6,
                     cost_multiplier=1.15, reliability_score=0.89,
                     capacity_available=8000, region="europe"),
            # TRAP 1: Suspiciously cheap
            Supplier(id="S008", name="FastValue Electronics",
                     location="Shantou, China", lead_time_days=2,
                     cost_multiplier=0.65, reliability_score=0.28,
                     capacity_available=30000, region="asia"),
            # Tier 2 — Components
            Supplier(id="S009", name="Samsung Display (T2)",
                     location="Asan, South Korea", lead_time_days=7,
                     cost_multiplier=1.18, reliability_score=0.94,
                     capacity_available=20000, region="asia"),
            Supplier(id="S010", name="Corning Glass (T2)",
                     location="Kentucky, USA", lead_time_days=9,
                     cost_multiplier=1.10, reliability_score=0.96,
                     capacity_available=15000, region="americas"),
            Supplier(id="S011", name="Infineon Sensors (T2)",
                     location="Munich, Germany", lead_time_days=8,
                     cost_multiplier=1.22, reliability_score=0.90,
                     capacity_available=10000, region="europe"),
            # TRAP 2: Bait supplier
            Supplier(id="S012", name="BudgetParts Direct",
                     location="Dhaka, Bangladesh", lead_time_days=3,
                     cost_multiplier=0.55, reliability_score=0.20,
                     capacity_available=40000, region="asia"),
            # Tier 3 — Raw Materials
            Supplier(id="S013", name="MP Materials (T3)",
                     location="Mountain Pass, USA", lead_time_days=21,
                     cost_multiplier=1.40, reliability_score=0.85,
                     capacity_available=50000, region="americas"),
            # Premium express
            Supplier(id="S014", name="GlobalExpress VIP",
                     location="Singapore", lead_time_days=2,
                     cost_multiplier=1.65, reliability_score=0.98,
                     capacity_available=5000, region="asia"),
            # Additional options
            Supplier(id="S015", name="Texas Instruments (T2)",
                     location="Dallas, USA", lead_time_days=6,
                     cost_multiplier=1.30, reliability_score=0.95,
                     capacity_available=8000, region="americas"),
            Supplier(id="S016", name="STMicro Europe (T2)",
                     location="Geneva, Switzerland", lead_time_days=7,
                     cost_multiplier=1.28, reliability_score=0.92,
                     capacity_available=7000, region="europe"),
        ]

        self.budget = Budget(total=600000, spent=0, remaining=600000, currency="USD")

        return self._build_rich_observation()

    def _build_rich_observation(self) -> Observation:
        """Build observation with ALL v2 simulation data."""
        world_obs = self.world.to_full_observation()
        obs = self.get_observation()

        # Inject every v2 field
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
        obs.launch_countdown = self.world.launch_countdown
        obs.dc_inventory = world_obs.get("dc_inventory")
        obs.in_transit_shipments = world_obs.get("in_transit_shipments")
        obs.legal_constraints = world_obs.get("legal_constraints")
        obs.sla_status = world_obs.get("sla_status")
        obs.capacity_utilization = world_obs.get("capacity_utilization")

        return obs

    def _handle_reroute(self, action) -> Reward:
        """Override with trap detection + region tracking + cascade check."""
        order = self._get_order(action.order_id)
        supplier = self._get_supplier(action.new_supplier_id)
        breakdown = RewardBreakdown()

        if action.order_id in self.acted_order_ids:
            breakdown.redundant_action_penalty = -0.05
            return self._make_reward(value=-0.05,
                reason=f"Order {action.order_id} already handled.", breakdown=breakdown)

        if supplier.capacity_available < order.quantity:
            breakdown.redundant_action_penalty = -0.05
            return self._make_reward(value=-0.05,
                reason=f"{supplier.name} lacks capacity.", breakdown=breakdown)

        extra_cost = max(0, order.value_usd * (supplier.cost_multiplier - 1.0))
        if self.budget.remaining < extra_cost:
            breakdown.budget_exceeded_penalty = -0.10
            return self._make_reward(value=-0.10,
                reason="Insufficient budget.", breakdown=breakdown)

        # TRAP CHECK
        is_trap = supplier.id in self.trap_supplier_ids
        was_investigated = supplier.id in self.investigated_ids

        if is_trap and not was_investigated:
            order.current_supplier_id = supplier.id
            order.status = OrderStatus.FULFILLED
            supplier.capacity_available -= order.quantity
            self.budget.spent += extra_cost
            self.budget.remaining -= extra_cost
            self.acted_order_ids.add(action.order_id)
            self.pending_trap_failures[action.order_id] = self.current_step + 2
            self.metrics.orders_saved += 1
            self.metrics.revenue_protected += order.value_usd
            breakdown.orders_saved_reward = 0.15

            # Track region
            if supplier.region:
                self.region_reroute_count[supplier.region] = \
                    self.region_reroute_count.get(supplier.region, 0) + 1

            return self._make_reward(value=0.15,
                reason=f"✅ Rerouted {action.order_id} to {supplier.name}.",
                breakdown=breakdown)

        if is_trap and was_investigated:
            breakdown.bad_supplier_penalty = -0.15
            return self._make_reward(value=-0.15,
                reason=f"⛔ {supplier.name} was found UNRELIABLE.", breakdown=breakdown)

        # Normal reroute
        on_time = supplier.lead_time_days <= order.deadline_days
        reliable = supplier.reliability_score and supplier.reliability_score >= 0.75
        order.current_supplier_id = supplier.id
        order.status = OrderStatus.FULFILLED if on_time else OrderStatus.DELAYED
        supplier.capacity_available -= order.quantity
        self.budget.spent += extra_cost
        self.budget.remaining -= extra_cost
        self.acted_order_ids.add(action.order_id)

        # Region tracking for cascade
        if supplier.region:
            self.region_reroute_count[supplier.region] = \
                self.region_reroute_count.get(supplier.region, 0) + 1
            # CASCADE CHECK: 4+ reroutes to same region triggers surge
            if self.region_reroute_count.get(supplier.region, 0) >= 4:
                for s in self.available_suppliers:
                    if s.region == supplier.region and s.id != supplier.id:
                        s.cost_multiplier *= 1.30  # +30% cost
                        s.lead_time_days += 2
                cascade_d = Disruption(
                    id=f"CASCADE_{supplier.region}",
                    type="supply_surge", severity="high",
                    affected_supplier_id=supplier.id,
                    affected_supplier_name=f"Region surge: {supplier.region}",
                    estimated_duration_days=10,
                    description=f"⚠️ CASCADE: Too many reroutes to {supplier.region}! "
                                f"All {supplier.region} suppliers: +30% cost, +2d lead time.",
                )
                self.disruptions.append(cascade_d)

        # Air/sea carbon tracking
        if action.shipping_method == "air":
            self.carbon_air += order.quantity
        else:
            self.carbon_sea += order.quantity

        if on_time:
            breakdown.orders_saved_reward = 0.15
            breakdown.deadline_met_reward = 0.10
            reward_val = 0.25
            self.metrics.orders_saved += 1
            self.metrics.revenue_protected += order.value_usd
            if reliable and supplier.cost_multiplier <= 1.25:
                breakdown.good_supplier_choice_reward = 0.05
                reward_val += 0.05
            reason = f"✅ {action.order_id} → {supplier.name} on time."
        else:
            breakdown.orders_saved_reward = 0.05
            breakdown.missed_deadline_penalty = -0.10
            reward_val = -0.05
            self.metrics.orders_delayed += 1
            reason = f"⚠️ {action.order_id} → {supplier.name} LATE."

        return self._make_reward(value=reward_val, reason=reason, breakdown=breakdown)

    def step(self, action):
        """Full simulation step: world advance + trap check + cascade."""
        new_events = self.world.advance_step()

        # Inject dynamic disruptions
        for event in new_events:
            d = Disruption(
                id=event.id, type=event.event_type, severity=event.severity,
                affected_supplier_id=event.affected_suppliers[0] if event.affected_suppliers else "UNKNOWN",
                affected_supplier_name=f"Affected by {event.event_type}",
                estimated_duration_days=event.duration_days,
                description=event.description,
            )
            self.disruptions.append(d)

        # Trap failure checks
        for order_id, fail_step in list(self.pending_trap_failures.items()):
            if self.current_step + 1 >= fail_step:
                order = self._get_order(order_id)
                if order.status == OrderStatus.FULFILLED:
                    order.status = OrderStatus.AT_RISK
                    self.acted_order_ids.discard(order_id)
                    self.metrics.orders_saved = max(0, self.metrics.orders_saved - 1)
                    self.metrics.revenue_protected -= order.value_usd
                    self.trap_failures.append(order_id)
                    self.world.market.file_insurance_claim("SH_LAX", order.value_usd * 0.2)
                    self.insurance_claims += 1
                    self.disruptions.append(Disruption(
                        id=f"TRAP_{order_id}", type="supplier_failure", severity="critical",
                        affected_supplier_id=order.current_supplier_id,
                        affected_supplier_name=f"TRAP FAILED: {order.current_supplier_id}",
                        estimated_duration_days=999,
                        description=f"⛔ TRAP SUPPLIER FAILED for {order_id}!",
                    ))
                del self.pending_trap_failures[order_id]

        # Launch countdown
        if self.world.launch_countdown > 0:
            self.world.launch_countdown -= 1

        obs, reward, done, info = super().step(action)
        if not done:
            obs = self._build_rich_observation()
            obs.step = self.current_step
            obs.done = self.done
        return obs, reward, done, info

    def get_final_score(self) -> float:
        """Multi-objective scoring: cost + service + launch + ESG."""
        total_value = sum(o.value_usd for o in self.orders)
        saved = sum(o.value_usd for o in self.orders if o.status == OrderStatus.FULFILLED)
        delayed = sum(o.value_usd for o in self.orders if o.status == OrderStatus.DELAYED)

        # 1. Cost (30%): budget efficiency + no unnecessary spending
        budget_eff = max(0, 1.0 - self.budget.spent / self.budget.total)
        cost_score = budget_eff

        # 2. Service (30%): revenue protected + on-time rate
        revenue_pct = (saved + delayed * 0.3) / total_value if total_value > 0 else 0
        service_score = revenue_pct

        # 3. Launch (25%): all critical orders fulfilled before launch
        critical_orders = [o for o in self.orders if o.priority in ("critical", "high")]
        critical_fulfilled = sum(1 for o in critical_orders if o.status == OrderStatus.FULFILLED)
        launch_score = critical_fulfilled / max(1, len(critical_orders))

        # 4. ESG (15%): sea-over-air preference
        total_carbon = self.carbon_air + self.carbon_sea
        if total_carbon > 0:
            esg_score = self.carbon_sea / total_carbon  # Higher = more sea = better
        else:
            esg_score = 0.5  # Neutral

        # Bonuses/penalties
        trap_penalty = len(self.trap_failures) * 0.05
        cascade_penalty = sum(1 for r, c in self.region_reroute_count.items() if c >= 4) * 0.05
        investigation_bonus = min(0.1, len(self.investigated_ids) * 0.02)

        raw_score = (0.30 * cost_score +
                     0.30 * service_score +
                     0.25 * launch_score +
                     0.15 * esg_score)
        raw_score = raw_score - trap_penalty - cascade_penalty + investigation_bonus

        return max(0.01, min(0.99, raw_score))
