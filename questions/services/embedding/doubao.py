"""
豆包向量嵌入服务：使用火山引擎 Ark SDK multimodal_embeddings 接口。
参考：火山引擎控制台 - 快捷 API 接入 - Doubao-embedding-vision
"""

import os
import time
from typing import List

from ..config_loader import get_doubao_embedding_config


def _get_ark_client(config: dict):
    """创建 Ark 客户端。禁用代理时设置 NO_PROXY 环境变量。"""
    from volcenginesdkarkruntime import Ark

    api_key = config.get("api_key") or os.environ.get("ARK_API_KEY")
    if not api_key:
        raise ValueError("未配置 DOUBAO_EMBEDDING_API_KEY 或 ARK_API_KEY")

    if config.get("disable_proxy"):
        os.environ["NO_PROXY"] = "ark.cn-beijing.volces.com,*.volces.com"

    return Ark(api_key=api_key)


def _to_input_items(texts: List[str]) -> List[dict]:
    """将文本列表转为 multimodal_embeddings 要求的 input 格式。"""
    return [{"type": "text", "text": (t or "(无描述)")} for t in texts]


def _extract_embedding(item) -> List[float] | None:
    """从单条结果中提取 embedding 向量。"""
    if item is None:
        return None
    if isinstance(item, (list, tuple)) and len(item) > 0 and isinstance(item[0], (int, float)):
        return list(item)
    if isinstance(item, dict):
        emb = item.get("embedding") or item.get("values") or item.get("embedding_vector")
        if emb is not None:
            return list(emb) if hasattr(emb, "__iter__") and not isinstance(emb, str) else emb
        return None
    emb = getattr(item, "embedding", None) or getattr(item, "values", None)
    if emb is not None:
        return list(emb) if hasattr(emb, "__iter__") and not isinstance(emb, str) else emb
    return None


def _parse_embeddings(resp) -> List[List[float]]:
    """
    从 multimodal_embeddings 响应中解析 embedding 列表。
    Ark SDK MultimodalEmbeddingResponse：data 可能是 List[MultimodalEmbedding] 或单个对象。
    """
    raw_data = getattr(resp, "data", None)

    # 转成可迭代的 items
    if isinstance(raw_data, list):
        items = raw_data
    elif raw_data is not None:
        # 单对象 或 需从 model_dump 解析
        emb = _extract_embedding(raw_data)
        if emb is not None:
            return [emb]
        if hasattr(raw_data, "embedding"):
            return [list(getattr(raw_data, "embedding", []))]
        items = [raw_data]
    else:
        d = resp.model_dump() if hasattr(resp, "model_dump") else {}
        raw_data = d.get("data")
        if isinstance(raw_data, list):
            items = raw_data
        elif raw_data is not None:
            items = [raw_data]
        else:
            items = []

    result = []
    for i, item in enumerate(items):
        emb = _extract_embedding(item)
        if emb is not None:
            idx = i
            if isinstance(item, dict):
                idx = item.get("index", i)
            elif hasattr(item, "index"):
                idx = getattr(item, "index", i)
            result.append((idx, emb))
    result.sort(key=lambda x: x[0])
    return [r[1] for r in result]


def get_embedding(text: str) -> List[float]:
    """
    对单条文本生成 embedding 向量。

    Args:
        text: 输入文本

    Returns:
        向量列表
    """
    config = get_doubao_embedding_config()
    client = _get_ark_client(config)
    model = config.get("model") or "doubao-embedding-vision-250615"

    input_items = _to_input_items([text])
    resp = client.multimodal_embeddings.create(model=model, input=input_items)
    vecs = _parse_embeddings(resp)
    if not vecs:
        raise ValueError("Embedding API 返回空结果")
    return vecs[0]


def get_embeddings_batch(texts: List[str], batch_size: int = None) -> List[List[float]]:
    """
    批量获取 embedding。豆包 multimodal_embeddings 每次只返回 1 个向量，故逐条请求。

    Args:
        texts: 文本列表
        batch_size: 忽略（保留参数兼容），实际每条单独请求

    Returns:
        向量列表，与 texts 一一对应
    """
    config = get_doubao_embedding_config()
    batch_delay = float(config.get("batch_delay") or 1.0)
    max_retries = int(config.get("max_retries") or 3)

    client = _get_ark_client(config)
    model = config.get("model") or "doubao-embedding-vision-250615"

    results = []
    for i, text in enumerate(texts):
        input_items = _to_input_items([text])

        for attempt in range(max_retries):
            try:
                resp = client.multimodal_embeddings.create(model=model, input=input_items)
                vecs = _parse_embeddings(resp)
                if vecs:
                    results.append(vecs[0])
                else:
                    raise ValueError("Embedding API 返回空结果")
                break
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "too many" in err_str or "rate" in err_str:
                    if attempt < max_retries - 1:
                        wait = (2 ** attempt) * batch_delay
                        time.sleep(wait)
                        continue
                raise

        if i + 1 < len(texts):
            time.sleep(batch_delay)

    return results
