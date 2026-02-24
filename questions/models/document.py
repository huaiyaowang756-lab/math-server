# -*- coding: utf-8 -*-
"""
试卷/文档管理。
"""

import datetime
import mongoengine as me


class Document(me.Document):
    """
    试卷/文档管理。
    支持 Word、PDF、PPT，存储于 TOS。
    """
    meta = {
        "collection": "documents",
        "ordering": ["-created_at"],
        "indexes": ["doc_type", "tags", "created_at"],
    }

    url = me.StringField(required=True)  # TOS 文档地址
    filename = me.StringField(default="")  # 原始文件名
    description = me.StringField(default="")  # 文档描述
    doc_type = me.StringField(
        default="other",
        choices=("exam", "topic", "other"),  # 试卷、专题、其他
    )
    tags = me.ListField(me.StringField(), default=list)  # 标签
    video_url = me.StringField(default="")  # 讲解视频地址

    created_at = me.DateTimeField(default=datetime.datetime.utcnow)
    updated_at = me.DateTimeField(default=datetime.datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)

    def to_dict(self):
        return {
            "id": str(self.id),
            "url": self.url or "",
            "filename": self.filename or "",
            "description": self.description or "",
            "docType": self.doc_type or "other",
            "tags": self.tags or [],
            "videoUrl": self.video_url or "",
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
