# -*- coding: utf-8 -*-
"""注册、登录（返回 token，10 分钟有效）。"""

import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models.chat_user import ChatUser, ChatSession
from .auth_utils import SESSION_VALID_MINUTES

JSON_OPTIONS = {"ensure_ascii": False}


def _json_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None


@csrf_exempt
@require_http_methods(["POST"])
def register(request):
    """
    POST /api/auth/register/
    Body: { "username": "...", "password": "..." }
    """
    data = _json_body(request)
    if not data:
        return JsonResponse({"error": "无效请求体"}, status=400, json_dumps_params=JSON_OPTIONS)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or len(username) < 2:
        return JsonResponse({"error": "用户名至少 2 个字符"}, status=400, json_dumps_params=JSON_OPTIONS)
    if len(username) > 64:
        return JsonResponse({"error": "用户名过长"}, status=400, json_dumps_params=JSON_OPTIONS)
    if not password or len(password) < 6:
        return JsonResponse({"error": "密码至少 6 位"}, status=400, json_dumps_params=JSON_OPTIONS)
    if ChatUser.objects(username=username).first():
        return JsonResponse({"error": "用户名已存在"}, status=400, json_dumps_params=JSON_OPTIONS)
    user = ChatUser(username=username)
    user.set_password(password)
    user.save()
    session = ChatSession.create_for_user(user, valid_minutes=SESSION_VALID_MINUTES)
    return JsonResponse({
        "token": session.token,
        "expires_at": session.expires_at.isoformat() + "Z",
        "user": {"username": user.username},
    }, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["POST"])
def login(request):
    """
    POST /api/auth/login/
    Body: { "username": "...", "password": "..." }
    """
    data = _json_body(request)
    if not data:
        return JsonResponse({"error": "无效请求体"}, status=400, json_dumps_params=JSON_OPTIONS)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    user = ChatUser.objects(username=username).first()
    if not user or not user.check_password(password):
        return JsonResponse({"error": "用户名或密码错误"}, status=401, json_dumps_params=JSON_OPTIONS)
    # 使该用户旧会话失效（可选：允许多端登录则去掉）
    ChatSession.objects(user_id=user.id).delete()
    session = ChatSession.create_for_user(user, valid_minutes=SESSION_VALID_MINUTES)
    return JsonResponse({
        "token": session.token,
        "expires_at": session.expires_at.isoformat() + "Z",
        "user": {"username": user.username},
    }, json_dumps_params=JSON_OPTIONS)
