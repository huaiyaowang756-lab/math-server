"""
OMML (Office Math Markup Language) → LaTeX 转换器。

直接从 Word 文档的 XML 结构中提取公式，无需 OCR，准确率接近 100%。

OMML 是 Word 2007+ 内置公式编辑器的存储格式，公式以结构化 XML 存储在
document.xml 中。本模块递归遍历 OMML 元素树，输出等价的 LaTeX 字符串。
"""

import xml.etree.ElementTree as ET

# ─── 命名空间 ─────────────────────────────────────────────────────────
MATH_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _m(tag: str) -> str:
    """构造 OMML 完整标签名。"""
    return f"{{{MATH_NS}}}{tag}"


def _w(tag: str) -> str:
    """构造 Word 完整标签名。"""
    return f"{{{WORD_NS}}}{tag}"


def _local(el) -> str:
    """获取元素的本地标签名（不含命名空间）。"""
    tag = el.tag if isinstance(el.tag, str) else ""
    return tag.split("}")[-1] if "}" in tag else tag


# ─── 属性访问工具 ──────────────────────────────────────────────────────

def _get_val(el, prop_path: str):
    """
    读取属性值。prop_path 形如 'accPr/chr'，
    表示 el → m:accPr → m:chr 的 m:val（或 val）属性。
    """
    parts = prop_path.split("/")
    current = el
    for part in parts:
        current = current.find(_m(part))
        if current is None:
            return None
    val = current.get(_m("val"))
    if val is None:
        val = current.get("val")
    return val


# ─── 属性标签集（跳过，不递归） ──────────────────────────────────────
_PROPERTY_TAGS = frozenset({
    "fPr", "radPr", "sSubPr", "sSupPr", "sSubSupPr", "naryPr",
    "dPr", "accPr", "barPr", "funcPr", "limLowPr", "limUppPr",
    "mPr", "eqArrPr", "sPrePr", "groupChrPr", "boxPr", "borderBoxPr",
    "oMathParaPr", "rPr", "ctrlPr", "phantPr",
})

# ─── Unicode → LaTeX 符号映射 ────────────────────────────────────────
UNICODE_TO_LATEX = {
    # 小写希腊字母
    "α": r"\alpha", "β": r"\beta", "γ": r"\gamma", "δ": r"\delta",
    "ε": r"\varepsilon", "ζ": r"\zeta", "η": r"\eta", "θ": r"\theta",
    "ι": r"\iota", "κ": r"\kappa", "λ": r"\lambda", "μ": r"\mu",
    "ν": r"\nu", "ξ": r"\xi", "π": r"\pi", "ρ": r"\rho",
    "σ": r"\sigma", "ς": r"\varsigma", "τ": r"\tau", "υ": r"\upsilon",
    "φ": r"\varphi", "χ": r"\chi", "ψ": r"\psi", "ω": r"\omega",
    "ϕ": r"\phi", "ϵ": r"\epsilon", "ϑ": r"\vartheta", "ϱ": r"\varrho",
    "ϖ": r"\varpi",
    # 大写希腊字母
    "Γ": r"\Gamma", "Δ": r"\Delta", "Θ": r"\Theta", "Λ": r"\Lambda",
    "Ξ": r"\Xi", "Π": r"\Pi", "Σ": r"\Sigma", "Υ": r"\Upsilon",
    "Φ": r"\Phi", "Ψ": r"\Psi", "Ω": r"\Omega",
    # 二元运算 / 关系
    "×": r"\times", "÷": r"\div", "±": r"\pm", "∓": r"\mp",
    "·": r"\cdot", "∙": r"\cdot", "⊕": r"\oplus", "⊗": r"\otimes",
    "≤": r"\leq", "≥": r"\geq", "≠": r"\neq", "≈": r"\approx",
    "≡": r"\equiv", "∼": r"\sim", "≅": r"\cong", "≪": r"\ll", "≫": r"\gg",
    "≺": r"\prec", "≻": r"\succ", "⪯": r"\preceq", "⪰": r"\succeq",
    "∝": r"\propto",
    # 集合 / 逻辑
    "∈": r"\in", "∉": r"\notin", "⊂": r"\subset", "⊃": r"\supset",
    "⊆": r"\subseteq", "⊇": r"\supseteq", "∅": r"\emptyset",
    "∪": r"\cup", "∩": r"\cap", "∖": r"\setminus",
    "∧": r"\wedge", "∨": r"\vee", "¬": r"\neg",
    # 箭头
    "⇒": r"\Rightarrow", "⇔": r"\Leftrightarrow", "⇐": r"\Leftarrow",
    "→": r"\rightarrow", "←": r"\leftarrow", "↔": r"\leftrightarrow",
    "↑": r"\uparrow", "↓": r"\downarrow",
    "↦": r"\mapsto", "⟹": r"\Longrightarrow", "⟸": r"\Longleftarrow",
    # 量词 / 微积分
    "∀": r"\forall", "∃": r"\exists", "∄": r"\nexists",
    "∞": r"\infty", "∂": r"\partial", "∇": r"\nabla",
    # 大运算符
    "∑": r"\sum", "∏": r"\prod", "∐": r"\coprod",
    "∫": r"\int", "∬": r"\iint", "∭": r"\iiint", "∮": r"\oint",
    # 其他
    "…": r"\ldots", "⋯": r"\cdots", "⋮": r"\vdots", "⋱": r"\ddots",
    "′": "'", "″": "''", "‴": "'''",
    "°": r"^{\circ}",
    "⊥": r"\perp", "∥": r"\parallel", "∠": r"\angle",
    "△": r"\triangle", "□": r"\square",
    "ℝ": r"\mathbb{R}", "ℤ": r"\mathbb{Z}", "ℕ": r"\mathbb{N}",
    "ℚ": r"\mathbb{Q}", "ℂ": r"\mathbb{C}",
    "ℓ": r"\ell", "ℏ": r"\hbar", "℘": r"\wp",
    "∘": r"\circ",
    "⊕": r"\oplus", "⊖": r"\ominus",
    # 特殊减号（Unicode MINUS SIGN vs ASCII hyphen）
    "\u2212": "-",
    "\u00b7": r"\cdot",
}

# 重音符号映射
ACCENT_MAP = {
    "\u0302": r"\hat",       # combining circumflex
    "\u0303": r"\tilde",     # combining tilde
    "\u0304": r"\bar",       # combining macron
    "\u0305": r"\overline",  # combining overline
    "\u0307": r"\dot",       # combining dot above
    "\u0308": r"\ddot",      # combining diaeresis
    "\u030C": r"\check",     # combining caron
    "\u0332": r"\underline", # combining low line
    "\u20D7": r"\vec",       # combining right arrow above
    "\u20D6": r"\overleftarrow",
    "^": r"\hat",
    "~": r"\tilde",
    "¯": r"\bar",
    "→": r"\vec",
    "⃗": r"\vec",
}

# N-ary 运算符映射
NARY_MAP = {
    "∑": r"\sum",
    "∏": r"\prod",
    "∐": r"\coprod",
    "∫": r"\int",
    "∬": r"\iint",
    "∭": r"\iiint",
    "∮": r"\oint",
    "⋃": r"\bigcup",
    "⋂": r"\bigcap",
    "⋁": r"\bigvee",
    "⋀": r"\bigwedge",
}

# 分隔符映射
DELIM_MAP = {
    "(": "(", ")": ")",
    "[": "[", "]": "]",
    "{": r"\{", "}": r"\}",
    "|": "|", "‖": r"\|",
    "⌊": r"\lfloor", "⌋": r"\rfloor",
    "⌈": r"\lceil", "⌉": r"\rceil",
    "⟨": r"\langle", "⟩": r"\rangle",
    "〈": r"\langle", "〉": r"\rangle",
}

# 组字符映射
GROUPCHR_MAP = {
    "\u23DE": r"\overbrace",   # top curly bracket  ⏞
    "\u23DF": r"\underbrace",  # bottom curly bracket ⏟
    "⏞": r"\overbrace",
    "⏟": r"\underbrace",
}

# 常见函数名
_FUNC_NAMES = {
    "sin", "cos", "tan", "sec", "csc", "cot",
    "arcsin", "arccos", "arctan",
    "sinh", "cosh", "tanh",
    "ln", "log", "lg", "exp",
    "lim", "max", "min", "sup", "inf",
    "det", "dim", "gcd", "deg",
    "arg", "hom", "ker",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  文本转换
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _convert_text(text: str) -> str:
    """将 Unicode 文本转为 LaTeX，替换已知的特殊符号。"""
    if not text:
        return ""
    parts: list[str] = []
    for ch in text:
        if ch in UNICODE_TO_LATEX:
            cmd = UNICODE_TO_LATEX[ch]
            parts.append(cmd)
            # 反斜杠命令后面紧跟字母时需要空格分隔
            if cmd.startswith("\\") and cmd[-1].isalpha():
                parts.append(" ")
        else:
            parts.append(ch)
    return "".join(parts)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  核心递归转换
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _convert_children(el) -> str:
    """递归转换所有子元素并拼接。"""
    parts: list[str] = []
    for child in el:
        local = _local(child)
        if local in _PROPERTY_TAGS:
            continue
        result = _convert_element(child)
        if result:
            parts.append(result)
    return "".join(parts)


def _convert_element(el) -> str:
    """将单个 OMML 元素路由到对应的转换函数。"""
    local = _local(el)
    if local in _PROPERTY_TAGS:
        return ""
    converter = _CONVERTERS.get(local)
    if converter:
        return converter(el)
    # 容器元素——递归转换子节点
    if local in ("oMath", "oMathPara", "e", "num", "den",
                 "sup", "sub", "deg", "lim", "fName"):
        return _convert_children(el)
    return ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  各 OMML 元素转换器
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _convert_math_run(el) -> str:
    """m:r（数学文本 run）→ LaTeX"""
    rpr = el.find(_m("rPr"))
    nor = False
    style = None
    script = None

    if rpr is not None:
        if rpr.find(_m("nor")) is not None:
            nor = True
        sty = rpr.find(_m("sty"))
        if sty is not None:
            style = sty.get(_m("val")) or sty.get("val")
        scr = rpr.find(_m("scr"))
        if scr is not None:
            script = scr.get(_m("val")) or scr.get("val")

    # 提取文本
    text_parts: list[str] = []
    for t_el in el.findall(_m("t")):
        text_parts.append(t_el.text or "")
    for t_el in el.findall(_w("t")):
        text_parts.append(t_el.text or "")
    text = "".join(text_parts)

    if nor:
        return rf"\text{{{text}}}"

    latex = _convert_text(text)

    # 数学脚本样式
    if script == "double-struck" and latex:
        return rf"\mathbb{{{latex.strip()}}}"
    if script == "script" and latex:
        return rf"\mathcal{{{latex.strip()}}}"
    if script == "fraktur" and latex:
        return rf"\mathfrak{{{latex.strip()}}}"

    # 数学字体样式
    if style == "b" and latex:
        return rf"\mathbf{{{latex.strip()}}}"
    if style == "bi" and latex:
        return rf"\boldsymbol{{{latex.strip()}}}"
    if style == "p" and latex:
        return rf"\mathrm{{{latex.strip()}}}"

    return latex


def _convert_fraction(el) -> str:
    """m:f（分数）→ LaTeX"""
    ftype = _get_val(el, "fPr/type")
    num = el.find(_m("num"))
    den = el.find(_m("den"))
    n = _convert_children(num) if num is not None else ""
    d = _convert_children(den) if den is not None else ""
    if ftype in ("skw", "lin"):
        return rf"{{{n}}}/{{{d}}}"
    return rf"\frac{{{n}}}{{{d}}}"


def _convert_radical(el) -> str:
    """m:rad（根号）→ LaTeX"""
    deg = el.find(_m("deg"))
    e = el.find(_m("e"))
    deg_hide = _get_val(el, "radPr/degHide")
    deg_s = _convert_children(deg) if deg is not None else ""
    e_s = _convert_children(e) if e is not None else ""
    if deg_hide == "1" or not deg_s.strip():
        return rf"\sqrt{{{e_s}}}"
    return rf"\sqrt[{deg_s}]{{{e_s}}}"


def _convert_superscript(el) -> str:
    """m:sSup（上标）→ LaTeX"""
    e = el.find(_m("e"))
    sup = el.find(_m("sup"))
    e_s = _convert_children(e) if e is not None else ""
    sup_s = _convert_children(sup) if sup is not None else ""
    if len(e_s) > 1 and not (e_s.startswith("{") or e_s.startswith("\\")):
        e_s = f"{{{e_s}}}"
    return f"{e_s}^{{{sup_s}}}"


def _convert_subscript(el) -> str:
    """m:sSub（下标）→ LaTeX"""
    e = el.find(_m("e"))
    sub = el.find(_m("sub"))
    e_s = _convert_children(e) if e is not None else ""
    sub_s = _convert_children(sub) if sub is not None else ""
    if len(e_s) > 1 and not (e_s.startswith("{") or e_s.startswith("\\")):
        e_s = f"{{{e_s}}}"
    return f"{e_s}_{{{sub_s}}}"


def _convert_subsuper(el) -> str:
    """m:sSubSup（上下标）→ LaTeX"""
    e = el.find(_m("e"))
    sub = el.find(_m("sub"))
    sup = el.find(_m("sup"))
    e_s = _convert_children(e) if e is not None else ""
    sub_s = _convert_children(sub) if sub is not None else ""
    sup_s = _convert_children(sup) if sup is not None else ""
    if len(e_s) > 1 and not (e_s.startswith("{") or e_s.startswith("\\")):
        e_s = f"{{{e_s}}}"
    return f"{e_s}_{{{sub_s}}}^{{{sup_s}}}"


def _convert_nary(el) -> str:
    """m:nary（N 元运算符：求和、积分等）→ LaTeX"""
    chr_val = _get_val(el, "naryPr/chr")
    if chr_val is None:
        chr_val = "∫"
    op = NARY_MAP.get(chr_val, chr_val)

    sub = el.find(_m("sub"))
    sup = el.find(_m("sup"))
    e = el.find(_m("e"))
    sub_s = _convert_children(sub) if sub is not None else ""
    sup_s = _convert_children(sup) if sup is not None else ""
    e_s = _convert_children(e) if e is not None else ""

    sub_hide = _get_val(el, "naryPr/subHide")
    sup_hide = _get_val(el, "naryPr/supHide")

    result = op
    if sub_s.strip() and sub_hide != "1":
        result += f"_{{{sub_s}}}"
    if sup_s.strip() and sup_hide != "1":
        result += f"^{{{sup_s}}}"
    if e_s.strip():
        result += f"{{{e_s}}}"
    return result


def _convert_delimiter(el) -> str:
    """m:d（分隔符 / 括号）→ LaTeX"""
    dpr = el.find(_m("dPr"))
    beg = "("
    end = ")"
    sep = "|"

    if dpr is not None:
        beg_el = dpr.find(_m("begChr"))
        end_el = dpr.find(_m("endChr"))
        sep_el = dpr.find(_m("sepChr"))
        if beg_el is not None:
            v = beg_el.get(_m("val"))
            if v is None:
                v = beg_el.get("val")
            if v is not None:
                beg = v
        if end_el is not None:
            v = end_el.get(_m("val"))
            if v is None:
                v = end_el.get("val")
            if v is not None:
                end = v
        if sep_el is not None:
            v = sep_el.get(_m("val"))
            if v is None:
                v = sep_el.get("val")
            if v is not None:
                sep = v

    # 收集所有 m:e 子元素
    elements = el.findall(_m("e"))
    parts = [_convert_children(e) for e in elements]

    if len(parts) > 1:
        sep_latex = _convert_text(sep) if sep else ", "
        inner = sep_latex.join(parts)
    else:
        inner = parts[0] if parts else ""

    beg_l = DELIM_MAP.get(beg, beg)
    end_l = DELIM_MAP.get(end, end)

    if not beg and not end:
        return inner

    beg_out = beg_l if beg else "."
    end_out = end_l if end else "."
    return rf"\left{beg_out} {inner} \right{end_out}"


def _convert_accent(el) -> str:
    """m:acc（重音符号：帽、波浪线等）→ LaTeX"""
    chr_val = _get_val(el, "accPr/chr")
    e = el.find(_m("e"))
    e_s = _convert_children(e) if e is not None else ""
    if chr_val is None:
        chr_val = "\u0302"
    cmd = ACCENT_MAP.get(chr_val, r"\hat")
    return f"{cmd}{{{e_s}}}"


def _convert_bar(el) -> str:
    """m:bar（上划线 / 下划线）→ LaTeX"""
    pos = _get_val(el, "barPr/pos")
    e = el.find(_m("e"))
    e_s = _convert_children(e) if e is not None else ""
    if pos == "bot":
        return rf"\underline{{{e_s}}}"
    return rf"\overline{{{e_s}}}"


def _convert_func(el) -> str:
    """m:func（函数名 + 参数）→ LaTeX"""
    fname_el = el.find(_m("fName"))
    e = el.find(_m("e"))
    fname_s = _convert_children(fname_el) if fname_el is not None else ""
    e_s = _convert_children(e) if e is not None else ""

    # 将 \mathrm{funcname} 替换为标准 \funcname
    for name in _FUNC_NAMES:
        mathrm_pat = rf"\mathrm{{{name}}}"
        if mathrm_pat in fname_s:
            fname_s = fname_s.replace(mathrm_pat, rf"\{name} ")
            break
        if fname_s.strip() == name:
            fname_s = rf"\{name} "
            break

    return f"{fname_s}{e_s}"


def _convert_limlower(el) -> str:
    """m:limLow（下极限）→ LaTeX"""
    e = el.find(_m("e"))
    lim = el.find(_m("lim"))
    e_s = _convert_children(e) if e is not None else ""
    lim_s = _convert_children(lim) if lim is not None else ""
    return f"{e_s}_{{{lim_s}}}"


def _convert_limupper(el) -> str:
    """m:limUpp（上极限）→ LaTeX"""
    e = el.find(_m("e"))
    lim = el.find(_m("lim"))
    e_s = _convert_children(e) if e is not None else ""
    lim_s = _convert_children(lim) if lim is not None else ""
    return f"{e_s}^{{{lim_s}}}"


def _convert_matrix(el) -> str:
    """m:m（矩阵）→ LaTeX"""
    rows = el.findall(_m("mr"))
    row_strs: list[str] = []
    for row in rows:
        cells = row.findall(_m("e"))
        cell_strs = [_convert_children(c) for c in cells]
        row_strs.append(" & ".join(cell_strs))
    inner = r" \\ ".join(row_strs)
    return rf"\begin{{matrix}} {inner} \end{{matrix}}"


def _convert_eqarr(el) -> str:
    """m:eqArr（方程组 / 等式数组）→ LaTeX"""
    rows = el.findall(_m("e"))
    row_strs = [_convert_children(r) for r in rows]
    inner = r" \\ ".join(row_strs)
    return rf"\begin{{aligned}} {inner} \end{{aligned}}"


def _convert_prescript(el) -> str:
    """m:sPre（前置上下标）→ LaTeX"""
    sub = el.find(_m("sub"))
    sup = el.find(_m("sup"))
    e = el.find(_m("e"))
    sub_s = _convert_children(sub) if sub is not None else ""
    sup_s = _convert_children(sup) if sup is not None else ""
    e_s = _convert_children(e) if e is not None else ""
    return f"{{}}_{{{sub_s}}}^{{{sup_s}}}{e_s}"


def _convert_groupchr(el) -> str:
    """m:groupChr（花括号分组）→ LaTeX"""
    chr_val = _get_val(el, "groupChrPr/chr")
    pos = _get_val(el, "groupChrPr/pos")
    e = el.find(_m("e"))
    e_s = _convert_children(e) if e is not None else ""
    if chr_val in GROUPCHR_MAP:
        cmd = GROUPCHR_MAP[chr_val]
        return f"{cmd}{{{e_s}}}"
    if pos == "bot":
        return rf"\underbrace{{{e_s}}}"
    return rf"\overbrace{{{e_s}}}"


def _convert_box(el) -> str:
    """m:box / m:borderBox（容器）→ LaTeX"""
    e = el.find(_m("e"))
    if e is not None:
        return _convert_children(e)
    return _convert_children(el)


def _convert_phant(el) -> str:
    """m:phant（幻影 / 占位符）→ LaTeX"""
    e = el.find(_m("e"))
    e_s = _convert_children(e) if e is not None else ""
    show = _get_val(el, "phantPr/show")
    if show == "0":
        return rf"\phantom{{{e_s}}}"
    return e_s


# ─── 元素分派表 ───────────────────────────────────────────────────────
_CONVERTERS = {
    "r": _convert_math_run,
    "f": _convert_fraction,
    "rad": _convert_radical,
    "sSup": _convert_superscript,
    "sSub": _convert_subscript,
    "sSubSup": _convert_subsuper,
    "nary": _convert_nary,
    "d": _convert_delimiter,
    "acc": _convert_accent,
    "bar": _convert_bar,
    "func": _convert_func,
    "limLow": _convert_limlower,
    "limUpp": _convert_limupper,
    "m": _convert_matrix,
    "eqArr": _convert_eqarr,
    "sPre": _convert_prescript,
    "groupChr": _convert_groupchr,
    "box": _convert_box,
    "borderBox": _convert_box,
    "phant": _convert_phant,
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  公开 API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def omml_to_latex(omath_el) -> str:
    """
    将 m:oMath 或 m:oMathPara 元素转为 LaTeX 字符串。

    Args:
        omath_el: ElementTree 元素，标签为 m:oMath 或 m:oMathPara

    Returns:
        LaTeX 字符串（不含 $ 包裹）
    """
    try:
        local = _local(omath_el)
        if local == "oMathPara":
            results: list[str] = []
            for omath in omath_el.findall(_m("oMath")):
                s = _convert_children(omath).strip()
                if s:
                    results.append(s)
            return r" \\ ".join(results)
        if local == "oMath":
            return _convert_children(omath_el).strip()
        return _convert_element(omath_el).strip()
    except Exception:
        return ""
