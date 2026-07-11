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


# ── 通用表格字段缺失检测 ──────────────────────────

def _normalize_table_text(text: str) -> str:
    """归一化表格文本：统一全角→半角、空白折叠。"""
    text = text.strip()
    text = text.translate(str.maketrans(
        "０１２３４５６７８９ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ"
        "ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ",
        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "abcdefghijklmnopqrstuvwxyz",
    ))
    text = text.replace("：", ":").replace("（", "(").replace("）", ")")
    text = text.replace("，", ",").replace("；", ";")
    text = re.sub(r"\s+", "", text)
    return text


def _expand_html_table_grid(table_html: str) -> list[list[str]]:
    """
    展开单个 HTML <table>，考虑 colspan，返回逻辑网格（行 × 列）。
    同一单元格因 colspan 展开多次时各副本保留相同文本。
    """
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL | re.IGNORECASE)
    grid: list[list[str]] = []
    for row_html in rows:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.DOTALL | re.IGNORECASE)
        expanded: list[str] = []
        for td in tds:
            text_raw = re.sub(r"<[^>]+>", "", td).strip()
            cs_match = re.search(
                r'colspan\s*=\s*["\'"]?(\\d+)["\'"]?', td, re.IGNORECASE,
            )
            cs = int(cs_match.group(1)) if cs_match else 1
            for _ in range(cs):
                expanded.append(text_raw)
        grid.append(expanded)
    return grid


def _parse_all_tables(md_text: str) -> list[list[list[str]]]:
    """提取所有 HTML <table>，展开为逻辑网格，返回≥3行的规格表列表。"""
    tables: list[list[list[str]]] = []
    for m in re.finditer(r"<table>(.*?)</table>", md_text, re.DOTALL | re.IGNORECASE):
        grid = _expand_html_table_grid(m.group(1))
        if len(grid) >= 3:
            tables.append(grid)
    return tables


def _cluster_pdf_words(
    pdf_words: list[tuple],
    page_height: float = 400.0,
) -> list[list[tuple[float, float, float, str]]]:
    """
    按 y 坐标重叠将 PDF words 聚类为视觉行。
    过滤页脚（底部 15%）和纯数字页码。
    返回 list[visual_line]，每行按 x0 排序。
    """
    FOOTER_Y = page_height * 0.85
    filtered = [
        w for w in pdf_words
        if w[4].strip() and not re.match(r"^\d+$", w[4].strip()) and w[1] <= FOOTER_Y
    ]
    if not filtered:
        return []

    filtered.sort(key=lambda w: (w[1], w[0]))
    lines: list[list] = []
    current: list = []
    cur_y1 = 0.0

    for w in filtered:
        y0, y1 = w[1], w[3]
        if not current or y0 <= cur_y1:
            current.append(w)
            cur_y1 = max(cur_y1, y1)
        else:
            lines.append(sorted(current, key=lambda x: x[0]))
            current = [w]
            cur_y1 = y1
    if current:
        lines.append(sorted(current, key=lambda x: x[0]))

    result: list[list[tuple[float, float, float, str]]] = []
    for line in lines:
        result.append([(w[0], w[2], (w[1] + w[3]) / 2, w[4].strip()) for w in line])
    return result


def detect_native_table_text_omission(
    md_text: str,
    pdf_words: list[tuple],
    page_width: float = 600.0,
    page_height: float = 400.0,
) -> tuple[list[str], dict]:
    """
    检测 MinerU HTML 表格中遗漏的 PDF 原生表格字段。

    算法：
    1. 解析所有 HTML <table> → 展开 colspan → 逻辑网格
    2. 提取所有网格文本 → html_all；首列文本 → html_first_col
    3. PDF words 按 y 聚类为视觉行
    4. 逐行：若任一 word 匹配 html_all（确认是表格行），
       检查该行左列候选标签在 html_first_col 中是否存在
    5. 遗漏 → native_table_text_missing
    """
    tables = _parse_all_tables(md_text)
    if not tables:
        return [], {"native_table_candidates": 0, "native_table_missing": 0, "missing_text": []}

    html_all: set[str] = set()
    html_first_col: set[str] = set()
    for grid in tables:
        for row in grid:
            for ct in row:
                if ct.strip():
                    html_all.add(_normalize_table_text(ct))
            if row and row[0].strip():
                html_first_col.add(_normalize_table_text(row[0]))

    if not html_all:
        return [], {"native_table_candidates": 0, "native_table_missing": 0, "missing_text": []}

    visual_lines = _cluster_pdf_words(pdf_words, page_height)
    if not visual_lines:
        return [], {"native_table_candidates": 0, "native_table_missing": 0, "missing_text": []}

    # 确定左右分界 x：从 html_all 匹配到的 words 中取最小 x0
    right_x0s = [x0 for line in visual_lines for x0, _, _, t in line
                 if _normalize_table_text(t) in html_all]
    split_x = max(page_width * 0.3, (min(right_x0s) * 0.9 if right_x0s else page_width * 0.4))

    # 逐行检测：仅对至少有一个 word 匹配 html_all 的视觉行
    missing_raw: set[str] = set()
    for line in visual_lines:
        has_html_match = any(_normalize_table_text(t) in html_all for _, _, _, t in line)
        if not has_html_match:
            continue
        for x0, _, _, text in line:
            norm = _normalize_table_text(text)
            if norm in html_all:
                continue  # 已在表格中
            if x0 >= split_x:
                continue  # 右列正文
            if norm not in html_first_col:
                missing_raw.add(text)

    missing_texts = sorted(missing_raw)
    signals = ["native_table_text_missing"] if missing_texts else []
    return signals, {
        "native_table_candidates": len(html_first_col),
        "native_table_missing": len(missing_texts),
        "missing_text": missing_texts,
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
