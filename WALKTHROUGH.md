# WALKTHROUGH.md — Solving task_full_sim (Expert Level)

> This document demonstrates how the LLM agent handles the `task_full_sim` scenario, which includes ITAR constraints, Tier 3 partial observability, and correlated risk events.

## Scenario Setup

* **Budget:** $5.0M
* **Launch Countdown:** 10 steps
* **Disruptions:** 
  - `D001`: Port strike at Shanghai (impacts Tier 1 shipments)
  - `D002`: Severe typhoon warning in Taiwan (impacts Tier 2 components)
* **Goal:** Fulfill 3 critical orders containing the upcoming product launch inventory before countdown hits 0.

---

## 🕒 Step 1: Investigation & Escalation

**Observation:** The agent sees `D001` (Port strike) but lacks data on a seemingly cheap alternative supplier `S008`.
**Action Taken:**
```json
{
  "action_type": "investigate",
  "target_id": "S008",
  "investigation_type": "reliability"
}
```
**Result:** The environment reveals that `S008` is actually a "trap" supplier with a 0.20 reliability score. A CostGreedy agent would have routed here and lost the shipment 2 steps later.

---

## 🕒 Step 2: Currency Hedging

**Observation:** The USD/CNY exchange rate is highly volatile (`change_pct: +1.8%`), and $3M of orders require Chinese suppliers.
**Action Taken:**
```json
{
  "action_type": "hedge_fx",
  "fx_pair": "USD_CNY",
  "hedge_coverage": 0.85
}
```
**Result:** The agent locks in the current rate for 85% of its exposure. As the simulation progresses, the spot rate drops further, but the hedge creates a positive mark-to-market P&L, crediting the budget.

---

## 🕒 Step 3: Resolving Tier 3 Obfuscation

**Observation:** Order `O002` (Batteries) is `at_risk` due to a delay at Tier 2. The root cause is masked.
**Action Taken:**
```json
{
  "action_type": "investigate",
  "target_id": "S003",
  "investigation_type": "tier_3_root_cause"
}
```
**Result:** The environment removes the masking, revealing a lithium shortage at `Glencore`. The agent now knows that simply rerouting to another Tier 2 using the same raw material will fail.

---

## 🕒 Step 4: Strategic Routing & Compliance

**Observation:** Order `O001` requires routing. The fastest route is via `S005` using Air freight, but `S005` is flagged in `ITAR_001` (Restricted Entity).
**Action Taken:**
```json
{
  "action_type": "reroute",
  "order_id": "O001",
  "new_supplier_id": "S002",
  "shipping_method": "sea"
}
```
**Result:** The agent bypasses the ITAR restriction (which would have yielded an automatic -0.15 score penalty and failed action). Sea freight is chosen to minimize cost.

---

## 🕒 Step 5: Customs Coordination

**Observation:** The agent previously chose `sea` freight, which triggers a potential delay if customs paperwork isn't filed.
**Action Taken:**
```json
{
  "action_type": "pre_clear",
  "lane_id": "SH_LAX",
  "order_id": "O001"
}
```
**Result:** The agent avoids the `Coordination Penalty` in the final grading by ensuring the cross-layer decision (shipping + documentation) is coherent.

---

## 🏁 Final Grade
**Pass/Fail:** Passed
**Score Breakdown:**
- **Cost Efficiency:** `0.85` (Budget protected by FX hedge, sea freight utilized)
- **Service Level:** `0.95` (Products arrived exactly on Step 9, beating the 10-step launch window)
- **Launch Precision:** `1.0` (All critical orders fulfilled)
- **Coordination Deductions:** `0.0` (No incoherent actions)
- **Final Normalized Score:** `0.784`
