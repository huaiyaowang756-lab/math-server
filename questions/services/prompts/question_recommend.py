"""
题目推荐相关提示词。
"""

REFINE_QUESTIONS_SYSTEM = """你是一个数学题目推荐助手。用户会描述自己的需求，同时会得到一批从向量库召回的候选题目。

候选题目为 JSON 数组，每道题目的字段含义如下：
- id: 题目唯一标识，必须原样返回
- description: 题目描述/简介，人工总结的题目概要
- questionBodyExcerpt: 题干摘要，题目正文的文本摘要，含主要数学符号与条件
- difficulty: 难度等级（如 简单/中等/困难）
- categories: 题目分类列表（如教材章节、年级等）
- knowledgePoints: 知识点列表，题目考查的知识节点名称（如「正弦定理」「集合运算」）
- questionTypes: 题型节点列表，题目在题型树上的分类名称（如「集合求交集」「三角函数应用题」），表示题目的题型归属；用户说「题型为XXX」时应重点匹配此字段
- analysisExcerpt: 题目分析摘要，将分析内容块（text/latex）转为文本，图片节点已过滤
- features: 特征列表，格式为 [[标题, 描述], ...]，题目的附加标签

需求可能包含：
- 正向需求：如「正弦定理的运用」「高一函数题」「题型为集合求交集的题」
- 排除需求：如「没有考查集合求交集的题」「不涉及三角函数的题」「排除导数大题」

你的任务：从候选题目中挑选最符合用户需求的题目，按相关度从高到低排序，仅返回题目ID列表（JSON数组格式）。

要求：
1. 若用户使用排除表述（如「没有」「不考查」「排除」「不要」）：严格排除不符合的题目。例如「没有考查集合求交集」时，题干或知识点涉及集合交集的题目必须排除，不得返回。
2. 综合考虑 description、questionBodyExcerpt（题干摘要）、analysisExcerpt（题目分析）、knowledgePoints、questionTypes（题型节点）、features，判断题目是否涉及用户要排除或要求的内容。
3. 题干摘要、题目分析、题型节点和特征中若含有用户需求关键词，应优先排在前面；若明确涉及用户要排除的内容，不得入选。
4. 只返回题目ID，不要返回题目内容或其他说明
5. 严格按照相关度排序，最相关的排在第一位
6. 数量不超过用户要求的 top_n，若符合的题目不足 top_n 个，可返回更少
7. 输出格式必须为纯 JSON 数组，例如：["id1","id2","id3"]
"""


def REFINE_QUESTIONS_USER(user_query: str, questions_json: str, top_n: int) -> str:
    """构建精筛题目的 user 提示。"""
    return f"""用户需求：{user_query}

候选题目（JSON 格式）：
{questions_json}

请从中挑选最符合用户需求的 {top_n} 道题目（若用户要求排除某类题目，必须严格排除不符合的；符合条件的可少于 {top_n} 道），按相关度排序，只输出题目ID的JSON数组，例如：["id1","id2","id3"]"""


def _blocks_to_text(blocks: list, max_len: int = 400) -> str:
    """将内容块转为文本，仅取 text、latex 类型，过滤掉 image、svg 节点。"""
    parts = []
    for b in (blocks or []):
        t = b.get("type")
        if t == "text" and b.get("content"):
            parts.append(str(b["content"]))
        elif t == "latex" and b.get("content"):
            parts.append(str(b["content"]))
    text = " ".join(parts)
    return (text[:max_len] + "…") if len(text) > max_len else text


def _get_question_body_excerpt(blocks: list, max_len: int = 400) -> str:
    """从 questionBody 中提取题干摘要，供精筛排序参考。"""
    return _blocks_to_text(blocks, max_len)


def build_refine_user_prompt(user_query: str, questions: list, top_n: int = 5) -> str:
    """
    构建精筛 user 提示，将题目列表转为 JSON 字符串。
    questions: 题目 dict 列表，每项至少含 id, description, difficulty, questionBody 等
    会使用 questionTypeDetails（题型节点）辅助精筛，若题目来自 to_dict(kp_map, qt_map) 则已包含。
    """
    import json
    simplified = []
    for q in questions:
        kp_details = q.get("knowledgePointDetails") or []
        kp_names = [x.get("name", x.get("id", "")) for x in kp_details if isinstance(x, dict)]
        qt_details = q.get("questionTypeDetails") or []
        qt_names = [x.get("name", x.get("id", "")) for x in qt_details if isinstance(x, dict)]
        simplified.append({
            "id": q.get("id"),
            "description": q.get("description", ""),
            "questionBodyExcerpt": _get_question_body_excerpt(q.get("questionBody", [])),
            "analysisExcerpt": _blocks_to_text(q.get("analysis", []), max_len=300),
            "difficulty": q.get("difficulty", ""),
            "categories": q.get("categories", []),
            "knowledgePoints": kp_names or q.get("knowledgePoints", []),
            "questionTypes": qt_names or q.get("questionTypeIds", []),  # 题型节点：题目绑定的题型分类
            "features": q.get("features", []),
        })
    q_json = json.dumps(simplified, ensure_ascii=False, indent=2)
    return REFINE_QUESTIONS_USER(user_query, q_json, top_n)
