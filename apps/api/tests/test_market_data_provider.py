from src.services.intelligence_providers import MarketDataProvider, MarketSnapshot


def test_market_data_consensus_rejects_price_outliers() -> None:
    provider = MarketDataProvider()
    provider._price_tolerance_pct = 3.0

    snapshot = provider._merge_snapshots(
        {"symbol": "SBIN", "exchange": "NSE"},
        [
            MarketSnapshot(
                symbol="SBIN",
                provider_symbol="SBIN.NS",
                last_price=100,
                previous_close=99,
                closes=[95, 98, 100],
                highs=[96, 99, 101],
                lows=[94, 97, 99],
                volumes=[1000, 1000, 1000],
                source="yahoo",
            ),
            MarketSnapshot(
                symbol="SBIN",
                provider_symbol="SBIN.NSE",
                last_price=118,
                previous_close=117,
                closes=[114, 116, 118],
                highs=[115, 117, 119],
                lows=[113, 115, 117],
                volumes=[1000, 1000, 1000],
                source="alpha_vantage",
            ),
        ],
        ["yahoo", "alpha_vantage"],
    )

    assert snapshot.last_price is None
    assert any("Rejected consensus last price" in warning for warning in snapshot.warnings)


def test_market_data_consensus_uses_median_when_sources_agree() -> None:
    provider = MarketDataProvider()
    provider._price_tolerance_pct = 3.0

    snapshot = provider._merge_snapshots(
        {"symbol": "INFY", "exchange": "NSE"},
        [
            MarketSnapshot(
                symbol="INFY",
                provider_symbol="INFY.NS",
                last_price=1500,
                previous_close=1490,
                closes=[1488, 1490, 1500],
                highs=[1490, 1492, 1502],
                lows=[1480, 1488, 1498],
                volumes=[1000, 1000, 1000],
                source="yahoo",
            ),
            MarketSnapshot(
                symbol="INFY",
                provider_symbol="INFY.NSE",
                last_price=1506,
                previous_close=1494,
                closes=[1489, 1494, 1506],
                highs=[1492, 1496, 1508],
                lows=[1487, 1491, 1501],
                volumes=[1000, 1000, 1000],
                source="alpha_vantage",
            ),
        ],
        ["yahoo", "alpha_vantage"],
    )

    assert snapshot.last_price == 1503
    assert snapshot.previous_close == 1492
    assert snapshot.source == "consensus:yahoo+alpha_vantage"
