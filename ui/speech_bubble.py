from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QFontMetrics, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QLabel, QWidget


class SpeechBubble(QWidget):
    """Speech bubble with a visible tail so it feels attached to the mascot."""

    MIN_WIDTH = 180
    MAX_WIDTH = 280
    SCREEN_MARGIN = 10
    ANCHOR_GAP = 4
    PADDING_X = 16
    PADDING_Y = 12
    CORNER_RADIUS = 14
    TAIL_WIDTH = 18
    TAIL_HEIGHT = 16
    BORDER_COLOR = QColor("#bcc6d3")
    FILL_COLOR = QColor("#fffdf8")
    TEXT_COLOR = QColor("#20242a")

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.label.setStyleSheet(
            """
            QLabel {
                background: transparent;
                color: #20242a;
                font-family: "Yu Gothic UI", "Meiryo", sans-serif;
                font-size: 13px;
            }
            """
        )

        self.tail_on_left = True
        self.anchor_rect = QRect()

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

    def show_message(
        self,
        text: str,
        anchor_rect: QRect,
        available_rect: QRect,
        duration_ms: int = 4000,
    ) -> None:
        self.anchor_rect = anchor_rect
        self.label.setText(text)
        self._resize_to_text(text)
        self.move(self._position_for(anchor_rect, available_rect))
        self.show()
        self.raise_()
        self.hide_timer.start(duration_ms)
        self.update()

    def reposition(self, anchor_rect: QRect, available_rect: QRect) -> None:
        self.anchor_rect = anchor_rect
        if self.isVisible():
            self.move(self._position_for(anchor_rect, available_rect))
            self.update()

    def _resize_to_text(self, text: str) -> None:
        metrics = QFontMetrics(self.label.font())
        content_width = max(
            self.MIN_WIDTH - self.PADDING_X * 2,
            min(self.MAX_WIDTH - self.PADDING_X * 2, metrics.horizontalAdvance(text[:80]) + 20),
        )
        text_rect = metrics.boundingRect(QRect(0, 0, content_width, 2000), Qt.TextWordWrap, text)
        body_width = max(self.MIN_WIDTH, min(self.MAX_WIDTH, text_rect.width() + self.PADDING_X * 2))
        body_height = text_rect.height() + self.PADDING_Y * 2

        total_width = body_width + self.TAIL_WIDTH
        total_height = body_height
        self.resize(total_width, total_height)

        if self.tail_on_left:
            label_x = self.TAIL_WIDTH
        else:
            label_x = 0
        self.label.setGeometry(label_x, 0, body_width, body_height)

    def _position_for(self, anchor_rect: QRect, available_rect: QRect) -> QPoint:
        body_width = self.width() - self.TAIL_WIDTH
        preferred_left_x = anchor_rect.left() - body_width - self.TAIL_WIDTH - self.ANCHOR_GAP
        preferred_right_x = anchor_rect.right() + self.ANCHOR_GAP

        place_left = preferred_left_x >= available_rect.left() + self.SCREEN_MARGIN
        self.tail_on_left = not place_left

        self._resize_to_text(self.label.text())

        x = preferred_left_x if place_left else preferred_right_x
        y = anchor_rect.top() + 12

        x = min(
            max(available_rect.left() + self.SCREEN_MARGIN, x),
            available_rect.right() - self.width() - self.SCREEN_MARGIN,
        )
        y = min(
            max(available_rect.top() + self.SCREEN_MARGIN, y),
            available_rect.bottom() - self.height() - self.SCREEN_MARGIN,
        )
        return QPoint(x, y)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(self.BORDER_COLOR, 1))
        painter.setBrush(self.FILL_COLOR)
        painter.drawPath(self._bubble_path())
        super().paintEvent(event)

    def _bubble_path(self) -> QPainterPath:
        rect = self.rect().adjusted(0, 0, -1, -1)
        body_rect = rect.adjusted(self.TAIL_WIDTH if self.tail_on_left else 0, 0, 0 if self.tail_on_left else -self.TAIL_WIDTH, 0)

        path = QPainterPath()
        path.addRoundedRect(body_rect, self.CORNER_RADIUS, self.CORNER_RADIUS)

        center_y = min(max(self.height() // 2, self.CORNER_RADIUS + 10), self.height() - self.CORNER_RADIUS - 10)
        tail = QPainterPath()
        if self.tail_on_left:
            tail.moveTo(body_rect.left(), center_y - 8)
            tail.lineTo(6, center_y)
            tail.lineTo(body_rect.left(), center_y + 8)
        else:
            tail.moveTo(body_rect.right(), center_y - 8)
            tail.lineTo(self.width() - 6, center_y)
            tail.lineTo(body_rect.right(), center_y + 8)
        tail.closeSubpath()
        path = path.united(tail)
        return path
