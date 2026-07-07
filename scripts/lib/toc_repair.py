"""TOC 修复：优先用 PDF 内置大纲，fallback 到文本层 x 坐标。

用法：
  import toc_repair
  toc_repair.repair(pdf_path, segments_dir, validate_tmp)

产出：
  - 更新 TOC 段的 Markdown，带缩进层级
  - 输出包根目录写入 toc_tree.json（[{title, page, depth}, ...]）
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    import fitz
except Exception:
    print("TOC 修复跳过：PyMuPDF 不可用", file=sys.stderr)
    sys.exit(0)

TITLE_DOTS = re.compile(r'^(\S.+?)\s*[.]{3,}\s*$')
DOTS_NUM = re.compile(r'^\s*[.]{3,}\s*(\d+)\s*$')
X_LEVEL_TOLERANCE = 8.0


# ── 方案 A：PDF 内置大纲 ──────────────────────────────────────────

def _build_from_outline(doc) -> list[dict] | None:
    """从 PDF 内置大纲提取 TOC，失败返回 None。"""
    toc = doc.get_toc()
    if not toc:
        return None

    entries = []
    for level, title, page in toc:
        title = title.strip()
        if len(title) < 2:
            continue
        entries.append({
            "title": title,
            "page": page,
            "depth": level - 1,  # get_toc level 是 1-based
        })
    return entries if entries else None


# ── 方案 B：文本层 x 坐标（fallback）──────────────────────────────

def _extract_entries_from_page(doc, page_index: int) -> list[dict]:
    """从单页提取 TOC 条目，返回 [{title, page, x0}, ...]."""
    blocks = doc[page_index].get_text("dict")["blocks"]

    text_lines = []
    for b in blocks:
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            text = "".join(s.get("text", "") for s in line.get("spans", []))
            y = line["bbox"][1]
            x0 = line["bbox"][0]
            text_lines.append((y, x0, text))

    text_lines.sort(key=lambda t: t[0])
    texts = [t[2] for t in text_lines]
    x0s = [t[1] for t in text_lines]

    entries = []
    prev_key = None
    for i in range(len(texts) - 1):
        title_m = TITLE_DOTS.match(texts[i])
        num_m = DOTS_NUM.match(texts[i + 1])
        if title_m and num_m:
            title = title_m.group(1).strip()
            page_ref = num_m.group(1)
            if len(title) >= 2 and not title.isdigit():
                key = (title, page_ref)
                if key == prev_key:
                    continue
                entries.append({
                    "title": title,
                    "page": int(page_ref),
                    "x0": x0s[i],
                })
                prev_key = key

    return entries


def _compute_depths(entries: list[dict]) -> None:
    """原地为 entries 添加 depth 字段，基于 x 坐标聚类。"""
    if not entries:
        return

    x0_values = sorted(set(e["x0"] for e in entries))
    clusters = []
    current_cluster = [x0_values[0]]
    for x in x0_values[1:]:
        if x - current_cluster[-1] <= X_LEVEL_TOLERANCE:
            current_cluster.append(x)
        else:
            clusters.append(sum(current_cluster) / len(current_cluster))
            current_cluster = [x]
    clusters.append(sum(current_cluster) / len(current_cluster))

    for e in entries:
        best_idx = 0
        best_dist = abs(e["x0"] - clusters[0])
        for idx, cx in enumerate(clusters):
            dist = abs(e["x0"] - cx)
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        e["depth"] = best_idx


# ── 公共 ───────────────────────────────────────────────────────────

def _build_markdown(entries: list[dict]) -> str:
    """生成带缩进的 Markdown TOC。"""
    lines = ["## 目录\n"]
    for e in entries:
        indent = "  " * e["depth"]
        lines.append(f"{indent}- {e['title']} {e['page']}")
    return "\n".join(lines) + "\n"


def _depth_distribution(entries: list[dict]) -> str:
    c = Counter(e["depth"] for e in entries)
    return ", ".join(f"{d}级:{c[d]}" for d in sorted(c))


def _write_toc_tree(pkg_root: Path, entries: list[dict]):
    tree_data = [
        {"title": e["title"], "page": e["page"], "depth": e["depth"]}
        for e in entries
    ]
    tree_path = pkg_root / "toc_tree.json"
    tree_path.write_text(
        json.dumps(tree_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ── 主入口 ─────────────────────────────────────────────────────────

def repair(pdf_path: Path, segments_dir: Path, validate_tmp: str) -> int:
    """修复所有 TOC 段，返回修复段数。"""
    with open(validate_tmp) as f:
        report = json.load(f)

    toc_segs = [
        s for s in report["segments"]
        if s.get("page_type_summary", {}).get("toc", 0) > 0
    ]
    if not toc_segs:
        return 0

    doc = fitz.open(str(pdf_path))
    fixed = 0

    # 方案 A：内置大纲
    entries = _build_from_outline(doc)
    source = "PDF 内置大纲"

    # 方案 B：文本层 fallback
    if not entries:
        entries = []
        for seg in toc_segs:
            for p in range(seg["start_page"] - 1, min(seg["end_page"], doc.page_count)):
                entries.extend(_extract_entries_from_page(doc, p))
        if entries:
            _compute_depths(entries)
            source = "文本层 x 坐标"
        else:
            doc.close()
            return 0

    if not entries:
        doc.close()
        return 0

    # 写回 TOC 段的 Markdown
    for seg in toc_segs:
        seg_dir = segments_dir / seg["name"]
        md_files = sorted(seg_dir.rglob("*.md"))
        if not md_files:
            continue
        md_path = md_files[0]
        md_path.write_text(_build_markdown(entries), encoding="utf-8")
        fixed += 1

    # 写入 toc_tree.json
    _write_toc_tree(segments_dir.parent, entries)

    print(f"  {fixed} 个 TOC 段: {len(entries)} 条目（{_depth_distribution(entries)}），来源: {source}", file=sys.stderr)
    doc.close()
    return fixed


def verify_entry_recall(pdf_path: Path, segments_dir: Path, validate_tmp: str) -> int:
    """TOC 再验证：条目召回率。"""
    with open(validate_tmp) as f:
        vreport = json.load(f)

    toc_segs = [
        s for s in vreport["segments"]
        if s.get("page_type_summary", {}).get("toc", 0) > 0
    ]
    if not toc_segs:
        return 0

    doc = fitz.open(str(pdf_path))

    # 优先用大纲
    entries = _build_from_outline(doc)
    if not entries:
        entries = []
        for seg in toc_segs:
            for p in range(seg["start_page"] - 1, min(seg["end_page"], doc.page_count)):
                entries.extend(_extract_entries_from_page(doc, p))

    if not entries:
        doc.close()
        return 0

    titles = {e["title"] for e in entries}
    updated = 0

    for seg in toc_segs:
        seg_dir = segments_dir / seg["name"]
        md_files = sorted(seg_dir.rglob("*.md"))
        if not md_files:
            continue
        md_text = md_files[0].read_text(encoding="utf-8", errors="replace")

        found = sum(1 for t in titles if t in md_text)
        recall = found / len(titles)
        new_coverage = round(recall, 4)
        new_status = "passed" if recall >= 0.9 else "suspicious"
        new_decision = "pass" if recall >= 0.9 else "review_only"

        print(f"  {seg['name']}: 条目召回 {found}/{len(titles)} ({recall:.0%}) → {new_status}", file=sys.stderr)

        seg["coverage"] = new_coverage
        seg["status"] = new_status
        seg["decision"] = new_decision
        seg["reason"] = "toc_entry_recall"
        seg["rerunnable"] = False
        for p in seg.get("pages", []):
            p["coverage"] = new_coverage
            p["status"] = new_status
            p["decision"] = new_decision
            p["reason"] = "toc_entry_recall"
        updated += 1

    doc.close()

    if updated:
        with open(validate_tmp, "w") as f:
            json.dump(vreport, f, ensure_ascii=False)
        all_ok = all(s["status"] == "passed" for s in vreport["segments"])
        print(f"TOC 再验证完成: {updated} 段，{'全部通过' if all_ok else '仍有未通过'}", file=sys.stderr)

    return updated
