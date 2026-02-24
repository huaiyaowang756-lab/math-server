"""
题型管理 API（题型节点树）。
与知识管理类似，支持父子树结构，题型节点可绑定题目。
绑定关系存储在题目侧的 question_type_ids。
"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import QuestionTypeNode, Question

JSON_OPTIONS = {"ensure_ascii": False}


def _json_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None


def _build_tree(nodes_by_parent, parent_id=""):
    children = nodes_by_parent.get(parent_id, [])
    result = []
    for n in children:
        node = n.to_dict()
        node["children"] = _build_tree(nodes_by_parent, str(n.id))
        result.append(node)
    return result


def _get_descendant_ids(node_id):
    ids = {str(node_id)}
    for c in QuestionTypeNode.objects.filter(parent_id=str(node_id)):
        ids |= _get_descendant_ids(str(c.id))
    return ids


@csrf_exempt
@require_http_methods(["GET"])
def question_type_tree(request):
    """GET /api/question-types/tree/"""
    all_nodes = list(QuestionTypeNode.objects.order_by("order", "created_at"))
    nodes_by_parent = {}
    for n in all_nodes:
        pid = n.parent_id or ""
        nodes_by_parent.setdefault(pid, []).append(n)
    tree = _build_tree(nodes_by_parent, "")
    return JsonResponse({"tree": tree}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["GET"])
def list_nodes(request):
    """GET /api/question-types/nodes/?parent_id=xxx"""
    parent_id = request.GET.get("parent_id", "").strip()
    nodes = QuestionTypeNode.objects.filter(parent_id=parent_id).order_by("order", "created_at")
    return JsonResponse({"nodes": [n.to_dict() for n in nodes]}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["POST"])
def create_node(request):
    """POST /api/question-types/nodes/create/"""
    data = _json_body(request)
    if not data or not (data.get("name") or "").strip():
        return JsonResponse({"error": "name 必填"}, status=400, json_dumps_params=JSON_OPTIONS)

    parent_id = (data.get("parentId") or "").strip()
    if parent_id and not QuestionTypeNode.objects.filter(id=parent_id).first():
        return JsonResponse({"error": "父节点不存在"}, status=400, json_dumps_params=JSON_OPTIONS)

    node = QuestionTypeNode(
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
    """GET /api/question-types/nodes/<id>/"""
    try:
        node = QuestionTypeNode.objects.get(id=node_id)
        return JsonResponse(node.to_dict(), json_dumps_params=JSON_OPTIONS)
    except QuestionTypeNode.DoesNotExist:
        return JsonResponse({"error": "节点不存在"}, status=404, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["PUT"])
def update_node(request, node_id):
    """PUT /api/question-types/nodes/<id>/update/"""
    data = _json_body(request)
    if not data:
        return JsonResponse({"error": "无效请求体"}, status=400, json_dumps_params=JSON_OPTIONS)

    try:
        node = QuestionTypeNode.objects.get(id=node_id)
    except QuestionTypeNode.DoesNotExist:
        return JsonResponse({"error": "节点不存在"}, status=404, json_dumps_params=JSON_OPTIONS)

    if "name" in data:
        name = (data["name"] or "").strip()
        if not name:
            return JsonResponse({"error": "名称不能为空"}, status=400, json_dumps_params=JSON_OPTIONS)
        node.name = name

    if "order" in data:
        node.order = int(data["order"]) if isinstance(data["order"], (int, float)) else 0

    if "parentId" in data:
        new_parent_id = (data["parentId"] or "").strip()
        if new_parent_id == str(node.id):
            return JsonResponse({"error": "不能将父节点设为自身"}, status=400, json_dumps_params=JSON_OPTIONS)
        if new_parent_id:
            descendants = _get_descendant_ids(str(node.id))
            if new_parent_id in descendants:
                return JsonResponse({"error": "不能将父节点设为自己的子孙节点"}, status=400, json_dumps_params=JSON_OPTIONS)
            if not QuestionTypeNode.objects.filter(id=new_parent_id).first():
                return JsonResponse({"error": "父节点不存在"}, status=400, json_dumps_params=JSON_OPTIONS)
        node.parent_id = new_parent_id

    node.save()
    return JsonResponse(node.to_dict(), json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_node(request, node_id):
    """DELETE /api/question-types/nodes/<id>/delete/"""
    try:
        node = QuestionTypeNode.objects.get(id=node_id)
    except QuestionTypeNode.DoesNotExist:
        return JsonResponse({"error": "节点不存在"}, status=404, json_dumps_params=JSON_OPTIONS)

    descendant_ids = _get_descendant_ids(str(node.id))
    descendant_ids.discard(str(node.id))
    for did in descendant_ids:
        try:
            QuestionTypeNode.objects.get(id=did).delete()
        except QuestionTypeNode.DoesNotExist:
            pass
    node.delete()
    return JsonResponse({"success": True, "deleted": len(descendant_ids) + 1}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["POST"])
def batch_sort_nodes(request):
    """POST /api/question-types/nodes/sort/"""
    data = _json_body(request)
    if not data or not isinstance(data.get("ids"), list):
        return JsonResponse({"error": "请提供 ids 列表"}, status=400, json_dumps_params=JSON_OPTIONS)

    for i, nid in enumerate(data["ids"]):
        try:
            node = QuestionTypeNode.objects.get(id=nid)
            node.order = i
            node.save()
        except QuestionTypeNode.DoesNotExist:
            continue
    return JsonResponse({"success": True}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["GET"])
def bound_question_ids(request, node_id):
    """
    GET /api/question-types/nodes/<id>/bound-ids/
    返回已绑定到该题型节点的题目 ID 列表。
    """
    try:
        node = QuestionTypeNode.objects.get(id=node_id)
    except QuestionTypeNode.DoesNotExist:
        return JsonResponse({"error": "节点不存在"}, status=404, json_dumps_params=JSON_OPTIONS)

    node_id_str = str(node.id)
    ids = [str(q.id) for q in Question.objects.filter(question_type_ids=node_id_str).only("id")]
    return JsonResponse({"questionIds": ids}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["POST"])
def bind_questions(request, node_id):
    """
    POST /api/question-types/nodes/<id>/bind-questions/
    JSON body: { questionIds: [id1, id2, ...] }
    将题目绑定到该题型节点。关系存储在题目侧 question_type_ids。
    """
    try:
        node = QuestionTypeNode.objects.get(id=node_id)
    except QuestionTypeNode.DoesNotExist:
        return JsonResponse({"error": "节点不存在"}, status=404, json_dumps_params=JSON_OPTIONS)

    data = _json_body(request)
    if not data or not isinstance(data.get("questionIds"), list):
        return JsonResponse({"error": "请提供 questionIds 列表"}, status=400, json_dumps_params=JSON_OPTIONS)

    node_id_str = str(node.id)
    bound = 0
    for qid in data["questionIds"]:
        try:
            q = Question.objects.get(id=qid)
            ids = list(q.question_type_ids or [])
            if node_id_str not in ids:
                ids.append(node_id_str)
                q.question_type_ids = ids
                q.save()
                bound += 1
        except Question.DoesNotExist:
            continue

    return JsonResponse({"success": True, "bound": bound}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["GET"])
def list_all_flat(request):
    """
    GET /api/question-types/nodes/flat/
    返回扁平列表（含路径），用于题型筛选下拉等。
    """
    all_db = list(QuestionTypeNode.objects.order_by("order", "created_at"))
    all_map = {str(n.id): n for n in all_db}

    def _build_path(nid):
        parts = []
        seen = set()
        while nid and nid in all_map and nid not in seen:
            seen.add(nid)
            n = all_map[nid]
            parts.append(n.name)
            nid = n.parent_id or ""
        parts.reverse()
        return " / ".join(parts)

    result = [{"id": str(n.id), "name": n.name, "path": _build_path(str(n.id))} for n in all_db]
    return JsonResponse({"nodes": result}, json_dumps_params=JSON_OPTIONS)
