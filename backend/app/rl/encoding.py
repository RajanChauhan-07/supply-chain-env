from __future__ import annotations

from typing import Any


MAX_DISRUPTIONS = 5
MAX_ORDERS = 8
MAX_SUPPLIERS = 7

DISRUPTION_TYPE_INDEX = {
    "delay": 0.15,
    "closure": 0.30,
    "capacity": 0.45,
    "quality": 0.60,
    "bankruptcy": 0.75,
    "geopolitical": 0.90,
}
SEVERITY_INDEX = {
    "low": 0.25,
    "medium": 0.50,
    "high": 0.75,
    "critical": 1.00,
}
ORDER_STATUS_INDEX = {
    "safe": 0.20,
    "at_risk": 0.40,
    "fulfilled": 0.60,
    "lost": 0.80,
    "delayed": 1.00,
}
PRIORITY_INDEX = {"low": 0.33, "medium": 0.66, "high": 1.00}


def _normalize_task(task_id: str) -> list[float]:
    return [
        1.0 if task_id == "task_easy" else 0.0,
        1.0 if task_id == "task_medium" else 0.0,
        1.0 if task_id == "task_hard" else 0.0,
    ]


def _normalize_id(identifier: str) -> float:
    digits = "".join(ch for ch in str(identifier) if ch.isdigit())
    if not digits:
        return 0.0
    return min(int(digits) / 100.0, 1.0)


def _supplier_lookup(observation: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {supplier["id"]: supplier for supplier in observation.get("available_suppliers", [])}


def encode_observation(observation: Any) -> list[float]:
    if hasattr(observation, "model_dump"):
        observation = observation.model_dump()

    vector: list[float] = []
    vector.extend(_normalize_task(observation.get("task_id", "")))
    vector.extend([
        observation.get("step", 0) / max(observation.get("max_steps", 1), 1),
        len(observation.get("disruptions", [])) / MAX_DISRUPTIONS,
        len(observation.get("orders", [])) / MAX_ORDERS,
        len(observation.get("available_suppliers", [])) / MAX_SUPPLIERS,
    ])

    budget = observation.get("budget", {})
    total_budget = max(float(budget.get("total", 1.0)), 1.0)
    vector.extend([
        float(budget.get("spent", 0.0)) / total_budget,
        float(budget.get("remaining", 0.0)) / total_budget,
    ])

    metrics = observation.get("metrics", {})
    vector.extend([
        metrics.get("orders_saved", 0) / MAX_ORDERS,
        metrics.get("orders_lost", 0) / MAX_ORDERS,
        metrics.get("orders_delayed", 0) / MAX_ORDERS,
        min(float(metrics.get("revenue_protected", 0.0)) / 250000.0, 1.0),
        min(float(metrics.get("revenue_lost", 0.0)) / 250000.0, 1.0),
        float(metrics.get("current_score", 0.0)),
    ])

    for disruption in observation.get("disruptions", [])[:MAX_DISRUPTIONS]:
        vector.extend([
            _normalize_id(disruption.get("id", "")),
            DISRUPTION_TYPE_INDEX.get(disruption.get("type"), 0.0),
            SEVERITY_INDEX.get(disruption.get("severity"), 0.0),
            min(disruption.get("estimated_duration_days", 0) / 30.0, 1.0),
            1.0 if disruption.get("is_resolved") else 0.0,
        ])
    vector.extend([0.0] * ((MAX_DISRUPTIONS - len(observation.get("disruptions", [])[:MAX_DISRUPTIONS])) * 5))

    suppliers = _supplier_lookup(observation)
    for order in observation.get("orders", [])[:MAX_ORDERS]:
        current_supplier = suppliers.get(order.get("current_supplier_id"), {})
        vector.extend([
            _normalize_id(order.get("id", "")),
            min(order.get("quantity", 0) / 5000.0, 1.0),
            min(float(order.get("value_usd", 0.0)) / 100000.0, 1.0),
            min(order.get("deadline_days", 0) / 30.0, 1.0),
            ORDER_STATUS_INDEX.get(order.get("status"), 0.0),
            PRIORITY_INDEX.get(order.get("priority"), 0.0),
            _normalize_id(order.get("current_supplier_id", "")),
            min(float(current_supplier.get("reliability_score") or 0.0), 1.0)
            if current_supplier.get("reliability_known", True) else -1.0,
        ])
    vector.extend([0.0] * ((MAX_ORDERS - len(observation.get("orders", [])[:MAX_ORDERS])) * 8))

    for supplier in observation.get("available_suppliers", [])[:MAX_SUPPLIERS]:
        reliability_value = supplier.get("reliability_score")
        vector.extend([
            _normalize_id(supplier.get("id", "")),
            min(supplier.get("lead_time_days", 0) / 30.0, 1.0),
            min(float(supplier.get("cost_multiplier", 0.0)) / 3.0, 1.0),
            min(float(reliability_value), 1.0) if reliability_value is not None else -1.0,
            1.0 if supplier.get("reliability_known", True) else 0.0,
            min(supplier.get("capacity_available", 0) / 5000.0, 1.0),
            1.0 if supplier.get("is_available", True) else 0.0,
        ])
    vector.extend([0.0] * ((MAX_SUPPLIERS - len(observation.get("available_suppliers", [])[:MAX_SUPPLIERS])) * 7))

    return vector


OBSERVATION_VECTOR_LENGTH = len(encode_observation({
    "task_id": "task_easy",
    "step": 0,
    "max_steps": 10,
    "disruptions": [],
    "orders": [],
    "available_suppliers": [],
    "budget": {"total": 1.0, "spent": 0.0, "remaining": 1.0},
    "metrics": {
        "orders_saved": 0,
        "orders_lost": 0,
        "orders_delayed": 0,
        "revenue_protected": 0.0,
        "revenue_lost": 0.0,
        "current_score": 0.0,
    },
}))
