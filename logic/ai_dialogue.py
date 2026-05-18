import os
from pathlib import Path

from logic.emotion import EmotionReplyTemplate
from logic.prompts import CHARACTER_PROMPT
from logic.state import CharacterStateService


APP_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = APP_ROOT / ".env"

def load_env_file(path: Path = ENV_PATH) -> None:
    """python-dotenv がなくても .env から最低限の環境変数を読みます。"""
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class AIDialogueService:
    """OpenAI API を使った会話生成です。失敗時はテンプレ返答へ戻します。"""

    def __init__(self, state_service: CharacterStateService) -> None:
        self.state_service = state_service
        self.template = EmotionReplyTemplate()
        load_env_file()

    def generate_reply(self, user_text: str, emotion: str) -> str:
        fallback = self.template.reply_for(emotion)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return fallback

        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            response = client.responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
                input=[
                    {
                        "role": "system",
                        "content": self._build_system_prompt(emotion),
                    },
                    {
                        "role": "user",
                        "content": user_text,
                    },
                ],
            )
            text = getattr(response, "output_text", "").strip()
            return text or fallback
        except Exception:
            return fallback

    def _build_system_prompt(self, emotion: str) -> str:
        state = self.state_service.state
        if state.friendship >= 20:
            tone = "かなり親しい。少しくだけた、あたたかい口調。"
        elif state.friendship >= 8:
            tone = "少し親しい。丁寧すぎず、やさしい口調。"
        else:
            tone = "まだ距離がある。控えめで礼儀正しい口調。"

        return (
            f"{CHARACTER_PROMPT}\n"
            f"現在の状態: {self.state_service.as_prompt_context()}\n"
            f"ユーザー感情分類: {emotion}\n"
            f"口調ルール: {tone}\n"
            f"mood={state.mood} を反映して返答してください。"
        )
