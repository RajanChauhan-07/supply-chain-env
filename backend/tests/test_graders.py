import unittest

from backend.app.environment.engine import SupplyChainEngine
from backend.app.models import Action
from inference import choose_fallback_action


class GraderTests(unittest.TestCase):
    def setUp(self):
        self.engine = SupplyChainEngine()

    def test_all_task_scores_stay_in_unit_interval(self):
        for task_id in ["task_easy", "task_medium", "task_hard"]:
            with self.subTest(task_id=task_id):
                self.engine.reset(task_id)
                grade = self.engine.grade()
                self.assertGreaterEqual(grade["score"], 0.0)
                self.assertLessEqual(grade["score"], 1.0)

    def test_grading_is_deterministic_for_easy_solution(self):
        scores = []
        for _ in range(2):
            self.engine.reset("task_easy")
            self.engine.step(
                Action(action_type="reroute", order_id="O001", new_supplier_id="S004")
            )
            scores.append(self.engine.grade()["score"])

        self.assertEqual(scores, [1.0, 1.0])

    def test_medium_task_solution_produces_passing_score(self):
        self.engine.reset("task_medium")
        for action in [
            Action(action_type="reroute", order_id="O003", new_supplier_id="S004"),
            Action(action_type="reroute", order_id="O001", new_supplier_id="S007"),
            Action(action_type="delay", order_id="O002", delay_days=7, reason="budget constraint"),
            Action(action_type="delay", order_id="O005", delay_days=7, reason="budget constraint"),
        ]:
            result = self.engine.step(action)
            if result["done"]:
                break

        grade = self.engine.grade()
        self.assertTrue(grade["passed"])
        self.assertGreaterEqual(grade["score"], 0.45)

    def test_hard_task_fallback_style_sequence_passes(self):
        observation = self.engine.reset("task_hard").model_dump()
        escalated_ids = set()

        for _ in range(40):
            action = Action(**choose_fallback_action(observation, escalated_ids))
            result = self.engine.step(action)
            observation = result["observation"].model_dump()
            if result["done"]:
                break

        grade = self.engine.grade()
        self.assertTrue(grade["passed"])
        self.assertGreaterEqual(grade["score"], 0.3)
        self.assertLessEqual(grade["score"], 1.0)

    def test_hard_task_score_breakdown_includes_optional_diagnostics(self):
        observation = self.engine.reset("task_hard").model_dump()
        escalated_ids = set()

        for _ in range(40):
            action = Action(**choose_fallback_action(observation, escalated_ids))
            result = self.engine.step(action)
            observation = result["observation"].model_dump()
            if result["done"]:
                break

        state = self.engine.state()
        self.assertIsNotNone(state.score_breakdown)
        self.assertIn("invalid_action_count", state.score_breakdown)
        self.assertIn("investigation_count", state.score_breakdown)
        self.assertIn("hidden_risk_suppliers_investigated", state.score_breakdown)
        self.assertIn("hidden_risk_supplier_used", state.score_breakdown)


if __name__ == "__main__":
    unittest.main()
