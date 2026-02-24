"""
题目推荐 API：聊天式输入，返回推荐题目。
"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services.vector_store.recommend import recommend_questions

JSON_OPTIONS = {"ensure_ascii": False}


def _json_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None


@csrf_exempt
@require_http_methods(["POST"])
def recommend(request):
    """
    POST /api/questions/recommend/
    JSON body: { "query": "高一函数题", "limit": 5 }
    返回推荐题目列表（经向量召回 + 大模型精筛）
    """
    data = _json_body(request)
    if not data:
        return JsonResponse(
            {"error": "无效请求体"},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )

    query = (data.get("query") or "").strip()
    if not query:
        return JsonResponse(
            {"error": "query 不能为空"},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )

    limit = data.get("limit", 5)
    if not isinstance(limit, int) or limit < 1 or limit > 20:
        limit = 5

    llm_model = (data.get("llm_model") or "").strip() or None

    try:
        questions = recommend_questions(user_query=query, limit=limit, recall_limit=20, llm_model=llm_model)
        return JsonResponse(
            {"questions": questions},
            json_dumps_params=JSON_OPTIONS,
        )
    except ValueError as e:
        return JsonResponse(
            {"error": str(e)},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )
    except Exception as e:
        return JsonResponse(
            {"error": f"推荐失败: {str(e)}"},
            status=500,
            json_dumps_params=JSON_OPTIONS,
        )
