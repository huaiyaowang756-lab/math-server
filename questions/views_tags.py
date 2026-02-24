"""
标签管理 API：难度、分类、地区、场景。
"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Tag

JSON_OPTIONS = {"ensure_ascii": False}

TAG_TYPE_LABELS = {
    "difficulty": "难度",
    "category": "分类",
    "region": "地区",
    "scenario": "场景",
}


def _json_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None


@csrf_exempt
@require_http_methods(["GET"])
def list_tags(request):
    """
    获取标签列表。
    GET /api/tags/?tag_type=difficulty
    - tag_type 必填，可选值：difficulty / category / region / scenario
    """
    tag_type = request.GET.get("tag_type", "").strip()
    if tag_type not in Tag.TAG_TYPES:
        return JsonResponse(
            {"error": f"tag_type 必须为: {', '.join(Tag.TAG_TYPES)}"},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )

    tags = Tag.objects.filter(tag_type=tag_type).order_by("order", "created_at")
    return JsonResponse(
        {"tags": [t.to_dict() for t in tags]},
        json_dumps_params=JSON_OPTIONS,
    )


@csrf_exempt
@require_http_methods(["POST"])
def create_tag(request):
    """
    创建标签。
    POST /api/tags/create/
    - JSON body: { tag_type, name, order? }
    """
    data = _json_body(request)
    if not data:
        return JsonResponse({"error": "无效的请求体"}, status=400, json_dumps_params=JSON_OPTIONS)

    tag_type = (data.get("tagType") or data.get("tag_type") or "").strip()
    name = (data.get("name") or "").strip()

    if tag_type not in Tag.TAG_TYPES:
        return JsonResponse(
            {"error": f"tag_type 必须为: {', '.join(Tag.TAG_TYPES)}"},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )
    if not name:
        return JsonResponse({"error": "名称不能为空"}, status=400, json_dumps_params=JSON_OPTIONS)

    if Tag.objects.filter(tag_type=tag_type, name=name).first():
        label = TAG_TYPE_LABELS.get(tag_type, tag_type)
        return JsonResponse(
            {"error": f"{label}标签「{name}」已存在"},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )

    order = data.get("order", 0)
    if not isinstance(order, int):
        order = 0

    tag = Tag(tag_type=tag_type, name=name, order=order)
    tag.save()
    return JsonResponse({"success": True, "tag": tag.to_dict()}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["PUT"])
def update_tag(request, tag_id):
    """
    更新标签。
    PUT /api/tags/<id>/update/
    - JSON body: { name?, order? }
    """
    data = _json_body(request)
    if not data:
        return JsonResponse({"error": "无效的请求体"}, status=400, json_dumps_params=JSON_OPTIONS)

    try:
        tag = Tag.objects.get(id=tag_id)
    except Tag.DoesNotExist:
        return JsonResponse({"error": "标签不存在"}, status=404, json_dumps_params=JSON_OPTIONS)

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            return JsonResponse({"error": "名称不能为空"}, status=400, json_dumps_params=JSON_OPTIONS)
        existing = Tag.objects.filter(tag_type=tag.tag_type, name=name).first()
        if existing and str(existing.id) != str(tag.id):
            return JsonResponse({"error": f"标签「{name}」已存在"}, status=400, json_dumps_params=JSON_OPTIONS)
        tag.name = name

    if "order" in data:
        tag.order = int(data["order"]) if isinstance(data["order"], (int, float)) else 0

    tag.save()
    return JsonResponse({"success": True, "tag": tag.to_dict()}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_tag(request, tag_id):
    """
    删除标签。
    DELETE /api/tags/<id>/delete/
    """
    try:
        tag = Tag.objects.get(id=tag_id)
        tag.delete()
        return JsonResponse({"success": True}, json_dumps_params=JSON_OPTIONS)
    except Tag.DoesNotExist:
        return JsonResponse({"error": "标签不存在"}, status=404, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["POST"])
def batch_sort_tags(request):
    """
    批量排序标签。
    POST /api/tags/sort/
    - JSON body: { ids: [id1, id2, ...] }  按新顺序排列
    """
    data = _json_body(request)
    if not data or not isinstance(data.get("ids"), list):
        return JsonResponse({"error": "请提供 ids 列表"}, status=400, json_dumps_params=JSON_OPTIONS)

    for i, tag_id in enumerate(data["ids"]):
        try:
            tag = Tag.objects.get(id=tag_id)
            tag.order = i
            tag.save()
        except Tag.DoesNotExist:
            continue

    return JsonResponse({"success": True}, json_dumps_params=JSON_OPTIONS)
