#!/usr/bin/env python3
import re
import sys
from pathlib import Path

VALID_STATUSES = {
    "候选",
    "设计中",
    "待实施",
    "实施中",
    "已完成",
    "已替代",
    "已合并",
    "已废弃",
}

COMPLETED = {"已完成"}
IMPLEMENTING = {"实施中"}
INACTIVE = {"已替代", "已合并", "已废弃"}


def fail(errors, message):
    errors.append(message)


def read_utf8(path, errors):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        fail(errors, f"{path}: not valid UTF-8")
    except FileNotFoundError:
        fail(errors, f"{path}: file not found")
    return ""


def table_rows(text, heading):
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return []
    tail = text[match.end():]
    next_heading = re.search(r"^##\s+", tail, re.MULTILINE)
    section = tail[: next_heading.start()] if next_heading else tail
    rows = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or "---" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells and cells[0] not in {"计划", "问题"}:
            rows.append(cells)
    return rows


def extract_plan_link(cell):
    match = re.search(r"\((plans/[^)]+\.md)\)", cell)
    if match:
        return match.group(1)
    if cell.endswith(".md") and cell.startswith("plans/"):
        return cell
    return None


def has_completion_evidence(plan_text):
    evidence_match = re.search(r"^#+\s+(Step 0 Evidence|Step 0 证据|完成证据|验证证据)\b", plan_text, re.MULTILINE)
    validation_match = re.search(r"^#+\s+(验证方式|验证)\b", plan_text, re.MULTILINE)
    return bool(evidence_match and validation_match)


def has_current_blocker(plan_text):
    for row in table_rows(plan_text, "未决问题"):
        joined = "|".join(row)
        if re.search(r"\b(Yes|是)\b", joined) and re.search(r"(Open|待确认|未解决)", joined):
            return True
    return False


def detect_dependency_cycles(edges):
    visited = set()
    stack = set()
    cycles = []

    def visit(node, path):
        if node in stack:
            cycles.append(" -> ".join(path + [node]))
            return
        if node in visited:
            return
        visited.add(node)
        stack.add(node)
        for dep in edges.get(node, []):
            visit(dep, path + [node])
        stack.remove(node)

    for node in edges:
        visit(node, [])
    return cycles


def main():
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    docs = root / "docs"
    plan_map = docs / "PLAN_MAP.md"
    errors = []

    if not plan_map.exists():
        print("未找到 docs/PLAN_MAP.md；当前仓库尚未初始化计划治理。")
        return 0

    text = read_utf8(plan_map, errors)
    plan_rows = table_rows(text, "计划索引")
    if not plan_rows:
        fail(errors, "docs/PLAN_MAP.md: 缺少计划索引表")

    plans = {}
    for row in plan_rows:
        if len(row) < 2:
            continue
        link = extract_plan_link(row[0])
        name = Path(link).stem if link else row[0].strip("` ")
        status = row[1].strip("` ")
        if status not in VALID_STATUSES:
            fail(errors, f"docs/PLAN_MAP.md: {name} 的状态不合法：{status}")
        if link:
            path = docs / link
            if not path.exists():
                fail(errors, f"docs/PLAN_MAP.md: 引用的计划文件不存在：{link}")
            plans[name] = {"path": path, "status": status, "depends": row[3] if len(row) > 3 else ""}
        else:
            fail(errors, f"docs/PLAN_MAP.md: 计划行缺少 docs/plans 链接：{row[0]}")

    edges = {}
    inactive = {name for name, data in plans.items() if data["status"] in INACTIVE}
    for name, data in plans.items():
        deps = [d.strip("` ") for d in re.split(r",|<br>|、", data["depends"]) if d.strip("` -")]
        edges[name] = [dep for dep in deps if dep in plans]
        if data["status"] in IMPLEMENTING:
            for dep in edges[name]:
                if dep in inactive:
                    fail(errors, f"{name}: 实施中计划依赖了非活跃计划 {dep}")

    for cycle in detect_dependency_cycles(edges):
        fail(errors, f"计划依赖存在环：{cycle}")

    for name, data in plans.items():
        plan_text = read_utf8(data["path"], errors)
        if data["status"] in COMPLETED and not has_completion_evidence(plan_text):
            fail(errors, f"{data['path']}: 已完成计划缺少 Step 0 证据或验证方式章节")
        if data["status"] in IMPLEMENTING and has_current_blocker(plan_text):
            fail(errors, f"{data['path']}: 实施中计划仍有未解决的当前阶段阻塞项")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("计划治理检查通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
