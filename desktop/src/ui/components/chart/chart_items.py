import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QPainter, QPen, QPicture


class CandlestickItem(pg.GraphicsObject):
    """Fast candlestick renderer for OHLC rows: [x, open, close, low, high]."""

    def __init__(self, data=None, body_width=0.7, up_color="#26a69a", down_color="#ef5350"):
        super().__init__()
        self.data = data or []
        self.body_width = max(1e-9, float(body_width))
        self.up_color = up_color
        self.down_color = down_color
        self._x_offset = 0.0
        self.picture = QPicture()
        self._bounding_rect = QRectF(0, 0, 1, 1)
        self.generatePicture(self.data)

    def set_colors(self, up_color, down_color):
        self.up_color = up_color
        self.down_color = down_color
        self.generatePicture(self.data)
        self.update()

    def set_body_width(self, body_width):
        self.body_width = max(1e-9, float(body_width))
        self.generatePicture(self.data)
        self.update()

    def set_data(self, data):
        self.setData(data)

    def setData(self, data):
        self.data = data if data is not None else []
        self.generatePicture(self.data)
        self.update()

    def generatePicture(self, data):
        self.picture = QPicture()
        painter = QPainter(self.picture)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        up_pen = QPen(pg.mkColor(self.up_color))
        down_pen = QPen(pg.mkColor(self.down_color))
        down_brush = QBrush(pg.mkColor(self.down_color))
        transparent_brush = QBrush(Qt.BrushStyle.NoBrush)

        for pen in (up_pen, down_pen):
            pen.setWidthF(1.0)
            pen.setCosmetic(True)

        min_x = float("inf")
        max_x = float("-inf")
        min_y = float("inf")
        max_y = float("-inf")

        rows = data if data is not None else []
        valid_times = []
        for row in rows:
            if row is None or len(row) < 5:
                continue
            try:
                valid_times.append(float(row[0]))
            except Exception:
                continue
        self._x_offset = min(valid_times) if valid_times else 0.0
        self.setPos(self._x_offset, 0.0)

        for row in rows:
            if len(row) < 5:
                continue

            try:
                t, open_, close, low, high = map(float, row[:5])
            except Exception:
                continue
            if not all(np.isfinite(value) for value in (t, open_, close, low, high)):
                continue
            t -= self._x_offset
            high = max(high, open_, close, low)
            low = min(low, open_, close, high)
            rising = close >= open_

            body_top = max(open_, close)
            body_bottom = min(open_, close)
            half_width = self.body_width / 2.0
            body = QRectF(t - half_width, body_bottom, self.body_width, body_top - body_bottom)

            painter.setPen(up_pen if rising else down_pen)
            painter.setBrush(transparent_brush if rising else down_brush)

            # Draw split wick segments so the body stays visually crisp like MT4/MT5.
            painter.drawLine(QPointF(t, low), QPointF(t, body_bottom))
            painter.drawLine(QPointF(t, body_top), QPointF(t, high))

            if body.height() < 1e-9:
                painter.drawLine(
                    QPointF(t - half_width, close),
                    QPointF(t + half_width, close),
                )
            else:
                painter.drawRect(body)

            min_x = min(min_x, t - self.body_width)
            max_x = max(max_x, t + self.body_width)
            min_y = min(min_y, low)
            max_y = max(max_y, high)

        painter.end()

        if min_x == float("inf"):
            self.setPos(0.0, 0.0)
            self._bounding_rect = QRectF(0, 0, 1, 1)
        else:
            self._bounding_rect = QRectF(min_x, min_y, max_x - min_x, max(max_y - min_y, 1e-9))

    def paint(self, painter, *args):
        painter.drawPicture(0, 0, self.picture)

    def boundingRect(self):
        return self._bounding_rect
