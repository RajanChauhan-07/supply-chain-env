import unittest

from backend.app.environment.engine import SupplyChainEngine
from backend.app.models import Action


class EnvironmentEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = SupplyChainEngine()

    def test_initial_grade_is_zero_for_all_tasks(self):
        for task_id in ["task_easy", "task_medium", "task_hard"]:
            with self.subTest(task_id=task_id):
                self.engine.reset(task_id)
                result = self.engine.grade()
                self.assertEqual(result["score"], 0.0)

    def test_easy_reroute_can_complete_episode_with_full_score(self):
        self.engine.reset("task_easy")
        result = self.engine.step(
            Action(action_type="reroute", order_id="O001", new_supplier_id="S004")
        )

        self.assertTrue(result["done"])
        self.assertEqual(result["observation"].orders[0].current_supplier_id, "S004")
        self.assertEqual(self.engine.grade()["score"], 1.0)

    def test_invalid_action_returns_negative_reward_without_finishing(self):
        self.engine.reset("task_easy")
        result = self.engine.step(
            Action(action_type="reroute", order_id="O001", new_supplier_id="S999")
        )

        self.assertFalse(result["done"])
        self.assertFalse(result["reward"].action_valid)
        self.assertLess(result["reward"].value, 0.0)

    def test_hard_task_escalations_only_give_partial_credit(self):
        self.engine.reset("task_hard")
        for disruption_id in ["D002", "D005", "D006"]:
            self.engine.step(
                Action(
                    action_type="escalate",
                    disruption_id=disruption_id,
                    escalation_priority="critical",
                )
            )

        grade = self.engine.grade()
        self.assertEqual(grade["score"], 0.1)
        self.assertEqual(grade["breakdown"]["escalation_decisions"], 0.1)

    def test_hard_task_hides_supplier_reliability_until_investigated(self):
        observation = self.engine.reset("task_hard")
        hidden_supplier = next(
            supplier for supplier in observation.available_suppliers if supplier.id == "S005_ALT"
        )
        self.assertIsNone(hidden_supplier.reliability_score)
        self.assertFalse(hidden_supplier.reliability_known)

        self.engine.step(Action(action_type="investigate", target_id="S005_ALT"))
        updated_observation = self.engine.state()
        revealed_supplier = next(
            supplier for supplier in updated_observation.available_suppliers if supplier.id == "S005_ALT"
        )
        self.assertEqual(revealed_supplier.reliability_score, 0.45)
        self.assertTrue(revealed_supplier.reliability_known)

    def test_hard_task_status_message_mentions_escalation_and_investigation(self):
        observation = self.engine.reset("task_hard")
        self.assertIn("escalate critical disruptions", observation.message)
        self.assertIn("investigate hidden-risk suppliers", observation.message)


if __name__ == "__main__":
    unittest.main()
