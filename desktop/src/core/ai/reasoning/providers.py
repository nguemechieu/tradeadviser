from __future__ import annotations

import json
import time
from typing import Any

import aiohttp

from core.ai.reasoning.schema import ReasoningResult


class HeuristicReasoningProvider:
    name = "heuristic"

    async def evaluate(self, *, messages=None, context=None, mode="assistive") -> ReasoningResult:
        start = time.perf_counter()
        context = dict(context or {})
        signal_side = str(context.get("strategy_signal") or "").strip().upper()
        signal_confidence = self._coerce_float(context.get("signal_confidence"))
        indicators = dict(context.get("indicators") or {})
        regime = dict(context.get("regime") or {})
        portfolio = dict(context.get("portfolio") or {})
        risk_limits = dict(context.get("risk_limits") or {})

        rsi = self._coerce_float(indicators.get("rsi"), default=None)
        trend_strength = self._coerce_float(regime.get("trend_strength"), default=0.0)
        gross_exposure = self._coerce_float(portfolio.get("gross_exposure"), default=0.0)
        equity = max(1.0, self._coerce_float(portfolio.get("equity"), default=1.0))
        exposure_pct = gross_exposure / equity

        warnings = []
        support = []
        opposition = []

        regime_state = str(regime.get("state") or "unknown").strip().lower()
        volatility = str(regime.get("volatility") or "unknown").strip().lower()
        if volatility == "high":
            warnings.append("High volatility can amplify slippage and stop-out risk.")
        if exposure_pct >= 0.7:
            warnings.append("Portfolio exposure is already elevated.")

        if signal_side == "BUY":
            support.append("The underlying strategy already produced a bullish signal.")
            if rsi is not None and rsi <= 35:
                support.append(f"RSI at {rsi:.1f} supports an oversold rebound thesis.")
            if regime_state == "bullish":
                support.append("The current regime remains supportive for long entries.")
            if regime_state == "bearish":
                opposition.append("The broader regime is still bearish against the long idea.")
        elif signal_side == "SELL":
            support.append("The underlying strategy already produced a bearish signal.")
            if rsi is not None and rsi >= 65:
                support.append(f"RSI at {rsi:.1f} supports an overbought mean-reversion thesis.")
            if regime_state == "bearish":
                support.append("The current regime remains supportive for short entries.")
            if regime_state == "bullish":
                opposition.append("The broader regime is still bullish against the short idea.")
        else:
            opposition.append("The signal is not directional enough for execution.")

        if trend_strength <= 0:
            opposition.append("Trend strength is weak or deteriorating.")
        elif trend_strength >= 0.4:
            support.append("Trend strength is healthy enough to support continuation.")

        if signal_confidence < 0.4:
            decision = "REJECT"
            warnings.append("Quant signal confidence is too low for execution.")
        elif signal_confidence < 0.6:
            decision = "NEUTRAL"
        else:
            decision = "APPROVE"

        if exposure_pct >= 1.0:
            decision = "REJECT"
            warnings.append("Portfolio exposure is above the preferred ceiling.")
        elif exposure_pct >= 0.7 and decision == "APPROVE":
            decision = "NEUTRAL"

        risk_label = "Low"
        if volatility == "high" or exposure_pct >= 0.7:
            risk_label = "High"
        elif volatility == "medium" or exposure_pct >= 0.35:
            risk_label = "Moderate"

        if not support:
            support.append("The setup is being carried mainly by the upstream strategy signal.")
        if not opposition:
            opposition.append("No major contradictory factor was detected in the sanitized context.")

        reasoning = f"{support[0]} {opposition[0]}"
        should_execute = decision != "REJECT"
        latency_ms = (time.perf_counter() - start) * 1000.0
        return ReasoningResult(
            decision=decision,
            confidence=signal_confidence,
            reasoning=reasoning.strip(),
            risk=risk_label,
            warnings=warnings,
            provider=self.name,
            mode=mode,
            should_execute=should_execute,
            latency_ms=latency_ms,
            payload={
                "support": support,
                "opposition": opposition,
                "exposure_pct": exposure_pct,
                "regime_state": regime_state,
            },
        )

    @staticmethod
    def _coerce_float(value, default=0.0):
        if value in (None, ""):
            return default
        try:
            return float(value)
        except Exception:
            return default


class OpenAIReasoningProvider:
    name = "openai"

    def __init__(self, *, api_key: str, model: str = "gpt-5-mini", timeout_seconds: float = 10.0, logger=None) -> None:
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "gpt-5-mini").strip() or "gpt-5-mini"
        self.timeout_seconds = max(1.0, float(timeout_seconds or 10.0))
        self.logger = logger

    async def evaluate(self, *, messages=None, context=None, mode="assistive") -> ReasoningResult:
        if not self.api_key:
            raise RuntimeError("OpenAI API key is not configured.")

        payload = {
            "model": self.model,
            "input": list(messages or []),
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        start = time.perf_counter()
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as session:
            async with session.post("https://api.openai.com/v1/responses", json=payload, headers=headers) as response:
                data = await response.json(content_type=None)
                if response.status >= 400:
                    message = data.get("error", {}).get("message") or str(data)
                    raise RuntimeError(f"OpenAI reasoning request failed: {message}")

        text = self._response_text(data)
        payload = self._extract_json_object(text)
        if not isinstance(payload, dict):
            raise RuntimeError("OpenAI reasoning response did not contain a valid JSON object.")

        latency_ms = (time.perf_counter() - start) * 1000.0
        return ReasoningResult.from_payload(
            payload,
            provider=self.name,
            mode=mode,
            latency_ms=latency_ms,
            payload={"raw_response": text, "context_symbol": dict(context or {}).get("symbol")},
        )

    def _response_text(self, data: dict[str, Any]) -> str:
        response_text = data.get("output_text")
        if isinstance(response_text, str) and response_text.strip():
            return response_text.strip()
        parts = []
        for item in data.get("output", []) or []:
            for content in item.get("content", []) or []:
                content_text = content.get("text")
                if isinstance(content_text, str) and content_text.strip():
                    parts.append(content_text.strip())
        return "\n".join(parts)

    def _extract_json_object(self, text: str) -> dict[str, Any] | None:
        body = str(text or "").strip()
        if not body:
            return None
        try:
            return json.loads(body)
        except Exception:
            pass

        start_index = body.find("{")
        end_index = body.rfind("}")
        if start_index < 0 or end_index <= start_index:
            return None
        try:
            return json.loads(body[start_index : end_index + 1])
        except Exception:
            return None
