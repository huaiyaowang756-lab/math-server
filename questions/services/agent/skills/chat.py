"""
闲聊技能：无匹配技能时，使用大模型进行通用对话。支持多轮历史（最多 20 轮）。
"""

import re
from typing import Any, Dict, Iterator, List

from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from .base import BaseSkill
from ...config_loader import get_doubao_config


CHAT_SYSTEM = """你是一个友好的数学学习助手。用户会和你闲聊或询问与数学题目推荐无关的问题。
请用简洁、自然的语气回复。若用户后续想推荐题目，可引导其描述具体需求。"""

MAX_HISTORY_ROUNDS = 20


def _strip_display_math(content: str) -> str:
    """将 $$...$$ 转为内联 $...$，便于历史中数学公式一致渲染、不重复包裹。"""
    if not content:
        return content
    return re.sub(r"\$\$([\s\S]*?)\$\$", r"$\1$", content)


def _history_to_messages(history: List[Dict]) -> List:
    """
    将前端历史转为 LangChain 消息列表。
    - 推荐/组卷的助手回复：不完整拼接题目卡片，用「这里是题目卡片信息」代替
    - 生成试题的助手回复：保留完整内容，但去掉 $$...$$ 包裹（改为内联 $...$）
    - 其他：用 content
    最多 20 轮（40 条）。
    """
    if not history:
        return []
    rounds = history if len(history) <= MAX_HISTORY_ROUNDS * 2 else history[-(MAX_HISTORY_ROUNDS * 2) :]
    out = []
    for item in rounds:
        role = (item.get("role") or "").strip()
        content = (item.get("content") or "").strip()
        intent = (item.get("intent") or "").strip()
        questions = item.get("questions") or []

        if role == "user":
            out.append(HumanMessage(content=content or "(用户未输入)"))
        elif role == "assistant":
            if questions and intent in ("recommend_questions", "assemble_paper"):
                content = "这里是题目卡片信息"
            elif questions and intent == "generate_questions":
                content = content or "这里是题目卡片信息"
                content = _strip_display_math(content)
            out.append(AIMessage(content=content or ""))
    return out


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
        history = kwargs.get("history") or []

        try:
            llm = _get_llm(model_override=llm_model)
            msgs = [SystemMessage(content=CHAT_SYSTEM)] + _history_to_messages(history) + [HumanMessage(content=user_query)]
            resp = llm.invoke(msgs)
            content = (resp.content or "").strip() or "抱歉，我暂时无法回答。"
        except Exception as e:
            content = f"抱歉，闲聊功能暂时不可用：{str(e)}"

        return {
            "content": content,
            "questions": None,
            "intent": self.intent,
            "skill_used": self.name,
        }

    def invoke_stream(self, user_query: str, **kwargs) -> Iterator[Dict[str, Any]]:
        """流式输出，支持多轮历史。"""
        llm_model = kwargs.get("llm_model")
        history = kwargs.get("history") or []

        try:
            llm = _get_llm(model_override=llm_model)
            msgs = [SystemMessage(content=CHAT_SYSTEM)] + _history_to_messages(history) + [HumanMessage(content=user_query)]
            full_content = []
            for chunk in llm.stream(msgs):
                if hasattr(chunk, "content") and chunk.content:
                    full_content.append(chunk.content)
                    yield {"type": "chunk", "content": chunk.content}
            content = "".join(full_content).strip() or "抱歉，我暂时无法回答。"
        except Exception as e:
            content = f"抱歉，闲聊功能暂时不可用：{str(e)}"

        yield {
            "type": "done",
            "content": content,
            "questions": None,
            "intent": self.intent,
            "skill_used": self.name,
        }
