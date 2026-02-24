# -*- coding: utf-8 -*-
"""
内容块（嵌入式文档，供 Question 使用）。
"""

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
