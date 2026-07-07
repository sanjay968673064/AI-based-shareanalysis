from src.schemas.intelligence import TechnicalAnalysisRead
from src.services.intelligence_providers import MarketSnapshot


class TechnicalAnalysisService:
    def analyze(self, holding: dict, snapshot: MarketSnapshot | None = None) -> TechnicalAnalysisRead:
        if snapshot and len(snapshot.closes) >= 20:
            return self._from_snapshot(holding, snapshot)
        return self._from_holding(holding, snapshot)

    def _from_snapshot(self, holding: dict, snapshot: MarketSnapshot) -> TechnicalAnalysisRead:
        closes = snapshot.closes
        highs = snapshot.highs
        lows = snapshot.lows
        last = snapshot.last_price or closes[-1]
        ema_20 = self._ema(closes, 20)
        ema_50 = self._ema(closes, 50)
        ema_100 = self._ema(closes, 100)
        ema_200 = self._ema(closes, 200)
        rsi = self._rsi(closes, 14)
        macd, signal = self._macd(closes)
        atr = self._atr(highs, lows, closes, 14)
        trend = self._trend(last, ema_20, ema_50)
        momentum = self._momentum_score(closes, rsi, trend)
        supports = self._levels(lows, last, below=True) or [round(last * 0.95, 2)]
        resistances = self._levels(highs, last, below=False) or [round(last * 1.08, 2)]
        notes = [
            f"Technical signals use {snapshot.source} OHLCV for {snapshot.provider_symbol}.",
        ]
        notes.extend(snapshot.warnings)
        if ema_200 is None:
            notes.append("Long-term EMA is unavailable because fewer than 200 daily closes were returned.")

        return TechnicalAnalysisRead(
            rsi_14=self._round_optional(rsi),
            macd=self._round_optional(macd),
            signal_line=self._round_optional(signal),
            ema_20=self._round_optional(ema_20),
            ema_50=self._round_optional(ema_50),
            ema_100=self._round_optional(ema_100),
            ema_200=self._round_optional(ema_200),
            atr=self._round_optional(atr),
            adx=None,
            support_levels=supports,
            resistance_levels=resistances,
            trend_direction=trend,
            momentum_score=momentum,
            notes=notes,
        )

    def _from_holding(self, holding: dict, snapshot: MarketSnapshot | None) -> TechnicalAnalysisRead:
        value = float(holding["quantity"]) * float(holding["last_price"])
        day_pnl = float(holding["day_pnl"])
        day_return = (day_pnl / max(value - day_pnl, 1)) * 100
        trend = "uptrend" if day_return > 1 else "downtrend" if day_return < -1 else "sideways"
        momentum = int(max(0, min(100, 50 + day_return * 10)))
        notes = [
            "Historical OHLCV data is unavailable for this holding.",
            "RSI, MACD, EMA, ATR, ADX, VWAP and volume profile require historical price data.",
        ]
        if snapshot:
            notes.extend(snapshot.warnings)
        return TechnicalAnalysisRead(
            support_levels=[round(float(holding["last_price"]) * 0.95, 2)],
            resistance_levels=[round(float(holding["last_price"]) * 1.08, 2)],
            trend_direction=trend,
            momentum_score=momentum,
            notes=notes,
        )

    def _ema(self, values: list[float], period: int) -> float | None:
        if len(values) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period
        for value in values[period:]:
            ema = value * multiplier + ema * (1 - multiplier)
        return ema

    def _rsi(self, closes: list[float], period: int) -> float | None:
        if len(closes) <= period:
            return None
        gains = []
        losses = []
        for previous, current in zip(closes[-period - 1 : -1], closes[-period:]):
            change = current - previous
            gains.append(max(change, 0))
            losses.append(abs(min(change, 0)))
        average_gain = sum(gains) / period
        average_loss = sum(losses) / period
        if average_loss == 0:
            return 100.0
        rs = average_gain / average_loss
        return 100 - (100 / (1 + rs))

    def _macd(self, closes: list[float]) -> tuple[float | None, float | None]:
        if len(closes) < 35:
            return None, None
        ema_12 = self._ema(closes, 12)
        ema_26 = self._ema(closes, 26)
        if ema_12 is None or ema_26 is None:
            return None, None
        macd_line = ema_12 - ema_26
        macd_series = []
        for index in range(26, len(closes) + 1):
            short = self._ema(closes[:index], 12)
            long = self._ema(closes[:index], 26)
            if short is not None and long is not None:
                macd_series.append(short - long)
        signal = self._ema(macd_series, 9)
        return macd_line, signal

    def _atr(self, highs: list[float], lows: list[float], closes: list[float], period: int) -> float | None:
        if len(highs) <= period or len(lows) <= period or len(closes) <= period:
            return None
        true_ranges = []
        for index in range(1, len(closes)):
            true_ranges.append(
                max(
                    highs[index] - lows[index],
                    abs(highs[index] - closes[index - 1]),
                    abs(lows[index] - closes[index - 1]),
                )
            )
        return sum(true_ranges[-period:]) / period

    def _levels(self, values: list[float], last: float, below: bool) -> list[float]:
        if not values:
            return []
        window = values[-60:]
        candidates = [value for value in window if value < last] if below else [value for value in window if value > last]
        if not candidates:
            return []
        ordered = sorted(candidates, reverse=below)
        return [round(value, 2) for value in ordered[:2]]

    def _trend(self, last: float, ema_20: float | None, ema_50: float | None) -> str:
        if ema_20 is None:
            return "sideways"
        if ema_50 is None:
            return "uptrend" if last > ema_20 else "downtrend" if last < ema_20 else "sideways"
        if last > ema_20 > ema_50:
            return "uptrend"
        if last < ema_20 < ema_50:
            return "downtrend"
        return "sideways"

    def _momentum_score(self, closes: list[float], rsi: float | None, trend: str) -> int:
        score = 50
        if len(closes) >= 22 and closes[-22]:
            score += ((closes[-1] - closes[-22]) / closes[-22]) * 90
        if rsi is not None:
            score += (rsi - 50) * 0.35
        if trend == "uptrend":
            score += 8
        elif trend == "downtrend":
            score -= 8
        return int(max(0, min(100, score)))

    def _round_optional(self, value: float | None) -> float | None:
        return None if value is None else round(value, 2)
