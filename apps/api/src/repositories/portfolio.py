from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.auth import UserContext


class PortfolioRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_holdings(self, context: UserContext) -> list[dict]:
        result = await self._session.execute(
            text(
                """
                SELECT symbol, exchange, company_name, sector, asset_class, quantity,
                       average_price, last_price, day_pnl, total_pnl, updated_at
                FROM holdings
                WHERE tenant_id = :tenant_id AND user_id = :user_id
                ORDER BY (quantity * last_price) DESC
                """
            ),
            {"tenant_id": context.tenant_id, "user_id": context.user_id},
        )
        return [dict(row) for row in result.mappings().all()]

    async def replace_holdings(self, context: UserContext, holdings: list[dict]) -> None:
        await self._session.execute(
            text(
                """
                DELETE FROM holdings
                WHERE tenant_id = :tenant_id AND user_id = :user_id
                """
            ),
            {"tenant_id": context.tenant_id, "user_id": context.user_id},
        )
        if holdings:
            await self._session.execute(
                text(
                    """
                    INSERT INTO holdings (
                        tenant_id, user_id, symbol, exchange, company_name, sector, asset_class,
                        quantity, average_price, last_price, day_pnl, total_pnl
                    )
                    VALUES (
                        :tenant_id, :user_id, :symbol, :exchange, :company_name, :sector, :asset_class,
                        :quantity, :average_price, :last_price, :day_pnl, :total_pnl
                    )
                    """
                ),
                [
                    {
                        **holding,
                        "tenant_id": context.tenant_id,
                        "user_id": context.user_id,
                    }
                    for holding in holdings
                ],
            )
        await self._session.commit()
