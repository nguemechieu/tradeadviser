from quant.risk_models import safe_float


def normalize_weights(weights):
    cleaned = {
        str(name): max(0.0, safe_float(value, 0.0))
        for name, value in (weights or {}).items()
        if str(name).strip()
    }
    total = sum(cleaned.values())
    if total <= 0:
        return {}
    return {name: value / total for name, value in cleaned.items()}


def equal_weight_allocation(strategies):
    names = [str(name) for name in (strategies or []) if str(name).strip()]
    if not names:
        return {}
    weight = 1.0 / len(names)
    return {name: weight for name in names}


def inverse_volatility_allocation(strategy_volatility_map):
    inverse = {}
    for name, volatility in (strategy_volatility_map or {}).items():
        vol = max(1e-8, safe_float(volatility, 0.0))
        if vol <= 0:
            continue
        inverse[str(name)] = 1.0 / vol
    return normalize_weights(inverse)


def capped_weights(weights, max_weight=1.0):
    normalized = normalize_weights(weights)
    if not normalized:
        return {}

    cap = max(0.01, min(1.0, safe_float(max_weight, 1.0)))
    adjusted = dict(normalized)
    while True:
        capped_any = False
        overflow = 0.0
        uncapped = []
        for name, value in adjusted.items():
            if value > cap:
                overflow += value - cap
                adjusted[name] = cap
                capped_any = True
            else:
                uncapped.append(name)
        if not capped_any or overflow <= 0 or not uncapped:
            break
        share = overflow / len(uncapped)
        for name in uncapped:
            adjusted[name] += share
    return normalize_weights(adjusted)
