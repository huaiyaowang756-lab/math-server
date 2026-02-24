"""
编排器：根据意图识别结果路由到对应技能执行。
"""

from typing import Any, Dict, Iterator

from .intents import recognize_intent, IntentType
from .skills import get_skill


def process_message_stream(
    user_query: str,
    limit: int = 5,
    recall_limit: int = 20,
    llm_model: str = None,
) -> Iterator[Dict[str, Any]]:
    """
    流式入口：yield SSE 事件。
    事件格式：{"type": "intent"|"chunk"|"done", ...}
    """
    intent: IntentType = recognize_intent(user_query, llm_model=llm_model)
    yield {"type": "intent", "intent": intent}

    skill = get_skill(intent)
    if not skill:
        skill = get_skill("chat")

    invoke_stream = getattr(skill, "invoke_stream", None)
    if invoke_stream:
        for evt in invoke_stream(
            user_query=user_query,
            limit=limit,
            recall_limit=recall_limit,
            llm_model=llm_model,
        ):
            yield evt
    else:
        result = skill.invoke(
            user_query=user_query,
            limit=limit,
            recall_limit=recall_limit,
            llm_model=llm_model,
        )
        yield {"type": "done", **result}


def process_message(
    user_query: str,
    limit: int = 5,
    recall_limit: int = 20,
    llm_model: str = None,
) -> Dict[str, Any]:
    """
    统一入口：用户输入 → 意图识别 → 技能执行。

    Args:
        user_query: 用户输入
        limit: 推荐试题时的数量（仅 recommend_questions 时生效）
        recall_limit: 向量召回数量（仅 recommend_questions 时生效）
        llm_model: 可选，覆盖默认大模型

    Returns:
        统一响应格式：
        {
            "intent": "recommend_questions" | "chat",
            "content": "文本内容",
            "questions": [...] | null,
            "skill_used": "技能名称"
        }
    """
    intent: IntentType = recognize_intent(user_query, llm_model=llm_model)
    skill = get_skill(intent)

    if skill:
        return skill.invoke(
            user_query=user_query,
            limit=limit,
            recall_limit=recall_limit,
            llm_model=llm_model,
        )

    # 理论上不会到达：chat 技能会兜底
    fallback = get_skill("chat")
    return fallback.invoke(user_query=user_query, llm_model=llm_model)
