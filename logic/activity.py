import ctypes
import ctypes.wintypes
from datetime import datetime


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.UINT),
        ("dwTime", ctypes.wintypes.DWORD),
    ]


class UserActivityMonitor:
    """Windows の最終入力時刻から、ユーザーの無操作時間を取得します。"""

    def idle_seconds(self) -> float:
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)

        try:
            if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
                return 0.0
            elapsed_ms = ctypes.windll.kernel32.GetTickCount() - info.dwTime
            return max(0.0, elapsed_ms / 1000.0)
        except Exception:
            return 0.0

    def is_quiet_hours(self) -> bool:
        """深夜帯は静かなモードにします。"""
        hour = datetime.now().hour
        return hour >= 23 or hour < 7

    def conversation_probability(self, base_probability: float = 0.35) -> float:
        """
        作業状況に応じて話しかけ確率を調整します。

        入力が頻繁にある時は作業中とみなし、話しかけ頻度を下げます。
        """
        if self.is_quiet_hours():
            return base_probability * 0.25

        idle_seconds = self.idle_seconds()
        if idle_seconds < 20:
            return base_probability * 0.35
        if idle_seconds > 180:
            return min(0.85, base_probability * 1.6)
        return base_probability
