class RegimeEngine:
    VERSION = "regime-v1"

    def classify_row(self, row):
        if row is None:
            return "unknown"

        trend_strength = float(row.get("trend_strength", 0.0) or 0.0)
        atr_pct = float(row.get("atr_pct", 0.0) or 0.0)
        momentum = float(row.get("momentum", 0.0) or 0.0)
        band_position = float(row.get("band_position", 0.5) or 0.5)

        if trend_strength >= 0.01 and momentum > 0:
            return "trending_up"
        if trend_strength >= 0.01 and momentum < 0:
            return "trending_down"
        if atr_pct >= 0.03 and 0.25 <= band_position <= 0.75:
            return "volatile_range"
        if band_position <= 0.10:
            return "range_low_edge"
        if band_position >= 0.90:
            return "range_high_edge"
        return "range"

    def classify_frame(self, frame):
        if frame is None or getattr(frame, "empty", True):
            return "unknown"
        try:
            row = frame.iloc[-1]
        except Exception:
            return "unknown"
        return self.classify_row(row)
