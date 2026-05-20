from __future__ import annotations

import json
import os
import re
from pathlib import Path

from logic.emotion import EmotionClassifier, EmotionReplyTemplate
from logic.persona_loader import PersonaRepository
from logic.prompts import CHARACTER_PROMPT
from logic.recent_responses import RecentResponseManager
from logic.state import CharacterStateService


APP_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = APP_ROOT / ".env"
TRIVIA_PATH = APP_ROOT / "dialogue_data" / "trivia.json"
SUPPORT_PATH = APP_ROOT / "dialogue_data" / "emotional_support.json"


def load_env_file(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


class AIDialogueService:
    """Generate yowa-style replies with context, variety, and light memory."""

    INTENT_RESPONSES = {
        "self_preference": [
            "よわは、きみとゆっくり話したいのだー！",
            "よわは、ここでいっしょにいるのが好きなのだ！",
            "よわは、のんびり見守っていたいのだー！",
        ],
        "abandonment_question": [
            "それはさみしいのだ。だから、いまここにいてほしいのだ！",
            "いなくなったら、よわはしょんぼりするのだ。まだいてほしいのだー！",
            "それはかなしいのだ。よわは、まだ話していたいのだ！",
        ],
        "daily_question": [
            "よわは、ここで見守ってたのだー！",
            "よわは、きみのことを気にしながら待ってたのだ！",
            "よわは、のんびりしながらここにいたのだー！",
        ],
        "scary_dream": [
            "それはこわかったのだ。もう夢は終わったのだ。少し落ち着くのだ！",
            "こわい夢はいやなのだ。いまは起きてるから大丈夫なのだ！",
            "それはびっくりなのだ。よわがとなりで落ち着く係をするのだー！",
        ],
        "silence_anxiety": [
            "静かすぎるとそわそわする時あるのだ。よわがここにいるのだー！",
            "しんとしすぎると不安になるの、わかるのだ。少しだけ声を出すのだ！",
            "静かすぎる空気って落ち着かないのだ。よわが話し相手になるのだー！",
        ],
        "kindness_question": [
            "きみにやさしくしたいからなのだー！",
            "よわは、やさしくいたいのだ！",
            "そうしたい気分なのだ。やさしいほうが落ち着くのだー！",
        ],
        "praise_request": [
            "ここまで来ただけでもえらいのだー！",
            "ちゃんと話してくれたの、えらいのだ！",
            "きょうを進んでるだけでじゅうぶんえらいのだー！",
        ],
        "failure": [
            "だめだった日もあるのだ。また次をちいさくやればいいのだ！",
            "うまくいかない時はあるのだ。きみまでだめになるわけじゃないのだ！",
            "だめだったって言えるの、ちゃんとえらいのだ。少し休むのだー！",
        ],
        "dawn_exhaustion": [
            "もう朝なのだ……ってなるやつなのだ。かなりおつかれなのだ！",
            "朝まで来ちゃったのだ。今日はやさしめにするのだー！",
            "もう朝なのはしんどいのだ。少しでも休める形にするのだ！",
        ],
        "couldnt_smile": [
            "笑えない日もあるのだ。今日は無理に明るくしなくていいのだ！",
            "うまく笑えない時はあるのだ。気持ちが追いつくまで待つのだー！",
            "笑えなかった日でも、きみがだめってことじゃないのだ！",
        ],
        "tired_but_tasks_left": [
            "つかれてるのに、まだ残ってるのは大変なのだ。ひとつだけ片づける気持ちでいくのだ！",
            "おつかれなのだ。でも残りがあるなら、いちばん小さいのからいくのだー！",
            "つかれてる日は、全部じゃなくてひとつでいいのだ！",
        ],
        "avoid_people": [
            "今日は人と話したくない日なのだ。静かめにしてていいのだ！",
            "そういう日はあるのだ。無理にしゃべらなくていいのだー！",
            "きょうはひとりモードなのだ。そっとしておくのもだいじなのだ！",
        ],
        "reasonless_pain": [
            "理由が見えなくてもしんどいものはしんどいのだ。まずは楽な姿勢になるのだ！",
            "わけがわからないしんどさもあるのだ。いまは自分をせめないのだー！",
            "理由がなく見えても、つらいのは本当なのだ。少しゆるめるのだ！",
        ],
        "sleepy_but_awake": [
            "寝たいのに頭だけ起きてるのはしんどいのだ。明るさをへらして、静かにするのだ！",
            "からだは休みたいのに頭が起きてる感じなのだ。あせらず目を休めるのだー！",
            "ねむいのに眠れないやつなのだ。今日はゆっくりモードでいくのだ！",
        ],
        "frozen_pressure": [
            "がんばらなきゃって思うほど動けなくなる時もあるのだ。まず深呼吸だけするのだ！",
            "気持ちだけ急いで、からだが止まる日もあるのだ。ひとつだけやるのだー！",
            "動けない時は、ちいさい動きからでいいのだ。立つだけでもえらいのだ！",
        ],
        "self_doubt": [
            "自分だけだめな気がする日はあるのだ。でもほんとにだめって決まったわけじゃないのだ！",
            "比べるとしんどくなるのだ。今日は自分をいじめないのだー！",
            "だめな感じがしても、きみまでだめになるわけじゃないのだ！",
        ],
        "small_happy": [
            "ちょっとだけでもうれしいのは、ちゃんといいことなのだー！",
            "それはいいのだ！ そのちいさいうれしさ、大事なのだ！",
            "少しでもうれしかったなら、今日はそこが光ってるのだー！",
        ],
        "doing_better": [
            "ちょっと調子いいのはうれしいのだ！ この感じを大事にするのだー！",
            "それはいい流れなのだ！ 無理しすぎずそのままいくのだ！",
            "調子がいい日は、すこしだけ前にいけるのだー！",
        ],
        "companionship": [
            "となりにいるのだー！",
            "ずっとそばにいるのだ！",
            "よわはここにいるのだー！",
        ],
        "attachment": [
            "よわはここにいるのだ！ ひとりにしないのだー！",
            "ちゃんといるのだ。いっしょにいるのだー！",
            "よわを呼んでくれてよかったのだ。ここにいるのだ！",
        ],
        "chat_request": [
            "よわと話す時間なのだー！",
            "もちろん話すのだ！",
            "いるのだー！ なに話すのだ？",
        ],
        "checkin": [
            "よわはここにいるのだ！ きみは元気なのだ？",
            "ぼちぼち元気なのだー！",
            "よわは元気なのだ！ そっちはどうなのだ？",
        ],
        "callout": [
            "いるのだー！",
            "ちゃんといるのだ！",
            "よんだのだ？ よわはここなのだー！",
        ],
        "small_talk_invite": [
            "話すのだー！ ゆっくりいくのだ！",
            "少しだけでも、いっしょに話すのだー！",
            "もちろん話すのだ！ よわはうれしいのだ！",
        ],
        "lonely_question": [
            "ちょっとさみしい時もあるのだ。でも、きみが呼ぶとうれしいのだ！",
            "さみしい気分になる時はあるのだ。だから会えるとうれしいのだー！",
            "よわも、ひとりだとしゅんとする時があるのだ！",
        ],
        "insomnia": [
            "朝まで眠れないのはつらいのだ。今日は無理せずゆるむのだー！",
            "それはかなりねむねむ案件なのだ。できるだけ静かに休むのだ！",
            "朝なのに寝れてないのはしんどいのだ。今日はやさしめにいくのだー！",
        ],
        "couldnt_do_anything": [
            "なにもできない日もあるのだ。今日は生きてるだけで十分なのだ！",
            "そういう日もあるのだ。できなかった日でも、きみはだめじゃないのだ！",
            "今日はおやすみ寄りの日だったのだ。またあとでいくのだー！",
        ],
        "thanks": [
            "どういたしましてなのだー！",
            "えへへ、うれしいのだ！",
            "そう言ってもらえてうれしいのだー！",
        ],
        "relief": [
            "少しでも安心できたならよかったのだー！",
            "ちょっと救われたなら、よわもうれしいのだ！",
            "その一息ぶん、ちゃんと大事なのだー！",
        ],
        "goodnight": [
            "おやすみなのだー！ いい夢みるのだ！",
            "ゆっくり休むのだー！ おやすみなのだ！",
            "おふとんでぬくぬくするのだー！ おやすみなのだ！",
        ],
        "stuck_pattern": [
            "ずっと同じ感じが続くと、じわじわしんどいのだ。今日はひとつだけ変えるのだ！",
            "同じ空気が続くと重たくなるのだ。少しだけ場所を変えるのだー！",
            "変わらない感じが続くのはつかれるのだ。ひと呼吸いれるのだ！",
        ],
        "weird_request": [
            "ラッコは寝る時に海藻を抱くことがあるんだって。かわいいのだ！",
            "ペンギンにも膝はあるんだって。見えないだけなのだ！",
            "コアラの指紋って、人の指紋とけっこう似てるらしいのだ！",
        ],
        "listen_request": [
            "わかったのだ。よわはちゃんと聞くのだ！",
            "うん、ここで聞いてるのだー！",
            "だいじょうぶなのだ。話してほしいのだ！",
        ],
        "quiet_observation": [
            "今日はちょっと静かめなのだー！",
            "静かな日なのだ。のんびりしてるのだー！",
            "そうなのだ。今日はしずしずモードなのだ！",
        ],
        "question_about_tone": [
            "よわはこういう喋り方なのだー！",
            "これがよわの喋り方なのだ！",
            "のだ口調で話してるのだー！",
        ],
        "gibberish": [
            "あわあわしてるのだ？ ちょっと落ち着くのだー！",
            "いっぱいになってそうなのだ。ひと呼吸するのだ！",
            "いまはぐるぐるかもなのだ。少しゆるめるのだー！",
        ],
        "self_harm": [
            "いまは安全をいちばんにするのだ。ひとりにならないで、誰かにつながるのだ。",
            "それはひとりで抱えないでほしいのだ。今すぐ近くの人に助けてって言うのだ。",
            "かなり危ない感じなのだ。すぐに身近な人か相談先につながってほしいのだ。",
        ],
    }

    def __init__(self, state_service: CharacterStateService) -> None:
        self.state_service = state_service
        self.template = EmotionReplyTemplate()
        self.persona = PersonaRepository()
        self.classifier = EmotionClassifier()
        self.recent_responses = RecentResponseManager(max_entries=14, similarity_threshold=0.83)
        self.trivia_lines = self._load_trivia_lines()
        self.support_replies = self._load_support_replies()
        load_env_file()

    def generate_reply(self, user_text: str, emotion: str, recent_log_text: str = "", context_text: str = "") -> str:
        fallback = self._fallback_reply(user_text, emotion, recent_log_text, context_text)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            reply = self._normalize_reply(fallback)
            self.recent_responses.remember(reply)
            return reply

        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key)
            response = client.responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
                input=[
                    {"role": "system", "content": self._build_system_prompt(emotion, recent_log_text, context_text)},
                    {"role": "user", "content": user_text},
                ],
            )
            text = getattr(response, "output_text", "").strip()
            reply = self._normalize_reply(text or fallback)
            if self.recent_responses.is_blocked(reply):
                reply = self._normalize_reply(fallback)
            self.recent_responses.remember(reply)
            return reply
        except Exception:
            reply = self._normalize_reply(fallback)
            self.recent_responses.remember(reply)
            return reply

    def _fallback_reply(self, user_text: str, emotion: str, recent_log_text: str = "", context_text: str = "") -> str:
        analysis = self.classifier.analyze(user_text)
        current_emotion = analysis.primary or emotion
        recent_entries = self._parse_recent_entries(recent_log_text)
        context_entries = self._parse_context_entries(context_text)

        intent = self._detect_intent(user_text)
        if not intent:
            intent = self._detect_contextual_intent(user_text, recent_entries, context_entries)

        if intent == "trivia_request" and self.trivia_lines:
            return self.recent_responses.choose(self.trivia_lines, self._seed(user_text))

        if intent in self.INTENT_RESPONSES:
            return self.recent_responses.choose(self.INTENT_RESPONSES[intent], self._seed(user_text))

        contextual = self._build_contextual_prefix(current_emotion, context_entries, analysis.summary)
        support_options = self.support_replies.get(current_emotion, [])
        if not support_options:
            support_options = self.template.REPLIES.get(current_emotion, self.template.REPLIES["stressed"])

        base = self.recent_responses.choose(support_options, self._seed(user_text))
        if contextual and contextual not in base:
            return f"{contextual} {base}"
        return base

    def _detect_intent(self, user_text: str) -> str | None:
        text = user_text.lower().strip()

        if "死にたい" in text:
            return "self_harm"
        if any(keyword in text for keyword in ("消えたい", "いなくなりたい")):
            return "self_harm"
        if any(keyword in text for keyword in ("静かすぎると不安", "静かすぎる", "不安になる")):
            return "silence_anxiety"
        if any(keyword in text for keyword in ("なんでそんなにやさしい", "なんでそんなに優しい", "そんなにやさしい")):
            return "kindness_question"
        if any(keyword in text for keyword in ("褒めて", "ほめて")):
            return "praise_request"
        if any(keyword in text for keyword in ("だめだった", "ダメだった", "うまくできなかった")):
            return "failure"
        if any(keyword in text for keyword in ("もう朝だ", "朝だ……", "朝だ...")):
            return "dawn_exhaustion"
        if any(keyword in text for keyword in ("うまく笑えなかった", "笑えなかった")):
            return "couldnt_smile"
        if any(keyword in text for keyword in ("つかれたけど", "疲れたけど", "まだやること残ってる", "まだやることが残ってる")):
            return "tired_but_tasks_left"
        if any(keyword in text for keyword in ("人と話したくない", "ひとと話したくない", "話したくない")):
            return "avoid_people"
        if any(keyword in text for keyword in ("しんどいけど理由がわからない", "理由がわからない", "理由わからない")):
            return "reasonless_pain"
        if any(keyword in text for keyword in ("よわはどうしたい", "どうしたいの", "どうしたい？", "どうしたい?")):
            return "self_preference"
        if any(keyword in text for keyword in ("もし私がいなくなったら", "もしわたしがいなくなったら", "いなくなったらどうする")):
            return "abandonment_question"
        if any(keyword in text for keyword in ("今日は何してた", "なにしてた", "何してた")):
            return "daily_question"
        if any(keyword in text for keyword in ("怖い夢", "こわい夢", "悪い夢", "こわいゆめ")):
            return "scary_dream"
        if any(keyword in text for keyword in ("寝たいのに頭だけ起きてる", "頭だけ起きてる", "寝たいのに")):
            return "sleepy_but_awake"
        if any(keyword in text for keyword in ("がんばらなきゃいけないのに動けない", "頑張らなきゃいけないのに動けない")):
            return "frozen_pressure"
        if any(keyword in text for keyword in ("自分だけダメ", "自分だけだめ", "自分だけ")):
            return "self_doubt"
        if any(keyword in text for keyword in ("ちょっとだけうれしかった", "うれしかった", "嬉しかった")):
            return "small_happy"
        if any(keyword in text for keyword in ("ちょっとだけ調子いい", "調子いい", "調子がいい")):
            return "doing_better"
        if any(keyword in text for keyword in ("ずっと一緒にいて", "そばにいて", "ずっといて")):
            return "companionship"
        if any(keyword in text for keyword in ("よわしかいない", "きみがいないと", "よわがいないと")):
            return "attachment"
        if any(keyword in text for keyword in ("少しだけ話そ", "すこしだけ話そ", "少しだけ話そう", "すこしだけ話そう")):
            return "small_talk_invite"
        if any(keyword in text for keyword in ("なんか話して", "話して", "しゃべって")):
            return "chat_request"
        if any(keyword in text for keyword in ("豆知識", "まめちしき", "トリビア")):
            return "trivia_request"
        if any(keyword in text for keyword in ("元気？", "元気?", "げんき？", "げんき?")):
            return "checkin"
        if any(keyword in text for keyword in ("よわって寂しい", "よわってさみしい", "寂しい？", "さみしい？")):
            return "lonely_question"
        if any(keyword in text for keyword in ("もう朝なのに寝れてない", "朝なのに寝れてない", "寝れてない", "眠れてない", "ねれてない")):
            return "insomnia"
        if any(keyword in text for keyword in ("今日はなにもできなかった", "今日は何もできなかった", "なにもできなかった", "何もできなかった")):
            return "couldnt_do_anything"
        if any(keyword in text for keyword in ("ありがとう", "ありがと", "助かった")):
            return "thanks"
        if any(keyword in text for keyword in ("安心した", "救われた")):
            return "relief"
        if any(keyword in text for keyword in ("おやすみ", "寝るね", "ねるね")):
            return "goodnight"
        if any(keyword in text for keyword in ("最近ずっと同じ感じ", "ずっと同じ感じ", "同じ感じ")):
            return "stuck_pattern"
        if any(keyword in text for keyword in ("変なこと言って", "変なこと", "へんなこと")):
            return "weird_request"
        if any(keyword in text for keyword in ("返事しなくてもいいから聞いて", "聞いて", "きいて")):
            return "listen_request"
        if any(keyword in text for keyword in ("今日は静かだね", "静かだね")):
            return "quiet_observation"
        if any(keyword in text for keyword in ("なんでそんな喋り方", "なんでそんな話し方", "その喋り方", "その話し方")):
            return "question_about_tone"
        if text in {"ねえ", "ねぇ", "ねえ、いる？", "ねぇ、いる？", "いる？", "……", "...", "…"}:
            return "callout"
        if any(keyword in text for keyword in ("あああ", "うああ", "うわあ", "わああ")):
            return "gibberish"
        return None

    def _detect_contextual_intent(
        self,
        user_text: str,
        recent_entries: list[tuple[str, str]],
        context_entries: list[tuple[str, str]],
    ) -> str | None:
        text = user_text.strip()
        last_user_message = self._last_message_for("user", recent_entries[:-1] if recent_entries else recent_entries)
        last_context_emotion = context_entries[-1][0] if context_entries else ""

        if last_user_message and "返事しなくてもいいから聞いて" in last_user_message and len(text) >= 2:
            return "listen_request"
        if text.startswith("逆に") and any(word in text for word in ("不安", "こわい")):
            return "silence_anxiety"
        if text.endswith("？") and last_context_emotion in {"lonely", "anxious"}:
            return "companionship"
        return None

    def _build_contextual_prefix(self, emotion: str, context_entries: list[tuple[str, str]], summary: str) -> str:
        if len(summary) >= 28 and any(marker in summary for marker in ("/", "けど", "のに", "でも")):
            if emotion in {"conflicted", "stressed", "anxious"}:
                return "いろいろ重なってそうなのだ。"
            if emotion in {"tired", "socially_tired", "empty"}:
                return "気力がじわっと減ってそうなのだ。"

        if not context_entries:
            return ""

        previous_emotions = [entry[0] for entry in context_entries[-3:]]
        if emotion == "relieved" and any(prev in {"anxious", "sad", "tired", "conflicted"} for prev in previous_emotions):
            return "さっきより少しゆるんだ感じなのだ。"
        if emotion in {"tired", "socially_tired"} and any(prev in {"tired", "stressed", "conflicted"} for prev in previous_emotions):
            return "さっきからつかれが続いてそうなのだ。"
        if emotion in {"anxious", "overstimulated"} and any(prev in {"anxious", "overstimulated"} for prev in previous_emotions):
            return "まだ少しざわざわが残ってそうなのだ。"
        return ""

    def _load_trivia_lines(self) -> list[str]:
        try:
            data = json.loads(TRIVIA_PATH.read_text(encoding="utf-8"))
            lines = data.get("trivia", [])
            return [line.strip() for line in lines if isinstance(line, str) and line.strip()]
        except Exception:
            return []

    def _load_support_replies(self) -> dict[str, list[str]]:
        try:
            data = json.loads(SUPPORT_PATH.read_text(encoding="utf-8"))
            replies = data.get("emotions", {})
            return {key: [line.strip() for line in value if isinstance(line, str) and line.strip()] for key, value in replies.items()}
        except Exception:
            return {}

    def _parse_recent_entries(self, recent_log_text: str) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for line in recent_log_text.splitlines():
            parts = line.split(" / ", 2)
            if len(parts) != 3:
                continue
            _, speaker, message = parts
            entries.append((speaker.strip().lower(), message.strip()))
        return entries

    def _parse_context_entries(self, context_text: str) -> list[tuple[str, str]]:
        entries: list[tuple[str, str]] = []
        for line in context_text.splitlines():
            if ":" not in line:
                continue
            emotion, rest = line.split(":", 1)
            entries.append((emotion.strip(), rest.strip()))
        return entries

    def _last_message_for(self, speaker: str, entries: list[tuple[str, str]]) -> str:
        speaker = speaker.lower()
        for entry_speaker, message in reversed(entries):
            if entry_speaker == speaker and message:
                return message
        return ""

    def _build_system_prompt(self, emotion: str, recent_log_text: str, context_text: str) -> str:
        state = self.state_service.state
        if state.friendship >= 20:
            tone = "かなり親しい。やわらかく、少し元気よく話す。"
        elif state.friendship >= 8:
            tone = "親しみやすく、やさしく話す。"
        else:
            tone = "やさしく、重くしすぎずに話す。"

        persona_fragment = self.persona.build_prompt_fragment()
        recent_fragment = f"最近の会話ログ:\n{recent_log_text}\n" if recent_log_text else ""
        context_fragment = f"最近の流れメモ:\n{context_text}\n" if context_text else ""

        return (
            f"{CHARACTER_PROMPT}\n"
            f"{persona_fragment}\n"
            f"現在の状態: {self.state_service.as_prompt_context()}\n"
            f"ユーザー感情: {emotion}\n"
            f"返答トーン: {tone}\n"
            f"{context_fragment}"
            f"{recent_fragment}"
            "返答は短めの1～3文にする。"
            " 語尾は『のだ』中心にする。"
            " 同じ構文の連打を避ける。"
            " 説教しない。"
            " 条件づけを多用しない。"
            " 勢いがほしい時は『！』で表現する。"
        )

    def _seed(self, text: str) -> int:
        return sum(ord(char) for char in text) % 997

    def _normalize_reply(self, text: str) -> str:
        normalized = " ".join(text.replace("\r", "\n").split()).strip()
        if not normalized:
            normalized = "だいじょうぶなのだー！"

        normalized = normalized.replace("～", "ー")
        normalized = re.sub(r"^(よわ|ai|assistant)\s*[:：]\s*", "", normalized, flags=re.IGNORECASE)
        normalized = re.sub(r"(のだ[ー!！]*)\s+\1", r"\1", normalized)

        if normalized.endswith(("のだ", "なのだ", "のだ。", "なのだ。", "のだ！", "なのだ！", "のだー！", "のだ？", "なのだ？", "のだ?", "なのだ?")):
            return normalized

        trimmed = normalized.rstrip("。！？!?… ")
        if not trimmed:
            return "だいじょうぶなのだー！"

        if trimmed.endswith(("です", "ます")):
            trimmed = re.sub(r"(です|ます)$", "", trimmed).rstrip()

        if trimmed.endswith(("い", "う", "る", "く", "す", "た", "だ", "な", "かも")):
            return f"{trimmed}のだ"
        return f"{trimmed}なのだ"
