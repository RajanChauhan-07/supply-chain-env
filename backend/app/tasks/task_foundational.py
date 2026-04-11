# backend/app/tasks/task_foundational.py
"""
Task 1: Foundational — Basic Rerouting
Difficulty: Easy | Max Steps: 10

Single-tier, deterministic scenario. No FX, no insurance, no bullwhip.
Tests basic constraint satisfaction: capacity, budget, deadline, reliability.
Entry point for agents to learn the action space.
"""

from typing import Optional
from .base import BaseTask
from ..models import (
    Observation, Disruption, Order, Supplier, Budget, Metrics,
    OrderStatus, RewardBreakdown
)


class TaskFoundational(BaseTask):
    task_id = "task_foundational"
    task_name = "Basic Rerouting"
    task_difficulty = "easy"
    task_description = (
        "A single supplier is disrupted. Three orders need rerouting to "
        "alternative suppliers. Test basic capacity and budget constraints."
    )
    max_steps = 10

    def reset(self, seed: Optional[int] = None) -> Observation:
        import random
        rng = random.Random(seed or 42)

        self.current_step = 0
        self.done = False
        self.episode_id = f"foundational_{seed or 42}"
        self.action_history = []
        self.acted_order_ids = set()
        self.acted_disruption_ids = set()
        self.investigated_ids = set()
        self.hidden_supplier_ids = set()
        self.metrics = Metrics()

        # Single disruption at primary supplier
        self.disruptions = [
            Disruption(
                id="D001",
                type="delay",
                severity="high",
                affected_supplier_id="S001",
                affected_supplier_name="PrimaryElec Shenzhen",
                estimated_duration_days=14,
                description="Factory equipment failure at PrimaryElec Shenzhen. "
                            "Production halted for 2 weeks.",
            ),
        ]

        # 3 orders at risk
        self.orders = [
            Order(id="O001", product="Smartphone Assembly Kit",
                  quantity=5000, value_usd=250000, deadline_days=7,
                  status=OrderStatus.AT_RISK, current_supplier_id="S001",
                  priority="high", region="asia"),
            Order(id="O002", product="Tablet Display Module",
                  quantity=3000, value_usd=180000, deadline_days=10,
                  status=OrderStatus.AT_RISK, current_supplier_id="S001",
                  priority="medium", region="americas"),
            Order(id="O003", product="Laptop Battery Pack",
                  quantity=2000, value_usd=80000, deadline_days=14,
                  status=OrderStatus.AT_RISK, current_supplier_id="S001",
                  priority="low", region="europe"),
        ]

        # 4 alternative suppliers (simple, single-tier)
        self.available_suppliers = [
            Supplier(id="S002", name="ReliableTech Taiwan",
                     location="Hsinchu, Taiwan", lead_time_days=5,
                     cost_multiplier=1.10, reliability_score=0.95,
                     capacity_available=8000, region="asia"),
            Supplier(id="S003", name="FastShip Korea",
                     location="Seoul, South Korea", lead_time_days=3,
                     cost_multiplier=1.30, reliability_score=0.90,
                     capacity_available=4000, region="asia"),
            Supplier(id="S004", name="EuroComponents GmbH",
                     location="Munich, Germany", lead_time_days=8,
                     cost_multiplier=1.15, reliability_score=0.88,
                     capacity_available=6000, region="europe"),
            Supplier(id="S005", name="AmeriParts Inc.",
                     location="Austin, Texas", lead_time_days=4,
                     cost_multiplier=1.25, reliability_score=0.92,
                     capacity_available=5000, region="americas"),
        ]

        self.budget = Budget(total=100000, spent=0, remaining=100000, currency="USD")

        return self.get_observation()

    def get_final_score(self) -> float:
        total_value = sum(o.value_usd for o in self.orders)
        saved_value = sum(o.value_usd for o in self.orders
                          if o.status == OrderStatus.FULFILLED)
        delayed_value = sum(o.value_usd for o in self.orders
                            if o.status == OrderStatus.DELAYED)

        revenue_pct = (saved_value + delayed_value * 0.5) / total_value if total_value > 0 else 0
        budget_pct = max(0, 1.0 - self.budget.spent / self.budget.total) if self.budget.total > 0 else 0

        score = 0.6 * revenue_pct + 0.3 * budget_pct + 0.1 * (1.0 if self.acted_disruption_ids else 0.0)
        return max(0.01, min(0.99, score))
