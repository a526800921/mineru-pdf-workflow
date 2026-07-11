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
    pdf_words: list[tuple] | None = None,
    page_width: float = 600.0,
    page_height: float = 400.0,
) -> dict:
    """
    对单页运行全部质量信号检测（含可选的通用表格字段缺失检测）。

    参数：
        md_text:       MinerU 输出的该页 Markdown 文本
        pdf_page_text: PyMuPDF 提取的该页原生文本
        pdf_words:     PyMuPDF get_text("words") 含 bbox 的逐词数据（可选）
                       传入后启用 native_table_text_missing 信号
        page_width:    PDF 页面宽度（用于表格区域判定）
        page_height:   PDF 页面高度（用于页脚排除）

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

    # 5 ── 通用表格字段缺失（可选，需 pdf_words）────────────
    if pdf_words is not None:
        fb_signals, fb_metrics = detect_native_table_text_omission(
            md_text, pdf_words, page_width, page_height,
        )
        signals.extend(fb_signals)
        metrics["native_table_candidates"] = fb_metrics.get("native_table_candidates", 0)
        metrics["native_table_missing"] = fb_metrics.get("native_table_missing", 0)
        if fb_metrics.get("missing_text"):
            metrics["missing_text"] = fb_metrics["missing_text"]

    return {
        "signals": signals,
        "metrics": metrics,
        "quality_ok": len(signals) == 0,
    }


# ── 通用表格字段缺失检测（阶段 5 新增）───────────────────────

def _normalize_table_text(text: str) -> str:
    """
    归一化表格文本用于比较：统一全角→半角、空白折叠、去两端。
    """
    text = text.strip()
    # 全角字母数字 → 半角
    text = text.translate(str.maketrans(
        "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
        "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz",
    ))
    # 全角标点 → 半角（保留冒号用于数值单位判断）
    text = text.replace("：", ":").replace("（", "(").replace("）", ")")
    text = text.replace("，", ",").replace("；", ";")
    # 折叠空白
    text = re.sub(r"\s+", "", text)
    return text


def _extract_html_cell_texts(md_text: str) -> set[str]:
    """
    从 MinerU Markdown 的 HTML <table> 中提取所有非空逻辑单元格文本。
    考虑 colspan/rowspan 展开，返回归一化后的去重集合。
    """
    m = re.search(r"<table>(.*?)</table>", md_text, re.DOTALL | re.IGNORECASE)
    if not m:
        return set()

    table_html = m.group(1)
    cells: set[str] = set()

    # 提取所有 <td> 文本，忽略属性
    for td in re.findall(r"<td[^>]*>(.*?)</td>", table_html, re.DOTALL):
        text = td.strip()
        if text and not re.match(r"^\s*$", text):
            cells.add(_normalize_table_text(text))

    return cells


def _is_spec_table(md_text: str) -> bool:
    """
    判断 HTML 表格是否为真正的规格表（≥ 3 行）。
    排除 2 行以内的警告框、装饰性框等。
    """
    m = re.search(r"<table>(.*?)</table>", md_text, re.DOTALL | re.IGNORECASE)
    if not m:
        return False
    rows = len(re.findall(r"<tr[^>]*>", m.group(1)))
    return rows >= 3


def _find_pdf_table_labels(
    pdf_words: list[tuple],
    page_width: float = 600.0,
    page_height: float = 400.0,
) -> set[str]:
    """
    从 PDF 原生 words 中提取表格区域内的左列候选标签。

    pdf_words: PyMuPDF get_text("words") 输出，每项为
               (x0, y0, x1, y1, word, block_no, line_no, word_no)

    判定规则：
    - 左列文字：x0 < page_width × 0.4（排除右列数值和页脚页码）
    - 排除页脚区域：y > page_height × 0.85（页码、页脚）
    - 排除页码样式的纯数字
    - 标签长度 <= 30 字符（排除大段正文被误当表格标签）
    """
    labels: set[str] = set()
    left_col_x = page_width * 0.4
    footer_y = page_height * 0.85

    for w in pdf_words:
        x0, y0, x1, y1, text = w[0], w[1], w[2], w[3], w[4]
        text = text.strip()
        if not text:
            continue
        # 排除右列数值区域
        if x0 >= left_col_x:
            continue
        # 排除页脚
        if y0 > footer_y:
            continue
        # 排除纯数字页码
        if re.match(r"^\d+$", text):
            continue
        # 表格标签通常是短字段名，排除长句正文
        if len(text) > 30:
            continue
        labels.add(_normalize_table_text(text))

    return labels


def detect_native_table_text_omission(
    md_text: str,
    pdf_words: list[tuple],
    page_width: float = 600.0,
    page_height: float = 400.0,
) -> tuple[list[str], dict]:
    """
    检测 MinerU HTML 表格中是否遗漏了 PDF 原生文本中的表格字段。

    返回 (signals, metrics):
        signals: ["native_table_text_missing"] 或 []
        metrics: {
            "native_table_candidates": int,      # PDF 表格区域候选标签数
            "native_table_missing": int,          # 遗漏数
            "missing_text": list[str],            # 遗漏的原文
        }
    """
    # 1. 检查页面是否有合格的规格表（≥ 3 行）
    if not _is_spec_table(md_text):
        return [], {"native_table_candidates": 0, "native_table_missing": 0,
                     "missing_text": []}
    html_cells = _extract_html_cell_texts(md_text)
    if not html_cells:
        return [], {"native_table_candidates": 0, "native_table_missing": 0,
                     "missing_text": []}

    # 2. 从 PDF 提取左列候选标签
    pdf_labels = _find_pdf_table_labels(pdf_words, page_width, page_height)
    if not pdf_labels:
        return [], {"native_table_candidates": 0, "native_table_missing": 0,
                     "missing_text": []}

    # 3. 比较：PDF 中存在但 HTML 中缺失的标签
    missing = sorted(pdf_labels - html_cells)

    signals = []
    if missing:
        signals.append("native_table_text_missing")

    return signals, {
        "native_table_candidates": len(pdf_labels),
        "native_table_missing": len(missing),
        "missing_text": missing,
    }


def compare_quality(
    original_metrics: dict,
    fallback_metrics: dict,
) -> str:
    """
    比较 original 和 fallback 的质量指标，返回选择建议。

    判定维度：
        1. 表格结构：空 <td> 数量、单行最大列数
        2. 文本完整性：文本覆盖率、Markdown 体积

    返回值：
        "fallback" — 表格结构明显改善且文本完整性未退化
        "original" — 表格结构无改善且文本完整性退化
        "review"   — 无法明确判断

    判定逻辑：
        - 表格改善 = 空 <td> 减少至少一半 或 单行列数减少至少 20%
        - 文本 OK = 文本覆盖率保持原始 80% 以上（最小值 0.3）
                     且 MD 字节保持原始 80% 以上；如果覆盖率上升，允许
                     Markdown 因删除重复空单元格而显著变小
        - 改善且文本 OK → fallback
        - 未改善且文本丢失 → original
        - 其它组合 → review
    """
    orig_empty = original_metrics.get("empty_td", 0)
    fb_empty = fallback_metrics.get("empty_td", 0)
    orig_cols = original_metrics.get("max_td_per_row", 0)
    fb_cols = fallback_metrics.get("max_td_per_row", 0)
    orig_bytes = original_metrics.get("md_bytes", 0)
    fb_bytes = fallback_metrics.get("md_bytes", 0)
    orig_cov = original_metrics.get("text_coverage", 1.0)
    fb_cov = fallback_metrics.get("text_coverage", 1.0)

    # 表格结构改善
    td_improved = fb_empty < orig_empty * 0.5 if orig_empty > 0 else False
    col_improved = fb_cols < orig_cols * 0.8 if orig_cols > 0 else False
    structurally_better = td_improved or col_improved

    # 文本完整性（覆盖率为主信号，体积为辅助）
    # 相等时直接判 OK（避免极低覆盖率被 0.3 下限误判）
    cov_ok: bool
    if fb_cov == orig_cov:
        cov_ok = True
    elif orig_cov < 1.0:
        cov_ok = fb_cov >= max(orig_cov * 0.8, 0.3)
    else:
        cov_ok = True

    vol_ok = fb_bytes >= orig_bytes * 0.8 if orig_bytes > 0 else True

    # 表格异常常由重复空单元格造成；此时总 Markdown 体积可能从数百 KB
    # 降到正常正文大小，不能把体积下降本身当成文本丢失。覆盖率上升时，
    # 以覆盖率作为更可靠的文本完整性证据。
    text_ok = cov_ok and (vol_ok or fb_cov > orig_cov)

    if structurally_better:
        # 表格改善 —— 文本完整性保留则采纳
        return "fallback" if text_ok else "review"
    else:
        # 表格无改善 —— 文本覆盖保留则待审，丢失则保留原文
        return "original" if not cov_ok else "review"
