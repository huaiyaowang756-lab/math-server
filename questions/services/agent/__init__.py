"""
意图识别与技能编排：用户输入先经过意图识别，再路由到对应技能。
- recommend_questions: 推荐试题
- chat: 闲聊（无匹配技能时）
"""

from .intents import recognize_intent
from .orchestrator import process_message, process_message_stream
from .skills import get_skill_registry

__all__ = ["recognize_intent", "process_message", "process_message_stream", "get_skill_registry"]
