from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.domain.auth import UserContext
from src.integrations.kite_mcp import KiteMcpClient
from src.repositories.app_settings import AppSettingsRepository
from src.repositories.audit import AuditLogRepository
from src.repositories.broker_connections import BrokerConnectionRepository
from src.repositories.portfolio import PortfolioRepository
from src.repositories.recommendation_history import RecommendationHistoryRepository
from src.repositories.users import UserRepository
from src.services.broker_service import BrokerService
from src.services.company_analytics_service import CompanyAnalyticsService
from src.services.intelligence_service import IntelligenceService
from src.services.openai_analytics_service import OpenAiAnalyticsService
from src.services.openai_settings_service import OpenAiSettingsService
from src.services.portfolio_service import PortfolioService


async def get_user_context(
    x_user_id: str = Header(default="demo-user"),
    session: AsyncSession = Depends(get_session),
) -> UserContext:
    context = await UserRepository(session).get_context_by_external_id(x_user_id)
    if context is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user.")
    return context


def get_portfolio_service(session: AsyncSession = Depends(get_session)) -> PortfolioService:
    return PortfolioService(PortfolioRepository(session), AuditLogRepository(session))


def get_broker_service(session: AsyncSession = Depends(get_session)) -> BrokerService:
    return BrokerService(
        BrokerConnectionRepository(session),
        PortfolioRepository(session),
        AuditLogRepository(session),
        KiteMcpClient(),
    )


def get_intelligence_service(session: AsyncSession = Depends(get_session)) -> IntelligenceService:
    return IntelligenceService(
        PortfolioRepository(session),
        RecommendationHistoryRepository(session),
        AuditLogRepository(session),
    )


def get_company_analytics_service(session: AsyncSession = Depends(get_session)) -> CompanyAnalyticsService:
    return CompanyAnalyticsService(PortfolioRepository(session))


def get_openai_settings_service(session: AsyncSession = Depends(get_session)) -> OpenAiSettingsService:
    return OpenAiSettingsService(AppSettingsRepository(session))


def get_openai_analytics_service(session: AsyncSession = Depends(get_session)) -> OpenAiAnalyticsService:
    return OpenAiAnalyticsService(AppSettingsRepository(session))
