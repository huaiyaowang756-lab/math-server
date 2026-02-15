"""
知识管理 API：知识分类、知识节点及前置依赖。
"""

import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import KnowledgeCategory, KnowledgeNode

JSON_OPTIONS = {"ensure_ascii": False}


def _json_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None


# ---------- 知识分类 ----------
@csrf_exempt
@require_http_methods(["GET"])
def list_categories(request):
    """GET /api/knowledge/categories/"""
    cats = KnowledgeCategory.objects.order_by("order", "created_at")
    return JsonResponse({"items": [c.to_dict() for c in cats]}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["POST"])
def create_category(request):
    """POST /api/knowledge/categories/create/  JSON: { name, order?, parentId? }"""
    data = _json_body(request)
    if not data or not data.get("name"):
        return JsonResponse({"error": "name 必填"}, status=400, json_dumps_params=JSON_OPTIONS)
    parent = None
    if data.get("parentId"):
        try:
            parent = KnowledgeCategory.objects.get(id=data["parentId"])
        except KnowledgeCategory.DoesNotExist:
            return JsonResponse({"error": "父分类不存在"}, status=400, json_dumps_params=JSON_OPTIONS)
    c = KnowledgeCategory(name=data["name"].strip(), order=data.get("order", 0), parent=parent)
    c.save()
    return JsonResponse(c.to_dict(), json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["GET"])
def get_category(request, category_id):
    """GET /api/knowledge/categories/<id>/"""
    try:
        c = KnowledgeCategory.objects.get(id=category_id)
        return JsonResponse(c.to_dict(), json_dumps_params=JSON_OPTIONS)
    except KnowledgeCategory.DoesNotExist:
        return JsonResponse({"error": "分类不存在"}, status=404, json_dumps_params=JSON_OPTIONS)


def _category_descendant_ids(category_id, all_cats):
    """返回某分类及其所有后代 id 集合，用于禁止将 parent 设为自己或后代（避免环）。"""
    ids = {str(category_id)}
    children = [c for c in all_cats if c.get("parentId") == str(category_id)]
    for ch in children:
        ids |= _category_descendant_ids(ch["id"], all_cats)
    return ids


@csrf_exempt
@require_http_methods(["PUT"])
def update_category(request, category_id):
    """PUT /api/knowledge/categories/<id>/  JSON: { name?, order?, parentId? }"""
    data = _json_body(request)
    if not data:
        return JsonResponse({"error": "无效请求体"}, status=400, json_dumps_params=JSON_OPTIONS)
    try:
        c = KnowledgeCategory.objects.get(id=category_id)
    except KnowledgeCategory.DoesNotExist:
        return JsonResponse({"error": "分类不存在"}, status=404, json_dumps_params=JSON_OPTIONS)
    if "name" in data:
        c.name = data["name"].strip()
    if "order" in data:
        c.order = data["order"]
    if "parentId" in data:
        pid = data["parentId"]
        if pid == str(c.id):
            return JsonResponse({"error": "不能将父分类设为自己"}, status=400, json_dumps_params=JSON_OPTIONS)
        all_cats = [x.to_dict() for x in KnowledgeCategory.objects.all()]
        descendants = _category_descendant_ids(str(c.id), all_cats)
        if pid and pid in descendants:
            return JsonResponse({"error": "不能将父分类设为自己的子分类"}, status=400, json_dumps_params=JSON_OPTIONS)
        if not pid:
            c.parent = None
        else:
            try:
                c.parent = KnowledgeCategory.objects.get(id=pid)
            except KnowledgeCategory.DoesNotExist:
                return JsonResponse({"error": "父分类不存在"}, status=400, json_dumps_params=JSON_OPTIONS)
    c.save()
    return JsonResponse(c.to_dict(), json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_category(request, category_id):
    """DELETE /api/knowledge/categories/<id>/"""
    try:
        c = KnowledgeCategory.objects.get(id=category_id)
        c.delete()
        return JsonResponse({"success": True}, json_dumps_params=JSON_OPTIONS)
    except KnowledgeCategory.DoesNotExist:
        return JsonResponse({"error": "分类不存在"}, status=404, json_dumps_params=JSON_OPTIONS)


# ---------- 知识节点 ----------
@csrf_exempt
@require_http_methods(["GET"])
def list_nodes(request):
    """GET /api/knowledge/nodes/  ?category_id= 可选"""
    category_id = request.GET.get("category_id")
    qs = KnowledgeNode.objects
    if category_id:
        qs = qs.filter(category=category_id)
    nodes = list(qs.order_by("category", "order", "created_at"))
    # 解析 ObjectId 的 prerequisite_ids 已在 to_dict 中转为 str
    return JsonResponse({"items": [n.to_dict() for n in nodes]}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["POST"])
def create_node(request):
    """POST /api/knowledge/nodes/  JSON: { categoryId, name, order?, prerequisiteIds? }"""
    data = _json_body(request)
    if not data or not data.get("categoryId") or not data.get("name"):
        return JsonResponse({"error": "categoryId 与 name 必填"}, status=400, json_dumps_params=JSON_OPTIONS)
    try:
        cat = KnowledgeCategory.objects.get(id=data["categoryId"])
    except KnowledgeCategory.DoesNotExist:
        return JsonResponse({"error": "分类不存在"}, status=400, json_dumps_params=JSON_OPTIONS)
    from bson import ObjectId
    prereq = []
    for pid in data.get("prerequisiteIds") or []:
        try:
            prereq.append(ObjectId(pid))
        except Exception:
            pass
    n = KnowledgeNode(
        category=cat,
        name=data["name"].strip(),
        order=data.get("order", 0),
        prerequisite_ids=prereq,
    )
    n.save()
    return JsonResponse(n.to_dict(), json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["GET"])
def get_node(request, node_id):
    """GET /api/knowledge/nodes/<id>/"""
    try:
        n = KnowledgeNode.objects.get(id=node_id)
        return JsonResponse(n.to_dict(), json_dumps_params=JSON_OPTIONS)
    except KnowledgeNode.DoesNotExist:
        return JsonResponse({"error": "节点不存在"}, status=404, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["PUT"])
def update_node(request, node_id):
    """PUT /api/knowledge/nodes/<id>/  JSON: { categoryId?, name?, order?, prerequisiteIds? }"""
    data = _json_body(request)
    if not data:
        return JsonResponse({"error": "无效请求体"}, status=400, json_dumps_params=JSON_OPTIONS)
    try:
        n = KnowledgeNode.objects.get(id=node_id)
    except KnowledgeNode.DoesNotExist:
        return JsonResponse({"error": "节点不存在"}, status=404, json_dumps_params=JSON_OPTIONS)
    if "categoryId" in data:
        try:
            n.category = KnowledgeCategory.objects.get(id=data["categoryId"])
        except KnowledgeCategory.DoesNotExist:
            return JsonResponse({"error": "分类不存在"}, status=400, json_dumps_params=JSON_OPTIONS)
    if "name" in data:
        n.name = data["name"].strip()
    if "order" in data:
        n.order = data["order"]
    if "prerequisiteIds" in data:
        from bson import ObjectId
        prereq = []
        for pid in data["prerequisiteIds"]:
            try:
                prereq.append(ObjectId(pid))
            except Exception:
                pass
        n.prerequisite_ids = prereq
    n.save()
    return JsonResponse(n.to_dict(), json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_node(request, node_id):
    """DELETE /api/knowledge/nodes/<id>/"""
    try:
        n = KnowledgeNode.objects.get(id=node_id)
        n.delete()
        return JsonResponse({"success": True}, json_dumps_params=JSON_OPTIONS)
    except KnowledgeNode.DoesNotExist:
        return JsonResponse({"error": "节点不存在"}, status=404, json_dumps_params=JSON_OPTIONS)


def _build_category_tree(cats_by_id, nodes_by_cat, parent_id=None):
    """递归构建分类树：每个项为 { category, children, nodes }。"""
    result = []
    for c in cats_by_id.values():
        if (c.get("parentId") or None) == parent_id:
            cid = c["id"]
            result.append({
                "category": c,
                "children": _build_category_tree(cats_by_id, nodes_by_cat, cid),
                "nodes": nodes_by_cat.get(cid, []),
            })
    result.sort(key=lambda x: (x["category"].get("order", 0), x["category"].get("name", "")))
    return result


@csrf_exempt
@require_http_methods(["GET"])
def knowledge_tree(request):
    """GET /api/knowledge/tree/  返回分类树（含子分类及节点），便于表格/图一次性加载"""
    cats = list(KnowledgeCategory.objects.order_by("order", "created_at"))
    nodes = list(KnowledgeNode.objects.order_by("category", "order", "created_at"))
    cats_by_id = {str(c.id): c.to_dict() for c in cats}
    nodes_by_cat = {}
    for n in nodes:
        cid = str(n.category.id)
        nodes_by_cat.setdefault(cid, []).append(n.to_dict())
    tree = _build_category_tree(cats_by_id, nodes_by_cat, None)
    return JsonResponse({"tree": tree}, json_dumps_params=JSON_OPTIONS)
