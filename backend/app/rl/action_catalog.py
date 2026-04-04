from __future__ import annotations

from typing import Any


ACTION_CATALOG_SIZE = 64
SHIPPING_METHODS = ["air", "truck", "rail", "sea"]
INVESTIGATION_TYPES = ["reliability", "capacity", "cost"]


def canonicalize_action(action: dict[str, Any]) -> tuple:
    return tuple((key, repr(value)) for key, value in sorted(action.items()))


def _candidate_score(order: dict[str, Any], supplier: dict[str, Any], budget_remaining: float) -> float:
    capacity_ok = supplier.get("capacity_available", 0) >= order.get("quantity", 0)
    deadline_ok = supplier.get("lead_time_days", 999) <= max(order.get("deadline_days", 0), 0)
    reliability = supplier.get("reliability_score")
    reliability_score = 0.65 if reliability is None else float(reliability)
    cost_penalty = max(float(supplier.get("cost_multiplier", 1.0)) - 1.0, 0.0)
    budget_penalty = 0.5 if budget_remaining <= 0 else min(cost_penalty * order.get("value_usd", 0) / max(budget_remaining, 1.0), 1.0)

    score = reliability_score
    if capacity_ok:
        score += 0.5
    if deadline_ok:
        score += 0.5
    score -= cost_penalty
    score -= budget_penalty
    return score


def build_action_catalog(observation: Any, max_actions: int = ACTION_CATALOG_SIZE) -> list[dict[str, Any]]:
    if hasattr(observation, "model_dump"):
        observation = observation.model_dump()

    disruptions = [
        disruption for disruption in observation.get("disruptions", [])
        if not disruption.get("is_resolved")
    ]
    orders = [
        order for order in observation.get("orders", [])
        if order.get("status") == "at_risk"
    ]
    suppliers = observation.get("available_suppliers", [])
    budget_remaining = float(observation.get("budget", {}).get("remaining", 0.0))

    candidates: list[dict[str, Any]] = []
    seen: set[tuple] = set()

    def add(action: dict[str, Any]) -> None:
        key = canonicalize_action(action)
        if key in seen or len(candidates) >= max_actions:
            return
        seen.add(key)
        candidates.append(action)

    hidden_suppliers = [supplier for supplier in suppliers if not supplier.get("reliability_known", True)]
    for supplier in hidden_suppliers:
        for investigation_type in INVESTIGATION_TYPES:
            add({
                "action_type": "investigate",
                "target_id": supplier["id"],
                "investigation_type": investigation_type,
            })

    for disruption in disruptions:
        add({
            "action_type": "escalate",
            "disruption_id": disruption["id"],
            "escalation_priority": "critical" if disruption.get("severity") == "critical" else "high",
            "escalation_message": "RL wrapper escalation for critical disruption handling.",
        })
        for investigation_type in INVESTIGATION_TYPES:
            add({
                "action_type": "investigate",
                "target_id": disruption["id"],
                "investigation_type": investigation_type,
            })

    for supplier in suppliers:
        for investigation_type in INVESTIGATION_TYPES:
            add({
                "action_type": "investigate",
                "target_id": supplier["id"],
                "investigation_type": investigation_type,
            })

    ranked_pairs: list[tuple[float, dict[str, Any]]] = []
    for order in orders:
        for supplier in suppliers:
            if supplier["id"] == order.get("current_supplier_id"):
                continue
            ranked_pairs.append((_candidate_score(order, supplier, budget_remaining), {
                "order": order,
                "supplier": supplier,
            }))

    for item in sorted(ranked_pairs, key=lambda pair: pair[0], reverse=True):
        order = item[1]["order"]
        supplier = item[1]["supplier"]
        preferred_shipping = "air" if supplier.get("lead_time_days", 99) <= max(order.get("deadline_days", 0), 0) else "truck"
        add({
            "action_type": "reroute",
            "order_id": order["id"],
            "new_supplier_id": supplier["id"],
            "shipping_method": preferred_shipping,
        })

    for order in orders:
        add({
            "action_type": "delay",
            "order_id": order["id"],
            "delay_days": 7,
            "reason": "RL wrapper delay action.",
        })
        add({
            "action_type": "cancel",
            "order_id": order["id"],
            "reason": "RL wrapper cancellation action.",
        })

    fallback_action = candidates[0] if candidates else {
        "action_type": "investigate",
        "target_id": "D001",
        "investigation_type": "reliability",
    }
    while len(candidates) < max_actions:
        candidates.append(dict(fallback_action))
    return candidates[:max_actions]
