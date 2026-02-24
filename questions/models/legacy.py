# -*- coding: utf-8 -*-
"""
保留旧模型以兼容已有数据（不再被新 API 使用）。
"""

import datetime
import mongoengine as me


class KnowledgeCategory(me.Document):
    """[已废弃] 旧知识分类模型。"""
    meta = {"collection": "knowledge_categories", "ordering": ["order", "created_at"]}
    parent = me.ReferenceField("KnowledgeCategory", null=True, reverse_delete_rule=me.NULLIFY)
    name = me.StringField(required=True, max_length=200)
    order = me.IntField(default=0)
    created_at = me.DateTimeField(default=datetime.datetime.utcnow)
    updated_at = me.DateTimeField(default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": str(self.id),
            "parentId": str(self.parent.id) if self.parent else None,
            "name": self.name,
            "order": self.order,
        }


class KnowledgeNode(me.Document):
    """[已废弃] 旧知识节点模型。"""
    meta = {"collection": "knowledge_nodes", "ordering": ["category", "order", "created_at"], "indexes": ["category"]}
    category = me.ReferenceField(KnowledgeCategory, required=True, reverse_delete_rule=me.CASCADE)
    name = me.StringField(required=True, max_length=200)
    order = me.IntField(default=0)
    prerequisite_ids = me.ListField(me.ObjectIdField(), default=list)
    created_at = me.DateTimeField(default=datetime.datetime.utcnow)
    updated_at = me.DateTimeField(default=datetime.datetime.utcnow)

    def to_dict(self):
        return {
            "id": str(self.id),
            "categoryId": str(self.category.id) if self.category else None,
            "name": self.name,
            "order": self.order,
            "prerequisiteIds": [str(oid) for oid in (self.prerequisite_ids or [])],
        }
