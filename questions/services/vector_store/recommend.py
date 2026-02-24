"""
题目推荐：向量检索 + 大模型精筛。
"""

from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

from ...models import Question, KnowledgePoint, QuestionTypeNode


def _object_id_to_uuid(oid: str) -> str:
    """将 MongoDB ObjectId 转为有效 UUID，供 Qdrant Point id 使用。"""
    h = (oid or "").replace("-", "")[:32].ljust(32, "0")
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"
import logging

from ..embedding.doubao import get_embedding, get_embeddings_batch
from ..embedding.text_builder import build_question_text, _build_kp_map, _build_qt_map
from .qdrant_client import (
    get_qdrant_client,
    get_collection_name,
    ensure_collection,
)


def build_vector_index(progress_callback=None) -> dict:
    """
    构建/重建向量索引：从 MongoDB 拉取所有 online 题目，生成 embedding 写入 Qdrant。

    Args:
        progress_callback: 可选，fn(current, total, message) 进度回调

    Returns:
        { "total": n, "success": m, "failed": k, "message": "..." }
    """
    questions = list(Question.objects.filter(status="online"))
    total = len(questions)
    if total == 0:
        return {"total": 0, "success": 0, "failed": 0, "message": "无在线题目"}

    if progress_callback:
        progress_callback(0, total, "加载知识点与题型映射...")

    kp_map = _build_kp_map([q.knowledge_points for q in questions])
    qt_map = _build_qt_map([q.question_type_ids for q in questions])

    texts = []
    for q in questions:
        t = build_question_text(q, kp_map, qt_map)
        texts.append(t or "(无描述)")

    if progress_callback:
        progress_callback(0, total, "生成 embedding...")

    batch_size = 20
    all_vectors = []
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i : i + batch_size]
        vecs = get_embeddings_batch(batch_texts)
        all_vectors.extend(vecs)
        if progress_callback:
            progress_callback(min(i + batch_size, total), total, f"已处理 {min(i + batch_size, total)} 题")

    client = get_qdrant_client()
    ensure_collection(client)
    coll = get_collection_name()

    points = []
    for i, q in enumerate(questions):
        vec = all_vectors[i] if i < len(all_vectors) else None
        if not vec:
            continue
        points.append(
            PointStruct(
                id=_object_id_to_uuid(str(q.id)),
                vector=vec,
                payload={
                    "question_id": str(q.id),
                    "difficulty": q.difficulty or "",
                    "categories": q.categories or [],
                    "status": q.status or "online",
                },
            )
        )

    if progress_callback:
        progress_callback(total, total, "写入 Qdrant...")

    # 全量重建：先清空再写入
    try:
        client.delete_collection(coll)
    except Exception:
        pass
    ensure_collection(client)

    upsert_batch = 100
    success = 0
    for j in range(0, len(points), upsert_batch):
        batch = points[j : j + upsert_batch]
        client.upsert(collection_name=coll, points=batch)
        success += len(batch)
        if progress_callback:
            progress_callback(success, total, f"已写入 {success} 条")

    return {
        "total": total,
        "success": success,
        "failed": total - success,
        "message": f"成功构建 {success} 条向量",
    }


def upsert_question_vector(question) -> bool:
    """
    单题向量更新：为 online 状态的题目生成 embedding 并写入 Qdrant。
    非 online 时删除 Qdrant 中的对应 Point。

    Returns:
        True 表示成功，False 表示跳过或失败（不影响主流程）
    """
    if question.status != "online":
        delete_question_vector(str(question.id))
        return True

    try:
        kp_map = _build_kp_map([question.knowledge_points])
        qt_map = _build_qt_map([question.question_type_ids])
        text = build_question_text(question, kp_map, qt_map) or "(无描述)"
        vec = get_embedding(text)
        if not vec:
            return False

        client = get_qdrant_client()
        ensure_collection(client)
        coll = get_collection_name()
        point = PointStruct(
            id=_object_id_to_uuid(str(question.id)),
            vector=vec,
            payload={
                "question_id": str(question.id),
                "difficulty": question.difficulty or "",
                "categories": question.categories or [],
                "status": question.status or "online",
            },
        )
        client.upsert(collection_name=coll, points=[point])
        return True
    except Exception as e:
        logging.getLogger(__name__).warning("upsert_question_vector failed: %s", e)
        return False


def delete_question_vector(question_id: str) -> bool:
    """
    从 Qdrant 中删除指定题目的向量。

    Returns:
        True 表示成功或点不存在，False 表示异常
    """
    try:
        client = get_qdrant_client()
        coll = get_collection_name()
        point_id = _object_id_to_uuid(question_id)
        client.delete(collection_name=coll, points_selector=[point_id])
        return True
    except Exception as e:
        logging.getLogger(__name__).warning("delete_question_vector failed: %s", e)
        return False


def _vector_search(query_vector, limit=20):
    """向量检索，返回 (question_id, score) 列表。"""
    client = get_qdrant_client()
    coll = get_collection_name()
    # 兼容 search / query_points 两种 API
    if hasattr(client, "search"):
        points = client.search(
            collection_name=coll,
            query_vector=query_vector,
            limit=limit,
            query_filter=Filter(
                must=[FieldCondition(key="status", match=MatchValue(value="online"))]
            ),
        )
    elif hasattr(client, "query_points"):
        resp = client.query_points(
            collection_name=coll,
            query=query_vector,
            limit=limit,
            query_filter=Filter(
                must=[FieldCondition(key="status", match=MatchValue(value="online"))]
            ),
        )
        points = getattr(resp, "points", None) or getattr(resp, "result", None) or []
    else:
        raise RuntimeError("QdrantClient 无 search 或 query_points 方法")

    def _qid(r):
        p = getattr(r, "payload", None) or {}
        return str(p.get("question_id", getattr(r, "id", "")))

    return [(_qid(r), getattr(r, "score", 0)) for r in points]


def _compute_recommend_score(vector_similarity: float, rank: int) -> int:
    """
    推荐题目打分，满分 100 分。

    打分规则（大模型精筛权重更高）：
    - 语义相似度（40 分）：向量余弦相似度 0-1 映射到 0-40
    - 精筛排序（60 分）：第 1 名 60 分，第 2 名 50，第 3 名 40，第 4 名 30，第 5 名 20，第 6 名及以后 10 分

    Args:
        vector_similarity: Qdrant 返回的相似度，通常 0-1
        rank: 精筛后的排名，1 表示最相关

    Returns:
        0-100 的整数分
    """
    vec = min(1.0, max(0.0, float(vector_similarity or 0)))
    semantic = round(vec * 40)

    rank_scores = {1: 60, 2: 50, 3: 40, 4: 30, 5: 20}
    rank_score = rank_scores.get(rank, 10)

    return min(100, semantic + rank_score)


def _refine_with_llm(user_query: str, recalled_questions: list, top_n: int = 5, llm_model: str = None) -> list:
    """
    使用大模型从召回的题目中精细挑选最相关的 top_n 道。
    recalled_questions: [{ "id", "description", "difficulty", ... }, ...]
    llm_model: 可选，Ark 模型 ID（来自 LLMModel.model）
    """
    from ..llm_refine import refine_questions_with_llm
    return refine_questions_with_llm(user_query, recalled_questions, top_n, llm_model=llm_model)


def recommend_questions(
    user_query: str,
    limit: int = 5,
    recall_limit: int = 20,
    llm_model: str = None,
) -> list:
    """
    推荐题目：向量召回 + 大模型精筛。

    Args:
        user_query: 用户输入
        limit: 最终返回数量
        recall_limit: 向量召回数量（供大模型精筛）

    Returns:
        题目详情列表（含 to_dict 字段）
    """
    query_vector = get_embedding(user_query.strip() or "数学题")
    recalled = _vector_search(query_vector, limit=recall_limit)
    if not recalled:
        return []

    qids = [r[0] for r in recalled]
    questions = list(Question.objects.filter(id__in=qids))
    q_map = {str(q.id): q for q in questions}
    kp_map = _build_kp_map([q.knowledge_points for q in questions])
    qt_map = _build_qt_map([q.question_type_ids for q in questions])

    # 构建召回列表（保持顺序）
    recalled_list = []
    for qid, score in recalled:
        q = q_map.get(qid)
        if not q:
            continue
        d = q.to_dict(kp_map=kp_map, qt_map=qt_map)
        d["_score"] = score
        recalled_list.append(d)

    # 向量得分映射
    vec_score_map = {r[0]: r[1] for r in recalled}

    # 大模型精筛
    refined_ids = _refine_with_llm(user_query, recalled_list, top_n=limit, llm_model=llm_model)
    if not refined_ids:
        subset = recalled_list[:limit]
        for i, item in enumerate(subset):
            vec = vec_score_map.get(item.get("id"), 0)
            item["score"] = _compute_recommend_score(vec, i + 1)
        subset.sort(key=lambda x: x.get("score", 0), reverse=True)
        return subset

    # 按精筛顺序返回，并计算 0-100 分
    result = []
    for rank, qid in enumerate(refined_ids, start=1):
        for item in recalled_list:
            if item.get("id") == qid:
                vec = vec_score_map.get(qid, 0)
                item["score"] = _compute_recommend_score(vec, rank)
                result.append(item)
                break
    # 若精筛返回不足，用召回的补齐
    seen = {item.get("id") for item in result}
    next_rank = len(result) + 1
    for item in recalled_list:
        if item.get("id") not in seen and len(result) < limit:
            vec = vec_score_map.get(item.get("id"), 0)
            item["score"] = _compute_recommend_score(vec, next_rank)
            result.append(item)
            seen.add(item.get("id"))
            next_rank += 1

    # 按得分降序排列
    result.sort(key=lambda x: x.get("score", 0), reverse=True)
    return result[:limit]
