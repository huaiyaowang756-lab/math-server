# -*- coding: utf-8 -*-
"""从请求中解析 token 并获取当前用户。"""

import datetime

from .models.chat_user import ChatUser, ChatSession

SESSION_VALID_MINUTES = 10


def get_token_from_request(request):
    """从 Authorization: Bearer <token> 或 query ?token= 获取。"""
    auth = request.META.get("HTTP_AUTHORIZATION") or ""
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return (request.GET or {}).get("token", "").strip()


def get_session_from_request(request, refresh=True):
    """
    从请求中取 token，校验并可选刷新过期时间。
    返回 (session, user) 或 (None, None)。
    """
    token = get_token_from_request(request)
    if not token:
        return None, None
    if refresh:
        session = ChatSession.refresh_if_valid(token, valid_minutes=SESSION_VALID_MINUTES)
    else:
        session = ChatSession.objects(token=token).first()
        if session and session.expires_at and session.expires_at <= datetime.datetime.utcnow():
            session = None
    if not session:
        return None, None
    user = ChatUser.objects(id=session.user_id).first()
    return session, user
