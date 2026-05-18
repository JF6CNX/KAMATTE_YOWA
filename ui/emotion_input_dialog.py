from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout


class EmotionInputDialog(QDialog):
    """ユーザーが今の気分を短く入力する小さなウィンドウです。"""

    submitted = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("今の気分を話す")
        self.setWindowFlags(self.windowFlags() | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setFixedSize(320, 180)

        self.input = QTextEdit(self)
        self.input.setPlaceholderText("今の気分を少しだけ書いてください")

        submit_button = QPushButton("話す", self)
        cancel_button = QPushButton("閉じる", self)
        submit_button.clicked.connect(self._submit)
        cancel_button.clicked.connect(self.close)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(submit_button)
        button_layout.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.input)
        layout.addLayout(button_layout)

    def _submit(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return

        self.submitted.emit(text)
        self.input.clear()
        self.close()
