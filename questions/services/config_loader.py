"""
配置加载：从 config/tos.yaml 读取 doubao、doubao_embedding 等配置。
"""

from pathlib import Path
from typing import Optional


def _load_yaml_config() -> Optional[dict]:
    """加载 config/tos.yaml 或 tos.yaml.example。"""
    try:
        import yaml
    except ImportError:
        return None

    base = Path(__file__).resolve().parent.parent.parent
    for name in ("tos.yaml", "tos.yaml.example"):
        config_path = base / "config" / name
        if config_path.exists():
            data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else None
    return None


def get_doubao_config() -> dict:
    """获取豆包大模型配置（LLM）。"""
    data = _load_yaml_config()
    doubao = (data or {}).get("doubao") or {}
    return {
        "api_key": doubao.get("DOUBAO_API_KEY") or "",
        "model": doubao.get("LLM_MODEL") or "doubao-1-5-pro-32k-250115",
        "disable_proxy": bool(doubao.get("DISABLE_PROXY", False)),
    }


def get_doubao_embedding_config() -> dict:
    """获取豆包向量嵌入配置。"""
    data = _load_yaml_config()
    emb = (data or {}).get("doubao_embedding") or {}
    return {
        "api_key": emb.get("DOUBAO_EMBEDDING_API_KEY") or "",
        "model": emb.get("DOUBAO_EMBEDDING_MODEL") or "doubao-embedding-vision-251215",
        "base_url": emb.get("BASE_URL") or "https://ark.cn-beijing.volces.com/api/v3",
        "dimension": int(emb.get("EMBEDDING_DIM") or 2048),
        "disable_proxy": bool(emb.get("DISABLE_PROXY", False)),
        "batch_size": emb.get("BATCH_SIZE"),
        "batch_delay": emb.get("BATCH_DELAY"),
        "max_retries": emb.get("MAX_RETRIES"),
    }


def get_qdrant_config() -> dict:
    """获取 Qdrant 配置，支持本地模式与远程模式。"""
    import os
    return {
        "url": os.environ.get("QDRANT_URL"),
        "path": os.environ.get("QDRANT_PATH") or "./qdrant_local_data",
        "collection": os.environ.get("QDRANT_COLLECTION") or "math_questions",
    }
