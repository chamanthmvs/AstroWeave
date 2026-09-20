import os
import unittest
from unittest.mock import patch

from astroweave.common.llm.config import resolve_llm_config


class LLMConfigTests(unittest.TestCase):
    def test_default_completion_budget_is_4096(self):
        with patch.dict(os.environ, {"ASTROWEAVE_LLM_MAX_TOKENS": ""}):
            config = resolve_llm_config("specialist", agent_name="career")

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


if __name__ == "__main__":
    unittest.main()