from src.schemas.intelligence import PortfolioAlertRead


class AlertingService:
    def generate(
        self,
        holdings: list[dict],
        recommendations: list,
        weights: dict[str, float],
        sector_values: dict[str, float],
        portfolio_value: float,
        snapshot_warnings: dict[str, list[str]],
    ) -> list[PortfolioAlertRead]:
        alerts: list[PortfolioAlertRead] = []
        alerts.extend(self._recommendation_alerts(recommendations))
        alerts.extend(self._concentration_alerts(weights))
        alerts.extend(self._daily_loss_alerts(holdings))
        alerts.extend(self._sector_alerts(sector_values, portfolio_value))
        alerts.extend(self._market_data_alerts(snapshot_warnings))
        return sorted(alerts, key=lambda item: {"high": 0, "medium": 1, "low": 2}[item.severity])

    def _recommendation_alerts(self, recommendations: list) -> list[PortfolioAlertRead]:
        alerts = []
        for item in recommendations:
            if item.recommendation in {"Exit", "Reduce"} and item.risk_score >= 75:
                alerts.append(
                    PortfolioAlertRead(
                        severity="high",
                        alert_type="risk_reduction",
                        symbol=item.symbol,
                        message=(
                            f"{item.symbol} is marked {item.recommendation} with risk score "
                            f"{item.risk_score}/100."
                        ),
                        action="Review position size, stop-loss discipline and exit thesis before adding more capital.",
                    )
                )
            elif item.recommendation == "Book Partial Profit":
                alerts.append(
                    PortfolioAlertRead(
                        severity="medium",
                        alert_type="profit_booking",
                        symbol=item.symbol,
                        message=f"{item.symbol} has profit-booking conditions based on allocation and return.",
                        action="Consider trimming only after checking tax impact, liquidity and next earnings date.",
                    )
                )
        return alerts

    def _concentration_alerts(self, weights: dict[str, float]) -> list[PortfolioAlertRead]:
        return [
            PortfolioAlertRead(
                severity="high" if weight > 25 else "medium",
                alert_type="position_concentration",
                symbol=symbol,
                message=f"{symbol} is {weight:.1f}% of the portfolio.",
                action="Avoid fresh buying until the position is back inside the target allocation range.",
            )
            for symbol, weight in weights.items()
            if weight > 15
        ]

    def _daily_loss_alerts(self, holdings: list[dict]) -> list[PortfolioAlertRead]:
        alerts = []
        for holding in holdings:
            value = float(holding["quantity"]) * float(holding["last_price"])
            day_pnl = float(holding["day_pnl"])
            day_return = (day_pnl / max(value - day_pnl, 1)) * 100
            if day_return < -3:
                alerts.append(
                    PortfolioAlertRead(
                        severity="medium",
                        alert_type="intraday_drawdown",
                        symbol=holding["symbol"],
                        message=f"{holding['symbol']} is down {abs(day_return):.2f}% today based on broker P&L.",
                        action="Check whether the move is market-wide, news-driven, or specific to the company.",
                    )
                )
        return alerts

    def _sector_alerts(self, sector_values: dict[str, float], portfolio_value: float) -> list[PortfolioAlertRead]:
        if portfolio_value <= 0:
            return []
        alerts = []
        for sector, value in sector_values.items():
            weight = value / portfolio_value * 100
            if weight > 35:
                alerts.append(
                    PortfolioAlertRead(
                        severity="medium",
                        alert_type="sector_concentration",
                        symbol=None,
                        message=f"{sector} exposure is {weight:.1f}% of the portfolio.",
                        action="Use new purchases to diversify instead of increasing this sector further.",
                    )
                )
            if sector == "Unclassified" and weight > 50:
                alerts.append(
                    PortfolioAlertRead(
                        severity="low",
                        alert_type="missing_sector_data",
                        symbol=None,
                        message=f"{weight:.1f}% of portfolio value has no sector classification.",
                        action="Map sectors for imported holdings to improve diversification scoring.",
                    )
                )
        return alerts

    def _market_data_alerts(self, snapshot_warnings: dict[str, list[str]]) -> list[PortfolioAlertRead]:
        alerts = []
        missing = [symbol for symbol, warnings in snapshot_warnings.items() if warnings]
        if len(missing) > 5:
            alerts.append(
                PortfolioAlertRead(
                    severity="low",
                    alert_type="market_data_coverage",
                    symbol=None,
                    message=f"Live market enrichment has warnings for {len(missing)} holdings.",
                    action="Review provider coverage before acting on technical signals.",
                )
            )
            return alerts
        for symbol in missing:
            alerts.append(
                PortfolioAlertRead(
                    severity="low",
                    alert_type="market_data_coverage",
                    symbol=symbol,
                    message=f"Live market enrichment is incomplete for {symbol}.",
                    action="Validate the symbol mapping and exchange suffix before relying on technical signals.",
                )
            )
        return alerts
