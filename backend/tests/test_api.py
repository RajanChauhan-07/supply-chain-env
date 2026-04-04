import unittest

from fastapi.testclient import TestClient

from backend.app.main import app


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_root_health_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "healthy")

    def test_tasks_endpoint_lists_three_tasks(self):
        response = self.client.get("/tasks")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["total"], 3)
        self.assertIn("task_easy", body["task_ids"])

    def test_reset_step_and_state_flow(self):
        reset_response = self.client.post("/reset", params={"task_id": "task_easy"})
        self.assertEqual(reset_response.status_code, 200)
        reset_body = reset_response.json()
        self.assertEqual(reset_body["task_id"], "task_easy")
        self.assertEqual(reset_body["observation"]["step"], 0)

        step_response = self.client.post(
            "/step",
            json={
                "action_type": "reroute",
                "order_id": "O001",
                "new_supplier_id": "S004",
            },
        )
        self.assertEqual(step_response.status_code, 200)
        step_body = step_response.json()
        self.assertTrue(step_body["done"])
        self.assertEqual(step_body["reward"]["action_valid"], True)

        state_response = self.client.get("/state")
        self.assertEqual(state_response.status_code, 200)
        state_body = state_response.json()
        self.assertEqual(state_body["task_id"], "task_easy")
        self.assertTrue(state_body["done"])

    def test_validate_endpoint_passes(self):
        response = self.client.get("/validate")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["all_passed"])

    def test_metadata_schema_and_mcp_endpoints_support_openenv_validator(self):
        metadata_response = self.client.get("/metadata")
        self.assertEqual(metadata_response.status_code, 200)
        metadata_body = metadata_response.json()
        self.assertIn("name", metadata_body)
        self.assertIn("description", metadata_body)

        schema_response = self.client.get("/schema")
        self.assertEqual(schema_response.status_code, 200)
        schema_body = schema_response.json()
        self.assertIn("action", schema_body)
        self.assertIn("observation", schema_body)
        self.assertIn("state", schema_body)

        mcp_response = self.client.post("/mcp", json={})
        self.assertEqual(mcp_response.status_code, 200)
        mcp_body = mcp_response.json()
        self.assertEqual(mcp_body["jsonrpc"], "2.0")
        self.assertIn("error", mcp_body)

    def test_hard_reset_hides_bad_supplier_reliability_in_observation(self):
        response = self.client.post("/reset", params={"task_id": "task_hard"})
        self.assertEqual(response.status_code, 200)
        suppliers = response.json()["observation"]["available_suppliers"]
        hidden_supplier = next(
            supplier for supplier in suppliers if supplier["id"] == "S005_ALT"
        )
        self.assertIsNone(hidden_supplier["reliability_score"])
        self.assertFalse(hidden_supplier["reliability_known"])


if __name__ == "__main__":
    unittest.main()
