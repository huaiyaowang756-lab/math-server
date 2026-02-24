"""
大模型管理 API：CRUD，供推荐精筛切换使用。
"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import LLMModel

JSON_OPTIONS = {"ensure_ascii": False}


def _json_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None


@require_http_methods(["GET"])
def list_llm_models(request):
    """
    GET /api/llm-models/
    列表（按 order、created_at 排序），供推荐聊天切换选择。
    """
    models = list(LLMModel.objects.order_by("order", "created_at"))
    return JsonResponse(
        {"models": [m.to_dict() for m in models]},
        json_dumps_params=JSON_OPTIONS,
    )


@csrf_exempt
@require_http_methods(["POST"])
def create_llm_model(request):
    """
    POST /api/llm-models/
    JSON body: { "name": "豆包 Lite", "model": "doubao-seed-2-0-lite-260215", "order": 0 }
    """
    data = _json_body(request)
    if not data:
        return JsonResponse({"error": "无效请求体"}, status=400, json_dumps_params=JSON_OPTIONS)

    name = (data.get("name") or "").strip()
    model = (data.get("model") or "").strip()
    if not name or not model:
        return JsonResponse(
            {"error": "name 和 model 不能为空"},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )

    m = LLMModel(name=name, model=model, order=data.get("order", 0))
    m.save()
    return JsonResponse({"success": True, "model": m.to_dict()}, json_dumps_params=JSON_OPTIONS)


@require_http_methods(["GET"])
def get_llm_model(request, model_id):
    """GET /api/llm-models/<id>/"""
    try:
        m = LLMModel.objects.get(id=model_id)
        return JsonResponse({"model": m.to_dict()}, json_dumps_params=JSON_OPTIONS)
    except LLMModel.DoesNotExist:
        return JsonResponse({"error": "大模型不存在"}, status=404, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["PUT"])
def update_llm_model(request, model_id):
    """
    PUT /api/llm-models/<id>/
    JSON body: { "name": "...", "model": "...", "order": 0 }
    """
    try:
        m = LLMModel.objects.get(id=model_id)
    except LLMModel.DoesNotExist:
        return JsonResponse({"error": "大模型不存在"}, status=404, json_dumps_params=JSON_OPTIONS)

    data = _json_body(request)
    if not data:
        return JsonResponse({"error": "无效请求体"}, status=400, json_dumps_params=JSON_OPTIONS)

    if "name" in data:
        v = (data["name"] or "").strip()
        if v:
            m.name = v
    if "model" in data:
        v = (data["model"] or "").strip()
        if v:
            m.model = v
    if "order" in data:
        m.order = int(data["order"]) if data["order"] is not None else 0

    m.save()
    return JsonResponse({"success": True, "model": m.to_dict()}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_llm_model(request, model_id):
    """DELETE /api/llm-models/<id>/"""
    try:
        m = LLMModel.objects.get(id=model_id)
        m.delete()
        return JsonResponse({"success": True}, json_dumps_params=JSON_OPTIONS)
    except LLMModel.DoesNotExist:
        return JsonResponse({"error": "大模型不存在"}, status=404, json_dumps_params=JSON_OPTIONS)
