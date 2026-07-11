"""
页级质量检测共享库。

提供：
- assess_page_quality(): 对单页运行四个质量信号检测（纯函数，不读写磁盘）
- compare_quality(): 比较 original 和 fallback 的质量指标，返回选择建议

依赖：
- 调用方负责提供 Markdown 文本和 PDF 原生文本
- 不依赖 content_list_v2.json（表格分析直接从 Markdown HTML 提取）
"""

import re
from collections.abc import Sequence

# ── 信号阈值（计划契约锁定） ──────────────────────────────
EMPTY_TD_THRESHOLD = 100          # 空 <td></td> ≥ 100
MAX_TD_PER_ROW_THRESHOLD = 20     # 单行 <td> ≥ 20
VOLUME_INFLATION_MULTIPLIER = 4   # Markdown 字节 ≥ PDF 原生字节 × 4
VOLUME_INFLATION_MIN_BYTES = 20480  # 且 ≥ 20 KiB
TEXT_COVERAGE_MIN_PDF_TOKENS = 50   # PDF 原生 token ≥ 50
TEXT_COVERAGE_THRESHOLD = 0.5       # 且覆盖率 < 50%


# ── 内部工具 ─────────────────────────────────────────────

def _strip_punct(token: str) -> str:
    """对单个 token 去掉标点符号。"""
    return re.sub(
        r"[·•.。．,，:：;；!！?？\-_—~～()（）\[\]【】<>《》/\\|]",
        "", token,
    )


def _tokens(text: str) -> list[str]:
    """
    英文数字连续词 + 中文单字。

    先按空白分节，再逐节提取 token，最后对每个 token 去标点。
    保留英文单词边界：'word1 word2' → ['word1', 'word2']（而非合并为一个）。
    """
    tokens: list[str] = []
    for segment in text.split():
        segment = segment.lower()
        # 从该节中提取英文数字连续词和中文单字
        for raw in re.findall(r"[a-z0-9]+|[一-鿿]", segment):
            cleaned = _strip_punct(raw)
            if cleaned:
                tokens.append(cleaned)
    return tokens


# ── 四个质量信号检测 ─────────────────────────────────────

def count_empty_td(md_text: str) -> int:
    """统计 Markdown HTML 中的空 <td></td> 或 <td> </td> 个数。"""
    return len(re.findall(r"<td>\s*</td>", md_text, re.IGNORECASE | re.DOTALL))


def max_td_per_row(md_text: str) -> int:
    """
    找出单一 <tr> 中 <td> 的最大数量。

    若 Markdown 中无表格 HTML，返回 0。
    """
    rows = re.findall(
        r"<tr[^>]*>(.*?)</tr>", md_text, re.IGNORECASE | re.DOTALL,
    )
    if not rows:
        return 0
    max_count = 0
    for row in rows:
        count = len(re.findall(r"<td[^>]*>", row, re.IGNORECASE))
        if count > max_count:
            max_count = count
    return max_count


def check_volume_inflation(md_text: str, pdf_text: str) -> bool:
    """
    Markdown 体积相对 PDF 原生文字异常膨胀。

    条件：Markdown UTF-8 字节数 >= PDF 原生文字字节数 × 4
          且 Markdown 字节数 >= 20 KiB
    PDF 原生文字为空时不命中（无文本层页面不误判）。
    """
    md_bytes = len(md_text.encode("utf-8"))
    pdf_bytes = len(pdf_text.encode("utf-8"))
    if pdf_bytes == 0:
        return False
    return (
        md_bytes >= pdf_bytes * VOLUME_INFLATION_MULTIPLIER
        and md_bytes >= VOLUME_INFLATION_MIN_BYTES
    )


def check_text_coverage(md_text: str, pdf_text: str) -> tuple[bool, float]:
    """
    PDF 原生存在文字但 MinerU 输出明显缺失。

    命中条件：PDF 原生 token ≥ 50 且覆盖率 < 50%。
    覆盖率 = 匹配 token 数 / PDF token 总数（分子分母均去重）。
    返回 (已命中, 覆盖率比率)。
    """
    pdf_toks = _tokens(pdf_text)
    if len(pdf_toks) < TEXT_COVERAGE_MIN_PDF_TOKENS:
        return False, 1.0

    md_toks = _tokens(md_text)
    from collections import Counter

    pdf_counts = Counter(pdf_toks)
    md_counts = Counter(md_toks)

    matched = sum(
        min(count, md_counts.get(token, 0))
        for token, count in pdf_counts.items()
    )
    total = sum(pdf_counts.values())
    coverage = matched / total if total > 0 else 1.0

    return coverage < TEXT_COVERAGE_THRESHOLD, coverage


# ── 主入口 ───────────────────────────────────────────────

def assess_page_quality(
    md_text: str,
    pdf_page_text: str,
) -> dict:
    """
    对单页运行全部四个质量信号检测。

    参数：
        md_text:      MinerU 输出的该页 Markdown 文本
        pdf_page_text: PyMuPDF 提取的该页原生文本

    返回 dict：
        signals:   list[str]  触发的信号名称列表
        metrics:   dict       原始质量指标
        quality_ok: bool       无异常（signals 为空）
        _signals_detail: list[dict]  每个信号的详细判定理由
    """
    signals: list[str] = []
    metrics: dict = {}

    # 1 ── 空 <td> 检测 ──────────────────────────────────
    empty_td = count_empty_td(md_text)
    metrics["empty_td"] = empty_td
    if empty_td >= EMPTY_TD_THRESHOLD:
        signals.append("excessive_empty_td")

    # 2 ── 单行 <td> 最大数量 ─────────────────────────────
    max_per_row = max_td_per_row(md_text)
    metrics["max_td_per_row"] = max_per_row
    if max_per_row >= MAX_TD_PER_ROW_THRESHOLD:
        signals.append("excessive_columns")

    # 3 ── 体积膨胀 ───────────────────────────────────────
    md_bytes = len(md_text.encode("utf-8"))
    pdf_bytes = len(pdf_page_text.encode("utf-8"))
    metrics["md_bytes"] = md_bytes
    metrics["pdf_bytes"] = pdf_bytes
    if check_volume_inflation(md_text, pdf_page_text):
        signals.append("volume_inflation")

    # 4 ── 文本缺失 ───────────────────────────────────────
    low_cov, coverage = check_text_coverage(md_text, pdf_page_text)
    metrics["text_coverage"] = round(coverage, 4)
    pdf_tok_count = len(_tokens(pdf_page_text))
    metrics["pdf_tokens"] = pdf_tok_count
    if low_cov:
        signals.append("text_coverage_low")

    return {
        "signals": signals,
        "metrics": metrics,
        "quality_ok": len(signals) == 0,
    }


def compare_quality(
    original_metrics: dict,
    fallback_metrics: dict,
) -> str:
    """
    比较 original 和 fallback 的质量指标，返回选择建议。

    返回值：
        "original" — fallback 无改善或更差
        "fallback" — 空单元格明显减少，文本没有明显减少
        "review"   — 无法明确判断（一个改善、一个恶化）

    判定逻辑：
        - fallback 空 <td> 减少至少一半 → 改善
        - fallback 文本量保持原始 80% 以上 → 文本 OK
        - 改善且文本 OK → fallback
        - 未改善且文本丢失 → original
        - 其它组合 → review
    """
    orig_empty = original_metrics.get("empty_td", 0)
    fb_empty = fallback_metrics.get("empty_td", 0)
    orig_bytes = original_metrics.get("md_bytes", 0)
    fb_bytes = fallback_metrics.get("md_bytes", 0)

    # fallback 空单元格减少至少一半
    td_improved = fb_empty < orig_empty * 0.5 if orig_empty > 0 else (fb_empty == 0)

    # fallback 文本保留至少 80%
    text_ok = fb_bytes >= orig_bytes * 0.8 if orig_bytes > 0 else True

    if td_improved and text_ok:
        return "fallback"
    elif not td_improved and not text_ok:
        return "original"
    else:
        return "review"
