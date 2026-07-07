
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, AsyncGenerator
try:
    import google.generativeai as genai
except ImportError as exc:
    genai = None
    _GENAI_IMPORT_ERROR = exc
else:
    _GENAI_IMPORT_ERROR = None

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class LLMResponse:
    """Kết quả trả về từ Gemini, kèm metadata cơ bản."""

    content: str
    input_tokens: int
    output_tokens: int
    model: str
    duration_ms: float

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMError(Exception):
    """Base exception cho LLM client."""


class LLMConfigError(LLMError):
    """Thiếu SDK/API key hoặc config không hợp lệ."""


class LLMTimeoutError(LLMError):
    """Request vượt quá timeout."""


class LLMBlockedError(LLMError):
    """Provider không trả nội dung usable."""


class LLMTruncatedError(LLMError):
    """Output bị cắt vì vượt max_output_tokens."""


class GeminiClient:

    JSON_MIME_TYPE = "application/json"

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float,
        max_output_tokens: int,
        timeout: float,
    ) -> None:
        if genai is None:
            raise LLMConfigError(
                "google-generativeai chưa được cài đặt. "
                "Cài dependency trong requirements.txt trước khi dùng GeminiClient."
            ) from _GENAI_IMPORT_ERROR

        if not api_key:
            raise LLMConfigError(
                "GOOGLE_API_KEY chưa được cấu hình. "
                "Thêm GOOGLE_API_KEY vào file .env."
            )

        if timeout <= 0:
            raise LLMConfigError("timeout phải lớn hơn 0")

        genai.configure(api_key=api_key)

        self.model_name = model
        self.default_temperature = temperature
        self.default_max_output_tokens = max_output_tokens
        self.timeout = timeout
        self._model = genai.GenerativeModel(model_name=model)

        logger.info("GeminiClient initialized | model=%s", model)

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        response_mime_type: str | None = None,
    ) -> LLMResponse:
        model = (
            genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt,
            )
            if system_prompt
            else self._model
        )
        generation_config = self._build_generation_config(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type=response_mime_type,
        )
        
        response = await self._call_once(
            model=model,
            prompt=prompt,
            generation_config=generation_config,
        )
        logger.info("Gemini response: %s", response.content)
        return response

    async def generate_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = 0.0,
        max_output_tokens: int | None = None,
    ) -> LLMResponse:
        return await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            response_mime_type=self.JSON_MIME_TYPE,
        )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream text chunks từ Gemini."""
        model = (
            genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_prompt,
            )
            if system_prompt
            else self._model
        )
        generation_config = self._build_generation_config(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        stream_done = object()

        try:
            stream = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    contents=prompt,
                    generation_config=generation_config,
                    stream=True,
                ),
                timeout=self.timeout,
            )
            stream_iter = iter(stream)

            def next_chunk() -> Any:
                try:
                    return next(stream_iter)
                except StopIteration:
                    return stream_done

            while True:
                chunk = await asyncio.wait_for(
                    asyncio.to_thread(next_chunk),
                    timeout=self.timeout,
                )
                if chunk is stream_done:
                    break

                text = self._extract_response_text(chunk, allow_empty=True)
                if text:
                    yield text
        except asyncio.TimeoutError as exc:
            raise LLMTimeoutError(
                f"Gemini không phản hồi trong {self.timeout}s"
            ) from exc
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Gemini API lỗi: {exc}") from exc

    async def _call_once(
        self,
        *,
        model: Any,
        prompt: str,
        generation_config: Any,
    ) -> LLMResponse:
        start = time.perf_counter()

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    model.generate_content,
                    contents=prompt,
                    generation_config=generation_config,
                ),
                timeout=self.timeout,
            )
            duration_ms = (time.perf_counter() - start) * 1000
            usage = getattr(response, "usage_metadata", None)

            # Kiểm tra finish_reason — phát hiện output bị cắt
            finish_reason = self._get_finish_reason(response)
            if finish_reason == "MAX_TOKENS":
                text = self._extract_response_text(response, allow_empty=True)
                raise LLMTruncatedError(
                    f"Gemini output bị cắt do vượt max_output_tokens. "
                    f"finish_reason={finish_reason}, "
                    f"output_preview={text[:200]!r}"
                )

            return LLMResponse(
                content=self._extract_response_text(response),
                input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
                output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
                model=self.model_name,
                duration_ms=duration_ms,
            )
        except asyncio.TimeoutError as exc:
            raise LLMTimeoutError(
                f"Gemini không phản hồi trong {self.timeout}s"
            ) from exc
        except LLMError:
            raise
        except Exception as exc:
            logger.exception("Gemini API call failed")
            raise LLMError(
                f"Gemini API lỗi: {type(exc).__name__}: {exc}"
            ) from exc

    def _build_generation_config(
        self,
        *,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        response_mime_type: str | None = None,
    ) -> Any:
        config: dict[str, Any] = {
            "temperature": (
                temperature
                if temperature is not None
                else self.default_temperature
            ),
            "max_output_tokens": (
                max_output_tokens
                if max_output_tokens is not None
                else self.default_max_output_tokens
            ),
        }

        if response_mime_type:
            config["response_mime_type"] = response_mime_type

        try:
            return genai.types.GenerationConfig(**config)
        except TypeError:
            if not response_mime_type:
                raise
            config.pop("response_mime_type", None)
            return genai.types.GenerationConfig(**config)

    @staticmethod
    def _get_finish_reason(response: Any) -> str | None:
        """Trích xuất finish_reason từ Gemini response."""
        for candidate in getattr(response, "candidates", []) or []:
            reason = getattr(candidate, "finish_reason", None)
            if reason is not None:
                # finish_reason có thể là enum hoặc string tùy SDK version
                return str(reason).replace("FinishReason.", "").upper()
        return None

    @staticmethod
    def _extract_response_text(response: Any, *, allow_empty: bool = False) -> str:
        try:
            text = response.text
        except Exception:
            text = None

        if text:
            return str(text)

        texts: list[str] = []
        for candidate in getattr(response, "candidates", []) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", []) or []:
                part_text = getattr(part, "text", None)
                if part_text:
                    texts.append(str(part_text))

        if texts:
            return "".join(texts)

        if allow_empty:
            return ""

        raise LLMBlockedError("Gemini không trả nội dung.")


@lru_cache(maxsize=1)
def get_gemini_client() -> GeminiClient:
    """Factory dùng settings toàn app."""
    from src.core.settings import get_settings

    settings = get_settings()

    return GeminiClient(
        api_key=settings.google_api_key,
        model=settings.gemini_model,
        temperature=settings.llm_temperature,
        max_output_tokens=settings.llm_max_output_tokens,
        timeout=settings.llm_timeout,
    )
