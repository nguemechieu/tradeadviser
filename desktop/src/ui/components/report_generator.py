from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas


class ReportGenerator:
    """Generate simple PDF trade reports using ReportLab."""

    def __init__(
            self,
            *,
            title: str = "TradeAdviser Trading Report",
            author: str = "TradeAdviser",
    ) -> None:
        self.title = str(title or "Trading Report")
        self.author = str(author or "TradeAdviser")

    def generate_report(self, filename: str | Path, trades: Iterable[Any]) -> str:
        path = Path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)

        trade_rows = self._normalize_trades(trades)

        pdf = canvas.Canvas(str(path), pagesize=letter)
        pdf.setTitle(self.title)
        pdf.setAuthor(self.author)

        width, height = letter
        margin = 0.65 * inch
        y = height - margin

        y = self._draw_header(pdf, y, width, margin)
        y = self._draw_summary(pdf, y, trade_rows, width, margin)

        if not trade_rows:
            pdf.setFont("Helvetica", 10)
            pdf.drawString(margin, y, "No trades available for this report.")
            pdf.save()
            return str(path)

        y -= 12
        y = self._draw_table_header(pdf, y, margin)

        for index, trade in enumerate(trade_rows, start=1):
            if y < margin + 40:
                pdf.showPage()
                y = height - margin
                y = self._draw_header(pdf, y, width, margin, compact=True)
                y = self._draw_table_header(pdf, y - 10, margin)

            y = self._draw_trade_row(pdf, y, margin, index, trade)

        pdf.save()
        return str(path)

    def _draw_header(self, pdf: canvas.Canvas, y: float, width: float, margin: float, *, compact: bool = False) -> float:
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold", 16 if not compact else 13)
        pdf.drawString(margin, y, self.title)

        pdf.setFont("Helvetica", 9)
        pdf.setFillColor(colors.darkgray)
        generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pdf.drawRightString(width - margin, y, f"Generated: {generated}")

        y -= 20 if not compact else 14

        pdf.setStrokeColor(colors.lightgrey)
        pdf.line(margin, y, width - margin, y)

        return y - 18

    def _draw_summary(self, pdf: canvas.Canvas, y: float, trades: list[dict[str, Any]], width: float, margin: float) -> float:
        total_trades = len(trades)
        total_pnl = sum(self._safe_float(trade.get("pnl")) for trade in trades)
        wins = sum(1 for trade in trades if self._safe_float(trade.get("pnl")) > 0)
        losses = sum(1 for trade in trades if self._safe_float(trade.get("pnl")) < 0)
        win_rate = wins / total_trades if total_trades else 0.0

        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(margin, y, "Summary")

        y -= 16
        pdf.setFont("Helvetica", 9)

        summary = [
            f"Total trades: {total_trades}",
            f"Wins: {wins}",
            f"Losses: {losses}",
            f"Win rate: {win_rate:.1%}",
            f"Total PnL: {total_pnl:.2f}",
        ]

        x = margin
        for item in summary:
            pdf.drawString(x, y, item)
            x += 1.35 * inch

        return y - 24

    def _draw_table_header(self, pdf: canvas.Canvas, y: float, margin: float) -> float:
        pdf.setFillColor(colors.HexColor("#F2F2F2"))
        pdf.rect(margin, y - 4, 7.1 * inch, 18, fill=True, stroke=False)

        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold", 8)

        columns = [
            ("#", 0),
            ("Symbol", 0.35),
            ("Side", 1.15),
            ("Qty", 1.75),
            ("Price", 2.35),
            ("PnL", 3.05),
            ("Strategy", 3.75),
            ("Status", 5.15),
            ("Time", 5.9),
        ]

        for label, offset in columns:
            pdf.drawString(margin + offset * inch, y, label)

        return y - 18

    def _draw_trade_row(self, pdf: canvas.Canvas, y: float, margin: float, index: int, trade: dict[str, Any]) -> float:
        pnl = self._safe_float(trade.get("pnl"))
        side = str(trade.get("side") or trade.get("action") or "").upper()
        symbol = str(trade.get("symbol") or "").upper()
        qty = self._safe_float(trade.get("quantity") or trade.get("qty") or trade.get("amount"))
        price = self._safe_float(trade.get("price") or trade.get("entry_price"))
        strategy = str(trade.get("strategy") or trade.get("strategy_name") or "")[:18]
        status = str(trade.get("status") or trade.get("outcome") or "")[:12]
        timestamp = str(trade.get("timestamp") or trade.get("time") or "")[:16]

        pdf.setFont("Helvetica", 8)
        pdf.setFillColor(colors.black)

        values = [
            (str(index), 0),
            (symbol[:10], 0.35),
            (side[:5], 1.15),
            (f"{qty:.6g}", 1.75),
            (f"{price:.6g}", 2.35),
            (f"{pnl:.2f}", 3.05),
            (strategy, 3.75),
            (status, 5.15),
            (timestamp, 5.9),
        ]

        for value, offset in values:
            pdf.drawString(margin + offset * inch, y, value)

        return y - 14

    def _normalize_trades(self, trades: Iterable[Any]) -> list[dict[str, Any]]:
        if trades is None:
            return []

        if hasattr(trades, "to_dict"):
            try:
                records = trades.to_dict("records")
                if isinstance(records, list):
                    return [self._normalize_trade(item) for item in records]
            except Exception:
                pass

        rows = []
        for trade in trades:
            rows.append(self._normalize_trade(trade))

        return rows

    def _normalize_trade(self, trade: Any) -> dict[str, Any]:
        if isinstance(trade, dict):
            return dict(trade)

        if hasattr(trade, "to_dict"):
            try:
                value = trade.to_dict()
                if isinstance(value, dict):
                    return dict(value)
            except Exception:
                pass

        if hasattr(trade, "__dict__"):
            return dict(vars(trade))

        return {"raw": str(trade)}

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value in (None, ""):
                return float(default)
            return float(value)
        except Exception:
            return float(default)


__all__ = ["ReportGenerator"]