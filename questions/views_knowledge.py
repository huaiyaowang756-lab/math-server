"""
知识管理 API（统一知识节点树）。
所有节点平等，任意节点可拥有子节点，支持无限层级。
"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import KnowledgePoint

JSON_OPTIONS = {"ensure_ascii": False}


def _json_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None


def _build_tree(nodes_by_parent, parent_id=""):
    """递归构建树结构。"""
    children = nodes_by_parent.get(parent_id, [])
    result = []
    for n in children:
        node = n.to_dict()
        node["children"] = _build_tree(nodes_by_parent, str(n.id))
        result.append(node)
    return result


@csrf_exempt
@require_http_methods(["GET"])
def knowledge_tree(request):
    """
    GET /api/knowledge/tree/
    返回完整知识点树。
    """
    all_nodes = list(KnowledgePoint.objects.order_by("order", "created_at"))

    nodes_by_parent = {}
    for n in all_nodes:
        pid = n.parent_id or ""
        nodes_by_parent.setdefault(pid, []).append(n)

    tree = _build_tree(nodes_by_parent, "")
    return JsonResponse({"tree": tree}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["GET"])
def list_nodes(request):
    """
    GET /api/knowledge/nodes/?parent_id=xxx
    获取指定父节点下的直接子节点（不传 parent_id 则获取顶级节点）。
    """
    parent_id = request.GET.get("parent_id", "").strip()
    nodes = KnowledgePoint.objects.filter(
        parent_id=parent_id
    ).order_by("order", "created_at")
    return JsonResponse(
        {"nodes": [n.to_dict() for n in nodes]},
        json_dumps_params=JSON_OPTIONS,
    )


@csrf_exempt
@require_http_methods(["POST"])
def create_node(request):
    """
    POST /api/knowledge/nodes/create/
    JSON body: { name, parentId?, order? }
    """
    data = _json_body(request)
    if not data or not (data.get("name") or "").strip():
        return JsonResponse(
            {"error": "name 必填"},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )

    parent_id = (data.get("parentId") or "").strip()
    if parent_id:
        if not KnowledgePoint.objects.filter(id=parent_id).first():
            return JsonResponse(
                {"error": "父节点不存在"},
                status=400,
                json_dumps_params=JSON_OPTIONS,
            )

    node = KnowledgePoint(
        parent_id=parent_id,
        name=data["name"].strip(),
        order=data.get("order", 0) if isinstance(data.get("order"), (int, float)) else 0,
    )
    node.save()
    result = node.to_dict()
    result["children"] = []
    return JsonResponse(result, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["GET"])
def get_node(request, node_id):
    """GET /api/knowledge/nodes/<id>/"""
    try:
        node = KnowledgePoint.objects.get(id=node_id)
        return JsonResponse(node.to_dict(), json_dumps_params=JSON_OPTIONS)
    except KnowledgePoint.DoesNotExist:
        return JsonResponse(
            {"error": "节点不存在"},
            status=404,
            json_dumps_params=JSON_OPTIONS,
        )


def _get_descendant_ids(node_id):
    """获取某节点所有后代 ID（含自身），用于避免环和级联删除。"""
    ids = {str(node_id)}
    children = KnowledgePoint.objects.filter(parent_id=str(node_id))
    for c in children:
        ids |= _get_descendant_ids(str(c.id))
    return ids


@csrf_exempt
@require_http_methods(["PUT"])
def update_node(request, node_id):
    """
    PUT /api/knowledge/nodes/<id>/update/
    JSON body: { name?, parentId?, order? }
    """
    data = _json_body(request)
    if not data:
        return JsonResponse(
            {"error": "无效请求体"},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )

    try:
        node = KnowledgePoint.objects.get(id=node_id)
    except KnowledgePoint.DoesNotExist:
        return JsonResponse(
            {"error": "节点不存在"},
            status=404,
            json_dumps_params=JSON_OPTIONS,
        )

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            return JsonResponse(
                {"error": "名称不能为空"},
                status=400,
                json_dumps_params=JSON_OPTIONS,
            )
        node.name = name

    if "order" in data:
        node.order = int(data["order"]) if isinstance(data["order"], (int, float)) else 0

    if "parentId" in data:
        new_parent_id = (data["parentId"] or "").strip()
        if new_parent_id == str(node.id):
            return JsonResponse(
                {"error": "不能将父节点设为自身"},
                status=400,
                json_dumps_params=JSON_OPTIONS,
            )
        if new_parent_id:
            descendants = _get_descendant_ids(str(node.id))
            if new_parent_id in descendants:
                return JsonResponse(
                    {"error": "不能将父节点设为自己的子孙节点"},
                    status=400,
                    json_dumps_params=JSON_OPTIONS,
                )
            if not KnowledgePoint.objects.filter(id=new_parent_id).first():
                return JsonResponse(
                    {"error": "父节点不存在"},
                    status=400,
                    json_dumps_params=JSON_OPTIONS,
                )
        node.parent_id = new_parent_id

    node.save()
    return JsonResponse(node.to_dict(), json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_node(request, node_id):
    """
    DELETE /api/knowledge/nodes/<id>/delete/
    级联删除所有后代节点。
    """
    try:
        node = KnowledgePoint.objects.get(id=node_id)
    except KnowledgePoint.DoesNotExist:
        return JsonResponse(
            {"error": "节点不存在"},
            status=404,
            json_dumps_params=JSON_OPTIONS,
        )

    descendant_ids = _get_descendant_ids(str(node.id))
    descendant_ids.discard(str(node.id))

    for did in descendant_ids:
        try:
            KnowledgePoint.objects.get(id=did).delete()
        except KnowledgePoint.DoesNotExist:
            pass

    node.delete()
    return JsonResponse(
        {"success": True, "deleted": len(descendant_ids) + 1},
        json_dumps_params=JSON_OPTIONS,
    )


@csrf_exempt
@require_http_methods(["GET"])
def search_nodes(request):
    """
    GET /api/knowledge/nodes/search/?q=xxx&limit=50
    按名称模糊搜索**叶子**知识节点（无子节点），返回扁平列表（含完整祖先路径）。
    只有叶子节点可作为知识点绑定到题目。
    """
    q = request.GET.get("q", "").strip()
    limit = min(int(request.GET.get("limit", 50)), 200)

    # 加载全部节点用于判断叶子节点和构建路径
    all_db = list(KnowledgePoint.objects.only("id", "parent_id", "name"))
    all_nodes_map = {str(n.id): n for n in all_db}

    # 收集所有 parent_id，拥有子节点的 ID 即为非叶子节点
    non_leaf_ids = set()
    for n in all_db:
        pid = n.parent_id or ""
        if pid:
            non_leaf_ids.add(pid)

    # 过滤：名称匹配 + 叶子节点
    if q:
        qs = KnowledgePoint.objects.filter(name__icontains=q)
    else:
        qs = KnowledgePoint.objects.all()

    candidates = list(qs.order_by("order", "created_at"))
    nodes = [n for n in candidates if str(n.id) not in non_leaf_ids][:limit]

    def _build_path(node_id):
        parts = []
        seen = set()
        nid = node_id
        while nid and nid in all_nodes_map and nid not in seen:
            seen.add(nid)
            n = all_nodes_map[nid]
            parts.append(n.name)
            nid = n.parent_id or ""
        parts.reverse()
        return " / ".join(parts)

    result = []
    for n in nodes:
        d = n.to_dict()
        d["path"] = _build_path(str(n.id))
        result.append(d)

    return JsonResponse({"nodes": result}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["GET"])
def batch_get_nodes(request):
    """
    GET /api/knowledge/nodes/batch/?ids=id1,id2,id3
    批量获取知识节点信息（用于回显已绑定的节点名称）。
    """
    ids_raw = request.GET.get("ids", "").strip()
    if not ids_raw:
        return JsonResponse({"nodes": []}, json_dumps_params=JSON_OPTIONS)

    ids = [i.strip() for i in ids_raw.split(",") if i.strip()]

    # 构建 id->node 映射
    all_db = list(KnowledgePoint.objects.only("id", "parent_id", "name"))
    all_nodes_map = {str(n.id): n for n in all_db}

    def _build_path(node_id):
        parts = []
        seen = set()
        nid = node_id
        while nid and nid in all_nodes_map and nid not in seen:
            seen.add(nid)
            n = all_nodes_map[nid]
            parts.append(n.name)
            nid = n.parent_id or ""
        parts.reverse()
        return " / ".join(parts)

    result = []
    for nid in ids:
        if nid in all_nodes_map:
            n = all_nodes_map[nid]
            d = {
                "id": str(n.id),
                "parentId": n.parent_id or None,
                "name": n.name,
                "path": _build_path(str(n.id)),
            }
            result.append(d)

    return JsonResponse({"nodes": result}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["POST"])
def batch_sort_nodes(request):
    """
    POST /api/knowledge/nodes/sort/
    JSON body: { ids: [id1, id2, ...] }  按新顺序排列
    """
    data = _json_body(request)
    if not data or not isinstance(data.get("ids"), list):
        return JsonResponse(
            {"error": "请提供 ids 列表"},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )

    for i, nid in enumerate(data["ids"]):
        try:
            node = KnowledgePoint.objects.get(id=nid)
            node.order = i
            node.save()
        except KnowledgePoint.DoesNotExist:
            continue

    return JsonResponse({"success": True}, json_dumps_params=JSON_OPTIONS)
