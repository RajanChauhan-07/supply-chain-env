# backend/app/environment/disruptions.py

from typing import List
from ..models import Disruption, DisruptionSeverity


def get_active_disruptions(disruptions: List[Disruption]) -> List[Disruption]:
    """Return only unresolved disruptions"""
    return [d for d in disruptions if not d.is_resolved]


def get_critical_disruptions(disruptions: List[Disruption]) -> List[Disruption]:
    """Return only critical severity disruptions"""
    return [
        d for d in disruptions
        if d.severity == DisruptionSeverity.CRITICAL
        and not d.is_resolved
    ]


def get_disruptions_for_supplier(
    disruptions: List[Disruption],
    supplier_id: str
) -> List[Disruption]:
    """Return all disruptions affecting a specific supplier"""
    return [
        d for d in disruptions
        if d.affected_supplier_id == supplier_id
        and not d.is_resolved
    ]


def is_supplier_disrupted(
    disruptions: List[Disruption],
    supplier_id: str
) -> bool:
    """Check if a supplier has any active disruption"""
    return any(
        d.affected_supplier_id == supplier_id
        and not d.is_resolved
        for d in disruptions
    )


def resolve_disruption(
    disruptions: List[Disruption],
    disruption_id: str
) -> bool:
    """
    Mark a disruption as resolved.
    Returns True if found and resolved, False if not found.
    """
    for d in disruptions:
        if d.id == disruption_id:
            d.is_resolved = True
            return True
    return False


def describe_disruptions(disruptions: List[Disruption]) -> str:
    """Build human-readable summary of all disruptions"""
    active = get_active_disruptions(disruptions)
    if not active:
        return "No active disruptions."

    lines = [f"Active disruptions ({len(active)}):"]
    for d in active:
        lines.append(
            f"  [{d.severity.upper():8}] {d.id} — "
            f"{d.affected_supplier_name}: {d.description[:60]}..."
        )
    return "\n".join(lines)