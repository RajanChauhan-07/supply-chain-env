# backend/app/graders/grader.py

from .base import BaseGrader
from ..tasks.base import BaseTask
from ..tasks import TASK_REGISTRY
from ..models import OrderStatus


class EasyGrader(BaseGrader):
    """
    Grader for Task Easy — Single Lane Disruption.

    Criteria:
        1. Was the order fulfilled on time?     → 0.50
        2. Was budget respected?                → 0.20
        3. Was the best supplier chosen?        → 0.20
        4. Was episode completed efficiently?   → 0.10

    Passing threshold: 0.60
    """

    task_id = "task_easy"
    PASS_THRESHOLD = 0.60

    def grade(self) -> dict:
        task   = self.task
        order  = task.orders[0] if task.orders else None
        score  = 0.0
        breakdown = {
            "order_fulfilled": 0.0,
            "budget_respected": 0.0,
            "supplier_choice": 0.0,
            "efficiency": 0.0,
        }

        if not task.has_resolution_action():
            return {
                "task_id": self.task_id,
                "score": 0.001,
                "breakdown": breakdown,
                "passed": False,
                "summary": self._build_summary(0.0, breakdown, order, task),
            }

        # ── 1. Order fulfilled on time? ────────────
        if order and order.status == OrderStatus.FULFILLED:
            breakdown["order_fulfilled"] = 0.50
            score += 0.50
        elif order and order.status == OrderStatus.DELAYED:
            breakdown["order_fulfilled"] = 0.15
            score += 0.15

        # ── 2. Budget respected? ───────────────────
        if task.budget.remaining >= 0 and task.budget.spent > 0:
            breakdown["budget_respected"] = 0.20
            score += 0.20

        # ── 3. Best supplier chosen? ───────────────
        if order and order.current_supplier_id == "S004":
            # Best: on time, cheapest valid option
            breakdown["supplier_choice"] = 0.20
            score += 0.20
        elif order and order.current_supplier_id == "S006":
            # Valid but expensive
            breakdown["supplier_choice"] = 0.10
            score += 0.10

        # ── 4. Efficiency bonus ────────────────────
        if task.done and order and order.status == OrderStatus.FULFILLED and task.current_step <= task.max_steps * 0.5:
            breakdown["efficiency"] = 0.10
            score += 0.10
        elif task.done and order and order.status in [OrderStatus.FULFILLED, OrderStatus.DELAYED] and task.current_step <= task.max_steps * 0.75:
            breakdown["efficiency"] = 0.05
            score += 0.05

        final_score = self._clamp(score)

        return {
            "task_id":   self.task_id,
            "score":     final_score,
            "breakdown": breakdown,
            "passed":    final_score >= self.PASS_THRESHOLD,
            "summary":   self._build_summary(final_score, breakdown, order, task)
        }

    def _build_summary(self, score, breakdown, order, task) -> str:
        lines = [
            f"=== EASY TASK GRADER REPORT ===",
            f"Task       : {task.task_name}",
            f"Steps used : {task.current_step} / {task.max_steps}",
            f"",
            f"SCORE BREAKDOWN:",
            f"  Order fulfilled  : {breakdown.get('order_fulfilled', 0):.2f} / 0.50",
            f"  Budget respected : {breakdown.get('budget_respected', 0):.2f} / 0.20",
            f"  Supplier choice  : {breakdown.get('supplier_choice', 0):.2f} / 0.20",
            f"  Efficiency       : {breakdown.get('efficiency', 0):.2f} / 0.10",
            f"",
            f"FINAL SCORE : {score:.3f}",
            f"PASSED      : {'✅ YES' if score >= self.PASS_THRESHOLD else '❌ NO'}",
            f"",
            f"ORDER STATUS:",
            f"  {order.id if order else 'N/A'} → {order.status if order else 'N/A'}",
            f"  Supplier : {order.current_supplier_id if order else 'N/A'}",
            f"  Revenue protected : ${task.metrics.revenue_protected:,.0f}",
            f"  Budget spent      : ${task.budget.spent:,.0f} / ${task.budget.total:,.0f}",
        ]
        return "\n".join(lines)


class MediumGrader(BaseGrader):
    """
    Grader for Task Medium — Multi-Point Failure.

    Criteria:
        1. High-value orders saved ratio    → 0.40
        2. Total revenue protected %        → 0.30
        3. Budget adherence                 → 0.20
        4. Correct prioritization (O003)    → 0.10

    Passing threshold: 0.45
    """

    task_id = "task_medium"
    PASS_THRESHOLD = 0.45

    def grade(self) -> dict:
        task  = self.task
        score = 0.0
        breakdown = {
            "high_value_orders_saved": 0.0,
            "revenue_protected": 0.0,
            "budget_adherence": 0.0,
            "prioritization_bonus": 0.0,
        }

        if not task.has_resolution_action():
            return {
                "task_id": self.task_id,
                "score": 0.001,
                "breakdown": breakdown,
                "passed": False,
                "summary": self._build_summary(0.0, breakdown, task),
            }

        total_value = sum(o.value_usd for o in task.orders)
        high_orders = [o for o in task.orders if o.priority == "high"]
        saved_high  = [o for o in high_orders if o.status == OrderStatus.FULFILLED]

        # ── 1. High-value order save ratio ─────────
        ratio = self._safe_ratio(len(saved_high), len(high_orders))
        component = round(0.40 * ratio, 4)
        breakdown["high_value_orders_saved"] = component
        score += component

        # ── 2. Revenue protected % ─────────────────
        rev_ratio = self._safe_ratio(
            task.metrics.revenue_protected, total_value
        )
        component = round(0.30 * rev_ratio, 4)
        breakdown["revenue_protected"] = component
        score += component

        # ── 3. Budget adherence ────────────────────
        if task.budget.remaining >= 0 and task.budget.spent > 0:
            breakdown["budget_adherence"] = 0.20
            score += 0.20
        elif task.budget.remaining < 0:
            breakdown["budget_adherence"] = 0.0
            score -= 0.05  # penalty for overspend

        # ── 4. Prioritization bonus ────────────────
        o003 = next((o for o in task.orders if o.id == "O003"), None)
        if o003 and o003.status == OrderStatus.FULFILLED:
            breakdown["prioritization_bonus"] = 0.10
            score += 0.10

        final_score = self._clamp(score)

        return {
            "task_id":   self.task_id,
            "score":     final_score,
            "breakdown": breakdown,
            "passed":    final_score >= self.PASS_THRESHOLD,
            "summary":   self._build_summary(final_score, breakdown, task)
        }

    def _build_summary(self, score, breakdown, task) -> str:
        high_orders  = [o for o in task.orders if o.priority == "high"]
        saved_high   = [o for o in high_orders if o.status == "fulfilled"]
        total_value  = sum(o.value_usd for o in task.orders)

        order_lines = []
        for o in task.orders:
            order_lines.append(
                f"  {o.id} [{o.priority:6}] ${o.value_usd:>10,.0f} → {o.status}"
            )

        lines = [
            f"=== MEDIUM TASK GRADER REPORT ===",
            f"Task       : {task.task_name}",
            f"Steps used : {task.current_step} / {task.max_steps}",
            f"",
            f"SCORE BREAKDOWN:",
            f"  High-value saved   : {breakdown.get('high_value_orders_saved', 0):.3f} / 0.40",
            f"  Revenue protected  : {breakdown.get('revenue_protected', 0):.3f} / 0.30",
            f"  Budget adherence   : {breakdown.get('budget_adherence', 0):.3f} / 0.20",
            f"  Prioritization     : {breakdown.get('prioritization_bonus', 0):.3f} / 0.10",
            f"",
            f"FINAL SCORE : {score:.3f}",
            f"PASSED      : {'✅ YES' if score >= self.PASS_THRESHOLD else '❌ NO'}",
            f"",
            f"ORDER SUMMARY ({len(saved_high)}/{len(high_orders)} high-value saved):",
        ] + order_lines + [
            f"",
            f"FINANCIALS:",
            f"  Revenue protected : ${task.metrics.revenue_protected:,.0f} / ${total_value:,.0f}",
            f"  Revenue lost      : ${task.metrics.revenue_lost:,.0f}",
            f"  Budget spent      : ${task.budget.spent:,.0f} / ${task.budget.total:,.0f}",
            f"  Budget remaining  : ${task.budget.remaining:,.0f}",
        ]
        return "\n".join(lines)


class HardGrader(BaseGrader):
    """
    Grader for Task Hard — Cascade Crisis.

    Criteria:
        1. High-value orders saved          → 0.35
        2. Total revenue protected %        → 0.25
        3. Budget not exceeded              → 0.20
        4. Correct escalation decisions     → 0.10
        5. Speed of resolution              → 0.10

    Passing threshold: 0.30
    """

    task_id = "task_hard"
    PASS_THRESHOLD = 0.30

    # These MUST be escalated for full marks
    CRITICAL_DISRUPTIONS = {"D002", "D005", "D006"}

    def grade(self) -> dict:
        task  = self.task
        score = 0.0
        breakdown = {
            "high_value_orders_saved": 0.0,
            "revenue_protected": 0.0,
            "budget_not_exceeded": 0.0,
            "escalation_decisions": 0.0,
            "speed": 0.0,
        }

        if not task.has_resolution_action():
            return {
                "task_id": self.task_id,
                "score": 0.001,
                "breakdown": breakdown,
                "passed": False,
                "summary": self._build_summary(
                    0.0, breakdown, task,
                    [], [o for o in task.orders if o.priority == "high"],
                    sum(o.value_usd for o in task.orders), set()
                )
            }

        total_value = sum(o.value_usd for o in task.orders)
        high_orders = [o for o in task.orders if o.priority == "high"]
        saved_high  = [o for o in high_orders if o.status == OrderStatus.FULFILLED]

        # ── 1. High-value orders saved ─────────────
        ratio     = self._safe_ratio(len(saved_high), len(high_orders))
        component = round(0.35 * ratio, 4)
        breakdown["high_value_orders_saved"] = component
        score += component

        # ── 2. Revenue protected % ─────────────────
        rev_ratio = self._safe_ratio(
            task.metrics.revenue_protected, total_value
        )
        component = round(0.25 * rev_ratio, 4)
        breakdown["revenue_protected"] = component
        score += component

        # ── 3. Budget not exceeded ─────────────────
        if task.budget.remaining >= 0 and task.budget.spent > 0:
            breakdown["budget_not_exceeded"] = 0.20
            score += 0.20
        elif task.budget.remaining < 0:
            breakdown["budget_not_exceeded"] = 0.0

        # ── 4. Escalation decisions ────────────────
        escalated = self.CRITICAL_DISRUPTIONS & task.acted_disruption_ids
        esc_ratio = self._safe_ratio(
            len(escalated), len(self.CRITICAL_DISRUPTIONS)
        )
        component = round(0.10 * esc_ratio, 4)
        breakdown["escalation_decisions"] = component
        score += component

        # ── 5. Speed of resolution ─────────────────
        if task.done and len(saved_high) == len(high_orders):
            step_ratio = task.current_step / task.max_steps
            if step_ratio <= 0.60:
                breakdown["speed"] = 0.10
                score += 0.10
            elif step_ratio <= 0.80:
                breakdown["speed"] = 0.05
                score += 0.05

        # ── Extra penalty: used bad supplier ───────
        bad_supplier_used = any(
            o.current_supplier_id == "S005_ALT"
            for o in task.orders
        )
        if bad_supplier_used:
            breakdown["bad_supplier_penalty"] = -0.10
            score -= 0.10

        final_score = self._clamp(score)

        return {
            "task_id":   self.task_id,
            "score":     final_score,
            "breakdown": breakdown,
            "passed":    final_score >= self.PASS_THRESHOLD,
            "summary":   self._build_summary(
                final_score, breakdown, task,
                saved_high, high_orders, total_value, escalated
            )
        }

    def _build_summary(
        self, score, breakdown, task,
        saved_high, high_orders, total_value, escalated
    ) -> str:
        invalid_actions = sum(1 for record in task.action_history if not record["was_valid"])
        investigate_actions = sum(
            1 for record in task.action_history if record["action_type"] == "investigate"
        )
        hidden_investigated = len(task.hidden_supplier_ids & task.investigated_ids)
        hidden_total = len(task.hidden_supplier_ids)
        hidden_used = sorted(
            order.id for order in task.orders if order.current_supplier_id in task.hidden_supplier_ids
        )

        order_lines = []
        for o in sorted(task.orders, key=lambda x: -x.value_usd):
            order_lines.append(
                f"  {o.id} [{o.priority:6}] "
                f"${o.value_usd:>10,.0f} → {o.status}"
            )

        lines = [
            f"=== HARD TASK GRADER REPORT ===",
            f"Task       : {task.task_name}",
            f"Steps used : {task.current_step} / {task.max_steps}",
            f"",
            f"SCORE BREAKDOWN:",
            f"  High-value saved   : {breakdown.get('high_value_orders_saved', 0):.4f} / 0.35",
            f"  Revenue protected  : {breakdown.get('revenue_protected', 0):.4f} / 0.25",
            f"  Budget not exceeded: {breakdown.get('budget_not_exceeded', 0):.4f} / 0.20",
            f"  Escalation correct : {breakdown.get('escalation_decisions', 0):.4f} / 0.10",
            f"  Speed              : {breakdown.get('speed', 0):.4f} / 0.10",
        ]

        if "bad_supplier_penalty" in breakdown:
            lines.append(
                f"  Bad supplier penalty: {breakdown['bad_supplier_penalty']:.4f}"
            )

        lines += [
            f"",
            f"DIAGNOSTICS:",
            f"  Hidden-risk checks : {hidden_investigated} / {hidden_total}",
            f"  Investigation actions: {investigate_actions}",
            f"  Invalid actions      : {invalid_actions}",
            f"  Critical escalations : {len(escalated)} / {len(self.CRITICAL_DISRUPTIONS)}",
            (
                f"  Hidden-risk supplier used on orders: {', '.join(hidden_used)}"
                if hidden_used else
                "  Hidden-risk supplier used on orders: none"
            ),
        ]

        lines += [
            f"",
            f"FINAL SCORE : {score:.3f}",
            f"PASSED      : {'✅ YES' if score >= self.PASS_THRESHOLD else '❌ NO'}",
            f"",
            f"ORDER SUMMARY ({len(saved_high)}/{len(high_orders)} high-value saved):",
        ] + order_lines + [
            f"",
            f"ESCALATIONS:",
            f"  Required : {self.CRITICAL_DISRUPTIONS}",
            f"  Done     : {escalated}",
            f"  Missed   : {self.CRITICAL_DISRUPTIONS - escalated}",
            f"",
            f"FINANCIALS:",
            f"  Revenue protected : ${task.metrics.revenue_protected:,.0f} / ${total_value:,.0f}",
            f"  Revenue lost      : ${task.metrics.revenue_lost:,.0f}",
            f"  Budget spent      : ${task.budget.spent:,.0f} / ${task.budget.total:,.0f}",
            f"  Budget remaining  : ${task.budget.remaining:,.0f}",
        ]
        return "\n".join(lines)


# ─────────────────────────────────────────
# GRADER REGISTRY
# ─────────────────────────────────────────

GRADER_REGISTRY = {
    "task_easy":   EasyGrader,
    "task_medium": MediumGrader,
    "task_hard":   HardGrader,
}


def get_grader(task: BaseTask) -> BaseGrader:
    """
    Factory function — returns correct grader for a task.
    Usage: grader = get_grader(task_instance)
    """
    grader_class = GRADER_REGISTRY.get(task.task_id)
    if not grader_class:
        raise ValueError(f"No grader found for task_id: {task.task_id}")
    return grader_class(task)
