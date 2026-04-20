from collections import deque
from datetime import datetime
import time


class TraderBehaviorGuard:
    def __init__(
        self,
        max_orders_per_hour=24,
        max_orders_per_day=120,
        max_consecutive_losses=4,
        cooldown_after_loss_seconds=900,
        same_symbol_reentry_cooldown_seconds=300,
        max_size_jump_ratio=3.0,
        daily_drawdown_limit_pct=0.06,
    ):
        self.max_orders_per_hour = max(1, int(max_orders_per_hour))
        self.max_orders_per_day = max(self.max_orders_per_hour, int(max_orders_per_day))
        self.max_consecutive_losses = max(1, int(max_consecutive_losses))
        self.cooldown_after_loss_seconds = max(60, int(cooldown_after_loss_seconds))
        self.same_symbol_reentry_cooldown_seconds = max(60, int(same_symbol_reentry_cooldown_seconds))
        self.max_size_jump_ratio = max(1.25, float(max_size_jump_ratio))
        self.daily_drawdown_limit_pct = max(0.0, float(daily_drawdown_limit_pct))

        self._order_attempts = deque()
        self._last_size_by_symbol = {}
        self._symbol_reentry_until = {}
        self._guard_cooldown_until = 0.0
        self._guard_cooldown_reason = ""
        self._last_block_reason = "Ready"
        self._last_blocked_at = None
        self._loss_streak = 0
        self._manual_lock_enabled = False
        self._manual_lock_reason = ""

        self._equity_day = datetime.now().date()
        self._day_start_equity = None
        self._peak_equity = None
        self._latest_equity = None

    def _safe_float(self, value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _normalize_symbol(self, value):
        return str(value or "").upper().strip()

    def _normalize_status(self, value):
        return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")

    def _reset_day_if_needed(self):
        today = datetime.now().date()
        if self._equity_day == today:
            return
        self._equity_day = today
        self._day_start_equity = self._latest_equity
        self._peak_equity = self._latest_equity
        self._loss_streak = 0

    def _prune(self, now):
        while self._order_attempts and now - self._order_attempts[0]["monotonic"] > 86400:
            self._order_attempts.popleft()

        expired_symbols = [
            symbol for symbol, expires_at in self._symbol_reentry_until.items()
            if expires_at <= now
        ]
        for symbol in expired_symbols:
            self._symbol_reentry_until.pop(symbol, None)

        if self._guard_cooldown_until <= now:
            self._guard_cooldown_until = 0.0
            self._guard_cooldown_reason = ""

    def _activate_guard_cooldown(self, now, seconds, reason):
        self._guard_cooldown_until = max(self._guard_cooldown_until, now + max(60, int(seconds)))
        self._guard_cooldown_reason = str(reason or "Trading cooldown active").strip()
        self._last_block_reason = self._guard_cooldown_reason
        self._last_blocked_at = datetime.now().isoformat(timespec="seconds")

    def _hourly_attempts(self, now):
        return sum(1 for item in self._order_attempts if now - item["monotonic"] <= 3600)

    def _daily_attempts(self, now):
        return sum(1 for item in self._order_attempts if now - item["monotonic"] <= 86400)

    def _blocked_attempts(self, now):
        return sum(
            1 for item in self._order_attempts
            if (now - item["monotonic"] <= 3600) and (not item.get("allowed", True))
        )

    def _daily_drawdown_pct(self):
        if self._latest_equity is None:
            return 0.0
        reference = max(
            self._safe_float(self._day_start_equity, 0.0),
            self._safe_float(self._peak_equity, 0.0),
        )
        if reference <= 0:
            return 0.0
        return max(0.0, (reference - self._latest_equity) / reference)

    def _format_seconds(self, seconds):
        seconds = max(0, int(seconds))
        minutes, remainder = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours}h {minutes:02d}m"
        if minutes > 0:
            return f"{minutes}m {remainder:02d}s"
        return f"{seconds}s"

    def record_equity(self, equity):
        value = self._safe_float(equity, 0.0)
        if value <= 0:
            return

        self._reset_day_if_needed()
        self._latest_equity = value
        if self._day_start_equity is None:
            self._day_start_equity = value
        if self._peak_equity is None or value > self._peak_equity:
            self._peak_equity = value

    def activate_manual_lock(self, reason="Emergency kill switch active"):
        self._manual_lock_enabled = True
        self._manual_lock_reason = str(reason or "Emergency kill switch active").strip()
        self._last_block_reason = self._manual_lock_reason
        self._last_blocked_at = datetime.now().isoformat(timespec="seconds")

    def clear_manual_lock(self):
        self._manual_lock_enabled = False
        self._manual_lock_reason = ""

    def is_locked(self):
        return bool(self._manual_lock_enabled)

    def evaluate_order(self, order):
        now = time.monotonic()
        self._reset_day_if_needed()
        self._prune(now)

        symbol = self._normalize_symbol((order or {}).get("symbol"))
        amount = abs(self._safe_float((order or {}).get("amount"), 0.0))

        if self._manual_lock_enabled:
            reason = self._manual_lock_reason or "Emergency kill switch active"
            return False, f"Behavior guard blocked trade: {reason}", self.status_snapshot()

        if self.daily_drawdown_limit_pct > 0:
            drawdown_pct = self._daily_drawdown_pct()
            if drawdown_pct >= self.daily_drawdown_limit_pct:
                reason = (
                    f"daily drawdown reached {drawdown_pct:.1%} "
                    f"(limit {self.daily_drawdown_limit_pct:.1%})"
                )
                self._activate_guard_cooldown(now, self.cooldown_after_loss_seconds, reason)
                return False, f"Behavior guard blocked trade: {reason}", self.status_snapshot()

        if self._guard_cooldown_until > now:
            remaining = self._format_seconds(self._guard_cooldown_until - now)
            reason = self._guard_cooldown_reason or "cooldown active"
            return False, f"Behavior guard cooldown active for {remaining}: {reason}", self.status_snapshot()

        hourly_attempts = self._hourly_attempts(now)
        if hourly_attempts >= self.max_orders_per_hour:
            reason = f"too many orders in the last hour ({hourly_attempts}/{self.max_orders_per_hour})"
            self._activate_guard_cooldown(now, 900, reason)
            return False, f"Behavior guard blocked trade: {reason}", self.status_snapshot()

        daily_attempts = self._daily_attempts(now)
        if daily_attempts >= self.max_orders_per_day:
            reason = f"too many orders in the last day ({daily_attempts}/{self.max_orders_per_day})"
            self._activate_guard_cooldown(now, 1800, reason)
            return False, f"Behavior guard blocked trade: {reason}", self.status_snapshot()

        if self._loss_streak >= self.max_consecutive_losses:
            reason = f"loss streak reached {self._loss_streak} trades"
            self._activate_guard_cooldown(now, self.cooldown_after_loss_seconds, reason)
            return False, f"Behavior guard blocked trade: {reason}", self.status_snapshot()

        reentry_until = self._symbol_reentry_until.get(symbol, 0.0)
        if reentry_until > now:
            remaining = self._format_seconds(reentry_until - now)
            reason = f"{symbol} is cooling down after a losing trade ({remaining} remaining)"
            self._last_block_reason = reason
            self._last_blocked_at = datetime.now().isoformat(timespec="seconds")
            return False, f"Behavior guard blocked trade: {reason}", self.status_snapshot()

        last_size = self._safe_float(self._last_size_by_symbol.get(symbol), 0.0)
        if amount > 0 and last_size > 0 and amount > last_size * self.max_size_jump_ratio:
            reason = (
                f"size jump on {symbol} is too large "
                f"({amount:.6g} vs recent {last_size:.6g}, limit {self.max_size_jump_ratio:.2f}x)"
            )
            self._last_block_reason = reason
            self._last_blocked_at = datetime.now().isoformat(timespec="seconds")
            return False, f"Behavior guard blocked trade: {reason}", self.status_snapshot()

        return True, "Allowed", self.status_snapshot()

    def record_order_attempt(self, order, allowed=True, reason=""):
        now = time.monotonic()
        self._reset_day_if_needed()
        self._prune(now)

        payload = order or {}
        symbol = self._normalize_symbol(payload.get("symbol"))
        amount = abs(self._safe_float(payload.get("amount") or payload.get("size"), 0.0))

        self._order_attempts.append(
            {
                "monotonic": now,
                "symbol": symbol,
                "source": str(payload.get("source") or "bot").strip().lower() or "bot",
                "amount": amount,
                "allowed": bool(allowed),
                "reason": str(reason or "").strip(),
            }
        )

        if allowed and symbol and amount > 0:
            self._last_size_by_symbol[symbol] = amount
        elif not allowed and reason:
            self._last_block_reason = str(reason)
            self._last_blocked_at = datetime.now().isoformat(timespec="seconds")

    def record_trade_update(self, trade):
        now = time.monotonic()
        self._reset_day_if_needed()
        self._prune(now)

        payload = trade or {}
        symbol = self._normalize_symbol(payload.get("symbol"))
        status = self._normalize_status(payload.get("status"))
        amount = abs(self._safe_float(payload.get("filled_size") or payload.get("size") or payload.get("amount"), 0.0))

        if symbol and amount > 0 and status in {"submitted", "open", "filled", "closed"}:
            self._last_size_by_symbol[symbol] = amount

        pnl_value = payload.get("pnl")
        pnl = None if pnl_value in ("", None) else self._safe_float(pnl_value, 0.0)

        if status in {"filled", "closed"}:
            if pnl is not None:
                if pnl < 0:
                    self._loss_streak += 1
                    if symbol:
                        self._symbol_reentry_until[symbol] = max(
                            self._symbol_reentry_until.get(symbol, 0.0),
                            now + self.same_symbol_reentry_cooldown_seconds,
                        )
                    if self._loss_streak >= self.max_consecutive_losses:
                        self._activate_guard_cooldown(
                            now,
                            self.cooldown_after_loss_seconds,
                            f"loss streak reached {self._loss_streak} trades",
                        )
                elif pnl > 0:
                    self._loss_streak = 0

    def status_snapshot(self):
        now = time.monotonic()
        self._reset_day_if_needed()
        self._prune(now)

        cooldown_remaining = max(0.0, self._guard_cooldown_until - now)
        drawdown_pct = self._daily_drawdown_pct()
        symbol_cooldowns = [
            self._format_seconds(expires_at - now)
            for expires_at in self._symbol_reentry_until.values()
            if expires_at > now
        ]

        state = "NORMAL"
        if self._manual_lock_enabled:
            state = "LOCKED"
        elif cooldown_remaining > 0:
            state = "COOLDOWN"
        elif self._loss_streak > 0 or drawdown_pct >= (self.daily_drawdown_limit_pct * 0.5):
            state = "WATCH"

        summary_parts = [
            f"{state}",
            f"{self._hourly_attempts(now)}/{self.max_orders_per_hour}h",
            f"{self._daily_attempts(now)}/{self.max_orders_per_day}d",
            f"L{self._loss_streak}",
            f"DD {drawdown_pct:.1%}",
        ]
        if cooldown_remaining > 0:
            summary_parts.append(self._format_seconds(cooldown_remaining))

        reason = self._manual_lock_reason or self._guard_cooldown_reason or self._last_block_reason
        if state == "NORMAL":
            reason = "No active behavior restrictions"

        return {
            "enabled": True,
            "state": state,
            "summary": " | ".join(summary_parts),
            "reason": reason,
            "cooldown_remaining_seconds": int(cooldown_remaining),
            "hourly_attempts": self._hourly_attempts(now),
            "daily_attempts": self._daily_attempts(now),
            "blocked_attempts_hour": self._blocked_attempts(now),
            "loss_streak": self._loss_streak,
            "daily_drawdown_pct": drawdown_pct,
            "active_symbol_cooldowns": len(symbol_cooldowns),
            "last_blocked_at": self._last_blocked_at,
        }
