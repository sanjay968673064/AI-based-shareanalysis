from src.schemas.intelligence import FundamentalAnalysisRead


class FundamentalAnalysisService:
    def analyze(self, holding: dict) -> FundamentalAnalysisRead:
        total_return_pct = self._total_return_pct(holding)
        score = 50 + (10 if total_return_pct > 20 else 0) - (10 if total_return_pct < -10 else 0)
        return FundamentalAnalysisRead(
            score=max(0, min(100, score)),
            notes=[
                "Company financial statement provider is not configured.",
                "Fundamental confidence is reduced until PE, ROE, debt, growth and cash-flow data are available.",
            ],
        )

    def _total_return_pct(self, holding: dict) -> float:
        avg = float(holding["average_price"])
        last = float(holding["last_price"])
        return ((last - avg) / avg * 100) if avg else 0
