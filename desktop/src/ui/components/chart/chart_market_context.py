import html

import numpy as np


def install_chart_market_context(ChartWidget):
    if getattr(ChartWidget, "_market_context_installed", False):
        return

    orig_build_candle_stats = ChartWidget._build_candle_stats
    orig_update_chart_header = ChartWidget._update_chart_header
    orig_update_market_info = ChartWidget._update_market_info

    def build_market_background_states(self, visible, visible_x):
        if visible is None or len(visible) < 3:
            return []

        sample = visible.tail(min(len(visible), 8)).copy()
        open_values = sample["open"].astype(float).to_numpy()
        high_values = sample["high"].astype(float).to_numpy()
        low_values = sample["low"].astype(float).to_numpy()
        close_values = sample["close"].astype(float).to_numpy()
        volume_values = sample["volume"].astype(float).to_numpy()
        sample_x = np.asarray(visible_x[-len(sample):], dtype=float)

        ranges = np.maximum(high_values - low_values, 1e-9)
        bodies = np.abs(close_values - open_values)
        upper_wicks = np.maximum(0.0, high_values - np.maximum(open_values, close_values))
        lower_wicks = np.maximum(0.0, np.minimum(open_values, close_values) - low_values)
        avg_range = float(np.nanmean(ranges)) if len(ranges) else 0.0

        states = []
        seen = set()

        def add_state(key, title, message, priority, summary_label=None):
            if key in seen:
                return
            seen.add(key)
            states.append(
                {
                    "key": key,
                    "title": title,
                    "message": message,
                    "priority": int(priority),
                    "summary_label": str(summary_label or title),
                }
            )

        diffs = np.diff(sample_x)
        diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
        if len(diffs) >= 4:
            baseline_slice = diffs[:-2] if len(diffs) > 2 else diffs
            baseline = float(np.nanmedian(baseline_slice)) if len(baseline_slice) else 0.0
            recent_speed = float(np.nanmean(diffs[-2:])) if len(diffs) >= 2 else baseline
            variable_speed = bool(np.nanstd(diffs) > max(1.0, float(np.nanmean(diffs)) * 0.12))
            if baseline > 0 and variable_speed:
                if recent_speed <= baseline * 0.70:
                    add_state(
                        "fast_bar_printing",
                        "Fast bar printing",
                        "High participation, momentum, news, breakout pressure.",
                        90,
                        summary_label="Fast bar printing",
                    )
                elif recent_speed >= baseline * 1.35:
                    add_state(
                        "slow_bar_printing",
                        "Slow bar printing",
                        "Low participation, chop, hesitation.",
                        90,
                        summary_label="Slow bar printing",
                    )
        elif len(volume_values) >= 6:
            earlier_volume = float(np.nanmean(volume_values[:-3])) if len(volume_values[:-3]) else 0.0
            recent_volume = float(np.nanmean(volume_values[-3:])) if len(volume_values[-3:]) else 0.0
            earlier_range = float(np.nanmean(ranges[:-3])) if len(ranges[:-3]) else 0.0
            recent_range = float(np.nanmean(ranges[-3:])) if len(ranges[-3:]) else 0.0
            if earlier_volume > 0 and earlier_range > 0:
                if recent_volume >= earlier_volume * 1.60 and recent_range >= earlier_range * 1.15:
                    add_state(
                        "fast_bar_printing",
                        "Fast bar printing",
                        "High participation, momentum, news, breakout pressure.",
                        85,
                        summary_label="Fast bar printing",
                    )
                elif recent_volume <= earlier_volume * 0.70 and recent_range <= earlier_range * 0.90:
                    add_state(
                        "slow_bar_printing",
                        "Slow bar printing",
                        "Low participation, chop, hesitation.",
                        85,
                        summary_label="Slow bar printing",
                    )

        bullish_strength = (close_values > open_values) & (bodies >= ranges * 0.55) & (upper_wicks <= ranges * 0.20)
        if (len(bullish_strength) >= 3 and np.count_nonzero(bullish_strength[-3:]) >= 2) or bool(bullish_strength[-1]):
            add_state(
                "aggressive_buying",
                "Long bullish candles",
                "Aggressive buying.",
                80,
                summary_label="Aggressive buying",
            )

        bearish_strength = (close_values < open_values) & (bodies >= ranges * 0.55) & (lower_wicks <= ranges * 0.20)
        if (len(bearish_strength) >= 3 and np.count_nonzero(bearish_strength[-3:]) >= 2) or bool(bearish_strength[-1]):
            add_state(
                "aggressive_selling",
                "Long bearish candles",
                "Aggressive selling.",
                80,
                summary_label="Aggressive selling",
            )

        rejection_candles = (bodies <= ranges * 0.32) & ((upper_wicks + lower_wicks) >= ranges * 0.60)
        if (len(rejection_candles) >= 4 and np.count_nonzero(rejection_candles[-4:]) >= 2) or bool(rejection_candles[-1]):
            add_state(
                "rejection_indecision",
                "Small candles with long wicks",
                "Rejection, indecision, liquidity probing.",
                78,
                summary_label="Rejection / indecision",
            )

        if len(high_values) >= 4:
            recent_highs = high_values[-4:]
            recent_lows = low_values[-4:]
            if np.all(np.diff(recent_highs) > 0) and np.all(np.diff(recent_lows) > 0):
                add_state(
                    "trend_strength",
                    "Repeated higher highs / higher lows",
                    "Trend strength.",
                    72,
                    summary_label="Trend strength",
                )

        if len(high_values) >= 5:
            recent_highs = high_values[-6:]
            recent_lows = low_values[-6:]
            recent_closes = close_values[-6:]
            tolerance = max(avg_range * 0.25, abs(float(recent_closes[-1])) * 0.0015, 1e-6)
            ceiling = float(np.max(recent_highs))
            floor = float(np.min(recent_lows))

            ceiling_hits = np.abs(recent_highs - ceiling) <= tolerance
            ceiling_rejections = ceiling_hits & (recent_closes < (ceiling - tolerance * 0.35))
            floor_hits = np.abs(recent_lows - floor) <= tolerance
            floor_bounces = floor_hits & (recent_closes > (floor + tolerance * 0.35))

            if np.count_nonzero(ceiling_hits) >= 2 and np.count_nonzero(ceiling_rejections) >= 2:
                add_state(
                    "resistance_pressure",
                    "Repeated failures at one level",
                    "Resistance is forming at the same zone.",
                    70,
                    summary_label="Resistance pressure",
                )
            elif np.count_nonzero(floor_hits) >= 2 and np.count_nonzero(floor_bounces) >= 2:
                add_state(
                    "support_reaction",
                    "Repeated failures at one level",
                    "Support is forming at the same zone.",
                    70,
                    summary_label="Support reaction",
                )

        states.sort(key=lambda item: int(item.get("priority", 0)), reverse=True)
        return states

    def market_background_summary(self, states=None, limit=3):
        state_rows = list(states or [])
        if not state_rows:
            return "Background: waiting for clearer structure."
        labels = [
            str(item.get("summary_label") or item.get("title") or "").strip()
            for item in state_rows[: max(1, int(limit or 3))]
            if str(item.get("summary_label") or item.get("title") or "").strip()
        ]
        if not labels:
            return "Background: waiting for clearer structure."
        return "Background: " + " | ".join(labels)

    def market_background_detail_html(self, states=None):
        state_rows = list(states or [])
        if not state_rows:
            return "<p><b>Background context:</b> Waiting for clearer structure.</p>"
        items = "".join(
            f"<li><b>{html.escape(str(item.get('title') or 'State'))}:</b> {html.escape(str(item.get('message') or ''))}</li>"
            for item in state_rows
        )
        return "<h4>Background context</h4><ul>" + items + "</ul>"

    def update_background_context_label(self):
        label = getattr(self, "background_context_label", None)
        if label is None:
            return
        stats = getattr(self, "_last_candle_stats", {}) or {}
        states = list(stats.get("background_states", []) or [])
        label.setText(self._market_background_summary(states))
        primary_key = str(states[0].get("key") or "") if states else ""
        color = "#e7c56f"
        if primary_key in {"aggressive_buying", "trend_strength", "support_reaction"}:
            color = "#63d59a"
        elif primary_key in {"aggressive_selling", "resistance_pressure"}:
            color = "#f08484"
        elif primary_key in {"slow_bar_printing", "rejection_indecision"}:
            color = "#e7c56f"
        label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 700;")

    def wrapped_build_candle_stats(self, df, x):
        stats = orig_build_candle_stats(self, df, x)
        if not stats:
            return stats
        start_index = int(stats.get("start_index", 0) or 0)
        visible = df.iloc[start_index:].copy() if df is not None else None
        visible_x = np.asarray(x[start_index:], dtype=float) if x is not None else np.array([], dtype=float)
        states = self._build_market_background_states(visible, visible_x)
        enriched = dict(stats)
        enriched["background_states"] = states
        enriched["background_summary"] = self._market_background_summary(states)
        return enriched

    def wrapped_update_chart_header(self):
        result = orig_update_chart_header(self)
        self._update_background_context_label()
        return result

    def wrapped_update_market_info(self):
        result = orig_update_market_info(self)
        stats = getattr(self, "_last_candle_stats", {}) or {}
        states = list(stats.get("background_states", []) or [])
        summary = getattr(self, "market_info_summary", None)
        if summary is not None and states:
            compact = ", ".join(
                str(item.get("summary_label") or item.get("title") or "").strip()
                for item in states[:2]
                if str(item.get("summary_label") or item.get("title") or "").strip()
            )
            if compact:
                summary.setText(f"{summary.text()} | {compact}")
        details = getattr(self, "market_info_details", None)
        if details is not None:
            current_html = details.toHtml()
            extra = self._market_background_detail_html(states)
            if "</body>" in current_html:
                current_html = current_html.replace("</body>", extra + "</body>")
            else:
                current_html += extra
            details.setHtml(current_html)
        return result

    ChartWidget._build_market_background_states = build_market_background_states
    ChartWidget._market_background_summary = market_background_summary
    ChartWidget._market_background_detail_html = market_background_detail_html
    ChartWidget._update_background_context_label = update_background_context_label
    ChartWidget._build_candle_stats = wrapped_build_candle_stats
    ChartWidget._update_chart_header = wrapped_update_chart_header
    ChartWidget._update_market_info = wrapped_update_market_info
    ChartWidget._market_context_installed = True
