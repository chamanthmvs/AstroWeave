import unittest

from astroweave.common.tools.base import (
    BaseToolReturnType,
    FunctionTool,
    ToolType,
    tool,
)
from astroweave.common.tools.registry import ToolRegistry


class SearchResult(BaseToolReturnType):
    result: str | None = None


class ToolTests(unittest.TestCase):
    def test_decorator_creates_function_tool_with_metadata(self):
        @tool(
            name="career_focus",
            description="Find the strongest career theme.",
            returns=SearchResult,
        )
        def career_focus(question: str) -> SearchResult:
            return SearchResult(success=True, result=question.upper())

        self.assertIsInstance(career_focus, FunctionTool)
        self.assertEqual(career_focus.metadata.name, "career_focus")
        self.assertEqual(career_focus.metadata.type, ToolType.FUNCTION)
        self.assertIs(career_focus.metadata.returns, SearchResult)
        self.assertEqual(career_focus("growth").result, "GROWTH")

    def test_decorator_uses_function_name_by_default(self):
        @tool(description="Check availability.")
        def availability() -> BaseToolReturnType:
            return BaseToolReturnType(success=True)

        self.assertEqual(availability.metadata.name, "availability")

    def test_function_tool_rejects_an_invalid_return_type(self):
        @tool(description="Return an invalid response.")
        def invalid_response() -> BaseToolReturnType:
            return {"success": True}  # type: ignore[return-value]

        with self.assertRaisesRegex(TypeError, "must return BaseToolReturnType"):
            invalid_response()

    def test_registry_owns_and_resolves_tools(self):
        @tool(name="career_focus", description="Find a career theme.")
        def career_focus() -> BaseToolReturnType:
            return BaseToolReturnType(success=True)

        registry = ToolRegistry([career_focus])

        self.assertIs(registry.require("career_focus"), career_focus)
        self.assertEqual(registry.metadata(), [career_focus.metadata])
        self.assertIn("career_focus", registry)

    def test_registry_rejects_duplicate_names(self):
        @tool(name="duplicate", description="First tool.")
        def first() -> BaseToolReturnType:
            return BaseToolReturnType(success=True)

        @tool(name="duplicate", description="Second tool.")
        def second() -> BaseToolReturnType:
            return BaseToolReturnType(success=True)

        with self.assertRaisesRegex(ValueError, "already registered"):
            ToolRegistry([first, second])


if __name__ == "__main__":
    unittest.main()