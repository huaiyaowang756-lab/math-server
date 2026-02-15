"""
将 doc-assets 目录下的 WMF 文件转为 PNG。
移植自 convert_wmf_to_png.py，改为可复用的模块函数。
"""

import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None

WHITE_THRESHOLD = 248
TRIM_PADDING = 20
_im_error_shown = False


def _find_imagemagick():
    for cmd in ("magick", "convert"):
        try:
            subprocess.run([cmd, "-version"], capture_output=True, check=True)
            return cmd
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    return None


def _find_libreoffice():
    candidates = [
        "libreoffice",
        "soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    for cmd in candidates:
        try:
            subprocess.run(
                [cmd, "--version"], capture_output=True, check=True, timeout=10
            )
            return cmd
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return None


def _find_wmf2eps():
    try:
        subprocess.run(["wmf2eps", "-h"], capture_output=True, timeout=5)
        return "wmf2eps"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _convert_imagemagick(wmf_path: Path, png_path: Path, convert_cmd: str) -> bool:
    global _im_error_shown
    try:
        r = subprocess.run(
            [convert_cmd, "-density", "150", str(wmf_path), str(png_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode != 0:
            if not _im_error_shown:
                _im_error_shown = True
                msg = (r.stderr or r.stdout or "").strip() or "未知错误"
                print("  ImageMagick 无法处理 WMF:", msg[:500], file=sys.stderr)
            return False
        return png_path.exists()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        if not _im_error_shown:
            _im_error_shown = True
            print(f"  ImageMagick 出错: {e}", file=sys.stderr)
        return False


def _convert_libreoffice(soffice_cmd: str, wmf_path: Path, png_path: Path) -> bool:
    try:
        out_dir = png_path.parent
        r = subprocess.run(
            [soffice_cmd, "--headless", "--convert-to", "png", "--outdir", str(out_dir), str(wmf_path)],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if r.returncode != 0 and r.stderr:
            print(f"  LibreOffice stderr: {r.stderr[:300]}", file=sys.stderr)
        return png_path.exists()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _convert_wmf2eps_then_png(wmf_path: Path, png_path: Path, convert_cmd: str) -> bool:
    try:
        work_dir = wmf_path.parent
        r = subprocess.run(
            ["wmf2eps", "-o", str(png_path.with_suffix(".eps")), str(wmf_path)],
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            return False
        eps_path = png_path.with_suffix(".eps")
        if not eps_path.exists():
            return False
        r2 = subprocess.run(
            [convert_cmd, "-density", "150", str(eps_path), str(png_path)],
            capture_output=True,
            timeout=15,
        )
        try:
            eps_path.unlink()
        except OSError:
            pass
        return r2.returncode == 0 and png_path.exists()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _trim_whitespace(png_path: Path) -> bool:
    if Image is None:
        return False
    if not png_path.exists():
        return False
    try:
        img = Image.open(png_path)
        if img.mode == "RGBA":
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
        w, h = img.size
        gray = img.convert("L")
        mask = gray.point(lambda v: 255 if v < WHITE_THRESHOLD else 0, mode="L")
        bbox = mask.getbbox()
        if not bbox:
            return False
        x1, y1, x2, y2 = bbox
        x1 = max(0, x1 - TRIM_PADDING)
        y1 = max(0, y1 - TRIM_PADDING)
        x2 = min(w, x2 + TRIM_PADDING)
        y2 = min(h, y2 + TRIM_PADDING)
        if x1 >= x2 or y1 >= y2:
            return False
        if x1 <= 0 and y1 <= 0 and x2 >= w and y2 >= h:
            return False
        cropped = img.crop((x1, y1, x2, y2))
        cropped.save(png_path, "PNG", optimize=False)
        return True
    except Exception:
        return False


def convert_wmf_to_png(assets_dir: Path) -> dict:
    """
    将 assets_dir/doc-assets/ 下的 WMF 文件转为 PNG。

    Returns:
        { "total": int, "success": int, "trimmed": int, "method": str|None }
    """
    doc_assets = assets_dir / "doc-assets"
    result = {"total": 0, "success": 0, "trimmed": 0, "method": None}

    if not doc_assets.is_dir():
        return result

    wmf_files = sorted(doc_assets.glob("*.wmf"))
    result["total"] = len(wmf_files)
    if not wmf_files:
        return result

    convert_cmd = _find_imagemagick()
    soffice = _find_libreoffice()
    wmf2eps = _find_wmf2eps()

    method = None
    if convert_cmd:
        test_ok = _convert_imagemagick(
            wmf_files[0], wmf_files[0].with_suffix(".png"), convert_cmd
        )
        if test_ok:
            method = "imagemagick"
        elif soffice:
            method = "libreoffice"
        elif wmf2eps and convert_cmd:
            method = "wmf2eps"
            if not wmf_files[0].with_suffix(".png").exists():
                if not _convert_wmf2eps_then_png(
                    wmf_files[0], wmf_files[0].with_suffix(".png"), convert_cmd
                ):
                    method = None

    if method is None:
        print("Warning: 无法转换 WMF 文件，缺少转换工具", file=sys.stderr)
        return result

    result["method"] = method
    ok = 0
    for wmf in wmf_files:
        png = wmf.with_suffix(".png")
        if png.exists() and png.stat().st_mtime >= wmf.stat().st_mtime:
            ok += 1
            continue
        success = False
        if method == "imagemagick":
            success = _convert_imagemagick(wmf, png, convert_cmd)
        elif method == "libreoffice":
            success = _convert_libreoffice(soffice, wmf, png)
        elif method == "wmf2eps":
            success = _convert_wmf2eps_then_png(wmf, png, convert_cmd)
        if success:
            _trim_whitespace(png)
            ok += 1

    result["success"] = ok

    # 对所有 PNG 做一次裁剪
    if Image is not None:
        trimmed = 0
        for png in sorted(doc_assets.glob("*.png")):
            if _trim_whitespace(png):
                trimmed += 1
        result["trimmed"] = trimmed

    return result


def replace_wmf_urls(questions: list) -> list:
    """将题目中的 .wmf 链接替换为 .png。"""
    import json

    s = json.dumps(questions, ensure_ascii=False)
    s = s.replace('.wmf"', '.png"')
    return json.loads(s)
