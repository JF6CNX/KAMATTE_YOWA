from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel


class SpeechBubble(QLabel):
    """キャラクターの近くに出る小さな吹き出しです。"""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumWidth(180)
        self.setMaximumWidth(260)
        self.setStyleSheet(
            """
            QLabel {
                background: rgba(255, 255, 255, 235);
                color: #20242a;
                border: 1px solid rgba(40, 45, 52, 80);
                border-radius: 12px;
                padding: 10px 12px;
                font-family: "Yu Gothic UI", "Meiryo", sans-serif;
                font-size: 13px;
            }
            """
        )

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.hide)

    def show_message(self, text: str, x: int, y: int, duration_ms: int = 4000) -> None:
        """指定位置にメッセージを表示し、数秒後に自動で消します。"""
        self.setText(text)
        self.adjustSize()
        self.move(x, y)
        self.show()
        self.hide_timer.start(duration_ms)
