import json
from datetime import UTC, datetime
from typing import Any

import httpx

from src.core.config import settings
from src.core.security import token_cipher
from src.domain.auth import UserContext
from src.repositories.app_settings import AppSettingsRepository
from src.schemas.ai_config import AiAnalyticsInsightRead, AiProvider
from src.schemas.analytics import PortfolioAnalyticsRead
from src.services.openai_settings_service import OpenAiSettingsService


GEMINI_FALLBACK_MODELS = ["gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-2.5-flash-lite"]


class OpenAiAnalyticsService:
    def __init__(self, settings_repo: AppSettingsRepository) -> None:
        self._settings = OpenAiSettingsService(settings_repo)

    async def generate(
        self,
        context: UserContext,
        analytics: PortfolioAnalyticsRead,
    ) -> AiAnalyticsInsightRead:
        provider = await self._settings.get_provider(context)
        api_key = await self._settings.get_api_key(context, provider)
        model = await self._settings.get_model(context, provider)
        if not api_key:
            result = AiAnalyticsInsightRead(
                configured=False,
                provider=provider,
                model=model,
                summary=f"{self._provider_label(provider)} is not configured. Add your API key in AI Config to generate AI analytics.",
                data_warnings=[f"No {self._provider_label(provider)} API key is configured."],
            )
            await self._store_latest(context, result)
            return result
        if not analytics.companies:
            result = AiAnalyticsInsightRead(
                configured=True,
                provider=provider,
                generated_at=datetime.now(UTC),
                model=model,
                summary="No portfolio holdings are available, so AI analysis was not generated.",
                data_warnings=["Sync Zerodha or import holdings before generating AI analytics."],
            )
            await self._store_latest(context, result)
            return result

        try:
            data = self._prompt_payload(analytics)
            if provider == "gemini":
                payload, used_model, retry_warnings = await self._call_gemini(api_key, model, data)
                result = self._parse_response(payload, provider, used_model, analytics, retry_warnings)
                await self._store_latest(context, result)
                return result
            payload = await self._call_openai(api_key, model, data)
            result = self._parse_response(payload, provider, model, analytics)
            await self._store_latest(context, result)
            return result
        except (httpx.HTTPError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            error_detail = self._safe_error_detail(exc)
            result = AiAnalyticsInsightRead(
                configured=True,
                provider=provider,
                generated_at=datetime.now(UTC),
                model=model,
                summary=f"{self._provider_label(provider)} analytics could not be generated. The calculated backend decision signals are still available.",
                data_warnings=[
                    f"{self._provider_label(provider)} request failed: {error_detail}.",
                    "Try a different Gemini model in AI Config if this repeats.",
                ],
            )
            await self._store_latest(context, result)
            return result

    async def _store_latest(self, context: UserContext, result: AiAnalyticsInsightRead) -> None:
        await self._settings._settings_repo.upsert(
            context,
            "latest_ai_analytics_snapshot",
            token_cipher.encrypt(result.model_dump_json(by_alias=True)),
        )

    async def _call_openai(self, api_key: str, model: str, data: dict[str, Any]) -> dict[str, Any]:
        instructions = self._instructions()
        user_content = json.dumps(data, ensure_ascii=True)
        async with httpx.AsyncClient(timeout=max(10.0, settings.openai_timeout_seconds)) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "instructions": instructions,
                    "input": user_content,
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "portfolio_ai_analytics",
                            "schema": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "summary": {"type": "string"},
                                    "buyFocus": {"type": "array", "items": {"type": "string"}},
                                    "holdFocus": {"type": "array", "items": {"type": "string"}},
                                    "sellOrReviewFocus": {"type": "array", "items": {"type": "string"}},
                                    "riskControls": {"type": "array", "items": {"type": "string"}},
                                    "dataWarnings": {"type": "array", "items": {"type": "string"}},
                                },
                                "required": [
                                    "summary",
                                    "buyFocus",
                                    "holdFocus",
                                    "sellOrReviewFocus",
                                    "riskControls",
                                    "dataWarnings",
                                ],
                            },
                        }
                    },
                },
            )
            response.raise_for_status()
            return response.json()

    async def _call_gemini(
        self, api_key: str, model: str, data: dict[str, Any]
    ) -> tuple[dict[str, Any], str, list[str]]:
        user_content = json.dumps(data, ensure_ascii=True)
        models_to_try = [model] + [
            fallback for fallback in GEMINI_FALLBACK_MODELS if fallback != model
        ]
        retry_warnings: list[str] = []
        last_error: Exception | None = None

        async with httpx.AsyncClient(timeout=max(10.0, settings.openai_timeout_seconds)) as client:
            for index, candidate_model in enumerate(models_to_try):
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{candidate_model}:generateContent",
                    params={"key": api_key},
                    headers={"Content-Type": "application/json"},
                    json={
                        "systemInstruction": {
                            "parts": [{"text": self._instructions()}],
                        },
                        "contents": [
                            {
                                "role": "user",
                                "parts": [{"text": user_content}],
                            }
                        ],
                        "generationConfig": {
                            "temperature": 0.2,
                            "responseMimeType": "application/json",
                        },
                    },
                )
                try:
                    response.raise_for_status()
                    if index > 0:
                        retry_warnings.append(
                            f"Gemini model {model} failed, so analysis used fallback model {candidate_model}."
                        )
                    return response.json(), candidate_model, retry_warnings
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    retry_warnings.append(
                        f"Gemini model {candidate_model} failed: {self._safe_error_detail(exc)}."
                    )
                    if exc.response.status_code in {400, 401, 403} and "API key not valid" in self._safe_error_detail(exc):
                        raise exc
                except httpx.TimeoutException as exc:
                    last_error = exc
                    retry_warnings.append(
                        f"Gemini model {candidate_model} timed out after {settings.openai_timeout_seconds:.0f} seconds."
                    )
                    continue
            if last_error:
                raise last_error
        raise ValueError("Gemini request did not return a response.")

    def _prompt_payload(self, analytics: PortfolioAnalyticsRead) -> dict[str, Any]:
        return {
            "modelVersion": analytics.model_version,
            "generatedAt": analytics.generated_at.isoformat(),
            "cachedForDate": analytics.cached_for_date.isoformat(),
            "nextRefreshAt": analytics.next_refresh_at.isoformat(),
            "dataQualityScore": analytics.data_quality_score,
            "summary": analytics.summary,
            "sanityChecks": [
                check.model_dump(mode="json", by_alias=True) for check in analytics.sanity_checks
            ],
            "decisionSignals": [
                signal.model_dump(mode="json", by_alias=True) for signal in analytics.decision_signals[:10]
            ],
            "companies": [
                {
                    "symbol": company.symbol,
                    "companyName": company.company_name,
                    "sector": company.sector,
                    "industry": company.industry,
                    "currency": company.currency,
                    "lastPrice": company.last_price,
                    "dayChangePct": company.day_change_pct,
                    "fiftyTwoWeekLow": company.fifty_two_week_low,
                    "fiftyTwoWeekHigh": company.fifty_two_week_high,
                    "overallScore": company.overall_score,
                    "balanceSheetScore": company.balance_sheet_score,
                    "growthScore": company.growth_score,
                    "cashFlowScore": company.cash_flow_score,
                    "valuationScore": company.valuation_score,
                    "recommendation": company.recommendation,
                    "planning": company.planning,
                    "strengths": company.strengths[:3],
                    "concerns": company.concerns[:3],
                    "financials": [
                        metric.model_dump(mode="json", by_alias=True) for metric in company.financials
                    ],
                    "news": [
                        {
                            "title": item.title,
                            "publisher": item.publisher,
                            "publishedAt": item.published_at.isoformat() if item.published_at else None,
                        }
                        for item in company.news[:3]
                    ],
                    "sourceNotes": company.source_notes[:4],
                }
                for company in analytics.companies[:10]
            ],
            "warnings": analytics.warnings,
        }

    def _parse_response(
        self,
        payload: dict[str, Any],
        provider: AiProvider,
        model: str,
        analytics: PortfolioAnalyticsRead,
        extra_warnings: list[str] | None = None,
    ) -> AiAnalyticsInsightRead:
        text = self._extract_text(provider, payload)
        parsed = json.loads(text or "{}")
        warnings = list(parsed.get("dataWarnings") or [])
        warnings.extend(extra_warnings or [])
        if analytics.data_quality_score < 70:
            warnings.append(f"Backend data quality is {analytics.data_quality_score}/100; verify before action.")
        return AiAnalyticsInsightRead(
            configured=True,
            provider=provider,
            generated_at=datetime.now(UTC),
            model=model,
            summary=self._clean_text(parsed.get("summary") or "AI analytics generated."),
            buy_focus=self._string_list(parsed.get("buyFocus")),
            hold_focus=self._string_list(parsed.get("holdFocus")),
            sell_or_review_focus=self._string_list(parsed.get("sellOrReviewFocus")),
            risk_controls=self._string_list(parsed.get("riskControls")),
            data_warnings=self._string_list(warnings),
        )

    def _extract_text(self, provider: AiProvider, payload: dict[str, Any]) -> str | None:
        if provider == "gemini":
            for candidate in payload.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    if part.get("text"):
                        return part["text"]
            return None

        text = payload.get("output_text")
        if not text:
            for item in payload.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") in {"output_text", "text"} and content.get("text"):
                        text = content["text"]
                        break
                if text:
                    break
        return text

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        output: list[str] = []
        for item in value:
            for line in str(item).splitlines():
                cleaned = self._clean_text(line)
                if cleaned:
                    output.append(cleaned)
        return output[:6]

    def _clean_text(self, value: Any) -> str:
        text = str(value or "").strip()
        text = text.replace("**", "").replace("__", "").replace("`", "")
        text = " ".join(text.split())
        for prefix in ("- ", "* ", "• "):
            if text.startswith(prefix):
                text = text[len(prefix) :].strip()
        if len(text) >= 3 and text[0].isdigit() and text[1] in {".", ")"}:
            text = text[2:].strip()
        return text

    def _safe_error_detail(self, exc: Exception) -> str:
        if isinstance(exc, httpx.HTTPStatusError):
            status_code = exc.response.status_code
            try:
                payload = exc.response.json()
            except json.JSONDecodeError:
                payload = {}
            error = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error, dict):
                message = str(error.get("message") or "").strip()
                status = str(error.get("status") or "").strip()
                parts = [f"HTTP {status_code}"]
                if status:
                    parts.append(status)
                if message:
                    parts.append(message[:220])
                return " - ".join(parts)
            return f"HTTP {status_code}"
        if isinstance(exc, httpx.TimeoutException):
            return "request timed out"
        if isinstance(exc, httpx.NetworkError):
            return "network error while contacting provider"
        return exc.__class__.__name__

    def _instructions(self) -> str:
        return (
            "You are a senior equity research analyst and portfolio risk manager with 20 years of Indian share-market "
            "experience. Analyze only the JSON payload supplied by the application. Focus only on the user's current "
            "portfolio holdings in the companies array. Never invent holdings, prices, ratios, financial statement data, "
            "news, targets, broker calls, dates, or guarantees. Treat the backend model scores, decisionSignals, sanityChecks, "
            "sourceNotes, financials, price position, growth, balance-sheet quality, cash-flow strength, valuation score and "
            "news headlines as the evidence base.\n\n"
            "Return strict JSON only with these exact keys: summary, buyFocus, holdFocus, sellOrReviewFocus, riskControls, "
            "dataWarnings. Do not include markdown, explanations outside JSON, or extra keys.\n\n"
            "Formatting rules:\n"
            "- Every JSON value must be plain text only. No markdown, bullets, numbering, tables, emojis, headings, or newline characters.\n"
            "- summary must be one compact paragraph with 3 to 5 sentences.\n"
            "- Every array item must be one short sentence, ideally 18 to 32 words.\n"
            "- Start symbol-specific items with the symbol followed by a colon, for example RELIANCE: Hold while cash-flow strength remains intact.\n\n"
            "Output requirements:\n"
            "- summary: 3 to 5 concise sentences giving the portfolio-level view, strongest opportunities, weakest risks, "
            "data quality, and what the investor should verify before action.\n"
            "- buyFocus: up to 5 symbol-specific items. Include only holdings where the data supports adding slowly. Mention "
            "the evidence, entry discipline, and one verification trigger. If no holding qualifies, return a cautious empty or "
            "wait message.\n"
            "- holdFocus: up to 5 symbol-specific items where the thesis is acceptable but not an aggressive add. Mention what "
            "must remain true for the hold thesis.\n"
            "- sellOrReviewFocus: up to 5 symbol-specific items where score weakness, risk flags, valuation stretch, weak "
            "cash-flow/balance-sheet data, poor trend, or low data confidence requires review, trimming discipline, or no fresh buying.\n"
            "- riskControls: up to 6 portfolio actions covering concentration, position sizing, staged buying, stop/review "
            "triggers, cash buffer, earnings/news verification, and invalidation points.\n"
            "- dataWarnings: list all important limitations from dataQualityScore, sanityChecks, warnings, missing financials, "
            "stale or partial news, missing live prices, or provider coverage gaps.\n\n"
            "Decision discipline:\n"
            "- Use symbols in every list item where possible.\n"
            "- Do not say 'guaranteed', 'sure shot', or 'must buy'. Use decision-support language.\n"
            "- Prefer staged actions such as add slowly, hold, wait, review, trim only if risk persists.\n"
            "- If dataQualityScore is below 70 or any sanity check is watch/fail, make verification a prominent warning.\n"
            "- If the payload has no companies, state that holdings must be synced/imported before analysis."
        )

    def _provider_label(self, provider: AiProvider) -> str:
        return "OpenAI" if provider == "openai" else "Gemini"
