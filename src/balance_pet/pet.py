"""桌面宠物主窗口。"""

from __future__ import annotations

import os
import time
from pathlib import Path

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QRectF,
    QSequentialAnimationGroup,
    QSettings,
    Qt,
    QUrl,
)
from PySide6.QtGui import QAction, QActionGroup, QIcon, QImage, QMouseEvent, QPainter, QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from .balance import BalanceResponseError, format_balance, parse_balance_body
from .bubble import BalanceBubble

BALANCE_URL = "https://hkust.azure-api.net/hkust-genai-auth/v1/balance"
REQUEST_COOLDOWN_SECONDS = 5.0
BASE_HEIGHT = 280
DRAG_THRESHOLD = 5
MAX_ANIMATION_SCALE_X = 1.13
MAX_ANIMATION_SCALE_Y = 1.08
# 判定“可见内容”的 alpha 阈值，用于忽略淡淡的抗锯齿/阴影像素。
ALPHA_VISIBLE_THRESHOLD = 128


def measure_transparent_margins(pixmap: QPixmap) -> tuple[int, int, int, int]:
    """测量图片四周透明边缘（左、上、右、下），以源图像素计。"""
    image = pixmap.toImage().convertToFormat(QImage.Format.Format_ARGB32)
    width, height = image.width(), image.height()
    stride = image.bytesPerLine()
    data = bytes(image.constBits())[: stride * height]
    left, top, right, bottom = width, height, -1, -1
    for y in range(height):
        base = y * stride
        for x in range(width):
            if data[base + 4 * x + 3] > ALPHA_VISIBLE_THRESHOLD:
                if x < left:
                    left = x
                if x > right:
                    right = x
                if y < top:
                    top = y
                if y > bottom:
                    bottom = y
    if right < 0:
        return 0, 0, 0, 0
    return left, top, width - 1 - right, height - 1 - bottom


class PetWindow(QWidget):
    def __init__(self, image_path: Path) -> None:
        super().__init__(None)
        self._source = QPixmap(str(image_path))
        if self._source.isNull():
            raise FileNotFoundError(f"无法读取宠物图片：{image_path}")

        self._alpha_margins = measure_transparent_margins(self._source)

        self._settings = QSettings("BalancePet", "BalanceDesktopPet")
        self._size_scale = float(self._settings.value("size_scale", 1.0))
        self._scale_x = 1.0
        self._scale_y = 1.0
        self._flipped = False
        self._press_global = QPoint()
        self._window_at_press = QPoint()
        self._dragging = False
        self._last_request_at = float("-inf")
        self._last_balance: str | None = None
        self._active_reply: QNetworkReply | None = None
        self._bounce: QSequentialAnimationGroup | None = None

        self._network = QNetworkAccessManager(self)
        self._bubble = BalanceBubble()
        self._tray = QSystemTrayIcon(self)

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setWindowTitle("余额桌面宠物")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._apply_size()
        self._create_tray()
        self._restore_position()
        self._update_flip()

    def _create_tray(self) -> None:
        icon = QIcon(self._source)
        self.setWindowIcon(icon)
        self._tray.setIcon(icon)
        self._tray.setToolTip("余额桌面宠物")
        menu = QMenu()
        menu.addAction("显示宠物").triggered.connect(self.restore_from_tray)
        menu.addSeparator()
        menu.addAction("退出").triggered.connect(QApplication.instance().quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.restore_from_tray()

    def restore_from_tray(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def _apply_size(self) -> None:
        height = round(BASE_HEIGHT * self._size_scale)
        width = round(height * self._source.width() / self._source.height())
        bottom_right = self.geometry().bottomRight()
        self.setFixedSize(width, height)
        if not bottom_right.isNull():
            self.move(bottom_right - QPoint(width - 1, height - 1))
        self.update()

    def _transparent_margins(self) -> tuple[int, int, int, int]:
        """按当前显示尺寸换算图片透明边缘（左、上、右、下），随窗口缩放变化。"""
        left, top, right, bottom = self._alpha_margins
        sx = self.width() / self._source.width()
        sy = self.height() / self._source.height()
        if self._flipped:
            left, right = right, left
        return round(left * sx), round(top * sy), round(right * sx), round(bottom * sy)

    def _clamp_to_screen(self, position: QPoint, screen) -> QPoint:
        area = screen.availableGeometry()
        left, top, right, _bottom = self._transparent_margins()
        # 允许窗口越出屏幕，使图片中的可见内容（不含透明边缘）刚好贴到屏幕边缘。
        x = min(max(position.x(), area.left() - left), area.right() - self.width() + 1 + right)
        y = min(max(position.y(), area.top() - top), area.bottom() - self.height() + 1)
        return QPoint(x, y)

    def _restore_position(self) -> None:
        saved = self._settings.value("position")
        if isinstance(saved, QPoint):
            screen = QApplication.screenAt(saved + QPoint(self.width() // 2, self.height() // 2))
            if screen is not None:
                self.move(self._clamp_to_screen(saved, screen))
                return
        screen = QApplication.primaryScreen()
        self.move(self._clamp_to_screen(QPoint(screen.availableGeometry().right() - self.width() - 24,
                                                screen.availableGeometry().bottom() - self.height() - 24), screen))

    def get_scale_x(self) -> float:
        return self._scale_x

    def set_scale_x(self, value: float) -> None:
        self._scale_x = value
        self.update()

    scaleX = Property(float, get_scale_x, set_scale_x)

    def get_scale_y(self) -> float:
        return self._scale_y

    def set_scale_y(self, value: float) -> None:
        self._scale_y = value
        self.update()

    scaleY = Property(float, get_scale_y, set_scale_y)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.translate(self.width() / 2, self.height())
        painter.scale((-1.0 if self._flipped else 1.0) * self._scale_x, self._scale_y)
        # 直接由原始高分辨率图片绘制到目标区域，只进行一次采样。
        # 旧实现先缩小 QPixmap，Q 弹动画时又让 Painter 二次缩放，在高 DPI 屏上会明显发糊。
        target = QRectF(-self.width() / 2, -self.height(), self.width(), self.height())
        painter.drawPixmap(target, self._source, QRectF(self._source.rect()))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._window_at_press = self.pos()
            self._dragging = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(event.globalPosition().toPoint())
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._press_global
            if delta.manhattanLength() >= DRAG_THRESHOLD:
                self._dragging = True
            if self._dragging:
                self.move(self._window_at_press + delta)
                self._update_flip()
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            if self._dragging:
                self._keep_on_screen()
            else:
                self._play_bounce()
                self._request_balance()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _keep_on_screen(self) -> None:
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(self._clamp_to_screen(self.pos(), screen))
        self._settings.setValue("position", self.pos())
        self._update_flip()

    def _update_flip(self) -> None:
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        should_flip = self.frameGeometry().center().x() < screen.availableGeometry().center().x()
        if should_flip != self._flipped:
            self._flipped = should_flip
            self.update()
        self._sync_visible_bubble()

    def _play_bounce(self) -> None:
        if self._bounce is not None:
            self._bounce.stop()
        sequence = QSequentialAnimationGroup(self)
        for duration, sx, sy, easing in (
            (85, 1.13, 0.86, QEasingCurve.Type.OutQuad),
            (105, 0.93, 1.08, QEasingCurve.Type.InOutQuad),
            (150, 1.0, 1.0, QEasingCurve.Type.OutBounce),
        ):
            group = QParallelAnimationGroup(sequence)
            for property_name, end_value in ((b"scaleX", sx), (b"scaleY", sy)):
                animation = QPropertyAnimation(self, property_name, group)
                animation.setDuration(duration)
                animation.setEndValue(end_value)
                animation.setEasingCurve(easing)
                group.addAnimation(animation)
            sequence.addAnimation(group)
        self._bounce = sequence
        sequence.start()

    def _bubble_side_and_position(self) -> tuple[bool, QPoint]:
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        pet_is_left = self.frameGeometry().center().x() < screen.availableGeometry().center().x()
        # 宠物在左边时气泡放右上方，小圆朝左；反之亦然。
        if pet_is_left:
            position = QPoint(
                self.x() + self.width() - 18 - self._bubble.PET_OVERLAP,
                self.y() - 42,
            )
            points_left = True
        else:
            position = QPoint(
                self.x() - self._bubble.width() + 18 + self._bubble.PET_OVERLAP,
                self.y() - 42,
            )
            points_left = False
        area = screen.availableGeometry()
        x = min(max(position.x(), area.left()), area.right() - self._bubble.width() + 1)
        y = min(max(position.y(), area.top()), area.bottom() - self._bubble.height() + 1)
        return points_left, QPoint(x, y)

    def _sync_visible_bubble(self) -> None:
        """让已显示的气泡跟随宠物，并在跨过屏幕中线后切换方向。"""
        if not self._bubble.isVisible():
            return
        points_left, position = self._bubble_side_and_position()
        self._bubble.move(position)
        self._bubble.set_points_left(points_left)

    def _show_bubble(self, text: str) -> None:
        points_left, position = self._bubble_side_and_position()
        self._bubble.move(position)
        self._bubble.show_message(text, points_left)

    def _request_balance(self) -> None:
        now = time.monotonic()
        if now - self._last_request_at < REQUEST_COOLDOWN_SECONDS:
            if self._last_balance is not None:
                self._show_bubble(f"余额\n{self._last_balance}")
            else:
                self._show_bubble("余额\n查询中…")
            return

        token = os.getenv("HKUST_BEARER_TOKEN", "").strip()
        if not token:
            self._show_bubble("余额\n未配置密钥")
            return

        self._last_request_at = now
        self._show_bubble("余额\n查询中…")
        request = QNetworkRequest(QUrl(BALANCE_URL))
        request.setRawHeader(b"Authorization", f"Bearer {token}".encode())
        request.setRawHeader(b"Accept", b"text/plain")
        request.setTransferTimeout(10_000)
        reply = self._network.get(request)
        self._active_reply = reply
        reply.finished.connect(lambda current=reply: self._handle_reply(current))

    def _handle_reply(self, reply: QNetworkReply) -> None:
        try:
            status = reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
            raw = bytes(reply.readAll())
            if reply.error() != QNetworkReply.NetworkError.NoError:
                message = f"请求失败\nHTTP {status}" if status else "请求失败\n网络错误"
                self._show_bubble(message)
                return
            self._last_balance = format_balance(parse_balance_body(raw))
            self._show_bubble(f"余额\n{self._last_balance}")
        except BalanceResponseError:
            self._show_bubble("余额\n响应格式错误")
        finally:
            if self._active_reply is reply:
                self._active_reply = None
            reply.deleteLater()

    def _show_context_menu(self, global_position: QPoint) -> None:
        menu = QMenu(self)
        size_menu = menu.addMenu("调整大小")
        size_group = QActionGroup(size_menu)
        size_group.setExclusive(True)
        for label, scale in (("50%", 0.5), ("75%", 0.75), ("100%", 1.0), ("125%", 1.25), ("150%", 1.5)):
            action = QAction(label, size_menu, checkable=True)
            action.setChecked(abs(self._size_scale - scale) < 0.001)
            action.triggered.connect(lambda checked=False, value=scale: self._set_size(value))
            size_group.addAction(action)
            size_menu.addAction(action)
        menu.addSeparator()
        menu.addAction("收到托盘").triggered.connect(self._hide_to_tray)
        menu.addSeparator()
        menu.addAction("退出").triggered.connect(QApplication.instance().quit)
        menu.exec(global_position)

    def _set_size(self, scale: float) -> None:
        self._size_scale = scale
        self._settings.setValue("size_scale", scale)
        self._apply_size()
        self._keep_on_screen()

    def _hide_to_tray(self) -> None:
        self._bubble.hide()
        self.hide()
        self._tray.showMessage("余额桌面宠物", "宠物已收到托盘，单击托盘图标可恢复。")

    def closeEvent(self, event) -> None:
        self._settings.setValue("position", self.pos())
        self._bubble.close()
        self._tray.hide()
        super().closeEvent(event)
