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


class Question(me.Document):
    """数学题目。"""
    meta = {
        "collection": "questions",
        "ordering": ["-created_at"],
        "indexes": ["question_type", "source_file", "created_at"],
    }

    index = me.IntField(required=True)
    question_type = me.StringField(
        choices=("single_choice", "multiple_choice", "fill_blank", "solution")
    )
    question_body = me.EmbeddedDocumentListField(ContentBlock, default=list)
    answer = me.EmbeddedDocumentListField(ContentBlock, default=list)
    analysis = me.EmbeddedDocumentListField(ContentBlock, default=list)
    detailed_solution = me.EmbeddedDocumentListField(ContentBlock, default=list)

    source_file = me.StringField(default="")
    session_id = me.StringField(default="")
    asset_base_url = me.StringField(default="")

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

    def to_dict(self):
        d = {
            "id": str(self.id),
            "index": self.index,
            "questionType": self.question_type,
            "questionBody": [b.to_dict() for b in self.question_body],
            "answer": [b.to_dict() for b in self.answer],
            "sourceFile": self.source_file,
            "sessionId": self.session_id,
            "assetBaseUrl": self.asset_base_url,
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
    def from_parsed(cls, data: dict, source_file: str = "", session_id: str = "", asset_base_url: str = ""):
        """从解析后的题目字典创建 Question 实例。"""
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

        return cls(
            index=data.get("index", 0),
            question_type=data.get("questionType", ""),
            question_body=_make_blocks(data.get("questionBody", [])),
            answer=_make_blocks(data.get("answer", [])),
            analysis=_make_blocks(data.get("analysis", [])),
            detailed_solution=_make_blocks(data.get("detailedSolution", [])),
            source_file=source_file,
            session_id=session_id,
            asset_base_url=asset_base_url,
        )


class KnowledgeCategory(me.Document):
    """知识分类节点，可多级嵌套（父分类下可包含子分类）。"""
    meta = {
        "collection": "knowledge_categories",
        "ordering": ["order", "created_at"],
    }
    parent = me.ReferenceField("KnowledgeCategory", null=True, reverse_delete_rule=me.NULLIFY)
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
            "parentId": str(self.parent.id) if self.parent else None,
            "name": self.name,
            "order": self.order,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class KnowledgeNode(me.Document):
    """知识节点（属于某分类，可配置前置依赖）。"""
    meta = {
        "collection": "knowledge_nodes",
        "ordering": ["category", "order", "created_at"],
        "indexes": ["category"],
    }
    category = me.ReferenceField(KnowledgeCategory, required=True, reverse_delete_rule=me.CASCADE)
    name = me.StringField(required=True, max_length=200)
    order = me.IntField(default=0)
    # 前置依赖：当前节点依赖的其它知识节点 id 列表
    prerequisite_ids = me.ListField(me.ObjectIdField(), default=list)
    created_at = me.DateTimeField(default=datetime.datetime.utcnow)
    updated_at = me.DateTimeField(default=datetime.datetime.utcnow)

    def save(self, *args, **kwargs):
        self.updated_at = datetime.datetime.utcnow()
        return super().save(*args, **kwargs)

    def to_dict(self):
        return {
            "id": str(self.id),
            "categoryId": str(self.category.id) if self.category else None,
            "name": self.name,
            "order": self.order,
            "prerequisiteIds": [str(oid) for oid in (self.prerequisite_ids or [])],
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
