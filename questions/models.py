"""
MongoDB 模型定义（使用 mongoengine）。
"""

import datetime
import mongoengine as me


class ContentBlock(me.EmbeddedDocument):
    """内容块：文本、LaTeX 公式或图片。"""
    type = me.StringField(required=True, choices=("text", "latex", "image", "svg"))
    content = me.StringField()  # type=text/latex 时使用
    url = me.StringField()      # type=image/svg 时使用
    width = me.IntField()       # 图片在 Word 中的显示宽度（像素，可选）
    height = me.IntField()      # 图片在 Word 中的显示高度（像素，可选）

    def to_dict(self):
        d = {"type": self.type}
        if self.type in ("text", "latex"):
            d["content"] = self.content or ""
        elif self.type in ("image", "svg"):
            d["url"] = self.url or ""
            if self.width is not None:
                d["width"] = self.width
            if self.height is not None:
                d["height"] = self.height
        return d


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


class Question(me.Document):
    """数学题目。"""
    meta = {
        "collection": "questions",
        "ordering": ["-created_at"],
        "indexes": ["question_type", "source_file", "created_at",
                     "difficulty", "categories", "regions", "scenario"],
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

    def to_dict(self, kp_map=None):
        """
        序列化为字典。
        kp_map: 可选的 {id: name} 映射，用于将 knowledge_points ID 解析为名称。
        """
        kp_ids = self.knowledge_points or []
        kp_details = []
        for kp_id in kp_ids:
            name = kp_map.get(kp_id, kp_id) if kp_map else kp_id
            kp_details.append({"id": kp_id, "name": name})

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
            source_file=source_file,
            session_id=session_id,
            asset_base_url=asset_base_url,
            source_document_id=source_document_id or "",
            source_document_filename=source_document_filename or "",
        )


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


class KnowledgePoint(me.Document):
    """
    统一知识节点（替代原 KnowledgeCategory + KnowledgeNode）。
    任意节点都可拥有子节点，支持无限层级嵌套。
    """
    meta = {
        "collection": "knowledge_points",
        "ordering": ["order", "created_at"],
        "indexes": ["parent_id"],
    }
    parent_id = me.StringField(default="")  # 父节点 ID，空串表示顶级节点
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


# ── 保留旧模型以兼容已有数据（不再被新 API 使用） ──
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
