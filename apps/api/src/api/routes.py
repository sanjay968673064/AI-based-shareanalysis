from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from src.api.dependencies import (
    get_broker_service,
    get_company_analytics_service,
    get_intelligence_service,
    get_openai_analytics_service,
    get_openai_settings_service,
    get_portfolio_service,
    get_user_context,
)
from src.domain.auth import UserContext
from src.integrations.kite_mcp import BrokerConfigurationError
from src.schemas.ai_config import AiAnalyticsInsightRead, OpenAiSettingsRead, OpenAiSettingsUpdate
from src.schemas.analytics import PortfolioAnalyticsRead
from src.schemas.intelligence import (
    IntelligenceReportRead,
    PortfolioAlertRead,
    PortfolioIntelligenceRead,
    RecommendationHistoryRead,
)
from src.schemas.portfolio import ManualPortfolioImportResponse, PortfolioSummaryRead
from src.services.csv_portfolio_parser import PortfolioCsvParseError
from src.schemas.zerodha import BrokerStatusRead, ReadOnlyConnectRequest, ReadOnlyConnectResponse
from src.schemas.zerodha import McpConnectResponse, McpSyncResponse
from src.services.broker_service import BrokerService
from src.services.company_analytics_service import CompanyAnalyticsService
from src.services.daily_refresh_service import daily_refresh_service
from src.services.intelligence_service import IntelligenceService
from src.services.openai_analytics_service import OpenAiAnalyticsService
from src.services.openai_settings_service import OpenAiSettingsService
from src.services.portfolio_service import PortfolioService

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/portfolio/summary", response_model=PortfolioSummaryRead, response_model_by_alias=True)
async def portfolio_summary(
    context: UserContext = Depends(get_user_context),
    service: PortfolioService = Depends(get_portfolio_service),
) -> PortfolioSummaryRead:
    return await service.get_summary(context)


@router.post(
    "/api/v1/portfolio/manual-import",
    response_model=ManualPortfolioImportResponse,
    response_model_by_alias=True,
)
async def manual_portfolio_import(
    file: UploadFile = File(...),
    context: UserContext = Depends(get_user_context),
    service: PortfolioService = Depends(get_portfolio_service),
) -> ManualPortfolioImportResponse:
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Upload a CSV file.")
    try:
        return await service.import_manual_csv(context, await file.read())
    except PortfolioCsvParseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/api/v1/zerodha/status", response_model=BrokerStatusRead)
async def zerodha_status(
    context: UserContext = Depends(get_user_context),
    service: BrokerService = Depends(get_broker_service),
) -> BrokerStatusRead:
    return await service.get_zerodha_status(context)


@router.post("/api/v1/zerodha/connect/read-only", response_model=ReadOnlyConnectResponse)
async def zerodha_read_only_connect(
    request: ReadOnlyConnectRequest,
    context: UserContext = Depends(get_user_context),
    service: BrokerService = Depends(get_broker_service),
) -> ReadOnlyConnectResponse:
    try:
        return await service.create_read_only_connection(context, request)
    except BrokerConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post("/api/v1/zerodha/mcp/connect", response_model=McpConnectResponse)
async def zerodha_mcp_connect(
    context: UserContext = Depends(get_user_context),
    service: BrokerService = Depends(get_broker_service),
) -> McpConnectResponse:
    try:
        return await service.create_mcp_connection(context)
    except BrokerConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post("/api/v1/zerodha/mcp/sync", response_model=McpSyncResponse, response_model_by_alias=True)
async def zerodha_mcp_sync(
    context: UserContext = Depends(get_user_context),
    service: BrokerService = Depends(get_broker_service),
) -> McpSyncResponse:
    try:
        return await service.sync_mcp_holdings(context)
    except BrokerConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get(
    "/api/v1/intelligence/analysis",
    response_model=PortfolioIntelligenceRead,
    response_model_by_alias=True,
)
async def intelligence_analysis(
    persist: bool = Query(default=False),
    context: UserContext = Depends(get_user_context),
    service: IntelligenceService = Depends(get_intelligence_service),
) -> PortfolioIntelligenceRead:
    return await service.analyze(context, persist=persist)


@router.post(
    "/api/v1/intelligence/run",
    response_model=PortfolioIntelligenceRead,
    response_model_by_alias=True,
)
async def intelligence_run(
    context: UserContext = Depends(get_user_context),
    service: IntelligenceService = Depends(get_intelligence_service),
) -> PortfolioIntelligenceRead:
    return await service.analyze(context, persist=True)


@router.get(
    "/api/v1/analytics/company",
    response_model=PortfolioAnalyticsRead,
    response_model_by_alias=True,
)
async def company_analytics(
    force_refresh: bool = Query(default=False, alias="forceRefresh"),
    context: UserContext = Depends(get_user_context),
    service: CompanyAnalyticsService = Depends(get_company_analytics_service),
) -> PortfolioAnalyticsRead:
    return await service.analyze(context, force_refresh=force_refresh)


@router.post("/api/v1/analytics/daily-refresh")
async def analytics_daily_refresh() -> dict[str, int | str]:
    refreshed = await daily_refresh_service.refresh_now()
    return {"status": "ok", "refreshedUsers": refreshed}


@router.get(
    "/api/v1/settings/openai",
    response_model=OpenAiSettingsRead,
    response_model_by_alias=True,
)
async def openai_settings(
    context: UserContext = Depends(get_user_context),
    service: OpenAiSettingsService = Depends(get_openai_settings_service),
) -> OpenAiSettingsRead:
    return await service.read(context)


@router.put(
    "/api/v1/settings/openai",
    response_model=OpenAiSettingsRead,
    response_model_by_alias=True,
)
async def save_openai_settings(
    payload: OpenAiSettingsUpdate,
    context: UserContext = Depends(get_user_context),
    service: OpenAiSettingsService = Depends(get_openai_settings_service),
) -> OpenAiSettingsRead:
    return await service.save(context, payload)


@router.delete(
    "/api/v1/settings/openai",
    response_model=OpenAiSettingsRead,
    response_model_by_alias=True,
)
async def delete_openai_settings(
    context: UserContext = Depends(get_user_context),
    service: OpenAiSettingsService = Depends(get_openai_settings_service),
) -> OpenAiSettingsRead:
    return await service.delete(context)


@router.post(
    "/api/v1/analytics/openai-insight",
    response_model=AiAnalyticsInsightRead,
    response_model_by_alias=True,
)
async def openai_analytics_insight(
    context: UserContext = Depends(get_user_context),
    analytics_service: CompanyAnalyticsService = Depends(get_company_analytics_service),
    openai_service: OpenAiAnalyticsService = Depends(get_openai_analytics_service),
) -> AiAnalyticsInsightRead:
    analytics = await analytics_service.analyze(context, force_refresh=False)
    return await openai_service.generate(context, analytics)


@router.get(
    "/api/v1/intelligence/reports/daily",
    response_model=IntelligenceReportRead,
    response_model_by_alias=True,
)
async def daily_intelligence_report(
    session: str = Query(default="morning", pattern="^(morning|evening)$"),
    context: UserContext = Depends(get_user_context),
    service: IntelligenceService = Depends(get_intelligence_service),
) -> IntelligenceReportRead:
    return await service.generate_report(context, f"daily-{session}")


@router.get(
    "/api/v1/intelligence/alerts",
    response_model=list[PortfolioAlertRead],
    response_model_by_alias=True,
)
async def intelligence_alerts(
    context: UserContext = Depends(get_user_context),
    service: IntelligenceService = Depends(get_intelligence_service),
) -> list[PortfolioAlertRead]:
    return await service.alerts(context)


@router.get(
    "/api/v1/intelligence/recommendations/history",
    response_model=list[RecommendationHistoryRead],
    response_model_by_alias=True,
)
async def recommendation_history(
    context: UserContext = Depends(get_user_context),
    service: IntelligenceService = Depends(get_intelligence_service),
) -> list[RecommendationHistoryRead]:
    return await service.history(context)
