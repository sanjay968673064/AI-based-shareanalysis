from src.schemas.intelligence import MarketAnalysisRead


class MarketAnalysisService:
    def analyze(self) -> MarketAnalysisRead:
        return MarketAnalysisRead(
            nifty_trend="unknown",
            bank_nifty_trend="unknown",
            india_vix=None,
            notes=[
                "Market index, VIX, USD/INR, bond yield and macro data providers are not configured.",
                "Market regime is treated as neutral until data is available.",
            ],
        )
