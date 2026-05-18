import sys

from PySide6.QtWidgets import QApplication

from ui.mascot_window import MascotWindow


def main() -> int:
    """アプリケーションの入口です。"""
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    mascot = MascotWindow()
    mascot.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
