import os
import unittest
from unittest.mock import patch

from astroweave.common.llm.config import resolve_llm_config

# Blank values count as unset, isolating tests from a local .env file.
_UNSET = {
    "ASTROWEAVE_LLM_PROVIDER": "",
    "ASTROWEAVE_LLM_MODEL": "",
    "ASTROWEAVE_LLM_MAX_TOKENS": "",
    "ASTROWEAVE_LLM_EFFORT": "",
}


class LLMConfigTests(unittest.TestCase):
    def test_defaults_to_claude_opus(self):
        with patch.dict(os.environ, _UNSET):
            config = resolve_llm_config("specialist", agent_name="career")

        self.assertEqual(config.provider, "anthropic")
        self.assertEqual(config.model, "claude-opus-5-5")
        # Thinking counts toward max_tokens, so Claude gets a large ceiling.
        self.assertEqual(config.max_tokens, 64000)

    def test_non_claude_providers_keep_the_4096_completion_budget(self):
        with patch.dict(os.environ, {**_UNSET, "ASTROWEAVE_LLM_PROVIDER": "groq"}):
            config = resolve_llm_config("specialist", agent_name="career")

        self.assertEqual(config.model, "openai/gpt-oss-120b")
        self.assertEqual(config.max_tokens, 4096)

    def test_agent_completion_budget_overrides_role_and_global_values(self):
        with patch.dict(
            os.environ,
            {
                "ASTROWEAVE_LLM_MAX_TOKENS": "1024",
                "ASTROWEAVE_LLM_MAX_TOKENS_SPECIALIST": "2048",
                "ASTROWEAVE_LLM_MAX_TOKENS_CAREER": "8192",
            },
        ):
            config = resolve_llm_config("specialist", agent_name="career")

        self.assertEqual(config.max_tokens, 8192)

    def test_effort_defaults_per_role_and_can_be_overridden(self):
        with patch.dict(os.environ, _UNSET):
            self.assertEqual(resolve_llm_config("specialist", agent_name="love").effort, "high")
            self.assertEqual(resolve_llm_config("orchestrator").effort, "medium")
        with patch.dict(os.environ, {**_UNSET, "ASTROWEAVE_LLM_EFFORT_LOVE": "xhigh"}):
            self.assertEqual(resolve_llm_config("specialist", agent_name="love").effort, "xhigh")


if __name__ == "__main__":
    unittest.main()
