"""LLM Factory: Provides resilient fallback across Groq, Gemini, and OpenAI models in strict order."""

from __future__ import annotations

import os
import time
import logging
from typing import Any, List, Optional
from dotenv import load_dotenv

from langchain_core.language_models.chat_models import BaseChatModel

logger = logging.getLogger(__name__)


def _load_all_dotenv() -> None:
    """Ensure .env is loaded from current working directory and parent directories."""
    load_dotenv(override=True)
    for env_path in [".env", "../.env", "../../.env"]:
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)


class ResilientFallbackModel(BaseChatModel):
    """Model wrapper that tries LLM providers sequentially in order: Groq -> Gemini -> OpenAI."""

    models: List[Any]

    def _generate(self, messages: Any, stop: Any = None, **kwargs: Any) -> Any:
        last_error = None
        for i, model in enumerate(self.models):
            try:
                return model._generate(messages, stop=stop, **kwargs)
            except Exception as exc:
                last_error = exc
                model_name = getattr(model, "model", getattr(model, "model_name", type(model).__name__))
                logger.warning(
                    "LLM provider %d (%s) failed with error: %s. Falling back to next provider...",
                    i + 1,
                    model_name,
                    exc,
                )
        if last_error:
            raise last_error
        raise RuntimeError("No LLM models available in fallback chain.")

    def invoke(self, input: Any, config: Any = None, **kwargs: Any) -> Any:
        last_error = None
        for i, model in enumerate(self.models):
            try:
                return model.invoke(input, config=config, **kwargs)
            except Exception as exc:
                last_error = exc
                model_name = getattr(model, "model", getattr(model, "model_name", type(model).__name__))
                logger.warning(
                    "LLM provider %d (%s) failed invoke: %s. Falling back to next provider...",
                    i + 1,
                    model_name,
                    exc,
                )
        if last_error:
            raise last_error
        raise RuntimeError("No LLM models available in fallback chain.")

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Any:
        structured_models = []
        for model in self.models:
            try:
                structured_models.append(model.with_structured_output(schema, **kwargs))
            except Exception as exc:
                logger.debug("Failed with_structured_output on %s: %s", model, exc)
                structured_models.append(model)
        return ResilientFallbackModel(models=structured_models)

    @property
    def _llm_type(self) -> str:
        return "resilient_ordered_fallback"


def get_ordered_llm(model: Optional[str] = None, temperature: float = 0.1) -> BaseChatModel:
    """Return an LLM instance ordered by priority: Groq -> Gemini -> OpenAI.

    If any provider hits a rate limit or API key error, execution automatically
    falls back to the next provider in the chain.
    """
    _load_all_dotenv()

    models: List[BaseChatModel] = []

    # 1. Groq (Priority 1)
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        try:
            from langchain_groq import ChatGroq
            groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
            models.append(
                ChatGroq(
                    model=groq_model,
                    groq_api_key=groq_key,
                    temperature=temperature,
                    max_retries=0,
                )
            )
            logger.info("Configured Groq LLM (%s) as Priority 1", groq_model)
        except Exception as exc:
            logger.warning("Failed to initialize Groq LLM: %s", exc)

    # 2. Gemini (Priority 2)
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if gemini_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
            models.append(
                ChatGoogleGenerativeAI(
                    model=gemini_model,
                    google_api_key=gemini_key,
                    temperature=temperature,
                    max_retries=0,
                )
            )
            logger.info("Configured Gemini LLM (%s) as Priority 2", gemini_model)
        except Exception as exc:
            logger.warning("Failed to initialize Gemini LLM: %s", exc)

    # 3. OpenAI (Priority 3)
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            openai_model = model or os.getenv("MODEL", "gemini-2.5-flash")
            models.append(
                ChatOpenAI(
                    model=openai_model,
                    api_key=openai_key,
                    base_url=base_url,
                    temperature=temperature,
                    max_retries=0,
                )
            )
            logger.info("Configured OpenAI LLM (%s) as Priority 3", openai_model)
        except Exception as exc:
            logger.warning("Failed to initialize OpenAI LLM: %s", exc)

    if not models:
        raise RuntimeError("No valid LLM API keys found (checked GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY).")

    if len(models) == 1:
        return models[0]

    return ResilientFallbackModel(models=models)
