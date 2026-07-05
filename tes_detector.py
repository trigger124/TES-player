import openai
import webbrowser
import time
from enum import Enum
from config import TES_CONFIG


class GameState(Enum):
    INITIAL = "initial"
    IN_GAME = "in_game"
    ADVANTAGE = "advantage"
    DISADVANTAGE = "disadvantage"
    GAME_ENDING = "game_ending"
    TES_WIN = "tes_win"
    TES_LOSE = "tes_lose"


class TESDetector:
    def __init__(self):
        self.client = openai.OpenAI(
            api_key=TES_CONFIG['api_key'],
            base_url=TES_CONFIG['api_base']
        )
        self.current_state = GameState.INITIAL
        self.context_history = []
        self.last_reasoning = ""
        self.is_processing = False

    def _get_state_description(self, state):
        descriptions = {
            GameState.INITIAL: "初始状态",
            GameState.IN_GAME: "比赛进行中",
            GameState.ADVANTAGE: "TES优势",
            GameState.DISADVANTAGE: "TES劣势",
            GameState.GAME_ENDING: "比赛即将结束",
            GameState.TES_WIN: "TES胜利",
            GameState.TES_LOSE: "TES失败"
        }
        return descriptions.get(state, "未知状态")

    def _build_prompt(self, text):
        self.context_history.append(text)
        if len(self.context_history) > TES_CONFIG['context_window_size']:
            self.context_history = self.context_history[-TES_CONFIG['context_window_size']:]

        context_text = "\n".join([f"[{i+1}] {t}" for i, t in enumerate(self.context_history)])

        prompt = f"""你是一个专业的英雄联盟比赛解说分析员。请根据以下解说文本，持续分析TES战队（滔博战队）的比赛状态。

当前比赛状态: {self._get_state_description(self.current_state)}

最近的解说内容:
{context_text}

请按照以下要求进行分析：
1. 判断当前比赛处于什么阶段（初始、进行中、优势、劣势、即将结束）
2. 判断TES战队是否取得了比赛胜利或失败
3. 如果不确定，请给出最可能的状态和置信度

请严格按照以下JSON格式输出，不要输出其他内容：
{{
    "state": "当前状态（initial/in_game/advantage/disadvantage/game_ending/tes_win/tes_lose）",
    "action": "动作（victory/defeat/continue）",
    "confidence": "置信度（0-1）",
    "reasoning": "你的分析理由"
}}

注意：
- victory: TES战队明确获胜
- defeat: TES战队明确失败
- continue: 比赛仍在进行中，需要继续观察
"""
        return prompt

    def process_text(self, text):
        if self.is_processing:
            return "continue"

        self.is_processing = True
        try:
            prompt = self._build_prompt(text)

            response = self.client.chat.completions.create(
                model=TES_CONFIG['model'],
                messages=[
                    {"role": "system", "content": "你是一个专业的英雄联盟比赛解说分析员。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )

            result_text = response.choices[0].message.content.strip()

            try:
                import json
                result = json.loads(result_text)
            except Exception:
                result = {
                    "state": "in_game",
                    "action": "continue",
                    "confidence": 0.5,
                    "reasoning": result_text
                }

            self.last_reasoning = result.get("reasoning", "")
            state_str = result.get("state", "in_game")

            try:
                self.current_state = GameState(state_str)
            except ValueError:
                self.current_state = GameState.IN_GAME

            action = result.get("action", "continue")
            confidence = result.get("confidence", 0.5)

            if confidence < TES_CONFIG['confidence_threshold'] and action != "continue":
                print(f"置信度不足({confidence:.2f})，继续观察...")
                return "continue"

            return action

        except Exception as e:
            print(f"AI分析出错: {e}")
            self.last_reasoning = f"分析出错: {e}"
            return "continue"
        finally:
            self.is_processing = False

    def handle_victory(self):
        print("\n\n🎉 TES战队取得了比赛胜利！")
        print(f"分析理由: {self.last_reasoning}")
        print("系统将自动关闭...")
        time.sleep(3)

    def handle_defeat(self):
        print("\n\n😢 TES战队未能取得比赛胜利")
        print(f"分析理由: {self.last_reasoning}")
        print(f"正在打开安慰视频: {TES_CONFIG['comfort_video_url']}")
        webbrowser.open(TES_CONFIG['comfort_video_url'])
        time.sleep(5)

    def cleanup(self):
        pass
