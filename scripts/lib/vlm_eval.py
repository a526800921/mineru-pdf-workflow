#!/usr/bin/env python3
"""多模态 VLM 图表理解（P4c）。

对输出包中 image_or_sparse 页整页渲染 → 调本地 VLM（qwen3-vl-8b）→
结构化描述 → 输出 data/vlm_eval.jsonl。

零新增依赖：fitz（已有）、openai（已有）、json（stdlib）。
"""
import base64
import json
import os
import re
from pathlib import Path


# ── 可复用：与 table_eval.py 同源口径 ──
_SEGMENT_RE = re.compile(r"^p(\d{4,})-(\d{4,})$")
_ANCHOR_RE = re.compile(r"^<!-- pages (\d+)-(\d+) -->\s*$", re.MULTILINE)
_H2_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


def parse_segment_name(name: str):
    """解析段目录名 pXXXX-YYYY，返回 (start_page, end_page)（1-based）或 None。

    复用 pdf-merge 的段名口径：严格 ^pXXXX-YYYY$，排除 rerun 后缀目录。
    """
    m = _SEGMENT_RE.match(name)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def build_section_index(md_text: str) -> list:
    """解析合并 Markdown，返回 [(seg_start, seg_end, section_title), ...]。

    段级近似：取每个页锚点区间内第一个 ## 标题，缺省空串。
    """
    if not md_text:
        return []
    anchors = [
        (m.start(), int(m.group(1)), int(m.group(2)))
        for m in _ANCHOR_RE.finditer(md_text)
    ]
    index = []
    for i, (pos, s, e) in enumerate(anchors):
        next_pos = anchors[i + 1][0] if i + 1 < len(anchors) else len(md_text)
        seg_text = md_text[pos:next_pos]
        hm = _H2_RE.search(seg_text)
        index.append((s, e, hm.group(1).strip() if hm else ""))
    return index


def section_for_page(index: list, page: int) -> str:
    """在 build_section_index 的结果中查 page 所属 section，缺省空串。"""
    for s, e, title in index:
        if s <= page <= e:
            return title
    return ""


# ── 常量 ──

DEFAULT_API_BASE = "http://127.0.0.1:9005"
DEFAULT_MODEL = "qwen3-vl-8b"
DEFAULT_DPI = 200

# VLM 响应 Schema 类型定义（用于 validate_vlm_response）
VLM_SCHEMA = {
    "page_summary": (str, type(None)),
    "visual_elements": (list,),
    "key_text": (list,),
    "confidence": (int, float, type(None)),
}


# ── 字段标准化 ──

_EXPECTED_FIELDS = {"page_summary", "visual_elements", "key_text", "confidence"}


def _normalize_vlm_fields(data: dict) -> dict:
    """标准化 VLM 返回的字段名。

    某些模型（如 MLX 8bit 量化 qwen3-vl-8b）会在字段名前加 `.` 前缀
    （`.page_summary` 而非 `page_summary`）。本函数做两步修复：
    1. 若不含预期字段但含带点号版本的字段，拷贝到无点号版本
    2. visual_elements 内子元素可能用 "text" 而非 "description"，也做映射
    """
    if not isinstance(data, dict):
        return data

    # Step 1: find dot-prefixed keys that match expected fields
    for key in list(data):
        if key.startswith(".") and key[1:] in _EXPECTED_FIELDS:
            clean = key[1:]
            if clean not in data or data[clean] is None:
                data[clean] = data[key]
            # Remove the dot-prefixed key to avoid confusion
            del data[key]

    # Step 2: normalize visual_elements sub-fields
    ve = data.get("visual_elements")
    if isinstance(ve, list):
        normalized_ve = []
        for item in ve:
            if isinstance(item, dict):
                # If item has "text" but no "description", copy text → description
                if "text" in item and "description" not in item:
                    item["description"] = item["text"]
            normalized_ve.append(item)
        data["visual_elements"] = normalized_ve

    return data


# ── 页分类 ──

def _is_image_or_sparse_page(pdf_text: str, cl_page_items: list) -> bool:
    """判断单页是否为 image_or_sparse。

    复刻 pdf-validate.detect_page_type 中 image_or_sparse 的判断逻辑：
    - content_list 包含 "image" 类型元素，或
    - PDF 文本 token < 15（稀疏文本页）
    """
    cl_types = {item.get("type") for item in (cl_page_items or []) if isinstance(item, dict)}
    if "image" in cl_types:
        return True
    pdf_token_count = len(pdf_text.split())
    return pdf_token_count < 15


def detect_image_or_sparse_pages(pdf_path: Path, segments_dir: Path) -> list[int]:
    """扫描所有段目录，返回所有 image_or_sparse 页的 1-based 页码列表。

    使用 pdf-merge 口径选段（排除 rerun/临时目录），读取各段 content_list_v2.json
    按 page_idx 分组，配合 fitz PDF 文本提取做页分类。
    """
    import fitz

    # 收集所有有效段
    segments = []
    for child in sorted(segments_dir.iterdir()):
        if not child.is_dir():
            continue
        parsed = parse_segment_name(child.name)
        if parsed is None:
            continue
        segments.append((parsed[0], parsed[1], child))

    if not segments:
        return []

    # 预加载 PDF 文本页（按段懒加载也可，但全扫描更简单）
    doc = fitz.open(str(pdf_path))
    image_or_sparse_pages = []

    try:
        for seg_start, seg_end, seg_dir in segments:
            # 找 content_list_v2.json
            cl_paths = sorted(seg_dir.rglob("*_content_list_v2.json"))
            if not cl_paths:
                continue
            try:
                cl_data = json.loads(cl_paths[0].read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            # content_list_v2.json 是一个列表，每元素对应一段内一页的 content 项列表
            if not isinstance(cl_data, list):
                continue

            for page_idx, cl_page in enumerate(cl_data):
                page_num = seg_start + page_idx
                # 段可能不满 8 页，超出实际 PDF 页数则跳过
                if page_num > doc.page_count:
                    break

                pdf_text = doc[page_num - 1].get_text("text")
                if _is_image_or_sparse_page(pdf_text, cl_page if isinstance(cl_page, list) else []):
                    image_or_sparse_pages.append(page_num)

    finally:
        doc.close()
    return sorted(set(image_or_sparse_pages))


# ── 图片渲染 ──

def render_page(pdf_path: Path, page_num: int, dpi: int = DEFAULT_DPI) -> bytes:
    """渲染单页为 PNG 字节。

    Args:
        pdf_path: PDF 文件路径
        page_num: 1-based 页码
        dpi: 渲染 DPI（默认 200）

    Returns:
        PNG 图片的字节数据

    Raises:
        IndexError: 页码超出范围
    """
    import fitz

    doc = fitz.open(str(pdf_path))
    try:
        if page_num < 1 or page_num > doc.page_count:
            raise IndexError(f"页码 {page_num} 超出范围 (1-{doc.page_count})")
        scale = dpi / 72.0
        matrix = fitz.Matrix(scale, scale)
        page = doc[page_num - 1]
        pix = page.get_pixmap(matrix=matrix)
        img_bytes = pix.tobytes("png")
    finally:
        doc.close()
    return img_bytes


def render_page_to_file(
    pdf_path: Path, page_num: int, output_dir: Path, dpi: int = DEFAULT_DPI
) -> Path:
    """渲染单页并保存到 output_dir/pNNNN.png。

    Returns:
        保存的文件路径
    """
    img_bytes = render_page(pdf_path, page_num, dpi)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"p{page_num:04d}.png"
    out_path.write_bytes(img_bytes)
    return out_path


# ── VLM API 调用 ──

def build_vlm_messages(
    page_image_bytes: bytes,
    system_prompt: str | None = "你是一个 PDF 页面描述助手。只输出合法 JSON，不包含任何其他文字。",
) -> list[dict]:
    """构建 OpenAI 格式的 messages 列表，含 base64 编码的页面图片。

    Args:
        page_image_bytes: PNG 图片字节
        system_prompt: 可选的 system prompt

    Returns:
        OpenAI chat.completions 格式的 messages 列表
    """
    b64 = base64.b64encode(page_image_bytes).decode("ascii")
    data_uri = f"data:image/png;base64,{b64}"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "image_url",
                "image_url": {"url": data_uri},
            },
            {
                "type": "text",
                "text": (
                    '描述此 PDF 页面的视觉内容，仅以合法 JSON 格式输出，字段名不加任何前缀：\n'
                    '{\n'
                    '  "page_summary": "string",\n'
                    '  "visual_elements": [{"type": "string", "description": "string"}],\n'
                    '  "key_text": ["string"],\n'
                    '  "confidence": 0.95\n'
                    '}\n'
                    "如果页面无有效视觉内容，page_summary 为空字符串，"
                    "visual_elements 和 key_text 为空数组，confidence 为 0。"
                ),
            },
        ],
    })
    return messages


def call_vlm_for_page(
    client: "OpenAI", model: str, image_bytes: bytes
) -> dict | None:
    """调用 VLM 获取页面结构化描述。

    Args:
        client: openai.OpenAI 客户端
        model: 模型名
        image_bytes: 页面 PNG 字节

    Returns:
        解析后的 dict（符合 VLM_SCHEMA），失败返回 None
    """
    messages = build_vlm_messages(image_bytes)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=1024,
        )
    except Exception:
        return None

    raw = resp.choices[0].message.content
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    # 字段名标准化：某些模型（MLX 8bit 量化）会在字段名前加 `.` 前缀
    data = _normalize_vlm_fields(data)
    return data


# ── 响应校验 ──

def validate_vlm_response(data: dict) -> tuple[bool, list[str]]:
    """校验 VLM 响应是否符合 VLM_SCHEMA。

    Args:
        data: VLM 返回的 dict

    Returns:
        (is_valid, errors): errors 为错误信息列表，为空则表示完全有效
    """
    errors = []
    if not isinstance(data, dict):
        return False, ["响应不是 dict"]

    for field, expected_types in VLM_SCHEMA.items():
        if field not in data:
            errors.append(f"缺少字段: {field}")
            continue
        val = data[field]
        if not isinstance(val, expected_types):
            errors.append(
                f"字段 {field} 类型错误: 期望 {expected_types}, 实际 {type(val).__name__}"
            )

    # 额外校验 confidence 范围
    conf = data.get("confidence")
    if conf is not None and not isinstance(conf, (int, float)):
        errors.append(f"confidence 类型错误: 期望数字, 实际 {type(conf).__name__}")
    elif conf is not None and not (0.0 <= conf <= 1.0):
        errors.append(f"confidence 超出 [0,1] 范围: {conf}")

    # extra 校验 visual_elements 结构
    ve = data.get("visual_elements")
    if isinstance(ve, list):
        for i, item in enumerate(ve):
            if not isinstance(item, dict):
                errors.append(f"visual_elements[{i}] 不是 object")
                continue
            if "type" not in item:
                errors.append(f"visual_elements[{i}] 缺少 type")
            if "description" not in item:
                errors.append(f"visual_elements[{i}] 缺少 description")

    return len(errors) == 0, errors


# ── 输出写入 ──

def write_vlm_jsonl(rows: list[dict], output_path: Path) -> Path:
    """写入 JSONL 行到 output_path。

    每行一个 JSON 对象，utf-8 编码，无 BOM。

    Returns:
        output_path（便于链式调用）
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return output_path


# ── 主编排 ──

def eval_vlm_package(
    package_dir: Path,
    api_base: str = DEFAULT_API_BASE,
    model: str = DEFAULT_MODEL,
    dpi: int = DEFAULT_DPI,
    keep_images: bool = False,
) -> tuple[list[dict], Path]:
    """完整编排：检测页 → 渲染 → VLM 调用 → 校验 → 写 JSONL。

    Args:
        package_dir: 输出包根目录（含 segments/ 和 * .pdf）
        api_base: VLM API 基础 URL
        model: VLM 模型名
        dpi: 渲染 DPI
        keep_images: 是否保留渲染的页面图片

    Returns:
        (rows, output_path): 所有页面的结果列表和输出文件路径

    Raises:
        FileNotFoundError: PDF 或 segments 未找到
    """
    from openai import OpenAI

    # 定位 PDF：常规布局为 <package_dir>/<package_name>.pdf
    pdf_candidates = sorted(package_dir.glob(f"{package_dir.name}.pdf"))
    if not pdf_candidates:
        # 另一种布局：<parent>/<package_name>.pdf（包目录与 PDF 同级）
        pdf_candidates = sorted(package_dir.parent.glob(f"{package_dir.name}.pdf"))
    if not pdf_candidates:
        # 尝试直接匹配 manifest 中的路径
        manifest_path = package_dir / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                sp = manifest.get("source_pdf", "")
                if sp:
                    pdf_candidates = [Path(sp)]
            except (json.JSONDecodeError, OSError):
                pass
    if not pdf_candidates:
        raise FileNotFoundError(
            f"在 {package_dir} 下找不到 {package_dir.name}.pdf，"
            f"请确保 PDF 文件位于输出包目录内"
        )
    pdf_path = pdf_candidates[0].resolve()
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")

    segments_dir = package_dir / "segments"
    if not segments_dir.is_dir():
        raise FileNotFoundError(f"找不到分段目录: {segments_dir}")

    # 检测 image_or_sparse 页
    pages = detect_image_or_sparse_pages(pdf_path, segments_dir)
    if not pages:
        # 无 image_or_sparse 页是合法状态，输出空 JSONL
        out_path = package_dir / "data" / "vlm_eval.jsonl"
        write_vlm_jsonl([], out_path)
        return [], out_path

    # 构建 section 索引（从合并 Markdown）
    section_index = []
    merged_md = _find_merged_markdown(package_dir)
    if merged_md:
        section_index = build_section_index(merged_md.read_text(encoding="utf-8", errors="replace"))

    # 初始化 VLM 客户端
    client = OpenAI(base_url=f"{api_base}/v1", api_key="not-needed")

    # 是否保留渲染图
    page_images_dir = package_dir / "data" / "page_images" if keep_images else None

    rows = []
    for i, page_num in enumerate(pages):
        # 渲染
        try:
            img_bytes = render_page(pdf_path, page_num, dpi)
        except (IndexError, RuntimeError, Exception) as e:
            rows.append(_make_failed_row(page_num, section_index, f"fitz render error: {e}"))
            continue

        # 可选保留图片
        if page_images_dir:
            render_page_to_file(pdf_path, page_num, page_images_dir, dpi)

        # VLM 调用
        vlm_data = call_vlm_for_page(client, model, img_bytes)

        # 校验 + 组装行
        if vlm_data is None:
            rows.append(
                _make_failed_row(page_num, section_index, "VLM API error or invalid JSON response")
            )
            continue

        is_valid, errors = validate_vlm_response(vlm_data)
        if not is_valid:
            rows.append(
                _make_failed_row(page_num, section_index, f"schema validation: {'; '.join(errors)}")
            )
            continue

        section = section_for_page(section_index, page_num)
        rows.append({
            "page": page_num,
            "page_summary": vlm_data.get("page_summary", ""),
            "visual_elements": vlm_data.get("visual_elements", []),
            "key_text": vlm_data.get("key_text", []),
            "confidence": vlm_data.get("confidence"),
            "section": section,
            "parse_status": "ok",
        })

    # 写入输出
    out_path = package_dir / "data" / "vlm_eval.jsonl"
    write_vlm_jsonl(rows, out_path)
    return rows, out_path


# ── 内部辅助 ──

def _find_merged_markdown(package_dir: Path) -> Path | None:
    """在输出包中查找合并 Markdown（排除 review.md）。"""
    for f in sorted(package_dir.glob("*.md")):
        if f.name != "review.md":
            return f
    return None


def _make_failed_row(page_num: int, section_index: list, error: str) -> dict:
    """构造失败行的标准 dict。"""
    section = section_for_page(section_index, page_num)
    return {
        "page": page_num,
        "page_summary": None,
        "visual_elements": [],
        "key_text": [],
        "confidence": None,
        "section": section,
        "parse_status": "failed",
        "error": error,
    }
