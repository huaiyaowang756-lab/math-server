"""
从 docx 文件中提取数学试题，输出结构化题目列表。
移植自 extract_questions.py，改为可复用的模块函数。
"""

import re
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

# Word OOXML namespaces
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
    "v": "urn:schemas-microsoft-com:vml",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
}

# EMU (English Metric Units) to pixels at 96 DPI: 1 inch = 914400 EMU = 96 px
EMU_PER_PX = 914400 / 96  # 9525


def _register_namespaces():
    for prefix, uri in NS.items():
        ET.register_namespace(prefix, uri)


def _get_rels(zip_f: ZipFile) -> dict:
    """Parse word/_rels/document.xml.rels -> rId -> target path."""
    rels_path = "word/_rels/document.xml.rels"
    if rels_path not in zip_f.namelist():
        return {}
    data = zip_f.read(rels_path).decode("utf-8")
    root = ET.fromstring(data)
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    out = {}
    for rel in root.findall(f".//{{{rel_ns}}}Relationship"):
        r_id = rel.get("Id")
        target = rel.get("Target")
        if r_id and target:
            out[r_id] = "word/" + target.lstrip("/")
    return out


def _extract_text_from_run(run_el):
    texts = run_el.findall(
        ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
    )
    return "".join((t.text or "") for t in texts)


def _get_embed_id_from_run(run_el):
    for el in run_el.iter():
        tag = el.tag if isinstance(el.tag, str) else (el.tag or "")
        if "blip" in tag:
            embed = el.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
            )
            if embed:
                return embed
    for el in run_el.iter():
        tag = el.tag if isinstance(el.tag, str) else (el.tag or "")
        if "imagedata" in tag:
            r_id = el.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            if r_id:
                return r_id
    return None


def _get_image_extent_from_run(run_el):
    """
    从 run 中读取 wp:extent 的 cx、cy（EMU），转为像素宽高。
    返回 (width_px, height_px) 或 (None, None)。
    """
    wp_ns = NS["wp"]
    extent = run_el.find(f".//{{{wp_ns}}}extent")
    if extent is None:
        return None, None
    cx = extent.get("cx")
    cy = extent.get("cy")
    if cx is None or cy is None:
        return None, None
    try:
        w = max(1, round(int(cx) / EMU_PER_PX))
        h = max(1, round(int(cy) / EMU_PER_PX))
        return w, h
    except (ValueError, TypeError):
        return None, None


def _iter_body_children(body_el):
    for child in body_el:
        tag = child.tag if isinstance(child.tag, str) else (child.tag or "")
        if "}p" in tag or "}p" == tag.split("}")[-1]:
            yield ("p", child)
        elif "}tbl" in tag or "}tbl" == tag.split("}")[-1]:
            yield ("tbl", child)


def _paragraph_to_blocks(p_el, rels, media_index_map, next_asset_index):
    from .omml_converter import omml_to_latex

    blocks = []
    w_ns = NS["w"]
    m_ns = NS["m"]

    def _handle_run(run):
        nonlocal next_asset_index
        text = _extract_text_from_run(run)
        embed_id = _get_embed_id_from_run(run)
        if text:
            blocks.append({"type": "text", "content": text})
        if embed_id and embed_id in rels:
            target = rels[embed_id]
            if target not in media_index_map:
                media_index_map[target] = next_asset_index
                next_asset_index += 1
            idx = media_index_map[target]
            ext = Path(target).suffix.lower()
            asset_name = f"asset_{idx:04d}{ext}"
            url = f"doc-assets/{asset_name}"
            block = {"type": "image", "url": url}
            w_px, h_px = _get_image_extent_from_run(run)
            if w_px is not None and h_px is not None:
                block["width"] = w_px
                block["height"] = h_px
            blocks.append(block)

    # 按文档顺序遍历段落的直接子元素，同时处理 w:r 和 m:oMath
    for child in p_el:
        tag = child.tag if isinstance(child.tag, str) else ""

        if tag == f"{{{w_ns}}}r":
            # 普通文本 / 图片 run
            _handle_run(child)
        elif tag in (f"{{{m_ns}}}oMath", f"{{{m_ns}}}oMathPara"):
            # OMML 公式 → 直接转为 LaTeX，无需 OCR
            latex = omml_to_latex(child)
            if latex:
                blocks.append({"type": "latex", "content": latex})
        elif tag == f"{{{w_ns}}}hyperlink":
            # 超链接内部的 run
            for run in child.findall(f"{{{w_ns}}}r"):
                _handle_run(run)

    return blocks, next_asset_index


def _table_to_blocks(tbl_el, next_asset_index):
    texts = []
    for cell in tbl_el.iter():
        tag = cell.tag if isinstance(cell.tag, str) else (cell.tag or "")
        if "}tc" in tag:
            for t in cell.findall(
                ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
            ):
                if t.text:
                    texts.append(t.text)
    if texts:
        return [{"type": "text", "content": " ".join(texts)}], next_asset_index
    return [], next_asset_index


def _extract_paragraphs_and_media(zip_f: ZipFile, rels: dict, assets_dir: Path):
    """迭代文档段落，提取内容块并解压媒体文件。"""
    _register_namespaces()
    data = zip_f.read("word/document.xml").decode("utf-8")
    root = ET.fromstring(data)
    body = root.find(
        ".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}body"
    )
    if body is None:
        return

    assets_dir.mkdir(parents=True, exist_ok=True)
    media_index_map = {}
    next_asset_index = 1

    for kind, el in _iter_body_children(body):
        if kind == "p":
            blocks, next_asset_index = _paragraph_to_blocks(
                el, rels, media_index_map, next_asset_index
            )
            if blocks:
                yield blocks
        elif kind == "tbl":
            blocks, next_asset_index = _table_to_blocks(el, next_asset_index)
            if blocks:
                yield blocks

    # 解压媒体文件到 assets 目录
    index_to_path = {v: k for k, v in media_index_map.items()}
    for idx in sorted(index_to_path.keys()):
        zip_path = index_to_path[idx]
        ext = Path(zip_path).suffix
        asset_name = f"asset_{idx:04d}{ext}"
        out_path = assets_dir / asset_name
        try:
            out_path.write_bytes(zip_f.read(zip_path))
        except Exception as e:
            print(f"Warning: could not extract {zip_path}: {e}")


def _get_paragraph_text(blocks):
    return "".join(b.get("content", "") for b in blocks if b.get("type") == "text")


# 章节标题 -> 题型
SECTION_TYPE_MAP = {
    "一、单选题": "single_choice",
    "二、多选题": "multiple_choice",
    "三、填空题": "fill_blank",
    "四、解答题": "solution",
}


def _append_with_break(target_list, blocks):
    """向目标列表追加内容，若已有内容则先插入换行。"""
    if target_list and blocks:
        target_list.append({"type": "text", "content": "\n"})
    target_list.extend(blocks)


def _split_into_questions(paragraphs_blocks):
    """将段落块列表拆分为题目对象列表。"""
    questions = []
    current = None
    state = None
    current_section_type = "single_choice"

    for blocks in paragraphs_blocks:
        first_text = _get_paragraph_text(blocks)
        stripped = first_text.strip()

        if stripped in SECTION_TYPE_MAP:
            current_section_type = SECTION_TYPE_MAP[stripped]
            continue

        if re.match(r"^\d+[．.]", stripped):
            if current is not None:
                questions.append(current)
            num_match = re.match(r"^(\d+)[．.]", stripped)
            num = int(num_match.group(1)) if num_match else len(questions) + 1
            current = {
                "index": num,
                "questionType": current_section_type,
                "questionBody": [],
                "answer": [],
                "analysis": [],
                "detailedSolution": [],
            }
            state = "body"
            if blocks:
                new_blocks = []
                for b in blocks:
                    if b.get("type") == "text" and b.get("content"):
                        content = re.sub(r"^\d+[．.]\s*", "", b["content"], count=1)
                        if content:
                            new_blocks.append({"type": "text", "content": content})
                    else:
                        new_blocks.append(b)
                if new_blocks:
                    current["questionBody"].extend(new_blocks)
            continue

        if current is None:
            continue

        if "【答案】" in stripped:
            state = "answer"
            new_blocks = []
            for b in blocks:
                if (
                    b.get("type") == "text"
                    and b.get("content")
                    and "【答案】" in b["content"]
                ):
                    content = b["content"].replace("【答案】", "").strip()
                    if content:
                        new_blocks.append({"type": "text", "content": content})
                else:
                    new_blocks.append(b)
            _append_with_break(current["answer"], new_blocks)
            continue

        if stripped.startswith("【分析】"):
            state = "analysis"
            new_blocks = []
            for b in blocks:
                if (
                    b.get("type") == "text"
                    and b.get("content")
                    and "【分析】" in b["content"]
                ):
                    content = b["content"].replace("【分析】", "").strip()
                    if content:
                        new_blocks.append({"type": "text", "content": content})
                else:
                    new_blocks.append(b)
            _append_with_break(current["analysis"], new_blocks)
            continue

        if stripped.startswith("【详解】"):
            state = "detailedSolution"
            new_blocks = []
            for b in blocks:
                if (
                    b.get("type") == "text"
                    and b.get("content")
                    and "【详解】" in b["content"]
                ):
                    content = b["content"].replace("【详解】", "").strip()
                    if content:
                        new_blocks.append({"type": "text", "content": content})
                else:
                    new_blocks.append(b)
            _append_with_break(current["detailedSolution"], new_blocks)
            continue

        if state == "body":
            _append_with_break(current["questionBody"], blocks)
        elif state == "answer":
            _append_with_break(current["answer"], blocks)
        elif state == "analysis":
            _append_with_break(current["analysis"], blocks)
        elif state == "detailedSolution":
            _append_with_break(current["detailedSolution"], blocks)

    if current is not None:
        questions.append(current)
    return questions


def _merge_consecutive_text_blocks(blocks: list) -> list:
    """
    将连续的 type 为 text 的块合并为一个；
    合并后按换行拆开：遇到换行则单独拆成一个节点（content 为 \\n），不跨换行合并。
    """
    if not blocks:
        return blocks
    result = []
    for b in blocks:
        if b.get("type") == "text" and result and result[-1].get("type") == "text":
            result[-1]["content"] = (result[-1].get("content") or "") + (b.get("content") or "")
        else:
            result.append(dict(b))

    # 每个 text 块按换行拆开，换行单独成节点（空串不落块）
    out = []
    for b in result:
        if b.get("type") != "text":
            out.append(b)
            continue
        content = b.get("content") or ""
        parts = re.split(r"(\n)", content)  # 保留 \n 在结果中
        for p in parts:
            if p:  # 跳过空串，保留 \n
                out.append({"type": "text", "content": p})
    return out


def parse_docx(docx_path: Path, assets_dir: Path) -> list[dict]:
    """
    解析 docx 文件，提取所有题目，返回题目列表。
    同时将嵌入的媒体文件解压到 assets_dir/doc-assets/。

    Args:
        docx_path: docx 文件路径
        assets_dir: 资源文件输出目录（会在其下创建 doc-assets/ 子目录）

    Returns:
        题目列表 [{ index, questionType, questionBody, answer, ... }, ...]
    """
    doc_assets_dir = assets_dir / "doc-assets"

    with ZipFile(docx_path, "r") as z:
        rels = _get_rels(z)
        paragraphs_blocks = list(
            _extract_paragraphs_and_media(z, rels, doc_assets_dir)
        )

    # 过滤文档头信息
    filtered = []
    for blocks in paragraphs_blocks:
        text = _get_paragraph_text(blocks)
        t = text.strip()
        if any(kw in t for kw in ("2026年", "学校:", "姓名：", "学校：", "姓名:")):
            continue
        if not t and len(blocks) == 0:
            continue
        filtered.append(blocks)

    questions = _split_into_questions(filtered)

    # 连续 type 为 text 的块合并为一块
    for q in questions:
        for key in ("questionBody", "answer", "analysis", "detailedSolution"):
            if key in q and q[key]:
                q[key] = _merge_consecutive_text_blocks(q[key])

    # 去除题干首块中的序号（避免下载时重复出现题号）
    for q in questions:
        body = q.get("questionBody") or []
        for i, b in enumerate(body):
            if b.get("type") != "text" or not b.get("content"):
                continue
            content = b["content"]
            # 匹配开头序号：数字 + 中文/英文句号或顿号 + 可选空格
            content = re.sub(r"^\d+[．.、]\s*", "", content, count=1)
            # 若首块仅为序号（如 "1" 或 "1." 单独成块），直接移除该块
            if not content.strip():
                body.pop(i)
                # 继续检查下一个块（可能成为新的首块）
                break
            if content != b["content"]:
                body[i] = {**b, "content": content}
            break

    # 清理空数组
    for q in questions:
        for key in ("analysis", "detailedSolution"):
            if key in q and not q[key]:
                del q[key]

    return questions
