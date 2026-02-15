"""
试卷解析异步任务：在后台线程中执行 process_docx，并更新 UploadTask 状态。
"""

import threading
from pathlib import Path

from django.conf import settings

from .pipeline import process_docx
from ..models import UploadTask


def run_parse_task(task_id: str):
    """
    在后台线程中执行 docx 解析，更新任务状态和结果。
    """
    try:
        task = UploadTask.objects.get(id=task_id)
    except UploadTask.DoesNotExist:
        return

    task.status = "processing"
    task.progress = 10
    task.save()

    docx_path = Path(task.docx_path)
    if not docx_path.exists():
        task.status = "failed"
        task.progress = 0
        task.error_msg = "临时文件不存在"
        task.save()
        return

    try:
        task.progress = 30
        task.save()

        result = process_docx(
            docx_path=docx_path,
            use_latex=task.use_latex,
            source_filename=task.source_filename,
        )

        task.status = "completed"
        task.progress = 100
        task.result = result
        task.error_msg = ""
        task.save()
    except Exception as e:
        task.status = "failed"
        task.progress = 0
        task.error_msg = str(e)
        task.result = {}
        task.save()
    finally:
        try:
            docx_path.unlink(missing_ok=True)
        except Exception:
            pass


def start_parse_task(task_id: str):
    """启动后台解析任务。"""
    thread = threading.Thread(target=run_parse_task, args=(task_id,), daemon=True)
    thread.start()
