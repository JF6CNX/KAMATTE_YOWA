import ctypes
import ctypes.wintypes
import random
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QPushButton, QWidget

from logic.actions import RandomAction, RandomActionManager
from logic.ai_dialogue import AIDialogueService
from logic.dialogue import DialogueManager
from logic.emotion import EmotionClassifier
from logic.state import CharacterStateService
from ui.emotion_input_dialog import EmotionInputDialog
from ui.speech_bubble import SpeechBubble


APP_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = APP_ROOT / "assets"


class MascotWindow(QWidget):
    """画面右下に表示する、ドラッグ可能なマスコットウィンドウです。"""

    WM_HOTKEY = 0x0312
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    VK_D = 0x44
    HOTKEY_ID = 1001

    def __init__(self) -> None:
        super().__init__()
        self.state_service = CharacterStateService()
        self.dialogue = DialogueManager()
        self.action_manager = RandomActionManager()
        self.emotion_classifier = EmotionClassifier()
        self.ai_dialogue = AIDialogueService(self.state_service)
        self.bubble = SpeechBubble()
        self.input_dialog: EmotionInputDialog | None = None

        self.drag_start_position: QPoint | None = None
        self.paused = False
        self.hotkey_registered = False

        self._setup_window()
        self._setup_character()
        self._setup_timers()
        self._setup_shortcut_fallback()
        self._update_character_image()

    @property
    def state(self):
        """UIから現在状態を参照しやすくするためのプロパティです。"""
        return self.state_service.state

    def _setup_window(self) -> None:
        """透明で常に手前に表示されるウィンドウにします。"""
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(172, 194)

    def _setup_character(self) -> None:
        """キャラクター画像と、気分入力ボタンを配置します。"""
        self.character_label = QLabel(self)
        self.character_label.setAlignment(Qt.AlignCenter)
        self.character_label.setGeometry(6, 0, 160, 160)

        self.talk_button = QPushButton("今の気分を話す", self)
        self.talk_button.setGeometry(18, 162, 136, 28)
        self.talk_button.clicked.connect(self._open_emotion_input)
        self.talk_button.setStyleSheet(
            """
            QPushButton {
                background: rgba(255, 255, 255, 225);
                color: #20242a;
                border: 1px solid rgba(40, 45, 52, 70);
                border-radius: 6px;
                font-family: "Yu Gothic UI", "Meiryo", sans-serif;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(246, 250, 255, 245);
            }
            """
        )

    def _setup_timers(self) -> None:
        """状態更新とランダム行動のタイマーを用意します。"""
        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self._tick_state)
        self.state_timer.start(60 * 1000)

        self.action_timer = QTimer(self)
        self.action_timer.timeout.connect(self._try_random_action)
        self._schedule_next_random_action()

    def _setup_shortcut_fallback(self) -> None:
        """
        グローバルホットキー登録に失敗した場合の保険です。
        ウィンドウにフォーカスがある時だけ Ctrl+Shift+D が効きます。
        """
        self.shortcut = QShortcut(QKeySequence("Ctrl+Shift+D"), self)
        self.shortcut.activated.connect(self.toggle_pause)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._move_to_bottom_right()
        self._register_global_hotkey()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._unregister_global_hotkey()
        self.bubble.close()
        if self.input_dialog:
            self.input_dialog.close()
        super().closeEvent(event)

    def nativeEvent(self, event_type, message):  # noqa: N802
        """
        Windows のグローバルホットキーを受け取ります。
        Ctrl+Shift+D で一時停止モードを切り替えます。
        """
        if event_type not in ("windows_generic_MSG", b"windows_generic_MSG"):
            return False, 0

        msg = ctypes.wintypes.MSG.from_address(int(message))
        if msg.message == self.WM_HOTKEY and msg.wParam == self.HOTKEY_ID:
            self.toggle_pause()
            return True, 0

        return False, 0

    def mousePressEvent(self, event) -> None:  # noqa: N802
        """左クリックの開始位置を覚えて、ドラッグ移動できるようにします。"""
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        """クリックしたまま動かした時、ウィンドウを移動します。"""
        if event.buttons() & Qt.LeftButton and self.drag_start_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_start_position)
            self._move_bubble_near_character()
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        """
        ほとんど動かさず離した場合はクリック反応を出します。
        ドラッグ後は反応しないようにしています。
        """
        if event.button() != Qt.LeftButton:
            return

        if self.drag_start_position is None:
            return

        current_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        moved_distance = (current_position - self.drag_start_position).manhattanLength()
        self.drag_start_position = None

        if moved_distance < 8 and not self.talk_button.geometry().contains(event.position().toPoint()):
            self._react_to_click()

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        """右クリックメニューから一時停止や終了を選べるようにします。"""
        menu = QMenu(self)
        pause_label = "再開" if self.paused else "一時停止"
        pause_action = QAction(pause_label, self)
        talk_action = QAction("今の気分を話す", self)
        quit_action = QAction("終了", self)

        pause_action.triggered.connect(self.toggle_pause)
        talk_action.triggered.connect(self._open_emotion_input)
        quit_action.triggered.connect(QApplication.quit)

        menu.addAction(talk_action)
        menu.addAction(pause_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        menu.exec(event.globalPos())

    def _tick_state(self) -> None:
        """時間経過による状態変化を反映して、画像も更新します。"""
        self.state_service.update_for_time_passage()
        if self._inactive_seconds() > 25 * 60:
            self.state_service.set_mood("sleepy")
        self._update_character_image()

    def _schedule_next_random_action(self) -> None:
        """作業状況と深夜帯を考慮して、次の行動チェックを予約します。"""
        if self.action_manager.activity_monitor.is_quiet_hours():
            seconds = random.randint(180, 360)
        elif self.action_manager.activity_monitor.idle_seconds() < 20:
            seconds = random.randint(150, 300)
        else:
            seconds = random.randint(60, 180)

        self.action_timer.start(seconds * 1000)

    def _try_random_action(self) -> None:
        """一時停止中でなければ、一定確率でランダム行動を実行します。"""
        if not self.paused:
            action = self.action_manager.choose_action(self.state)
            if action:
                self._perform_random_action(action)

        self._schedule_next_random_action()

    def _perform_random_action(self, action: RandomAction) -> None:
        """ランダム行動をUIへ反映します。"""
        self.action_manager.is_acting = True

        if action.mood:
            self.state_service.set_mood(action.mood)
            self._update_character_image()

        if action.move_to_edge:
            self._small_move_near_edge()

        self._show_bubble(action.line, action.duration_ms)
        self.state_service.mark_talked()
        QTimer.singleShot(action.duration_ms, self._finish_random_action)

    def _finish_random_action(self) -> None:
        """行動中フラグを戻し、基本状態に合わせて画像を戻します。"""
        self.action_manager.is_acting = False
        self.state_service.update_mood_from_friendship()
        self.state_service.save()
        self._update_character_image()

    def _react_to_click(self) -> None:
        """クリック時のランダム反応と、友情度上昇処理を行います。"""
        self.state_service.mark_interaction()
        increased = random.random() < 0.35
        if increased:
            self.state_service.increase_friendship()
        else:
            self.state_service.update_mood_from_friendship()
            self.state_service.save()

        text = self.dialogue.random_click_line(self.state.friendship)
        if increased:
            text = f"{text}\n友情度 +1"

        self._update_character_image()
        self._show_bubble(text)
        self.state_service.mark_talked()

    def _open_emotion_input(self) -> None:
        """小さな入力ウィンドウを開きます。"""
        if self.input_dialog is None:
            self.input_dialog = EmotionInputDialog(self)
            self.input_dialog.submitted.connect(self._handle_emotion_text)

        self.input_dialog.move(self.x() - 320, self.y())
        self.input_dialog.show()
        self.input_dialog.raise_()
        self.input_dialog.activateWindow()

    def _handle_emotion_text(self, text: str) -> None:
        """ユーザー入力を分類し、状態と返答へ反映します。"""
        emotion = self.emotion_classifier.classify(text)
        self.state_service.apply_emotion(emotion)
        reply = self.ai_dialogue.generate_reply(text, emotion)

        if emotion in {"sad", "stressed", "angry"}:
            self.state_service.set_mood("sad")
        elif emotion == "tired":
            self.state_service.set_mood("sleepy")
        elif emotion == "happy":
            self.state_service.set_mood("happy")

        self._update_character_image()
        self._show_bubble(reply, 5500)
        self.state_service.mark_talked()

    def toggle_pause(self) -> None:
        """Ctrl+Shift+D から呼ばれる一時停止モードの切り替えです。"""
        self.paused = not self.paused
        if self.paused:
            self.action_timer.stop()
            self._show_bubble(self.dialogue.random_paused_line())
        else:
            self._schedule_next_random_action()
            self._show_bubble(self.dialogue.random_resumed_line())

    def _update_character_image(self) -> None:
        """現在の mood に応じてキャラクター画像を切り替えます。"""
        mood = self.state.mood if self.state.mood in {"normal", "happy", "sad", "sleepy"} else "normal"
        image_candidates = [
            ASSETS_DIR / f"character_{mood}.png",
            ASSETS_DIR / f"{mood}.png",
            ASSETS_DIR / "character.png",
        ]
        pixmap = next((QPixmap(str(path)) for path in image_candidates if path.exists()), QPixmap())

        if pixmap.isNull():
            self._show_placeholder_character(mood)
            return

        self.character_label.setText("")
        self.character_label.setStyleSheet("background: transparent;")
        scaled = pixmap.scaled(
            self.character_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )
        self.character_label.setPixmap(scaled)

    def _show_placeholder_character(self, mood: str) -> None:
        """画像がない場合の仮表示です。"""
        colors = {
            "normal": "#f8fbff",
            "happy": "#fff4c7",
            "sad": "#dfe9ff",
            "sleepy": "#ece7ff",
        }
        self.character_label.setPixmap(QPixmap())
        self.character_label.setText(mood)
        self.character_label.setStyleSheet(
            f"""
            QLabel {{
                background: {colors.get(mood, "#f8fbff")};
                color: #2b2f36;
                border: 2px solid rgba(43, 47, 54, 90);
                border-radius: 80px;
                font-family: "Yu Gothic UI", "Meiryo", sans-serif;
                font-size: 18px;
                font-weight: bold;
            }}
            """
        )

    def _show_bubble(self, text: str, duration_ms: int = 4000) -> None:
        """キャラクターの左上付近に吹き出しを表示します。"""
        x, y = self._bubble_position()
        self.bubble.show_message(text, x, y, duration_ms)

    def _move_bubble_near_character(self) -> None:
        """ドラッグ中に吹き出しが出ている場合、キャラクターに追従させます。"""
        if self.bubble.isVisible():
            x, y = self._bubble_position()
            self.bubble.move(x, y)

    def _bubble_position(self) -> tuple[int, int]:
        """画面外にはみ出しにくい吹き出し位置を計算します。"""
        screen = self.screen()
        available = screen.availableGeometry() if screen else self.geometry()

        bubble_width = max(self.bubble.width(), 220)
        x = self.x() - bubble_width + 20
        y = self.y() - 20

        x = max(available.left() + 8, x)
        y = max(available.top() + 8, y)
        return x, y

    def _move_to_bottom_right(self) -> None:
        """起動時に利用可能な画面領域の右下へ移動します。"""
        screen = self.screen()
        if screen is None:
            return

        available = screen.availableGeometry()
        margin = 24
        x = available.right() - self.width() - margin
        y = available.bottom() - self.height() - margin
        self.move(x, y)

    def _small_move_near_edge(self) -> None:
        """画面端で少しだけ位置を変える行動です。"""
        screen = self.screen()
        if screen is None:
            return

        available = screen.availableGeometry()
        new_x = min(available.right() - self.width() - 8, max(available.left() + 8, self.x() + random.choice([-18, 18])))
        new_y = min(available.bottom() - self.height() - 8, max(available.top() + 8, self.y() + random.choice([-8, 8])))
        self.move(new_x, new_y)

    def _inactive_seconds(self) -> float:
        """ユーザーの無操作秒数を取得します。"""
        return self.action_manager.activity_monitor.idle_seconds()

    def _register_global_hotkey(self) -> None:
        """Windows の RegisterHotKey API で Ctrl+Shift+D を登録します。"""
        if self.hotkey_registered:
            return

        try:
            user32 = ctypes.windll.user32
            hwnd = int(self.winId())
            self.hotkey_registered = bool(
                user32.RegisterHotKey(
                    hwnd,
                    self.HOTKEY_ID,
                    self.MOD_CONTROL | self.MOD_SHIFT,
                    self.VK_D,
                )
            )
        except Exception:
            self.hotkey_registered = False

    def _unregister_global_hotkey(self) -> None:
        """アプリ終了時に登録したグローバルホットキーを解除します。"""
        if not self.hotkey_registered:
            return

        try:
            ctypes.windll.user32.UnregisterHotKey(int(self.winId()), self.HOTKEY_ID)
        finally:
            self.hotkey_registered = False
