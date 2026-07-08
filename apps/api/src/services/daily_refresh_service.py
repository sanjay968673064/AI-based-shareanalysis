import asyncio
from datetime import UTC, date, datetime

from src.core.config import settings
from src.db.session import SessionLocal
from src.repositories.app_settings import AppSettingsRepository
from src.repositories.audit import AuditLogRepository
from src.repositories.portfolio import PortfolioRepository
from src.repositories.recommendation_history import RecommendationHistoryRepository
from src.repositories.users import UserRepository
from src.services.company_analytics_service import CompanyAnalyticsService
from src.services.intelligence_service import IntelligenceService


class DailyRefreshService:
    def __init__(self) -> None:
        self._last_refresh_date: date | None = None
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        if not settings.analytics_daily_refresh_enabled or self._task is not None:
            return
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run_loop(self) -> None:
        await asyncio.sleep(10)
        while True:
            try:
                await self.refresh_if_needed()
            except Exception as exc:  # pragma: no cover - scheduler must never crash the API.
                print(f"Daily analytics refresh failed: {exc.__class__.__name__}: {exc}")
            await asyncio.sleep(max(900, settings.analytics_daily_refresh_check_seconds))

    async def refresh_if_needed(self) -> None:
        today = datetime.now(UTC).date()
        if self._last_refresh_date == today:
            return
        await self.refresh_now()
        self._last_refresh_date = today

    async def refresh_now(self) -> int:
        refreshed = 0
        async with SessionLocal() as session:
            contexts = await UserRepository(session).list_contexts_with_holdings()
        for context in contexts:
            async with SessionLocal() as session:
                portfolio_repo = PortfolioRepository(session)
                audit_repo = AuditLogRepository(session)
                await CompanyAnalyticsService(portfolio_repo, AppSettingsRepository(session)).analyze(context, force_refresh=True)
                await IntelligenceService(
                    portfolio_repo,
                    RecommendationHistoryRepository(session),
                    audit_repo,
                ).analyze(context, persist=True)
                await audit_repo.record(context, "analytics.daily_refresh.completed", "portfolio")
                refreshed += 1
        return refreshed


daily_refresh_service = DailyRefreshService()
