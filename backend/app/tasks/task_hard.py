# backend/app/tasks/task_hard.py

import uuid
from .base import BaseTask
from ..models import Observation, Budget, Metrics, Disruption, Order, Supplier, OrderStatus


class TaskHard(BaseTask):
    """
    TASK 3 — Cascade Crisis (HARD)

    Scenario:
        5 simultaneous disruptions including bankruptcy + geopolitical.
        8 orders (3 high-value, 3 medium, 2 low).
        Very tight budget — hard tradeoffs required.
        Some alternatives have hidden reliability issues.
        Escalation needed for 2 critical disruptions.
        Cascading effects — decisions affect each other.

    What agent must do:
        Multi-step resolution.
        Discover hidden info through investigation.
        Prioritize high-value orders first.
        Know when to escalate vs handle alone.
        Manage cascading effects carefully.

    Expected score for good agent: 0.45 - 0.7
    """

    task_id         = "task_hard"
    task_name       = "Cascade Crisis"
    task_difficulty = "hard"
    task_description = (
        "Five simultaneous disruptions including a bankruptcy and geopolitical "
        "closure threaten eight orders. Budget is severely constrained. "
        "Some suppliers have hidden issues discoverable only through investigation. "
        "Prioritize wisely — a perfect rescue is intentionally infeasible."
    )
    max_steps = 30

    def reset(self, seed=None) -> Observation:
        self.current_step         = 0
        self.done                 = False
        self.episode_id           = str(uuid.uuid4())[:8]
        self.acted_order_ids      = set()
        self.acted_disruption_ids = set()
        self.investigated_ids     = set()
        self.hidden_supplier_ids  = {"S005_ALT"}
        self.action_history       = []

        # ── Five disruptions ───────────────────────
        self.disruptions = [
            Disruption(
                id="D001",
                type="delay",
                severity="high",
                affected_supplier_id="S001",
                affected_supplier_name="PrimeSource Industries",
                estimated_duration_days=10,
                description=(
                    "PrimeSource Industries machinery breakdown. "
                    "Affects O001, O003, O009, O012."
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
                    "EastBridge Supplies regulatory closure. "
                    "Affects O002, O005, O007."
                ),
                is_resolved=False
            ),
            Disruption(
                id="D003",
                type="capacity",
                severity="high",
                affected_supplier_id="S005",
                affected_supplier_name="SunCoast Trading",
                estimated_duration_days=15,
                description=(
                    "SunCoast Trading at 40% capacity due to strike. "
                    "Affects O006, O008."
                ),
                is_resolved=False
            ),
            Disruption(
                id="D005",
                type="bankruptcy",
                severity="critical",
                affected_supplier_id="S008",
                affected_supplier_name="PacificRim Partners",
                estimated_duration_days=90,
                description=(
                    "PacificRim Partners filed for bankruptcy. "
                    "All operations suspended. Affects O011."
                ),
                is_resolved=False
            ),
            Disruption(
                id="D006",
                type="geopolitical",
                severity="critical",
                affected_supplier_id="S010",
                affected_supplier_name="GlobalEdge Manufacturing",
                estimated_duration_days=45,
                description=(
                    "Trade sanctions block GlobalEdge Manufacturing imports. "
                    "Affects O010."
                ),
                is_resolved=False
            )
        ]

        # ── Eight orders ───────────────────────────
        self.orders = [
            # High value
            Order(
                id="O012",
                product="Defense Grade Alloys",
                quantity=1000,
                value_usd=750000.0,
                deadline_days=8,
                status=OrderStatus.AT_RISK,
                current_supplier_id="S001",
                priority="high"
            ),
            Order(
                id="O009",
                product="Aerospace Fasteners",
                quantity=2000,
                value_usd=480000.0,
                deadline_days=12,
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
            # Medium value
            Order(
                id="O001",
                product="Industrial Circuit Boards",
                quantity=5000,
                value_usd=250000.0,
                deadline_days=7,
                status=OrderStatus.AT_RISK,
                current_supplier_id="S001",
                priority="medium"
            ),
            Order(
                id="O002",
                product="Steel Reinforcement Rods",
                quantity=20000,
                value_usd=180000.0,
                deadline_days=14,
                status=OrderStatus.AT_RISK,
                current_supplier_id="S003",
                priority="medium"
            ),
            Order(
                id="O007",
                product="Solar Panel Components",
                quantity=10000,
                value_usd=150000.0,
                deadline_days=18,
                status=OrderStatus.AT_RISK,
                current_supplier_id="S003",
                priority="medium"
            ),
            # Low value
            Order(
                id="O010",
                product="Agricultural Equipment Parts",
                quantity=7000,
                value_usd=60000.0,
                deadline_days=30,
                status=OrderStatus.AT_RISK,
                current_supplier_id="S010",
                priority="low"
            ),
            Order(
                id="O011",
                product="Textile Raw Materials",
                quantity=30000,
                value_usd=45000.0,
                deadline_days=20,
                status=OrderStatus.AT_RISK,
                current_supplier_id="S008",
                priority="low"
            )
        ]

        # ── Suppliers — some with hidden issues ────
        # S008 has low reliability (hidden until investigated)
        self.available_suppliers = [
            Supplier(
                id="S004",
                name="NorthStar Logistics",
                location="Canada",
                lead_time_days=4,
                cost_multiplier=1.1,
                reliability_score=0.92,
                capacity_available=10000,   # tight capacity
                is_available=True
            ),
            Supplier(
                id="S006",
                name="AlphaSupply Co",
                location="USA",
                lead_time_days=2,
                cost_multiplier=1.5,
                reliability_score=0.97,
                capacity_available=5000,    # very tight
                is_available=True
            ),
            Supplier(
                id="S007",
                name="MedTerra Exports",
                location="Spain",
                lead_time_days=7,
                cost_multiplier=1.05,
                reliability_score=0.89,
                capacity_available=12000,
                is_available=True
            ),
            Supplier(
                id="S009",
                name="BridgePoint Supply",
                location="Turkey",
                lead_time_days=6,
                cost_multiplier=0.90,
                reliability_score=0.83,
                capacity_available=7000,
                is_available=True
            ),
            Supplier(
                id="S011",
                name="ArcticFlow Industries",
                location="Finland",
                lead_time_days=6,
                cost_multiplier=1.15,
                reliability_score=0.94,
                capacity_available=8000,
                is_available=True
            ),
            Supplier(
                id="S012",
                name="QuickShip Distributors",
                location="Netherlands",
                lead_time_days=3,
                cost_multiplier=1.3,
                reliability_score=0.91,
                capacity_available=12000,
                is_available=True
            ),
            # Hidden bad supplier — low reliability
            Supplier(
                id="S005_ALT",
                name="SunCoast Reserve Unit",
                location="India",
                lead_time_days=8,
                cost_multiplier=0.65,
                reliability_score=0.45,    # ← HIDDEN: very unreliable
                capacity_available=50000,
                is_available=True
            )
        ]

        # ── Very tight budget ──────────────────────
        self.budget = Budget(
            total=18000.0,
            spent=0.0,
            remaining=18000.0
        )

        self.metrics = Metrics()
        self._apply_seed_variation(seed)
        return self.get_observation()

    def get_final_score(self) -> float:
        """
        Score breakdown:
            High-value orders saved        → 0.35
            Total revenue protected %      → 0.25
            Budget not exceeded            → 0.20
            Correct escalation decisions   → 0.10
            Speed of resolution            → 0.10
        """
        # ── No actions taken yet → score is 0.0 ──
        if not self.has_resolution_action():
            return 0.0

        score = 0.0
        total_value = sum(o.value_usd for o in self.orders)
        high_orders = [o for o in self.orders if o.priority == "high"]

        # High value orders saved
        saved_high = [o for o in high_orders if o.status == OrderStatus.FULFILLED]
        if high_orders:
            score += 0.35 * (len(saved_high) / len(high_orders))

        # Revenue protected
        if total_value > 0:
            score += 0.25 * (self.metrics.revenue_protected / total_value)

        # Budget not exceeded (only reward if actions were taken)
        if self.acted_order_ids and self.budget.remaining >= 0:
            score += 0.20
        # Escalation decisions
        critical_disruption_ids = {"D002", "D005", "D006"}
        escalated = critical_disruption_ids & self.acted_disruption_ids
        if critical_disruption_ids:
            score += 0.10 * (len(escalated) / len(critical_disruption_ids))

        # Speed bonus (only when done)
        if self.done and len(saved_high) == len(high_orders):
            if self.current_step <= self.max_steps * 0.60:
                score += 0.10
            elif self.current_step <= self.max_steps * 0.80:
                score += 0.05

        return round(min(max(score, 0.0), 1.0), 3)
