"""
生成人工兜底清单 Markdown（review.md）。

从 pdf-validate JSON 报告提取需人工复核的分段和页面，生成结构化 review 文档。
被 scripts/pdf-review 和 scripts/pdf-auto 调用。
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


def generate_review_report(
    validate_json_path: str,
    review_output_path: str,
    threshold: float,
    pdf_path: str,
    segments_dir: str,
    rerun_failures: Optional[str] = None,
    *,
    include_page_type: bool = False,
    file: Optional[object] = None,
) -> str:
    """生成人工兜底清单 Markdown。

    Args:
        validate_json_path: pdf-validate JSON 报告路径
        review_output_path: 输出 review.md 路径
        threshold: 覆盖率阈值
        pdf_path: 原始 PDF 路径
        segments_dir: 分段目录路径
        rerun_failures: 空格分隔的重跑失败分段名，可选
        include_page_type: 逐页详情是否包含页面类型列
        file: 可选，写入目标（默认 Path.write_text）

    Returns:
        review_output_path
    """
    with open(validate_json_path) as f:
        report = json.load(f)

    rerun_failures_set: set[str] = set()
    if rerun_failures and rerun_failures.strip():
        rerun_failures_set = set(rerun_failures.strip().split())

    # 收集需人工复核的段
    issues = [
        s for s in report["segments"]
        if s.get("decision") in ("review_only", "rerun")
        or s["status"] in ("failed", "skipped")
    ]

    lines: list[str] = []
    lines.append("# 人工兜底清单")
    lines.append("")
    lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"原始 PDF: {pdf_path}")
    lines.append(f"分段目录: {segments_dir}")
    lines.append(f"阈值: {threshold}")
    lines.append("")

    # --- 段级汇总 ---
    _append_segment_summary(lines, report, rerun_failures_set)

    # --- 人工审核结论约定 ---
    _append_review_conventions(lines)

    # --- 需复核分段 ---
    _append_issue_segments(lines, issues, threshold, rerun_failures_set)

    # --- 逐页详情 ---
    _append_page_details(lines, issues, threshold, include_page_type)

    content = "\n".join(lines)
    if file is not None:
        file.write(content)
    else:
        Path(review_output_path).write_text(content, encoding="utf-8")

    print(f"人工兜底清单已生成: {review_output_path}", file=sys.stderr)
    return review_output_path


def _append_segment_summary(
    lines: list[str],
    report: dict,
    rerun_failures_set: set[str],
) -> None:
    lines.append("## 段级汇总")
    lines.append("")
    lines.append("| 分段 | 页码范围 | 段级状态 | 可重跑 | 需复核页数 | 页级分布 |")
    lines.append("|------|----------|----------|--------|------------|----------|")

    for seg in report["segments"]:
        seg_name = seg["name"]
        pages = f"{seg['start_page']}-{seg['end_page']}"
        decision = seg.get("decision", "")
        status = seg.get("status", "")

        if decision == "review_only":
            seg_status = "`review_only`"
        elif decision == "rerun":
            seg_status = "`rerun`"
        elif decision == "pass" or status == "passed":
            seg_status = "`passed`"
        elif status == "failed":
            seg_status = "`failed`"
        elif status == "skipped":
            seg_status = "`skipped`"
        else:
            seg_status = f"`{decision or status}`"

        rerunnable = "是" if seg.get("rerunnable", False) else "否"

        pages_data = seg.get("pages", [])
        review_count = 0
        dist: dict[str, int] = {}
        if pages_data:
            for p in pages_data:
                pd = p.get("decision", "")
                ps = p.get("status", "")
                key = pd if pd in ("review_only", "rerun", "pass") else (ps or "?")
                dist[key] = dist.get(key, 0) + 1
                if pd in ("review_only", "rerun") or ps in ("failed", "skipped", "suspicious"):
                    review_count += 1
        else:
            if decision in ("review_only", "rerun") or status in ("failed", "skipped"):
                review_count = 1
            key = decision or status or "?"
            dist[key] = 1

        dist_str = ", ".join(f"{k}:{v}" for k, v in sorted(dist.items()))
        lines.append(f"| {seg_name} | {pages} | {seg_status} | {rerunnable} | {review_count} | {dist_str} |")

    lines.append("")


def _append_review_conventions(lines: list[str]) -> None:
    lines.append("## 人工审核结论约定")
    lines.append("")
    lines.append("| 结论 | 含义 |")
    lines.append("|------|------|")
    lines.append("| `pass` | 人工确认该段无需修改 |")
    lines.append("| `fix_md` | 人工直接修正合并 Markdown |")
    lines.append("| `rerun` | 人工决定后续重新解析该段 |")
    lines.append("")


def _append_issue_segments(
    lines: list[str],
    issues: list[dict],
    threshold: float,
    rerun_failures_set: set[str],
) -> None:
    lines.append("## 需复核分段")
    lines.append("")
    lines.append("| 分段 | 页码范围 | 覆盖率 | 处理建议 | 原因 |")
    lines.append("|------|----------|--------|----------|------|")

    for seg in issues:
        pages = f"{seg['start_page']}-{seg['end_page']}"
        cov = f"{seg['coverage']:.2f}" if seg.get("coverage") is not None else "-"

        decision = seg.get("decision", seg.get("status", ""))
        reason = seg.get("reason", "")
        status = seg.get("status", "")

        if seg["name"] in rerun_failures_set:
            action = "重跑失败，使用原始结果"
            note = "mineru 退出非0"
        elif decision == "review_only":
            page_type_summary = seg.get("page_type_summary", {})
            type_desc = ", ".join(
                f"{t}({c})" for t, c in page_type_summary.items() if c > 0
            )
            action = "人工复核（不重跑）"
            note = f"页面类型: {type_desc}" if type_desc else reason
        elif decision == "rerun":
            action = "需重跑"
            note = f"high 重跑后仍未通过阈值 {threshold}"
        elif status == "failed" and reason == "missing_markdown":
            action = "需检查"
            note = "mineru 运行成功但未生成 Markdown 文件"
        elif status == "skipped" and reason == "no_text_layer":
            action = "已跳过"
            note = "原 PDF 文本层为空，无法验证"
        else:
            action = "需复核"
            note = f"{decision}: {reason}" if reason else decision

        lines.append(f"| {seg['name']} | {pages} | {cov} | {action} | {note} |")

    lines.append("")


def _append_page_details(
    lines: list[str],
    issues: list[dict],
    threshold: float,
    include_page_type: bool,
) -> None:
    for seg in issues:
        pages_data = seg.get("pages", [])
        if not pages_data:
            continue

        # Skip segments with no low-coverage pages (unless include_page_type is True)
        if not include_page_type:
            low_pages = [
                p for p in pages_data
                if p.get("coverage") is not None and p["coverage"] < threshold
            ]
            if not low_pages:
                continue

        seg_pages = f"{seg['start_page']}-{seg['end_page']}"
        lines.append(f"## {seg['name']} 逐页详情（PDF 第 {seg_pages} 页）")
        lines.append("")

        if include_page_type:
            lines.append("| PDF 页码 | 覆盖率 | 页面类型 | 处理决策 | PDF token | MD token | 缺失较多的词 |")
            lines.append("|----------|--------|----------|----------|-----------|----------|-------------|")
        else:
            lines.append("| PDF 页码 | 覆盖率 | PDF token | MD token | 缺失较多的词 |")
            lines.append("|----------|--------|-----------|----------|-------------|")

        for p in pages_data:
            cov = p.get("coverage")
            if cov is None:
                continue

            pdf_page_num = p["page"] + 1
            cov_str = f"{cov:.2f}"
            flag = " ⚠️" if cov < threshold else ""
            missing = ", ".join(
                f"{t}({c})" for t, c in p.get("missing_tokens", [])[:5]
            )
            if not missing:
                missing = "—"

            if include_page_type:
                page_type = p.get("page_type", "?")
                page_decision = p.get("decision", "?")
                lines.append(
                    f"| {pdf_page_num}{flag} | {cov_str} | {page_type} | {page_decision} | "
                    f"{p['pdf_tokens']} | {p['md_tokens']} | {missing} |"
                )
            else:
                lines.append(
                    f"| {pdf_page_num}{flag} | {cov_str} | {p['pdf_tokens']} | "
                    f"{p['md_tokens']} | {missing} |"
                )

        lines.append("")


# ---- CLI entry point (used by scripts/pdf-review) ----

if __name__ == "__main__":
    if len(sys.argv) < 6:
        print(
            "Usage: python3 review_report.py <validate_json> <review_output> "
            "<threshold> <pdf_path> <segments_dir> [rerun_failures] [include_page_type]",
            file=sys.stderr,
        )
        sys.exit(2)

    validate_json_path = sys.argv[1]
    review_output_path = sys.argv[2]
    threshold = float(sys.argv[3])
    pdf_path = sys.argv[4]
    segments_dir = sys.argv[5]
    rerun_failures_str = sys.argv[6] if len(sys.argv) > 6 else ""
    include_page_type = sys.argv[7].lower() == "true" if len(sys.argv) > 7 else False

    generate_review_report(
        validate_json_path=validate_json_path,
        review_output_path=review_output_path,
        threshold=threshold,
        pdf_path=pdf_path,
        segments_dir=segments_dir,
        rerun_failures=rerun_failures_str if rerun_failures_str else None,
        include_page_type=include_page_type,
    )
