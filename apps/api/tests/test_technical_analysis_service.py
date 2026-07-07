from src.services.intelligence_providers import MarketSnapshot
from src.services.technical_analysis_service import TechnicalAnalysisService


def test_technical_analysis_uses_market_snapshot() -> None:
    service = TechnicalAnalysisService()
    closes = [100 + index * 0.8 for index in range(220)]
    snapshot = MarketSnapshot(
        symbol="SBIN",
        provider_symbol="SBIN.NS",
        last_price=closes[-1],
        previous_close=closes[-2],
        closes=closes,
        highs=[value + 2 for value in closes],
        lows=[value - 2 for value in closes],
        volumes=[1000 + index for index in range(220)],
        source="test",
    )

    result = service.analyze(
        {
            "symbol": "SBIN",
            "quantity": 10,
            "last_price": closes[-1],
            "day_pnl": 20,
        },
        snapshot,
    )

    assert result.rsi_14 is not None
    assert result.macd is not None
    assert result.ema_200 is not None
    assert result.trend_direction == "uptrend"
    assert result.momentum_score > 50
    assert "test OHLCV" in result.notes[0]
