"""
Word 解析三阶段流水线：

阶段一：按原始 type 解析（text、wmf、png、jpeg 等），不做转换
阶段二：专门处理 WMF 公式 -> LaTeX；PNG/JPEG 等 -> 保存到 TOS；text 不处理
阶段三：返回结果，供前端确认保存
"""

import shutil
import uuid
from pathlib import Path

from django.conf import settings

from .docx_parser import parse_docx
from .image_converter import convert_wmf_to_png, replace_wmf_urls
from .latex_converter import convert_to_latex
from .tos_upload import upload_content_image, is_content_image_ext

# 公式图扩展名（WMF/EMF），阶段二转为 LaTeX
FORMULA_IMAGE_EXTS = (".wmf", ".emf")


def process_docx(
    docx_path: Path,
    use_latex: bool = True,
    source_filename: str = "",
) -> dict:
    """
    处理上传的 docx 文件，三阶段解析后返回题目数据。

    Args:
        docx_path: docx 文件路径
        use_latex: 是否将 WMF 公式转为 LaTeX（True 则转 LaTeX，False 则转 PNG）
        source_filename: 原始文件名（用于记录来源）

    Returns:
        {
            "session_id": str,
            "source_filename": str,
            "questions": list[dict],
            "asset_base_url": str,
            "stats": {...},
        }
    """
    session_id = uuid.uuid4().hex[:12]
    work_dir = Path(settings.MEDIA_ROOT) / "uploads" / session_id
    work_dir.mkdir(parents=True, exist_ok=True)

    dest_docx = work_dir / "source.docx"
    if docx_path.resolve() != dest_docx.resolve():
        shutil.copy2(docx_path, dest_docx)

    # ========== 阶段一：按原始 type 解析（text、wmf、png、jpeg 等） ==========
    questions = parse_docx(dest_docx, work_dir)

    # ========== 阶段二：WMF -> LaTeX；PNG/JPEG -> TOS ==========
    tos_stats = {"total": 0, "uploaded": 0, "skipped": 0, "failed": 0}
    wmf_stats = {"total": 0, "success": 0, "method": None, "trimmed": 0}
    latex_stats = None

    doc_assets = work_dir / "doc-assets"

    # 2a) PNG/JPEG 等内容图 -> 上传 TOS（不改变 type，只更新 url）
    for q in questions:
        for key in ("questionBody", "answer", "analysis", "detailedSolution"):
            for b in q.get(key) or []:
                if b.get("type") != "image":
                    continue
                url = b.get("url", "")
                ext = Path(url).suffix.lower()
                if not is_content_image_ext(ext):
                    continue
                tos_stats["total"] += 1
                local_path = doc_assets / Path(url).name
                if not local_path.exists():
                    tos_stats["skipped"] += 1
                    continue
                tos_url = upload_content_image(local_path)
                if tos_url:
                    b["url"] = tos_url
                    tos_stats["uploaded"] += 1
                else:
                    tos_stats["failed"] += 1

    # 2b) WMF 公式 -> PNG，再（可选）-> LaTeX
    wmf_stats = convert_wmf_to_png(work_dir)
    questions = replace_wmf_urls(questions)
    if use_latex:
        latex_stats = convert_to_latex(questions, work_dir)

    # ========== 阶段三：返回结果 ==========
    asset_base_url = f"{settings.MEDIA_URL}uploads/{session_id}/"

    return {
        "session_id": session_id,
        "source_filename": source_filename or docx_path.name,
        "questions": questions,
        "asset_base_url": asset_base_url,
        "stats": {
            "question_count": len(questions),
            "tos_upload": tos_stats,
            "wmf_conversion": wmf_stats,
            "latex_conversion": latex_stats,
        },
    }
