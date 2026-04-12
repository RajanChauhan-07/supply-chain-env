# backend/app/simulation/market_dynamics.py
"""
Market dynamics simulation: FX rates, spot freight, insurance feedback loops.

FX Model: Random walk with mean-reversion (calibrated to real volatility).
Freight: Seasonal pattern + surge during disruptions.
Insurance: Premium = base_rate × (1 + claim_frequency × sensitivity).
Hedge Book: Positions carry across steps with mark-to-market P&L.
Claims: Filed claims resolve after N steps and credit back to budget.
"""

import math
import random
from dataclasses import dataclass, field
from typing import Optional


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
class HedgeReceipt:
    """Record of an FX hedge position opened at a specific step."""
    pair: str
    coverage: float        # 0.0-1.0
    cost: float            # USD cost to open the position
    step_opened: int
    locked_rate: float     # FX rate at time of hedge
    notional_usd: float = 1_000_000.0  # Notional per position


@dataclass
class InsuranceClaim:
    """A pending insurance claim that resolves after N steps."""
    claim_id: str
    lane_id: str
    value: float           # Payout value
    filed_step: int
    resolution_steps: int = 3  # Steps until payout
    resolved: bool = False
    payout: float = 0.0


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

        # ── Hedge Book ────────────────────────
        self.hedge_book: list[HedgeReceipt] = []
        self.total_hedge_pnl: float = 0.0

        # ── Pending Insurance Claims ──────────
        self.pending_claims: list[InsuranceClaim] = []
        self.resolved_claims: list[InsuranceClaim] = []
        self._claim_counter: int = 0

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

        # Compute hedge mark-to-market P&L
        self._compute_hedge_pnl()

        # Resolve mature insurance claims
        self._resolve_claims()

    def apply_disruption_freight_surge(self, lane_id: str, severity: float):
        """Spike freight rates when a disruption affects a lane."""
        if lane_id in self.spot_freight:
            surge = 1.0 + severity * 0.5  # Up to +50% for critical
            self.spot_freight[lane_id] *= surge

    def file_insurance_claim(self, lane_id: str, value: float):
        """Record an insurance claim — raises premiums."""
        if lane_id in self.insurance:
            self.insurance[lane_id].file_claim(value)

    def hedge_fx(self, pair: str, coverage: float, step: int = 0) -> float:
        """Set FX hedge coverage. Returns hedging cost and records position."""
        if pair in self.fx_rates:
            fx = self.fx_rates[pair]
            old_coverage = fx.hedge_coverage
            fx.hedge_coverage = max(0.0, min(1.0, coverage))
            # Cost proportional to coverage increase
            increase = max(0, fx.hedge_coverage - old_coverage)
            cost = increase * 0.005 * 1_000_000  # Cost per $1M notional

            if increase > 0:
                receipt = HedgeReceipt(
                    pair=pair,
                    coverage=fx.hedge_coverage,
                    cost=cost,
                    step_opened=step,
                    locked_rate=fx.rate,
                )
                self.hedge_book.append(receipt)

            return cost
        return 0.0

    def _compute_hedge_pnl(self):
        """Mark-to-market P&L for all open hedge positions."""
        total_pnl = 0.0
        for hedge in self.hedge_book:
            fx = self.fx_rates.get(hedge.pair)
            if fx:
                # P&L = notional × coverage × (current_rate - locked_rate) / locked_rate
                rate_change = (fx.rate - hedge.locked_rate) / hedge.locked_rate
                pnl = hedge.notional_usd * hedge.coverage * rate_change
                total_pnl += pnl
        self.total_hedge_pnl = round(total_pnl, 2)

    def file_insurance_claim(self, lane_id: str, value: float):
        """Record an insurance claim — raises premiums and starts resolution timer."""
        if lane_id in self.insurance:
            self.insurance[lane_id].file_claim(value)
        self._claim_counter += 1
        claim = InsuranceClaim(
            claim_id=f"CLM_{self._claim_counter:03d}",
            lane_id=lane_id,
            value=value,
            filed_step=self.step_count,
            resolution_steps=3,  # Resolves after 3 steps
            payout=value * 0.8,  # 80% payout ratio
        )
        self.pending_claims.append(claim)

    def _resolve_claims(self):
        """Check and resolve any matured insurance claims."""
        still_pending = []
        for claim in self.pending_claims:
            if not claim.resolved and (self.step_count - claim.filed_step) >= claim.resolution_steps:
                claim.resolved = True
                self.resolved_claims.append(claim)
            else:
                still_pending.append(claim)
        self.pending_claims = still_pending

    def get_resolved_payouts(self) -> float:
        """Return total payout from newly resolved claims and clear the list."""
        total = sum(c.payout for c in self.resolved_claims)
        self.resolved_claims = []
        return total

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
            "hedge_book": [
                {
                    "pair": h.pair,
                    "coverage": h.coverage,
                    "locked_rate": round(h.locked_rate, 4),
                    "step_opened": h.step_opened,
                    "cost": round(h.cost, 2),
                }
                for h in self.hedge_book
            ],
            "hedge_pnl": self.total_hedge_pnl,
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
            "pending_insurance_claims": [
                {
                    "id": c.claim_id,
                    "lane": c.lane_id,
                    "value": round(c.value, 2),
                    "payout": round(c.payout, 2),
                    "steps_remaining": max(0, c.resolution_steps - (self.step_count - c.filed_step)),
                }
                for c in self.pending_claims
            ],
        }
