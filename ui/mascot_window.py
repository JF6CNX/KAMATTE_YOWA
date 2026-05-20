from __future__ import annotations

import ctypes
import ctypes.wintypes
import random
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QPushButton, QWidget

from logic.actions import RandomAction, RandomActionManager
from logic.ai_dialogue import AIDialogueService
from logic.animation_manager import AnimationManager
from logic.conversation_context import ConversationContextManager
from logic.conversation_log import ConversationLogManager
from logic.dialogue import DialogueManager
from logic.emotion import EmotionClassifier
from logic.state import CharacterStateService
from logic.trivia import TriviaManager
from ui.emotion_input_dialog import EmotionInputDialog
from ui.speech_bubble import SpeechBubble


APP_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = APP_ROOT / "assets"


class MascotWindow(QWidget):
    """Desktop mascot window that coordinates UI, dialogue, logging, and animation."""

    WM_HOTKEY = 0x0312
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    VK_D = 0x44
    HOTKEY_ID = 1001

    def __init__(self) -> None:
        super().__init__()
        self.state_service = CharacterStateService()
        self.dialogue = DialogueManager()
        self.trivia = TriviaManager()
        self.action_manager = RandomActionManager()
        self.emotion_classifier = EmotionClassifier()
        self.ai_dialogue = AIDialogueService(self.state_service)
        self.conversation_log = ConversationLogManager()
        self.conversation_context = ConversationContextManager()
        self.bubble = SpeechBubble()
        self.animation_manager = AnimationManager(ASSETS_DIR, (160, 160))
        self.input_dialog: EmotionInputDialog | None = None

        self.drag_start_position: QPoint | None = None
        self.paused = False
        self.hotkey_registered = False

        self._setup_window()
        self._setup_character()
        self._setup_animation()
        self._setup_timers()
        self._setup_shortcut_fallback()
        self._update_character_image()

    @property
    def state(self):
        return self.state_service.state

    def _setup_window(self) -> None:
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(172, 194)

    def _setup_character(self) -> None:
        self.character_label = QLabel(self)
        self.character_label.setAlignment(Qt.AlignCenter)
        self.character_label.setGeometry(6, 0, 160, 160)

        self.talk_button = QPushButton("気持ちを話す", self)
        self.talk_button.setGeometry(18, 162, 136, 28)
        self.talk_button.clicked.connect(self._open_emotion_input)
        self.talk_button.setStyleSheet(
            """
            QPushButton {
                background: rgba(255, 255, 255, 245);
                color: #20242a;
                border: 1px solid rgba(40, 45, 52, 70);
                border-radius: 6px;
                font-family: "Yu Gothic UI", "Meiryo", sans-serif;
                font-size: 12px;
            }
            QPushButton:hover {
                background: rgba(246, 250, 255, 255);
            }
            """
        )

    def _setup_animation(self) -> None:
        self.animation_manager.frame_changed.connect(self._set_character_pixmap)
        self.animation_manager.placeholder_requested.connect(self._show_placeholder_character)

    def _setup_timers(self) -> None:
        self.state_timer = QTimer(self)
        self.state_timer.timeout.connect(self._tick_state)
        self.state_timer.start(60 * 1000)

        self.action_timer = QTimer(self)
        self.action_timer.timeout.connect(self._try_random_action)
        self._schedule_next_random_action()

        self.trivia_timer = QTimer(self)
        self.trivia_timer.timeout.connect(self._maybe_share_trivia)
        self._schedule_next_trivia()

    def _setup_shortcut_fallback(self) -> None:
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
        if event_type not in ("windows_generic_MSG", b"windows_generic_MSG"):
            return False, 0

        msg = ctypes.wintypes.MSG.from_address(int(message))
        if msg.message == self.WM_HOTKEY and msg.wParam == self.HOTKEY_ID:
            self.toggle_pause()
            return True, 0

        return False, 0

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.drag_start_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if event.buttons() & Qt.LeftButton and self.drag_start_position is not None:
            self.move(event.globalPosition().toPoint() - self.drag_start_position)
            self._move_bubble_near_character()
            event.accept()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
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
        menu = QMenu(self)
        pause_label = "再開" if self.paused else "一時停止"
        pause_action = QAction(pause_label, self)
        talk_action = QAction("気持ちを話す", self)
        copy_log_action = QAction("会話ログをコピー", self)
        quit_action = QAction("終了", self)

        pause_action.triggered.connect(self.toggle_pause)
        talk_action.triggered.connect(self._open_emotion_input)
        copy_log_action.triggered.connect(self._copy_conversation_log)
        quit_action.triggered.connect(QApplication.quit)

        menu.addAction(talk_action)
        menu.addAction(copy_log_action)
        menu.addAction(pause_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        menu.exec(event.globalPos())

    def _tick_state(self) -> None:
        self.state_service.update_for_time_passage()
        if self._inactive_seconds() > 25 * 60:
            self.state_service.set_mood("sleepy")
        self._update_character_image()

    def _schedule_next_random_action(self) -> None:
        if self.action_manager.activity_monitor.is_quiet_hours():
            seconds = random.randint(180, 360)
        elif self.action_manager.activity_monitor.idle_seconds() < 20:
            seconds = random.randint(150, 300)
        else:
            seconds = random.randint(60, 180)
        self.action_timer.start(seconds * 1000)

    def _schedule_next_trivia(self) -> None:
        seconds = random.randint(480, 900)
        self.trivia_timer.start(seconds * 1000)

    def _try_random_action(self) -> None:
        if not self.paused:
            action = self.action_manager.choose_action(self.state)
            if action:
                self._perform_random_action(action)
            else:
                self.animation_manager.maybe_play_tail_wag(0.14)

        self._schedule_next_random_action()

    def _perform_random_action(self, action: RandomAction) -> None:
        self.action_manager.is_acting = True

        if action.mood:
            self.state_service.set_mood(action.mood)

        self._update_character_image()
        if action.animation:
            self.animation_manager.play_action(action.animation, loop=False)

        if action.move_to_edge:
            self._small_move_near_edge()

        line = action.line or self.dialogue.random_idle_line(self.state.friendship)
        self._show_character_message(line, action.duration_ms, speaker="character")
        self.state_service.mark_talked()
        QTimer.singleShot(action.duration_ms, self._finish_random_action)

    def _finish_random_action(self) -> None:
        self.action_manager.is_acting = False
        self.animation_manager.clear_action()
        self.state_service.update_mood_from_friendship()
        self.state_service.save()
        self._update_character_image()

    def _react_to_click(self) -> None:
        self.state_service.mark_interaction()
        increased = random.random() < 0.35
        if increased:
            self.state_service.increase_friendship()
            self.animation_manager.play_action("happy", loop=False)
        else:
            self.state_service.update_mood_from_friendship()
            self.state_service.save()
            self.animation_manager.maybe_play_tail_wag(0.35)

        text = self.dialogue.random_click_line(self.state.friendship)
        if increased:
            text = f"{text}\n親密度 +1"

        self._update_character_image()
        self._show_character_message(text)
        self.state_service.mark_talked()

    def _open_emotion_input(self) -> None:
        if self.input_dialog is None:
            self.input_dialog = EmotionInputDialog(self)
            self.input_dialog.submitted.connect(self._handle_emotion_text)

        self.input_dialog.move(self.x() - 320, self.y())
        self.input_dialog.show()
        self.input_dialog.raise_()
        self.input_dialog.activateWindow()

    def _handle_emotion_text(self, text: str) -> None:
        self.conversation_log.add_entry("user", text)
        analysis = self.emotion_classifier.analyze(text)
        emotion = analysis.primary
        self.state_service.apply_emotion(emotion)
        self.conversation_context.add_user_message(text, emotion)
        reply = self.ai_dialogue.generate_reply(
            text,
            emotion,
            self.conversation_log.recent_log_text(limit=12),
            self.conversation_context.recent_context_text(limit=5),
        )
        self.conversation_log.add_entry("ai", reply)
        self.conversation_context.add_ai_reply(reply)

        if emotion in {"sad", "stressed", "angry", "anxious", "lonely", "empty", "socially_tired", "overstimulated", "conflicted"}:
            self.state_service.set_mood("sad")
        elif emotion == "tired":
            self.state_service.set_mood("sleepy")
        elif emotion in {"happy", "relieved"}:
            self.state_service.set_mood("happy")
            self.animation_manager.play_action("happy", loop=False)

        self._update_character_image()
        self._show_bubble(reply, 5500)
        self.state_service.mark_talked()

    def _maybe_share_trivia(self) -> None:
        if not self.paused and not self.action_manager.is_acting:
            line = self.trivia.maybe_pick_line(
                self.state,
                self.paused,
                recent_emotions=self.conversation_context.recent_emotions(limit=4),
            )
            if line:
                self.animation_manager.maybe_play_tail_wag(0.25)
                self._show_character_message(line, 5000, speaker="trivia")
                self.state_service.mark_talked()
        self._schedule_next_trivia()

    def _copy_conversation_log(self) -> None:
        text = self.conversation_log.recent_log_text()
        if not text:
            text = "会話ログはまだありません。"
        QGuiApplication.clipboard().setText(text)
        self._show_bubble("直近の会話ログをコピーしたよ……", 2800)

    def toggle_pause(self) -> None:
        self.paused = not self.paused
        if self.paused:
            self.action_timer.stop()
            self.trivia_timer.stop()
            self._show_character_message(self.dialogue.random_paused_line())
        else:
            self._schedule_next_random_action()
            self._schedule_next_trivia()
            self._show_character_message(self.dialogue.random_resumed_line())

    def _update_character_image(self) -> None:
        mood = self.state.mood if self.state.mood in {"normal", "happy", "sad", "sleepy"} else "normal"
        self.animation_manager.set_mood(mood)

    def _set_character_pixmap(self, pixmap: QPixmap) -> None:
        self.character_label.setText("")
        self.character_label.setStyleSheet("background: transparent;")
        self.character_label.setPixmap(pixmap)

    def _show_placeholder_character(self, mood: str) -> None:
        colors = {
            "normal": "#f8fbff",
            "happy": "#fff4c7",
            "sad": "#dfe9ff",
            "sleepy": "#ece7ff",
        }
        self.character_label.setPixmap(QPixmap())
        self.character_label.setText("よわ")
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

    def _show_character_message(self, text: str, duration_ms: int = 4000, speaker: str = "character") -> None:
        self.conversation_log.add_entry(speaker, text)
        self.ai_dialogue.recent_responses.remember(text)
        self.dialogue.remember(text)
        self._show_bubble(text, duration_ms)

    def _show_bubble(self, text: str, duration_ms: int = 4000) -> None:
        self.bubble.show_message(text, self._bubble_anchor_rect(), self._available_geometry(), duration_ms)

    def _move_bubble_near_character(self) -> None:
        self.bubble.reposition(self._bubble_anchor_rect(), self._available_geometry())

    def _bubble_anchor_rect(self) -> QRect:
        top_left = self.mapToGlobal(self.character_label.geometry().topLeft())
        return QRect(top_left, self.character_label.size())

    def _available_geometry(self) -> QRect:
        screen = self.screen()
        return screen.availableGeometry() if screen else self.geometry()

    def _move_to_bottom_right(self) -> None:
        screen = self.screen()
        if screen is None:
            return

        available = screen.availableGeometry()
        margin = 24
        x = available.right() - self.width() - margin
        y = available.bottom() - self.height() - margin
        self.move(x, y)

    def _small_move_near_edge(self) -> None:
        screen = self.screen()
        if screen is None:
            return

        available = screen.availableGeometry()
        new_x = min(available.right() - self.width() - 8, max(available.left() + 8, self.x() + random.choice([-18, 18])))
        new_y = min(available.bottom() - self.height() - 8, max(available.top() + 8, self.y() + random.choice([-8, 8])))
        self.move(new_x, new_y)
        self._move_bubble_near_character()

    def _inactive_seconds(self) -> float:
        return self.action_manager.activity_monitor.idle_seconds()

    def _register_global_hotkey(self) -> None:
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
        if not self.hotkey_registered:
            return

        try:
            ctypes.windll.user32.UnregisterHotKey(int(self.winId()), self.HOTKEY_ID)
        finally:
            self.hotkey_registered = False
