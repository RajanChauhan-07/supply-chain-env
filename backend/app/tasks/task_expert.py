# backend/app/tasks/task_expert.py

import uuid
from .base import BaseTask
from ..models import Observation, Budget, Metrics, Disruption, Order, Supplier, OrderStatus


class TaskExpert(BaseTask):
    """
    TASK 4 — Cascading Domino Effect (EXPERT)

    Scenario:
        10 orders across 3 geographic regions (Asia, Europe, Americas).
        4 initial disruptions that CASCADE — rerouting to a stressed region
        can trigger secondary disruptions (supply surge bottleneck).
        Budget is moderate but cascade costs escalate quickly.
        Agent must think 2 moves ahead to avoid domino failures.

    Unique Mechanics:
        - cascade_rules: rerouting too many orders to one region triggers
          a new disruption in that region (supply surge).
        - region_stress: tracks how many orders are routed to each region.
        - Once a region hits stress threshold (3+ reroutes), a cascade
          disruption fires — all suppliers in that region get +30% cost
          and -2 day lead time penalty.

    What agent must do:
        - Balance reroutes across regions to avoid cascades.
        - Investigate before committing to expensive suppliers.
        - Escalate critical disruptions affecting multiple orders.
        - Accept strategic losses on low-value orders.

    Expected score for good agent: 0.35 - 0.65
    """

    task_id         = "task_expert"
    task_name       = "Cascading Domino Effect"
    task_difficulty  = "expert"
    task_description = (
        "Ten orders span three geographic regions. Disruptions cascade — "
        "rerouting too many orders to a single region triggers secondary "
        "supply-surge bottlenecks. The agent must spread risk across regions, "
        "think two moves ahead, and accept strategic trade-offs to minimize "
        "total portfolio loss."
    )
    max_steps = 25

    # Cascade threshold: how many reroutes to a region before cascade fires
    CASCADE_THRESHOLD = 3

    def reset(self, seed=None) -> Observation:
        self.current_step         = 0
        self.done                 = False
        self.episode_id           = str(uuid.uuid4())[:8]
        self.acted_order_ids      = set()
        self.acted_disruption_ids = set()
        self.investigated_ids     = set()
        self.hidden_supplier_ids  = {"S_EU_03", "S_AM_03"}
        self.action_history       = []

        # Region stress tracking (unique to this task)
        self.region_reroute_count = {"asia": 0, "europe": 0, "americas": 0}
        self.cascade_fired        = {"asia": False, "europe": False, "americas": False}
        self.cascade_events       = []  # Log of cascade events for grading

        # ── 4 Initial Disruptions ───────────────────
        self.disruptions = [
            Disruption(
                id="D_EX_01",
                type="factory_fire",
                severity="critical",
                affected_supplier_id="S_AS_01",
                affected_supplier_name="TechParts Shanghai",
                estimated_duration_days=14,
                description=(
                    "Major factory fire at TechParts Shanghai. "
                    "All 3 orders sourced from this supplier are at risk. "
                    "Asian supply chain severely impacted."
                ),
            ),
            Disruption(
                id="D_EX_02",
                type="port_closure",
                severity="high",
                affected_supplier_id="S_EU_01",
                affected_supplier_name="EuroComponents GmbH",
                estimated_duration_days=10,
                description=(
                    "Rotterdam port closure due to labor strike. "
                    "European shipments delayed 10+ days. "
                    "2 orders affected."
                ),
            ),
            Disruption(
                id="D_EX_03",
                type="regulatory",
                severity="medium",
                affected_supplier_id="S_AM_01",
                affected_supplier_name="AmeriParts LLC",
                estimated_duration_days=7,
                description=(
                    "New customs regulations at US-Mexico border. "
                    "AmeriParts shipments require additional documentation. "
                    "1 order affected, delays expected."
                ),
            ),
            Disruption(
                id="D_EX_04",
                type="cyber_attack",
                severity="critical",
                affected_supplier_id="S_AS_02",
                affected_supplier_name="NipponTech Solutions",
                estimated_duration_days=12,
                description=(
                    "Ransomware attack on NipponTech's logistics systems. "
                    "All order tracking and shipment scheduling offline. "
                    "2 orders in limbo."
                ),
            ),
        ]

        # ── 10 Orders Across 3 Regions ───────────────
        self.orders = [
            # ASIA region (3 orders affected by D_EX_01)
            Order(id="O_EX_01", product="Semiconductor Chips (7nm)",
                  quantity=5000, value_usd=85000, priority="critical",
                  deadline_days=8, status="at_risk",
                  original_supplier_id="S_AS_01", current_supplier_id="S_AS_01",
                  region="asia"),
            Order(id="O_EX_02", product="PCB Assemblies",
                  quantity=3000, value_usd=42000, priority="high",
                  deadline_days=10, status="at_risk",
                  original_supplier_id="S_AS_01", current_supplier_id="S_AS_01",
                  region="asia"),
            Order(id="O_EX_03", product="Display Panels",
                  quantity=2000, value_usd=35000, priority="medium",
                  deadline_days=12, status="at_risk",
                  original_supplier_id="S_AS_02", current_supplier_id="S_AS_02",
                  region="asia"),

            # EUROPE region (2 orders affected by D_EX_02)
            Order(id="O_EX_04", product="Precision Motors",
                  quantity=1500, value_usd=65000, priority="critical",
                  deadline_days=9, status="at_risk",
                  original_supplier_id="S_EU_01", current_supplier_id="S_EU_01",
                  region="europe"),
            Order(id="O_EX_05", product="Battery Cells",
                  quantity=4000, value_usd=52000, priority="high",
                  deadline_days=11, status="at_risk",
                  original_supplier_id="S_EU_01", current_supplier_id="S_EU_01",
                  region="europe"),

            # AMERICAS region (1 order affected by D_EX_03)
            Order(id="O_EX_06", product="Steel Housings",
                  quantity=2500, value_usd=28000, priority="medium",
                  deadline_days=14, status="at_risk",
                  original_supplier_id="S_AM_01", current_supplier_id="S_AM_01",
                  region="americas"),

            # CROSS-REGION orders (affected by D_EX_04)
            Order(id="O_EX_07", product="Sensor Arrays",
                  quantity=6000, value_usd=78000, priority="critical",
                  deadline_days=7, status="at_risk",
                  original_supplier_id="S_AS_02", current_supplier_id="S_AS_02",
                  region="asia"),
            Order(id="O_EX_08", product="Control Boards",
                  quantity=1000, value_usd=22000, priority="low",
                  deadline_days=15, status="at_risk",
                  original_supplier_id="S_AS_02", current_supplier_id="S_AS_02",
                  region="asia"),

            # Not currently disrupted but at risk of cascade
            Order(id="O_EX_09", product="Power Supplies",
                  quantity=3500, value_usd=45000, priority="high",
                  deadline_days=10, status="active",
                  original_supplier_id="S_EU_02", current_supplier_id="S_EU_02",
                  region="europe"),
            Order(id="O_EX_10", product="Wiring Harnesses",
                  quantity=5000, value_usd=18000, priority="low",
                  deadline_days=20, status="active",
                  original_supplier_id="S_AM_02", current_supplier_id="S_AM_02",
                  region="americas"),
        ]

        # ── Available Suppliers (by region) ───────────
        self.available_suppliers = [
            # ASIA alternatives
            Supplier(id="S_AS_03", name="ShenZhen Quick Parts",
                     region="asia",
                     capacity_available=4000, lead_time_days=5,
                     cost_multiplier=1.15, reliability_score=0.88),
            Supplier(id="S_AS_04", name="Taiwan Precision Corp",
                     region="asia",
                     capacity_available=6000, lead_time_days=7,
                     cost_multiplier=1.25, reliability_score=0.92),

            # EUROPE alternatives
            Supplier(id="S_EU_02", name="Nordic Components AB",
                     region="europe",
                     capacity_available=3500, lead_time_days=6,
                     cost_multiplier=1.20, reliability_score=0.90),
            Supplier(id="S_EU_03", name="MediterraneanTech SRL",
                     region="europe",
                     capacity_available=5000, lead_time_days=8,
                     cost_multiplier=1.10, reliability_score=0.55),  # HIDDEN: unreliable

            # AMERICAS alternatives
            Supplier(id="S_AM_02", name="CanadaParts Inc",
                     region="americas",
                     capacity_available=4000, lead_time_days=4,
                     cost_multiplier=1.05, reliability_score=0.95),
            Supplier(id="S_AM_03", name="BrazilTech Ltda",
                     region="americas",
                     capacity_available=7000, lead_time_days=9,
                     cost_multiplier=1.30, reliability_score=0.45),  # HIDDEN: unreliable

            # CROSS-REGION (expensive but always available)
            Supplier(id="S_GLOBAL_01", name="GlobalExpress Logistics",
                     region="global",
                     capacity_available=10000, lead_time_days=3,
                     cost_multiplier=1.60, reliability_score=0.97),
        ]

        # ── Budget ────────────────────────────────────
        self.budget = Budget(
            total=55000.0,
            spent=0.0,
            remaining=55000.0,
            currency="USD"
        )

        self.metrics = Metrics()

        if seed:
            self._apply_seed_variation(seed)

        return self.get_observation()

    def _handle_reroute(self, action):
        """Override reroute to track region stress and trigger cascades."""
        supplier = self._get_supplier(action.new_supplier_id)

        # Track which region is receiving the reroute
        region = getattr(supplier, 'region', 'global')
        if region != 'global':
            self.region_reroute_count[region] = self.region_reroute_count.get(region, 0) + 1

        # Process the normal reroute
        reward = super()._handle_reroute(action)

        # Check for cascade trigger
        if (region != 'global' and
            self.region_reroute_count.get(region, 0) >= self.CASCADE_THRESHOLD and
            not self.cascade_fired.get(region, False)):
            self._trigger_cascade(region)
            reward.reason += (
                f" ⚠️ CASCADE TRIGGERED in {region.upper()}! "
                f"Region overloaded with {self.region_reroute_count[region]} reroutes. "
                f"All {region} suppliers now +30% cost, -2 days slower."
            )

        return reward

    def _trigger_cascade(self, region: str):
        """Apply cascade penalty to all suppliers in the affected region."""
        self.cascade_fired[region] = True
        cascade_event = {
            "region": region,
            "step": self.current_step,
            "description": f"Supply surge bottleneck in {region}. All {region} suppliers penalized."
        }
        self.cascade_events.append(cascade_event)

        # Penalize all suppliers in the region
        for supplier in self.available_suppliers:
            if getattr(supplier, 'region', 'global') == region:
                supplier.cost_multiplier = round(supplier.cost_multiplier * 1.30, 2)
                supplier.lead_time_days = max(1, supplier.lead_time_days + 2)

        # Add a new disruption to the list
        cascade_disruption = Disruption(
            id=f"D_CASCADE_{region.upper()}",
            type="supply_surge",
            severity="high",
            affected_supplier_id="MULTIPLE",
            affected_supplier_name=f"All {region.title()} suppliers",
            estimated_duration_days=5,
            description=(
                f"⚡ CASCADING DISRUPTION: Supply surge in {region.title()} region. "
                f"Too many orders rerouted to this region, causing bottleneck. "
                f"All {region} suppliers now operating at +30% cost and 2 extra days lead time."
            ),
        )
        self.disruptions.append(cascade_disruption)

    def get_final_score(self) -> float:
        """
        Expert scoring emphasizes:
          1. Revenue protected (weighted by priority)   → 0.30
          2. Cascade prevention (fewer cascades = better) → 0.20
          3. Budget adherence                             → 0.15
          4. Regional balance (spread across regions)     → 0.15
          5. Strategic investigation usage                → 0.10
          6. Efficiency (fewer steps = bonus)             → 0.10
        """
        if not self.has_resolution_action():
            return 0.001

        score = 0.0

        # 1. Revenue protected (priority-weighted)
        total_value = sum(o.value_usd for o in self.orders)
        priority_weights = {"critical": 2.0, "high": 1.5, "medium": 1.0, "low": 0.5}
        weighted_saved = 0.0
        weighted_total = 0.0
        for o in self.orders:
            w = priority_weights.get(o.priority, 1.0)
            weighted_total += o.value_usd * w
            if o.status == OrderStatus.FULFILLED:
                weighted_saved += o.value_usd * w
            elif o.status == OrderStatus.DELAYED:
                weighted_saved += o.value_usd * w * 0.5

        if weighted_total > 0:
            score += 0.30 * (weighted_saved / weighted_total)

        # 2. Cascade prevention (0 cascades = 0.20, 1 = 0.10, 2 = 0.05, 3 = 0)
        cascades_fired = sum(1 for v in self.cascade_fired.values() if v)
        cascade_scores = {0: 0.20, 1: 0.10, 2: 0.05, 3: 0.0}
        score += cascade_scores.get(cascades_fired, 0.0)

        # 3. Budget adherence
        if self.budget.remaining >= 0:
            remaining_ratio = self.budget.remaining / self.budget.total
            score += 0.15 * min(remaining_ratio * 2, 1.0)

        # 4. Regional balance (spread reroutes across regions)
        counts = [v for v in self.region_reroute_count.values() if v > 0]
        if len(counts) >= 2:
            max_count = max(counts)
            min_count = min(counts)
            balance = 1.0 - (max_count - min_count) / max(max_count, 1)
            score += 0.15 * balance
        elif len(counts) == 1:
            score += 0.05  # All eggs in one basket = low score

        # 5. Strategic investigation
        useful_investigations = len(self.investigated_ids & self.hidden_supplier_ids)
        if useful_investigations > 0:
            score += 0.10
        elif self.investigated_ids:
            score += 0.05

        # 6. Efficiency
        if self.done and self.current_step <= self.max_steps * 0.6:
            score += 0.10
        elif self.done and self.current_step <= self.max_steps * 0.8:
            score += 0.05

        score = round(min(max(score, 0.0), 1.0), 3)
        return max(0.001, min(score, 0.999))
