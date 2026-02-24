# -*- coding: utf-8 -*-
"""
标签管理：难度、分类、地区、场景。
"""

import datetime
import mongoengine as me


class Tag(me.Document):
    """
    通用标签管理：难度、分类、地区、场景。
    同一 tag_type 下 name 唯一。
    """
    meta = {
        "collection": "tags",
        "ordering": ["tag_type", "order", "created_at"],
        "indexes": ["tag_type"],
    }

    TAG_TYPES = ("difficulty", "category", "region", "scenario")

    tag_type = me.StringField(required=True, choices=TAG_TYPES)
    name = me.StringField(required=True, max_length=100)
    order = me.IntField(default=0)

    created_at = me.DateTimeField(default=datetime.datetime.utcnow)
    updated_at = me.DateTimeField(default=datetime.datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)

    def to_dict(self):
        return {
            "id": str(self.id),
            "tagType": self.tag_type,
            "name": self.name,
            "order": self.order,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
