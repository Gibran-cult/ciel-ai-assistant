"""flow/components/ciel_fallback_model.py: DeepSeek with Gemini as the fallback."""

import asyncio
import importlib.util
import re
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / "flow" / "components" / "ciel_fallback_model.py").read_text(encoding="utf-8")

STUBBED = (
    "langchain_google_genai", "langchain_openai", "langflow", "langflow.base", "langflow.base.models",
    "langflow.base.models.model", "langflow.field_typing", "langflow.field_typing.range_spec", "langflow.io",
    "langflow.logging", "langflow.logging.logger", "lfx", "lfx.utils", "lfx.utils.ssrf_httpx",
    "pydantic", "pydantic.v1",
)


class Bound:
    def __init__(self, model, tools, kwargs):
        self.model, self.tools, self.kwargs = model, tools, kwargs

    def with_fallbacks(self, fallbacks):
        return ("with_fallbacks", self, fallbacks)


class FakeChatModel:
    """Stands in for ChatOpenAI and ChatGoogleGenerativeAI: records settings, fails on demand."""

    error = None

    def __init__(self, **kwargs):
        self.settings = kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)
        self.model_name = kwargs.get("model")

    @classmethod
    def model_rebuild(cls, **kwargs):
        pass

    def bind_tools(self, tools, **kwargs):
        return Bound(self, tools, kwargs)

    def _generate(self, *args, **kwargs):
        if self.error:
            raise self.error
        return "answer"

    async def _agenerate(self, *args, **kwargs):
        return self._generate()

    def _stream(self, *args, **kwargs):
        yield self._generate()

    async def _astream(self, *args, **kwargs):
        yield self._generate()


class Logger:
    def __init__(self):
        self.lines = []

    def warning(self, message):
        self.lines.append(("warning", message))

    def error(self, message):
        self.lines.append(("error", message))


def load_with_stubs():
    """Load the component with Langflow and LangChain replaced by fakes (CI has neither)."""

    class ChatOpenAI(FakeChatModel):
        pass

    class ChatGoogleGenerativeAI(FakeChatModel):
        pass

    class LCModelComponent:
        def __init__(self, **inputs):
            self.__dict__.update(inputs)

        @staticmethod
        def get_base_inputs():
            return []

    def spec(*args, **kwargs):
        return kwargs

    logger = Logger()
    modules = {name: types.ModuleType(name) for name in STUBBED}
    modules["langchain_openai"].ChatOpenAI = ChatOpenAI
    modules["langchain_google_genai"].ChatGoogleGenerativeAI = ChatGoogleGenerativeAI
    modules["langflow.base.models.model"].LCModelComponent = LCModelComponent
    modules["langflow.field_typing"].LanguageModel = object
    modules["langflow.field_typing.range_spec"].RangeSpec = spec
    for name in ("DictInput", "IntInput", "SecretStrInput", "SliderInput", "StrInput"):
        setattr(modules["langflow.io"], name, spec)
    modules["langflow.logging.logger"].logger = logger
    modules["lfx.utils.ssrf_httpx"].ssrf_protected_openai_clients_for_url = lambda url: {}
    modules["pydantic.v1"].SecretStr = lambda value: types.SimpleNamespace(get_secret_value=lambda: value)

    saved = {name: sys.modules.get(name) for name in STUBBED}
    sys.modules.update(modules)
    try:
        namespace = {}
        exec(compile(SOURCE, "ciel_fallback_model.py", "exec"), namespace)
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    return namespace, logger


class FallbackWiringTest(unittest.TestCase):

    def setUp(self):
        self.ns, self.logger = load_with_stubs()
        self.gemini = self.ns["GeminiFallback"](model="gemini-3.5-flash-lite")
        self.model = self.ns["ChatOpenAIWithFallback"](model="deepseek-flash", fallback_model=self.gemini)

    def test_each_model_call_falls_back_to_gemini(self):
        bound = self.model.bind_tools(["search"], tool_choice="auto", parallel_tool_calls=False)
        kind, primary, fallbacks = bound
        self.assertEqual(kind, "with_fallbacks")
        self.assertEqual(primary.kwargs, {"tool_choice": "auto", "parallel_tool_calls": False})
        self.assertIs(fallbacks[0].model, self.gemini)
        self.assertEqual(fallbacks[0].tools, ["search"])
        # OpenAI-only options are not passed to Gemini.
        self.assertEqual(fallbacks[0].kwargs, {"tool_choice": "auto"})

    def test_after_deepseek_fails_the_run_goes_straight_to_gemini(self):
        self.model.error = ConnectionError("Error code: 503 - Service is too busy")
        for _ in range(2):
            # With streaming, _generate runs _stream: one failure passes twice.
            with self.assertRaises(RuntimeError) as raised:
                self.model._generate([])
        self.assertTrue(str(raised.exception).startswith("Ciel model unavailable: deepseek-flash failed: ConnectionError"))
        self.assertIsInstance(raised.exception.__cause__, ConnectionError)
        self.assertEqual(len(self.logger.lines), 1)
        level, line = self.logger.lines[0]
        self.assertEqual(level, "warning")
        self.assertIn("deepseek-flash failed, answering with gemini-3.5-flash-lite", line)

        bound = self.model.bind_tools(["search"], tool_choice="auto")
        self.assertIsInstance(bound, Bound)
        self.assertIs(bound.model, self.gemini)

    def test_async_and_streaming_failures_are_marked_too(self):
        self.model.error = TimeoutError("Request timed out.")

        async def consume(stream):
            return [chunk async for chunk in stream]

        for call in (
            lambda: asyncio.run(self.model._agenerate([])),
            lambda: list(self.model._stream([])),
            lambda: asyncio.run(consume(self.model._astream([]))),
        ):
            with self.assertRaisesRegex(RuntimeError, "^Ciel model unavailable: deepseek-flash failed"):
                call()
        self.assertTrue(self.model.primary_failed)

    def test_a_gemini_failure_is_logged_and_marked_for_the_app(self):
        self.gemini.error = ValueError("429 RESOURCE_EXHAUSTED")
        with self.assertRaisesRegex(RuntimeError, "^Ciel model unavailable: gemini-3.5-flash-lite failed: ValueError"):
            self.gemini._generate([])
        self.assertEqual(self.logger.lines[0][0], "error")
        self.assertIn("gemini-3.5-flash-lite failed too", self.logger.lines[0][1])

    def test_working_models_answer_unchanged(self):
        self.assertEqual(self.model._generate([]), "answer")
        self.assertEqual(self.gemini._generate([]), "answer")
        self.assertFalse(self.model.primary_failed)
        self.assertEqual(self.logger.lines, [])

    def test_build_model_uses_the_tested_settings(self):
        component = self.ns["CielFallbackModel"](
            model_name="deepseek-flash", api_base="https://api.deepseek.com", api_key="ds-key",
            model_kwargs={"extra_body": {"thinking": {"type": "disabled"}}}, temperature=1, seed=1, stream=False,
            fallback_model_name="gemini-3.5-flash-lite", fallback_api_key="gm-key",
        )
        model = component.build_model()
        self.assertEqual(model.settings["timeout"], 60)
        self.assertEqual(model.settings["max_retries"], 0)
        self.assertEqual(model.settings["model_kwargs"], {"extra_body": {"thinking": {"type": "disabled"}}})
        self.assertEqual(model.settings["api_key"], "ds-key")
        gemini = model.fallback_model
        self.assertEqual(type(gemini).__name__, "GeminiFallback")
        self.assertEqual(gemini.settings, {
            "model": "gemini-3.5-flash-lite", "google_api_key": "gm-key",
            "timeout": 60, "max_retries": 1, "thinking_level": "low",
        })

    def test_app_reads_the_same_marker(self):
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        self.assertIn(f'MODEL_UNAVAILABLE = "{self.ns["MODEL_UNAVAILABLE"]}"', app)


def real_stack():
    return all(importlib.util.find_spec(name) for name in ("langchain", "langchain_openai", "langflow"))


@unittest.skipUnless(real_stack(), "needs the Langflow venv (LangChain and Langflow are not installed in CI)")
class FallbackAgentTest(unittest.TestCase):
    """The real LangChain agent loop, with an unreachable DeepSeek and a scripted fallback."""

    def test_the_agent_finishes_on_the_fallback_and_skips_deepseek_after_it_failed(self):
        from langchain.agents import create_agent
        from langchain_core.language_models import BaseLanguageModel
        from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
        from langchain_core.messages import AIMessage
        from langchain_core.tools import tool

        namespace = {}
        exec(compile(SOURCE, "ciel_fallback_model.py", "exec"), namespace)
        model_class = namespace["ChatOpenAIWithFallback"]
        model_class.model_rebuild(force=True, _types_namespace={"Any": __import__("typing").Any})

        class Scripted(FakeMessagesListChatModel):
            def bind_tools(self, tools, **kwargs):
                return self

        @tool
        def evaluate_expression(expression: str) -> str:
            """Evaluate a math expression."""
            return "434000"

        fallback = Scripted(responses=[
            AIMessage(content="", tool_calls=[{"name": "evaluate_expression", "args": {"expression": "0.175*2480000"}, "id": "c1"}]),
            AIMessage(content="Hasilnya 434.000."),
        ])
        model = model_class(model="deepseek-flash", base_url="http://127.0.0.1:9/v1", api_key="x",
                            max_retries=0, timeout=5, fallback_model=fallback)
        self.assertIsInstance(model, BaseLanguageModel)

        calls = []
        original = model_class.bind_tools

        def counting_bind_tools(self, tools, **kwargs):
            bound = original(self, tools, **kwargs)
            calls.append(type(bound).__name__)
            return bound

        model_class.bind_tools = counting_bind_tools
        try:
            agent = create_agent(model=model, tools=[evaluate_expression], system_prompt="Kamu Ciel.")
            result = agent.invoke({"messages": [("user", "Berapa 17,5% dari 2.480.000?")]})
        finally:
            model_class.bind_tools = original

        self.assertEqual(result["messages"][-1].content, "Hasilnya 434.000.")
        self.assertTrue(any(m.type == "tool" and m.content == "434000" for m in result["messages"]))
        self.assertTrue(model.primary_failed)
        # First call: DeepSeek with Gemini behind it; second call: the fallback alone.
        self.assertEqual(calls, ["RunnableWithFallbacks", "Scripted"])


if __name__ == "__main__":
    unittest.main()
