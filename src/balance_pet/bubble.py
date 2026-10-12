"""余额气泡浮层。"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


class BalanceBubble(QWidget):
    WIDTH = 190
    HEIGHT = 126
    # 图片四周有透明留白，气泡尾部需要更深入宠物窗口，避免拉伸时看起来被裁住。
    PET_OVERLAP = 30

    def __init__(self) -> None:
        super().__init__(None)
        self._text = "余额\n查询中…"
        self._points_left = True
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_message(self, text: str, points_left: bool, timeout_ms: int = 8000) -> None:
        self._text = text
        self.set_points_left(points_left)
        self.update()
        self.show()
        self.raise_()
        self._hide_timer.start(timeout_ms)

    def set_points_left(self, points_left: bool) -> None:
        """拖动宠物跨过屏幕中线时，仅调整气泡朝向，不重置隐藏计时。"""
        if self._points_left != points_left:
            self._points_left = points_left
            self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor(76, 69, 105, 230), 2.5))
        painter.setBrush(QColor(252, 250, 255, 242))

        # 指向宠物方向的两个小圆，以及承载文字的大椭圆。
        if self._points_left:
            small = [QPointF(13, 105), QPointF(30, 91)]
        else:
            small = [QPointF(177, 105), QPointF(160, 91)]
        painter.drawEllipse(small[0], 5, 5)
        painter.drawEllipse(small[1], 8, 8)

        ellipse = QRectF(10, 8, 170, 82)
        painter.drawEllipse(ellipse)
        painter.setPen(QColor(56, 51, 76))
        font = QFont("Microsoft YaHei UI", 12)
        font.setWeight(QFont.Weight.DemiBold)
        painter.setFont(font)
        painter.drawText(ellipse.adjusted(12, 7, -12, -7), Qt.AlignmentFlag.AlignCenter, self._text)
