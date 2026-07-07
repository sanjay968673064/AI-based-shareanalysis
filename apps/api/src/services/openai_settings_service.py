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
        await self._settings_repo.upsert(
            context,
            AI_PROVIDER_SETTING,
            token_cipher.encrypt(provider),
        )
        await self._settings_repo.upsert(
            context,
            self._api_key_setting(provider),
            token_cipher.encrypt(payload.api_key.strip()),
        )
        if payload.model:
            await self._settings_repo.upsert(
                context,
                self._model_setting(provider),
                token_cipher.encrypt(payload.model.strip()),
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
