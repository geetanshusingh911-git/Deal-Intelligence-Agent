"""Unit tests for Deal Intelligence Agent backend.

Covers:
- LLM fallback and defensive JSON parsing
- Empty-recall handling and graceful degradation
- Zero-calls deal edge case
- CONTRACT.md shape compliance
"""

import unittest
from unittest.mock import MagicMock, patch

from agents import brief_agent, coach_agent
from llm import _clean_json_text, call_llm_json
from storage import get_deal, save_deal


class TestLLMFallback(unittest.TestCase):
    def test_clean_json_text_markdown_fence(self):
        """Verify markdown code fences are stripped cleanly."""
        raw = "```json\n{\"key\": \"value\"}\n```"
        self.assertEqual(_clean_json_text(raw), "{\"key\": \"value\"}")

        raw_extra = "Here is the result:\n```json\n{\"status\": \"ok\"}\n```\nHope that helps!"
        self.assertEqual(_clean_json_text(raw_extra), "{\"status\": \"ok\"}")

    @patch("llm._invoke_groq")
    def test_llm_json_fallback_on_failure(self, mock_invoke):
        """Verify that when primary LLM fails, fallback model or fallback_value is returned."""
        # Simulate primary model throwing an exception on every attempt
        mock_invoke.side_effect = RuntimeError("Service Unavailable")

        fallback = {"test_status": "fallback_applied"}
        result = call_llm_json("Return status", fallback_value=fallback)
        self.assertEqual(result, fallback)

    @patch("llm._invoke_groq")
    def test_llm_json_secondary_model_recovery(self, mock_invoke):
        """Verify cascade: primary model fails, secondary model succeeds."""
        # Fail first 2 attempts (primary model), succeed on 3rd attempt (fallback model)
        mock_invoke.side_effect = [
            RuntimeError("Rate limit"),
            RuntimeError("Rate limit"),
            "{\"recovered\": true}",
        ]
        result = call_llm_json("Test recovery")
        self.assertEqual(result.get("recovered"), True)


class TestEmptyRecallAndEdgeCases(unittest.TestCase):
    def setUp(self):
        # Create an empty deal with 0 calls
        save_deal("test-zero-calls", "Zero Calls Inc", 50000, calls=[])

    def test_zero_calls_deal_brief(self):
        """A deal with zero calls should return empty lists without raising an error."""
        brief = brief_agent("test-zero-calls", memory="on")
        self.assertEqual(brief["memory_used"], False)
        self.assertEqual(brief["recalled_facts"], [])
        self.assertEqual(brief["open_objections"], [])
        self.assertEqual(brief["stakeholders"], [])
        self.assertEqual(brief["promises"], [])
        self.assertIn("No call history", brief["brief"])

    @patch("agents.recall_facts")
    @patch("agents.coach_agent")
    def test_empty_recall_path(self, mock_coach, mock_recall):
        """When Hindsight recall returns nothing, brief_agent gracefully constructs a brief."""
        # Deal with 1 call
        deal_id = "test-empty-recall-deal"
        save_deal(
            deal_id,
            "Recall Edge Corp",
            75000,
            calls=[
                {
                    "call_no": 1,
                    "date": "2026-11-01",
                    "participants": ["Rep", "Buyer"],
                    "transcript": "Rep: Hello Buyer. Buyer: We are reviewing the budget.",
                }
            ],
        )

        mock_recall.return_value = []
        mock_coach.return_value = {"playbook_tips": []}

        brief = brief_agent(deal_id, memory="on")
        self.assertTrue(brief["memory_used"])
        self.assertIsInstance(brief["recalled_facts"], list)
        self.assertEqual(len(brief["recalled_facts"]), 0)
        self.assertIn("brief", brief)
        self.assertIn("open_objections", brief)
        self.assertIn("stakeholders", brief)
        self.assertIn("promises", brief)

    @patch("agents.recall_facts")
    @patch("agents.reflect_facts")
    def test_coach_agent_empty_playbook(self, mock_reflect, mock_recall):
        """When playbook bank is completely empty, coach_agent returns empty lists."""
        mock_recall.return_value = []
        mock_reflect.return_value = ""

        coach_data = coach_agent()
        self.assertEqual(coach_data["playbook_tips"], [])
        self.assertEqual(coach_data["insights"], [])
        self.assertEqual(coach_data["mental_models"], [])


if __name__ == "__main__":
    unittest.main()
