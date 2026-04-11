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


class ExpertGrader(BaseGrader):
    """
    Grader for Task Expert — Cascading Domino Effect.

    Criteria:
        1. Revenue protected (priority-weighted)  → 0.25
        2. Cascade prevention                     → 0.20
        3. Regional balance                       → 0.15
        4. Budget adherence                       → 0.15
        5. Strategic investigation                → 0.10
        6. Escalation quality                     → 0.10
        7. Efficiency                             → 0.05

    Passing threshold: 0.40
    """

    task_id = "task_expert"
    PASS_THRESHOLD = 0.40

    def grade(self) -> dict:
        task = self.task
        score = 0.0
        breakdown = {
            "revenue_protected":       0.0,
            "cascade_prevention":      0.0,
            "regional_balance":        0.0,
            "budget_adherence":        0.0,
            "strategic_investigation": 0.0,
            "escalation_quality":      0.0,
            "efficiency":              0.0,
        }

        if not task.has_resolution_action():
            return {
                "task_id": self.task_id,
                "score": 0.001,
                "breakdown": breakdown,
                "passed": False,
                "summary": self._build_summary(0.001, breakdown, task),
            }

        # 1. Revenue protected (priority-weighted)
        priority_weights = {"critical": 2.0, "high": 1.5, "medium": 1.0, "low": 0.5}
        weighted_saved = 0.0
        weighted_total = 0.0
        for o in task.orders:
            w = priority_weights.get(o.priority, 1.0)
            weighted_total += o.value_usd * w
            if o.status == OrderStatus.FULFILLED:
                weighted_saved += o.value_usd * w
            elif o.status == OrderStatus.DELAYED:
                weighted_saved += o.value_usd * w * 0.5

        if weighted_total > 0:
            breakdown["revenue_protected"] = round(0.25 * (weighted_saved / weighted_total), 4)
            score += breakdown["revenue_protected"]

        # 2. Cascade prevention
        cascades_fired = sum(1 for v in task.cascade_fired.values() if v)
        cascade_scores = {0: 0.20, 1: 0.10, 2: 0.05, 3: 0.0}
        breakdown["cascade_prevention"] = cascade_scores.get(cascades_fired, 0.0)
        score += breakdown["cascade_prevention"]

        # 3. Regional balance
        counts = [v for v in task.region_reroute_count.values() if v > 0]
        if len(counts) >= 2:
            max_c, min_c = max(counts), min(counts)
            balance = 1.0 - (max_c - min_c) / max(max_c, 1)
            breakdown["regional_balance"] = round(0.15 * balance, 4)
        elif len(counts) == 1:
            breakdown["regional_balance"] = 0.05
        score += breakdown["regional_balance"]

        # 4. Budget adherence
        if task.budget.remaining >= 0:
            ratio = task.budget.remaining / task.budget.total
            breakdown["budget_adherence"] = round(0.15 * min(ratio * 2, 1.0), 4)
            score += breakdown["budget_adherence"]

        # 5. Strategic investigation
        useful = len(task.investigated_ids & task.hidden_supplier_ids)
        if useful > 0:
            breakdown["strategic_investigation"] = 0.10
        elif task.investigated_ids:
            breakdown["strategic_investigation"] = 0.05
        score += breakdown["strategic_investigation"]

        # 6. Escalation quality
        critical_disruptions = [d for d in task.disruptions if d.severity in ["critical", "high"] and not d.id.startswith("D_CASCADE")]
        escalated = len(task.acted_disruption_ids & {d.id for d in critical_disruptions})
        if critical_disruptions:
            breakdown["escalation_quality"] = round(0.10 * (escalated / len(critical_disruptions)), 4)
            score += breakdown["escalation_quality"]

        # 7. Efficiency
        if task.done and task.current_step <= task.max_steps * 0.6:
            breakdown["efficiency"] = 0.05
        elif task.done and task.current_step <= task.max_steps * 0.8:
            breakdown["efficiency"] = 0.025
        score += breakdown["efficiency"]

        final_score = self._clamp(score)
        return {
            "task_id":   self.task_id,
            "score":     final_score,
            "breakdown": breakdown,
            "passed":    final_score >= self.PASS_THRESHOLD,
            "summary":   self._build_summary(final_score, breakdown, task),
        }

    def _build_summary(self, score, breakdown, task) -> str:
        cascades = sum(1 for v in task.cascade_fired.values() if v)
        regions_used = {k: v for k, v in task.region_reroute_count.items() if v > 0}
        lines = [
            f"=== EXPERT TASK GRADER REPORT ===",
            f"Task       : {task.task_name}",
            f"Steps used : {task.current_step} / {task.max_steps}",
            f"",
            f"SCORE BREAKDOWN (7 dimensions):",
            f"  Revenue protected     : {breakdown['revenue_protected']:.3f} / 0.250",
            f"  Cascade prevention    : {breakdown['cascade_prevention']:.3f} / 0.200",
            f"  Regional balance      : {breakdown['regional_balance']:.3f} / 0.150",
            f"  Budget adherence      : {breakdown['budget_adherence']:.3f} / 0.150",
            f"  Strategic investigation: {breakdown['strategic_investigation']:.3f} / 0.100",
            f"  Escalation quality    : {breakdown['escalation_quality']:.3f} / 0.100",
            f"  Efficiency            : {breakdown['efficiency']:.3f} / 0.050",
            f"",
            f"FINAL SCORE : {score:.3f}",
            f"PASSED      : {'✅ YES' if score >= self.PASS_THRESHOLD else '❌ NO'}",
            f"",
            f"CASCADE ANALYSIS:",
            f"  Cascades triggered : {cascades} / 3 regions",
            f"  Region reroutes    : {regions_used}",
            f"  Cascade events     : {len(getattr(task, 'cascade_events', []))}",
            f"",
            f"FINANCIALS:",
            f"  Budget spent      : ${task.budget.spent:,.0f} / ${task.budget.total:,.0f}",
            f"  Budget remaining  : ${task.budget.remaining:,.0f}",
        ]
        return "\n".join(lines)


class AdversarialGrader(BaseGrader):
    """
    Grader for Task Adversarial — Supplier Trap Detection.

    Criteria:
        1. Revenue protected (final state)           → 0.25
        2. Traps detected (investigated before use)  → 0.25
        3. Zero trap failures                        → 0.20
        4. Budget efficiency                         → 0.15
        5. Investigation thoroughness                → 0.10
        6. Efficiency                                → 0.05

    Passing threshold: 0.40
    """

    task_id = "task_adversarial"
    PASS_THRESHOLD = 0.40

    def grade(self) -> dict:
        task = self.task
        score = 0.0
        breakdown = {
            "revenue_protected":    0.0,
            "traps_detected":       0.0,
            "zero_trap_failures":   0.0,
            "budget_efficiency":    0.0,
            "investigation_depth":  0.0,
            "efficiency":           0.0,
        }

        if not task.has_resolution_action():
            return {
                "task_id": self.task_id,
                "score": 0.001,
                "breakdown": breakdown,
                "passed": False,
                "summary": self._build_summary(0.001, breakdown, task),
            }

        # 1. Revenue protected
        total_value = sum(o.value_usd for o in task.orders)
        protected = sum(
            o.value_usd for o in task.orders
            if o.status in [OrderStatus.FULFILLED, OrderStatus.DELAYED]
        )
        if total_value > 0:
            breakdown["revenue_protected"] = round(0.25 * (protected / total_value), 4)
            score += breakdown["revenue_protected"]

        # 2. Traps detected
        traps_total = len(getattr(task, 'trap_supplier_ids', set()))
        traps_found = len(getattr(task, 'trap_revealed_ids', set()))
        if traps_total > 0:
            breakdown["traps_detected"] = round(0.25 * (traps_found / traps_total), 4)
            score += breakdown["traps_detected"]

        # 3. Zero trap failures
        trap_failures = getattr(task, 'trap_failures_count', 0)
        if trap_failures == 0:
            breakdown["zero_trap_failures"] = 0.20
        elif trap_failures == 1:
            breakdown["zero_trap_failures"] = 0.10
        elif trap_failures == 2:
            breakdown["zero_trap_failures"] = 0.05
        score += breakdown["zero_trap_failures"]

        # 4. Budget efficiency
        if task.budget.remaining >= 0:
            ratio = task.budget.remaining / task.budget.total
            breakdown["budget_efficiency"] = round(0.15 * min(ratio * 2, 1.0), 4)
            score += breakdown["budget_efficiency"]

        # 5. Investigation depth
        total_investigated = len(task.investigated_ids)
        if total_investigated >= 3:
            breakdown["investigation_depth"] = 0.10
        elif total_investigated >= 1:
            breakdown["investigation_depth"] = 0.05
        score += breakdown["investigation_depth"]

        # 6. Efficiency
        if task.done and task.current_step <= task.max_steps * 0.6:
            breakdown["efficiency"] = 0.05
        elif task.done and task.current_step <= task.max_steps * 0.8:
            breakdown["efficiency"] = 0.025
        score += breakdown["efficiency"]

        final_score = self._clamp(score)
        return {
            "task_id":   self.task_id,
            "score":     final_score,
            "breakdown": breakdown,
            "passed":    final_score >= self.PASS_THRESHOLD,
            "summary":   self._build_summary(final_score, breakdown, task),
        }

    def _build_summary(self, score, breakdown, task) -> str:
        trap_failures = getattr(task, 'trap_failures_count', 0)
        traps_found = len(getattr(task, 'trap_revealed_ids', set()))
        lines = [
            f"=== ADVERSARIAL TASK GRADER REPORT ===",
            f"Task       : {task.task_name}",
            f"Steps used : {task.current_step} / {task.max_steps}",
            f"",
            f"SCORE BREAKDOWN (6 dimensions):",
            f"  Revenue protected    : {breakdown['revenue_protected']:.3f} / 0.250",
            f"  Traps detected       : {breakdown['traps_detected']:.3f} / 0.250",
            f"  Zero trap failures   : {breakdown['zero_trap_failures']:.3f} / 0.200",
            f"  Budget efficiency    : {breakdown['budget_efficiency']:.3f} / 0.150",
            f"  Investigation depth  : {breakdown['investigation_depth']:.3f} / 0.100",
            f"  Efficiency           : {breakdown['efficiency']:.3f} / 0.050",
            f"",
            f"FINAL SCORE : {score:.3f}",
            f"PASSED      : {'✅ YES' if score >= self.PASS_THRESHOLD else '❌ NO'}",
            f"",
            f"TRAP ANALYSIS:",
            f"  Traps in environment : 3",
            f"  Traps discovered     : {traps_found}",
            f"  Trap failures        : {trap_failures}",
            f"  Orders lost to traps : {trap_failures}",
            f"",
            f"INVESTIGATION LOG:",
            f"  Targets investigated : {len(task.investigated_ids)}",
            f"  Investigations       : {', '.join(sorted(task.investigated_ids)) or 'none'}",
            f"",
            f"FINANCIALS:",
            f"  Budget spent      : ${task.budget.spent:,.0f} / ${task.budget.total:,.0f}",
            f"  Budget remaining  : ${task.budget.remaining:,.0f}",
        ]
        return "\n".join(lines)


# ─────────────────────────────────────────
# GRADER REGISTRY
# ─────────────────────────────────────────


class FoundationalGrader(BaseGrader):
    """Grader for Task Foundational — calls task.get_final_score()."""
    task_id = "task_foundational"
    PASS_THRESHOLD = 0.50

    def grade(self) -> dict:
        task = self.task
        score = self._clamp(task.get_final_score())
        total_value = sum(o.value_usd for o in task.orders)
        saved_count = sum(1 for o in task.orders if o.status == OrderStatus.FULFILLED)
        return {
            "task_id": self.task_id,
            "score": score,
            "breakdown": {
                "orders_saved": f"{saved_count}/{len(task.orders)}",
                "revenue_protected": f"${task.metrics.revenue_protected:,.0f}",
                "budget_spent": f"${task.budget.spent:,.0f}/${task.budget.total:,.0f}",
            },
            "passed": score >= self.PASS_THRESHOLD,
            "summary": (
                f"=== FOUNDATIONAL GRADER ===\n"
                f"Score: {score:.3f} | Saved: {saved_count}/{len(task.orders)} | "
                f"Budget: ${task.budget.spent:,.0f}/${task.budget.total:,.0f}"
            ),
        }


class MultiTierGrader(BaseGrader):
    """Grader for Task Multi-Tier — multi-objective with cascade awareness."""
    task_id = "task_multi_tier"
    PASS_THRESHOLD = 0.40

    def grade(self) -> dict:
        task = self.task
        score = self._clamp(task.get_final_score())
        saved_count = sum(1 for o in task.orders if o.status == OrderStatus.FULFILLED)
        delayed_count = sum(1 for o in task.orders if o.status == OrderStatus.DELAYED)
        return {
            "task_id": self.task_id,
            "score": score,
            "breakdown": {
                "orders_saved": f"{saved_count}/{len(task.orders)}",
                "orders_delayed": delayed_count,
                "investigated": len(task.investigated_ids),
                "disruptions_escalated": len(task.acted_disruption_ids),
                "budget_spent": f"${task.budget.spent:,.0f}",
            },
            "passed": score >= self.PASS_THRESHOLD,
            "summary": (
                f"=== MULTI-TIER GRADER ===\n"
                f"Score: {score:.3f} | Saved: {saved_count} | "
                f"Delayed: {delayed_count} | "
                f"Investigated: {len(task.investigated_ids)} | "
                f"Escalated: {len(task.acted_disruption_ids)}"
            ),
        }


class StochasticGrader(BaseGrader):
    """Grader for Task Stochastic — multi-objective: cost, service, launch, ESG."""
    task_id = "task_stochastic"
    PASS_THRESHOLD = 0.35

    def grade(self) -> dict:
        task = self.task
        score = self._clamp(task.get_final_score())
        total_value = sum(o.value_usd for o in task.orders)
        saved = sum(o.value_usd for o in task.orders if o.status == OrderStatus.FULFILLED)
        return {
            "task_id": self.task_id,
            "score": score,
            "breakdown": {
                "revenue_pct": f"{saved/total_value*100:.1f}%" if total_value > 0 else "0%",
                "budget_efficiency": f"${task.budget.remaining:,.0f} remaining",
                "dynamic_disruptions_handled": len([d for d in task.disruptions if d.id.startswith("EVT")]),
                "launch_countdown_final": getattr(task.world, 'launch_countdown', -1),
            },
            "passed": score >= self.PASS_THRESHOLD,
            "summary": (
                f"=== STOCHASTIC GRADER ===\n"
                f"Score: {score:.3f} | Revenue: {saved/total_value*100:.1f}% | "
                f"Dynamic events: {len([d for d in task.disruptions if d.id.startswith('EVT')])} | "
                f"Budget: ${task.budget.remaining:,.0f} left"
            ),
        }


class AdversarialV2Grader(BaseGrader):
    """Grader for Task Adversarial V2 — trap detection + insurance exploit."""
    task_id = "task_adversarial_v2"
    PASS_THRESHOLD = 0.40

    def grade(self) -> dict:
        task = self.task
        score = self._clamp(task.get_final_score())
        traps_investigated = len(task.trap_supplier_ids & task.investigated_ids)
        return {
            "task_id": self.task_id,
            "score": score,
            "breakdown": {
                "traps_detected": f"{traps_investigated}/{len(task.trap_supplier_ids)}",
                "trap_failures": len(task.trap_failures),
                "orders_saved": sum(1 for o in task.orders if o.status == OrderStatus.FULFILLED),
                "investigation_depth": len(task.investigated_ids),
                "budget_spent": f"${task.budget.spent:,.0f}",
                "insurance_claims": len(getattr(task, 'trap_failures', [])),
            },
            "passed": score >= self.PASS_THRESHOLD,
            "summary": (
                f"=== ADVERSARIAL V2 GRADER ===\n"
                f"Score: {score:.3f} | Traps found: {traps_investigated}/{len(task.trap_supplier_ids)} | "
                f"Trap failures: {len(task.trap_failures)} | "
                f"Investigated: {len(task.investigated_ids)}"
            ),
        }


class FullSimGrader(BaseGrader):
    """
    Grader for Task Full Sim — Apple-Scale.
    Multi-objective: Cost (30%) + Service (30%) + Launch (25%) + ESG (15%)
    """
    task_id = "task_full_sim"
    PASS_THRESHOLD = 0.30

    def grade(self) -> dict:
        task = self.task
        score = self._clamp(task.get_final_score())
        total_value = sum(o.value_usd for o in task.orders)
        saved = sum(o.value_usd for o in task.orders if o.status == OrderStatus.FULFILLED)

        # Detailed multi-objective breakdown
        budget_eff = max(0, 1.0 - task.budget.spent / task.budget.total) if task.budget.total > 0 else 0
        service_pct = saved / total_value if total_value > 0 else 0
        critical_orders = [o for o in task.orders if o.priority in ("critical", "high")]
        critical_saved = sum(1 for o in critical_orders if o.status == OrderStatus.FULFILLED)
        launch_pct = critical_saved / max(1, len(critical_orders))
        total_carbon = task.carbon_air + task.carbon_sea
        esg_pct = task.carbon_sea / total_carbon if total_carbon > 0 else 0.5

        return {
            "task_id": self.task_id,
            "score": score,
            "breakdown": {
                "cost_score": f"{budget_eff:.2f} (weight: 0.30)",
                "service_score": f"{service_pct:.2f} (weight: 0.30)",
                "launch_score": f"{launch_pct:.2f} (weight: 0.25)",
                "esg_score": f"{esg_pct:.2f} (weight: 0.15)",
                "trap_failures": len(task.trap_failures),
                "cascade_regions": sum(1 for c in task.region_reroute_count.values() if c >= 4),
                "investigations": len(task.investigated_ids),
                "itar_blocks": task.itar_blocks,
                "insurance_claims": task.insurance_claims,
                "dynamic_events": len([d for d in task.disruptions if d.id.startswith("EVT")]),
            },
            "passed": score >= self.PASS_THRESHOLD,
            "summary": (
                f"=== FULL SIMULATION GRADER (Apple-Scale) ===\n"
                f"OVERALL SCORE: {score:.3f}\n\n"
                f"MULTI-OBJECTIVE BREAKDOWN:\n"
                f"  Cost Efficiency   : {budget_eff:.2f} × 0.30 = {budget_eff*0.30:.3f}\n"
                f"  Service Level     : {service_pct:.2f} × 0.30 = {service_pct*0.30:.3f}\n"
                f"  Launch Precision  : {launch_pct:.2f} × 0.25 = {launch_pct*0.25:.3f}\n"
                f"  ESG/Carbon        : {esg_pct:.2f} × 0.15 = {esg_pct*0.15:.3f}\n\n"
                f"ADVANCED MECHANICS:\n"
                f"  Trap failures     : {len(task.trap_failures)}\n"
                f"  Cascade overloads : {sum(1 for c in task.region_reroute_count.values() if c >= 4)}\n"
                f"  Investigations    : {len(task.investigated_ids)}\n"
                f"  Dynamic disruptions: {len([d for d in task.disruptions if d.id.startswith('EVT')])}\n\n"
                f"FINANCIALS:\n"
                f"  Budget: ${task.budget.spent:,.0f} / ${task.budget.total:,.0f}\n"
                f"  Revenue protected: ${saved:,.0f} / ${total_value:,.0f}"
            ),
        }


GRADER_REGISTRY = {
    # v1 (legacy)
    "task_easy":            EasyGrader,
    "task_medium":          MediumGrader,
    "task_hard":            HardGrader,
    "task_expert":          ExpertGrader,
    "task_adversarial":     AdversarialGrader,
    # v2 (God-level)
    "task_foundational":    FoundationalGrader,
    "task_multi_tier":      MultiTierGrader,
    "task_stochastic":      StochasticGrader,
    "task_adversarial_v2":  AdversarialV2Grader,
    "task_full_sim":        FullSimGrader,
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

