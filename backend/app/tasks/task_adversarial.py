# backend/app/tasks/task_adversarial.py

import uuid
from .base import BaseTask
from ..models import Observation, Budget, Metrics, Disruption, Order, Supplier, OrderStatus
from ..models.reward import Reward, RewardBreakdown


class TaskAdversarial(BaseTask):
    """
    TASK 5 — Supplier Trap Detection (ADVERSARIAL)

    Scenario:
        6 orders with varying priorities and values.
        8 suppliers available, but 3 are TRAPS:
          - They look great on paper (low cost, high capacity)
          - But have hidden fatal flaws only discoverable through investigation
          - If agent reroutes to a trap WITHOUT investigating first:
            → The order appears fulfilled initially
            → But 2 steps later, the order FAILS silently (status → at_risk again)
            → Agent must fix it again using remaining budget
          - If agent investigates first: trap is revealed, agent avoids it

    Unique Mechanics:
        - trap_suppliers: 3 suppliers that look excellent but fail after reroute
        - delayed_failures: orders rerouted to traps fail after 2 steps
        - trust_but_verify: investigating a trap reveals the issue, letting agent avoid it
        - double_cost: fixing a trap-failed order costs 50% more (emergency premium)

    What agent must do:
        - Investigate suspicious suppliers before committing orders.
        - Identify which suppliers are trustworthy vs traps.
        - Manage budget carefully — trap failures drain resources fast.
        - Prioritize high-value orders for reliable suppliers.

    Expected score for good agent: 0.40 - 0.70
    """

    task_id         = "task_adversarial"
    task_name       = "Supplier Trap Detection"
    task_difficulty  = "adversarial"
    task_description = (
        "Six critical orders need rerouting, but three of the eight available "
        "suppliers are traps — they look ideal on paper but will fail after "
        "accepting your orders. Only investigation can reveal the truth. "
        "A greedy agent that skips investigation will lose orders and budget. "
        "A careful, methodical agent that verifies before trusting will excel."
    )
    max_steps = 20

    # Track delayed failures
    TRAP_FAILURE_DELAY = 2  # Steps until trap supplier fails

    def reset(self, seed=None) -> Observation:
        self.current_step         = 0
        self.done                 = False
        self.episode_id           = str(uuid.uuid4())[:8]
        self.acted_order_ids      = set()
        self.acted_disruption_ids = set()
        self.investigated_ids     = set()
        self.hidden_supplier_ids  = {"S_TRAP_01", "S_TRAP_02", "S_TRAP_03"}
        self.action_history       = []

        # Adversarial tracking
        self.trap_supplier_ids    = {"S_TRAP_01", "S_TRAP_02", "S_TRAP_03"}
        self.trap_revealed_ids    = set()  # Traps that have been investigated
        self.pending_failures     = []  # (order_id, fail_at_step)
        self.trap_failures_count  = 0
        self.traps_avoided_count  = 0

        # ── 3 Disruptions ──────────────────────────────
        self.disruptions = [
            Disruption(
                id="D_ADV_01",
                type="bankruptcy",
                severity="critical",
                affected_supplier_id="S_DEAD_01",
                affected_supplier_name="QuickShip Corp",
                estimated_duration_days=999,
                description=(
                    "QuickShip Corp has filed for bankruptcy. "
                    "All 3 orders sourced from them are stranded. "
                    "Must find alternative suppliers immediately."
                ),
            ),
            Disruption(
                id="D_ADV_02",
                type="quality_recall",
                severity="high",
                affected_supplier_id="S_DEAD_02",
                affected_supplier_name="ValueParts Co",
                estimated_duration_days=21,
                description=(
                    "ValueParts Co issued a product quality recall. "
                    "2 orders affected. Products must be resourced "
                    "from inspected suppliers."
                ),
            ),
            Disruption(
                id="D_ADV_03",
                type="embargo",
                severity="high",
                affected_supplier_id="S_DEAD_03",
                affected_supplier_name="TradeWind Logistics",
                estimated_duration_days=30,
                description=(
                    "Trade embargo affects TradeWind Logistics. "
                    "1 order affected. Must find compliant alternative."
                ),
            ),
        ]

        # ── 6 Orders ──────────────────────────────────
        self.orders = [
            # From QuickShip Corp (bankrupted)
            Order(id="O_ADV_01", product="Medical Devices",
                  quantity=2000, value_usd=120000, priority="critical",
                  deadline_days=6, status="at_risk",
                  original_supplier_id="S_DEAD_01", current_supplier_id="S_DEAD_01"),
            Order(id="O_ADV_02", product="Pharmaceutical Ingredients",
                  quantity=5000, value_usd=95000, priority="critical",
                  deadline_days=8, status="at_risk",
                  original_supplier_id="S_DEAD_01", current_supplier_id="S_DEAD_01"),
            Order(id="O_ADV_03", product="Lab Equipment",
                  quantity=800, value_usd=45000, priority="high",
                  deadline_days=10, status="at_risk",
                  original_supplier_id="S_DEAD_01", current_supplier_id="S_DEAD_01"),

            # From ValueParts Co (quality recall)
            Order(id="O_ADV_04", product="Safety Components",
                  quantity=3000, value_usd=68000, priority="high",
                  deadline_days=9, status="at_risk",
                  original_supplier_id="S_DEAD_02", current_supplier_id="S_DEAD_02"),
            Order(id="O_ADV_05", product="Testing Kits",
                  quantity=1500, value_usd=32000, priority="medium",
                  deadline_days=12, status="at_risk",
                  original_supplier_id="S_DEAD_02", current_supplier_id="S_DEAD_02"),

            # From TradeWind Logistics (embargo)
            Order(id="O_ADV_06", product="Electronic Assemblies",
                  quantity=4000, value_usd=55000, priority="medium",
                  deadline_days=14, status="at_risk",
                  original_supplier_id="S_DEAD_03", current_supplier_id="S_DEAD_03"),
        ]

        # ── 8 Available Suppliers (3 are TRAPS) ────────
        self.available_suppliers = [
            # ═══ TRAP SUPPLIERS ═══
            # Look amazing on paper but will FAIL after reroute
            Supplier(id="S_TRAP_01", name="FastTrack Global",
                     capacity_available=8000, lead_time_days=3,
                     cost_multiplier=0.90,  # Suspiciously cheap!
                     reliability_score=0.30),  # Hidden: terrible reliability
            Supplier(id="S_TRAP_02", name="BudgetSupply Direct",
                     capacity_available=10000, lead_time_days=4,
                     cost_multiplier=0.85,  # Even cheaper!
                     reliability_score=0.25),  # Hidden: even worse
            Supplier(id="S_TRAP_03", name="ExpressLine Solutions",
                     capacity_available=6000, lead_time_days=2,
                     cost_multiplier=0.95,  # Cheap with fastest delivery!
                     reliability_score=0.20),  # Hidden: worst reliability

            # ═══ RELIABLE SUPPLIERS ═══
            Supplier(id="S_SAFE_01", name="MedGrade Certified",
                     capacity_available=3000, lead_time_days=5,
                     cost_multiplier=1.25,
                     reliability_score=0.96),
            Supplier(id="S_SAFE_02", name="PharmaPartners AG",
                     capacity_available=5000, lead_time_days=6,
                     cost_multiplier=1.35,
                     reliability_score=0.94),
            Supplier(id="S_SAFE_03", name="QualityFirst Ltd",
                     capacity_available=4000, lead_time_days=7,
                     cost_multiplier=1.20,
                     reliability_score=0.91),
            Supplier(id="S_SAFE_04", name="TrustChain Supply",
                     capacity_available=2500, lead_time_days=4,
                     cost_multiplier=1.40,
                     reliability_score=0.98),
            Supplier(id="S_SAFE_05", name="VerifiedSource Inc",
                     capacity_available=6000, lead_time_days=8,
                     cost_multiplier=1.15,
                     reliability_score=0.89),
        ]

        # ── Budget ────────────────────────────────────
        self.budget = Budget(
            total=85000.0,
            spent=0.0,
            remaining=85000.0,
            currency="USD"
        )

        self.metrics = Metrics()

        if seed:
            self._apply_seed_variation(seed)

        return self.get_observation()

    def step(self, action):
        """Override step to check for delayed trap failures."""
        # First, check if any pending trap failures should fire NOW
        self._process_pending_failures()

        # Then process the action normally
        return super().step(action)

    def _process_pending_failures(self):
        """Check if any trap-rerouted orders should fail this step."""
        still_pending = []
        for order_id, fail_at_step in self.pending_failures:
            if self.current_step >= fail_at_step:
                # TRAP FAILURE: order reverts to at_risk
                order = self._get_order(order_id)
                if order and order.status == OrderStatus.FULFILLED:
                    order.status = OrderStatus.AT_RISK
                    self.acted_order_ids.discard(order_id)
                    self.trap_failures_count += 1
                    self.metrics.orders_saved = max(0, self.metrics.orders_saved - 1)

                    # Add a new disruption describing the failure
                    fail_disruption = Disruption(
                        id=f"D_TRAP_FAIL_{order_id}",
                        type="supplier_failure",
                        severity="critical",
                        affected_supplier_id="TRAP",
                        affected_supplier_name="Unreliable Supplier",
                        estimated_duration_days=0,
                        description=(
                            f"💀 TRAP FAILURE: Order {order_id} was rerouted to an "
                            f"unverified supplier that failed to deliver. "
                            f"Order is back at risk. Emergency re-routing required "
                            f"at 50% premium cost."
                        ),
                    )
                    self.disruptions.append(fail_disruption)
            else:
                still_pending.append((order_id, fail_at_step))
        self.pending_failures = still_pending

    def _handle_reroute(self, action):
        """Override reroute to implement trap mechanics."""
        supplier = self._get_supplier(action.new_supplier_id)

        # Check if routing to a trap supplier without investigating
        is_trap = action.new_supplier_id in self.trap_supplier_ids
        trap_revealed = action.new_supplier_id in self.trap_revealed_ids

        if is_trap and not trap_revealed:
            # Agent didn't investigate — trap will fire after delay
            reward = super()._handle_reroute(action)
            if reward.value > 0:  # Reroute was "successful" (for now)
                # Schedule delayed failure
                fail_at = self.current_step + self.TRAP_FAILURE_DELAY
                self.pending_failures.append((action.order_id, fail_at))
                reward.reason += (
                    " ⚠️ NOTE: This supplier was NOT investigated before routing. "
                    "Proceed with caution."
                )
            return reward
        elif is_trap and trap_revealed:
            # Agent investigated and knows it's a trap — should avoid!
            # Let them do it anyway (maybe they have no choice)
            self.traps_avoided_count -= 1  # They chose a known-bad supplier
            reward = super()._handle_reroute(action)
            if reward.value > 0:
                fail_at = self.current_step + self.TRAP_FAILURE_DELAY
                self.pending_failures.append((action.order_id, fail_at))
                reward.reason += (
                    " ❌ WARNING: You routed to a KNOWN unreliable supplier! "
                    "This order WILL fail in 2 steps."
                )
            return reward
        else:
            # Safe supplier — normal handling
            return super()._handle_reroute(action)

    def _handle_investigate(self, action):
        """Override investigate to reveal traps."""
        if action.target_id in self.trap_supplier_ids and action.target_id not in self.trap_revealed_ids:
            self.trap_revealed_ids.add(action.target_id)
            self.traps_avoided_count += 1

        return super()._handle_investigate(action)

    def get_final_score(self) -> float:
        """
        Adversarial scoring emphasizes:
          1. Revenue protected (final state)            → 0.25
          2. Trap avoidance (investigated before routing) → 0.25
          3. Zero trap failures (clean execution)        → 0.20
          4. Budget efficiency                           → 0.15
          5. Strategic investigation usage                → 0.10
          6. Efficiency (fewer steps)                     → 0.05
        """
        if not self.has_resolution_action():
            return 0.001

        score = 0.0

        # 1. Revenue protected (final state — after trap failures resolve)
        total_value = sum(o.value_usd for o in self.orders)
        protected = sum(
            o.value_usd for o in self.orders
            if o.status in [OrderStatus.FULFILLED, OrderStatus.DELAYED]
        )
        if total_value > 0:
            ratio = protected / total_value
            score += 0.25 * ratio

        # 2. Trap avoidance (how many traps were investigated before any routing attempt)
        traps_total = len(self.trap_supplier_ids)
        traps_found = len(self.trap_revealed_ids)
        if traps_total > 0:
            score += 0.25 * (traps_found / traps_total)

        # 3. Zero trap failures bonus
        if self.trap_failures_count == 0:
            score += 0.20  # Perfect — no orders lost to traps
        elif self.trap_failures_count == 1:
            score += 0.10  # One mistake
        elif self.trap_failures_count == 2:
            score += 0.05  # Two mistakes

        # 4. Budget efficiency
        if self.budget.remaining >= 0:
            remaining_ratio = self.budget.remaining / self.budget.total
            score += 0.15 * min(remaining_ratio * 2, 1.0)

        # 5. Strategic investigation
        if len(self.investigated_ids) >= 3:
            score += 0.10  # Thorough investigation
        elif len(self.investigated_ids) >= 1:
            score += 0.05

        # 6. Efficiency
        if self.done and self.current_step <= self.max_steps * 0.6:
            score += 0.05
        elif self.done and self.current_step <= self.max_steps * 0.8:
            score += 0.025

        score = round(min(max(score, 0.0), 1.0), 3)
        return max(0.001, min(score, 0.999))
