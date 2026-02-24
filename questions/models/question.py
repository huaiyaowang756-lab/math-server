# -*- coding: utf-8 -*-
"""
数学题目。
"""

import datetime
import mongoengine as me

from .content_block import ContentBlock


class Question(me.Document):
    """数学题目。"""
    meta = {
        "collection": "questions",
        "ordering": ["-created_at"],
        "indexes": ["question_type", "source_file", "created_at",
                    "difficulty", "categories", "regions", "scenario", "question_type_ids"],
    }

    index = me.IntField(required=True)
    question_type = me.StringField(
        choices=("single_choice", "multiple_choice", "fill_blank", "solution")
    )
    question_body = me.EmbeddedDocumentListField(ContentBlock, default=list)
    answer = me.EmbeddedDocumentListField(ContentBlock, default=list)
    analysis = me.EmbeddedDocumentListField(ContentBlock, default=list)
    detailed_solution = me.EmbeddedDocumentListField(ContentBlock, default=list)

    # ── 新增字段 ──
    difficulty = me.StringField(default="")              # 题目难度
    categories = me.ListField(me.StringField(), default=list)  # 题目分类（多选）
    regions = me.ListField(me.StringField(), default=list)     # 适用地区（多选）
    scenario = me.StringField(default="")                # 题目场景
    knowledge_points = me.ListField(me.StringField(), default=list)  # 知识点
    description = me.StringField(default="")             # 题目描述
    features = me.ListField(me.ListField(me.StringField()), default=list)  # 特征 [[title, desc], ...]
    question_type_ids = me.ListField(me.StringField(), default=list)  # 题型节点 ID 列表（题目属于哪些题型）

    source_file = me.StringField(default="")
    session_id = me.StringField(default="")
    asset_base_url = me.StringField(default="")
    # 来源试卷：便于与原卷对比（试卷管理解析 or 导入试题上传后都会落库试卷记录）
    source_document_id = me.StringField(default="")
    source_document_filename = me.StringField(default="")

    # 题目状态：待校验（保存后默认）→ 人工确认后改为上线
    status = me.StringField(
        default="pending_verification",
        choices=("pending_verification", "online"),
    )

    created_at = me.DateTimeField(default=datetime.datetime.utcnow)
    updated_at = me.DateTimeField(default=datetime.datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)

    def to_dict(self, kp_map=None, qt_map=None):
        """
        序列化为字典。
        kp_map: 可选的 {id: name} 映射，用于将 knowledge_points ID 解析为名称。
        qt_map: 可选的 {id: name} 映射，用于将 question_type_ids 解析为名称。
        """
        kp_ids = self.knowledge_points or []
        kp_details = []
        for kp_id in kp_ids:
            name = kp_map.get(kp_id, kp_id) if kp_map else kp_id
            kp_details.append({"id": kp_id, "name": name})

        qt_ids = self.question_type_ids or []
        qt_details = []
        for qt_id in qt_ids:
            name = qt_map.get(qt_id, qt_id) if qt_map else qt_id
            qt_details.append({"id": qt_id, "name": name})

        d = {
            "id": str(self.id),
            "index": self.index,
            "questionType": self.question_type,
            "questionBody": [b.to_dict() for b in self.question_body],
            "answer": [b.to_dict() for b in self.answer],
            "difficulty": self.difficulty or "",
            "categories": self.categories or [],
            "regions": self.regions or [],
            "scenario": self.scenario or "",
            "knowledgePoints": kp_ids,
            "knowledgePointDetails": kp_details,
            "description": self.description or "",
            "features": self.features or [],
            "questionTypeIds": qt_ids,
            "questionTypeDetails": qt_details,
            "sourceFile": self.source_file,
            "sessionId": self.session_id,
            "assetBaseUrl": self.asset_base_url,
            "sourceDocumentId": self.source_document_id or None,
            "sourceDocumentFilename": self.source_document_filename or None,
            "status": self.status or "pending_verification",
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
        if self.analysis:
            d["analysis"] = [b.to_dict() for b in self.analysis]
        if self.detailed_solution:
            d["detailedSolution"] = [b.to_dict() for b in self.detailed_solution]
        return d

    @classmethod
    def from_parsed(
        cls,
        data: dict,
        source_file: str = "",
        session_id: str = "",
        asset_base_url: str = "",
        source_document_id: str = "",
        source_document_filename: str = "",
        presets: dict = None,
    ):
        """从解析后的题目字典创建 Question 实例。presets 为预设值字典。"""
        def _make_blocks(items: list) -> list:
            blocks = []
            for item in (items or []):
                blocks.append(ContentBlock(
                    type=item.get("type", "text"),
                    content=item.get("content"),
                    url=item.get("url"),
                    width=item.get("width"),
                    height=item.get("height"),
                ))
            return blocks

        presets = presets or {}

        return cls(
            index=data.get("index", 0),
            question_type=data.get("questionType", ""),
            question_body=_make_blocks(data.get("questionBody", [])),
            answer=_make_blocks(data.get("answer", [])),
            analysis=_make_blocks(data.get("analysis", [])),
            detailed_solution=_make_blocks(data.get("detailedSolution", [])),
            difficulty=data.get("difficulty") or presets.get("difficulty", ""),
            categories=data.get("categories") or presets.get("categories", []),
            regions=data.get("regions") or presets.get("regions", []),
            scenario=data.get("scenario") or presets.get("scenario", ""),
            knowledge_points=data.get("knowledgePoints") or presets.get("knowledge_points", []),
            description=data.get("description", ""),
            features=data.get("features", []),
            question_type_ids=data.get("questionTypeIds", []),
            source_file=source_file,
            session_id=session_id,
            asset_base_url=asset_base_url,
            source_document_id=source_document_id or "",
            source_document_filename=source_document_filename or "",
        )
