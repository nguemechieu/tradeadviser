"""Reasoning providers for AI decision-making in InvestPro trade advisory."""

from __future__ import annotations

import asyncio
import json
import math
import time
from typing import Any, Optional

import aiohttp

from .prompt_engine import PromptEngine
from .schema import ReasoningResult


class HeuristicReasoningProvider:
    """Local fallback reasoning provider.

    This provider never calls an external API. It reviews the sanitized
    reasoning context and returns a conservative ReasoningResult.
    """

    name = "heuristic"

    async def evaluate(
        self,
        *,
        messages: Optional[list[dict[str, Any]]] = None,
        context: Optional[dict[str, Any]] = None,
        mode: str = "assistive",
    ) -> ReasoningResult:
        start = time.perf_counter()

        context = dict(context or {})
        normalized_mode = str(
            mode or "assistive").strip().lower() or "assistive"

        signal_side = str(context.get("strategy_signal") or "").strip().upper()
        signal_confidence = self._clamp(
            self._coerce_float(context.get("signal_confidence"), 0.0),
            0.0,
            1.0,
        )

        indicators = dict(context.get("indicators") or {})
        regime = dict(context.get("regime") or {})
        portfolio = dict(context.get("portfolio") or {})
        risk_limits = dict(context.get("risk_limits") or {})

        price = self._coerce_float(context.get("price"), 0.0)
        quantity = self._coerce_float(context.get("quantity"), 0.0)
        notional = self._coerce_float(
            context.get("notional"), abs(price * quantity))
        order_notional_pct = self._coerce_float(
            context.get("order_notional_pct"), 0.0)

        rsi = self._coerce_float(indicators.get("rsi"), default=None)
        atr_pct = self._coerce_float(
            regime.get("atr_pct", indicators.get("atr_pct")),
            default=0.0,
        )
        trend_strength = self._coerce_float(
            regime.get("trend_strength", indicators.get("trend_strength")),
            default=0.0,
        )
        momentum = self._coerce_float(
            regime.get("momentum", indicators.get("momentum")),
            default=0.0,
        )
        band_position = self._coerce_float(
            regime.get("band_position", indicators.get("band_position")),
            default=0.5,
        )

        gross_exposure = self._coerce_float(
            portfolio.get("gross_exposure"), default=0.0)
        equity = max(1.0, self._coerce_float(
            portfolio.get("equity"), default=1.0))
        exposure_pct = self._coerce_float(
            portfolio.get("gross_exposure_pct"),
            default=gross_exposure / equity,
        )

        max_gross_exposure_pct = self._coerce_float(
            risk_limits.get("max_gross_exposure_pct"),
            default=2.0,
        )
        max_position_size_pct = self._coerce_float(
            risk_limits.get("max_position_size_pct"),
            default=0.10,
        )

        warnings: list[str] = []
        support: list[str] = []
        opposition: list[str] = []

        regime_state = str(
            regime.get("state")
            or regime.get("regime")
            or regime.get("name")
            or "unknown"
        ).strip().lower()

        volatility = str(regime.get("volatility") or "unknown").strip().lower()

        # --------------------------------------------------------------
        # Basic context validation
        # --------------------------------------------------------------

        if signal_side not in {"BUY", "SELL", "HOLD"}:
            opposition.append(
                "The strategy signal is not a recognized BUY, SELL, or HOLD action.")
            warnings.append("Signal direction is invalid or missing.")

        if price <= 0:
            opposition.append(
                "The proposed trade has no valid execution price.")
            warnings.append("Invalid or missing price.")

        if quantity <= 0 and signal_side in {"BUY", "SELL"}:
            opposition.append(
                "The proposed trade has no valid positive quantity.")
            warnings.append("Invalid or missing quantity.")

        if signal_confidence <= 0:
            opposition.append(
                "The strategy signal confidence is missing or zero.")

        # --------------------------------------------------------------
        # Regime / volatility
        # --------------------------------------------------------------

        if volatility == "high" or regime_state in {"volatile", "high_volatility"}:
            warnings.append(
                "High volatility can amplify slippage and stop-out risk.")
            opposition.append("The volatility regime is elevated.")

        if atr_pct >= 0.05:
            warnings.append(
                f"ATR percentage is high at {atr_pct:.3f}, suggesting abnormal volatility.")
            opposition.append(
                "ATR-based volatility is above a conservative threshold.")
        elif atr_pct >= 0.02:
            support.append(
                "ATR percentage is moderate and still within tradable conditions.")

        if trend_strength <= 0:
            opposition.append("Trend strength is weak or unavailable.")
        elif trend_strength >= 0.45:
            support.append(
                "Trend strength is supportive enough for a directional setup.")
        elif trend_strength < 0.20:
            opposition.append(
                "Trend strength is weak, which reduces directional edge.")

        # --------------------------------------------------------------
        # Directional signal checks
        # --------------------------------------------------------------

        if signal_side == "BUY":
            support.append("The upstream strategy produced a bullish signal.")

            if rsi is not None and rsi <= 35:
                support.append(
                    f"RSI at {rsi:.1f} supports an oversold rebound thesis.")
            elif rsi is not None and rsi >= 75:
                opposition.append(
                    f"RSI at {rsi:.1f} is overbought for a new long entry.")

            if regime_state in {"bullish", "trending_up", "uptrend"}:
                support.append("The market regime supports long exposure.")
            elif regime_state in {"bearish", "trending_down", "downtrend"}:
                opposition.append(
                    "The broader regime is bearish against the long idea.")

            if momentum < -0.01:
                opposition.append(
                    "Momentum is negative against the bullish signal.")

        elif signal_side == "SELL":
            support.append("The upstream strategy produced a bearish signal.")

            if rsi is not None and rsi >= 65:
                support.append(
                    f"RSI at {rsi:.1f} supports an overbought mean-reversion thesis.")
            elif rsi is not None and rsi <= 25:
                opposition.append(
                    f"RSI at {rsi:.1f} is oversold for a new short entry.")

            if regime_state in {"bearish", "trending_down", "downtrend"}:
                support.append("The market regime supports short exposure.")
            elif regime_state in {"bullish", "trending_up", "uptrend"}:
                opposition.append(
                    "The broader regime is bullish against the short idea.")

            if momentum > 0.01:
                opposition.append(
                    "Momentum is positive against the bearish signal.")

        else:
            opposition.append(
                "The signal is not directional enough for execution.")

        # --------------------------------------------------------------
        # Portfolio / exposure checks
        # --------------------------------------------------------------

        if exposure_pct >= max_gross_exposure_pct:
            warnings.append(
                f"Gross exposure {exposure_pct:.2f} is above the configured ceiling {max_gross_exposure_pct:.2f}."
            )
            opposition.append(
                "Portfolio exposure is above the configured limit.")
        elif exposure_pct >= max_gross_exposure_pct * 0.75:
            warnings.append("Portfolio exposure is already elevated.")
            opposition.append("Available risk budget is limited.")

        if order_notional_pct >= max_position_size_pct > 0:
            warnings.append(
                f"Order notional {order_notional_pct:.2%} exceeds max position size {max_position_size_pct:.2%}."
            )
            opposition.append(
                "The proposed order is too large versus configured position limits.")
        elif order_notional_pct >= max_position_size_pct * 0.75:
            warnings.append(
                "Order size is close to the configured maximum position size.")

        # --------------------------------------------------------------
        # Confidence and decision
        # --------------------------------------------------------------

        score = 0.0
        score += signal_confidence * 0.55
        score += min(max(trend_strength, 0.0), 1.0) * 0.15
        score += max(0.0, 1.0 - min(exposure_pct /
                     max(max_gross_exposure_pct, 1e-9), 1.5)) * 0.15
        score += max(0.0, 1.0 - min(atr_pct / 0.06, 1.5)) * 0.15

        if opposition:
            score -= min(len(opposition), 5) * 0.05

        if warnings:
            score -= min(len(warnings), 5) * 0.03

        score = self._clamp(score, 0.0, 1.0)

        if signal_confidence < 0.40:
            decision = "REJECT"
            warnings.append(
                "Quant signal confidence is too low for execution.")
        elif signal_confidence < 0.60:
            decision = "NEUTRAL"
        else:
            decision = "APPROVE"

        if signal_side == "HOLD":
            decision = "REJECT"

        if price <= 0 or quantity <= 0:
            decision = "REJECT"

        if exposure_pct >= max_gross_exposure_pct:
            decision = "REJECT"

        if order_notional_pct >= max_position_size_pct > 0:
            decision = "REJECT"

        if volatility == "high" and decision == "APPROVE":
            decision = "NEUTRAL"

        if normalized_mode == "autonomous":
            if warnings and decision == "APPROVE":
                decision = "NEUTRAL"
            if signal_confidence < 0.65:
                decision = "NEUTRAL" if decision != "REJECT" else "REJECT"

        risk_label = "Low"
        if (
            volatility == "high"
            or atr_pct >= 0.04
            or exposure_pct >= max_gross_exposure_pct * 0.75
            or order_notional_pct >= max_position_size_pct * 0.75
        ):
            risk_label = "High"
        elif volatility == "medium" or atr_pct >= 0.02 or exposure_pct >= max_gross_exposure_pct * 0.35:
            risk_label = "Moderate"

        if not support:
            support.append(
                "The setup is mainly supported by the upstream strategy signal.")

        if not opposition:
            opposition.append(
                "No major contradictory factor was detected in the sanitized context.")

        reasoning = self._build_reasoning_text(
            support=support,
            opposition=opposition,
            warnings=warnings,
            decision=decision,
            risk=risk_label,
        )

        should_execute = decision == "APPROVE"

        latency_ms = (time.perf_counter() - start) * 1000.0

        return ReasoningResult(
            decision=decision,
            confidence=score if score > 0 else signal_confidence,
            reasoning=reasoning,
            risk=risk_label,
            warnings=self._dedupe(warnings),
            provider=self.name,
            mode=normalized_mode,
            should_execute=should_execute,
            latency_ms=latency_ms,
            payload={
                "supporting_factors": self._dedupe(support),
                "opposing_factors": self._dedupe(opposition),
                "support": self._dedupe(support),
                "opposition": self._dedupe(opposition),
                "exposure_pct": exposure_pct,
                "order_notional_pct": order_notional_pct,
                "regime_state": regime_state,
                "volatility": volatility,
                "atr_pct": atr_pct,
                "trend_strength": trend_strength,
                "momentum": momentum,
                "band_position": band_position,
                "notional": notional,
            },
        )

    def _build_reasoning_text(
        self,
        *,
        support: list[str],
        opposition: list[str],
        warnings: list[str],
        decision: str,
        risk: str,
    ) -> str:
        first_support = support[0] if support else "No strong supporting factor was found."
        first_opposition = opposition[0] if opposition else "No major opposing factor was found."
        first_warning = warnings[0] if warnings else ""

        text = f"{decision}: {first_support} {first_opposition} Risk is {risk}."
        if first_warning:
            text += f" Warning: {first_warning}"

        return text.strip()

    @staticmethod
    def _coerce_float(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
        if value in (None, ""):
            return default
        try:
            number = float(value)
        except Exception:
            return default
        if not math.isfinite(number):
            return default
        return number

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, float(value)))

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        output: list[str] = []
        seen: set[str] = set()
        for value in values:
            text = str(value or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            output.append(text)
        return output


class OpenAIReasoningProvider:
    """OpenAI-backed reasoning provider.

    Uses the Responses API and expects the prompt to request strict JSON.
    Falls back safely by raising errors to the caller, so the main
    ReasoningEngine can use the heuristic provider.
    """

    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-5-mini",
        timeout_seconds: float = 10.0,
        logger: Any = None,
        max_retries: int = 1,
        retry_delay_seconds: float = 0.75,
        prompt_engine: Optional[PromptEngine] = None,
    ) -> None:
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "gpt-5-mini").strip() or "gpt-5-mini"
        self.timeout_seconds = max(1.0, float(timeout_seconds or 10.0))
        self.logger = logger
        self.max_retries = max(0, int(max_retries or 0))
        self.retry_delay_seconds = max(0.0, float(retry_delay_seconds or 0.0))
        self.prompt_engine = prompt_engine or PromptEngine()

    async def evaluate(
        self,
        *,
        messages: Optional[list[dict[str, Any]]] = None,
        context: Optional[dict[str, Any]] = None,
        mode: str = "assistive",
    ) -> ReasoningResult:
        if not self.api_key:
            raise RuntimeError("OpenAI API key is not configured.")

        normalized_mode = str(
            mode or "assistive").strip().lower() or "assistive"
        context_payload = dict(context or {})

        if not messages:
            messages = self.prompt_engine.build_messages(
                context_payload, mode=normalized_mode)

        request_payload = {
            "model": self.model,
            "input": list(messages or []),
            "text": {
                "format": {
                    "type": "json_object",
                }
            },
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        start = time.perf_counter()
        data: dict[str, Any] | None = None
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                data = await self._post_responses_api(request_payload, headers)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                if self.logger:
                    try:
                        self.logger.warning(
                            "OpenAI reasoning attempt %s/%s failed: %s",
                            attempt + 1,
                            self.max_retries + 1,
                            exc,
                        )
                    except Exception:
                        pass

                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay_seconds * (attempt + 1))

        if last_error is not None:
            raise last_error

        text = self._response_text(data or {})
        parsed_payload = self._extract_json_object(text)

        if not isinstance(parsed_payload, dict):
            raise RuntimeError(
                "OpenAI reasoning response did not contain a valid JSON object.")

        normalized_payload = self.prompt_engine.normalize_response(
            parsed_payload)

        latency_ms = (time.perf_counter() - start) * 1000.0

        return ReasoningResult.from_payload(
            normalized_payload,
            provider=self.name,
            mode=normalized_mode,
            latency_ms=latency_ms,
            payload={
                "raw_response": text,
                "raw_payload": parsed_payload,
                "context_symbol": context_payload.get("symbol"),
                "model": self.model,
            },
        )

    async def _post_responses_api(
        self,
        payload: dict[str, Any],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)
        ) as session:
            async with session.post(
                "https://api.openai.com/v1/responses",
                json=payload,
                headers=headers,
            ) as response:
                data = await response.json(content_type=None)

                if response.status >= 400:
                    message = (
                        data.get("error", {}).get("message")
                        if isinstance(data, dict)
                        else None
                    ) or str(data)
                    raise RuntimeError(
                        f"OpenAI reasoning request failed: {message}")

                if not isinstance(data, dict):
                    raise RuntimeError(
                        "OpenAI reasoning response was not a JSON object.")

                return data

    def _response_text(self, data: dict[str, Any]) -> str:
        response_text = data.get("output_text")
        if isinstance(response_text, str) and response_text.strip():
            return response_text.strip()

        parts: list[str] = []

        for item in data.get("output", []) or []:
            if not isinstance(item, dict):
                continue

            for content in item.get("content", []) or []:
                if not isinstance(content, dict):
                    continue

                content_text = content.get("text")
                if isinstance(content_text, str) and content_text.strip():
                    parts.append(content_text.strip())
                    continue

                # Some Responses API payloads use nested output_text structures.
                if content.get("type") == "output_text":
                    text = content.get("text")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())

        return "\n".join(parts).strip()

    def _extract_json_object(self, text: str) -> dict[str, Any] | None:
        body = str(text or "").strip()
        if not body:
            return None

        # Remove common accidental markdown fences.
        if body.startswith("```"):
            body = body.strip("`").strip()
            if body.lower().startswith("json"):
                body = body[4:].strip()

        try:
            parsed = json.loads(body)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            pass

        start_index = body.find("{")
        end_index = body.rfind("}")

        if start_index < 0 or end_index <= start_index:
            return None

        try:
            parsed = json.loads(body[start_index: end_index + 1])
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
