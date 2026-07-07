from src.schemas.intelligence import (
    FundamentalAnalysisRead,
    NewsAnalysisRead,
    RecommendationLabel,
    StockRecommendationRead,
    TechnicalAnalysisRead,
)


class RecommendationEngine:
    def recommend(
        self,
        holding: dict,
        allocation_pct: float,
        fundamental: FundamentalAnalysisRead,
        technical: TechnicalAnalysisRead,
        news: NewsAnalysisRead,
        previous: dict | None,
    ) -> StockRecommendationRead:
        total_return_pct = self._total_return_pct(holding)
        risk_score = self._risk_score(allocation_pct, total_return_pct, fundamental, technical)
        confidence = self._confidence_score(fundamental, technical, news)
        recommendation = self._label(allocation_pct, total_return_pct, risk_score, confidence)
        target_allocation = self._target_allocation(allocation_pct, risk_score, recommendation)
        expected_upside = max(3.0, min(35.0, 8 + max(total_return_pct, 0) * 0.25 + technical.momentum_score * 0.08))
        expected_downside = -max(4.0, min(30.0, risk_score * 0.25))
        what_changed = self._what_changed(previous, recommendation)

        bullish = []
        bearish = []
        if total_return_pct > 0:
            bullish.append(f"Position is profitable with {total_return_pct:.2f}% unrealized return.")
        else:
            bearish.append(f"Position is down {abs(total_return_pct):.2f}% from average cost.")
        if technical.momentum_score >= 60:
            bullish.append(f"Short-term momentum score is {technical.momentum_score}/100.")
        elif technical.momentum_score <= 40:
            bearish.append(f"Short-term momentum score is weak at {technical.momentum_score}/100.")
        if allocation_pct > 15:
            bearish.append(f"Allocation is elevated at {allocation_pct:.1f}% of portfolio.")
        if fundamental.notes:
            bearish.append("Fundamental data is incomplete, reducing conviction.")

        return StockRecommendationRead(
            symbol=holding["symbol"],
            company_name=holding["company_name"],
            recommendation=recommendation,
            confidence_score=confidence,
            risk_score=risk_score,
            expected_upside=round(expected_upside, 2),
            expected_downside=round(expected_downside, 2),
            suggested_holding_period="3-12 months; review after earnings or material news.",
            target_allocation=round(target_allocation, 2),
            reasoning=self._reasoning(recommendation, allocation_pct, total_return_pct, risk_score, confidence),
            bullish_factors=bullish or ["No strong bullish factor found from currently available data."],
            bearish_factors=bearish or ["No major bearish factor found from currently available data."],
            key_risks=[
                "External fundamentals, historical technicals and trusted news are not fully configured.",
                "Recommendation is advisory only and must not be treated as an automated trade instruction.",
            ],
            what_changed=what_changed,
            fundamental=fundamental,
            technical=technical,
            news=news,
        )

    def _label(
        self, allocation_pct: float, total_return_pct: float, risk_score: int, confidence: int
    ) -> RecommendationLabel:
        if risk_score >= 82 and total_return_pct < -15:
            return "Exit"
        if allocation_pct > 20 and total_return_pct > 12:
            return "Book Partial Profit"
        if allocation_pct > 18 or risk_score >= 75:
            return "Reduce"
        if confidence >= 70 and total_return_pct > 20 and risk_score < 55:
            return "Buy More"
        if confidence >= 60 and total_return_pct >= 0 and risk_score < 65:
            return "Accumulate"
        if confidence >= 80 and risk_score < 45:
            return "Strong Buy"
        return "Hold"

    def _risk_score(
        self,
        allocation_pct: float,
        total_return_pct: float,
        fundamental: FundamentalAnalysisRead,
        technical: TechnicalAnalysisRead,
    ) -> int:
        risk = 35 + allocation_pct * 1.3
        if total_return_pct < -15:
            risk += 18
        if technical.momentum_score < 40:
            risk += 10
        if fundamental.score < 45:
            risk += 10
        return int(max(0, min(100, risk)))

    def _confidence_score(
        self,
        fundamental: FundamentalAnalysisRead,
        technical: TechnicalAnalysisRead,
        news: NewsAnalysisRead,
    ) -> int:
        missing_penalty = 0
        missing_penalty += 20 if fundamental.notes else 0
        missing_penalty += 15 if technical.notes else 0
        missing_penalty += 10 if news.notes else 0
        return int(max(20, min(95, 75 - missing_penalty + fundamental.score * 0.15 + technical.momentum_score * 0.1)))

    def _target_allocation(self, allocation_pct: float, risk_score: int, recommendation: RecommendationLabel) -> float:
        if recommendation in {"Reduce", "Book Partial Profit", "Exit"}:
            return max(0, allocation_pct * (0.45 if recommendation == "Exit" else 0.7))
        if recommendation in {"Strong Buy", "Buy More", "Accumulate"}:
            return min(12, allocation_pct + 2)
        return allocation_pct

    def _reasoning(
        self, recommendation: RecommendationLabel, allocation_pct: float, total_return_pct: float, risk: int, confidence: int
    ) -> str:
        return (
            f"{recommendation} is selected because allocation is {allocation_pct:.1f}%, "
            f"position return is {total_return_pct:+.2f}%, risk score is {risk}/100, "
            f"and confidence is {confidence}/100 after missing-data penalties."
        )

    def _what_changed(self, previous: dict | None, recommendation: RecommendationLabel) -> str:
        if previous is None:
            return "First recommendation recorded for this symbol."
        previous_label = previous["recommendation"]
        if previous_label == recommendation:
            return f"Recommendation remains {recommendation} since the previous report."
        return f"Recommendation changed from {previous_label} to {recommendation}."

    def _total_return_pct(self, holding: dict) -> float:
        avg = float(holding["average_price"])
        last = float(holding["last_price"])
        return ((last - avg) / avg * 100) if avg else 0
