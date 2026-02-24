# -*- coding: utf-8 -*-
"""
大模型配置。
"""

import datetime
import mongoengine as me


class LLMModel(me.Document):
    """
    大模型配置：用于推荐精筛时可选不同模型。
    name: 切换列表中显示的名称
    model: 火山引擎 Ark 的模型 ID（如 doubao-seed-2-0-lite-260215）
    """
    meta = {
        "collection": "llm_models",
        "ordering": ["order", "created_at"],
    }

    name = me.StringField(required=True, max_length=100)
    model = me.StringField(required=True, max_length=200)
    order = me.IntField(default=0)

    created_at = me.DateTimeField(default=datetime.datetime.utcnow)
    updated_at = me.DateTimeField(default=datetime.datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name or "",
            "model": self.model or "",
            "order": self.order or 0,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
