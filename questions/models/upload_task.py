# -*- coding: utf-8 -*-
"""
试卷上传解析异步任务。
"""

import datetime
import mongoengine as me


class UploadTask(me.Document):
    """
    试卷上传解析异步任务。
    状态：pending -> processing -> completed | failed
    """
    meta = {
        "collection": "upload_tasks",
        "ordering": ["-created_at"],
        "indexes": ["status", "created_at"],
    }

    source_filename = me.StringField(required=True)
    # 来源试卷 id（试卷管理解析 or 导入试题上传后创建的试卷记录）
    document_id = me.StringField(default="")
    status = me.StringField(
        default="pending",
        choices=("pending", "processing", "completed", "failed"),
    )
    progress = me.IntField(default=0)  # 0-100
    error_msg = me.StringField(default="")
    # 解析完成后的结果（与 process_docx 返回格式一致）
    result = me.DictField(default=dict)  # session_id, questions, asset_base_url, stats
    use_latex = me.BooleanField(default=True)
    # 临时文件路径（任务完成后可清理）
    docx_path = me.StringField(default="")

    # ── 预设字段：解析出的题目默认使用这些值 ──
    preset_difficulty = me.StringField(default="")
    preset_categories = me.ListField(me.StringField(), default=list)
    preset_regions = me.ListField(me.StringField(), default=list)
    preset_scenario = me.StringField(default="")
    preset_knowledge_points = me.ListField(me.StringField(), default=list)

    created_at = me.DateTimeField(default=datetime.datetime.utcnow)
    updated_at = me.DateTimeField(default=datetime.datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)

    def get_presets(self):
        """返回预设字段字典，用于创建题目时填充默认值。"""
        return {
            "difficulty": self.preset_difficulty or "",
            "categories": self.preset_categories or [],
            "regions": self.preset_regions or [],
            "scenario": self.preset_scenario or "",
            "knowledge_points": self.preset_knowledge_points or [],
        }

    def to_dict(self):
        d = {
            "id": str(self.id),
            "sourceFilename": self.source_filename,
            "documentId": self.document_id or None,
            "status": self.status,
            "progress": self.progress,
            "errorMsg": self.error_msg or "",
            "useLatex": self.use_latex,
            "presets": {
                "difficulty": self.preset_difficulty or "",
                "categories": self.preset_categories or [],
                "regions": self.preset_regions or [],
                "scenario": self.preset_scenario or "",
                "knowledgePoints": self.preset_knowledge_points or [],
            },
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
        if self.status == "completed" and self.result:
            d["result"] = self.result
        return d
