# backend/app/tasks/task_adversarial_v2.py
"""
Task 4: Adversarial — Trap Suppliers + Insurance Exploit Detection
Difficulty: Hard | Max Steps: 20

Trap suppliers that look amazing but fail after reroute.
Insurance feedback loop — premiums rise if agent exploits risky lanes.
Agent must investigate before trusting, and avoid gaming the system.
"""

from typing import Optional
from .base import BaseTask
from ..models import (
    Observation, Disruption, Order, Supplier, Budget, Metrics,
    OrderStatus, RewardBreakdown, Reward
)
from ..simulation.world_state import WorldState


class TaskAdversarialV2(BaseTask):
    task_id = "task_adversarial_v2"
    task_name = "Trap & Verify"
    task_difficulty = "hard"
    task_description = (
        "3 of 8 suppliers are traps — suspiciously cheap but will fail after "
        "reroute. Insurance premiums rise dynamically when the agent routes "
        "through risky lanes. Only investigation reveals the truth."
    )
    max_steps = 20

    def reset(self, seed: Optional[int] = None) -> Observation:
        import random

        self.current_step = 0
        self.done = False
        self.episode_id = f"adversarial_v2_{seed or 42}"
        self.action_history = []
        self.acted_order_ids = set()
        self.acted_disruption_ids = set()
        self.investigated_ids = set()
        self.hidden_supplier_ids = {"S005", "S006", "S007", "S008", "S009"}
        self.metrics = Metrics()

        # Track trap failures
        self.trap_supplier_ids = {"S005", "S007", "S009"}
        self.trap_failures = []
        self.pending_trap_failures = {}  # order_id → step_to_fail

        # World state
        self.world = WorldState(seed=seed or 42, difficulty=0.3)

        self.disruptions = [
            Disruption(
                id="D001", type="bankruptcy", severity="critical",
                affected_supplier_id="S001",
                affected_supplier_name="PrimaryChip Corp",
                estimated_duration_days=90,
                description="PrimaryChip Corp has filed for bankruptcy. "
                            "All orders must be rerouted immediately.",
            ),
            Disruption(
                id="D002", type="quality", severity="high",
                affected_supplier_id="S002",
                affected_supplier_name="QuickAssembly Ltd",
                estimated_duration_days=21,
                description="Quality recall on QuickAssembly products. "
                            "Factory under inspection.",
            ),
            Disruption(
                id="D003", type="embargo", severity="high",
                affected_supplier_id="S003",
                affected_supplier_name="CheapParts International",
                estimated_duration_days=180,
                description="Trade embargo restricts imports from CheapParts. "
                            "Alternative sourcing required.",
            ),
        ]

        # 6 orders that all need rerouting
        self.orders = [
            Order(id="O001", product="Processor Unit A15",
                  quantity=10000, value_usd=800000, deadline_days=8,
                  status=OrderStatus.AT_RISK, current_supplier_id="S001",
                  priority="critical", region="asia"),
            Order(id="O002", product="Memory Module DDR5",
                  quantity=8000, value_usd=400000, deadline_days=10,
                  status=OrderStatus.AT_RISK, current_supplier_id="S001",
                  priority="high", region="americas"),
            Order(id="O003", product="Display Assembly",
                  quantity=6000, value_usd=360000, deadline_days=12,
                  status=OrderStatus.AT_RISK, current_supplier_id="S002",
                  priority="high", region="europe"),
            Order(id="O004", product="Battery Management IC",
                  quantity=12000, value_usd=180000, deadline_days=15,
                  status=OrderStatus.AT_RISK, current_supplier_id="S002",
                  priority="medium", region="asia"),
            Order(id="O005", product="Antenna Module",
                  quantity=15000, value_usd=120000, deadline_days=18,
                  status=OrderStatus.AT_RISK, current_supplier_id="S003",
                  priority="medium", region="americas"),
            Order(id="O006", product="Speaker Unit",
                  quantity=20000, value_usd=60000, deadline_days=21,
                  status=OrderStatus.AT_RISK, current_supplier_id="S003",
                  priority="low", region="europe"),
        ]

        # 8 suppliers — 3 are TRAPS (suspiciously cheap, unknown reliability)
        self.available_suppliers = [
            Supplier(id="S004", name="ReliableTech Premium",
                     location="Hsinchu, Taiwan", lead_time_days=5,
                     cost_multiplier=1.25, reliability_score=0.96,
                     capacity_available=12000, region="asia"),
            # TRAP 1: Too cheap, too good
            Supplier(id="S005", name="ValueFirst Electronics",
                     location="Shantou, China", lead_time_days=3,
                     cost_multiplier=0.70, reliability_score=0.30,
                     capacity_available=25000, region="asia"),
            Supplier(id="S006", name="SafeShip Korea",
                     location="Seoul, South Korea", lead_time_days=6,
                     cost_multiplier=1.15, reliability_score=0.91,
                     capacity_available=10000, region="asia"),
            # TRAP 2: Low cost, high capacity bait
            Supplier(id="S007", name="BargainParts Global",
                     location="Dhaka, Bangladesh", lead_time_days=4,
                     cost_multiplier=0.60, reliability_score=0.25,
                     capacity_available=30000, region="asia"),
            Supplier(id="S008", name="EuroQuality GmbH",
                     location="Munich, Germany", lead_time_days=8,
                     cost_multiplier=1.20, reliability_score=0.93,
                     capacity_available=8000, region="europe"),
            # TRAP 3: Plausible but unreliable
            Supplier(id="S009", name="RapidSource Ltd",
                     location="Shenzhen, China", lead_time_days=2,
                     cost_multiplier=0.80, reliability_score=0.35,
                     capacity_available=20000, region="asia"),
            Supplier(id="S010", name="AmeriParts Corp",
                     location="Austin, USA", lead_time_days=5,
                     cost_multiplier=1.30, reliability_score=0.94,
                     capacity_available=7000, region="americas"),
            Supplier(id="S011", name="ExpressGlobal Premium",
                     location="Singapore", lead_time_days=3,
                     cost_multiplier=1.50, reliability_score=0.97,
                     capacity_available=5000, region="asia"),
        ]

        self.budget = Budget(total=350000, spent=0, remaining=350000, currency="USD")

        return self._build_rich_observation()

    def _build_rich_observation(self) -> Observation:
        world_obs = self.world.to_full_observation()
        obs = self.get_observation()
        obs.insurance_premiums = world_obs.get("insurance_premiums")
        obs.fx_rates = world_obs.get("fx_rates")
        obs.legal_constraints = world_obs.get("legal_constraints")
        obs.sla_status = world_obs.get("sla_status")
        return obs

    def _handle_reroute(self, action) -> Reward:
        """Override: detect trap reroutes and schedule delayed failure."""
        order = self._get_order(action.order_id)
        supplier = self._get_supplier(action.new_supplier_id)
        breakdown = RewardBreakdown()

        # Already acted?
        if action.order_id in self.acted_order_ids:
            breakdown.redundant_action_penalty = -0.05
            return self._make_reward(value=-0.05,
                reason=f"Order {action.order_id} already handled.", breakdown=breakdown)

        # Capacity check
        if supplier.capacity_available < order.quantity:
            breakdown.redundant_action_penalty = -0.05
            return self._make_reward(value=-0.05,
                reason=f"{supplier.name} lacks capacity.", breakdown=breakdown)

        # Budget check
        extra_cost = max(0, order.value_usd * (supplier.cost_multiplier - 1.0))
        if self.budget.remaining < extra_cost:
            breakdown.budget_exceeded_penalty = -0.10
            return self._make_reward(value=-0.10,
                reason="Insufficient budget.", breakdown=breakdown)

        # TRAP MECHANIC: if supplier is a trap AND not investigated
        is_trap = supplier.id in self.trap_supplier_ids
        was_investigated = supplier.id in self.investigated_ids

        if is_trap and not was_investigated:
            # Appears to succeed initially...
            order.current_supplier_id = supplier.id
            order.status = OrderStatus.FULFILLED
            supplier.capacity_available -= order.quantity
            self.budget.spent += extra_cost
            self.budget.remaining -= extra_cost
            self.acted_order_ids.add(action.order_id)

            # ...but schedule delayed failure (2 steps later)
            self.pending_trap_failures[action.order_id] = self.current_step + 2

            self.metrics.orders_saved += 1
            self.metrics.revenue_protected += order.value_usd
            breakdown.orders_saved_reward = 0.15
            return self._make_reward(value=0.15,
                reason=f"✅ Order {action.order_id} rerouted to {supplier.name}. "
                       f"Extra cost: ${extra_cost:,.0f}.",
                breakdown=breakdown)

        if is_trap and was_investigated:
            # Agent investigated and found it's a trap — penalize rerouting anyway
            breakdown.bad_supplier_penalty = -0.15
            return self._make_reward(value=-0.15,
                reason=f"⛔ {supplier.name} was investigated and found UNRELIABLE. "
                       f"Rerouting anyway is a mistake.", breakdown=breakdown)

        # Normal reroute (non-trap supplier)
        on_time = supplier.lead_time_days <= order.deadline_days
        order.current_supplier_id = supplier.id
        order.status = OrderStatus.FULFILLED if on_time else OrderStatus.DELAYED
        supplier.capacity_available -= order.quantity
        self.budget.spent += extra_cost
        self.budget.remaining -= extra_cost
        self.acted_order_ids.add(action.order_id)

        if on_time:
            breakdown.orders_saved_reward = 0.15
            breakdown.deadline_met_reward = 0.10
            self.metrics.orders_saved += 1
            self.metrics.revenue_protected += order.value_usd
            return self._make_reward(value=0.25,
                reason=f"✅ Order {action.order_id} rerouted to {supplier.name} on time.",
                breakdown=breakdown)
        else:
            breakdown.orders_saved_reward = 0.05
            breakdown.missed_deadline_penalty = -0.10
            self.metrics.orders_delayed += 1
            return self._make_reward(value=-0.05,
                reason=f"⚠️ Order {action.order_id} rerouted but will miss deadline.",
                breakdown=breakdown)

    def step(self, action):
        """Override to handle trap failure mechanics."""
        self.world.advance_step()

        # Check for pending trap failures
        failures_to_fire = []
        for order_id, fail_step in list(self.pending_trap_failures.items()):
            if self.current_step + 1 >= fail_step:
                failures_to_fire.append(order_id)
                del self.pending_trap_failures[order_id]

        for order_id in failures_to_fire:
            order = self._get_order(order_id)
            if order.status == OrderStatus.FULFILLED:
                order.status = OrderStatus.AT_RISK
                self.acted_order_ids.discard(order_id)
                self.metrics.orders_saved = max(0, self.metrics.orders_saved - 1)
                self.metrics.revenue_protected -= order.value_usd
                self.trap_failures.append(order_id)
                # Rise insurance premium
                self.world.market.file_insurance_claim("SH_LAX", order.value_usd * 0.2)

                # Add message about the failure
                trap_disruption = Disruption(
                    id=f"TRAP_{order_id}",
                    type="supplier_failure",
                    severity="critical",
                    affected_supplier_id=order.current_supplier_id,
                    affected_supplier_name=f"TRAP FAILURE: {order.current_supplier_id}",
                    estimated_duration_days=999,
                    description=f"⛔ TRAP SUPPLIER FAILED! Order {order_id} reverted to at_risk. "
                                f"Supplier was unreliable. Budget already spent.",
                )
                self.disruptions.append(trap_disruption)

        obs, reward, done, info = super().step(action)
        if not done:
            obs = self._build_rich_observation()
            obs.step = self.current_step
            obs.done = self.done
        return obs, reward, done, info

    def get_final_score(self) -> float:
        total_value = sum(o.value_usd for o in self.orders)
        saved = sum(o.value_usd for o in self.orders if o.status == OrderStatus.FULFILLED)

        # Revenue after trap failures resolve
        revenue_score = saved / total_value if total_value > 0 else 0

        # Trap detection: investigated traps before rerouting
        traps_investigated = len(self.trap_supplier_ids & self.investigated_ids)
        trap_score = traps_investigated / len(self.trap_supplier_ids)

        # Zero trap failures bonus
        zero_trap_score = 1.0 if len(self.trap_failures) == 0 else 0.0

        # Budget efficiency
        budget_score = max(0, 1.0 - self.budget.spent / self.budget.total)

        # Investigation depth
        invest_score = min(1.0, len(self.investigated_ids) / max(1, len(self.hidden_supplier_ids)))

        score = (0.25 * revenue_score +
                 0.25 * trap_score +
                 0.20 * zero_trap_score +
                 0.15 * budget_score +
                 0.15 * invest_score)
        return max(0.01, min(0.99, score))
