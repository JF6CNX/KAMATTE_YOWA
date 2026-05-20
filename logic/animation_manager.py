from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap


class AnimationManager(QObject):
    """Handles looping frame animations with static-image fallback."""

    frame_changed = Signal(QPixmap)
    placeholder_requested = Signal(str)

    def __init__(self, assets_dir: Path, character_size: tuple[int, int]) -> None:
        super().__init__()
        self.assets_dir = assets_dir
        self.character_size = character_size
        self.current_mood = "normal"
        self.current_animation = "idle"
        self.temporary_animation: str | None = None
        self.frames: list[Path] = []
        self.frame_index = 0
        self.loop_temporary = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._advance_frame)
        self.timer.setInterval(180)

    def set_mood(self, mood: str) -> None:
        self.current_mood = mood
        if self.temporary_animation is None:
            self._apply_animation(self._animation_name_for_mood(mood))

    def play_action(self, animation_name: str, loop: bool = False) -> None:
        self.temporary_animation = animation_name
        self.loop_temporary = loop
        self._apply_animation(animation_name)

    def clear_action(self) -> None:
        self.temporary_animation = None
        self.loop_temporary = False
        self._apply_animation(self._animation_name_for_mood(self.current_mood))

    def maybe_play_tail_wag(self, probability: float = 0.2) -> bool:
        import random

        if self.temporary_animation is not None:
            return False
        if random.random() >= probability:
            return False
        if not self._frame_paths("tail_wag"):
            return False
        self.play_action("tail_wag", loop=False)
        return True

    def _animation_name_for_mood(self, mood: str) -> str:
        mapping = {
            "happy": "happy",
            "sleepy": "sleepy",
            "sad": "idle",
            "normal": "idle",
        }
        return mapping.get(mood, "idle")

    def _apply_animation(self, animation_name: str) -> None:
        self.current_animation = animation_name
        self.frames = self._frame_paths(animation_name)
        self.frame_index = 0

        if not self.frames:
            self.timer.stop()
            self._emit_static_pixmap()
            return

        self._emit_frame(self.frames[0])
        if len(self.frames) > 1:
            self.timer.start()
        else:
            self.timer.stop()
            if self.temporary_animation and not self.loop_temporary:
                self.clear_action()

    def _advance_frame(self) -> None:
        if not self.frames:
            self.timer.stop()
            return

        self.frame_index += 1
        if self.frame_index >= len(self.frames):
            if self.temporary_animation and not self.loop_temporary:
                self.clear_action()
                return
            self.frame_index = 0

        self._emit_frame(self.frames[self.frame_index])

    def _frame_paths(self, animation_name: str) -> list[Path]:
        frame_dir = self.assets_dir / "animations" / animation_name
        if not frame_dir.exists():
            return []
        return sorted(
            [path for path in frame_dir.iterdir() if path.is_file() and path.suffix.lower() == ".png"],
            key=lambda path: path.name.lower(),
        )

    def _emit_static_pixmap(self) -> None:
        mood = self.current_mood if self.current_mood in {"normal", "happy", "sad", "sleepy"} else "normal"
        candidates = [
            self.assets_dir / f"character_{mood}.png",
            self.assets_dir / f"{mood}.png",
            self.assets_dir / "character.png",
        ]

        for path in candidates:
            if not path.exists():
                continue
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                continue
            self.frame_changed.emit(self._scaled(pixmap))
            return

        self.placeholder_requested.emit(mood)

    def _emit_frame(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._emit_static_pixmap()
            return
        self.frame_changed.emit(self._scaled(pixmap))

    def _scaled(self, pixmap: QPixmap) -> QPixmap:
        width, height = self.character_size
        return pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
