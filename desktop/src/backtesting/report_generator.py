from datetime import datetime
from pathlib import Path

import pandas as pd


class ReportGenerator:
    def __init__(self, trades=None, equity_history=None, output_dir="reports"):
        self.trades = self._normalize_trades(trades)
        self.equity_history = list(equity_history or [])
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _normalize_trades(self, trades):
        if trades is None:
            return pd.DataFrame()
        if isinstance(trades, pd.DataFrame):
            return trades.copy()
        return pd.DataFrame(trades)

    def generate(self, trades=None, equity_history=None):
        trades_df = self._normalize_trades(trades) if trades is not None else self.trades
        equity_curve = list(equity_history) if equity_history is not None else list(self.equity_history)

        if trades_df.empty:
            return {
                "total_trades": 0,
                "closed_trades": 0,
                "total_profit": 0.0,
                "gross_profit": 0.0,
                "gross_loss": 0.0,
                "win_rate": 0.0,
                "avg_profit": 0.0,
                "sharpe_ratio": 0.0,
                "sortino_ratio": 0.0,
                "profit_factor": 0.0,
                "expectancy": 0.0,
                "commission_paid": 0.0,
                "slippage_cost": 0.0,
                "max_drawdown": 0.0,
                "final_equity": float(equity_curve[-1]) if equity_curve else 0.0,
                "net_return_pct": 0.0,
            }

        pnl = pd.to_numeric(trades_df.get("pnl", pd.Series(dtype=float)), errors="coerce").dropna()
        closed_trade_count = int((trades_df.get("type") == "EXIT").sum()) if "type" in trades_df else len(pnl)

        total_profit = float(pnl.sum()) if not pnl.empty else 0.0
        win_rate = float((pnl > 0).mean()) if not pnl.empty else 0.0
        avg_profit = float(pnl.mean()) if not pnl.empty else 0.0
        sharpe = float(pnl.mean() / pnl.std()) if len(pnl) > 1 and float(pnl.std()) != 0 else 0.0
        downside = pnl[pnl < 0]
        downside_std = float(downside.std()) if len(downside) > 1 else 0.0
        sortino = float(pnl.mean() / downside_std) if downside_std not in (0.0, float("nan")) else 0.0
        gross_profit = float(pnl[pnl > 0].sum()) if not pnl.empty else 0.0
        gross_loss = abs(float(pnl[pnl < 0].sum())) if not pnl.empty else 0.0
        profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
        expectancy = avg_profit
        commission_paid = float(pd.to_numeric(trades_df.get("commission", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum())
        slippage_cost = float(pd.to_numeric(trades_df.get("slippage_cost", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum())

        if not equity_curve and "equity" in trades_df:
            equity_curve = pd.to_numeric(trades_df["equity"], errors="coerce").dropna().tolist()

        max_drawdown = float(self._max_drawdown(equity_curve))
        final_equity = float(equity_curve[-1]) if equity_curve else 0.0

        return {
            "total_trades": int(len(trades_df)),
            "closed_trades": int(closed_trade_count),
            "total_profit": total_profit,
            "gross_profit": gross_profit,
            "gross_loss": -gross_loss,
            "win_rate": win_rate,
            "avg_profit": avg_profit,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "commission_paid": commission_paid,
            "slippage_cost": slippage_cost,
            "max_drawdown": max_drawdown,
            "final_equity": final_equity,
            "net_return_pct": ((final_equity - float(equity_curve[0])) / float(equity_curve[0]) * 100.0) if equity_curve and float(equity_curve[0]) else 0.0,
        }

    def _max_drawdown(self, equity_curve):
        if not equity_curve:
            return 0.0

        series = pd.Series(equity_curve, dtype=float)
        peak = series.cummax()
        drawdown = peak - series
        return float(drawdown.max())

    def _timestamped_path(self, suffix):
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.output_dir / f"backtest_report_{stamp}.{suffix}"

    def export_excel(self, path=None):
        report = self.generate()
        trades_df = self.trades.copy()
        summary_df = pd.DataFrame([report])

        path = Path(path) if path else self._timestamped_path("xlsx")
        try:
            with pd.ExcelWriter(path) as writer:
                trades_df.to_excel(writer, sheet_name="trades", index=False)
                summary_df.to_excel(writer, sheet_name="summary", index=False)
        except Exception:
            path = path.with_suffix(".csv")
            merged = trades_df.copy()
            for key, value in report.items():
                merged[key] = value
            merged.to_csv(path, index=False)
        return path

    def export_pdf(self, path=None):
        report = self.generate()
        lines = [
            "Sopotek Backtest Report",
            "",
        ]
        for key, value in report.items():
            lines.append(f"{key.replace('_', ' ').title()}: {value}")

        path = Path(path) if path else self._timestamped_path("pdf")
        self._write_simple_pdf(path, lines)
        return path

    def _write_simple_pdf(self, path, lines):
        escaped = []
        for line in lines:
            escaped.append(
                str(line).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            )

        content_parts = ["BT", "/F1 12 Tf", "72 760 Td"]
        for index, line in enumerate(escaped):
            if index > 0:
                content_parts.append("0 -16 Td")
            content_parts.append(f"({line}) Tj")
        content_parts.append("ET")
        content = "\n".join(content_parts).encode("latin-1", errors="replace")

        objects = []
        objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
        objects.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
        objects.append(
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >> endobj\n"
        )
        objects.append(
            f"4 0 obj << /Length {len(content)} >> stream\n".encode("latin-1")
            + content
            + b"\nendstream endobj\n"
        )
        objects.append(b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")

        output = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for obj in objects:
            offsets.append(len(output))
            output.extend(obj)

        xref_start = len(output)
        output.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
        output.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            output.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))

        output.extend(
            (
                f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref_start}\n%%EOF"
            ).encode("latin-1")
        )

        path.write_bytes(output)
