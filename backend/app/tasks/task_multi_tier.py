# backend/app/tasks/task_multi_tier.py
"""
Task 2: Multi-Tier Crisis
Difficulty: Medium | Max Steps: 20

Multi-tier supply network with Tier 1/2/3 cascading disruptions.
Bullwhip effect amplifies demand uncertainty up the tiers.
Agent must understand that fixing Tier 1 requires Tier 2 stability.
"""

from typing import Optional
from .base import BaseTask
from ..models import (
    Observation, Disruption, Order, Supplier, Budget, Metrics,
    OrderStatus, RewardBreakdown
)
from ..simulation.world_state import WorldState


class TaskMultiTier(BaseTask):
    task_id = "task_multi_tier"
    task_name = "Multi-Tier Crisis"
    task_difficulty = "medium"
    task_description = (
        "A Tier 3 rare earth supplier disruption cascades through Tier 2 "
        "components to Tier 1 assembly. The agent must investigate the "
        "root cause and reroute across tiers. Bullwhip effect amplifies "
        "demand uncertainty at each level. "
        "PARTIAL OBSERVABILITY: Tier 3 supplier state is hidden until investigated."
    )
    max_steps = 20

    # ── Partial observability: Tier 3 is opaque until investigated ──
    partial_obs = True

    def reset(self, seed: Optional[int] = None) -> Observation:
        import random
        rng = random.Random(seed or 42)

        self.current_step = 0
        self.done = False
        self.episode_id = f"multi_tier_{seed or 42}"
        self.action_history = []
        self.acted_order_ids = set()
        self.acted_disruption_ids = set()
        self.investigated_ids = set()
        self.hidden_supplier_ids = {"S005", "S007"}
        self.metrics = Metrics()

        # Track which tiers have been "revealed" via investigation
        self.revealed_tier3_suppliers: set = set()

        # World state for rich observation
        self.world = WorldState(seed=seed or 42, difficulty=0.5)

        # Tier 3 disruption that cascades down
        self.disruptions = [
            Disruption(
                id="D001", type="geopolitical", severity="critical",
                affected_supplier_id="S001",
                affected_supplier_name="Rare Earth Mining Corp (Tier 3)",
                estimated_duration_days=30,
                description="Export restrictions on rare earth materials from "
                            "primary mining region. Tier 2 component supplies affected.",
            ),
            Disruption(
                id="D002", type="capacity", severity="high",
                affected_supplier_id="S002",
                affected_supplier_name="DisplayTech (Tier 2)",
                estimated_duration_days=14,
                description="Cascading shortage — rare earth embargo restricts "
                            "display component production.",
            ),
            Disruption(
                id="D003", type="delay", severity="medium",
                affected_supplier_id="S003",
                affected_supplier_name="Foxconn Assembly (Tier 1)",
                estimated_duration_days=7,
                description="Assembly line slowdown due to component shortage "
                            "from upstream Tier 2 suppliers.",
            ),
        ]

        # 6 orders at risk across priorities
        self.orders = [
            Order(id="O001", product="iPhone Pro Assembly",
                  quantity=10000, value_usd=500000, deadline_days=7,
                  status=OrderStatus.AT_RISK, current_supplier_id="S003",
                  priority="critical", region="asia"),
            Order(id="O002", product="iPad Display Module",
                  quantity=8000, value_usd=320000, deadline_days=10,
                  status=OrderStatus.AT_RISK, current_supplier_id="S002",
                  priority="high", region="americas"),
            Order(id="O003", product="MacBook Battery Cell",
                  quantity=5000, value_usd=200000, deadline_days=14,
                  status=OrderStatus.AT_RISK, current_supplier_id="S001",
                  priority="high", region="europe"),
            Order(id="O004", product="Watch Sensor Kit",
                  quantity=15000, value_usd=150000, deadline_days=12,
                  status=OrderStatus.AT_RISK, current_supplier_id="S003",
                  priority="medium", region="asia"),
            Order(id="O005", product="AirPods Driver Unit",
                  quantity=20000, value_usd=100000, deadline_days=20,
                  status=OrderStatus.AT_RISK, current_supplier_id="S002",
                  priority="medium", region="americas"),
            Order(id="O006", product="Charger PCB",
                  quantity=30000, value_usd=60000, deadline_days=21,
                  status=OrderStatus.AT_RISK, current_supplier_id="S003",
                  priority="low", region="europe"),
        ]

        # Suppliers across tiers
        self.available_suppliers = [
            # Tier 1 alternatives
            Supplier(id="S004", name="Pegatron Shanghai (T1)",
                     location="Shanghai, China", lead_time_days=4,
                     cost_multiplier=1.15, reliability_score=0.91,
                     capacity_available=12000, region="asia"),
            Supplier(id="S005", name="Jabil Penang (T1)", # Hidden reliability
                     location="Penang, Malaysia", lead_time_days=6,
                     cost_multiplier=1.08, reliability_score=0.72,
                     capacity_available=8000, region="asia"),
            # Tier 2 alternatives
            Supplier(id="S006", name="LG Display (T2)",
                     location="Paju, South Korea", lead_time_days=8,
                     cost_multiplier=1.20, reliability_score=0.89,
                     capacity_available=10000, region="asia"),
            Supplier(id="S007", name="Corning Glass (T2)", # Hidden reliability
                     location="Kentucky, USA", lead_time_days=10,
                     cost_multiplier=1.05, reliability_score=0.96,
                     capacity_available=15000, region="americas"),
            # Tier 3 alternative
            Supplier(id="S008", name="MP Materials (T3)",
                     location="Mountain Pass, USA", lead_time_days=21,
                     cost_multiplier=1.40, reliability_score=0.85,
                     capacity_available=50000, region="americas"),
            # Global expeditor
            Supplier(id="S009", name="GlobalFlex Express",
                     location="Singapore", lead_time_days=3,
                     cost_multiplier=1.50, reliability_score=0.94,
                     capacity_available=5000, region="asia"),
        ]

        self.budget = Budget(total=300000, spent=0, remaining=300000, currency="USD")

        return self._build_rich_observation()

    def _mask_tier3(self, supply_tiers: dict) -> dict:
        """Apply partial observability: mask Tier 3 supplier details."""
        if not self.partial_obs or not supply_tiers:
            return supply_tiers

        masked = dict(supply_tiers)
        if "tier3" in masked:
            tier3 = dict(masked["tier3"])
            masked_suppliers = []
            for s in tier3.get("suppliers", []):
                sid = s.get("id", "")
                if sid in self.revealed_tier3_suppliers:
                    masked_suppliers.append(s)  # Fully visible after investigation
                else:
                    masked_suppliers.append({
                        "id": sid,
                        "name": s.get("name", "Unknown"),
                        "region": s.get("region", "unknown"),
                        "location": "HIDDEN — investigate to reveal",
                        "capacity_available": "unknown",
                        "lead_time_days": "unknown",
                        "cost_multiplier": "unknown",
                        "reliability": None,
                        "reliability_known": False,
                        "is_disrupted": "unknown",
                        "depends_on": s.get("depends_on", []),
                    })
            tier3["suppliers"] = masked_suppliers
            masked["tier3"] = tier3
        return masked

    def _build_rich_observation(self) -> Observation:
        """Build observation with v2 fields and partial observability."""
        world_obs = self.world.to_full_observation()
        obs = self.get_observation()

        # Apply partial observability mask to tier 3
        supply_tiers = self._mask_tier3(world_obs.get("supply_tiers"))

        # Inject v2 fields
        obs.supply_tiers = supply_tiers
        obs.shipping_lanes = world_obs.get("shipping_lanes")
        obs.carrier_options = world_obs.get("carrier_options")
        obs.bullwhip_state = world_obs.get("bullwhip_state")
        obs.demand_forecast = world_obs.get("demand_forecast")
        obs.dc_inventory = world_obs.get("dc_inventory")

        return obs

    def _handle_investigate(self, action):
        """Override investigate to reveal Tier 3 suppliers."""
        result = super()._handle_investigate(action)
        # If the investigated target is a T3 supplier in the world sim, reveal it
        target_id = getattr(action, 'target_id', None)
        if target_id:
            for sup in self.world.network.get_all_suppliers_flat():
                if sup.id == target_id and sup.tier == 3:
                    self.revealed_tier3_suppliers.add(target_id)
            # Also reveal T3 suppliers matching the task-level supplier IDs
            t3_ids = {"S001", "S008"}  # Task-level Tier 3 supplier IDs
            if target_id in t3_ids:
                self.revealed_tier3_suppliers.add(target_id)
        return result

    def step(self, action):
        """Override step to advance world state."""
        # Advance world simulation
        self.world.advance_step()
        # Delegate to parent
        obs, reward, done, info = super().step(action)
        # Enrich observation
        if not done:
            world_obs = self.world.to_full_observation()
            supply_tiers = self._mask_tier3(world_obs.get("supply_tiers"))
            obs.supply_tiers = supply_tiers
            obs.bullwhip_state = world_obs.get("bullwhip_state")
            obs.demand_forecast = world_obs.get("demand_forecast")
        return obs, reward, done, info

    def get_final_score(self) -> float:
        total_value = sum(o.value_usd for o in self.orders)
        saved = sum(o.value_usd for o in self.orders if o.status == OrderStatus.FULFILLED)
        delayed = sum(o.value_usd for o in self.orders if o.status == OrderStatus.DELAYED)

        # Multi-objective
        revenue_score = (saved + delayed * 0.4) / total_value if total_value > 0 else 0
        budget_score = max(0, 1.0 - self.budget.spent / self.budget.total * 1.5)
        investigation_score = len(self.investigated_ids) / max(1, len(self.hidden_supplier_ids))
        escalation_score = len(self.acted_disruption_ids) / max(1, len(self.disruptions))

        score = (0.40 * revenue_score +
                 0.25 * budget_score +
                 0.20 * min(1.0, investigation_score) +
                 0.15 * min(1.0, escalation_score))
        return max(0.01, min(0.99, score))
