"""
大模型精筛：使用 LangChain + Doubao 从召回的题目中挑选最相关的。
"""

import json
import re
from typing import List

from langchain_core.messages import SystemMessage, HumanMessage

from .config_loader import get_doubao_config
from .prompts.question_recommend import REFINE_QUESTIONS_SYSTEM, build_refine_user_prompt


def _get_llm(model_override: str = None):
    """
    获取 LangChain 豆包聊天模型（豆包方舟 Ark 提供 OpenAI 兼容 Chat API）。
    model_override: 可选，覆盖 config 中的 model（来自 LLMModel.model）
    """
    cfg = get_doubao_config()
    api_key = cfg.get("api_key")
    if not api_key:
        raise ValueError("未配置 DOUBAO_API_KEY，请在 config/tos.yaml 的 doubao 中配置")

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


def _parse_ids_from_response(text: str) -> List[str]:
    """从大模型返回中解析题目 ID 列表。"""
    text = (text or "").strip()
    # 尝试提取 JSON 数组
    m = re.search(r'\[[\s\S]*?\]', text)
    if m:
        try:
            ids = json.loads(m.group())
            if isinstance(ids, list):
                return [str(x) for x in ids if x]
        except json.JSONDecodeError:
            pass
    return []


def refine_questions_with_llm(
    user_query: str,
    recalled_questions: list,
    top_n: int = 5,
    llm_model: str = None,
) -> List[str]:
    """
    使用大模型从召回的题目中挑选最相关的 top_n 道，返回题目 ID 列表。

    Args:
        user_query: 用户需求
        recalled_questions: 召回题目列表，每项为 dict（含 id, description 等）
        top_n: 需要返回的数量
        llm_model: 可选，Ark 模型 ID（来自 LLMModel.model），用于覆盖默认模型

    Returns:
        题目 ID 列表，按相关度排序
    """
    if not recalled_questions:
        return []
    if top_n <= 0:
        top_n = 5

    try:
        llm = _get_llm(model_override=llm_model)
    except Exception as e:
        # 若 LLM 不可用，直接按向量得分顺序取前 top_n
        return [q.get("id") for q in recalled_questions[:top_n] if q.get("id")]

    user_prompt = build_refine_user_prompt(user_query, recalled_questions, top_n)
    messages = [
        SystemMessage(content=REFINE_QUESTIONS_SYSTEM),
        HumanMessage(content=user_prompt),
    ]

    try:
        resp = llm.invoke(messages)
        text = resp.content if hasattr(resp, "content") else str(resp)
        ids = _parse_ids_from_response(text)
        if ids:
            return ids
    except Exception:
        pass

    # 解析失败则按召回顺序返回
    return [q.get("id") for q in recalled_questions[:top_n] if q.get("id")]
