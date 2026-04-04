import unittest

from backend.app.environment.engine import SupplyChainEngine
from backend.app.rl.action_catalog import ACTION_CATALOG_SIZE, build_action_catalog
from backend.app.rl.encoding import OBSERVATION_VECTOR_LENGTH, encode_observation


class RLFoundationTests(unittest.TestCase):
    def setUp(self):
        self.engine = SupplyChainEngine()

    def test_encoded_observation_has_stable_length(self):
        easy_obs = self.engine.reset("task_easy")
        easy_encoded = encode_observation(easy_obs)
        self.assertEqual(len(easy_encoded), OBSERVATION_VECTOR_LENGTH)

        hard_obs = self.engine.reset("task_hard")
        hard_encoded = encode_observation(hard_obs)
        self.assertEqual(len(hard_encoded), OBSERVATION_VECTOR_LENGTH)

    def test_action_catalog_is_fixed_size(self):
        observation = self.engine.reset("task_medium")
        catalog = build_action_catalog(observation)
        self.assertEqual(len(catalog), ACTION_CATALOG_SIZE)

    def test_hard_catalog_prioritizes_hidden_supplier_investigation(self):
        observation = self.engine.reset("task_hard")
        catalog = build_action_catalog(observation)
        self.assertTrue(any(
            action.get("action_type") == "investigate" and action.get("target_id") == "S005_ALT"
            for action in catalog[:20]
        ))

    def test_easy_catalog_contains_expected_reroute(self):
        observation = self.engine.reset("task_easy")
        catalog = build_action_catalog(observation)
        self.assertTrue(any(
            action.get("action_type") == "reroute" and action.get("order_id") == "O001"
            for action in catalog
        ))


if __name__ == "__main__":
    unittest.main()
