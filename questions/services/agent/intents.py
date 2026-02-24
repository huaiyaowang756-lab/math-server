"""
意图识别：使用 LLM 判断用户输入属于哪种意图，便于路由到对应技能。
"""

import json
import re
from typing import Literal

from langchain_core.messages import SystemMessage, HumanMessage

from ..config_loader import get_doubao_config


# 支持的意图类型，后续新增技能时可扩展
IntentType = Literal["recommend_questions", "generate_questions", "assemble_paper", "chat"]


def _get_llm(model_override: str = None):
    """获取 LangChain 豆包模型。"""
    cfg = get_doubao_config()
    api_key = cfg.get("api_key")
    if not api_key:
        raise ValueError("未配置 DOUBAO_API_KEY")
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


INTENT_SYSTEM = """你是一个意图识别助手。根据用户输入，判断其意图类型。

意图类型：
- recommend_questions: 用户想要从题库中获取/推荐已有数学题目，例如：给我一些高一的函数题、推荐几道集合求交集的题、有没有正弦定理的题目、题型为三角函数的题
- generate_questions: 用户想要生成/出题/创作新的数学题目，例如：帮我出一道集合求交集的题、生成一道二次函数大题、出一道高一三角函数选择题
- assemble_paper: 用户想要组卷、出试卷、生成练习卷，例如：帮我组一份高一代数练习卷、出一张10道题的试卷、组一张三角函数专题卷
- chat: 闲聊、问候、无关数学题目推荐或生成的其他对话，例如：你好、谢谢、这是什么、讲个笑话

只输出一个 JSON 对象，格式：{"intent": "recommend_questions" 或 "generate_questions" 或 "assemble_paper" 或 "chat"}
不要输出其他内容。"""


def recognize_intent(user_query: str, llm_model: str = None) -> IntentType:
    """
    识别用户输入的意图。

    Args:
        user_query: 用户输入
        llm_model: 可选，覆盖默认模型

    Returns:
        "recommend_questions" 或 "chat"
    """
    q = (user_query or "").strip()
    if not q:
        return "chat"

    try:
        llm = _get_llm(model_override=llm_model)
        resp = llm.invoke([
            SystemMessage(content=INTENT_SYSTEM),
            HumanMessage(content=f"用户输入：{q}"),
        ])
        text = (resp.content or "").strip()
        m = re.search(r'\{[^{}]*\}', text)
        if m:
            data = json.loads(m.group())
            intent = (data.get("intent") or "").strip().lower()
            if intent == "recommend_questions":
                return "recommend_questions"
            if intent == "generate_questions":
                return "generate_questions"
            if intent == "assemble_paper":
                return "assemble_paper"
    except Exception:
        pass

    return "chat"
