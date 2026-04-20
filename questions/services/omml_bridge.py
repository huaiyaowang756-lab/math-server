# -*- coding: utf-8 -*-
"""
OMML → LaTeX：仅使用 PyPI 包 omml2latex（KaTeX 友好）。
若缺少依赖或转换失败，直接抛出异常，由上层接口返回失败。
"""

import re


def _bs_count_before(s: str, i: int) -> int:
    """s[i] 之前连续反斜杠个数（用于判断 \\{ 是否为字面花括号）。"""
    c = 0
    j = i - 1
    while j >= 0 and s[j] == "\\":
        c += 1
        j -= 1
    return c


def _is_tex_group_open(s: str, i: int) -> bool:
    return i < len(s) and s[i] == "{" and _bs_count_before(s, i) % 2 == 0


def _is_tex_group_close(s: str, i: int) -> bool:
    return i < len(s) and s[i] == "}" and _bs_count_before(s, i) % 2 == 0


def _whole_string_is_single_tex_group(s: str) -> bool:
    """整段是否恰好一对「非字面」{ … }（中间可有 \\text{…}、\\frac 等嵌套）。"""
    s = s.strip()
    if len(s) < 2:
        return False
    if not _is_tex_group_open(s, 0) or not _is_tex_group_close(s, len(s) - 1):
        return False
    depth = 0
    i = 0
    while i < len(s):
        if _is_tex_group_open(s, i):
            depth += 1
        elif _is_tex_group_close(s, i):
            depth -= 1
            if depth < 0:
                return False
            if depth == 0 and i < len(s) - 1:
                return False
        i += 1
    return depth == 0


def _escape_visible_set_braces(t: str) -> str:
    """
    数学模式里未转义的 { } 只起分组作用，不显示花括号。
    omml2latex 常输出 { x\\left| ... }，需改为 \\{ ... \\} 才能在 KaTeX 中显示集合括号。
    """
    u = t.strip()
    if not _whole_string_is_single_tex_group(u):
        return t
    if u.startswith("\\{"):
        return t
    # 集合描述符：竖线分隔，或含 \\in（描述法）
    if not (
        r"\left|" in u
        or r"\mid" in u
        or re.search(r"\\in(?![a-zA-Z])", u)
    ):
        return t
    inner = u[1:-1]
    return r"\{" + inner + r"\}"


def _wrap_bare_enumerated_set(t: str) -> str:
    """
    Word 中「{-1,3,4,5}」若被转成纯 LaTeX「-1, 3, 4, 5」且无花括号，补上 \\{ \\}。
    仅匹配整数/逗号/空白，避免误伤含命令的公式。
    """
    u = t.strip().strip("，,")
    if not u or "\\" in u or "{" in u:
        return t
    # 可选首尾空白、Unicode 减号、数字与中英文逗号分隔
    if not re.match(
        r"^[−\-]?\d+(?:\s*[,，、]\s*[−\-]?\d+)*\s*$",
        u,
    ):
        return t
    return r"\{" + u + r"\}"


def _collapse_unary_minus_in_sets(t: str) -> str:
    """
    Word / omml2latex 常在「{」与负号之间插入空格，并把 Unicode 减号 − 与 - 混用，
    导致 B={−1,...} 变成「B={ - 1,...}」。此处压成一元负号写法 {-1 / \\{-1。
    """
    t = t.replace("\u2212", "-")  # MINUS SIGN → ASCII hyphen-minus
    # { - 1 → {-1，\\{ - 1 → \\{-1；枚举里 , - 2 → ,-2
    for _ in range(8):
        n = t
        t = re.sub(r"(\{)\s*-\s+(\d)", r"\1-\2", t)
        t = re.sub(r"(\\\{)\s*-\s+(\d)", r"\1-\2", t)
        t = re.sub(r",\s*-\s+(\d)", r",-\1", t)
        if n == t:
            break
    return t


def _fix_right_before_non_delimiter(t: str) -> str:
    """
    \\right 后必须跟合法定界符；Word 常在「或」等汉字前误留 \\right，导致 KaTeX 报错。
    例：\\right或 → \\right. \\text{或}
    """
    # 常见：\\right或、\\right 或（\\right 后须为定界符，否则 KaTeX 报错）
    t = re.sub(r"\\right(\s*)或", r"\\right.\1 \\text{或}", t)
    # 其它紧跟在 \\right 后的 CJK（非空白、非 \\、非常规定界符）
    t = re.sub(
        r"\\right(?!\s*[\.\)\]\}\|/\\])(\s*)([\u3000-\u9fff\uf900-\ufadf])",
        r"\\right.\1 \\text{\2}",
        t,
    )
    return t


def sanitize_latex_for_katex(s: str) -> str:
    """
    修正 Word OMML / omml2latex 常见输出，避免 KaTeX 整段报错显示为红字源码。

    典型问题：集合构造里 \\left| ... 的闭合被写成 \\right \\right\\}，
    第一个 \\right 实际应为 \\right|（竖线成对），否则括号不配平。
    """
    if not s or not isinstance(s, str):
        return s
    t = s
    t = _collapse_unary_minus_in_sets(t)
    # 竖线与左花括号写法统一
    t = re.sub(r"\\left\s+\|", r"\\left|", t)
    t = re.sub(r"\\right\s+\|", r"\\right|", t)

    # 「使得」竖线：\right \right\} → 第一个补全为 \right|（同一串里可出现多次）
    # 注意：正则里 \\right 才表示匹配字面量 \right；\right\s 会被当成 \\r + ight\\s。
    # 闭合为 Word 的 \right\}（反斜杠+}），模式末尾需写成 \\right\\}。
    if r"\left|" in t or r"\left |" in t:
        for _ in range(12):
            n = t
            t = re.sub(r"\\right\s+\\right\\}", r"\\right| \\right\\}", t)
            if n == t:
                break
    else:
        # 无 \left| 时多为多余重复，合并为一个 \right\} / \right) / \right]
        for _ in range(6):
            n = t
            t = re.sub(r"\\right\s+\\right\\}", r"\\right\\}", t)
            t = re.sub(r"\\right\s+\\right\)", r"\\right)", t)
            t = re.sub(r"\\right\s+\\right\]", r"\\right]", t)
            if n == t:
                break

    # 整数集/自然数：\text{Z} \text{N} → \mathbb{...}（KaTeX 中更标准）
    t = re.sub(r"\\in\s*\\text\{Z\}", r"\\in \\mathbb{Z}", t)
    t = re.sub(r"\\in\s*\\text\{N\}", r"\\in \\mathbb{N}", t)
    t = re.sub(r"\\in\s*\\text\{R\}", r"\\in \\mathbb{R}", t)
    t = re.sub(r"\\in\s*\\text\{Q\}", r"\\in \\mathbb{Q}", t)

    # \\right 后跟「或」等非法定界符；集合 { … } 显示为花括号；裸枚举补 \\{ \\}
    t = _fix_right_before_non_delimiter(t)
    t = _escape_visible_set_braces(t)
    t = _wrap_bare_enumerated_set(t)

    return t


def _strip_omml2latex_delimiters(s: str) -> str:
    """omml2latex 对 m:oMath 返回 $...$，对 m:oMathPara 返回 $$...$$，题目块需裸 LaTeX。"""
    t = (s or "").strip()
    if len(t) >= 4 and t.startswith("$$") and t.endswith("$$"):
        return t[2:-2].strip()
    if len(t) >= 2 and t.startswith("$") and t.endswith("$"):
        # 避免把单个 "$" 误判；至少 "$x$"
        return t[1:-1].strip()
    return t


def omml_element_to_latex(omath_el) -> str:
    """
    将 m:oMath 或 m:oMathPara 转为 LaTeX 字符串（不含 $ 包裹）。
    """
    try:
        from omml2latex import convert_omml
    except ImportError as e:
        raise RuntimeError(
            "缺少依赖 omml2latex，无法进行 OMML 转 LaTeX。请先安装 requirements.txt 依赖。"
        ) from e

    try:
        raw = convert_omml(omath_el)
    except Exception as e:
        raise RuntimeError(f"omml2latex 转换失败: {e}") from e

    latex = _strip_omml2latex_delimiters(raw)
    if not latex:
        raise RuntimeError("omml2latex 转换结果为空")
    return sanitize_latex_for_katex(latex.strip())


def sanitize_latex_block_list(blocks) -> None:
    """
    就地修正一组内容块中的 LaTeX（dict 或 ContentBlock 嵌入式文档均可）。
    """
    if not blocks:
        return
    for b in blocks:
        if isinstance(b, dict):
            if b.get("type") == "latex" and b.get("content"):
                b["content"] = sanitize_latex_for_katex(b["content"])
        elif getattr(b, "type", None) == "latex" and getattr(b, "content", None):
            b.content = sanitize_latex_for_katex(b.content)


def sanitize_latex_in_question_dict(q: dict) -> None:
    """就地修正单个题目字典（questionBody / answer / analysis / detailedSolution）。"""
    if not q:
        return
    for key in ("questionBody", "answer", "analysis", "detailedSolution"):
        sanitize_latex_block_list(q.get(key))


def sanitize_latex_blocks_in_questions(questions: list) -> None:
    """就地修正题目列表中所有 latex 块（解析流水线、批量保存前调用）。"""
    if not questions:
        return
    for q in questions:
        sanitize_latex_in_question_dict(q)
