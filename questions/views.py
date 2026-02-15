"""
数学题目 API 视图。
"""

import json
import shutil
import tempfile
import urllib.request
import uuid
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Question, UploadTask
from .services.latex_converter import recognize_formula_image
from .services.async_task import start_parse_task

# 中文/英文等直接输出为原文，不转成 \uXXXX
JSON_OPTIONS = {"ensure_ascii": False}


def _json_body(request):
    """解析请求体中的 JSON。"""
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None


@csrf_exempt
@require_http_methods(["POST"])
def recognize_formula(request):
    """
    上传公式截图，识别为 LaTeX。
    POST /api/formula/recognize/
    - multipart/form-data: file (图片，支持 png/jpg/jpeg)
    - 返回 { "latex": "..." } 或 { "error": "..." }
    """
    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "请上传图片文件"}, status=400, json_dumps_params=JSON_OPTIONS)

    name = (uploaded.name or "").lower()
    if not any(name.endswith(ext) for ext in (".png", ".jpg", ".jpeg")):
        return JsonResponse({"error": "仅支持 PNG、JPG、JPEG 格式"}, status=400, json_dumps_params=JSON_OPTIONS)

    suffix = Path(uploaded.name).suffix or ".png"
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in uploaded.chunks():
                tmp.write(chunk)
            tmp_path = Path(tmp.name)
        latex = recognize_formula_image(tmp_path)
        if latex is None:
            return JsonResponse(
                {"error": "公式识别失败，请确保图片清晰且为数学公式"},
                status=422,
                json_dumps_params=JSON_OPTIONS,
            )
        return JsonResponse({"latex": latex}, json_dumps_params=JSON_OPTIONS)
    except Exception as e:
        return JsonResponse(
            {"error": f"识别异常: {str(e)}"},
            status=500,
            json_dumps_params=JSON_OPTIONS,
        )
    finally:
        try:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


@csrf_exempt
@require_http_methods(["POST"])
def recognize_formula_url(request):
    """
    通过图片 URL 识别公式为 LaTeX（用于编辑模式下将图片块转为公式）。
    POST /api/formula/recognize-url/
    - JSON body: { "url": "https://..." }
    - 返回 { "latex": "..." } 或 { "error": "..." }
    """
    data = _json_body(request)
    if not data or not data.get("url"):
        return JsonResponse(
            {"error": "请提供图片 url"},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )

    image_url = data["url"].strip()
    tmp_path = None

    try:
        # 判断是否为绝对 URL
        if image_url.startswith(("http://", "https://")):
            # 从网络下载图片
            req = urllib.request.Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                content_type = resp.headers.get("Content-Type", "")
                if "image" not in content_type and not image_url.lower().endswith(
                    (".png", ".jpg", ".jpeg")
                ):
                    return JsonResponse(
                        {"error": "URL 不是有效的图片"},
                        status=400,
                        json_dumps_params=JSON_OPTIONS,
                    )
                img_data = resp.read()
            suffix = ".png"
            for ext in (".jpg", ".jpeg", ".png"):
                if image_url.lower().endswith(ext):
                    suffix = ext
                    break
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(img_data)
                tmp_path = Path(tmp.name)
        else:
            return JsonResponse(
                {"error": "仅支持 http/https 图片 URL"},
                status=400,
                json_dumps_params=JSON_OPTIONS,
            )

        latex = recognize_formula_image(tmp_path)
        if latex is None:
            return JsonResponse(
                {"error": "公式识别失败，请确保图片清晰且为数学公式"},
                status=422,
                json_dumps_params=JSON_OPTIONS,
            )
        return JsonResponse({"latex": latex}, json_dumps_params=JSON_OPTIONS)

    except urllib.error.URLError as e:
        return JsonResponse(
            {"error": f"下载图片失败: {str(e)}"},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )
    except Exception as e:
        return JsonResponse(
            {"error": f"识别异常: {str(e)}"},
            status=500,
            json_dumps_params=JSON_OPTIONS,
        )
    finally:
        try:
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


@csrf_exempt
@require_http_methods(["POST"])
def upload_docx(request):
    """
    上传 docx 文件并创建异步解析任务。
    POST /api/upload/
    - multipart/form-data: file (docx), use_latex (0/1)
    - 立即返回 task_id，解析在后台异步执行
    """
    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "请上传 docx 文件"}, status=400, json_dumps_params=JSON_OPTIONS)

    if not uploaded.name.endswith((".docx", ".doc")):
        return JsonResponse({"error": "仅支持 .docx 文件"}, status=400, json_dumps_params=JSON_OPTIONS)

    use_latex = request.POST.get("use_latex", "1") != "0"

    # 保存到 media/uploads 下的临时目录，任务完成后由 async_task 删除
    task_dir = Path(settings.MEDIA_ROOT) / "uploads" / "_tasks"
    task_dir.mkdir(parents=True, exist_ok=True)
    tmp_name = f"{uuid.uuid4().hex}.docx"
    tmp_path = task_dir / tmp_name

    try:
        with open(tmp_path, "wb") as f:
            for chunk in uploaded.chunks():
                f.write(chunk)
    except Exception as e:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return JsonResponse({"error": f"保存文件失败: {str(e)}"}, status=500, json_dumps_params=JSON_OPTIONS)

    task = UploadTask(
        source_filename=uploaded.name,
        status="pending",
        progress=0,
        use_latex=use_latex,
        docx_path=str(tmp_path.resolve()),
    )
    task.save()

    start_parse_task(str(task.id))

    return JsonResponse({
        "task_id": str(task.id),
        "status": task.status,
        "source_filename": task.source_filename,
    }, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["GET"])
def list_upload_tasks(request):
    """
    获取上传解析任务列表。
    GET /api/upload/tasks/?limit=20
    """
    limit = min(int(request.GET.get("limit", 20)), 100)
    tasks = UploadTask.objects.order_by("-created_at").limit(limit)
    return JsonResponse({
        "tasks": [t.to_dict() for t in tasks],
    }, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
def get_or_delete_upload_task(request, task_id):
    """
    获取或删除单个任务。
    GET /api/upload/tasks/<task_id>/  — 获取详情
    DELETE /api/upload/tasks/<task_id>/  — 删除记录及关联文件
    """
    try:
        task = UploadTask.objects.get(id=task_id)
    except UploadTask.DoesNotExist:
        return JsonResponse({"error": "任务不存在"}, status=404, json_dumps_params=JSON_OPTIONS)

    if request.method == "DELETE":
        session_id = (task.result or {}).get("session_id", "")
        docx_path = Path(task.docx_path) if task.docx_path else None

        task.delete()

        if docx_path and docx_path.exists():
            try:
                docx_path.unlink(missing_ok=True)
            except Exception:
                pass

        if session_id:
            session_dir = Path(settings.MEDIA_ROOT) / "uploads" / session_id
            if session_dir.is_dir():
                try:
                    shutil.rmtree(session_dir, ignore_errors=True)
                except Exception:
                    pass

        return JsonResponse({"success": True}, json_dumps_params=JSON_OPTIONS)

    return JsonResponse({"task": task.to_dict()}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["POST"])
def save_questions(request):
    """
    保存确认后的题目到 MongoDB。
    POST /api/questions/save/
    - JSON body: { session_id, source_filename, asset_base_url, questions: [...] }
    """
    data = _json_body(request)
    if not data:
        return JsonResponse({"error": "无效的请求体"}, status=400, json_dumps_params=JSON_OPTIONS)

    questions_data = data.get("questions", [])
    if not questions_data:
        return JsonResponse({"error": "题目列表为空"}, status=400, json_dumps_params=JSON_OPTIONS)

    session_id = data.get("session_id", "")
    source_file = data.get("source_filename", "")
    asset_base_url = data.get("asset_base_url", "")

    saved_ids = []
    for q_data in questions_data:
        q = Question.from_parsed(
            q_data,
            source_file=source_file,
            session_id=session_id,
            asset_base_url=asset_base_url,
        )
        q.save()
        saved_ids.append(str(q.id))

    return JsonResponse({
        "success": True,
        "count": len(saved_ids),
        "ids": saved_ids,
    }, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["GET"])
def list_questions(request):
    """
    获取已保存的题目列表（分页）。
    GET /api/questions/?page=1&page_size=20&question_type=single_choice&status=pending_verification
    """
    page = int(request.GET.get("page", 1))
    page_size = int(request.GET.get("page_size", 20))
    question_type = request.GET.get("question_type", "")
    status = request.GET.get("status", "")

    qs = Question.objects
    if question_type:
        qs = qs.filter(question_type=question_type)
    if status and status in ("pending_verification", "online"):
        qs = qs.filter(status=status)

    total = qs.count()
    offset = (page - 1) * page_size
    questions = qs.skip(offset).limit(page_size)

    return JsonResponse({
        "questions": [q.to_dict() for q in questions],
        "total": total,
        "page": page,
        "page_size": page_size,
    }, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["GET"])
def get_question(request, question_id):
    """
    获取单个题目详情。
    GET /api/questions/<id>/
    """
    try:
        q = Question.objects.get(id=question_id)
        return JsonResponse({"question": q.to_dict()}, json_dumps_params=JSON_OPTIONS)
    except Question.DoesNotExist:
        return JsonResponse({"error": "题目不存在"}, status=404, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["PUT"])
def update_question(request, question_id):
    """
    更新题目。
    PUT /api/questions/<id>/
    """
    data = _json_body(request)
    if not data:
        return JsonResponse({"error": "无效的请求体"}, status=400, json_dumps_params=JSON_OPTIONS)

    try:
        q = Question.objects.get(id=question_id)
    except Question.DoesNotExist:
        return JsonResponse({"error": "题目不存在"}, status=404, json_dumps_params=JSON_OPTIONS)

    def _make_blocks(items):
        from .models import ContentBlock
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

    if "questionBody" in data:
        q.question_body = _make_blocks(data["questionBody"])
    if "answer" in data:
        q.answer = _make_blocks(data["answer"])
    if "analysis" in data:
        q.analysis = _make_blocks(data["analysis"])
    if "detailedSolution" in data:
        q.detailed_solution = _make_blocks(data["detailedSolution"])
    if "questionType" in data:
        q.question_type = data["questionType"]
    if "status" in data and data["status"] in ("pending_verification", "online"):
        q.status = data["status"]

    q.save()
    return JsonResponse({"success": True, "question": q.to_dict()}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_question(request, question_id):
    """
    删除题目。
    DELETE /api/questions/<id>/
    """
    try:
        q = Question.objects.get(id=question_id)
        q.delete()
        return JsonResponse({"success": True}, json_dumps_params=JSON_OPTIONS)
    except Question.DoesNotExist:
        return JsonResponse({"error": "题目不存在"}, status=404, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_batch(request):
    """
    批量删除题目。
    DELETE /api/questions/batch/
    JSON body: { ids: [...] }
    """
    data = _json_body(request)
    if not data:
        return JsonResponse({"error": "无效的请求体"}, status=400, json_dumps_params=JSON_OPTIONS)

    ids = data.get("ids", [])
    if not ids:
        return JsonResponse({"error": "ID 列表为空"}, status=400, json_dumps_params=JSON_OPTIONS)

    deleted = 0
    for qid in ids:
        try:
            q = Question.objects.get(id=qid)
            q.delete()
            deleted += 1
        except Question.DoesNotExist:
            continue

    return JsonResponse({"success": True, "deleted": deleted}, json_dumps_params=JSON_OPTIONS)
