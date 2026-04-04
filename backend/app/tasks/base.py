# backend/app/tasks/base.py

from abc import ABC, abstractmethod
from typing import List
from ..models import (
    Observation, Action, Reward, State,
    Disruption, Order, Supplier, Budget, Metrics, OrderStatus,
    RewardBreakdown
)


class BaseTask(ABC):
    """
    Base class for all tasks.
    Every task (easy/medium/hard) inherits from this.
    """

    # ─────────────────────────────────────
    # These MUST be set in each child task
    # ─────────────────────────────────────
    task_id: str = ""
    task_name: str = ""
    task_difficulty: str = ""
    task_description: str = ""
    max_steps: int = 10

    def __init__(self):
        self.current_step: int = 0
        self.done: bool = False
        self.episode_id: str = ""

        # These get populated by child class reset()
        self.disruptions: List[Disruption] = []
        self.orders: List[Order] = []
        self.available_suppliers: List[Supplier] = []
        self.budget: Budget = None
        self.metrics: Metrics = Metrics()
        self.action_history: list = []

        # Track what orders were already acted on
        self.acted_order_ids: set = set()
        self.acted_disruption_ids: set = set()
        self.investigated_ids: set = set()
        self.hidden_supplier_ids: set = set()

    def has_resolution_action(self) -> bool:
        """Return True once the agent has taken an action that can affect grading."""
        return bool(self.acted_order_ids or self.acted_disruption_ids)

    # ─────────────────────────────────────
    # ABSTRACT — child must implement these
    # ─────────────────────────────────────

    @abstractmethod
    def reset(self) -> Observation:
        """Reset environment to initial state for this task"""
        pass

    @abstractmethod
    def get_final_score(self) -> float:
        """Calculate final score 0.0 to 1.0 when episode ends"""
        pass

    # ─────────────────────────────────────
    # SHARED LOGIC — used by all tasks
    # ─────────────────────────────────────

    def get_observation(self) -> Observation:
        """Build observation from current state"""
        return Observation(
            task_id=self.task_id,
            step=self.current_step,
            max_steps=self.max_steps,
            done=self.done,
            disruptions=self.disruptions,
            orders=self.orders,
            available_suppliers=self._get_visible_suppliers(),
            budget=self.budget,
            metrics=self.metrics,
            message=self._get_status_message()
        )

    def get_state(self) -> State:
        """Build full state from current environment"""
        from ..models.state import ActionRecord
        records = []
        for h in self.action_history:
            records.append(ActionRecord(
                step=h["step"],
                action_type=h["action_type"],
                action_summary=h["action_summary"],
                reward_received=h["reward_received"],
                was_valid=h["was_valid"]
            ))

        return State(
            task_id=self.task_id,
            task_name=self.task_name,
            task_difficulty=self.task_difficulty,
            step=self.current_step,
            max_steps=self.max_steps,
            done=self.done,
            episode_id=self.episode_id,
            disruptions=self.disruptions,
            orders=self.orders,
            available_suppliers=self.available_suppliers,
            budget=self.budget,
            metrics=self.metrics,
            action_history=records,
            final_score=self.get_final_score() if self.done else None,
            score_breakdown=self._get_score_breakdown() if self.done else None
        )

    def _get_visible_suppliers(self) -> List[Supplier]:
        """Return the supplier view exposed to the agent in observations."""
        visible_suppliers = []
        for supplier in self.available_suppliers:
            supplier_data = supplier.model_dump()
            if (
                supplier.id in self.hidden_supplier_ids and
                supplier.id not in self.investigated_ids
            ):
                supplier_data["reliability_score"] = None
                supplier_data["reliability_known"] = False
            else:
                supplier_data["reliability_known"] = True
            visible_suppliers.append(Supplier(**supplier_data))
        return visible_suppliers

    def step(self, action: Action) -> tuple:
        """
        Process one action.
        Returns: (observation, reward, done, info)
        """
        # Increment step
        self.current_step += 1

        # Check if already done
        if self.done:
            reward = self._make_reward(
                value=0.0,
                reason="Episode already finished.",
                action_valid=False,
                invalid_reason="Cannot act after episode is done."
            )
            return self.get_observation(), reward, True, {}

        # Validate action
        is_valid, invalid_reason = self._validate_action(action)

        if not is_valid:
            reward = self._make_reward(
                value=-0.05,
                reason=f"Invalid action: {invalid_reason}",
                action_valid=False,
                invalid_reason=invalid_reason
            )
            self._record_action(action, -0.05, False, invalid_reason)
            self.metrics.actions_taken += 1

            # Check episode end
            if self.current_step >= self.max_steps:
                self.done = True
                self._apply_terminal_rewards()

            obs = self.get_observation()
            return obs, reward, self.done, {"invalid_reason": invalid_reason}

        # Process valid action
        reward = self._process_action(action)

        # Record in history
        self._record_action(action, reward.value, True, "")
        self.metrics.actions_taken += 1

        # Update running score
        self._update_running_score()

        # Check episode end
        if self.current_step >= self.max_steps or self._all_resolved():
            self.done = True
            terminal_reward = self._apply_terminal_rewards()
            reward.value += terminal_reward
            reward.cumulative_score = self.get_final_score()

        obs = self.get_observation()
        return obs, reward, self.done, {}

    def _process_action(self, action: Action) -> Reward:
        """Route action to correct handler"""
        action_type = action.action_type

        if action_type == "reroute":
            return self._handle_reroute(action)
        elif action_type == "substitute":
            return self._handle_substitute(action)
        elif action_type == "delay":
            return self._handle_delay(action)
        elif action_type == "cancel":
            return self._handle_cancel(action)
        elif action_type == "escalate":
            return self._handle_escalate(action)
        elif action_type == "investigate":
            return self._handle_investigate(action)
        else:
            return self._make_reward(
                value=-0.05,
                reason="Unknown action type.",
                action_valid=False,
                invalid_reason="Unrecognized action_type"
            )

    # ─────────────────────────────────────
    # ACTION HANDLERS
    # ─────────────────────────────────────

    def _handle_reroute(self, action: Action) -> Reward:
        """Handle reroute action — move order to new supplier"""
        order = self._get_order(action.order_id)
        supplier = self._get_supplier(action.new_supplier_id)
        breakdown = RewardBreakdown()

        # Already acted on this order?
        if action.order_id in self.acted_order_ids:
            breakdown.redundant_action_penalty = -0.05
            return self._make_reward(
                value=-0.05,
                reason=f"Order {action.order_id} already handled. Redundant action.",
                breakdown=breakdown
            )

        # Can supplier handle the quantity?
        if supplier.capacity_available < order.quantity:
            breakdown.redundant_action_penalty = -0.05
            return self._make_reward(
                value=-0.05,
                reason=f"{supplier.name} does not have enough capacity for order {action.order_id}.",
                breakdown=breakdown
            )

        # Will it arrive in time?
        on_time = supplier.lead_time_days <= order.deadline_days

        # Is supplier reliable?
        reliable = supplier.reliability_score >= 0.75

        # Calculate extra cost
        extra_cost = order.value_usd * (supplier.cost_multiplier - 1.0)
        extra_cost = max(0.0, extra_cost)

        # Check budget
        if self.budget.remaining < extra_cost:
            breakdown.budget_exceeded_penalty = -0.10
            return self._make_reward(
                value=-0.10,
                reason=f"Insufficient budget to reroute to {supplier.name}. Need ${extra_cost:,.0f} more.",
                breakdown=breakdown
            )

        # Apply the reroute
        order.current_supplier_id = supplier.id
        order.status = OrderStatus.FULFILLED if on_time else OrderStatus.DELAYED
        supplier.capacity_available -= order.quantity
        self.budget.spent += extra_cost
        self.budget.remaining -= extra_cost
        self.acted_order_ids.add(action.order_id)

        # Calculate reward
        reward_value = 0.0

        if on_time:
            breakdown.orders_saved_reward = 0.15
            breakdown.deadline_met_reward = 0.10
            reward_value += 0.25
            self.metrics.orders_saved += 1
            self.metrics.revenue_protected += order.value_usd
            reason = (
                f"✅ Order {action.order_id} successfully rerouted to "
                f"{supplier.name}. Will arrive in {supplier.lead_time_days} days "
                f"(deadline: {order.deadline_days} days). Extra cost: ${extra_cost:,.0f}"
            )
        else:
            breakdown.orders_saved_reward = 0.05
            breakdown.missed_deadline_penalty = -0.10
            reward_value += -0.05
            self.metrics.orders_delayed += 1
            reason = (
                f"⚠️ Order {action.order_id} rerouted to {supplier.name} "
                f"but will MISS deadline. Lead time {supplier.lead_time_days} days "
                f"> deadline {order.deadline_days} days."
            )

        if not reliable:
            breakdown.bad_supplier_penalty = -0.05
            reward_value -= 0.05
            reason += f" ⚠️ Warning: {supplier.name} has low reliability ({supplier.reliability_score})."

        if reliable and on_time and supplier.cost_multiplier <= 1.2:
            breakdown.good_supplier_choice_reward = 0.05
            reward_value += 0.05
            reason += " 💰 Good cost-efficient choice!"

        return self._make_reward(
            value=round(reward_value, 3),
            reason=reason,
            breakdown=breakdown
        )

    def _handle_substitute(self, action: Action) -> Reward:
        """Handle substitute action — replace product"""
        order = self._get_order(action.order_id)
        breakdown = RewardBreakdown()

        if action.order_id in self.acted_order_ids:
            breakdown.redundant_action_penalty = -0.05
            return self._make_reward(
                value=-0.05,
                reason=f"Order {action.order_id} already handled.",
                breakdown=breakdown
            )

        if not action.alternative_product:
            return self._make_reward(
                value=-0.05,
                reason="Substitute action requires alternative_product field.",
                action_valid=False,
                invalid_reason="Missing alternative_product"
            )

        # Substitute is partial value recovery
        order.product = action.alternative_product
        order.status = OrderStatus.FULFILLED
        order.value_usd = order.value_usd * 0.80  # 80% value (customer accepts sub)
        self.acted_order_ids.add(action.order_id)

        breakdown.orders_saved_reward = 0.10
        self.metrics.orders_saved += 1
        self.metrics.revenue_protected += order.value_usd

        reason = (
            f"🔄 Order {action.order_id} substituted with '{action.alternative_product}'. "
            f"Partial value recovered (80%). Customer notified: {action.notify_customer}."
        )

        return self._make_reward(
            value=0.10,
            reason=reason,
            breakdown=breakdown
        )

    def _handle_delay(self, action: Action) -> Reward:
        """Handle delay action — push deadline"""
        order = self._get_order(action.order_id)
        breakdown = RewardBreakdown()

        if action.order_id in self.acted_order_ids:
            breakdown.redundant_action_penalty = -0.05
            return self._make_reward(
                value=-0.05,
                reason=f"Order {action.order_id} already handled.",
                breakdown=breakdown
            )

        if not action.delay_days or action.delay_days <= 0:
            return self._make_reward(
                value=-0.05,
                reason="Delay action requires delay_days > 0.",
                action_valid=False,
                invalid_reason="Missing or invalid delay_days"
            )

        # Delay is always a partial loss — customer unhappy
        order.deadline_days += action.delay_days
        order.status = OrderStatus.DELAYED
        self.acted_order_ids.add(action.order_id)

        breakdown.orders_saved_reward = 0.05
        breakdown.missed_deadline_penalty = -0.05
        self.metrics.orders_delayed += 1
        self.metrics.revenue_protected += order.value_usd * 0.60

        reason = (
            f"⏰ Order {action.order_id} delayed by {action.delay_days} days. "
            f"New deadline: {order.deadline_days} days. "
            f"Partial revenue retained (60%). Reason: {action.reason or 'Supply disruption'}."
        )

        return self._make_reward(
            value=0.0,
            reason=reason,
            breakdown=breakdown
        )

    def _handle_cancel(self, action: Action) -> Reward:
        """Handle cancel action — lose the order"""
        order = self._get_order(action.order_id)
        breakdown = RewardBreakdown()

        if action.order_id in self.acted_order_ids:
            breakdown.redundant_action_penalty = -0.05
            return self._make_reward(
                value=-0.05,
                reason=f"Order {action.order_id} already handled.",
                breakdown=breakdown
            )

        order.status = OrderStatus.LOST
        self.acted_order_ids.add(action.order_id)

        breakdown.order_lost_penalty = -0.15
        self.metrics.orders_lost += 1
        self.metrics.revenue_lost += order.value_usd

        reason = (
            f"❌ Order {action.order_id} cancelled. "
            f"Lost ${order.value_usd:,.0f} in revenue. "
            f"Reason: {action.reason or 'No reason provided'}."
        )

        return self._make_reward(
            value=-0.15,
            reason=reason,
            breakdown=breakdown
        )

    def _handle_escalate(self, action: Action) -> Reward:
        """Handle escalate action — flag disruption to management"""
        disruption = self._get_disruption(action.disruption_id)
        breakdown = RewardBreakdown()

        if action.disruption_id in self.acted_disruption_ids:
            breakdown.redundant_action_penalty = -0.05
            return self._make_reward(
                value=-0.05,
                reason=f"Disruption {action.disruption_id} already escalated.",
                breakdown=breakdown
            )

        # Good escalation = critical disruption escalated at high/critical priority
        correct_priority = (
            disruption.severity in ["critical", "high"] and
            action.escalation_priority in ["critical", "high"]
        )

        self.acted_disruption_ids.add(action.disruption_id)

        if correct_priority:
            breakdown.escalation_reward = 0.08
            reason = (
                f"🚨 Disruption {action.disruption_id} correctly escalated "
                f"at {action.escalation_priority} priority. "
                f"Management alerted."
            )
            return self._make_reward(value=0.08, reason=reason, breakdown=breakdown)
        else:
            breakdown.escalation_reward = 0.02
            reason = (
                f"📋 Disruption {action.disruption_id} escalated "
                f"at {action.escalation_priority} priority. "
                f"Consider severity level for better escalation."
            )
            return self._make_reward(value=0.02, reason=reason, breakdown=breakdown)

    def _handle_investigate(self, action: Action) -> Reward:
        """Handle investigate action — gather more info"""
        breakdown = RewardBreakdown()

        if action.target_id in self.investigated_ids:
            breakdown.redundant_action_penalty = -0.05
            return self._make_reward(
                value=-0.05,
                reason=f"Target {action.target_id} already investigated.",
                breakdown=breakdown
            )

        self.investigated_ids.add(action.target_id)
        breakdown.investigation_reward = 0.05

        # Find what was investigated
        supplier = next(
            (s for s in self.available_suppliers if s.id == action.target_id),
            None
        )
        disruption = next(
            (d for d in self.disruptions if d.id == action.target_id),
            None
        )

        if supplier:
            reason = (
                f"🔍 Investigated {supplier.name}: "
                f"Reliability={supplier.reliability_score}, "
                f"Lead time={supplier.lead_time_days} days, "
                f"Cost multiplier={supplier.cost_multiplier}x, "
                f"Capacity={supplier.capacity_available:,} units available."
            )
        elif disruption:
            reason = (
                f"🔍 Investigated disruption {action.target_id}: "
                f"Type={disruption.type}, "
                f"Severity={disruption.severity}, "
                f"Duration={disruption.estimated_duration_days} days. "
                f"{disruption.description}"
            )
        else:
            reason = f"🔍 Investigated {action.target_id}. No additional info found."

        return self._make_reward(value=0.05, reason=reason, breakdown=breakdown)

    # ─────────────────────────────────────
    # HELPER METHODS
    # ─────────────────────────────────────

    def _get_order(self, order_id: str) -> Order:
        for o in self.orders:
            if o.id == order_id:
                return o
        raise ValueError(f"Order {order_id} not found")

    def _get_supplier(self, supplier_id: str) -> Supplier:
        for s in self.available_suppliers:
            if s.id == supplier_id:
                return s
        raise ValueError(f"Supplier {supplier_id} not found")

    def _get_disruption(self, disruption_id: str) -> Disruption:
        for d in self.disruptions:
            if d.id == disruption_id:
                return d
        raise ValueError(f"Disruption {disruption_id} not found")

    def _validate_action(self, action: Action) -> tuple:
        """Validate action before processing. Returns (is_valid, reason)"""
        try:
            if action.action_type in ["reroute", "substitute", "delay", "cancel"]:
                if not action.order_id:
                    return False, "order_id is required for this action"
                order_ids = [o.id for o in self.orders]
                if action.order_id not in order_ids:
                    return False, f"Order {action.order_id} does not exist"

            if action.action_type == "reroute":
                if not action.new_supplier_id:
                    return False, "new_supplier_id is required for reroute"
                supplier_ids = [s.id for s in self.available_suppliers]
                if action.new_supplier_id not in supplier_ids:
                    return False, f"Supplier {action.new_supplier_id} does not exist"

            if action.action_type in ["escalate"]:
                if not action.disruption_id:
                    return False, "disruption_id is required for escalate"
                disruption_ids = [d.id for d in self.disruptions]
                if action.disruption_id not in disruption_ids:
                    return False, f"Disruption {action.disruption_id} does not exist"

            if action.action_type == "investigate":
                if not action.target_id:
                    return False, "target_id is required for investigate"

            return True, ""

        except Exception as e:
            return False, str(e)

    def _all_resolved(self) -> bool:
        """Check if all orders have been acted on"""
        return all(
            o.status in [OrderStatus.FULFILLED, OrderStatus.LOST, OrderStatus.DELAYED]
            for o in self.orders
        )

    def _apply_terminal_rewards(self) -> float:
        """Apply end-of-episode bonus/penalty rewards"""
        terminal = 0.0

        # Bonus: all high-value orders saved
        high_value_orders = [o for o in self.orders if o.priority == "high"]
        saved_high = [
            o for o in high_value_orders
            if o.status == OrderStatus.FULFILLED
        ]
        if len(high_value_orders) > 0:
            ratio = len(saved_high) / len(high_value_orders)
            if ratio == 1.0:
                terminal += 0.20
            elif ratio >= 0.5:
                terminal += 0.10

        # Bonus: finished under budget
        if self.budget.remaining > 0:
            terminal += 0.10

        # Bonus: finished early
        if self.current_step < self.max_steps * 0.75:
            terminal += 0.05

        # Penalty: more than half orders lost
        total = len(self.orders)
        lost = self.metrics.orders_lost
        if total > 0 and lost / total > 0.5:
            terminal -= 0.20

        return round(terminal, 3)

    def _update_running_score(self):
        """Update the running score in metrics"""
        self.metrics.current_score = round(
            self.get_final_score(), 3
        )

    def _get_status_message(self) -> str:
        """Generate a human-readable status message"""
        active_disruptions = [d for d in self.disruptions if not d.is_resolved]
        at_risk_orders = [o for o in self.orders if o.status == "at_risk"]
        hidden_suppliers_remaining = len(
            [
                supplier_id for supplier_id in self.hidden_supplier_ids
                if supplier_id not in self.investigated_ids
            ]
        )

        if self.done:
            return (
                f"Episode complete. Final score: {self.metrics.current_score:.2f}. "
                f"Orders saved: {self.metrics.orders_saved}, "
                f"Lost: {self.metrics.orders_lost}."
            )

        message = (
            f"Step {self.current_step}/{self.max_steps}. "
            f"Active disruptions: {len(active_disruptions)}. "
            f"Orders at risk: {len(at_risk_orders)}. "
            f"Budget remaining: ${self.budget.remaining:,.0f}."
        )

        if self.task_id == "task_hard":
            message += (
                " Hard-task guidance: budget is severely constrained; escalate critical disruptions "
                "(especially D002, D005, D006) and investigate hidden-risk suppliers before rerouting."
            )
            if hidden_suppliers_remaining > 0:
                message += f" Hidden supplier-risk checks remaining: {hidden_suppliers_remaining}."

        return message

    def _get_score_breakdown(self) -> dict:
        """Return score breakdown as dict"""
        total = len(self.orders)
        score_breakdown = {
            "orders_saved": self.metrics.orders_saved,
            "orders_lost": self.metrics.orders_lost,
            "orders_delayed": self.metrics.orders_delayed,
            "revenue_protected": self.metrics.revenue_protected,
            "revenue_lost": self.metrics.revenue_lost,
            "budget_used": self.budget.spent,
            "budget_remaining": self.budget.remaining,
            "steps_used": self.current_step,
            "valid_action_count": sum(1 for record in self.action_history if record["was_valid"]),
            "invalid_action_count": sum(1 for record in self.action_history if not record["was_valid"]),
            "investigation_count": sum(
                1 for record in self.action_history if record["action_type"] == "investigate"
            ),
            "escalation_count": sum(
                1 for record in self.action_history if record["action_type"] == "escalate"
            ),
            "final_score": self.get_final_score(),
            "completion_rate": round(
                (self.metrics.orders_saved + self.metrics.orders_delayed) / total, 2
            ) if total > 0 else 0.0
        }

        if self.hidden_supplier_ids:
            hidden_used = [
                order.id
                for order in self.orders
                if order.current_supplier_id in self.hidden_supplier_ids
            ]
            score_breakdown.update({
                "hidden_risk_suppliers_total": len(self.hidden_supplier_ids),
                "hidden_risk_suppliers_investigated": len(
                    self.hidden_supplier_ids & self.investigated_ids
                ),
                "hidden_risk_suppliers_remaining": len(
                    self.hidden_supplier_ids - self.investigated_ids
                ),
                "hidden_risk_supplier_orders": hidden_used,
                "hidden_risk_supplier_used": bool(hidden_used),
            })

        return score_breakdown

    def _make_reward(
        self,
        value: float,
        reason: str,
        breakdown: RewardBreakdown = None,
        action_valid: bool = True,
        invalid_reason: str = None
    ) -> Reward:
        """Helper to build Reward object"""
        from ..models import Reward
        return Reward(
            value=round(value, 3),
            cumulative_score=round(self.metrics.current_score, 3),
            breakdown=breakdown or RewardBreakdown(),
            reason=reason,
            action_valid=action_valid,
            invalid_reason=invalid_reason
        )

    def _record_action(
        self,
        action: Action,
        reward_value: float,
        was_valid: bool,
        note: str
    ):
        """Record action in history"""
        summary = f"{action.action_type}"
        if action.order_id:
            summary += f" on order {action.order_id}"
        if action.new_supplier_id:
            summary += f" → supplier {action.new_supplier_id}"
        if action.disruption_id:
            summary += f" on disruption {action.disruption_id}"
        if note:
            summary += f" ({note})"

        self.action_history.append({
            "step": self.current_step,
            "action_type": action.action_type,
            "action_summary": summary,
            "reward_received": reward_value,
            "was_valid": was_valid
        })
