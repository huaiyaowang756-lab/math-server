"""
试卷/文档管理 API。
支持 Word、PDF、PPT 上传到 TOS，并生成数据库记录。
"""

import json
import subprocess
import tempfile
import urllib.request
import uuid
from pathlib import Path

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Document, UploadTask
from .services.async_task import start_parse_task
from .services.tos_upload import upload_document_to_tos, DOCUMENT_EXTS

JSON_OPTIONS = {"ensure_ascii": False}


def _json_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return None


def _collect_descendant_ids(folder_id):
    ids = []
    children = Document.objects.filter(parent_id=str(folder_id))
    for child in children:
        cid = str(child.id)
        ids.append(cid)
        if child.is_folder:
            ids.extend(_collect_descendant_ids(cid))
    return ids


def _copy_document_tree(source_doc: Document, target_parent_id: str):
    copied = Document(
        parent_id=target_parent_id,
        is_folder=bool(source_doc.is_folder),
        url=source_doc.url or "",
        filename=source_doc.filename or "",
        description=source_doc.description or "",
        doc_type=source_doc.doc_type or "other",
        tags=source_doc.tags or [],
        video_url=source_doc.video_url or "",
    )
    copied.save()
    if source_doc.is_folder:
        children = list(Document.objects.filter(parent_id=str(source_doc.id)))
        for child in children:
            _copy_document_tree(child, str(copied.id))
    return copied


@csrf_exempt
@require_http_methods(["POST"])
def upload_document(request):
    """
    上传文档到 TOS 并创建记录。
    POST /api/documents/upload/
    - multipart/form-data: file (必填), description, doc_type, tags (JSON 数组), video_url, parent_id
    """
    uploaded = request.FILES.get("file")
    if not uploaded:
        return JsonResponse({"error": "请上传文件"}, status=400, json_dumps_params=JSON_OPTIONS)

    ext = Path(uploaded.name).suffix.lower()
    if ext not in DOCUMENT_EXTS:
        return JsonResponse(
            {"error": f"仅支持 Word、PDF、PPT 格式：{', '.join(DOCUMENT_EXTS)}"},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )

    file_bytes = b"".join(uploaded.chunks())
    url = upload_document_to_tos(file_bytes, uploaded.name)
    if not url:
        return JsonResponse(
            {"error": "文档上传到存储失败，请检查 TOS 配置"},
            status=500,
            json_dumps_params=JSON_OPTIONS,
        )

    description = request.POST.get("description", "").strip()
    doc_type = request.POST.get("doc_type", "other").strip().lower()
    if doc_type not in ("exam", "topic", "other"):
        doc_type = "other"

    tags = []
    tags_raw = request.POST.get("tags", "")
    if tags_raw:
        try:
            tags = json.loads(tags_raw)
            if isinstance(tags, list):
                tags = [str(t).strip() for t in tags if t]
            else:
                tags = []
        except Exception:
            pass

    video_url = request.POST.get("video_url", "").strip()
    parent_id = request.POST.get("parent_id", "").strip()
    if parent_id:
        parent = Document.objects.filter(id=parent_id).first()
        if not parent or not parent.is_folder:
            return JsonResponse({"error": "父文件夹不存在"}, status=400, json_dumps_params=JSON_OPTIONS)

    doc = Document(
        parent_id=parent_id,
        is_folder=False,
        url=url,
        filename=uploaded.name,
        description=description,
        doc_type=doc_type,
        tags=tags,
        video_url=video_url,
        question_status="unparsed",
    )
    doc.save()
    return JsonResponse({"success": True, "document": doc.to_dict()}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["GET"])
def list_documents(request):
    """
    GET /api/documents/?page=1&page_size=20&doc_type=exam&parent_id=
    """
    page = max(1, int(request.GET.get("page", 1)))
    page_size = min(100, max(1, int(request.GET.get("page_size", 20))))
    doc_type = request.GET.get("doc_type", "").strip()
    question_status = request.GET.get("question_status", "").strip()
    tag = request.GET.get("tag", "").strip()
    parent_id = request.GET.get("parent_id", "").strip()

    qs = Document.objects.filter(parent_id=parent_id)
    if doc_type and doc_type in ("exam", "topic", "other"):
        qs = qs.filter(doc_type=doc_type, is_folder=False)
    if question_status and question_status in ("unparsed", "unimported", "imported"):
        qs = qs.filter(question_status=question_status, is_folder=False)
    if tag:
        qs = qs.filter(tags=tag)
    docs_all = list(qs)
    docs_all.sort(key=lambda d: (0 if d.is_folder else 1, (d.filename or "").lower(), -d.created_at.timestamp()))
    total = len(docs_all)
    offset = (page - 1) * page_size
    docs = docs_all[offset: offset + page_size]
    return JsonResponse(
        {
            "documents": [d.to_dict() for d in docs],
            "total": total,
            "page": page,
            "pageSize": page_size,
        },
        json_dumps_params=JSON_OPTIONS,
    )


@csrf_exempt
@require_http_methods(["POST"])
def create_folder(request):
    """
    POST /api/documents/folders/create/
    JSON body: { name, parentId? }
    """
    data = _json_body(request)
    if not data or not (data.get("name") or "").strip():
        return JsonResponse({"error": "文件夹名称必填"}, status=400, json_dumps_params=JSON_OPTIONS)
    parent_id = (data.get("parentId") or "").strip()
    if parent_id:
        parent = Document.objects.filter(id=parent_id).first()
        if not parent or not parent.is_folder:
            return JsonResponse({"error": "父文件夹不存在"}, status=400, json_dumps_params=JSON_OPTIONS)
    folder = Document(
        parent_id=parent_id,
        is_folder=True,
        filename=(data.get("name") or "").strip(),
        url="",
        description="",
        doc_type="other",
        tags=[],
        video_url="",
    )
    folder.save()
    return JsonResponse({"success": True, "folder": folder.to_dict()}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["GET"])
def get_document(request, doc_id):
    try:
        doc = Document.objects.get(id=doc_id)
        return JsonResponse({"document": doc.to_dict()}, json_dumps_params=JSON_OPTIONS)
    except Document.DoesNotExist:
        return JsonResponse({"error": "文档不存在"}, status=404, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["PUT"])
def update_document(request, doc_id):
    data = _json_body(request)
    if not data:
        return JsonResponse({"error": "无效的请求体"}, status=400, json_dumps_params=JSON_OPTIONS)

    try:
        doc = Document.objects.get(id=doc_id)
    except Document.DoesNotExist:
        return JsonResponse({"error": "文档不存在"}, status=404, json_dumps_params=JSON_OPTIONS)

    if "description" in data:
        doc.description = str(data["description"] or "").strip()
    if "docType" in data:
        v = str(data["docType"] or "").strip().lower()
        if v in ("exam", "topic", "other"):
            doc.doc_type = v
    if "tags" in data:
        tags = data["tags"]
        doc.tags = [str(t).strip() for t in tags] if isinstance(tags, list) else []
    if "videoUrl" in data:
        doc.video_url = str(data["videoUrl"] or "").strip()
    if "filename" in data:
        name = str(data["filename"] or "").strip()
        if not name:
            return JsonResponse({"error": "名称不能为空"}, status=400, json_dumps_params=JSON_OPTIONS)
        if doc.is_folder:
            doc.filename = name
        else:
            # 试卷名称不允许修改后缀名：后缀固定为原文件后缀
            old_ext = Path(doc.filename or "").suffix or Path(doc.url or "").suffix
            base_name = Path(name).stem
            doc.filename = f"{base_name}{old_ext}" if old_ext else base_name
    if "parentId" in data:
        new_parent_id = str(data["parentId"] or "").strip()
        if new_parent_id == str(doc.id):
            return JsonResponse({"error": "不能将父文件夹设为自身"}, status=400, json_dumps_params=JSON_OPTIONS)
        if new_parent_id:
            parent = Document.objects.filter(id=new_parent_id).first()
            if not parent or not parent.is_folder:
                return JsonResponse({"error": "父文件夹不存在"}, status=400, json_dumps_params=JSON_OPTIONS)
            if doc.is_folder:
                descendants = set(_collect_descendant_ids(str(doc.id)))
                if new_parent_id in descendants:
                    return JsonResponse({"error": "不能移动到子文件夹下"}, status=400, json_dumps_params=JSON_OPTIONS)
        doc.parent_id = new_parent_id

    doc.save()
    return JsonResponse({"success": True, "document": doc.to_dict()}, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["DELETE"])
def delete_document(request, doc_id):
    try:
        doc = Document.objects.get(id=doc_id)
        if doc.is_folder:
            descendants = _collect_descendant_ids(str(doc.id))
            for cid in descendants:
                try:
                    Document.objects.get(id=cid).delete()
                except Document.DoesNotExist:
                    pass
        doc.delete()
        return JsonResponse({"success": True}, json_dumps_params=JSON_OPTIONS)
    except Document.DoesNotExist:
        return JsonResponse({"error": "文档不存在"}, status=404, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["GET"])
def download_document(request, doc_id):
    """
    代理下载文档，使用原始文件名（Content-Disposition）。
    GET /api/documents/<id>/download/
    """
    try:
        doc = Document.objects.get(id=doc_id)
    except Document.DoesNotExist:
        return JsonResponse({"error": "文档不存在"}, status=404, json_dumps_params=JSON_OPTIONS)
    if doc.is_folder:
        return JsonResponse({"error": "文件夹不支持下载"}, status=400, json_dumps_params=JSON_OPTIONS)

    filename = doc.filename or "document"
    if not Path(filename).suffix:
        ext = Path(doc.url).suffix
        if ext:
            filename += ext

    try:
        req = urllib.request.Request(doc.url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read()
            content_type = resp.headers.get("Content-Type", "application/octet-stream")
    except Exception as e:
        return JsonResponse(
            {"error": f"获取文档失败: {str(e)}"},
            status=502,
            json_dumps_params=JSON_OPTIONS,
        )

    from urllib.parse import quote
    response = HttpResponse(data, content_type=content_type)
    response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
    return response


def _find_soffice():
    """查找 LibreOffice soffice 可执行文件。"""
    for cmd in ("libreoffice", "soffice", "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        try:
            subprocess.run([cmd, "--version"], capture_output=True, check=True, timeout=10)
            return cmd
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return None


def _convert_to_pdf(soffice_cmd: str, input_path: Path) -> bytes | None:
    """使用 LibreOffice 将文档转为 PDF，返回 PDF 字节。"""
    out_dir = input_path.parent
    r = subprocess.run(
        [soffice_cmd, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(input_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if r.returncode != 0:
        return None
    pdf_path = input_path.with_suffix(".pdf")
    if not pdf_path.exists():
        return None
    return pdf_path.read_bytes()


@csrf_exempt
@require_http_methods(["GET"])
def preview_document(request, doc_id):
    """
    预览文档：转为 PDF 后返回二进制流，供 iframe 内嵌显示。
    GET /api/documents/<id>/preview-pdf/
    支持 .doc, .docx, .ppt, .pptx 转换；.pdf 直接返回。
    """
    try:
        doc = Document.objects.get(id=doc_id)
    except Document.DoesNotExist:
        return JsonResponse({"error": "文档不存在"}, status=404, json_dumps_params=JSON_OPTIONS)
    if doc.is_folder:
        return JsonResponse({"error": "文件夹不支持预览"}, status=400, json_dumps_params=JSON_OPTIONS)

    ext = Path(doc.filename or doc.url or "").suffix.lower()
    if ext in (".pdf",):
        # PDF 直接代理返回
        try:
            req = urllib.request.Request(doc.url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
        except Exception as e:
            return JsonResponse(
                {"error": f"获取文档失败: {str(e)}"},
                status=502,
                json_dumps_params=JSON_OPTIONS,
            )
        response = HttpResponse(data, content_type="application/pdf")
        response["Content-Disposition"] = "inline"
        return response

    if ext not in (".doc", ".docx", ".ppt", ".pptx"):
        return JsonResponse(
            {"error": "该格式暂不支持预览"},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )

    soffice = _find_soffice()
    if not soffice:
        return JsonResponse(
            {"error": "预览需要安装 LibreOffice"},
            status=503,
            json_dumps_params=JSON_OPTIONS,
        )

    try:
        req = urllib.request.Request(doc.url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            file_bytes = resp.read()
    except Exception as e:
        return JsonResponse(
            {"error": f"获取文档失败: {str(e)}"},
            status=502,
            json_dumps_params=JSON_OPTIONS,
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = Path(tmpdir) / f"doc{ext}"
        input_path.write_bytes(file_bytes)
        pdf_bytes = _convert_to_pdf(soffice, input_path)
        if not pdf_bytes:
            return JsonResponse(
                {"error": "文档转换失败"},
                status=500,
                json_dumps_params=JSON_OPTIONS,
            )
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = "inline"
        return response


@csrf_exempt
@require_http_methods(["POST"])
def parse_document(request, doc_id):
    """
    从试卷管理的文档创建解析任务，与上传试卷页面共用任务流。
    POST /api/documents/<id>/parse/
    - JSON body: { use_latex?: true }
    - 从 TOS 拉取 docx，创建 UploadTask，启动异步解析
    - 返回 task_id，前端可跳转到上传试卷页面查看任务
    """
    data = _json_body(request) if request.body else {}
    use_latex = data.get("use_latex", True) if isinstance(data, dict) else True

    try:
        doc = Document.objects.get(id=doc_id)
    except Document.DoesNotExist:
        return JsonResponse({"error": "文档不存在"}, status=404, json_dumps_params=JSON_OPTIONS)
    if doc.is_folder:
        return JsonResponse({"error": "文件夹不支持解析"}, status=400, json_dumps_params=JSON_OPTIONS)

    ext = Path(doc.filename or doc.url or "").suffix.lower()
    if ext not in (".doc", ".docx"):
        return JsonResponse(
            {"error": "仅支持 .doc、.docx 格式的试卷解析"},
            status=400,
            json_dumps_params=JSON_OPTIONS,
        )

    try:
        req = urllib.request.Request(doc.url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            file_bytes = resp.read()
    except Exception as e:
        return JsonResponse(
            {"error": f"获取文档失败: {str(e)}"},
            status=502,
            json_dumps_params=JSON_OPTIONS,
        )

    task_dir = Path(settings.MEDIA_ROOT) / "uploads" / "_tasks"
    task_dir.mkdir(parents=True, exist_ok=True)
    tmp_name = f"{uuid.uuid4().hex}.docx"
    tmp_path = task_dir / tmp_name

    try:
        tmp_path.write_bytes(file_bytes)
    except Exception as e:
        return JsonResponse(
            {"error": f"保存文件失败: {str(e)}"},
            status=500,
            json_dumps_params=JSON_OPTIONS,
        )

    # 预设字段：解析出的题目将默认使用这些值
    presets = data.get("presets") or {} if isinstance(data, dict) else {}

    task = UploadTask(
        source_filename=doc.filename or "试卷.docx",
        document_id=str(doc.id),
        status="pending",
        progress=0,
        use_latex=use_latex,
        docx_path=str(tmp_path.resolve()),
        preset_difficulty=str(presets.get("difficulty", "") or "").strip(),
        preset_categories=[str(t).strip() for t in presets.get("categories", []) if t] if isinstance(presets.get("categories"), list) else [],
        preset_regions=[str(t).strip() for t in presets.get("regions", []) if t] if isinstance(presets.get("regions"), list) else [],
        preset_scenario=str(presets.get("scenario", "") or "").strip(),
        preset_knowledge_points=[str(t).strip() for t in presets.get("knowledgePoints", []) if t] if isinstance(presets.get("knowledgePoints"), list) else [],
    )
    task.save()
    doc.question_status = "unimported"
    doc.save()

    start_parse_task(str(task.id))

    return JsonResponse({
        "task_id": str(task.id),
        "status": task.status,
        "source_filename": task.source_filename,
    }, json_dumps_params=JSON_OPTIONS)


@csrf_exempt
@require_http_methods(["POST"])
def copy_document(request, doc_id):
    """
    复制文件/文件夹到目标目录（文件夹递归复制）。
    POST /api/documents/<id>/copy/
    JSON body: { targetParentId?: "" }
    """
    data = _json_body(request) or {}
    target_parent_id = str(data.get("targetParentId") or "").strip()
    try:
        source = Document.objects.get(id=doc_id)
    except Document.DoesNotExist:
        return JsonResponse({"error": "源文件不存在"}, status=404, json_dumps_params=JSON_OPTIONS)

    if target_parent_id:
        target = Document.objects.filter(id=target_parent_id).first()
        if not target or not target.is_folder:
            return JsonResponse({"error": "目标文件夹不存在"}, status=400, json_dumps_params=JSON_OPTIONS)
        if source.is_folder:
            descendants = set(_collect_descendant_ids(str(source.id)))
            if target_parent_id == str(source.id) or target_parent_id in descendants:
                return JsonResponse({"error": "不能复制到自身或子文件夹下"}, status=400, json_dumps_params=JSON_OPTIONS)

    copied = _copy_document_tree(source, target_parent_id)
    return JsonResponse(
        {"success": True, "document": copied.to_dict()},
        json_dumps_params=JSON_OPTIONS,
    )


@csrf_exempt
@require_http_methods(["POST"])
def finalize_document_questions(request, doc_id):
    """
    试卷题目全部入库后，回填 document.question_ids，并清理解析任务快照 result。
    POST /api/documents/<id>/finalize-questions/
    JSON body: { questionIds: [...], taskId?: "..." }
    """
    data = _json_body(request)
    if not data or not isinstance(data.get("questionIds"), list):
        return JsonResponse({"error": "请提供 questionIds 列表"}, status=400, json_dumps_params=JSON_OPTIONS)
    try:
        doc = Document.objects.get(id=doc_id)
    except Document.DoesNotExist:
        return JsonResponse({"error": "文档不存在"}, status=404, json_dumps_params=JSON_OPTIONS)

    qids = [str(qid).strip() for qid in data.get("questionIds", []) if str(qid).strip()]
    doc.question_ids = qids
    doc.question_status = "imported" if qids else "unimported"
    doc.save()

    task_id = str(data.get("taskId") or "").strip()
    if task_id:
        task = UploadTask.objects.filter(id=task_id, document_id=str(doc.id)).first()
        if task:
            task.result = {}
            task.save()

    return JsonResponse({"success": True, "document": doc.to_dict()}, json_dumps_params=JSON_OPTIONS)
