# backend/app/tasks/task_easy.py

import uuid
from .base import BaseTask
from ..models import Observation, Budget, Metrics, Disruption, Order, Supplier, OrderStatus


class TaskEasy(BaseTask):
    """
    TASK 1 — Single Lane Disruption (EASY)

    Scenario:
        One supplier delayed.
        One order at risk.
        Two clear alternatives available.
        Generous budget.
        Obvious correct answer.

    What agent must do:
        Pick the right alternative supplier
        considering cost + lead time vs deadline.

    Expected score for good agent: 0.8 - 1.0
    """

    task_id         = "task_easy"
    task_name       = "Single Lane Disruption"
    task_difficulty = "easy"
    task_description = (
        "A single supplier is delayed. One high-value order is at risk. "
        "Two alternative suppliers are available. Choose wisely to meet "
        "the deadline within budget."
    )
    max_steps = 10

    def reset(self) -> Observation:
        """Set up easy scenario"""
        self.current_step    = 0
        self.done            = False
        self.episode_id      = str(uuid.uuid4())[:8]
        self.acted_order_ids      = set()
        self.acted_disruption_ids = set()
        self.investigated_ids     = set()
        self.action_history       = []

        # ── Single disruption ──────────────────────
        self.disruptions = [
            Disruption(
                id="D001",
                type="delay",
                severity="medium",
                affected_supplier_id="S001",
                affected_supplier_name="PrimeSource Industries",
                estimated_duration_days=10,
                description=(
                    "PrimeSource Industries is experiencing a 10-day delay "
                    "due to unexpected machinery breakdown at their main "
                    "production facility in Germany."
                ),
                is_resolved=False
            )
        ]

        # ── Single at-risk order ───────────────────
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
            )
        ]

        # ── Two clear alternatives ─────────────────
        # S004: on time, moderate cost  ← CORRECT CHOICE
        # S006: on time, expensive      ← Valid but costly
        self.available_suppliers = [
            Supplier(
                id="S004",
                name="NorthStar Logistics",
                location="Canada",
                lead_time_days=4,
                cost_multiplier=1.1,
                reliability_score=0.92,
                capacity_available=25000,
                is_available=True
            ),
            Supplier(
                id="S006",
                name="AlphaSupply Co",
                location="USA",
                lead_time_days=2,
                cost_multiplier=1.5,
                reliability_score=0.97,
                capacity_available=20000,
                is_available=True
            )
        ]

        # ── Generous budget ────────────────────────
        self.budget = Budget(
            total=50000.0,
            spent=0.0,
            remaining=50000.0
        )

        self.metrics = Metrics()

        return self.get_observation()

    def get_final_score(self) -> float:
        """
        Score breakdown:
            Order fulfilled on time  → 0.50
            Budget respected         → 0.20
            Good supplier chosen     → 0.20
            Completed early          → 0.10
        """
        # ── No actions taken yet → score is 0.0 ──
        if not self.has_resolution_action():
            return 0.0

        score = 0.0
        if not self.orders:
            return 0.0

        order = self.orders[0]

        # Was order saved on time?
        if order.status == OrderStatus.FULFILLED:
            score += 0.50
        elif order.status == OrderStatus.DELAYED:
            score += 0.15

        # Budget respected? (only reward if we actually spent something)
        if self.budget.spent > 0 and self.budget.remaining >= 0:
            score += 0.20
        # Good supplier chosen?
        if order.current_supplier_id == "S004":
            score += 0.20
        elif order.current_supplier_id == "S006":
            score += 0.10

        # Finished early after actually resolving the task
        if self.done and order.status == OrderStatus.FULFILLED and self.current_step <= self.max_steps * 0.5:
            score += 0.10

        return round(min(score, 1.0), 3)
