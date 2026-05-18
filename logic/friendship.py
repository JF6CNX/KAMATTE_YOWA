import random

from data.database import FriendshipRepository


class FriendshipService:
    """友情度を管理します。値は SQLite に保存されます。"""

    def __init__(self, repository: FriendshipRepository | None = None) -> None:
        self.repository = repository or FriendshipRepository()
        self.friendship = self.repository.load_friendship()

    def maybe_increase_on_click(self) -> bool:
        """
        クリック時に一定確率で友情度を上げます。

        戻り値が True なら、今回のクリックで友情度が上がったという意味です。
        """
        increase_chance = 0.35
        if random.random() >= increase_chance:
            return False

        self.friendship += 1
        self.repository.save_friendship(self.friendship)
        return True
