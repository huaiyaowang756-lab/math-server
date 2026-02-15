"""
将题目中的公式图（PNG）通过 pix2tex 识别为 LaTeX。
移植自 formula_to_latex.py，改为可复用的模块函数。
"""

import os
import warnings

os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")
warnings.filterwarnings("ignore", message=".*albumentations.*", category=UserWarning)
warnings.filterwarnings("ignore", message=".*Pydantic.*", category=UserWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

import re
import sys
from pathlib import Path

MIN_DIM = 80
PAD_BORDER = 25


def _get_latex_ocr():
    try:
        from pix2tex.cli import LatexOCR
        from PIL import Image

        return LatexOCR(), Image
    except ImportError as e:
        print("请先安装: pip install pix2tex Pillow", file=sys.stderr)
        raise RuntimeError("pix2tex not installed") from e


def _preprocess_image(Image_module, img):
    if img.mode == "RGBA":
        bg = Image_module.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")
    w, h = img.size
    if w < MIN_DIM or h < MIN_DIM:
        scale = max(MIN_DIM / w, MIN_DIM / h, 1.0)
        nw, nh = int(round(w * scale)), int(round(h * scale))
        resample = (
            getattr(Image_module, "Resampling", Image_module).LANCZOS
            if hasattr(Image_module, "Resampling")
            else Image_module.LANCZOS
        )
        img = img.resize((nw, nh), resample)
    if PAD_BORDER > 0:
        try:
            from PIL import ImageOps

            img = ImageOps.expand(img, border=PAD_BORDER, fill=(255, 255, 255))
        except ImportError:
            pass
    return img


def sanitize_latex(latex: str) -> str:
    """校验并修正 pix2tex 常见识别错误。"""
    if not latex:
        return latex
    s = latex

    for left, right in [("[", "]"), ("(", ")"), ("{", "}")]:
        escaped_r = "\\right" + (right if right != "}" else "\\}")
        escaped_l = "\\left" + (left if left != "{" else "\\{")
        s = s.replace(escaped_r + escaped_r + escaped_l, escaped_r + escaped_l)

    ORPHAN_AFTER = [
        "\\pm", "\\mp", "=", "+", "-", "\\cdot", "\\times", "\\div",
        "\\sin", "\\cos", "\\tan", "\\left", "\\quad", "\\,", "\\;",
        "\\infty", "\\sum", "\\int", "\\lim",
    ]
    for left, right in [("[", "]"), ("(", ")"), ("{", "}")]:
        escaped_r = "\\right" + (right if right != "}" else "\\}")
        escaped_l = "\\left" + (left if left != "{" else "\\{")
        n_left = s.count(escaped_l)
        n_right = s.count(escaped_r)
        to_remove = n_right - n_left
        if to_remove <= 0:
            continue
        dup = escaped_r + escaped_r
        while to_remove > 0 and dup in s:
            s = s.replace(dup, escaped_r, 1)
            to_remove -= 1
        for suffix in ORPHAN_AFTER:
            pattern = escaped_r + suffix
            repl = suffix
            while to_remove > 0 and pattern in s:
                s = s.replace(pattern, repl, 1)
                to_remove -= 1
            if to_remove <= 0:
                break
        if to_remove > 0 and s.endswith(escaped_r):
            s = s[: -len(escaped_r)]
            to_remove -= 1

    for double, single in [
        ("\\pm\\pm", "\\pm"),
        ("\\mp\\mp", "\\mp"),
        ("\\cdot\\cdot", "\\cdot"),
        ("\\times\\times", "\\times"),
        ("\\div\\div", "\\div"),
        ("\\quad\\quad", "\\quad"),
    ]:
        s = s.replace(double, single)

    s = re.sub(r"\\sqrt(\d)", r"\\sqrt{\1}", s)
    return s


def _image_to_latex(ocr_model, Image_module, image_path: Path) -> str | None:
    """单张公式图片识别为 LaTeX，支持 PNG/JPEG 等 PIL 可读格式。"""
    if not image_path.exists():
        return None
    try:
        img = Image_module.open(image_path)
        img = _preprocess_image(Image_module, img)
        out = ocr_model(img)
        s = (out or "").strip()
        if s:
            s = sanitize_latex(s)
        return s if s else None
    except Exception:
        return None


def recognize_formula_image(image_path: Path) -> str | None:
    """
    将单张公式截图识别为 LaTeX，供编辑时「上传公式截图」使用。
    支持 PNG、JPEG 等常见图片格式。
    """
    try:
        model, Image = _get_latex_ocr()
        return _image_to_latex(model, Image, image_path)
    except RuntimeError:
        return None


def convert_to_latex(questions: list, assets_dir: Path) -> dict:
    """
    将题目中引用的 PNG 公式图通过 pix2tex 转为 LaTeX。
    直接修改 questions 列表中的内容块。

    Returns:
        { "total_images": int, "converted": int, "failed": int }
    """
    doc_assets = assets_dir / "doc-assets"
    result = {"total_images": 0, "converted": 0, "failed": 0}

    # 只收集由 WMF 转换而来的公式 PNG（doc-assets/ 下有对应 .wmf 文件的）
    # 跳过：绝对 URL（已上传 TOS 的内容图）、原始 PNG/JPEG 内容图
    png_urls = set()
    for q in questions:
        for key in ("questionBody", "answer", "analysis", "detailedSolution"):
            for b in q.get(key) or []:
                if b.get("type") not in ("image", "svg"):
                    continue
                u = (b.get("url") or "").replace("\\", "/")
                # 跳过绝对 URL（TOS 已上传的内容图）
                if u.startswith("http://") or u.startswith("https://"):
                    continue
                if not u.endswith(".png"):
                    continue
                # 只处理有对应 .wmf 源文件的 PNG（即公式图）
                name = Path(u).name
                wmf_name = Path(name).stem + ".wmf"
                if (doc_assets / wmf_name).exists():
                    png_urls.add(u)

    result["total_images"] = len(png_urls)
    if not png_urls:
        return result

    try:
        model, Image = _get_latex_ocr()
    except RuntimeError:
        result["failed"] = len(png_urls)
        return result

    asset_to_latex = {}
    for url in sorted(png_urls):
        name = Path(url).name
        local = doc_assets / name
        latex = _image_to_latex(model, Image, local)
        if latex:
            asset_to_latex[url] = latex
        else:
            result["failed"] += 1

    result["converted"] = len(asset_to_latex)

    # 替换内容块
    for q in questions:
        for key in ("questionBody", "answer", "analysis", "detailedSolution"):
            for b in q.get(key) or []:
                if b.get("type") in ("image", "svg"):
                    url = (b.get("url") or "").replace("\\", "/")
                    if url in asset_to_latex:
                        b["type"] = "latex"
                        b["content"] = asset_to_latex[url]
                        if "url" in b:
                            del b["url"]

    return result
