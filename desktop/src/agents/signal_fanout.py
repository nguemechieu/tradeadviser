import asyncio

def _normalize_candidate(candidate):
    signal = dict((candidate or {}).get("signal") or {})

    side = str(signal.get("side") or "").lower()
    confidence = float(signal.get("confidence", 0.0) or 0.0)

    if side not in ("buy", "sell"):
        return None

    signal["confidence"] = max(0.0, min(confidence, 1.0))

    # 🔥 NEW: quality score
    signal["quality"] = (
            signal["confidence"]
            * float(signal.get("strategy_assignment_weight", 1.0))
    )

    candidate["signal"] = signal
    return candidate
def _merge_assignment_rows(existing_rows, new_rows):
    merged_rows = [dict(row) for row in list(existing_rows or []) if isinstance(row, dict)]
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


def _candidate_fingerprint(candidate):
    signal = dict((candidate or {}).get("signal") or {})
    return (
        str((candidate or {}).get("agent_name") or "").strip(),
        str(signal.get("strategy_name") or (candidate or {}).get("strategy_name") or "").strip(),
        str(signal.get("timeframe") or (candidate or {}).get("timeframe") or "").strip(),
        str(signal.get("side") or (candidate or {}).get("side") or "").strip().lower(),
    )


def _candidate_rank(candidate):
    signal = dict((candidate or {}).get("signal") or {})
    adaptive_score = float(signal.get("adaptive_score", 0.0) or 0.0)
    weighted_confidence = float(signal.get("confidence", 0.0) or 0.0) * max(
        0.0001, float(signal.get("strategy_assignment_weight", 0.0) or 0.0)
    )
    return (
        adaptive_score,
        weighted_confidence,
        float(signal.get("confidence", 0.0) or 0.0),
    )


def merge_signal_agent_results(context, results):
    working = dict(context or {})
    merged_assignments = _merge_assignment_rows(working.get("assigned_strategies") or [], [])
    merged_candidates = []
    seen_candidates = {}
    blocked_reasons = []

    for candidate in list(working.get("signal_candidates") or []):
        if not isinstance(candidate, dict):
            continue

        candidate_copy = _normalize_candidate(dict(candidate))
        if candidate_copy is None:
         continue
        fingerprint = _candidate_fingerprint(candidate_copy)
        existing_index = seen_candidates.get(fingerprint)
        if existing_index is None:
            seen_candidates[fingerprint] = len(merged_candidates)
            merged_candidates.append(candidate_copy)
            continue
        if _candidate_rank(candidate_copy) > _candidate_rank(merged_candidates[existing_index]):
            merged_candidates[existing_index] = candidate_copy

    for result in list(results or []):
        if not isinstance(result, dict):
            continue
        merged_assignments = _merge_assignment_rows(merged_assignments, result.get("assigned_strategies") or [])
        for candidate in list(result.get("signal_candidates") or []):
            if not isinstance(candidate, dict):
                continue
            candidate_copy = dict(candidate)
            fingerprint = _candidate_fingerprint(candidate_copy)
            existing_index = seen_candidates.get(fingerprint)
            if existing_index is None:
                seen_candidates[fingerprint] = len(merged_candidates)
                merged_candidates.append(candidate_copy)
                continue
            if _candidate_rank(candidate_copy) > _candidate_rank(merged_candidates[existing_index]):
                merged_candidates[existing_index] = candidate_copy
        if result.get("blocked_by_news_bias"):
            reason = str(result.get("news_bias_reason") or "").strip()
            if reason:
                blocked_reasons.append(reason)

    working["assigned_strategies"] = merged_assignments
    working["signal_candidates"] = merged_candidates
    working.pop("signal", None)
    working.pop("display_signal", None)
    if merged_candidates:
        working.pop("blocked_by_news_bias", None)
        working.pop("news_bias_reason", None)
    elif blocked_reasons:
        working["blocked_by_news_bias"] = True
        unique_reasons = []
        for reason in blocked_reasons:
            if reason not in unique_reasons:
                unique_reasons.append(reason)
        working["news_bias_reason"] = " | ".join(unique_reasons)
    else:
        working.pop("blocked_by_news_bias", None)
        working.pop("news_bias_reason", None)
    # 🔥 FINAL SORT (VERY IMPORTANT)
    merged_candidates = sorted(
    merged_candidates,
    key=_candidate_rank,
    reverse=True
)

# 🔥 FILTER WEAK SIGNALS
    merged_candidates = [
    c for c in merged_candidates
    if float(c["signal"].get("confidence", 0)) >= 0.3
]

    print(f"\n🧠 MERGED SIGNALS ({working.get('symbol')}):")

    for c in merged_candidates:
     s = c["signal"]
     print(f"👉 {s.get('strategy_name')} | {s.get('side')} | conf={s.get('confidence')}")
    return working


async def run_signal_agents_parallel(signal_agents, context):
    agents = list(signal_agents or [])
    if not agents:
        return dict(context or {})
    if len(agents) == 1:
        return await agents[0].process(dict(context or {}))

    base_context = dict(context or {})
    results = await asyncio.gather(
        *(agent.process(dict(base_context)) for agent in agents),
    )
    return merge_signal_agent_results(base_context, results)
