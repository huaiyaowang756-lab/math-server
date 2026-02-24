"""
闲聊技能：无匹配技能时，使用大模型进行通用对话。
"""

from typing import Any, Dict

from langchain_core.messages import SystemMessage, HumanMessage

from .base import BaseSkill
from ...config_loader import get_doubao_config


CHAT_SYSTEM = """你是一个友好的数学学习助手。用户会和你闲聊或询问与数学题目推荐无关的问题。
请用简洁、自然的语气回复。若用户后续想推荐题目，可引导其描述具体需求。"""


def _get_llm(model_override: str = None):
    cfg = get_doubao_config()
    api_key = cfg.get("api_key")
    if not api_key:
        raise ValueError("未配置 DOUBAO_API_KEY，闲聊功能不可用")
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


class ChatSkill(BaseSkill):
    """闲聊技能。"""

    intent = "chat"
    name = "闲聊"

    def invoke(self, user_query: str, **kwargs) -> Dict[str, Any]:
        llm_model = kwargs.get("llm_model")

        try:
            llm = _get_llm(model_override=llm_model)
            resp = llm.invoke([
                SystemMessage(content=CHAT_SYSTEM),
                HumanMessage(content=user_query),
            ])
            content = (resp.content or "").strip() or "抱歉，我暂时无法回答。"
        except Exception as e:
            content = f"抱歉，闲聊功能暂时不可用：{str(e)}"

        return {
            "content": content,
            "questions": None,
            "intent": self.intent,
            "skill_used": self.name,
        }
