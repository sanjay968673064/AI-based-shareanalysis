from src.schemas.analytics import AnalyticsMetricRead, CompanyAnalyticsRead, CompanyNewsRead
from src.services.intelligence_providers import MarketSnapshot
from src.services.company_analytics_service import CompanyAnalyticsService, MODEL_VERSION, SCORING_WEIGHTS


def _company(symbol: str = "INFY", score: int = 82) -> CompanyAnalyticsRead:
    return CompanyAnalyticsRead(
        symbol=symbol,
        company_name="Infosys Ltd",
        sector="Information Technology",
        industry="IT Services",
        currency="INR",
        last_price=1500,
        day_change_pct=0.7,
        fifty_two_week_low=1200,
        fifty_two_week_high=1700,
        business_summary="Infosys Ltd operates in Information Technology.",
        overall_score=score,
        balance_sheet_score=78,
        growth_score=74,
        cash_flow_score=80,
        valuation_score=62,
        recommendation="Build",
        planning="Plan staged accumulation only on valuation comfort.",
        strengths=["Revenue is growing year over year.", "Free cash flow conversion is healthy."],
        concerns=["No major provider-derived concern detected."],
        financials=[
            AnalyticsMetricRead(label="Revenue growth", value="12.0%", tone="good"),
            AnalyticsMetricRead(label="Net income growth", value="10.0%", tone="good"),
            AnalyticsMetricRead(label="Debt / equity", value="0.20", tone="good"),
            AnalyticsMetricRead(label="Cash / debt", value="1.20", tone="good"),
            AnalyticsMetricRead(label="FCF margin", value="14.0%", tone="good"),
            AnalyticsMetricRead(label="ROE", value="18.0%", tone="good"),
            AnalyticsMetricRead(label="Liabilities / assets", value="0.35", tone="good"),
            AnalyticsMetricRead(label="Operating cash flow / debt", value="0.80", tone="good"),
            AnalyticsMetricRead(label="Price in 52W range", value="60.0%", tone="watch"),
        ],
        news=[CompanyNewsRead(title="Infosys market update", publisher="Provider")],
        source_notes=[f"Analytics model: {MODEL_VERSION}."],
    )


def test_company_analytics_decision_signal_is_conservative_and_explainable() -> None:
    service = CompanyAnalyticsService(portfolio_repo=None)

    signal = service._decision_signals([_company()])[0]

    assert signal.symbol == "INFY"
    assert signal.action == "Add Candidate"
    assert signal.confidence >= 70
    assert signal.conviction_score >= 70
    assert "BI" in signal.reasoning
    assert signal.entry_discipline
    assert signal.exit_guard


def test_company_analytics_sanity_checks_fail_when_no_holdings() -> None:
    service = CompanyAnalyticsService(portfolio_repo=None)

    checks = service._sanity_checks([], [])

    assert checks[0].status == "fail"
    assert "No holdings" in checks[0].detail


def test_company_analytics_quality_penalizes_missing_data() -> None:
    service = CompanyAnalyticsService(portfolio_repo=None)
    company = _company(score=55)
    company.financials = [
        AnalyticsMetricRead(label="Revenue growth", value="N/A", detail="Missing", tone="neutral")
        for _ in range(4)
    ]
    checks = service._sanity_checks([company], ["Missing provider data."])

    quality = service._quality_score([company], checks)

    assert quality < 60


def test_company_analytics_withholds_unverified_live_price() -> None:
    service = CompanyAnalyticsService(portfolio_repo=None)

    company = service._apply_verified_market_snapshot(
        _company(),
        MarketSnapshot(
            symbol="INFY",
            provider_symbol="INFY.NS",
            source="consensus:yahoo+alpha_vantage",
            warnings=["Rejected consensus last price for INFY."],
        ),
    )

    assert company.last_price is None
    assert company.day_change_pct is None
    assert any("Withheld live price" in note for note in company.source_notes)


def test_weighted_scoring_engine_uses_required_multi_factor_weights() -> None:
    service = CompanyAnalyticsService(portfolio_repo=None)

    final_score = service._weighted_final_score(
        fundamental=80,
        technical=70,
        valuation=60,
        risk=50,
        governance=40,
        sector=30,
        news=20,
        sentiment=10,
    )

    assert sum(SCORING_WEIGHTS.values()) == 1
    assert final_score == 62


def test_recommendation_bands_follow_final_score_and_risk_gate() -> None:
    service = CompanyAnalyticsService(portfolio_repo=None)

    assert service._recommendation(96, risk=70) == "Strong Conviction Buy"
    assert service._recommendation(82, risk=70) == "Buy"
    assert service._recommendation(64, risk=70) == "Hold"
    assert service._recommendation(45, risk=70) == "Reduce"
    assert service._recommendation(35, risk=70) == "Sell"
    assert service._recommendation(82, risk=20) == "Reduce"
