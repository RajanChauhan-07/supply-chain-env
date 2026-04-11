# backend/app/simulation/market_dynamics.py
"""
Market dynamics simulation: FX rates, spot freight, insurance feedback loops.

FX Model: Random walk with mean-reversion (calibrated to real volatility).
Freight: Seasonal pattern + surge during disruptions.
Insurance: Premium = base_rate × (1 + claim_frequency × sensitivity).
"""

import math
import random
from dataclasses import dataclass, field


@dataclass
class FXState:
    """Foreign exchange rate state."""
    pair: str           # e.g., "USD_CNY"
    rate: float         # Current rate
    base_rate: float    # Long-term mean
    volatility: float   # Daily vol (annualized ~15% → daily ~0.01)
    hedge_coverage: float = 0.0  # 0.0-1.0, fraction hedged

    def step_rate(self, rng: random.Random) -> float:
        """Advance one step: mean-reverting random walk."""
        mean_reversion = 0.05 * (self.base_rate - self.rate)
        shock = rng.gauss(0, self.volatility)
        self.rate = max(0.5 * self.base_rate,
                        min(1.5 * self.base_rate,
                            self.rate + mean_reversion + shock))
        return self.rate

    def hedging_cost(self, amount_usd: float) -> float:
        """Cost of hedging a given USD amount at current rate."""
        # Simplified: hedging costs ~0.5% of notional
        return amount_usd * 0.005 * (1.0 - self.hedge_coverage)

    def exposure(self, amount_usd: float) -> float:
        """Unhedged FX exposure."""
        rate_change = (self.rate - self.base_rate) / self.base_rate
        return amount_usd * rate_change * (1.0 - self.hedge_coverage)


@dataclass
class InsuranceState:
    """Cargo insurance with dynamic premiums (feedback loop)."""
    lane_id: str
    base_premium_rate: float    # e.g., 0.02 (2% of cargo value)
    current_premium_rate: float = 0.0
    claim_count: int = 0
    total_claims_value: float = 0.0
    sensitivity: float = 0.3    # How fast premiums rise per claim

    def __post_init__(self):
        if self.current_premium_rate == 0.0:
            self.current_premium_rate = self.base_premium_rate

    def file_claim(self, claim_value: float):
        """File an insurance claim (raises future premiums)."""
        self.claim_count += 1
        self.total_claims_value += claim_value
        # Premium rises with each claim
        self.current_premium_rate = self.base_premium_rate * (
            1.0 + self.claim_count * self.sensitivity
        )

    def get_premium(self, cargo_value: float) -> float:
        """Get insurance premium for a shipment."""
        return cargo_value * self.current_premium_rate

    def decay_premium(self):
        """Slowly decay premium back toward base (mean reversion)."""
        decay = 0.05 * (self.current_premium_rate - self.base_premium_rate)
        self.current_premium_rate = max(self.base_premium_rate,
                                         self.current_premium_rate - decay)


class MarketDynamics:
    """
    Manages all market-level state: FX, freight, insurance, fuel.
    Evolves every step to create a dynamic environment.
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.step_count = 0

        # ── FX Rates ──────────────────────────────
        self.fx_rates: dict[str, FXState] = {
            "USD_CNY": FXState(pair="USD_CNY", rate=7.24, base_rate=7.24,
                               volatility=0.015),
            "USD_EUR": FXState(pair="USD_EUR", rate=0.92, base_rate=0.92,
                               volatility=0.008),
            "USD_INR": FXState(pair="USD_INR", rate=83.50, base_rate=83.50,
                               volatility=0.20),
            "USD_JPY": FXState(pair="USD_JPY", rate=149.50, base_rate=149.50,
                               volatility=0.50),
        }

        # ── Spot Freight Rates (per TEU or per kg) ──
        self.spot_freight: dict[str, float] = {
            "SH_LAX":      2500.0,   # $/TEU Shanghai → LA (sea)
            "SH_LAX_AIR":  4.50,     # $/kg Shanghai → LA (air)
            "SH_AMS":      2800.0,   # $/TEU Shanghai → Amsterdam
            "SH_AMS_SUEZ": 3100.0,   # $/TEU via Suez
            "GDL_LAX":     1800.0,   # $/load Guadalajara → LA (truck)
            "KY_LAX":      1200.0,   # $/load Kentucky → LA (rail)
            "MUN_AMS":      900.0,   # $/load Munich → Amsterdam
            "HSC_SH":      1500.0,   # $/TEU Hsinchu → Shanghai
        }
        self._base_freight = dict(self.spot_freight)

        # ── Fuel Surcharge ────────────────────────
        self.fuel_surcharge_index: float = 1.0  # Multiplier on freight

        # ── Insurance ─────────────────────────────
        self.insurance: dict[str, InsuranceState] = {}
        for lane_id in self.spot_freight:
            self.insurance[lane_id] = InsuranceState(
                lane_id=lane_id,
                base_premium_rate=0.02,  # 2% base
            )

    def step(self):
        """Advance all market dynamics by one time step."""
        self.step_count += 1

        # Evolve FX rates
        for fx in self.fx_rates.values():
            fx.step_rate(self.rng)

        # Evolve spot freight (seasonal + noise)
        for lane_id, base_rate in self._base_freight.items():
            seasonal = 0.15 * math.sin(self.step_count * 0.25)
            noise = self.rng.gauss(0, 0.05)
            multiplier = 1.0 + seasonal + noise
            self.spot_freight[lane_id] = max(
                base_rate * 0.6,
                base_rate * multiplier
            )

        # Evolve fuel surcharge
        fuel_drift = self.rng.gauss(0, 0.02)
        self.fuel_surcharge_index = max(0.5, min(2.0,
            self.fuel_surcharge_index + fuel_drift))

        # Decay insurance premiums
        for ins in self.insurance.values():
            ins.decay_premium()

    def apply_disruption_freight_surge(self, lane_id: str, severity: float):
        """Spike freight rates when a disruption affects a lane."""
        if lane_id in self.spot_freight:
            surge = 1.0 + severity * 0.5  # Up to +50% for critical
            self.spot_freight[lane_id] *= surge

    def file_insurance_claim(self, lane_id: str, value: float):
        """Record an insurance claim — raises premiums."""
        if lane_id in self.insurance:
            self.insurance[lane_id].file_claim(value)

    def hedge_fx(self, pair: str, coverage: float) -> float:
        """Set FX hedge coverage. Returns hedging cost."""
        if pair in self.fx_rates:
            fx = self.fx_rates[pair]
            old_coverage = fx.hedge_coverage
            fx.hedge_coverage = max(0.0, min(1.0, coverage))
            # Cost proportional to coverage increase
            increase = max(0, fx.hedge_coverage - old_coverage)
            return increase * 0.005 * 1_000_000  # Cost per $1M notional
        return 0.0

    def to_observation_dict(self) -> dict:
        """Convert market state to observation-friendly dict."""
        return {
            "fx_rates": {
                pair: {
                    "rate": round(fx.rate, 4),
                    "base_rate": round(fx.base_rate, 4),
                    "change_pct": round((fx.rate - fx.base_rate) / fx.base_rate * 100, 2),
                    "hedge_coverage": round(fx.hedge_coverage, 2),
                }
                for pair, fx in self.fx_rates.items()
            },
            "fx_hedge_coverage": round(
                sum(fx.hedge_coverage for fx in self.fx_rates.values()) /
                max(1, len(self.fx_rates)), 2
            ),
            "spot_freight_rates": {
                lane: round(rate, 2) for lane, rate in self.spot_freight.items()
            },
            "fuel_surcharge": round(self.fuel_surcharge_index, 3),
            "insurance_premiums": {
                lane: {
                    "rate_pct": round(ins.current_premium_rate * 100, 2),
                    "claims": ins.claim_count,
                }
                for lane, ins in self.insurance.items()
            },
        }
