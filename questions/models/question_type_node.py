# -*- coding: utf-8 -*-
"""
题型节点（树结构）。
"""

import datetime
import mongoengine as me


class QuestionTypeNode(me.Document):
    """
    题型节点（树结构）。
    任意节点都可拥有子节点，支持无限层级。
    题目侧通过 question_type_ids 存储绑定的题型节点 ID。
    """
    meta = {
        "collection": "question_type_nodes",
        "ordering": ["order", "created_at"],
        "indexes": ["parent_id"],
    }
    parent_id = me.StringField(default="")
    name = me.StringField(required=True, max_length=200)
    order = me.IntField(default=0)

    created_at = me.DateTimeField(default=datetime.datetime.utcnow)
    updated_at = me.DateTimeField(default=datetime.datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)

    def to_dict(self):
        return {
            "id": str(self.id),
            "parentId": self.parent_id or None,
            "name": self.name,
            "order": self.order,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
