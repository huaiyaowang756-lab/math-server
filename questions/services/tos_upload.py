"""
TOS 对象存储上传服务。
将试题中的内容图片（如函数图象）上传到 TOS，文件名使用内容 MD5。
"""

import hashlib
from pathlib import Path
from typing import Optional

# 内容图扩展名：非公式图（WMF/EMF 为公式图）
CONTENT_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp")
# 公式图扩展名
FORMULA_IMAGE_EXTS = (".wmf", ".emf")


def _load_tos_config() -> Optional[dict]:
    """加载 TOS 配置，未配置或未启用则返回 None。"""
    try:
        import yaml
    except ImportError:
        return None

    base = Path(__file__).resolve().parent.parent.parent
    # 优先读取 config/tos.yaml（用户配置），其次 config/tos.yaml.example（模板）
    for name in ("tos.yaml", "tos.yaml.example"):
        config_path = base / "config" / name
        if config_path.exists():
            break
    else:
        return None

    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    tos = data.get("tos") if isinstance(data, dict) else None
    if not tos or not tos.get("enabled"):
        return None

    return tos


def _get_s3_client(config: dict):
    """创建 S3 兼容客户端（boto3）。"""
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=config.get("endpoint_url"),
        region_name=config.get("region", "auto"),
        aws_access_key_id=config.get("access_key_id"),
        aws_secret_access_key=config.get("secret_access_key"),
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
        ),
    )


def upload_content_image(local_path: Path) -> Optional[str]:
    """
    将内容图片上传到 TOS，使用内容 MD5 作为文件名。

    Args:
        local_path: 本地图片文件路径

    Returns:
        上传成功返回可访问的 URL；失败或未配置返回 None
    """
    config = _load_tos_config()
    if not config:
        return None

    if not local_path.exists():
        return None

    data = local_path.read_bytes()
    ext = local_path.suffix.lower()
    if ext not in CONTENT_IMAGE_EXTS:
        return None

    # 根据内容生成 MD5 文件名
    md5 = hashlib.md5(data).hexdigest()
    key = f"{config.get('prefix', '')}{md5}{ext}"

    try:
        client = _get_s3_client(config)
        bucket = config.get("bucket", "")
        endpoint = (config.get("endpoint_url") or "").lower()

        # 如果 endpoint 域名已包含 bucket（virtual-hosted），Bucket 参数传 bucket 即可
        # boto3 virtual 模式不会在路径再加 bucket
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=_get_content_type(ext),
        )
    except Exception as e:
        import sys
        print(f"TOS 上传失败 {local_path.name}: {e}", file=sys.stderr)
        return None

    # 拼接公开 URL
    base_url = config.get("public_base_url", "").rstrip("/")
    if not base_url:
        base_url = (config.get("endpoint_url") or "").rstrip("/")
    if base_url:
        return f"{base_url}/{key}"
    return key


def _get_content_type(ext: str) -> str:
    m = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".gif": "image/gif", ".webp": "image/webp"}
    return m.get(ext, "application/octet-stream")


def is_content_image_ext(ext: str) -> bool:
    """判断是否为内容图扩展名（非公式图）。"""
    return ext.lower() in CONTENT_IMAGE_EXTS


# 试卷/文档支持的扩展名
DOCUMENT_EXTS = (".doc", ".docx", ".pdf", ".ppt", ".pptx")
DOC_CONTENT_TYPES = {
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def upload_document_to_tos(file_bytes: bytes, filename: str) -> Optional[str]:
    """
    将文档（Word/PDF/PPT）上传到 TOS，使用内容 MD5 作为文件名。

    Args:
        file_bytes: 文件内容
        filename: 原始文件名（用于取扩展名）

    Returns:
        上传成功返回可访问的 URL；失败或未配置返回 None
    """
    config = _load_tos_config()
    if not config:
        return None

    ext = Path(filename).suffix.lower()
    if ext not in DOCUMENT_EXTS:
        return None

    md5 = hashlib.md5(file_bytes).hexdigest()
    prefix = (config.get("prefix") or "math-questions/images/").replace("images/", "documents/")
    key = f"{prefix}{md5}{ext}"

    try:
        client = _get_s3_client(config)
        bucket = config.get("bucket", "")
        content_type = DOC_CONTENT_TYPES.get(ext, "application/octet-stream")
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
    except Exception as e:
        import sys
        print(f"TOS 上传文档失败 {filename}: {e}", file=sys.stderr)
        return None

    base_url = config.get("public_base_url", "").rstrip("/")
    if not base_url:
        base_url = (config.get("endpoint_url") or "").rstrip("/")
    if base_url:
        return f"{base_url}/{key}"
    return key

