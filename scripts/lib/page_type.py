"""PDF 页面类型共享判定口径。"""

import re


_TOKEN_NORMALIZE_RE = re.compile(r"[·•.。．,，:：;；!！?？\-_—~～()（）\[\]【】<>《》/\\|]")
_TOKEN_RE = re.compile(r"[a-z0-9]+|[一-鿿]")
_TOC_PATTERN = re.compile(r"[.]{4,}\s*\d+")


def text_tokens(text: str) -> list[str]:
    """按 pdf-validate 的口径提取文本 token。"""
    normalized = text.lower()
    normalized = _TOKEN_NORMALIZE_RE.sub(" ", normalized)
    return _TOKEN_RE.findall(normalized)


def is_image_or_sparse_page(pdf_text: str, cl_page_items: list | None) -> bool:
    """判断页面是否属于视觉页或稀疏文本页。

    content_list 含 image 时直接判定；否则使用与 pdf-validate 相同的
    中英文 token 统计，避免 Python ``str.split`` 对连续中文只计 1 token。
    """
    cl_types = {
        item.get("type")
        for item in (cl_page_items or [])
        if isinstance(item, dict)
    }
    return "image" in cl_types or len(text_tokens(pdf_text)) < 15


def is_toc_page(pdf_text: str, cl_page_items: list | None) -> bool:
    """按 pdf-validate 的口径识别目录页。"""
    items = cl_page_items or []
    token_count = len(text_tokens(pdf_text))
    toc_lines = len(_TOC_PATTERN.findall(pdf_text))
    has_toc_title = "目录" in pdf_text or "目錄" in pdf_text
    return toc_lines >= 3 or (has_toc_title and len(items) <= 5 and token_count > 50)
