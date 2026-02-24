"""
组卷技能：根据用户对试卷的要求，通过推荐接口获取题目，供用户预览后下载。
"""

from typing import Any, Dict, Iterator

from .base import BaseSkill
from ...vector_store.recommend import recommend_questions


class AssemblePaperSkill(BaseSkill):
    """组卷技能：推荐题目组成试卷，供 review 后下载。"""

    intent = "assemble_paper"
    name = "组卷"

    def invoke(self, user_query: str, **kwargs) -> Dict[str, Any]:
        limit = max(kwargs.get("limit", 5), 10)
        recall_limit = kwargs.get("recall_limit", 30)
        llm_model = kwargs.get("llm_model")

        questions = recommend_questions(
            user_query=user_query,
            limit=limit,
            recall_limit=recall_limit,
            llm_model=llm_model,
        )

        if questions:
            content = f"已根据您的要求组卷，共 {len(questions)} 道题。请预览下方题目，确认后点击「下载试卷」。"
        else:
            content = "暂未找到匹配的题目，请尝试换一种描述（如知识点、难度、题量）。"

        return {
            "content": content,
            "questions": questions,
            "intent": self.intent,
            "skill_used": self.name,
        }

    def invoke_stream(self, user_query: str, **kwargs) -> Iterator[Dict[str, Any]]:
        """组卷无增量流式，直接执行后返回 done。"""
        result = self.invoke(
            user_query=user_query,
            limit=max(kwargs.get("limit", 5), 10),
            recall_limit=kwargs.get("recall_limit", 30),
            llm_model=kwargs.get("llm_model"),
        )
        yield {"type": "done", **result}
