"""
统一聊天 API：用户输入先经过意图识别，再路由到对应技能。
含登录用户聊天记录获取/保存。
"""

import json

from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services.agent import process_message, process_message_stream
from .models.chat_user import ChatHistory
from .auth_utils import get_session_from_request

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
    history = data.get("history")
    if not isinstance(history, list):
        history = []
    # 最多 20 轮（40 条）
    if len(history) > 40:
        history = history[-40:]

    def gen():
        try:
            for evt in process_message_stream(
                user_query=query,
                limit=limit,
                recall_limit=recall_limit,
                llm_model=llm_model,
                history=history,
            ):
                yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"

    resp = StreamingHttpResponse(gen(), content_type="text/event-stream")
    resp["Cache-Control"] = "no-cache"
    resp["X-Accel-Buffering"] = "no"
    return resp


@csrf_exempt
@require_http_methods(["GET"])
def get_chat_history(request):
    """
    GET /api/chat/history/
    Header: Authorization: Bearer <token>
    返回当前用户的 messages 列表。
    """
    _, user = get_session_from_request(request)
    if not user:
        return JsonResponse({"error": "请先登录"}, status=401, json_dumps_params=JSON_OPTIONS)
    doc = ChatHistory.objects(user_id=user.id).first()
    messages = doc.messages if doc else []
    return JsonResponse({"messages": messages}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["POST"])
def save_chat_history(request):
    """
    POST /api/chat/history/
    Header: Authorization: Bearer <token>
    Body: { "messages": [...] }
    """
    _, user = get_session_from_request(request)
    if not user:
        return JsonResponse({"error": "请先登录"}, status=401, json_dumps_params=JSON_OPTIONS)
    data = _json_body(request)
    if not data:
        return JsonResponse({"error": "无效请求体"}, status=400, json_dumps_params=JSON_OPTIONS)
    messages = data.get("messages", [])
    if not isinstance(messages, list):
        return JsonResponse({"error": "messages 须为数组"}, status=400, json_dumps_params=JSON_OPTIONS)
    doc = ChatHistory.objects(user_id=user.id).first()
    if not doc:
        doc = ChatHistory(user_id=user.id, messages=messages)
    else:
        doc.messages = messages
    doc.save()
    return JsonResponse({"ok": True}, json_dumps_params=JSON_OPTIONS)
