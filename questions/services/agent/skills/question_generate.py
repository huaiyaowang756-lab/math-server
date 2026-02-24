"""
高中数学试题生成技能：根据用户描述生成对应的高中数学题目。
直接输出纯文本，不按题目协议结构化。
"""

from typing import Any, Dict, Iterator

from langchain_core.messages import SystemMessage, HumanMessage

from .base import BaseSkill
from ...config_loader import get_doubao_config


GENERATE_SYSTEM = """你是一名高中数学命题专家。根据用户描述，直接生成一道符合要求的高中数学题目。

输出格式（必须严格遵循，方便前端解析）：
1. 【题干】后接题干内容，选择题的选项（A、B、C、D）写在题干中
2. 【答案】后接答案内容
3. 【解析】后接简要解析（可选）
4. 数学公式必须用 LaTeX 表示，用 $$公式$$ 包裹（不要用 \( \)），例如：已知 $$x^2+y^2=1$$ 则...
5. 题干和答案必须用【题干】【答案】明确区分
6. 题目难度适中，符合高中数学课程标准"""


def _get_llm(model_override: str = None):
    cfg = get_doubao_config()
    api_key = cfg.get("api_key")
    if not api_key:
        raise ValueError("未配置 DOUBAO_API_KEY，试题生成功能不可用")
    from langchain_openai import ChatOpenAI
    model = (model_override or "").strip() or cfg.get("model", "doubao-1.5-pro-32k-250115")
    kw = {
        "api_key": api_key,
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": model,
    }
    if cfg.get("disable_proxy"):
        import httpx
        kw["http_client"] = httpx.Client(trust_env=False)
    return ChatOpenAI(**kw)


class QuestionGenerateSkill(BaseSkill):
    """高中数学试题生成技能。"""

    intent = "generate_questions"
    name = "生成试题"

    def invoke(self, user_query: str, **kwargs) -> Dict[str, Any]:
        llm_model = kwargs.get("llm_model")

        try:
            llm = _get_llm(model_override=llm_model)
            resp = llm.invoke([
                SystemMessage(content=GENERATE_SYSTEM),
                HumanMessage(content=f"请根据以下描述生成一道高中数学题目：\n\n{user_query}"),
            ])
            content = (resp.content or "").strip()
            if not content:
                content = "抱歉，未生成出有效题目，请尝试换一种描述方式。"
        except Exception as e:
            content = f"题目生成失败：{str(e)}"

        return {
            "content": content,
            "questions": [],
            "intent": self.intent,
            "skill_used": self.name,
        }

    def invoke_stream(
        self,
        user_query: str,
        **kwargs,
    ) -> Iterator[Dict[str, Any]]:
        """流式生成：直接输出纯文本。"""
        llm_model = kwargs.get("llm_model")

        try:
            llm = _get_llm(model_override=llm_model)
            full_text = []
            for chunk in llm.stream([
                SystemMessage(content=GENERATE_SYSTEM),
                HumanMessage(content=f"请根据以下描述生成一道高中数学题目：\n\n{user_query}"),
            ]):
                if hasattr(chunk, "content") and chunk.content:
                    full_text.append(chunk.content)
                    yield {"type": "chunk", "content": chunk.content}

            content = "".join(full_text).strip()
            if not content:
                content = "抱歉，未生成出有效题目，请尝试换一种描述方式。"
        except Exception as e:
            content = f"题目生成失败：{str(e)}"

        yield {
            "type": "done",
            "content": content,
            "questions": [],
            "intent": self.intent,
            "skill_used": self.name,
        }
