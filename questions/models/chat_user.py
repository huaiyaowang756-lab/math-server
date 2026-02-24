# -*- coding: utf-8 -*-
"""聊天用户与会话（math-client 登录注册、10 分钟免登录）。"""

import datetime
import hashlib
import secrets
import mongoengine as me


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()


class ChatUser(me.Document):
    """聊天用户（注册用）。"""
    meta = {"collection": "chat_users", "indexes": ["username"]}
    username = me.StringField(required=True, unique=True, max_length=64)
    password_hash = me.StringField(required=True)
    salt = me.StringField(required=True)
    created_at = me.DateTimeField(default=datetime.datetime.utcnow)

    def set_password(self, raw_password: str) -> None:
        self.salt = secrets.token_hex(16)
        self.password_hash = _hash_password(raw_password, self.salt)

    def check_password(self, raw_password: str) -> bool:
        return self.password_hash == _hash_password(raw_password, self.salt)


class ChatSession(me.Document):
    """用户会话：10 分钟内有效，用于免重新登录。"""
    meta = {"collection": "chat_sessions", "indexes": ["token"], "strict": False}
    user_id = me.ObjectIdField(required=True)
    token = me.StringField(required=True, unique=True)
    expires_at = me.DateTimeField(required=True)
    created_at = me.DateTimeField(default=datetime.datetime.utcnow)

    @classmethod
    def create_for_user(cls, user: ChatUser, valid_minutes: int = 10) -> "ChatSession":
        now = datetime.datetime.utcnow()
        expires = now + datetime.timedelta(minutes=valid_minutes)
        session = cls(user_id=user.id, token=secrets.token_urlsafe(32), expires_at=expires)
        session.save()
        return session

    @classmethod
    def refresh_if_valid(cls, token: str, valid_minutes: int = 10) -> "ChatSession":
        """若 token 有效则刷新过期时间并返回 session，否则返回 None。"""
        session = cls.objects(token=token).first()
        if not session:
            return None
        now = datetime.datetime.utcnow()
        if session.expires_at <= now:
            session.delete()
            return None
        session.expires_at = now + datetime.timedelta(minutes=valid_minutes)
        session.save()
        return session


class ChatHistory(me.Document):
    """用户聊天记录（每个用户一条文档，messages 为完整列表）。"""
    meta = {"collection": "chat_histories", "indexes": ["user_id"]}
    user_id = me.ObjectIdField(required=True, unique=True)
    messages = me.ListField(me.DictField(), default=list)
    updated_at = me.DateTimeField(default=datetime.datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)
