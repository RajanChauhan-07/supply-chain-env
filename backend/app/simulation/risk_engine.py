# backend/app/simulation/risk_engine.py
"""
Stochastic Risk Engine — draws disruptions from historical distributions.

Each step the engine rolls dice per disruption type. Disruptions are
seeded (deterministic per seed) but appear stochastic to the agent.
Multiple disruptions can compound.
"""

import random
import math
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DisruptionEvent:
    """A disruption event injected by the risk engine."""
    id: str
    event_type: str
    severity: str           # "low", "medium", "high", "critical"
    severity_score: float   # 0.0-1.0 numeric severity
    region: str
    affected_suppliers: list = field(default_factory=list)
    affected_lanes: list = field(default_factory=list)
    duration_days: int = 7
    started_step: int = 0
    description: str = ""
    is_resolved: bool = False
    tier_affected: int = 0  # 0 = all, 1/2/3 = specific tier


# Historical disruption catalog with real-world calibrated probabilities
DISRUPTION_CATALOG = {
    "port_strike": {
        "probability_per_step": 0.06,
        "duration_range": (3, 21),
        "severity_weights": {"low": 0.1, "medium": 0.3, "high": 0.4, "critical": 0.2},
        "regions": ["asia", "europe", "americas"],
        "affects": "lanes",
        "description_templates": [
            "Port workers strike at {location} disrupting {n} shipping lanes.",
            "Labor dispute at {location} halts port operations.",
        ],
    },
    "typhoon": {
        "probability_per_step": 0.10,
        "duration_range": (1, 7),
        "severity_weights": {"low": 0.05, "medium": 0.2, "high": 0.4, "critical": 0.35},
        "regions": ["asia"],
        "seasonal_peak_step": 15,  # Peak around step 15
        "affects": "both",
        "description_templates": [
            "Typhoon warning in {location}. Ports and factories affected.",
            "Severe weather system approaching {location} coast.",
        ],
    },
    "tariff_shock": {
        "probability_per_step": 0.04,
        "duration_range": (30, 90),
        "severity_weights": {"low": 0.2, "medium": 0.5, "high": 0.25, "critical": 0.05},
        "regions": ["asia", "americas"],
        "affects": "suppliers",
        "description_templates": [
            "New {pct}% tariff imposed on goods from {region}.",
            "Trade policy shift: additional duties on {region} imports.",
        ],
    },
    "suez_blockage": {
        "probability_per_step": 0.02,
        "duration_range": (3, 14),
        "severity_weights": {"low": 0.0, "medium": 0.1, "high": 0.3, "critical": 0.6},
        "regions": ["global"],
        "affects": "lanes",
        "description_templates": [
            "Vessel grounded in Suez Canal. All Suez-route traffic halted.",
        ],
    },
    "chip_shortage": {
        "probability_per_step": 0.03,
        "duration_range": (14, 60),
        "severity_weights": {"low": 0.1, "medium": 0.3, "high": 0.4, "critical": 0.2},
        "regions": ["asia"],
        "affects": "suppliers",
        "tier_target": 2,
        "description_templates": [
            "Semiconductor supply crunch affecting Tier 2 component suppliers.",
            "Wafer fab utilization at 100%. Lead times extending globally.",
        ],
    },
    "cyber_attack": {
        "probability_per_step": 0.05,
        "duration_range": (2, 14),
        "severity_weights": {"low": 0.1, "medium": 0.3, "high": 0.35, "critical": 0.25},
        "regions": ["asia", "europe", "americas"],
        "affects": "suppliers",
        "description_templates": [
            "Ransomware attack on {supplier_name} IT systems. Operations halted.",
            "Cybersecurity breach at {supplier_name}. Manual operations only.",
        ],
    },
    "pandemic_wave": {
        "probability_per_step": 0.02,
        "duration_range": (14, 45),
        "severity_weights": {"low": 0.15, "medium": 0.35, "high": 0.35, "critical": 0.15},
        "regions": ["asia", "europe", "americas"],
        "affects": "both",
        "description_templates": [
            "New pandemic wave in {region}. Factory shutdowns and port delays.",
        ],
    },
    "earthquake": {
        "probability_per_step": 0.01,
        "duration_range": (7, 30),
        "severity_weights": {"low": 0.0, "medium": 0.1, "high": 0.3, "critical": 0.6},
        "regions": ["asia"],
        "affects": "both",
        "tier_target": 3,
        "description_templates": [
            "Major earthquake near {location}. Mining and extraction halted.",
        ],
    },
    "sanctions": {
        "probability_per_step": 0.03,
        "duration_range": (90, 365),
        "severity_weights": {"low": 0.0, "medium": 0.2, "high": 0.5, "critical": 0.3},
        "regions": ["asia", "africa"],
        "affects": "suppliers",
        "description_templates": [
            "New export controls on {region} materials. Compliance review required.",
            "Government sanctions affecting raw material imports from {region}.",
        ],
    },
    "labor_shortage": {
        "probability_per_step": 0.08,
        "duration_range": (7, 28),
        "severity_weights": {"low": 0.3, "medium": 0.4, "high": 0.2, "critical": 0.1},
        "regions": ["asia", "europe", "americas"],
        "affects": "suppliers",
        "description_templates": [
            "Skilled labor shortage at {location}. Production capacity reduced.",
        ],
    },
}

SEVERITY_MAP = {"low": 0.25, "medium": 0.50, "high": 0.75, "critical": 1.0}


class RiskEngine:
    """
    Stochastic risk engine that injects disruptions from historical distributions.
    Seeded for reproducibility, but appears random to the agent.
    """

    def __init__(self, seed: int = 42, difficulty: float = 1.0):
        self.rng = random.Random(seed)
        self.difficulty = difficulty
        self.active_events: list[DisruptionEvent] = []
        self.event_counter = 0
        self.event_log: list[DisruptionEvent] = []

    def step(self, current_step: int, supply_network=None) -> list[DisruptionEvent]:
        """
        Roll for new disruptions this step. Returns newly created events.
        """
        new_events = []

        for event_type, config in DISRUPTION_CATALOG.items():
            prob = config["probability_per_step"] * self.difficulty

            # Seasonal adjustment
            if "seasonal_peak_step" in config:
                peak = config["seasonal_peak_step"]
                seasonal_boost = 0.15 * math.exp(-0.5 * ((current_step - peak) / 5) ** 2)
                prob += seasonal_boost

            if self.rng.random() < prob:
                event = self._create_event(event_type, config, current_step,
                                           supply_network)
                if event:
                    new_events.append(event)
                    self.active_events.append(event)
                    self.event_log.append(event)

        # Resolve expired events
        self._resolve_expired(current_step)

        return new_events

    def _create_event(self, event_type: str, config: dict,
                      current_step: int, supply_network=None) -> Optional[DisruptionEvent]:
        """Create a new disruption event from catalog config."""
        self.event_counter += 1
        event_id = f"EVT_{self.event_counter:03d}"

        # Pick severity
        severities = list(config["severity_weights"].keys())
        weights = list(config["severity_weights"].values())
        severity = self.rng.choices(severities, weights=weights, k=1)[0]

        # Pick region
        regions = config["regions"]
        region = self.rng.choice(regions)

        # Pick duration
        dur_min, dur_max = config["duration_range"]
        duration = self.rng.randint(dur_min, dur_max)

        # Build description
        template = self.rng.choice(config["description_templates"])
        description = template.format(
            location=region.title(),
            region=region.title(),
            supplier_name=f"Supplier in {region.title()}",
            n=self.rng.randint(1, 4),
            pct=self.rng.randint(5, 25),
        )

        # Determine affected suppliers/lanes
        affected_suppliers = []
        affected_lanes = []
        tier_target = config.get("tier_target", 0)

        if supply_network:
            affects = config["affects"]
            if affects in ("suppliers", "both"):
                for sup in supply_network.get_all_suppliers_flat():
                    if (region == "global" or sup.region == region) and \
                       (tier_target == 0 or sup.tier == tier_target):
                        if self.rng.random() < 0.5:  # 50% chance each supplier
                            affected_suppliers.append(sup.id)
            if affects in ("lanes", "both"):
                for lane in supply_network.lanes:
                    if region == "global" or region in (lane.origin, lane.destination):
                        if self.rng.random() < 0.4:
                            affected_lanes.append(lane.id)

        return DisruptionEvent(
            id=event_id,
            event_type=event_type,
            severity=severity,
            severity_score=SEVERITY_MAP[severity],
            region=region,
            affected_suppliers=affected_suppliers,
            affected_lanes=affected_lanes,
            duration_days=duration,
            started_step=current_step,
            description=description,
            tier_affected=tier_target,
        )

    def _resolve_expired(self, current_step: int):
        """Mark events whose duration has elapsed as resolved."""
        for event in self.active_events:
            if not event.is_resolved:
                elapsed = current_step - event.started_step
                if elapsed >= event.duration_days:
                    event.is_resolved = True

        self.active_events = [e for e in self.active_events if not e.is_resolved]

    def get_active_events(self) -> list[DisruptionEvent]:
        return [e for e in self.active_events if not e.is_resolved]

    def get_risk_context(self) -> dict:
        """Compute aggregate risk scores by region and weather/geopolitical."""
        weather_severity = {}
        geopolitical_tension = {}

        for event in self.get_active_events():
            region = event.region
            score = event.severity_score

            if event.event_type in ("typhoon", "earthquake", "pandemic_wave"):
                weather_severity[region] = max(
                    weather_severity.get(region, 0), score)
            if event.event_type in ("sanctions", "tariff_shock"):
                geopolitical_tension[region] = max(
                    geopolitical_tension.get(region, 0), score)

        return {
            "weather_severity": weather_severity,
            "geopolitical_tension": geopolitical_tension,
            "active_event_count": len(self.get_active_events()),
            "event_types_active": list(set(e.event_type for e in self.get_active_events())),
        }

    def to_observation_list(self) -> list[dict]:
        """Convert active events to observation-friendly list."""
        return [
            {
                "id": e.id,
                "type": e.event_type,
                "severity": e.severity,
                "severity_score": e.severity_score,
                "region": e.region,
                "affected_suppliers": e.affected_suppliers,
                "affected_lanes": e.affected_lanes,
                "duration_days": e.duration_days,
                "step_started": e.started_step,
                "description": e.description,
                "is_resolved": e.is_resolved,
                "tier_affected": e.tier_affected,
            }
            for e in self.get_active_events()
        ]
