"""Resolve structured-candidate section paths from the physical-page TOC."""

from __future__ import annotations


def build_toc_section_index(entries: list[dict]) -> list[tuple[int, tuple[str, ...]]]:
    """Build snapshots of the hierarchical TOC effective from each target page."""
    normalized = []
    for order, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        title = str(entry.get("title", "")).strip()
        try:
            page = int(entry.get("target_page"))
            depth = int(entry.get("depth", 0))
        except (TypeError, ValueError):
            continue
        if not title or page < 1 or depth < 0:
            continue
        normalized.append((page, order, depth, title))

    stack: list[tuple[int, str]] = []
    snapshots: list[tuple[int, tuple[str, ...]]] = []
    for page, _order, depth, title in sorted(normalized, key=lambda item: (item[0], item[1])):
        while stack and stack[-1][0] >= depth:
            stack.pop()
        stack.append((depth, title))
        snapshots.append((page, tuple(title for _level, title in stack)))
    return snapshots


def section_path_for_page(index: list[tuple[int, tuple[str, ...]]], page: int) -> str:
    """Return the last effective hierarchical TOC path at a physical page."""
    try:
        physical_page = int(page)
    except (TypeError, ValueError):
        return ""
    selected = ""
    for target_page, path in index:
        if target_page > physical_page:
            break
        selected = " / ".join(path)
    return selected
