"""
Qdrant 客户端：本地模式 / 远程模式统一封装。
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from ..config_loader import get_qdrant_config, get_doubao_embedding_config

COLLECTION_NAME = "math_questions"

_client = None


def get_qdrant_client() -> QdrantClient:
    """获取 Qdrant 客户端，支持本地 path 和远程 url。"""
    global _client
    if _client is not None:
        return _client

    cfg = get_qdrant_config()
    url = cfg.get("url")
    path = cfg.get("path") or "./qdrant_local_data"

    if url:
        _client = QdrantClient(url=url)
    else:
        _client = QdrantClient(path=path)

    return _client


def get_collection_name() -> str:
    cfg = get_qdrant_config()
    return cfg.get("collection") or COLLECTION_NAME


def get_vector_dimension() -> int:
    return get_doubao_embedding_config().get("dimension", 1024)


def ensure_collection(client: QdrantClient = None):
    """确保 collection 存在，不存在则创建。"""
    client = client or get_qdrant_client()
    name = get_collection_name()
    dim = get_vector_dimension()

    collections = client.get_collections().collections
    names = [c.name for c in collections]
    if name not in names:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
