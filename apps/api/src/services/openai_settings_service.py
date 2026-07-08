import json

import httpx

from src.core.config import settings
from src.core.security import token_cipher
from src.domain.auth import UserContext
from src.repositories.app_settings import AppSettingsRepository
from src.schemas.ai_config import AiProvider, OpenAiSettingsRead, OpenAiSettingsUpdate


AI_PROVIDER_SETTING = "ai_provider"
OPENAI_API_KEY_SETTING = "openai_api_key"
OPENAI_MODEL_SETTING = "openai_model"
GEMINI_API_KEY_SETTING = "gemini_api_key"
GEMINI_MODEL_SETTING = "gemini_model"


class AiConnectionValidationError(ValueError):
    pass


class OpenAiSettingsService:
    def __init__(self, settings_repo: AppSettingsRepository) -> None:
        self._settings_repo = settings_repo

    async def read(self, context: UserContext) -> OpenAiSettingsRead:
        provider = await self.get_provider(context)
        api_key = await self.get_api_key(context, provider)
        model = await self.get_model(context, provider)
        return OpenAiSettingsRead(
            configured=bool(api_key),
            provider=provider,
            masked_key=self._mask(api_key) if api_key else None,
            model=model,
        )

    async def save(self, context: UserContext, payload: OpenAiSettingsUpdate) -> OpenAiSettingsRead:
        provider = payload.provider
        api_key = payload.api_key.strip()
        model = payload.model.strip() if payload.model else self._default_model(provider)
        await self._validate_connection(provider, api_key, model)
        await self._settings_repo.upsert(
            context,
            AI_PROVIDER_SETTING,
            token_cipher.encrypt(provider),
        )
        await self._settings_repo.upsert(
            context,
            self._api_key_setting(provider),
            token_cipher.encrypt(api_key),
        )
        await self._settings_repo.upsert(
            context,
            self._model_setting(provider),
            token_cipher.encrypt(model),
        )
        return await self.read(context)

    async def delete(self, context: UserContext) -> OpenAiSettingsRead:
        provider = await self.get_provider(context)
        await self._settings_repo.delete(context, self._api_key_setting(provider))
        await self._settings_repo.delete(context, self._model_setting(provider))
        return await self.read(context)

    async def get_provider(self, context: UserContext) -> AiProvider:
        encrypted = await self._settings_repo.get(context, AI_PROVIDER_SETTING)
        provider = token_cipher.decrypt(encrypted) if encrypted else "gemini"
        return "openai" if provider == "openai" else "gemini"

    async def get_api_key(self, context: UserContext, provider: AiProvider | None = None) -> str:
        active_provider = provider or await self.get_provider(context)
        encrypted = await self._settings_repo.get(context, self._api_key_setting(active_provider))
        if encrypted:
            return token_cipher.decrypt(encrypted)
        if active_provider == "openai":
            return settings.openai_api_key.strip()
        return settings.gemini_api_key.strip()

    async def get_model(self, context: UserContext, provider: AiProvider | None = None) -> str:
        active_provider = provider or await self.get_provider(context)
        encrypted = await self._settings_repo.get(context, self._model_setting(active_provider))
        if encrypted:
            return token_cipher.decrypt(encrypted)
        if active_provider == "openai":
            return settings.openai_model
        return settings.gemini_model

    def _api_key_setting(self, provider: AiProvider) -> str:
        return OPENAI_API_KEY_SETTING if provider == "openai" else GEMINI_API_KEY_SETTING

    def _model_setting(self, provider: AiProvider) -> str:
        return OPENAI_MODEL_SETTING if provider == "openai" else GEMINI_MODEL_SETTING

    def _mask(self, api_key: str) -> str:
        if len(api_key) <= 8:
            return "Configured"
        return f"...{api_key[-6:]}"

    def _default_model(self, provider: AiProvider) -> str:
        return settings.openai_model if provider == "openai" else settings.gemini_model

    async def _validate_connection(self, provider: AiProvider, api_key: str, model: str) -> None:
        if provider == "openai":
            await self._validate_openai(api_key, model)
            return
        await self._validate_gemini(api_key, model)

    async def _validate_gemini(self, api_key: str, model: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=min(max(settings.openai_timeout_seconds, 10.0), 30.0)) as client:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                    params={"key": api_key},
                    headers={"Content-Type": "application/json"},
                    json={
                        "contents": [
                            {
                                "role": "user",
                                "parts": [{"text": "Connection test. Reply with OK."}],
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0,
                            "maxOutputTokens": 8,
                        },
                    },
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AiConnectionValidationError(
                f"Gemini connection failed: {self._provider_error(exc)}"
            ) from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise AiConnectionValidationError(
                f"Gemini connection failed: {self._safe_error(exc)}"
            ) from exc

    async def _validate_openai(self, api_key: str, model: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=min(max(settings.openai_timeout_seconds, 10.0), 30.0)) as client:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "input": "Connection test. Reply with OK.",
                        "max_output_tokens": 16,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AiConnectionValidationError(
                f"OpenAI connection failed: {self._provider_error(exc)}"
            ) from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise AiConnectionValidationError(
                f"OpenAI connection failed: {self._safe_error(exc)}"
            ) from exc

    def _provider_error(self, exc: httpx.HTTPStatusError) -> str:
        try:
            payload = exc.response.json()
        except json.JSONDecodeError:
            return f"HTTP {exc.response.status_code}"
        error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error, dict):
            message = str(error.get("message") or "").strip()
            status = str(error.get("status") or "").strip()
            details = " - ".join(item for item in [f"HTTP {exc.response.status_code}", status, message[:220]] if item)
            return details or f"HTTP {exc.response.status_code}"
        return f"HTTP {exc.response.status_code}"

    def _safe_error(self, exc: Exception) -> str:
        if isinstance(exc, httpx.TimeoutException):
            return "request timed out while validating the key"
        if isinstance(exc, httpx.NetworkError):
            return "network error while contacting the AI provider"
        return exc.__class__.__name__
