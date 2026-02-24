"""
题目文本拼接：将 Question 的字段拼接为用于 embedding 的文本。
"""

from ...models import Question, KnowledgePoint, QuestionTypeNode


def _build_kp_map(ids_list):
    """批量查询知识点 ID -> 名称"""
    all_ids = set()
    for ids in ids_list:
        all_ids.update(ids or [])
    if not all_ids:
        return {}
    return {str(kp.id): kp.name for kp in KnowledgePoint.objects.filter(id__in=list(all_ids))}


def _build_qt_map(ids_list):
    """批量查询题型 ID -> 名称"""
    all_ids = set()
    for ids in ids_list:
        all_ids.update(ids or [])
    if not all_ids:
        return {}
    return {str(qt.id): qt.name for qt in QuestionTypeNode.objects.filter(id__in=list(all_ids))}


def build_question_text(q: Question, kp_map: dict = None, qt_map: dict = None) -> str:
    """
    将题目拼接为用于 embedding 的文本。

    Args:
        q: Question 实例
        kp_map: 知识点 id -> name 映射（可选，不传则查询）
        qt_map: 题型 id -> name 映射（可选，不传则查询）

    Returns:
        拼接后的文本
    """
    kp_map = kp_map or {}
    qt_map = qt_map or {}

    parts = []
    if q.description:
        parts.append(q.description)

    if q.difficulty:
        parts.append(f"难度：{q.difficulty}")
    if q.categories:
        parts.append(f"分类：{', '.join(q.categories)}")
    if q.regions:
        parts.append(f"地区：{', '.join(q.regions)}")
    if q.scenario:
        parts.append(f"场景：{q.scenario}")

    kp_ids = q.knowledge_points or []
    if kp_ids:
        names = [kp_map.get(kid, kid) for kid in kp_ids]
        parts.append(f"知识点：{', '.join(names)}")

    if q.features:
        for pair in q.features:
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                parts.append(f"{pair[0]}：{pair[1]}")
            elif isinstance(pair, str):
                parts.append(pair)

    qt_ids = q.question_type_ids or []
    if qt_ids:
        names = [qt_map.get(qid, qid) for qid in qt_ids]
        parts.append(f"题型：{', '.join(names)}")

    # 题目正文摘要（仅取 text 类型内容）
    for block in (q.question_body or []):
        if block.type == "text" and block.content:
            parts.append(block.content[:200])
        elif block.type == "latex" and block.content:
            parts.append(block.content[:100])

    return " ".join(p for p in parts if p)
