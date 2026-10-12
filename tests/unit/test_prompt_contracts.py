"""Guards for the prompt rules that keep readings honest.

These check that the instructions are present, not how a model follows them;
they fail if a later edit quietly drops a rule.
"""

import unittest

from astroweave.agents.specialists import SPECIALIST_REGISTRY
from astroweave.agents.specialists.method import SPECIALIST_OUTPUT_SCHEMA
from astroweave.graphs.orchestrator.prompts import ORCHESTRATOR_SYNTHESIS_PROMPT


class SpecialistPromptContractTests(unittest.TestCase):
    def test_every_specialist_carries_the_honesty_rules(self):
        for agent in SPECIALIST_REGISTRY:
            with self.subTest(agent=agent.name):
                prompt = agent.prompt
                self.assertIn("## Honesty and accuracy", prompt)
                self.assertIn("If a fact is not in the data, do not state it", prompt.replace("\n", " "))
                self.assertIn("Do not soften, omit or bury them", prompt)
                self.assertIn("astrology cannot determine it from this chart", prompt)

    def test_every_specialist_has_both_confidence_rubrics(self):
        for agent in SPECIALIST_REGISTRY:
            with self.subTest(agent=agent.name):
                self.assertIn("Events and timing", agent.prompt)
                self.assertIn("Character, temperament and life themes", agent.prompt)
                self.assertIn("at least two independent", agent.prompt.replace("\n", " "))

    def test_timing_is_narrowed_only_inside_the_pratyantardasha_window(self):
        prompt = SPECIALIST_REGISTRY.require("career").prompt.replace("\n", " ")
        self.assertIn("dasha.pratyantardashas", prompt)
        self.assertIn("outside that window give antardasha-level dates", prompt)

    def test_specialists_must_explain_their_confidence(self):
        self.assertIn("confidence_reason", SPECIALIST_OUTPUT_SCHEMA["required"])


class SynthesisPromptContractTests(unittest.TestCase):
    def test_synthesis_adds_nothing_and_softens_nothing(self):
        prompt = ORCHESTRATOR_SYNTHESIS_PROMPT.replace("\n", " ")
        self.assertIn("Use only what the specialists found", prompt)
        self.assertIn("Do not soften an unfavourable finding", prompt)

    def test_synthesis_explains_limits_instead_of_printing_a_label(self):
        prompt = ORCHESTRATOR_SYNTHESIS_PROMPT.replace("\n", " ")
        self.assertIn('do not print a confidence label', prompt)
        self.assertIn("If nothing meaningful limits the answer, say nothing about certainty", prompt)


if __name__ == "__main__":
    unittest.main()
