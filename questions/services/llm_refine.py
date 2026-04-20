"""
大模型精筛：使用 LangChain + Doubao 从召回的题目中挑选最相关的。
"""

import json
import re
from typing import List

from langchain_core.messages import SystemMessage, HumanMessage

from .config_loader import get_doubao_config
from .prompts.question_recommend import REFINE_QUESTIONS_SYSTEM, build_refine_user_prompt

FIX_LATEX_SYSTEM = """
你是数学 LaTeX 修复助手。请修复用户提供的 LaTeX 公式，使其满足：
1) 语法正确，可被 KaTeX 渲染；
2) 数学语义不变，不改变题意；
3) 保留原有中文文本与符号风格；
4) 仅返回修复后的 LaTeX 字符串，不要解释，不要 markdown 代码块，不要多余文字。
"""


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


def _extract_latex_text(text: str) -> str:
    """从模型回复中提取纯 LaTeX 文本。"""
    s = (text or "").strip()
    if not s:
        return ""
    # ```latex ... ``` / ```...```
    m = re.search(r"```(?:latex)?\s*([\s\S]*?)```", s, flags=re.IGNORECASE)
    if m:
        s = (m.group(1) or "").strip()
    # 去掉外层 $...$ / $$...$$
    if len(s) >= 4 and s.startswith("$$") and s.endswith("$$"):
        s = s[2:-2].strip()
    elif len(s) >= 2 and s.startswith("$") and s.endswith("$"):
        s = s[1:-1].strip()
    return s


def fix_latex_with_llm(
    latex: str,
    context: str = "",
    llm_model: str = None,
) -> str:
    """
    使用豆包大模型修复单条 LaTeX。

    Args:
        latex: 待修复 LaTeX
        context: 可选上下文（如题干片段）
        llm_model: 可选 Ark 模型 ID

    Returns:
        修复后的 LaTeX（若修复失败则抛异常）
    """
    src = (latex or "").strip()
    if not src:
        raise ValueError("latex 不能为空")

    llm = _get_llm(model_override=llm_model)
    user_prompt = (
        "请修复以下 LaTeX，保证 KaTeX 可渲染且语义不变。\n\n"
        f"上下文（可为空）：\n{(context or '').strip()}\n\n"
        f"原始 LaTeX：\n{src}\n"
    )
    messages = [
        SystemMessage(content=FIX_LATEX_SYSTEM.strip()),
        HumanMessage(content=user_prompt),
    ]
    resp = llm.invoke(messages)
    text = resp.content if hasattr(resp, "content") else str(resp)
    fixed = _extract_latex_text(text)
    if not fixed:
        raise RuntimeError("大模型未返回可用的 LaTeX")
    return fixed
