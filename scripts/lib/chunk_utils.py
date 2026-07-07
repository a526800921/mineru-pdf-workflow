"""
Chunk 预处理工具：将合并 Markdown 转换为下游可向量化的纯文本块。

对齐 motor-app §10 chunk 预处理规范：
1. 按 ## 标题切分 chunk（语义小节粒度）
2. HTML 表格 → 自然语言展开（规则转换）
3. 图片占位符 → 文字标注
4. 清洗 Markdown 标记
5. 导出 JSONL

不引入任何外部依赖，纯标准库实现。
"""

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional


# ---- 常量 ----

MAX_TOKENS = 384  # BGE 512 上限留余量
OVERLAP_SENTENCES = 2  # 相邻 chunk 重叠句数
TOKEN_LIMIT_RATIO = 0.85  # 超限触发再切分的阈值


# ---- Token 计数 ----

def count_tokens(text: str) -> int:
    """中文字数 + 英文单词数。中文按单字、英文/数字按空格分词。"""
    # 连续中文字符算单字
    cjk = len(re.findall(r"[一-鿿㐀-䶿]", text))
    # 英文/数字词
    en_words = len(re.findall(r"[a-zA-Z0-9]+", text))
    return cjk + en_words


# ---- HTML 表格解析 ----

class _TableParser(HTMLParser):
    """解析 HTML table，提取单元格文本矩阵。"""

    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._current_cell: str = ""
        self._in_cell = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag in ("td", "th"):
            self._in_cell = True
            self._current_cell = ""

    def handle_endtag(self, tag: str):
        if tag in ("td", "th"):
            self._in_cell = False
            self._current_row.append(self._current_cell.strip())
        elif tag == "tr":
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = []

    def handle_data(self, data: str):
        if self._in_cell:
            self._current_cell += data


def _parse_table_html(html: str) -> list[list[str]]:
    """将 HTML table 字符串解析为二维单元格列表。"""
    parser = _TableParser()
    parser.feed(html)
    return parser.rows


def _expand_table_to_text(html: str) -> str:
    """将 HTML 表格展开为自然语言键值对。

    策略：
    - 2 列且首列非空：视为键值对 → "键：值"
    - 多列：取首列作键，后续列的文本合成值
    - 单列：直接取文本（警告/注意块）
    """
    rows = _parse_table_html(html)
    if not rows:
        return ""

    # 清洗每行：去除空行
    clean_rows = [[c for c in row if c] for row in rows]
    clean_rows = [r for r in clean_rows if r]

    if not clean_rows:
        return ""

    parts: list[str] = []

    # 检测是否为简单键值对表格（2列且每行2个非空单元格）
    is_kv = all(len(r) >= 2 for r in clean_rows)
    # 检测是否为单属性警告块（首行作标题，次行作内容）
    is_warning = len(clean_rows) == 2 and len(clean_rows[0]) == 1 and len(clean_rows[1]) == 1

    if is_warning:
        # 警告/注意块：标题 — 内容
        label = clean_rows[0][0] if clean_rows[0] else ""
        content = clean_rows[1][0] if clean_rows[1] else ""
        if label and content:
            return f"{label} — {content}"
        return content or label

    if is_kv:
        for row in clean_rows:
            key = row[0]
            value = " / ".join(row[1:]) if len(row) > 1 else ""
            if key and value:
                parts.append(f"{key}：{value}")
    else:
        # 混合表格：尝试首列作键
        for row in clean_rows:
            text = " / ".join(row)
            parts.append(text)

    return "；".join(parts) if parts else ""


# ---- 图片替换 ----

_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

# 文件名→汉语标签的启发式映射（可扩展）
_FILENAME_HINTS = {
    "oil": "机油",
    "engine": "发动机",
    "frame": "车架",
    "brake": "刹车",
    "tire": "轮胎",
    "wheel": "车轮",
    "light": "灯光",
    "switch": "开关",
    "meter": "仪表",
    "fuel": "燃油",
    "coolant": "冷却液",
    "battery": "蓄电池",
    "fuse": "保险丝",
    "lock": "锁",
    "seat": "座椅",
    "helmet": "头盔",
    "storage": "储物",
    "mirror": "后视镜",
    "handle": "把手",
    "pedal": "踏板",
    "chain": "链条",
    "belt": "皮带",
    "filter": "滤清器",
    "pump": "泵",
    "valve": "阀门",
    "spring": "弹簧",
    "shock": "减震",
    "clutch": "离合器",
    "gear": "齿轮",
    "shaft": "轴",
    "bolt": "螺栓",
    "nut": "螺母",
    "screw": "螺丝",
    "washer": "垫圈",
    "bearing": "轴承",
    "seal": "密封",
    "gasket": "垫片",
    "hose": "软管",
    "pipe": "管路",
    "tank": "油箱",
    "cap": "盖子",
    "cover": "盖子",
    "panel": "面板",
    "cable": "线缆",
    "wire": "电线",
    "connector": "接头",
    "sensor": "传感器",
    "relay": "继电器",
    "motor": "电机",
    "fan": "风扇",
    "radiator": "散热器",
    "exhaust": "排气",
    "intake": "进气",
    "carburetor": "化油器",
    "injector": "喷油器",
    "cylinder": "气缸",
    "piston": "活塞",
    "crank": "曲轴",
    "cam": "凸轮",
}


def _replace_image(match: re.Match) -> str:
    """将 Markdown 图片替换为文字占位符。"""
    alt = match.group(1)
    src = match.group(2)

    if alt and alt.strip():
        return f"[示意图：{alt.strip()}]"

    # 从文件名推导描述
    filename = Path(src).stem.lower()
    for hint_key, hint_label in _FILENAME_HINTS.items():
        if hint_key in filename:
            return f"[示意图：{hint_label}]"

    return "[示意图]"


# ---- Markdown 清洗 ----

def _clean_inline_markdown(text: str) -> str:
    """去除行内 Markdown 标记，保留纯文本。"""
    # 去除粗体/斜体标记
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)
    # 去除行内代码
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # 去除链接 [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


def _clean_html_tags(text: str) -> str:
    """去除残留 HTML 标签和实体。"""
    # 去除 HTML 标签
    text = re.sub(r"<[^>]+>", "", text)
    # 常见 HTML 实体
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#39;", "'")
    text = text.replace("&nbsp;", " ")
    text = text.replace("&middot;", "·")
    text = text.replace("&times;", "×")
    return text


def clean_text(text: str) -> str:
    """完整清洗：图片替换 → 表格展开 → 去除标题标记 → 行内标记 → HTML 残留。"""
    # 1. 图片替换（先于任何清洗，避免 HTML 标签干扰）
    text = _IMAGE_RE.sub(_replace_image, text)

    # 2. HTML 表格展开（保留 HTML 表格文本，但转换为自然语言）
    text = _TABLE_RE.sub(lambda m: _expand_table_to_text(m.group(0)), text)

    # 3. 去除标题标记（保留标题文本）
    text = re.sub(r"^#{1,4}\s+", "", text, flags=re.MULTILINE)

    # 4. 行内 Markdown 标记
    text = _clean_inline_markdown(text)

    # 5. HTML 残留（包括非表格标签）
    text = _clean_html_tags(text)

    # 6. 清洗空白
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)

    return text.strip()


# 匹配 HTML table 元素（嵌套 depth 不限）
_TABLE_RE = re.compile(r"<table[^>]*>.*?</table>", re.DOTALL | re.IGNORECASE)


# ---- Chunk 切分 ----

_H2_RE = re.compile(r"^## (.+)$", re.MULTILINE)
_SENTENCE_RE = re.compile(r"(?<=[。！？.!?])\s*")


def chunk_markdown(md_text: str, model_name: str) -> list[dict]:
    """将合并 Markdown 切分为 chunk 列表。

    Args:
        md_text: 合并 Markdown 全文
        model_name: 模型名（用于 id 前缀）

    Returns:
        chunk 列表，每个 dict 含 id/content/page/section/token_count
    """
    # Step 0: 解析页面锚点，建立行号→页码范围映射
    page_anchors = list(re.finditer(r"^<!-- pages (\d+)-(\d+) -->\s*$", md_text, re.MULTILINE))
    page_map = _build_page_map(md_text, page_anchors)

    # Step 1: 按 ## 标题切分
    sections = _split_by_h2(md_text, page_anchors)

    # Step 2: 每个段清洗 + 再切分（超限时）
    chunks: list[dict] = []
    seq = 0

    for i, section in enumerate(sections):
        raw_text = section["text"]
        # 如果该段在页面锚点范围内，确定页码范围
        start_page, end_page = _find_page_range(section["pos"], page_map)
        section_title = section.get("title", "")

        # 清洗文本
        cleaned = clean_text(raw_text)
        if not cleaned:
            continue

        # 检查 token 是否超限
        if count_tokens(cleaned) <= MAX_TOKENS:
            seq += 1
            chunks.append({
                "id": f"{model_name}@seq_{seq:03d}",
                "content": cleaned,
                "page": f"{start_page}-{end_page}" if start_page != end_page else str(start_page),
                "section": section_title,
                "token_count": count_tokens(cleaned),
            })
        else:
            # 超限：按段落再切分
            sub_chunks = _split_long_chunk(
                cleaned, model_name, seq, start_page, end_page, section_title
            )
            for sc in sub_chunks:
                seq += 1
                sc["id"] = f"{model_name}@seq_{seq:03d}"
                chunks.append(sc)
            seq = int(chunks[-1]["id"].split("_")[-1]) if chunks else seq

    return chunks


def _build_page_map(
    text: str, anchors: list[re.Match]
) -> list[tuple[int, int, int]]:
    """(行首字节偏移, 起始页, 结束页) 列表。"""
    if not anchors:
        return []
    pmap = []
    for m in anchors:
        pmap.append((m.start(), int(m.group(1)), int(m.group(2))))
    return pmap


def _find_page_range(pos: int, page_map: list[tuple[int, int, int]]) -> tuple[int, int]:
    """根据文本位置找到所属的页码范围。"""
    if not page_map:
        return 1, 1
    for i, (anchor_pos, sp, ep) in enumerate(page_map):
        next_pos = page_map[i + 1][0] if i + 1 < len(page_map) else float("inf")
        if anchor_pos <= pos < next_pos:
            return sp, ep
    # 在第一个锚点之前
    return page_map[0][1], page_map[0][2]


def _split_by_h2(
    text: str, page_anchors: list[re.Match]
) -> list[dict]:
    """按 ## 标题切分文本，允许页面锚点成为子切分边界。"""
    # 收集所有切分点：## 标题 + 页面锚点
    split_points: list[tuple[int, str, str]] = []  # (pos, type, title)

    for m in re.finditer(r"^## (.+)$", text, re.MULTILINE):
        split_points.append((m.start(), "h2", m.group(1).strip()))

    # 同时也按页面锚点切分（如果 ## 标题间的文本跨越了分页段）
    for m in page_anchors:
        # 检查该锚点位置是否已在某个 ## 标题的首行
        already_split = any(
            abs(sp[0] - m.start()) < 5 for sp in split_points if sp[1] == "h2"
        )
        if not already_split:
            split_points.append((m.start(), "anchor", ""))

    split_points.sort(key=lambda x: x[0])

    # 去重：相邻切分点如果 < 5 字符，视为同一位置
    deduped = []
    for sp in split_points:
        if deduped and sp[0] - deduped[-1][0] < 5:
            # 保留 ## 标题优先
            if sp[1] == "h2":
                deduped[-1] = sp
        else:
            deduped.append(sp)

    sections = []
    last_title = ""  # 跟踪最近的 ## 标题，用于 anchor 段继承
    for i, (pos, stype, title) in enumerate(deduped):
        start = pos
        end = deduped[i + 1][0] if i + 1 < len(deduped) else len(text)
        section_text = text[start:end].strip()

        # anchor 段继承最近的前一个 ## 标题
        if stype == "anchor" and not title:
            title = last_title
        elif stype == "h2" and title:
            last_title = title

        sections.append({
            "pos": start,
            "type": stype,
            "title": title,
            "text": section_text,
        })

    return sections


def _split_long_chunk(
    text: str,
    model_name: str,
    start_seq: int,
    page_start: int,
    page_end: int,
    section: str,
) -> list[dict]:
    """将超长 chunk 按段落/句子再切分，保留 overlap。"""
    chunks: list[dict] = []

    # 按双换行切段落
    paragraphs = re.split(r"\n\n+", text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    current = ""
    current_tokens = 0

    for para in paragraphs:
        para_tokens = count_tokens(para)

        if current_tokens + para_tokens <= MAX_TOKENS:
            if current:
                current += "\n\n" + para
            else:
                current = para
            current_tokens += para_tokens
        else:
            # 当前积累块先保存
            if current:
                chunks.append({
                    "id": "",  # caller fills
                    "content": current,
                    "page": f"{page_start}-{page_end}" if page_start != page_end else str(page_start),
                    "section": section,
                    "token_count": count_tokens(current),
                })

            # 如果单个段落仍超限，按句子再切
            if para_tokens > MAX_TOKENS:
                sub = _split_by_sentence(para, page_start, page_end, section)
                chunks.extend(sub)
                current = ""
                current_tokens = 0
            else:
                # 保留 1-2 句 overlap，但确保不超限
                prev_sentences = _SENTENCE_RE.split(current)[-OVERLAP_SENTENCES:] if current else []
                overlap_text = "\n".join(prev_sentences) if prev_sentences else ""
                overlap_tokens = count_tokens(overlap_text)

                if overlap_tokens + para_tokens > MAX_TOKENS:
                    # overlap + para 超限：只保留 para 本身，不 overlap
                    current = para
                    current_tokens = para_tokens
                else:
                    current = (overlap_text + "\n\n" + para).strip() if overlap_text else para
                    current_tokens = count_tokens(current)

    if current:
        chunks.append({
            "id": "",
            "content": current,
            "page": f"{page_start}-{page_end}" if page_start != page_end else str(page_start),
            "section": section,
            "token_count": count_tokens(current),
        })

    return chunks


def _split_by_sentence(
    text: str, page_start: int, page_end: int, section: str
) -> list[dict]:
    """将超长段落按句子切分，保留 overlap。无句读时按字符数兜底切分。"""
    sentences = _SENTENCE_RE.split(text)
    sentences = [s.strip() for s in sentences if s.strip()]

    chunks = []
    current = ""
    current_tokens = 0

    for sent in sentences:
        st = count_tokens(sent)

        # 如果单句超限，按字符兜底切分（中文约 1 token/字）
        if st > MAX_TOKENS:
            # 先保存当前积累
            if current:
                chunks.append({
                    "id": "",
                    "content": current,
                    "page": f"{page_start}-{page_end}" if page_start != page_end else str(page_start),
                    "section": section,
                    "token_count": count_tokens(current),
                })
                current = ""
                current_tokens = 0

            # 字符级切分：每 MAX_TOKENS 字符一段（中文场景下 ≈ token 数）
            for i in range(0, len(sent), MAX_TOKENS):
                piece = sent[i:i + MAX_TOKENS]
                chunks.append({
                    "id": "",
                    "content": piece.strip(),
                    "page": f"{page_start}-{page_end}" if page_start != page_end else str(page_start),
                    "section": section,
                    "token_count": count_tokens(piece),
                })
            continue

        if current_tokens + st <= MAX_TOKENS:
            current = (current + " " + sent).strip() if current else sent
            current_tokens += st
        else:
            if current:
                chunks.append({
                    "id": "",
                    "content": current,
                    "page": f"{page_start}-{page_end}" if page_start != page_end else str(page_start),
                    "section": section,
                    "token_count": count_tokens(current),
                })

            # overlap: 保留前 1-2 句，但确保不超限
            prev = _SENTENCE_RE.split(current)[-OVERLAP_SENTENCES:] if current else []
            overlap_text = " ".join(prev) if prev else ""
            overlap_tokens = count_tokens(overlap_text)

            if overlap_tokens + st > MAX_TOKENS:
                current = sent
                current_tokens = st
            else:
                current = (overlap_text + " " + sent).strip() if overlap_text else sent
                current_tokens = count_tokens(current)

    if current:
        chunks.append({
            "id": "",
            "content": current,
            "page": f"{page_start}-{page_end}" if page_start != page_end else str(page_start),
            "section": section,
            "token_count": count_tokens(current),
        })

    return chunks


# ---- 导出入口 ----

def export_chunks(
    package_dir: Path,
    output_path: Optional[Path] = None,
) -> tuple[list[dict], Path]:
    """从输出包导出 chunks.jsonl。

    Args:
        package_dir: 输出包根目录
        output_path: 输出路径，默认 `<package>/data/chunks.jsonl`

    Returns:
        (chunks列表, 输出文件路径)
    """
    # 读取 manifest 获取 model 名
    manifest_path = package_dir / "manifest.json"
    model_name = package_dir.name
    if manifest_path.is_file():
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
            model_name = manifest.get("model", model_name)
        except Exception:
            pass

    # 读取合并 Markdown
    md_path = None
    for f in package_dir.glob("*.md"):
        if f.name != "review.md":
            md_path = f
            break

    if md_path is None:
        raise FileNotFoundError(f"未找到合并 Markdown 文件：{package_dir}")

    md_text = md_path.read_text(encoding="utf-8", errors="replace")

    # 切分
    chunks = chunk_markdown(md_text, model_name)

    # 输出
    if output_path is None:
        data_dir = package_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        output_path = data_dir / "chunks.jsonl"

    with open(output_path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    return chunks, output_path
