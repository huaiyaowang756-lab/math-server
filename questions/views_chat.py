"""
统一聊天 API：用户输入先经过意图识别，再路由到对应技能。
"""

import json

from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services.agent import process_message, process_message_stream

JSON_OPTIONS = {"ensure_ascii": False}


def _json_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None


@csrf_exempt
@require_http_methods(["POST"])
def chat(request):
    """
    POST /api/chat/
    JSON body: { "query": "用户输入", "limit": 5, "llm_model": "..." }
    返回统一格式：{ "content", "questions", "intent", "skill_used" }
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
    recall_limit = data.get("recall_limit", 20)
    llm_model = (data.get("llm_model") or "").strip() or None

    try:
        result = process_message(
            user_query=query,
            limit=limit,
            recall_limit=recall_limit,
            llm_model=llm_model,
        )
        return JsonResponse(result, json_dumps_params=JSON_OPTIONS)
    except ValueError as e:
        return JsonResponse(
            {"error": str(e)},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )
    except Exception as e:
        return JsonResponse(
            {"error": f"处理失败: {str(e)}"},
            status=500,
            json_dumps_params=JSON_OPTIONS,
        )


@csrf_exempt
@require_http_methods(["POST"])
def chat_stream(request):
    """
    POST /api/chat/stream/
    流式输出，返回 SSE。事件：intent -> chunk(可选) -> done
    """
    data = _json_body(request)
    if not data:
        return JsonResponse({"error": "无效请求体"}, status=400, json_dumps_params=JSON_OPTIONS)

    query = (data.get("query") or "").strip()
    if not query:
        return JsonResponse({"error": "query 不能为空"}, status=400, json_dumps_params=JSON_OPTIONS)

    limit = data.get("limit", 5)
    if not isinstance(limit, int) or limit < 1 or limit > 20:
        limit = 5
    recall_limit = data.get("recall_limit", 20)
    llm_model = (data.get("llm_model") or "").strip() or None

    def gen():
        try:
            for evt in process_message_stream(
                user_query=query,
                limit=limit,
                recall_limit=recall_limit,
                llm_model=llm_model,
            ):
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    resp = StreamingHttpResponse(gen(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp
