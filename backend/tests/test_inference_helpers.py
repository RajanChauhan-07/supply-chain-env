import unittest
from io import StringIO
from contextlib import redirect_stdout

from inference import (
    build_completion_kwargs,
    build_recent_event_summary,
    build_user_prompt,
    classify_execution_mode,
    choose_fallback_action,
    extract_json_candidates,
    infer_action_from_prose,
    log_end,
    log_start,
    log_step,
    normalize_action_payload,
    parse_action_response,
    summarize_results,
    validate_action_against_observation,
)


class InferenceHelperTests(unittest.TestCase):
    def test_log_helpers_match_sample_stdout_contract(self):
        stream = StringIO()
        with redirect_stdout(stream):
            log_start("task_easy", "supply-chain-disruption-env", "openai/gpt-4o")
            log_step(1, '{"action_type":"investigate","target_id":"D001"}', 0.05, False, None)
            log_end(True, 1, 0.83, [0.05, 0.78])
        output = stream.getvalue().strip().splitlines()
        self.assertEqual(
            output[0],
            "[START] task=task_easy env=supply-chain-disruption-env model=openai/gpt-4o",
        )
        self.assertEqual(
            output[1],
            '[STEP] step=1 action={"action_type":"investigate","target_id":"D001"} reward=0.05 done=false error=null',
        )
        self.assertEqual(
            output[2],
            "[END] success=true steps=1 score=0.830 rewards=0.05,0.78",
        )

    def test_build_completion_kwargs_uses_gpt5_token_field(self):
        from inference import MODEL_NAME as original_model_name
        import inference

        inference.MODEL_NAME = "openai/gpt-5.2"
        kwargs = build_completion_kwargs([{"role": "user", "content": "hi"}], max_tokens=123)
        self.assertIn("max_completion_tokens", kwargs)
        self.assertNotIn("max_tokens", kwargs)
        inference.MODEL_NAME = original_model_name

    def test_build_completion_kwargs_uses_standard_token_field(self):
        from inference import MODEL_NAME as original_model_name
        import inference

        inference.MODEL_NAME = "openai/gpt-4o"
        kwargs = build_completion_kwargs([{"role": "user", "content": "hi"}], max_tokens=123)
        self.assertIn("max_tokens", kwargs)
        self.assertNotIn("max_completion_tokens", kwargs)
        inference.MODEL_NAME = original_model_name

    def test_parse_plain_json_action(self):
        raw = '{"action_type":"reroute","order_id":"O001","new_supplier_id":"S004"}'
        parsed = parse_action_response(raw)
        self.assertEqual(parsed["action_type"], "reroute")
        self.assertEqual(parsed["order_id"], "O001")

    def test_parse_fenced_json_action(self):
        raw = '```json\n{"action_type":"investigate","target_id":"D001"}\n```'
        parsed = parse_action_response(raw)
        self.assertEqual(parsed["action_type"], "investigate")
        self.assertEqual(parsed["target_id"], "D001")

    def test_parse_embedded_json_action(self):
        raw = (
            "We should escalate first.\n"
            '{"action_type":"escalate","disruption_id":"D002","escalation_priority":"critical"}'
        )
        parsed = parse_action_response(raw)
        self.assertEqual(parsed["action_type"], "escalate")
        self.assertEqual(parsed["disruption_id"], "D002")

    def test_parse_wrapped_action_object(self):
        raw = '{"action":{"action_type":"delay","order_id":"O002","delay_days":7}}'
        parsed = parse_action_response(raw)
        self.assertEqual(parsed["action_type"], "delay")
        self.assertEqual(parsed["order_id"], "O002")

    def test_extract_candidates_preserves_embedded_object(self):
        raw = 'Thinking... {"action_type":"cancel","order_id":"O011","reason":"No feasible alternative"}'
        candidates = extract_json_candidates(raw)
        self.assertTrue(any('"action_type":"cancel"' in candidate for candidate in candidates))

    def test_normalize_action_payload_rejects_non_action_dict(self):
        self.assertIsNone(normalize_action_payload({"message": "hello"}))

    def test_infer_reroute_from_prose(self):
        raw = "Likely reroute O003 to supplier S004 because it arrives in time and fits capacity."
        parsed = infer_action_from_prose(raw)
        self.assertEqual(parsed["action_type"], "reroute")
        self.assertEqual(parsed["order_id"], "O003")
        self.assertEqual(parsed["new_supplier_id"], "S004")

    def test_infer_escalate_from_prose(self):
        raw = "We should escalate disruption D002 at critical priority immediately."
        parsed = infer_action_from_prose(raw)
        self.assertEqual(parsed["action_type"], "escalate")
        self.assertEqual(parsed["disruption_id"], "D002")
        self.assertEqual(parsed["escalation_priority"], "critical")

    def test_infer_delay_from_prose(self):
        raw = "Best next move is to delay O005 by 7 days while preserving higher value orders."
        parsed = infer_action_from_prose(raw)
        self.assertEqual(parsed["action_type"], "delay")
        self.assertEqual(parsed["order_id"], "O005")
        self.assertEqual(parsed["delay_days"], 7)

    def test_validate_action_against_observation_rejects_unknown_supplier(self):
        observation = {
            "orders": [{"id": "O001", "quantity": 5000, "value_usd": 250000.0}],
            "available_suppliers": [{"id": "S004", "capacity_available": 10000, "cost_multiplier": 1.1}],
            "disruptions": [],
            "budget": {"remaining": 50000.0},
        }
        valid, reason = validate_action_against_observation(
            observation,
            {"action_type": "reroute", "order_id": "O001", "new_supplier_id": "S001"},
        )
        self.assertFalse(valid)
        self.assertIn("unknown supplier_id", reason)

    def test_validate_action_against_observation_accepts_feasible_reroute(self):
        observation = {
            "orders": [{"id": "O001", "quantity": 5000, "value_usd": 250000.0}],
            "available_suppliers": [{"id": "S004", "capacity_available": 10000, "cost_multiplier": 1.1}],
            "disruptions": [],
            "budget": {"remaining": 50000.0},
        }
        valid, reason = validate_action_against_observation(
            observation,
            {"action_type": "reroute", "order_id": "O001", "new_supplier_id": "S004"},
        )
        self.assertTrue(valid)
        self.assertEqual(reason, "")

    def test_classify_execution_mode_hybrid(self):
        mode = classify_execution_mode(
            model_actions_used=2,
            fallback_actions_used=1,
            parse_failures=0,
            model_action_rejections=1,
        )
        self.assertEqual(mode, "hybrid")

    def test_summarize_results_reports_model_and_fallback_split(self):
        results = [
            {
                "task_id": "task_easy",
                "score": 1.0,
                "passed": True,
                "execution_mode": "model_only",
                "fallback_used": False,
                "fallback_actions_used": 0,
            },
            {
                "task_id": "task_medium",
                "score": 0.83,
                "passed": True,
                "execution_mode": "hybrid",
                "fallback_used": True,
                "fallback_actions_used": 2,
            },
        ]
        summary = summarize_results(results, elapsed=12.5)
        self.assertEqual(summary["fully_model_driven_tasks"], ["task_easy"])
        self.assertEqual(summary["fallback_assisted_tasks"], ["task_medium"])
        self.assertEqual(summary["execution_modes"]["task_medium"], "hybrid")
        self.assertTrue(summary["used_fallback"])

    def test_fallback_investigates_hidden_supplier_before_using_it(self):
        observation = {
            "orders": [
                {
                    "id": "O010",
                    "status": "at_risk",
                    "priority": "low",
                    "quantity": 7000,
                    "value_usd": 60000.0,
                    "deadline_days": 30,
                }
            ],
            "available_suppliers": [
                {
                    "id": "S005_ALT",
                    "capacity_available": 50000,
                    "cost_multiplier": 0.65,
                    "lead_time_days": 8,
                    "reliability_score": None,
                    "reliability_known": False,
                }
            ],
            "disruptions": [],
            "budget": {"remaining": 18000.0},
        }
        action = choose_fallback_action(observation, set())
        self.assertEqual(action["action_type"], "investigate")
        self.assertEqual(action["target_id"], "S005_ALT")

    def test_build_user_prompt_marks_unknown_reliability(self):
        observation = {
            "disruptions": [],
            "orders": [
                {
                    "id": "O012",
                    "status": "at_risk",
                    "priority": "high",
                    "quantity": 1000,
                    "value_usd": 750000.0,
                    "deadline_days": 8,
                    "current_supplier_id": "S001",
                }
            ],
            "available_suppliers": [
                {
                    "id": "S005_ALT",
                    "name": "Hidden Supplier",
                    "location": "India",
                    "lead_time_days": 8,
                    "cost_multiplier": 0.65,
                    "reliability_score": None,
                    "reliability_known": False,
                    "capacity_available": 50000,
                }
            ],
            "budget": {"total": 18000.0, "spent": 0.0, "remaining": 18000.0},
            "metrics": {"orders_saved": 0, "orders_lost": 0, "orders_delayed": 0, "current_score": 0.0},
            "message": "Hard-task guidance here.",
        }
        prompt = build_user_prompt(observation, step=1)
        self.assertIn("UNKNOWN (investigate)", prompt)
        self.assertIn("reliability_score >= 0.75 (or investigate if unknown)", prompt)

    def test_recent_event_summary_is_compact(self):
        summary = build_recent_event_summary(
            step=3,
            action_dict={"action_type": "reroute", "order_id": "O003", "new_supplier_id": "S004"},
            reward_value=0.30,
            reason="Order rerouted successfully to NorthStar Logistics under budget.",
            source="model",
        )
        self.assertIn("step 3", summary)
        self.assertIn("model", summary)
        self.assertIn("O003", summary)


if __name__ == "__main__":
    unittest.main()
