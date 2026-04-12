# ACTION_REFERENCE.md — Complete Action Type Reference

> Every action the agent can take, with required/optional fields,
> legal and illegal examples, and which tasks support each action.

---

## 1. `reroute` — Move order to a different supplier

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `action_type` | ✅ | `"reroute"` | — |
| `order_id` | ✅ | string | Must be a valid order ID from observation |
| `new_supplier_id` | ✅ | string | Must be a valid supplier ID from observation |
| `shipping_method` | ❌ | string | `"air"`, `"sea"`, `"rail"`, `"truck"` (default: `"air"`) |

**Legal example:**
```json
{"action_type": "reroute", "order_id": "O001", "new_supplier_id": "S004", "shipping_method": "sea"}
```

**Illegal example (capacity exceeded):**
```json
{"action_type": "reroute", "order_id": "O001", "new_supplier_id": "S009"}
```
> Rejection: `"S009 lacks capacity. Available: 5000, Required: 10000"`

**Supported tasks:** All

---

## 2. `escalate` — Escalate disruption to management

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `action_type` | ✅ | `"escalate"` | — |
| `disruption_id` | ✅ | string | Must be a valid disruption ID |
| `escalation_priority` | ✅ | string | `"low"`, `"medium"`, `"high"`, `"critical"` |
| `escalation_message` | ❌ | string | Free-form message |

**Legal example:**
```json
{"action_type": "escalate", "disruption_id": "D001", "escalation_priority": "critical", "escalation_message": "Port closure affecting 3 critical orders"}
```

**Illegal example (unknown disruption):**
```json
{"action_type": "escalate", "disruption_id": "D999", "escalation_priority": "high"}
```
> Rejection: `"Unknown disruption D999"`

**Supported tasks:** All

---

## 3. `investigate` — Get more info about a supplier or disruption

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `action_type` | ✅ | `"investigate"` | — |
| `target_id` | ✅ | string | Supplier ID or disruption ID |
| `investigation_type` | ❌ | string | `"reliability"`, `"capacity"`, `"cost"` |

**Legal example:**
```json
{"action_type": "investigate", "target_id": "S005", "investigation_type": "reliability"}
```

**Effect:** Reveals hidden `reliability_score` for supplier. In `task_multi_tier`, also reveals masked Tier 3 supplier details.

**Supported tasks:** All (critical for adversarial and multi-tier tasks)

---

## 4. `delay` — Push order deadline back

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `action_type` | ✅ | `"delay"` | — |
| `order_id` | ✅ | string | Valid order ID |
| `delay_days` | ✅ | integer | Must be > 0 |
| `reason` | ❌ | string | Justification |

**Legal example:**
```json
{"action_type": "delay", "order_id": "O003", "delay_days": 7, "reason": "Waiting for supplier audit"}
```

**Supported tasks:** All

---

## 5. `cancel` — Cancel order entirely

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `action_type` | ✅ | `"cancel"` | — |
| `order_id` | ✅ | string | Valid order ID |
| `reason` | ❌ | string | Justification |

**Legal example:**
```json
{"action_type": "cancel", "order_id": "O006", "reason": "Low priority, no viable supplier"}
```

**Supported tasks:** All (penalized heavily for critical/high orders)

---

## 6. `substitute` — Replace product with alternative

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `action_type` | ✅ | `"substitute"` | — |
| `order_id` | ✅ | string | Valid order ID |
| `alternative_product` | ✅ | string | Product name |
| `notify_customer` | ❌ | boolean | Default: `true` |

**Legal example:**
```json
{"action_type": "substitute", "order_id": "O002", "alternative_product": "iPad Display Gen2", "notify_customer": true}
```

**Supported tasks:** All

---

## 7. `hedge_fx` — Buy FX forward contract

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `action_type` | ✅ | `"hedge_fx"` | — |
| `fx_pair` | ✅ | string | e.g. `"USD_CNY"`, `"USD_EUR"`, `"USD_JPY"` |
| `hedge_coverage` | ✅ | float | 0.0 to 1.0 |

**Legal example:**
```json
{"action_type": "hedge_fx", "fx_pair": "USD_CNY", "hedge_coverage": 0.80}
```

**Effect:** Locks in current FX rate. Hedge position carries across steps. Mark-to-market P&L affects budget.

**Supported tasks:** task_stochastic, task_full_sim

---

## 8. `insure` — Purchase cargo insurance

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `action_type` | ✅ | `"insure"` | — |
| `lane_id` | ✅ | string | Shipping lane ID |
| `coverage_value` | ✅ | float | USD value to insure |

**Legal example:**
```json
{"action_type": "insure", "lane_id": "SH_LAX", "coverage_value": 500000}
```

**Effect:** Premiums rise with usage. Claims resolve after 3 steps and credit budget.

**Supported tasks:** task_stochastic, task_adversarial_v2, task_full_sim

---

## 9. `expedite` — Pay premium for faster shipping

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `action_type` | ✅ | `"expedite"` | — |
| `order_id` | ✅ | string | Valid order ID |
| `lane_id` | ✅ | string | Shipping lane to expedite on |

**Legal example:**
```json
{"action_type": "expedite", "order_id": "O001", "lane_id": "SH_LAX_AIR"}
```

**Supported tasks:** task_stochastic, task_full_sim

---

## 10. `rebalance_inventory` — Move stock between DCs

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `action_type` | ✅ | `"rebalance_inventory"` | — |
| `from_dc` | ✅ | string | Source DC ID |
| `to_dc` | ✅ | string | Destination DC ID |
| `sku` | ✅ | string | SKU to transfer |
| `quantity` | ✅ | integer | Units to move |

**Supported tasks:** task_full_sim

---

## 11. `pre_clear` — File customs pre-clearance

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `action_type` | ✅ | `"pre_clear"` | — |
| `lane_id` | ✅ | string | Shipping lane |
| `order_id` | ✅ | string | Order to pre-clear |

**Effect:** Required within 2 steps of a sea route to avoid coordination penalty in grading.

**Supported tasks:** task_stochastic, task_full_sim

---

## 12. `select_carrier` — Choose specific carrier for a lane

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `action_type` | ✅ | `"select_carrier"` | — |
| `carrier_id` | ✅ | string | Carrier ID |
| `lane_id` | ✅ | string | Lane ID |
| `order_id` | ✅ | string | Order ID |

**Supported tasks:** task_stochastic, task_full_sim

---

## Common Model Mistakes (Auto-Fixed)

| Model Output | Auto-Corrected To |
|-------------|-------------------|
| `"action_id"` in escalate | → `"disruption_id"` |
| `"supplier_id"` in reroute | → `"new_supplier_id"` |
| `"days"` in delay | → `"delay_days"` |
