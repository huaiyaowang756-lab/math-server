"""
技能基类：所有技能需实现 invoke 方法。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseSkill(ABC):
    """技能基类，新增技能时继承此类并注册到 skills/__init__.py。"""

    intent: str = ""   # 对应意图，如 recommend_questions
    name: str = ""     # 展示名称，如「推荐试题」

    @abstractmethod
    def invoke(self, user_query: str, **kwargs) -> Dict[str, Any]:
        """
        执行技能逻辑。

        Args:
            user_query: 用户输入
            **kwargs: 其他参数（如 limit, llm_model 等）

        Returns:
            统一响应格式，至少含 content；推荐试题类可含 questions 等
        """
        pass
