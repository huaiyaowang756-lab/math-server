"""
math_server 项目初始化：连接 MongoDB。
"""

import mongoengine
from django.conf import settings


def _connect_mongo():
    try:
        mongoengine.connect(
            db=getattr(settings, "MONGO_DB_NAME", "math_questions"),
            host=getattr(settings, "MONGO_HOST", "localhost"),
            port=getattr(settings, "MONGO_PORT", 27017),
        )
    except Exception as e:
        import sys
        print(f"Warning: MongoDB 连接失败: {e}", file=sys.stderr)
        print("  请确保 MongoDB 正在运行: brew services start mongodb-community", file=sys.stderr)


# Django 加载时自动连接 MongoDB
try:
    _connect_mongo()
except Exception:
    pass
