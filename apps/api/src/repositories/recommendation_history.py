import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.auth import UserContext
from src.schemas.intelligence import RecommendationHistoryRead, StockRecommendationRead


class RecommendationHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ensure_schema(self) -> None:
        await self._session.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS recommendation_history (
                  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                  user_id UUID NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
                  symbol TEXT NOT NULL,
                  recommendation TEXT NOT NULL,
                  confidence_score NUMERIC(6, 2) NOT NULL,
                  risk_score NUMERIC(6, 2) NOT NULL,
                  price_at_recommendation NUMERIC(18, 4) NOT NULL,
                  target_allocation NUMERIC(6, 2) NOT NULL,
                  payload JSONB NOT NULL DEFAULT '{}',
                  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        )
        await self._session.commit()

    async def latest_by_symbol(self, context: UserContext) -> dict[str, dict]:
        await self.ensure_schema()
        result = await self._session.execute(
            text(
                """
                SELECT DISTINCT ON (symbol)
                  symbol, recommendation, confidence_score, risk_score,
                  price_at_recommendation, payload, created_at
                FROM recommendation_history
                WHERE tenant_id = :tenant_id AND user_id = :user_id
                ORDER BY symbol, created_at DESC
                """
            ),
            {"tenant_id": context.tenant_id, "user_id": context.user_id},
        )
        return {row["symbol"]: dict(row) for row in result.mappings().all()}

    async def save_many(
        self,
        context: UserContext,
        recommendations: list[StockRecommendationRead],
        price_by_symbol: dict[str, float],
    ) -> None:
        await self.ensure_schema()
        if not recommendations:
            return
        await self._session.execute(
            text(
                """
                INSERT INTO recommendation_history (
                  tenant_id, user_id, symbol, recommendation, confidence_score,
                  risk_score, price_at_recommendation, target_allocation, payload
                )
                VALUES (
                  :tenant_id, :user_id, :symbol, :recommendation, :confidence_score,
                  :risk_score, :price_at_recommendation, :target_allocation, CAST(:payload AS JSONB)
                )
                """
            ),
            [
                {
                    "tenant_id": context.tenant_id,
                    "user_id": context.user_id,
                    "symbol": item.symbol,
                    "recommendation": item.recommendation,
                    "confidence_score": item.confidence_score,
                    "risk_score": item.risk_score,
                    "price_at_recommendation": price_by_symbol.get(item.symbol, 0),
                    "target_allocation": item.target_allocation,
                    "payload": json.dumps(item.model_dump(mode="json", by_alias=True)),
                }
                for item in recommendations
            ],
        )
        await self._session.commit()

    async def list_history(self, context: UserContext, limit: int = 100) -> list[RecommendationHistoryRead]:
        await self.ensure_schema()
        result = await self._session.execute(
            text(
                """
                SELECT symbol, recommendation, confidence_score, risk_score,
                       price_at_recommendation, created_at
                FROM recommendation_history
                WHERE tenant_id = :tenant_id AND user_id = :user_id
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"tenant_id": context.tenant_id, "user_id": context.user_id, "limit": limit},
        )
        return [
            RecommendationHistoryRead(
                symbol=row["symbol"],
                recommendation=row["recommendation"],
                confidence_score=float(row["confidence_score"]),
                risk_score=float(row["risk_score"]),
                price_at_recommendation=float(row["price_at_recommendation"]),
                current_outcome="Tracking; compare current price in next report.",
                created_at=row["created_at"],
            )
            for row in result.mappings().all()
        ]
