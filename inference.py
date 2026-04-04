# inference.py
# ─────────────────────────────────────────────────────────────────
# OpenEnv Baseline Inference Script
# Supply Chain Disruption Management Environment
#
# Usage:
#   export API_BASE_URL="https://your-openai-compatible-endpoint"
#   export MODEL_NAME="your-model-name"
#   export HF_TOKEN="your-api-key"
#   python inference.py
#
# Must complete in under 20 minutes.
# Must use OpenAI client for all LLM calls.
# ─────────────────────────────────────────────────────────────────

import os
import sys
import ast
import json
import time
import re
from typing import Optional
import httpx
import traceback
from openai import OpenAI


# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────

API_BASE_URL  = os.environ.get(
    "API_BASE_URL",
    ""
)
MODEL_NAME    = os.environ.get("MODEL_NAME",  "")
HF_TOKEN      = os.environ.get("HF_TOKEN") or os.environ.get("OPENAI_API_KEY", "")
ENV_BASE_URL  = os.environ.get("ENV_URL",      "http://localhost:7860")
STRICT_BASELINE = os.environ.get("STRICT_BASELINE", "").strip().lower() in {
    "1", "true", "yes", "on"
}

TASK_IDS      = ["task_easy", "task_medium", "task_hard"]
MAX_STEPS     = {"task_easy": 10, "task_medium": 20, "task_hard": 30}
MAX_CONTEXT_EVENTS = 6


# ─────────────────────────────────────────
# OPENAI CLIENT SETUP
# ─────────────────────────────────────────

def get_llm_client() -> OpenAI:
    """Initialize OpenAI-compatible client."""
    if not API_BASE_URL or not MODEL_NAME:
        raise ValueError(
            "API_BASE_URL and MODEL_NAME must be set for model-backed inference."
        )
    return OpenAI(
        api_key=HF_TOKEN,
        base_url=API_BASE_URL,
        timeout=30.0,
        max_retries=1,
    )


BENCHMARK_NAME = "supply-chain-disruption-env"


def _single_line(value: Optional[str]) -> str:
    """Collapse free-form text into a safe one-line field value."""
    if value is None:
        return "null"
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    return text if text else "null"


def _bool_str(value: bool) -> str:
    return "true" if value else "false"


def _format_action_str(action_dict: dict) -> str:
    """Render the executed action as a compact single-line string."""
    return json.dumps(action_dict, separators=(",", ":"), sort_keys=True)


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} "
        f"done={_bool_str(done)} error={_single_line(error)}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: list[float]) -> None:
    rewards_str = ",".join(f"{reward:.2f}" for reward in rewards)
    print(
        f"[END] success={_bool_str(success)} steps={steps} "
        f"score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


def build_completion_kwargs(messages: list[dict], max_tokens: int) -> dict:
    """Build provider-compatible completion kwargs."""
    kwargs = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.2,
    }
    if "gpt-5" in MODEL_NAME:
        kwargs["max_completion_tokens"] = max_tokens
    else:
        kwargs["max_tokens"] = max_tokens
    return kwargs


def extract_json_candidates(raw_text: str) -> list[str]:
    """
    Extract likely JSON snippets from a model response.
    Handles full-response JSON, fenced blocks, and embedded JSON objects.
    """
    if not raw_text:
        return []

    candidates = []
    text = raw_text.strip()
    candidates.append(text)

    fenced_blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    candidates.extend(block.strip() for block in fenced_blocks if block.strip())

    start = None
    depth = 0
    in_string = False
    escape = False
    for index, char in enumerate(text):
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start is not None:
                    candidates.append(text[start:index + 1].strip())
                    start = None

    # Preserve order while removing duplicates.
    seen = set()
    unique = []
    for candidate in candidates:
        if candidate and candidate not in seen:
            unique.append(candidate)
            seen.add(candidate)
    return unique


def normalize_action_payload(payload) -> Optional[dict]:
    """Normalize common model response shapes into the action dict expected by the env."""
    if isinstance(payload, list) and payload:
        payload = payload[0]

    if not isinstance(payload, dict):
        return None

    if "action_type" in payload:
        return payload

    for key in ["action", "next_action", "response", "output", "json"]:
        nested = payload.get(key)
        if isinstance(nested, dict) and "action_type" in nested:
            return nested

    return None


def parse_action_response(raw_text: str) -> Optional[dict]:
    """
    Parse a model response into an action dict.
    Tries strict JSON first, then fenced/embedded JSON, then Python-literal style dicts.
    """
    for candidate in extract_json_candidates(raw_text):
        try:
            parsed = json.loads(candidate)
            normalized = normalize_action_payload(parsed)
            if normalized:
                return normalized
        except json.JSONDecodeError:
            pass

        try:
            parsed = ast.literal_eval(candidate)
            normalized = normalize_action_payload(parsed)
            if normalized:
                return normalized
        except (ValueError, SyntaxError):
            pass

    return None


def infer_action_from_prose(raw_text: str) -> Optional[dict]:
    """
    Recover an action from free-form model prose when strict JSON parsing fails.
    This is intentionally conservative: it only returns an action when the text
    contains a clear action type plus the fields needed to execute it.
    """
    if not raw_text:
        return None

    text = raw_text.strip()
    lowered = text.lower()

    order_ids = re.findall(r"\bO\d+\b", text, flags=re.IGNORECASE)
    supplier_ids = re.findall(r"\bS\d+(?:_ALT)?\b", text, flags=re.IGNORECASE)
    disruption_ids = re.findall(r"\bD\d+\b", text, flags=re.IGNORECASE)
    priorities = re.findall(r"\b(low|medium|high|critical)\b", lowered)
    investigation_types = re.findall(r"\b(reliability|capacity|cost)\b", lowered)

    def first_or_none(values):
        return values[0].upper() if values else None

    delay_match = re.search(r"\b(\d+)\s*day", lowered)
    delay_days = int(delay_match.group(1)) if delay_match else None

    if "reroute" in lowered and order_ids and supplier_ids:
        return {
            "action_type": "reroute",
            "order_id": first_or_none(order_ids),
            "new_supplier_id": first_or_none(supplier_ids),
            "shipping_method": "air",
        }

    if "escalate" in lowered and disruption_ids:
        escalation_priority = priorities[0] if priorities else "critical"
        return {
            "action_type": "escalate",
            "disruption_id": first_or_none(disruption_ids),
            "escalation_priority": escalation_priority,
            "escalation_message": "Escalating disruption based on model reasoning.",
        }

    if "investigate" in lowered:
        target_id = first_or_none(disruption_ids) or first_or_none(supplier_ids)
        if target_id:
            payload = {
                "action_type": "investigate",
                "target_id": target_id,
            }
            if investigation_types:
                payload["investigation_type"] = investigation_types[0]
            return payload

    if "delay" in lowered and order_ids:
        return {
            "action_type": "delay",
            "order_id": first_or_none(order_ids),
            "delay_days": delay_days or 7,
            "reason": "Delay inferred from model response.",
        }

    if "cancel" in lowered and order_ids:
        return {
            "action_type": "cancel",
            "order_id": first_or_none(order_ids),
            "reason": "Cancellation inferred from model response.",
        }

    if "substitute" in lowered and order_ids:
        alt_match = re.search(
            r"substitute(?:\s+order)?\s+O\d+\s+(?:with|for)\s+([A-Za-z0-9 _-]+?)(?:[.;,\n]|$)",
            text,
            flags=re.IGNORECASE,
        )
        alternative_product = alt_match.group(1).strip() if alt_match else "Alternative Product"
        return {
            "action_type": "substitute",
            "order_id": first_or_none(order_ids),
            "alternative_product": alternative_product,
            "notify_customer": True,
        }

    return None


def create_chat_completion(client: OpenAI, messages: list[dict], max_tokens: int = 300) -> str:
    """Send one chat completion request and return text content."""
    kwargs = build_completion_kwargs(messages, max_tokens=max_tokens)
    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:
        message = str(exc)
        if (
            "max_tokens" in kwargs
            and "max_completion_tokens" in message
            and "Unsupported parameter" in message
        ):
            kwargs.pop("max_tokens", None)
            kwargs["max_completion_tokens"] = max_tokens
            response = client.chat.completions.create(**kwargs)
        else:
            raise
    return (response.choices[0].message.content or "").strip()


def request_model_action(
    client: OpenAI,
    conversation: list[dict],
    verbose: bool = True,
) -> tuple[Optional[dict], Optional[str], bool]:
    """
    Request an action from the model.
    Returns: (action_dict, raw_response, used_repair)
    """
    raw_action = create_chat_completion(client, conversation, max_tokens=300)

    conversation.append({
        "role": "assistant",
        "content": raw_action,
    })

    if verbose:
        print(f"  LLM → {raw_action[:100]}")

    action_dict = parse_action_response(raw_action) or infer_action_from_prose(raw_action)
    if action_dict is not None:
        return action_dict, raw_action, False

    repair_prompt = (
        "Your last reply was not parseable as the required action JSON.\n"
        "Return ONLY one valid JSON object for exactly one next action.\n"
        "Do not include any explanation, markdown, or extra text.\n"
        'Example: {"action_type":"investigate","target_id":"D001"}'
    )
    conversation.append({
        "role": "user",
        "content": repair_prompt,
    })

    repaired_action = create_chat_completion(client, conversation, max_tokens=160)
    conversation.append({
        "role": "assistant",
        "content": repaired_action,
    })

    if verbose:
        print(f"  Repair → {repaired_action[:100]}")

    action_dict = parse_action_response(repaired_action) or infer_action_from_prose(repaired_action)
    return action_dict, repaired_action, True


def validate_action_against_observation(observation: dict, action_dict: dict) -> tuple[bool, str]:
    """
    Lightweight local guardrail so obviously impossible model actions do not
    waste steps before we can recover.
    """
    if not action_dict or "action_type" not in action_dict:
        return False, "missing action_type"

    action_type = action_dict["action_type"]
    orders = {order["id"]: order for order in observation.get("orders", [])}
    suppliers = {supplier["id"]: supplier for supplier in observation.get("available_suppliers", [])}
    disruptions = {disruption["id"]: disruption for disruption in observation.get("disruptions", [])}
    budget_remaining = observation.get("budget", {}).get("remaining", 0.0)

    if action_type in {"reroute", "substitute", "delay", "cancel"}:
        order_id = action_dict.get("order_id")
        if order_id not in orders:
            return False, f"unknown order_id {order_id}"

    if action_type == "reroute":
        order = orders[action_dict["order_id"]]
        supplier_id = action_dict.get("new_supplier_id")
        if supplier_id not in suppliers:
            return False, f"unknown supplier_id {supplier_id}"
        supplier = suppliers[supplier_id]
        if supplier.get("capacity_available", 0) < order.get("quantity", 0):
            return False, f"supplier {supplier_id} lacks capacity"
        extra_cost = max(
            0.0,
            order.get("value_usd", 0.0) * (supplier.get("cost_multiplier", 1.0) - 1.0),
        )
        if extra_cost > budget_remaining:
            return False, f"insufficient budget for supplier {supplier_id}"

    if action_type == "delay":
        delay_days = action_dict.get("delay_days")
        if not isinstance(delay_days, int) or delay_days <= 0:
            return False, "delay_days must be a positive integer"

    if action_type == "escalate":
        disruption_id = action_dict.get("disruption_id")
        if disruption_id not in disruptions:
            return False, f"unknown disruption_id {disruption_id}"

    if action_type == "investigate":
        target_id = action_dict.get("target_id")
        if target_id not in disruptions and target_id not in suppliers:
            return False, f"unknown target_id {target_id}"

    return True, ""


def classify_execution_mode(
    model_actions_used: int,
    fallback_actions_used: int,
    parse_failures: int,
    model_action_rejections: int,
) -> str:
    """Classify how a task was executed for judge-facing reporting."""
    if model_actions_used > 0 and fallback_actions_used == 0:
        return "model_only"
    if model_actions_used == 0 and fallback_actions_used > 0:
        return "fallback_only"
    if model_actions_used > 0 and fallback_actions_used > 0:
        return "hybrid"
    if parse_failures > 0 or model_action_rejections > 0:
        return "failed_model"
    return "no_actions"


def summarize_results(results: list[dict], elapsed: float) -> dict:
    """Build a machine-readable summary for the full baseline run."""
    average_score = round(
        sum(result["score"] for result in results) / len(results), 4
    ) if results else 0.0

    execution_modes = {
        result["task_id"]: result.get("execution_mode", "unknown")
        for result in results
    }

    fallback_assisted_tasks = [
        result["task_id"]
        for result in results
        if result.get("fallback_actions_used", 0) > 0
    ]
    model_only_tasks = [
        result["task_id"]
        for result in results
        if result.get("execution_mode") == "model_only"
    ]

    return {
        "baseline_results": results,
        "average_score": average_score,
        "total_runtime_s": round(elapsed, 2),
        "model": MODEL_NAME,
        "strict_baseline": STRICT_BASELINE,
        "used_fallback": any(result.get("fallback_used") for result in results),
        "fallback_assisted_tasks": fallback_assisted_tasks,
        "fully_model_driven_tasks": model_only_tasks,
        "execution_modes": execution_modes,
        "all_passed": all(result["passed"] for result in results),
    }


def build_step_log(
    task_id: str,
    step: int,
    max_steps: int,
    action_dict: dict,
    action_source: str,
    reward_value: float,
    done: bool,
    observation: dict,
    reason: str,
    parse_failures: int,
    repair_attempts_used: int,
    model_action_rejections: int,
) -> dict:
    at_risk = [
        order["id"]
        for order in observation.get("orders", [])
        if order.get("status") == "at_risk"
    ]
    return {
        "task_id": task_id,
        "step": step,
        "max_steps": max_steps,
        "action_source": action_source,
        "action": action_dict,
        "reward": round(reward_value, 4),
        "done": done,
        "at_risk_orders": at_risk,
        "reason": clip_text(reason, 160),
        "parse_failures": parse_failures,
        "repair_attempts_used": repair_attempts_used,
        "model_action_rejections": model_action_rejections,
    }


def clip_text(text: str, limit: int = 140) -> str:
    """Keep free-form text compact for prompts and summaries."""
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def build_recent_event_summary(
    step: int,
    action_dict: dict,
    reward_value: float,
    reason: str,
    source: str,
) -> str:
    """Create a compact memory line for the next prompt turn."""
    action_type = action_dict.get("action_type", "unknown")
    fragments = [f"step {step}", source, action_type]
    if action_dict.get("order_id"):
        fragments.append(action_dict["order_id"])
    if action_dict.get("new_supplier_id"):
        fragments.append(f"->{action_dict['new_supplier_id']}")
    if action_dict.get("disruption_id"):
        fragments.append(action_dict["disruption_id"])
    if action_dict.get("target_id"):
        fragments.append(action_dict["target_id"])
    fragments.append(f"reward {reward_value:+.2f}")
    fragments.append(clip_text(reason, 80))
    return " | ".join(fragments)


def choose_fallback_action(observation: dict, escalated_ids: set[str]) -> dict:
    """
    Deterministic backup policy used when the model call fails.
    This keeps baseline runs reproducible even when external endpoints are flaky.
    """
    critical = [
        d for d in observation.get("disruptions", [])
        if d.get("severity") == "critical" and d.get("id") not in escalated_ids
    ]
    if critical:
        disruption = critical[0]
        escalated_ids.add(disruption["id"])
        return {
            "action_type": "escalate",
            "disruption_id": disruption["id"],
            "escalation_priority": "critical",
            "escalation_message": "Escalating critical supply chain disruption.",
        }

    budget_remaining = observation.get("budget", {}).get("remaining", 0.0)
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    at_risk_orders = sorted(
        [
            o for o in observation.get("orders", [])
            if o.get("status") == "at_risk"
        ],
        key=lambda o: (
            priority_rank.get(o.get("priority"), 99),
            -o.get("value_usd", 0.0),
            o.get("deadline_days", 999),
        ),
    )

    for order in at_risk_orders:
        candidates = []
        for supplier in observation.get("available_suppliers", []):
            if supplier.get("capacity_available", 0) < order.get("quantity", 0):
                continue

            extra_cost = max(
                0.0,
                order.get("value_usd", 0.0) * (supplier.get("cost_multiplier", 1.0) - 1.0),
            )
            if extra_cost > budget_remaining:
                continue

            on_time = supplier.get("lead_time_days", 999) <= order.get("deadline_days", 0)
            reliability_score = supplier.get("reliability_score")
            reliability_known = supplier.get("reliability_known", True)
            reliable = reliability_known and reliability_score is not None and reliability_score >= 0.75
            rank = (
                1 if on_time else 0,
                1 if reliable else 0,
                1 if reliability_known else 0,
                -extra_cost,
                -supplier.get("lead_time_days", 999),
                reliability_score if reliability_score is not None else 0.0,
            )
            candidates.append((rank, supplier))

        if candidates:
            candidates.sort(reverse=True, key=lambda item: item[0])
            supplier = candidates[0][1]

            if not supplier.get("reliability_known", True):
                return {
                    "action_type": "investigate",
                    "target_id": supplier["id"],
                    "investigation_type": "reliability",
                }

            return {
                "action_type": "reroute",
                "order_id": order["id"],
                "new_supplier_id": supplier["id"],
                "shipping_method": "air",
            }

        if order.get("priority") == "low":
            return {
                "action_type": "cancel",
                "order_id": order["id"],
                "reason": "No feasible alternative within current constraints.",
            }

        return {
            "action_type": "delay",
            "order_id": order["id"],
            "delay_days": 7,
            "reason": "Temporary delay while preserving higher priority fulfillment.",
        }

    disruptions = observation.get("disruptions", [])
    if disruptions:
        return {
            "action_type": "investigate",
            "target_id": disruptions[0]["id"],
            "investigation_type": "reliability",
        }

    return {
        "action_type": "investigate",
        "target_id": "D001",
        "investigation_type": "reliability",
    }


# ─────────────────────────────────────────
# ENVIRONMENT CLIENT
# ─────────────────────────────────────────

def env_reset(task_id: str) -> dict:
    """Call environment reset endpoint"""
    response = httpx.post(
        f"{ENV_BASE_URL}/reset",
        params={"task_id": task_id},
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()


def env_step(action: dict) -> dict:
    """Call environment step endpoint"""
    response = httpx.post(
        f"{ENV_BASE_URL}/step",
        json=action,
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()


def env_grade() -> dict:
    """Call environment grade endpoint"""
    response = httpx.get(
        f"{ENV_BASE_URL}/grade",
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()


# ─────────────────────────────────────────
# PROMPT BUILDER
# ─────────────────────────────────────────

def build_system_prompt() -> str:
    return """You are an expert supply chain operations manager.
Your job is to manage supply chain disruptions by taking actions to protect orders and minimize revenue loss.

AVAILABLE ACTIONS:
1. reroute     — Move an order to a different supplier
   Required: action_type, order_id, new_supplier_id
   Optional: shipping_method (air/sea/rail/truck)

2. substitute  — Replace product with alternative
   Required: action_type, order_id, alternative_product
   Optional: notify_customer (true/false)

3. delay       — Push order deadline back
   Required: action_type, order_id, delay_days
   Optional: reason

4. cancel      — Cancel order entirely (last resort)
   Required: action_type, order_id
   Optional: reason

5. escalate    — Escalate disruption to management
   Required: action_type, disruption_id, escalation_priority (low/medium/high/critical)
   Optional: escalation_message

6. investigate — Get more info about supplier or disruption
   Required: action_type, target_id
   Optional: investigation_type (reliability/capacity/cost)

STRATEGY GUIDELINES:
- Prioritize HIGH priority orders first
- Check supplier lead_time_days vs order deadline_days before rerouting
- Check supplier capacity_available vs order quantity
- Consider cost_multiplier impact on budget
- Avoid suppliers with reliability_score below 0.75
- If reliability is UNKNOWN, investigate before committing unless no better option exists
- Escalate CRITICAL severity disruptions immediately
- Investigate unknown suppliers before using them
- Cancel only as absolute last resort
- Premium fast suppliers are often unaffordable under tight budgets; verify extra cost first

RESPONSE FORMAT:
You must respond with ONLY a valid JSON object. No explanation. No markdown. No thinking.
Example:
{"action_type": "reroute", "order_id": "O001", "new_supplier_id": "S004"}
"""


def build_user_prompt(
    observation: dict,
    step: int,
    recent_events: Optional[list[str]] = None,
    failed_actions: Optional[list[str]] = None,
) -> str:
    """Build a compact prompt from current observation and recent memory."""

    # Format disruptions
    disruptions_text = ""
    for d in observation.get("disruptions", []):
        status = "✅ RESOLVED" if d.get("is_resolved") else "🔴 ACTIVE"
        disruptions_text += (
            f"\n  {status} [{d['severity'].upper()}] {d['id']} — "
            f"{d['affected_supplier_name']} | "
            f"type={d['type']} | duration={d['estimated_duration_days']}d | "
            f"{clip_text(d['description'], 90)}"
        )

    orders = observation.get("orders", [])
    resolved_counts = {"fulfilled": 0, "delayed": 0, "lost": 0}
    for order in orders:
        if order["status"] in resolved_counts:
            resolved_counts[order["status"]] += 1

    # Format suppliers — show capacity clearly
    suppliers_text = ""
    for s in observation.get("available_suppliers", []):
        capacity_warning = (
            " ⚠️ LOW CAPACITY"
            if s["capacity_available"] < 5000
            else ""
        )
        reliability_score = s.get("reliability_score")
        reliability_known = s.get("reliability_known", True)
        reliability_text = (
            f"{reliability_score}"
            if reliability_known and reliability_score is not None
            else "UNKNOWN (investigate)"
        )
        suppliers_text += (
            f"\n  {s['id']} — {s['name']} ({s['location']}) | "
            f"Lead: {s['lead_time_days']}d | "
            f"Cost: {s['cost_multiplier']}x | "
            f"Reliability: {reliability_text} | "
            f"Capacity: {s['capacity_available']:,}{capacity_warning}"
        )

    # Budget
    budget = observation.get("budget", {})
    budget_text = (
        f"Total: ${budget.get('total', 0):,.0f} | "
        f"Spent: ${budget.get('spent', 0):,.0f} | "
        f"Remaining: ${budget.get('remaining', 0):,.0f}"
    )

    # Metrics
    metrics = observation.get("metrics", {})
    metrics_text = (
        f"Saved: {metrics.get('orders_saved', 0)} | "
        f"Lost: {metrics.get('orders_lost', 0)} | "
        f"Delayed: {metrics.get('orders_delayed', 0)} | "
        f"Score: {metrics.get('current_score', 0):.3f}"
    )

    # At-risk orders — highlight these
    at_risk = [
        o for o in observation.get("orders", [])
        if o["status"] == "at_risk"
    ]
    at_risk_text = ""
    if at_risk:
        at_risk_text = "\n\n🚨 ORDERS STILL NEEDING ACTION:\n"
        for o in at_risk:
            at_risk_text += (
                f"  → {o['id']} ({o['priority'].upper()}) "
                f"${o['value_usd']:,.0f} — "
                f"qty {o['quantity']:,} — "
                f"deadline {o['deadline_days']} days — "
                f"current supplier {o['current_supplier_id']}\n"
            )
        at_risk_text += (
            "\nFor each at-risk order, check which suppliers have:\n"
            "  1. capacity_available >= order quantity\n"
            "  2. lead_time_days <= deadline_days\n"
            "  3. reliability_score >= 0.75 (or investigate if unknown)\n"
        )

    recent_events_text = ""
    if recent_events:
        recent_events_text = "\n\nRECENT EPISODE MEMORY:"
        for event in recent_events[-MAX_CONTEXT_EVENTS:]:
            recent_events_text += f"\n  - {event}"

    failed_actions_text = ""
    if failed_actions:
        failed_actions_text = "\n\nDO NOT REPEAT THESE RECENT FAILURES:"
        for failure in failed_actions[-3:]:
            failed_actions_text += f"\n  - {clip_text(failure, 140)}"

    resolved_text = (
        f"Resolved orders so far: fulfilled={resolved_counts['fulfilled']}, "
        f"delayed={resolved_counts['delayed']}, lost={resolved_counts['lost']}"
    )

    return f"""STEP {step} — CURRENT SITUATION

ACTIVE DISRUPTIONS:{disruptions_text}

{at_risk_text}
{recent_events_text}
{failed_actions_text}
AVAILABLE SUPPLIERS:{suppliers_text}

BUDGET: {budget_text}
METRICS: {metrics_text}
SUMMARY: {resolved_text}
STATUS: {observation.get('message', '')}

Choose ONE action. Respond with valid JSON only.
IMPORTANT: Check capacity_available before rerouting.
If a supplier lacks capacity, is over budget, or you already tried it — pick a DIFFERENT one.
Your entire reply must be exactly one JSON object and nothing else."""


def run_agent_on_task(
    client: Optional[OpenAI],
    task_id: str,
    verbose: bool = True
) -> dict:
    """
    Run the LLM agent on one task.
    Uses conversation history so LLM remembers past actions.
    Returns final grade result.
    """
    # Reset environment
    reset_result = env_reset(task_id)
    observation  = reset_result["observation"]
    max_steps    = MAX_STEPS[task_id]

    total_reward  = 0.0
    step          = 0
    done          = False
    rewards_seen: list[float] = []

    system_prompt = build_system_prompt()

    # Track compact episode memory instead of full transcript
    recent_events = []
    failed_actions = []
    escalated_ids = set()
    fallback_used = False
    fallback_actions_used = 0
    model_actions_used = 0
    repair_attempts_used = 0
    parse_failures = 0
    model_action_rejections = 0
    task_started = False
    current_model_name = MODEL_NAME or "fallback"

    grade_result = {"score": 0.0, "passed": False, "breakdown": {}}
    log_start(task=task_id, env=BENCHMARK_NAME, model=current_model_name)
    task_started = True

    try:
        while not done and step < max_steps:
            step += 1
            action_source = "model"

            user_message = build_user_prompt(
                observation,
                step,
                recent_events=recent_events,
                failed_actions=failed_actions,
            )
            conversation = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]

            action_dict = None
            raw_action = ""

            if client is not None:
                try:
                    action_dict, raw_action, used_repair = request_model_action(
                        client=client,
                        conversation=conversation,
                        verbose=verbose,
                    )
                    if used_repair:
                        repair_attempts_used += 1
                    if action_dict is None:
                        parse_failures += 1
                except Exception as e:
                    raw_action = clip_text(str(e), 200)

            if action_dict is None:
                if STRICT_BASELINE:
                    break
                fallback_used = True
                fallback_actions_used += 1
                action_source = "fallback"
                action_dict = choose_fallback_action(observation, escalated_ids)
            else:
                is_locally_valid, rejection_reason = validate_action_against_observation(
                    observation=observation,
                    action_dict=action_dict,
                )
                if not is_locally_valid:
                    model_action_rejections += 1
                    if STRICT_BASELINE:
                        break
                    fallback_used = True
                    fallback_actions_used += 1
                    action_source = "fallback"
                    action_dict = choose_fallback_action(observation, escalated_ids)
                else:
                    model_actions_used += 1

            try:
                step_result  = env_step(action_dict)
                observation  = step_result["observation"]
                reward       = step_result["reward"]
                done         = step_result["done"]

                reward_val    = reward["value"]
                total_reward += reward_val
                rewards_seen.append(reward_val)
                reason        = reward["reason"]
                error_value   = reward.get("invalid_reason")

                if reward_val < 0 or not reward.get("action_valid", True):
                    fail_summary = (
                        f"Step {step}: {json.dumps(action_dict)} "
                        f"→ FAILED ({reason[:60]})"
                    )
                    failed_actions.append(fail_summary)

                recent_events.append(
                    build_recent_event_summary(
                        step=step,
                        action_dict=action_dict,
                        reward_value=reward_val,
                        reason=reason,
                        source=action_source,
                    )
                )
                recent_events = recent_events[-MAX_CONTEXT_EVENTS:]

                log_step(
                    step=step,
                    action=_format_action_str(action_dict),
                    reward=reward_val,
                    done=done,
                    error=error_value,
                )

                time.sleep(0.3)

            except Exception as e:
                log_step(
                    step=step,
                    action=_format_action_str(action_dict),
                    reward=0.0,
                    done=False,
                    error=str(e),
                )
                break

        try:
            grade_result = env_grade()
        except Exception:
            grade_result = {"score": 0.0, "passed": False, "breakdown": {}}
    finally:
        if task_started:
            log_end(
                success=bool(grade_result.get("passed", False)),
                steps=step,
                score=float(grade_result.get("score", 0.0)),
                rewards=rewards_seen,
            )

    execution_mode = classify_execution_mode(
        model_actions_used=model_actions_used,
        fallback_actions_used=fallback_actions_used,
        parse_failures=parse_failures,
        model_action_rejections=model_action_rejections,
    )
    return {
        "task_id":      task_id,
        "steps_taken":  step,
        "total_reward": round(total_reward, 4),
        "score":        grade_result["score"],
        "passed":       grade_result["passed"],
        "breakdown":    grade_result.get("breakdown", {}),
        "fallback_used": fallback_used,
        "fallback_actions_used": fallback_actions_used,
        "model_actions_used": model_actions_used,
        "repair_attempts_used": repair_attempts_used,
        "parse_failures": parse_failures,
        "model_action_rejections": model_action_rejections,
        "execution_mode": execution_mode,
    }


# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────

def main():
    # ── Verify environment is up ───────────────
    try:
        response = httpx.get(f"{ENV_BASE_URL}/", timeout=10.0)
        response.raise_for_status()
    except Exception as e:
        print(f"environment_not_reachable: {str(e)}", file=sys.stderr, flush=True)
        sys.exit(1)

    # ── Setup LLM client ───────────────────────
    client = None
    if HF_TOKEN:
        try:
            client = get_llm_client()
        except Exception as e:
            print(f"client_setup_fallback: {clip_text(str(e), 200)}", file=sys.stderr, flush=True)
    else:
        print("client_setup_fallback: no_api_token_found", file=sys.stderr, flush=True)

    # ── Run all 3 tasks ────────────────────────
    results     = []
    start_time  = time.time()

    for task_id in TASK_IDS:
        try:
            result = run_agent_on_task(client, task_id, verbose=True)
            results.append(result)
        except Exception as e:
            results.append({
                "task_id":      task_id,
                "steps_taken":  0,
                "total_reward": 0.0,
                "score":        0.0,
                "passed":       False,
                "breakdown":    {},
            })

        # Small pause between tasks
        time.sleep(1.0)

    elapsed = time.time() - start_time

    summary = summarize_results(results, elapsed)
    print(json.dumps(summary, sort_keys=True), file=sys.stderr, flush=True)

    return results


if __name__ == "__main__":
    main()
