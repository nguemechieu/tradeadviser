from __future__ import annotations

"""
InvestPro Signal Fanout

Runs multiple SignalAgent instances in parallel and merges their outputs.

Responsibilities:
- Execute signal agents concurrently
- Normalize candidate signals
- Deduplicate candidates
- Merge assigned strategy rows
- Preserve strongest candidate per fingerprint
- Handle news-bias blocks
- Sort candidates by adaptive/quality score
- Filter weak signals
- Return a clean merged context for consensus + aggregation agents
"""

import asyncio
import inspect
import math
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Optional


DEFAULT_MIN_CANDIDATE_CONFIDENCE = 0.30


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return float(default)

    try:
        number = float(value)
    except Exception:
        return float(default)

    if not math.isfinite(number):
        return float(default)

    return number


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _normalize_side(value: Any) -> str:
    text = str(value or "").strip().lower()

    if text in {"buy", "long"}:
        return "buy"

    if text in {"sell", "short"}:
        return "sell"

    if text in {"hold", "wait", "neutral", "none", ""}:
        return "hold"

    return "hold"


def _object_to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return dict(value)

    if is_dataclass(value):
        try:
            return asdict(value)
        except Exception:
            return {}

    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            result = value.to_dict()
            return dict(result or {}) if isinstance(result, dict) else {}
        except Exception:
            return {}

    output: dict[str, Any] = {}

    for key in (
        "symbol",
        "side",
        "action",
        "decision",
        "confidence",
        "amount",
        "price",
        "reason",
        "strategy_name",
        "source_strategy",
        "timeframe",
        "timestamp",
        "metadata",
        "adaptive_score",
        "adaptive_weight",
        "strategy_assignment_weight",
        "strategy_assignment_score",
        "risk_score",
        "risk_estimate",
        "expected_return",
        "alpha_score",
    ):
        if hasattr(value, key):
            output[key] = getattr(value, key)

    return output


def _timestamp_score(value: Any) -> float:
    if value in (None, ""):
        return 0.0

    if isinstance(value, (int, float)):
        timestamp = float(value)
        if abs(timestamp) > 1e11:
            timestamp = timestamp / 1000.0
        return timestamp

    if hasattr(value, "timestamp"):
        try:
            return float(value.timestamp())
        except Exception:
            return 0.0

    text = str(value or "").strip()
    if not text:
        return 0.0

    try:
        timestamp = float(text)
        if abs(timestamp) > 1e11:
            timestamp = timestamp / 1000.0
        return timestamp
    except Exception:
        pass

    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return float(parsed.timestamp())
    except Exception:
        return 0.0


def _normalize_candidate(candidate: Any) -> dict[str, Any] | None:
    if not isinstance(candidate, dict):
        return None

    candidate_copy = dict(candidate)
    signal = _object_to_dict(candidate_copy.get("signal"))

    if not signal:
        return None

    side = _normalize_side(
        signal.get("side")
        or signal.get("action")
        or signal.get("decision")
    )

    if side not in {"buy", "sell"}:
        return None

    confidence = _clamp(_safe_float(signal.get("confidence"), 0.0), 0.0, 1.0)

    strategy_weight = max(
        0.0001,
        _safe_float(signal.get("strategy_assignment_weight"), 1.0),
    )
    adaptive_weight = max(
        0.0001,
        _safe_float(signal.get("adaptive_weight"), 1.0),
    )
    explicit_weight = max(
        0.0001,
        _safe_float(signal.get("weight"), 1.0),
    )

    weighted_confidence = confidence * strategy_weight
    quality = confidence * strategy_weight * adaptive_weight * explicit_weight

    adaptive_score = _safe_float(
        signal.get("adaptive_score"),
        default=quality,
    )

    signal["side"] = side
    signal["confidence"] = confidence
    signal["strategy_assignment_weight"] = strategy_weight
    signal["adaptive_weight"] = adaptive_weight
    signal["weight"] = explicit_weight
    signal["weighted_confidence"] = weighted_confidence
    signal["quality"] = quality
    signal["adaptive_score"] = adaptive_score

    if not signal.get("timestamp"):
        signal["timestamp"] = datetime.now(timezone.utc).isoformat()

    candidate_copy["signal"] = signal
    candidate_copy.setdefault("agent_name", signal.get(
        "signal_source_agent") or signal.get("agent_name") or "")
    candidate_copy.setdefault(
        "strategy_name", signal.get("strategy_name") or "")
    candidate_copy.setdefault("timeframe", signal.get("timeframe") or "")
    candidate_copy.setdefault("side", side)

    return candidate_copy


def _merge_assignment_rows(existing_rows: Any, new_rows: Any) -> list[dict[str, Any]]:
    merged_rows = [
        dict(row)
        for row in list(existing_rows or [])
        if isinstance(row, dict)
    ]

    fingerprints = {
        (
            str(row.get("strategy_name") or "").strip(),
            str(row.get("timeframe") or "").strip(),
        )
        for row in merged_rows
    }

    for row in list(new_rows or []):
        if not isinstance(row, dict):
            continue

        fingerprint = (
            str(row.get("strategy_name") or "").strip(),
            str(row.get("timeframe") or "").strip(),
        )

        if fingerprint in fingerprints:
            continue

        merged_rows.append(dict(row))
        fingerprints.add(fingerprint)

    return merged_rows


def _candidate_fingerprint(candidate: Any) -> tuple[str, str, str, str, str]:
    candidate_dict = dict(candidate or {})
    signal = dict(candidate_dict.get("signal") or {})

    return (
        str(candidate_dict.get("agent_name") or signal.get(
            "signal_source_agent") or "").strip(),
        str(signal.get("strategy_name") or candidate_dict.get(
            "strategy_name") or "").strip(),
        str(signal.get("timeframe") or candidate_dict.get(
            "timeframe") or "").strip(),
        str(signal.get("side") or candidate_dict.get(
            "side") or "").strip().lower(),
        str(signal.get("symbol") or candidate_dict.get(
            "symbol") or "").strip().upper(),
    )


def _candidate_rank(candidate: Any) -> tuple[float, float, float, float, float, float]:
    signal = dict((candidate or {}).get("signal") or {})

    adaptive_score = _safe_float(signal.get("adaptive_score"), 0.0)
    quality = _safe_float(signal.get("quality"), 0.0)
    weighted_confidence = _safe_float(
        signal.get("weighted_confidence"),
        _safe_float(signal.get("confidence"), 0.0)
        * max(0.0001, _safe_float(signal.get("strategy_assignment_weight"), 1.0)),
    )
    confidence = _safe_float(signal.get("confidence"), 0.0)
    inverse_risk = 1.0 - _clamp(
        _safe_float(signal.get(
            "risk_score", signal.get("risk_estimate")), 0.5),
        0.0,
        1.0,
    )
    recency = _timestamp_score(signal.get(
        "timestamp") or (candidate or {}).get("timestamp"))

    return (
        adaptive_score,
        quality,
        weighted_confidence,
        confidence,
        inverse_risk,
        recency,
    )


def _merge_candidate(
    merged_candidates: list[dict[str, Any]],
    seen_candidates: dict[tuple[str, str, str, str, str], int],
    candidate: Any,
) -> None:
    candidate_copy = _normalize_candidate(candidate)
    if candidate_copy is None:
        return

    fingerprint = _candidate_fingerprint(candidate_copy)
    existing_index = seen_candidates.get(fingerprint)

    if existing_index is None:
        seen_candidates[fingerprint] = len(merged_candidates)
        merged_candidates.append(candidate_copy)
        return

    if _candidate_rank(candidate_copy) > _candidate_rank(merged_candidates[existing_index]):
        merged_candidates[existing_index] = candidate_copy


def _unique_reasons(reasons: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()

    for reason in reasons:
        text = str(reason or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)

    return output


def _candidate_preview(candidates: list[dict[str, Any]], *, limit: int = 20) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []

    for index, candidate in enumerate(list(candidates or [])[:limit], start=1):
        signal = dict(candidate.get("signal") or {})
        preview.append(
            {
                "rank": index,
                "agent_name": candidate.get("agent_name"),
                "strategy_name": signal.get("strategy_name"),
                "timeframe": signal.get("timeframe"),
                "side": signal.get("side"),
                "confidence": signal.get("confidence"),
                "quality": signal.get("quality"),
                "adaptive_score": signal.get("adaptive_score"),
                "weighted_confidence": signal.get("weighted_confidence"),
                "reason": signal.get("reason"),
            }
        )

    return preview


def merge_signal_agent_results(
    context: dict[str, Any],
    results: list[Any],
    *,
    min_candidate_confidence: float = DEFAULT_MIN_CANDIDATE_CONFIDENCE,
    debug: bool = False,
) -> dict[str, Any]:
    working = dict(context or {})

    merged_assignments = _merge_assignment_rows(
        working.get("assigned_strategies") or [],
        [],
    )

    merged_candidates: list[dict[str, Any]] = []
    seen_candidates: dict[tuple[str, str, str, str, str], int] = {}
    blocked_reasons: list[str] = []
    errors: list[str] = []

    for candidate in list(working.get("signal_candidates") or []):
        _merge_candidate(
            merged_candidates=merged_candidates,
            seen_candidates=seen_candidates,
            candidate=candidate,
        )

    for result in list(results or []):
        if isinstance(result, Exception):
            errors.append(f"{type(result).__name__}: {result}")
            continue

        if not isinstance(result, dict):
            continue

        merged_assignments = _merge_assignment_rows(
            merged_assignments,
            result.get("assigned_strategies") or [],
        )

        for candidate in list(result.get("signal_candidates") or []):
            _merge_candidate(
                merged_candidates=merged_candidates,
                seen_candidates=seen_candidates,
                candidate=candidate,
            )

        if result.get("blocked_by_news_bias"):
            reason = str(result.get("news_bias_reason") or "").strip()
            if reason:
                blocked_reasons.append(reason)

        if result.get("signal_fanout_errors"):
            for error in list(result.get("signal_fanout_errors") or []):
                text = str(error or "").strip()
                if text:
                    errors.append(text)

    merged_candidates = sorted(
        merged_candidates,
        key=_candidate_rank,
        reverse=True,
    )

    min_conf = _clamp(min_candidate_confidence, 0.0, 1.0)

    merged_candidates = [
        candidate
        for candidate in merged_candidates
        if _safe_float((candidate.get("signal") or {}).get("confidence"), 0.0) >= min_conf
    ]

    working["assigned_strategies"] = merged_assignments
    working["signal_candidates"] = merged_candidates
    working.pop("signal", None)
    working.pop("display_signal", None)

    if merged_candidates:
        working.pop("blocked_by_news_bias", None)
        working.pop("news_bias_reason", None)
    elif blocked_reasons:
        working["blocked_by_news_bias"] = True
        working["news_bias_reason"] = " | ".join(
            _unique_reasons(blocked_reasons))
    else:
        working.pop("blocked_by_news_bias", None)
        working.pop("news_bias_reason", None)

    if errors:
        working["signal_fanout_errors"] = _unique_reasons(errors)
    else:
        working.pop("signal_fanout_errors", None)

    working["signal_fanout"] = {
        "candidate_count": len(merged_candidates),
        "assignment_count": len(merged_assignments),
        "blocked_by_news_bias": bool(working.get("blocked_by_news_bias")),
        "news_bias_reason": working.get("news_bias_reason"),
        "errors": list(working.get("signal_fanout_errors") or []),
        "candidates": _candidate_preview(merged_candidates),
    }

    if debug:
        print(f"\n🧠 MERGED SIGNALS ({working.get('symbol')}):")
        for candidate in merged_candidates:
            signal = candidate["signal"]
            print(
                "👉 "
                f"{signal.get('strategy_name')} | "
                f"{signal.get('side')} | "
                f"conf={signal.get('confidence')} | "
                f"quality={signal.get('quality')}"
            )

    return working


async def _run_agent_process(agent: Any, context: dict[str, Any]) -> Any:
    process = getattr(agent, "process", None)
    if not callable(process):
        return {
            "signal_fanout_errors": [
                f"{agent.__class__.__name__} has no process() method."
            ]
        }

    result = process(dict(context or {}))
    if inspect.isawaitable(result):
        return await result

    return result


async def run_signal_agents_parallel(
    signal_agents: list[Any],
    context: dict[str, Any],
    *,
    min_candidate_confidence: float = DEFAULT_MIN_CANDIDATE_CONFIDENCE,
    timeout_seconds: Optional[float] = None,
    debug: bool = False,
) -> dict[str, Any]:
    agents = list(signal_agents or [])

    if not agents:
        return dict(context or {})

    base_context = dict(context or {})

    if len(agents) == 1:
        try:
            result = await _run_agent_process(agents[0], base_context)
        except Exception as exc:
            result = {
                "signal_fanout_errors": [
                    f"{agents[0].__class__.__name__}: {type(exc).__name__}: {exc}"
                ]
            }

        return merge_signal_agent_results(
            base_context,
            [result],
            min_candidate_confidence=min_candidate_confidence,
            debug=debug,
        )

    tasks = [
        asyncio.create_task(
            _run_agent_process(agent, base_context),
            name=f"signal_agent:{getattr(agent, 'name', agent.__class__.__name__)}",
        )
        for agent in agents
    ]

    try:
        if timeout_seconds is None:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=max(0.1, float(timeout_seconds)),
            )
    except asyncio.TimeoutError:
        for task in tasks:
            if not task.done():
                task.cancel()

        results = [
            TimeoutError(
                f"Signal agent fanout timed out after {timeout_seconds}s")
        ]

    return merge_signal_agent_results(
        base_context,
        list(results or []),
        min_candidate_confidence=min_candidate_confidence,
        debug=debug,
    )
