"""
技能注册表：管理所有可调用的技能，便于扩展。
"""

from typing import Dict, Optional

from .base import BaseSkill
from .question_recommend import QuestionRecommendSkill
from .chat import ChatSkill

# 技能注册表：intent -> skill
_registry: Dict[str, BaseSkill] = {}


def _init_registry():
    if not _registry:
        recommend = QuestionRecommendSkill()
        chat = ChatSkill()
        _registry[recommend.intent] = recommend
        _registry[chat.intent] = chat


def get_skill(intent: str) -> Optional[BaseSkill]:
    """根据意图获取对应技能。"""
    _init_registry()
    return _registry.get(intent)


def get_skill_registry() -> Dict[str, BaseSkill]:
    """获取完整技能注册表（用于调试或 UI 展示）。"""
    _init_registry()
    return _registry.copy()


def register_skill(skill: BaseSkill) -> None:
    """注册新技能，便于扩展。"""
    _init_registry()
    _registry[skill.intent] = skill
