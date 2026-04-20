def dynamic_based_on_latency(latency_tracker, base_interval=1.0):

    stats = latency_tracker.stats()

    avg = stats["avg"]
    p95 = stats["p95"]
    error_rate = stats["error_rate"]

    # =========================
    # BASE ADJUSTMENT
    # =========================
    interval = base_interval

    # Slow API → increase interval
    if avg > 0.5:
        interval *= 1.5

    if p95 > 1.0:
        interval *= 2.0

    # High errors → throttle hard
    if error_rate > 0.1:
        interval *= 2.5

    # Fast API → speed up
    if avg < 0.2 and error_rate < 0.02:
        interval *= 0.8

    # clamp
    return max(0.5, min(5.0, interval))