from src.schemas.intelligence import NewsAnalysisRead


class NewsAnalysisService:
    def analyze(self, symbol: str) -> NewsAnalysisRead:
        return NewsAnalysisRead(
            sentiment_score=0,
            trusted_items=[],
            notes=[f"No trusted news provider is configured for {symbol}; sentiment is neutral with reduced confidence."],
        )
