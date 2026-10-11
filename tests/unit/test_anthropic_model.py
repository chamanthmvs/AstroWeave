import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from langchain_core.messages import HumanMessage, SystemMessage

from astroweave.common.llm import invoke_json_response
from astroweave.common.llm.anthropic_model import (
    REFUSAL_FALLBACK_BETA,
    AnthropicChatModel,
    ClaudeRefusalError,
)


def _client_returning(message):
    client = MagicMock()
    stream = client.beta.messages.stream.return_value.__enter__.return_value
    stream.get_final_message.return_value = message
    return client


def _message(text, stop_reason="end_turn"):
    return SimpleNamespace(
        content=[
            SimpleNamespace(type="thinking", thinking=""),
            SimpleNamespace(type="text", text=text),
        ],
        stop_reason=stop_reason,
        stop_details=None,
        model="claude-opus-5-5",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0),
    )


class AnthropicChatModelTests(unittest.TestCase):
    def test_request_shape_for_current_claude_models(self):
        client = _client_returning(_message("hello"))
        model = AnthropicChatModel("claude-opus-5-5", max_tokens=64000, effort="high", client=client)

        response = model.invoke([SystemMessage(content="system brief"), HumanMessage(content="question")])

        self.assertEqual(response.content, "hello")  # thinking blocks are skipped
        request = client.beta.messages.stream.call_args.kwargs
        self.assertEqual(request["model"], "claude-opus-5-5")
        self.assertEqual(request["max_tokens"], 64000)
        self.assertEqual(request["thinking"], {"type": "adaptive"})
        self.assertEqual(request["output_config"], {"effort": "high"})
        self.assertEqual(request["messages"], [{"role": "user", "content": "question"}])
        self.assertEqual(request["system"][0]["text"], "system brief")
        self.assertEqual(request["system"][0]["cache_control"], {"type": "ephemeral"})
        self.assertEqual(request["betas"], [REFUSAL_FALLBACK_BETA])
        self.assertEqual(request["fallbacks"], "default")
        self.assertNotIn("temperature", request)  # rejected by current Claude models

    def test_fallbacks_are_only_sent_to_models_that_accept_them(self):
        for model_id, expects_fallback in [
            ("claude-sonnet-5-5", True),
            ("claude-sonnet-5", False),
            ("claude-sonnet-4-6", False),
            ("claude-haiku-5-5", False),
        ]:
            client = _client_returning(_message("ok"))
            AnthropicChatModel(model_id, 64000, "high", client=client).invoke([HumanMessage(content="q")])
            request = client.beta.messages.stream.call_args.kwargs
            self.assertEqual("fallbacks" in request, expects_fallback, model_id)
            self.assertEqual("betas" in request, expects_fallback, model_id)

    def test_json_schema_becomes_a_structured_output(self):
        client = _client_returning(_message('{"analysis": "a"}'))
        model = AnthropicChatModel("claude-opus-5-5", 64000, "high", client=client)
        schema = {"type": "object", "properties": {"analysis": {"type": "string"}}}

        parsed = invoke_json_response("node", model, [HumanMessage(content="q")], json_schema=schema)

        self.assertEqual(parsed, {"analysis": "a"})
        output_config = client.beta.messages.stream.call_args.kwargs["output_config"]
        self.assertEqual(output_config["format"], {"type": "json_schema", "schema": schema})

    def test_refusal_raises_instead_of_returning_empty_text(self):
        client = _client_returning(_message("", stop_reason="refusal"))
        model = AnthropicChatModel("claude-opus-5-5", 64000, "high", client=client)

        with self.assertRaises(ClaudeRefusalError):
            model.invoke([HumanMessage(content="q")])

    def test_missing_credentials_become_a_clear_configuration_error(self):
        from astroweave.common.llm.anthropic_model import ClaudeConfigurationError

        client = MagicMock()
        client.beta.messages.stream.side_effect = TypeError(
            "Could not resolve authentication method. Expected one of api_key ..."
        )
        model = AnthropicChatModel("claude-opus-5-5", 64000, "high", client=client)

        with self.assertRaisesRegex(ClaudeConfigurationError, "ANTHROPIC_API_KEY"):
            model.invoke([HumanMessage(content="q")])

    def test_providers_without_schema_support_get_a_plain_invoke(self):
        llm = MagicMock()  # MagicMock attributes are truthy but not `True`
        llm.invoke.return_value = MagicMock(content='{"reasoning": "r"}')

        invoke_json_response("node", llm, ["m"], json_schema={"type": "object"})

        llm.invoke.assert_called_once_with(["m"])


if __name__ == "__main__":
    unittest.main()
