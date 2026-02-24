"""
运维 API：构建向量索引等。
"""

import json
import traceback

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .services.vector_store.recommend import build_vector_index

JSON_OPTIONS = {"ensure_ascii": False}


def _error_detail(e):
    """提取异常详情，便于排查。"""
    msg = str(e)
    if hasattr(e, "response") and e.response is not None:
        try:
            body = e.response.text
            if body and len(body) < 500:
                msg = f"{msg} | 响应: {body}"
        except Exception:
            pass
    return msg


@csrf_exempt
@require_http_methods(["POST"])
def build_vectors(request):
    """
    POST /api/ops/build-vectors/
    手动触发构建向量索引，从 MongoDB 拉取所有 online 题目，生成 embedding 写入 Qdrant。
    返回 { total, success, failed, message } 或 { error, total, success, failed }
    """
    try:
        result = build_vector_index()
        return JsonResponse(result, json_dumps_params=JSON_OPTIONS)
    except ValueError as e:
        return JsonResponse(
            {"error": str(e), "total": 0, "success": 0, "failed": 0},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )
    except Exception as e:
        detail = _error_detail(e)
        payload = {"error": detail, "total": 0, "success": 0, "failed": 0}
        if getattr(settings, "DEBUG", False):
            payload["traceback"] = traceback.format_exc()
        return JsonResponse(
            payload,
            status=500,
            json_dumps_params=JSON_OPTIONS,
        )
