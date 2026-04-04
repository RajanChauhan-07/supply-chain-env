# backend/app/tasks/task_medium.py

import uuid
from .base import BaseTask
from ..models import Observation, Budget, Metrics, Disruption, Order, Supplier, OrderStatus


class TaskMedium(BaseTask):
    """
    TASK 2 — Multi-Point Failure (MEDIUM)

    Scenario:
        3 simultaneous disruptions.
        4 orders at risk (mixed priorities/deadlines).
        Limited alternatives — some overlap.
        Tighter budget — cannot save everything.
        Agent must PRIORITIZE which orders to save.

    What agent must do:
        Triage orders by value + deadline.
        Find non-conflicting supplier alternatives.
        Accept that some orders will be lost.

    Expected score for good agent: 0.7 - 0.9
    """

    task_id         = "task_medium"
    task_name       = "Multi-Point Failure"
    task_difficulty = "medium"
    task_description = (
        "Three simultaneous supply disruptions put four orders at risk. "
        "Budget is limited — you cannot save everything on time. Prioritize high-value "
        "orders and find the best alternatives under constraints."
    )
    max_steps = 20

    def reset(self) -> Observation:
        self.current_step         = 0
        self.done                 = False
        self.episode_id           = str(uuid.uuid4())[:8]
        self.acted_order_ids      = set()
        self.acted_disruption_ids = set()
        self.investigated_ids     = set()
        self.action_history       = []

        # ── Three disruptions ──────────────────────
        self.disruptions = [
            Disruption(
                id="D001",
                type="delay",
                severity="high",
                affected_supplier_id="S001",
                affected_supplier_name="PrimeSource Industries",
                estimated_duration_days=10,
                description=(
                    "PrimeSource Industries facing 10-day delay due to "
                    "machinery breakdown. Affects orders O001 and O003."
                ),
                is_resolved=False
            ),
            Disruption(
                id="D002",
                type="closure",
                severity="critical",
                affected_supplier_id="S003",
                affected_supplier_name="EastBridge Supplies",
                estimated_duration_days=30,
                description=(
                    "EastBridge Supplies ordered to close for 30 days "
                    "due to regulatory violations. Affects orders O002 and O005."
                ),
                is_resolved=False
            ),
            Disruption(
                id="D003",
                type="capacity",
                severity="medium",
                affected_supplier_id="S005",
                affected_supplier_name="SunCoast Trading",
                estimated_duration_days=15,
                description=(
                    "SunCoast Trading operating at 40% capacity due to "
                    "worker strike. Affects order O006."
                ),
                is_resolved=False
            )
        ]

        # ── Four orders at risk ────────────────────
        self.orders = [
            Order(
                id="O001",
                product="Industrial Circuit Boards",
                quantity=5000,
                value_usd=250000.0,
                deadline_days=7,
                status=OrderStatus.AT_RISK,
                current_supplier_id="S001",
                priority="high"
            ),
            Order(
                id="O003",
                product="Medical Grade Plastics",
                quantity=8000,
                value_usd=320000.0,
                deadline_days=5,
                status=OrderStatus.AT_RISK,
                current_supplier_id="S001",
                priority="high"
            ),
            Order(
                id="O002",
                product="Steel Reinforcement Rods",
                quantity=20000,
                value_usd=180000.0,
                deadline_days=14,
                status=OrderStatus.AT_RISK,
                current_supplier_id="S003",
                priority="high"
            ),
            Order(
                id="O005",
                product="Consumer Electronics Parts",
                quantity=15000,
                value_usd=75000.0,
                deadline_days=21,
                status=OrderStatus.AT_RISK,
                current_supplier_id="S003",
                priority="medium"
            )
        ]

        # ── Limited alternatives ───────────────────
        self.available_suppliers = [
            Supplier(
                id="S004",
                name="NorthStar Logistics",
                location="Canada",
                lead_time_days=4,
                cost_multiplier=1.1,
                reliability_score=0.92,
                capacity_available=15000,   # limited capacity
                is_available=True
            ),
            Supplier(
                id="S006",
                name="AlphaSupply Co",
                location="USA",
                lead_time_days=2,
                cost_multiplier=1.5,
                reliability_score=0.97,
                capacity_available=10000,   # very limited
                is_available=True
            ),
            Supplier(
                id="S007",
                name="MedTerra Exports",
                location="Spain",
                lead_time_days=7,
                cost_multiplier=1.05,
                reliability_score=0.89,
                capacity_available=30000,
                is_available=True
            ),
            Supplier(
                id="S012",
                name="QuickShip Distributors",
                location="Netherlands",
                lead_time_days=3,
                cost_multiplier=1.3,
                reliability_score=0.91,
                capacity_available=20000,
                is_available=True
            )
        ]

        # ── Tighter budget ─────────────────────────
        self.budget = Budget(
            total=45000.0,
            spent=0.0,
            remaining=45000.0
        )

        self.metrics = Metrics()
        return self.get_observation()

    def get_final_score(self) -> float:
        """
        Score breakdown:
            High-value orders saved ratio  → 0.40
            Total revenue protected %      → 0.30
            Budget adherence               → 0.20
            Correct prioritization         → 0.10
        """
        # ── No actions taken yet → score is 0.0 ──
        if not self.has_resolution_action():
            return 0.0

        score = 0.0
        total_value = sum(o.value_usd for o in self.orders)
        high_orders = [o for o in self.orders if o.priority == "high"]

        # High value order save ratio
        saved_high = [o for o in high_orders if o.status == OrderStatus.FULFILLED]
        if high_orders:
            score += 0.40 * (len(saved_high) / len(high_orders))

        # Revenue protected
        if total_value > 0:
            score += 0.30 * (self.metrics.revenue_protected / total_value)

        # Budget adherence (only reward if actions were taken)
        if self.acted_order_ids and self.budget.remaining >= 0:
            score += 0.20
        # Prioritization bonus
        o003 = next((o for o in self.orders if o.id == "O003"), None)
        if o003 and o003.status == OrderStatus.FULFILLED:
            score += 0.10

        return round(min(max(score, 0.0), 1.0), 3)
