from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from agents.validation_engine import ValidationResult
from models.signal import Signal, SignalStatus


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _position_side(quantity: float) -> str:
    return "buy" if _safe_float(quantity) >= 0.0 else "sell"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _latest_history_note(signal: Signal) -> str:
    history = list(getattr(signal, "confidence_history", []) or [])
    if not history:
        return ""
    return str(getattr(history[-1], "note", "") or "").strip()


def evaluate_trader_symbol(
    agent: Any,
    symbol: str,
    *,
    profile_id: str | None = None,
    prepared_signals: list[Signal] | None = None,
    prepared_features: dict[str, float] | None = None,
    validation_result: ValidationResult | None = None,
):
    profile_key = str(profile_id or agent.active_profile_id or "").strip() or agent.active_profile_id
    profile = agent.get_profile(profile_key)
    now = _utc_now()
    latest_price = agent._latest_price(symbol)
    collection = agent.signal_engine.collect(symbol, agent.strategy_signals, now=now)
    signals = list(prepared_signals if prepared_signals is not None else collection.signals)
    features = dict(prepared_features if prepared_features is not None else agent._resolve_feature_context(symbol, signals=signals))
    validation = validation_result
    if validation is None:
        validation = agent.validation_engine.validate(
            symbol=symbol,
            signals=signals,
            feature_context=features,
            minimum_confidence=agent._min_confidence(profile),
            model_probability=agent._model_probability(symbol, features),
            reasoning_lookup=lambda target_symbol, strategy_name: agent.latest_reasoning.get((target_symbol, strategy_name)),
            reasoning_contributor=lambda target_symbol, strategy_name, side, seed: agent._openai_reasoning_contribution(
                symbol=target_symbol,
                selected_strategy=strategy_name,
                winning_side=side,
                reasoning_seed=seed,
            ),
            reasoning_metadata=agent._reasoning_contribution_metadata,
        )
        signals = list(validation.validated_signals)

    reference_time = agent._market_reference_time(symbol, fallback=now)
    applied_constraints: list[str] = []
    market_hours = agent._market_hours_decision(symbol, now=reference_time)
    existing_position = agent.active_positions.get(symbol)
    profile_stats = dict(agent.performance_by_profile.get(profile_key, {}))
    performance_context = {
        "trades": float(profile_stats.get("trades", 0.0) or 0.0),
        "wins": float(profile_stats.get("wins", 0.0) or 0.0),
        "losses": float(profile_stats.get("losses", 0.0) or 0.0),
        "realized_pnl": float(profile_stats.get("realized_pnl", 0.0) or 0.0),
        "loss_streak": int(agent.loss_streak_by_profile.get(profile_key, 0) or 0),
        "symbol_loss_streak": int(agent.loss_streak_by_symbol.get((profile_key, symbol), 0) or 0),
    }
    profile_metadata = {
        "profile": profile,
        "goal": profile.goal,
        "risk_level": profile.risk_level,
        "trade_frequency": profile.trade_frequency,
        "time_horizon": profile.time_horizon,
        "market_hours": market_hours.to_metadata(),
        "performance_context": performance_context,
        "validation_notes": list(validation.notes if validation is not None else []),
    }

    if not market_hours.trade_allowed:
        applied_constraints.append("market_hours")
        return agent._build_decision(
            profile_key,
            symbol,
            action="SKIP",
            side="",
            quantity=0.0,
            price=latest_price,
            confidence=0.0,
            selected_strategy="none",
            reasoning=f"SKIP because {market_hours.reason}",
            applied_constraints=applied_constraints,
            votes={},
            features=features,
            model_probability=validation.model_probability if validation is not None else None,
            metadata=profile_metadata,
        ), None

    if profile.preferred_assets and symbol not in profile.preferred_assets:
        return agent._build_decision(
            profile_key,
            symbol,
            action="SKIP",
            side="",
            quantity=0.0,
            price=latest_price,
            confidence=0.0,
            selected_strategy="none",
            reasoning=f"SKIP because {symbol} is outside the investor's preferred assets.",
            applied_constraints=["preferred_assets"],
            votes={},
            features=features,
            model_probability=validation.model_probability if validation is not None else None,
            metadata=profile_metadata,
        ), None

    if not signals:
        management_plan = agent._build_position_management_plan(
            symbol=symbol,
            profile=profile,
            position=existing_position,
            latest_price=latest_price,
            features=features,
            winning_side=None,
            base_confidence=0.0,
            votes={},
            model_probability=validation.model_probability if validation is not None else None,
        )
        if management_plan is not None:
            plan_action = str(management_plan.get("action") or "").strip().lower()
            return agent._build_decision(
                profile_key,
                symbol,
                action=plan_action.upper(),
                side=str(management_plan.get("target_side") or management_plan.get("existing_side") or ""),
                quantity=float(management_plan.get("quantity") or 0.0),
                price=_safe_float(management_plan.get("price") or latest_price, latest_price),
                confidence=0.0,
                selected_strategy="position_management",
                reasoning=str(management_plan.get("reason") or f"Manage the open {symbol} position."),
                applied_constraints=[*applied_constraints, f"position_management:{plan_action}"],
                votes={},
                features=features,
                model_probability=validation.model_probability if validation is not None else None,
                metadata={**profile_metadata, "position_management": management_plan},
            ), None
        if validation is not None and validation.filtered_signals:
            representative = max(validation.filtered_signals, key=lambda item: float(getattr(item, "confidence", 0.0) or 0.0))
            reasoning_contribution = dict(representative.metadata.get("reasoning_contribution") or {})
            constraint = str(
                reasoning_contribution.get("constraint")
                or representative.metadata.get("validation_reason")
                or ""
            ).strip()
            filtered_reason = str(
                reasoning_contribution.get("skip_reason")
                or _latest_history_note(representative)
                or representative.reason
                or f"{representative.strategy_name} was filtered during validation."
            ).strip()
            if filtered_reason and not filtered_reason.lower().startswith("skip because "):
                filtered_reason = f"SKIP because {filtered_reason.rstrip('.')}."
            filtered_metadata = {
                **profile_metadata,
                "validation_state": "filtered",
                "filtered_signal_id": representative.id,
                "filtered_count": len(validation.filtered_signals),
                "validation_reason": representative.metadata.get("validation_reason"),
            }
            if reasoning_contribution:
                filtered_metadata["reasoning_contribution"] = reasoning_contribution
            filtered_constraints = [*applied_constraints]
            if constraint:
                filtered_constraints.append(constraint)
            return agent._build_decision(
                profile_key,
                symbol,
                action="SKIP",
                side=str(representative.side or ""),
                quantity=0.0,
                price=_safe_float(representative.price or latest_price, latest_price),
                confidence=0.0,
                selected_strategy=str(representative.strategy_name or "validation_engine"),
                reasoning=filtered_reason or f"SKIP because all fresh {symbol} signals were filtered during validation.",
                applied_constraints=filtered_constraints,
                votes={},
                features=features,
                model_probability=validation.model_probability if validation is not None else None,
                metadata=filtered_metadata,
            ), None
        return agent._build_decision(
            profile_key,
            symbol,
            action="HOLD",
            side="",
            quantity=0.0,
            price=latest_price,
            confidence=0.0,
            selected_strategy="none",
            reasoning=(
                f"HOLD because no signals survived validation for {symbol}."
                if validation is not None and validation.filtered_signals
                else f"HOLD because there are no recent strategy signals for {symbol}."
            ),
            applied_constraints=applied_constraints,
            votes={},
            features=features,
            model_probability=validation.model_probability if validation is not None else None,
            metadata=profile_metadata,
        ), None

    weighted_decision = agent.decision_engine.decide(
        signals,
        weight_resolver=lambda strategy_name: agent._strategy_weight(profile, strategy_name),
    )
    votes = dict(weighted_decision.votes)
    buy_score = votes.get("buy", 0.0)
    sell_score = votes.get("sell", 0.0)
    if weighted_decision.winning_side is None or weighted_decision.selected_signal is None:
        return agent._build_decision(
            profile_key,
            symbol,
            action="HOLD",
            side="",
            quantity=0.0,
            price=latest_price,
            confidence=0.0,
            selected_strategy="none",
            reasoning=f"HOLD because weighted voting is inconclusive for {symbol} (buy={buy_score:.2f}, sell={sell_score:.2f}).",
            applied_constraints=applied_constraints,
            votes=votes,
            features=features,
            model_probability=validation.model_probability if validation is not None else None,
            metadata=profile_metadata,
        ), None

    winning_side = str(weighted_decision.winning_side)
    best_signal = weighted_decision.selected_signal
    base_confidence = float(weighted_decision.confidence)
    selected_strategy = str(weighted_decision.selected_strategy)
    reasoning_seed = agent.latest_reasoning.get((symbol, selected_strategy))
    model_probability = validation.model_probability if validation is not None else agent._model_probability(symbol, features)
    reasoning_metadata = dict(best_signal.metadata.get("reasoning_contribution") or {})
    reasoning_influence = {"summary": str(reasoning_metadata.get("summary") or "").strip()}
    reasoning_constraint = str(reasoning_metadata.get("constraint") or "").strip()
    if reasoning_constraint:
        applied_constraints.append(reasoning_constraint)

    quantity = max(0.0, _safe_float(best_signal.quantity, 0.0) * agent._size_multiplier(profile))
    trade_price = latest_price or _safe_float(best_signal.price)
    decision_metadata = {
        **profile_metadata,
        "decision_vote_margin": float(weighted_decision.vote_margin),
        **({"reasoning_contribution": reasoning_metadata} if reasoning_metadata else {}),
    }

    management_plan = agent._build_position_management_plan(
        symbol=symbol,
        profile=profile,
        position=existing_position,
        latest_price=trade_price,
        features=features,
        winning_side=winning_side,
        base_confidence=base_confidence,
        votes=votes,
        model_probability=model_probability,
    )
    if existing_position is None and agent._trade_cooldown_active(profile_key, symbol, reference_time):
        applied_constraints.append("trade_frequency")
        return agent._build_decision(
            profile_key,
            symbol,
            action="SKIP",
            side="",
            quantity=0.0,
            price=trade_price,
            confidence=0.0,
            selected_strategy="none",
            reasoning=f"SKIP because the {profile.trade_frequency} frequency setting is enforcing a cooldown on {symbol}.",
            applied_constraints=applied_constraints,
            votes=votes,
            features=features,
            model_probability=model_probability,
            metadata=profile_metadata,
        ), None

    if existing_position is not None and management_plan is None:
        existing_side = _position_side(existing_position.quantity)
        if existing_side == winning_side:
            quantity = max(0.0, quantity - abs(_safe_float(existing_position.quantity)))
            applied_constraints.append("existing_position_reduce")
        elif len(signals) == 1:
            management_plan = {
                "action": "reverse",
                "quantity": abs(_safe_float(existing_position.quantity)),
                "existing_side": existing_side,
                "target_side": winning_side,
                "price": trade_price,
                "reason": (
                    f"{winning_side.upper()} because {selected_strategy} explicitly flipped against the open "
                    f"{'long' if existing_side == 'buy' else 'short'} position in {symbol}."
                ),
                "metadata": {"explicit_signal_flip": True},
            }
        else:
            return agent._build_decision(
                profile_key,
                symbol,
                action="HOLD",
                side=winning_side,
                quantity=0.0,
                price=trade_price,
                confidence=base_confidence,
                selected_strategy=selected_strategy,
                reasoning=f"HOLD because an open {'long' if existing_side == 'buy' else 'short'} position in {symbol} has not met the reversal threshold yet.",
                applied_constraints=[*applied_constraints, "existing_position_opposite_side"],
                votes=votes,
                features=features,
                model_probability=model_probability,
                metadata=decision_metadata,
            ), None

    quantity = max(0.0, quantity - agent._active_order_quantity(symbol, side=winning_side))
    if agent._active_order_quantity(symbol, side=winning_side) > 1e-12:
        applied_constraints.append("active_order_reduce")

    if management_plan is not None and str(management_plan.get("action") or "").strip().lower() in {"reduce", "close"}:
        plan_action = str(management_plan.get("action") or "").strip().lower()
        return agent._build_decision(
            profile_key,
            symbol,
            action=plan_action.upper(),
            side=str(management_plan.get("target_side") or management_plan.get("existing_side") or winning_side),
            quantity=float(management_plan.get("quantity") or 0.0),
            price=_safe_float(management_plan.get("price") or trade_price, trade_price),
            confidence=base_confidence,
            selected_strategy=selected_strategy,
            reasoning=str(management_plan.get("reason") or f"Manage the open {symbol} position."),
            applied_constraints=[*applied_constraints, f"position_management:{plan_action}"],
            votes=votes,
            features=features,
            model_probability=model_probability,
            metadata={**decision_metadata, "position_management": management_plan},
        ), None

    entry_guardrail = agent._entry_guardrail(
        symbol=symbol,
        profile=profile,
        winning_side=winning_side,
        base_confidence=base_confidence,
        votes=votes,
        features=features,
        model_probability=model_probability,
        market_hours=market_hours,
    )
    if entry_guardrail["skip_reason"]:
        skip_constraints = [*applied_constraints, *entry_guardrail["constraints"]]
        if str((management_plan or {}).get("action") or "").strip().lower() == "reverse":
            return agent._reverse_close_only_decision(
                profile_id=profile_key,
                symbol=symbol,
                trade_price=trade_price,
                confidence=base_confidence,
                selected_strategy=selected_strategy,
                skip_reason=str(entry_guardrail["skip_reason"]),
                applied_constraints=skip_constraints,
                votes=votes,
                features=features,
                model_probability=model_probability,
                metadata=decision_metadata,
                management_plan=management_plan,
            )
        return agent._build_decision(
            profile_key,
            symbol,
            action="SKIP",
            side=winning_side,
            quantity=0.0,
            price=trade_price,
            confidence=min(base_confidence, model_probability) if model_probability is not None else base_confidence,
            selected_strategy=selected_strategy,
            reasoning=str(entry_guardrail["skip_reason"]),
            applied_constraints=skip_constraints,
            votes=votes,
            features=features,
            model_probability=model_probability,
            metadata=decision_metadata,
        ), None
    quantity *= float(entry_guardrail["quantity_multiplier"])
    applied_constraints.extend(entry_guardrail["constraints"])

    quantity = max(0.0, quantity)
    if quantity <= 1e-12:
        return agent._build_decision(
            profile_key,
            symbol,
            action="SKIP",
            side=winning_side,
            quantity=0.0,
            price=trade_price,
            confidence=base_confidence,
            selected_strategy=selected_strategy,
            reasoning=f"SKIP because the final position size for {symbol} was reduced to zero by trader discipline rules.",
            applied_constraints=[*applied_constraints, "quantity_zero"],
            votes=votes,
            features=features,
            model_probability=model_probability,
            metadata=decision_metadata,
        ), None

    stop_price, take_profit = agent._protective_prices(trade_price, winning_side, profile, features)
    reasoning = agent._compose_reasoning(
        symbol=symbol,
        profile=profile,
        selected_strategy=selected_strategy,
        winning_side=winning_side,
        features=features,
        votes=votes,
        applied_constraints=applied_constraints,
        model_probability=model_probability,
        reasoning_seed=reasoning_seed,
        reasoning_contribution=reasoning_influence,
        market_hours=market_hours,
    )
    if management_plan is not None:
        plan_action = str(management_plan.get("action") or "").strip().lower()
        applied_constraints.append(f"position_management:{plan_action}")
        reasoning = f"{management_plan.get('reason')} {reasoning}".strip()

    decision = agent._build_decision(
        profile_key,
        symbol,
        action="BUY" if winning_side == "buy" else "SELL",
        side=winning_side,
        quantity=quantity,
        price=trade_price,
        confidence=base_confidence,
        selected_strategy=selected_strategy,
        reasoning=reasoning,
        applied_constraints=applied_constraints,
        votes=votes,
        features=features,
        model_probability=model_probability,
        metadata={
            **decision_metadata,
            **({"position_management": management_plan} if management_plan is not None else {}),
        },
    )
    order_signal = best_signal.transition(
        stage="decision_selected",
        status=SignalStatus.CREATED,
        confidence=base_confidence,
        note=f"Weighted voting selected {selected_strategy}",
        metadata={
            "profile_id": profile_key,
            "profile_goal": profile.goal,
            "risk_level": profile.risk_level,
            "trade_frequency": profile.trade_frequency,
            "profile_max_drawdown": profile.max_drawdown,
            "profile_preferred_assets": list(profile.preferred_assets),
            "selected_strategy": selected_strategy,
            "applied_constraints": list(applied_constraints),
            "votes": dict(votes),
            "vote_margin": float(weighted_decision.vote_margin),
            "model_probability": model_probability,
            "performance_context": performance_context,
            "profit_protection_enabled": True,
            "asset_type": market_hours.asset_type,
            "market_session": market_hours.session,
            "high_liquidity_session": market_hours.high_liquidity,
            "market_hours": market_hours.to_metadata(),
            **({"reasoning_contribution": reasoning_metadata} if reasoning_metadata else {}),
            **({"position_management": management_plan} if management_plan is not None else {}),
        },
        timestamp=reference_time,
    ).clone(
        symbol=symbol,
        side=winning_side,
        quantity=quantity,
        price=trade_price,
        strategy_name=selected_strategy,
        reason=reasoning,
        stop_price=stop_price,
        take_profit=take_profit,
    )
    return decision, order_signal
