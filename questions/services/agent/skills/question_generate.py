"""
高中数学试题生成技能：根据用户描述生成对应的高中数学题目。
输出纯文本（【题干】【答案】【解析】），并解析为结构化题目供多选下载试卷。
"""

import re
from typing import Any, Dict, Iterator, List

from langchain_core.messages import SystemMessage, HumanMessage

from .base import BaseSkill
from ...config_loader import get_doubao_config


def _text_to_blocks(text: str) -> List[Dict[str, Any]]:
    """将含 $$latex$$ 的文本拆成 text/latex 块，与 to_dict 中 ContentBlock 一致。"""
    if not (text or text.strip()):
        return []
    blocks = []
    # 按 $$...$$ 分割，奇数段为 latex
    parts = re.split(r"\$\$(.*?)\$\$", text.strip(), flags=re.DOTALL)
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        if i % 2 == 1:
            blocks.append({"type": "latex", "content": part})
        else:
            blocks.append({"type": "text", "content": part})
    if not blocks:
        blocks = [{"type": "text", "content": text.strip()}]
    return blocks


def _parse_generated_question(content: str) -> Dict[str, Any] | None:
    """
    从生成技能的输出解析出单道题目的结构化 dict（与 to_dict 格式兼容，便于导出试卷）。
    格式：【题干】...【答案】...【解析】...，公式用 $$...$$。
    """
    if not (content or content.strip()):
        return None
    text = content.strip()
    body, answer, analysis = "", "", ""
    # 【题干】...【答案】...【解析】...
    m_body = re.search(r"【题干】\s*(.*?)(?=【答案】|【解析】|$)", text, re.DOTALL)
    if m_body:
        body = m_body.group(1).strip()
    m_ans = re.search(r"【答案】\s*(.*?)(?=【解析】|$)", text, re.DOTALL)
    if m_ans:
        answer = m_ans.group(1).strip()
    m_ana = re.search(r"【解析】\s*(.*?)$", text, re.DOTALL)
    if m_ana:
        analysis = m_ana.group(1).strip()
    if not body and not answer:
        return None
    return {
        "questionType": "solution",
        "questionBody": _text_to_blocks(body) if body else [{"type": "text", "content": ""}],
        "answer": _text_to_blocks(answer) if answer else [],
        "analysis": _text_to_blocks(analysis) if analysis else [],
        "detailedSolution": [],
        "assetBaseUrl": "",
    }


GENERATE_SYSTEM = """你是一名高中数学命题专家。根据用户描述，直接生成一道符合要求的高中数学题目。

输出格式（必须严格遵循，方便前端解析）：
1. 【题干】后接题干内容，选择题的选项（A、B、C、D）写在题干中
2. 【答案】后接答案内容
3. 【解析】后接简要解析（可选）
4. 数学公式必须用 LaTeX 表示，用 $$公式$$ 包裹（不要用 \( \)），例如：已知 $$x^2+y^2=1$$ 则...
5. 题干和答案必须用【题干】【答案】明确区分
6. 题目难度适中，符合高中数学课程标准"""


def _get_llm(model_override: str = None):
    cfg = get_doubao_config()
    api_key = cfg.get("api_key")
    if not api_key:
        raise ValueError("未配置 DOUBAO_API_KEY，试题生成功能不可用")
    from langchain_openai import ChatOpenAI
    model = (model_override or "").strip() or cfg.get("model", "doubao-1.5-pro-32k-250115")
    kw = {
        "api_key": api_key,
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": model,
    }
    if cfg.get("disable_proxy"):
        import httpx
        kw["http_client"] = httpx.Client(trust_env=False)
    return ChatOpenAI(**kw)


class QuestionGenerateSkill(BaseSkill):
    """高中数学试题生成技能。"""

    intent = "generate_questions"
    name = "生成试题"

    def invoke(self, user_query: str, **kwargs) -> Dict[str, Any]:
        llm_model = kwargs.get("llm_model")

        try:
            llm = _get_llm(model_override=llm_model)
            resp = llm.invoke([
                SystemMessage(content=GENERATE_SYSTEM),
                HumanMessage(content=f"请根据以下描述生成一道高中数学题目：\n\n{user_query}"),
            ])
            content = (resp.content or "").strip()
            if not content:
                content = "抱歉，未生成出有效题目，请尝试换一种描述方式。"
        except Exception as e:
            content = f"题目生成失败：{str(e)}"

        questions = []
        parsed = _parse_generated_question(content)
        if parsed:
            questions = [parsed]

        return {
            "content": content,
            "questions": questions,
            "intent": self.intent,
            "skill_used": self.name,
        }

    def invoke_stream(
        self,
        user_query: str,
        **kwargs,
    ) -> Iterator[Dict[str, Any]]:
        """流式生成：直接输出纯文本。"""
        llm_model = kwargs.get("llm_model")

        try:
            llm = _get_llm(model_override=llm_model)
            full_text = []
            for chunk in llm.stream([
                SystemMessage(content=GENERATE_SYSTEM),
                HumanMessage(content=f"请根据以下描述生成一道高中数学题目：\n\n{user_query}"),
            ]):
                if hasattr(chunk, "content") and chunk.content:
                    full_text.append(chunk.content)
                    yield {"type": "chunk", "content": chunk.content}

            content = "".join(full_text).strip()
            if not content:
                content = "抱歉，未生成出有效题目，请尝试换一种描述方式。"
        except Exception as e:
            content = f"题目生成失败：{str(e)}"

        questions = []
        parsed = _parse_generated_question(content)
        if parsed:
            questions = [parsed]

        yield {
            "type": "done",
            "content": content,
            "questions": questions,
            "intent": self.intent,
            "skill_used": self.name,
        }
