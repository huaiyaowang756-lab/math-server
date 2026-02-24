# -*- coding: utf-8 -*-
"""
MongoDB 模型定义（使用 mongoengine），按表维度拆分。
"""

from .content_block import ContentBlock
from .tag import Tag
from .document import Document
from .upload_task import UploadTask
from .question import Question
from .question_type_node import QuestionTypeNode
from .knowledge_point import KnowledgePoint
from .llm_model import LLMModel
from .legacy import KnowledgeCategory, KnowledgeNode

__all__ = [
    "ContentBlock",
    "Tag",
    "Document",
    "UploadTask",
    "Question",
    "QuestionTypeNode",
    "KnowledgePoint",
    "LLMModel",
    "KnowledgeCategory",
    "KnowledgeNode",
]
