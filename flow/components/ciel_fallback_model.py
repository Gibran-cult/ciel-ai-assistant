"""Ciel Fallback Model (Langflow custom component).

The main Agent's model: DeepSeek, with Gemini answering when a DeepSeek call
fails. DeepSeek answers 503 "Service is too busy" during overload windows and
402 when the prepaid balance is empty; before v1.13.0 the whole app was down in
both cases.

The fallback is attached in bind_tools, because Langflow's Agent only accepts a
connected BaseLanguageModel (a plain .with_fallbacks() wrapper is rejected) and
LangChain's create_agent calls bind_tools on every model call. So each model
call falls back on its own: a run can switch to Gemini mid-way and keep the tool
results it already has. Once DeepSeek has failed in a run, the later calls of
that run go straight to Gemini, because an overload lasts minutes.

Both models' errors are logged. When Gemini fails too, the error raised (and
shown in Langflow's HTTP 500 detail) starts with MODEL_UNAVAILABLE, which the
app reads to tell the user the model is busy.

Tested 2026-11-03 on a test copy with DeepSeek forced to fail:
gemini-3.5-flash-lite answered 16/16 cases with the right tools 15/16
(median 9.3 s); gemini-3.5-flash and gemini-3.8-flash timed out on this key.
"""

from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langflow.base.models.model import LCModelComponent
from langflow.field_typing import LanguageModel
from langflow.field_typing.range_spec import RangeSpec
from langflow.io import DictInput, IntInput, SecretStrInput, SliderInput, StrInput
from langflow.logging.logger import logger
from lfx.utils.ssrf_httpx import ssrf_protected_openai_clients_for_url
from pydantic.v1 import SecretStr

# Same text in app.py (components cannot import the app).
MODEL_UNAVAILABLE = "Ciel model unavailable"

# A non-streamed DeepSeek answer arrives in one piece, so the timeout must fit
# a whole answer (whole runs took at most 21 s in the 2026-11-03 tests). No
# retries: an overload lasts minutes and the fallback answers in about 10 s
# (with the SDK's default 2 retries a 503 took 55-113 s to surface).
PRIMARY_TIMEOUT = 60
PRIMARY_MAX_RETRIES = 0
FALLBACK_TIMEOUT = 60
FALLBACK_MAX_RETRIES = 1
FALLBACK_THINKING_LEVEL = "low"

# Keyword arguments every provider's bind_tools understands.
PORTABLE_BIND_KWARGS = ("tool_choice",)


def unavailable(model, error):
    return RuntimeError(f"{MODEL_UNAVAILABLE}: {model} failed: {type(error).__name__}: {error}")


class GeminiFallback(ChatGoogleGenerativeAI):
    """Gemini that logs its failures and marks them for the app."""

    def _failed(self, error):
        logger.error(f"Ciel Fallback Model: {self.model} failed too: {type(error).__name__}: {error}")
        return unavailable(self.model, error)

    def _generate(self, *args, **kwargs):
        try:
            return super()._generate(*args, **kwargs)
        except Exception as error:
            raise self._failed(error) from error

    async def _agenerate(self, *args, **kwargs):
        try:
            return await super()._agenerate(*args, **kwargs)
        except Exception as error:
            raise self._failed(error) from error

    def _stream(self, *args, **kwargs):
        try:
            yield from super()._stream(*args, **kwargs)
        except Exception as error:
            raise self._failed(error) from error

    async def _astream(self, *args, **kwargs):
        try:
            async for chunk in super()._astream(*args, **kwargs):
                yield chunk
        except Exception as error:
            raise self._failed(error) from error


class ChatOpenAIWithFallback(ChatOpenAI):
    fallback_model: Any = None
    primary_failed: bool = False

    def bind_tools(self, tools, **kwargs):
        if self.fallback_model is None:
            return super().bind_tools(tools, **kwargs)
        portable = {key: value for key, value in kwargs.items() if key in PORTABLE_BIND_KWARGS}
        backup = self.fallback_model.bind_tools(tools, **portable)
        if self.primary_failed:
            return backup
        return super().bind_tools(tools, **kwargs).with_fallbacks([backup])

    def _failed(self, error):
        # With streaming, _generate runs _stream, so one failure passes here twice.
        if not self.primary_failed:
            backup = getattr(self.fallback_model, "model", "no fallback")
            logger.warning(
                f"Ciel Fallback Model: {self.model_name} failed, answering with {backup}: "
                f"{type(error).__name__}: {error}"
            )
        self.primary_failed = True
        return unavailable(self.model_name, error)

    def _generate(self, *args, **kwargs):
        try:
            return super()._generate(*args, **kwargs)
        except Exception as error:
            raise self._failed(error) from error

    async def _agenerate(self, *args, **kwargs):
        try:
            return await super()._agenerate(*args, **kwargs)
        except Exception as error:
            raise self._failed(error) from error

    def _stream(self, *args, **kwargs):
        try:
            yield from super()._stream(*args, **kwargs)
        except Exception as error:
            raise self._failed(error) from error

    async def _astream(self, *args, **kwargs):
        try:
            async for chunk in super()._astream(*args, **kwargs):
                yield chunk
        except Exception as error:
            raise self._failed(error) from error


class CielFallbackModel(LCModelComponent):
    display_name = "Ciel Fallback Model"
    description = "DeepSeek untuk Agent utama, dengan Gemini sebagai cadangan saat DeepSeek gagal."
    icon = "DeepSeek"
    name = "CielFallbackModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        StrInput(name="model_name", display_name="DeepSeek Model", value="deepseek-flash"),
        StrInput(name="api_base", display_name="DeepSeek API Base", value="https://api.deepseek.com", advanced=True),
        SecretStrInput(name="api_key", display_name="DeepSeek API Key", value="DEEPSEEK_API_KEY", required=True),
        DictInput(name="model_kwargs", display_name="DeepSeek Model Kwargs", advanced=True),
        SliderInput(
            name="temperature",
            display_name="DeepSeek Temperature",
            value=1.0,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            advanced=True,
        ),
        IntInput(name="seed", display_name="Seed", value=1, advanced=True),
        StrInput(name="fallback_model_name", display_name="Gemini Fallback Model", value="gemini-3.5-flash-lite"),
        SecretStrInput(name="fallback_api_key", display_name="Gemini API Key", value="GEMINI_API_KEY", required=True),
    ]

    def build_model(self) -> LanguageModel:
        # Langflow keeps only imports and definitions from component code and
        # runs them in its own namespace, so pydantic cannot resolve the field
        # annotations of these subclasses by itself.
        for model_class in (GeminiFallback, ChatOpenAIWithFallback):
            model_class.model_rebuild(force=True, _types_namespace={"Any": Any})

        fallback = GeminiFallback(
            model=self.fallback_model_name,
            google_api_key=SecretStr(self.fallback_api_key).get_secret_value(),
            timeout=FALLBACK_TIMEOUT,
            max_retries=FALLBACK_MAX_RETRIES,
            thinking_level=FALLBACK_THINKING_LEVEL,
        )
        api_key = SecretStr(self.api_key).get_secret_value() if self.api_key else None
        return ChatOpenAIWithFallback(
            model=self.model_name,
            temperature=self.temperature if self.temperature is not None else 1.0,
            model_kwargs=self.model_kwargs or {},
            base_url=self.api_base,
            api_key=api_key,
            streaming=self.stream if hasattr(self, "stream") else False,
            seed=self.seed,
            timeout=PRIMARY_TIMEOUT,
            max_retries=PRIMARY_MAX_RETRIES,
            fallback_model=fallback,
            **ssrf_protected_openai_clients_for_url(self.api_base),
        )
