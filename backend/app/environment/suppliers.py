# backend/app/environment/suppliers.py

from typing import List, Optional
from ..models import Supplier, Order


def get_available_suppliers(suppliers: List[Supplier]) -> List[Supplier]:
    """Return only available suppliers"""
    return [s for s in suppliers if s.is_available]


def get_supplier_by_id(
    suppliers: List[Supplier],
    supplier_id: str
) -> Optional[Supplier]:
    """Find supplier by ID"""
    return next((s for s in suppliers if s.id == supplier_id), None)


def can_fulfill_order(supplier: Supplier, order: Order) -> bool:
    """Check if supplier can fulfill this order"""
    return (
        supplier.is_available and
        supplier.capacity_available >= order.quantity
    )


def will_meet_deadline(supplier: Supplier, order: Order) -> bool:
    """Check if supplier can deliver before deadline"""
    return supplier.lead_time_days <= order.deadline_days


def calculate_extra_cost(supplier: Supplier, order: Order) -> float:
    """
    Calculate extra cost of using this supplier vs baseline (1.0x).
    Returns 0.0 if cheaper or same cost.
    """
    extra = order.value_usd * (supplier.cost_multiplier - 1.0)
    return max(0.0, round(extra, 2))


def rank_suppliers(
    suppliers: List[Supplier],
    order: Order,
    budget_remaining: float
) -> List[dict]:
    """
    Rank available suppliers for a given order.
    Returns list of dicts sorted by best fit score.

    Scoring:
        on_time      → 40 points
        reliable     → 30 points (reliability * 30)
        affordable   → 20 points (inverse of cost_multiplier)
        has_capacity → 10 points
    """
    rankings = []

    for supplier in suppliers:
        if not supplier.is_available:
            continue

        score     = 0.0
        extra_cost = calculate_extra_cost(supplier, order)

        on_time  = will_meet_deadline(supplier, order)
        has_cap  = can_fulfill_order(supplier, order)
        in_budget = extra_cost <= budget_remaining

        if on_time:
            score += 40
        if has_cap:
            score += 10
        score += supplier.reliability_score * 30
        # Cost score: cheaper = higher score
        cost_score = max(0, 20 - (supplier.cost_multiplier - 1.0) * 40)
        score += cost_score

        rankings.append({
            "supplier":     supplier,
            "fit_score":    round(score, 2),
            "on_time":      on_time,
            "has_capacity": has_cap,
            "in_budget":    in_budget,
            "extra_cost":   extra_cost,
            "recommended":  on_time and has_cap and in_budget,
        })

    # Sort by fit score descending
    rankings.sort(key=lambda x: -x["fit_score"])
    return rankings


def describe_suppliers(suppliers: List[Supplier]) -> str:
    """Build human-readable summary of available suppliers"""
    available = get_available_suppliers(suppliers)
    if not available:
        return "No suppliers available."

    lines = [f"Available suppliers ({len(available)}):"]
    for s in available:
        lines.append(
            f"  {s.id} — {s.name:30} | "
            f"Lead: {s.lead_time_days:2}d | "
            f"Cost: {s.cost_multiplier:.2f}x | "
            f"Reliability: {s.reliability_score:.2f} | "
            f"Capacity: {s.capacity_available:,}"
        )
    return "\n".join(lines)