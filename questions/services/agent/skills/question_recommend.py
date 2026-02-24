"""
推荐试题技能：封装向量召回 + 大模型精筛。
"""

from typing import Any, Dict, Iterator

from .base import BaseSkill
from ...vector_store.recommend import recommend_questions


class QuestionRecommendSkill(BaseSkill):
    """推荐试题技能。"""

    intent = "recommend_questions"
    name = "推荐试题"

    def invoke(self, user_query: str, **kwargs) -> Dict[str, Any]:
        limit = kwargs.get("limit", 5)
        recall_limit = kwargs.get("recall_limit", 20)
        llm_model = kwargs.get("llm_model")

        questions = recommend_questions(
            user_query=user_query,
            limit=limit,
            recall_limit=recall_limit,
            llm_model=llm_model,
        )

        content = f"为您推荐了 {len(questions)} 道相关题目：" if questions else "暂未找到匹配的题目，请尝试换一种描述方式。"

        return {
            "content": content,
            "questions": questions,
            "intent": self.intent,
            "skill_used": self.name,
        }

    def invoke_stream(self, user_query: str, **kwargs) -> Iterator[Dict[str, Any]]:
        """推荐无增量流式输出，直接执行后返回 done。"""
        result = self.invoke(user_query=user_query, **kwargs)
        yield {"type": "done", **result}
