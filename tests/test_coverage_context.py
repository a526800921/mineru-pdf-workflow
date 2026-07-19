import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from lib.coverage_context import build_toc_section_index, section_path_for_page


TOC = [
    {"title": "LCD仪表（根据配置）", "target_page": 63, "depth": 0},
    {"title": "仪表指示灯", "target_page": 64, "depth": 1},
    {"title": "信息显示", "target_page": 67, "depth": 1},
    {"title": "TFT仪表（根据配置）", "target_page": 73, "depth": 0},
    {"title": "仪表指示灯", "target_page": 74, "depth": 1},
]


def test_section_path_uses_physical_page_and_hierarchical_toc():
    index = build_toc_section_index(TOC)

    assert section_path_for_page(index, 66) == "LCD仪表（根据配置） / 仪表指示灯"
    assert section_path_for_page(index, 67) == "LCD仪表（根据配置） / 信息显示"
    assert section_path_for_page(index, 76) == "TFT仪表（根据配置） / 仪表指示灯"
    assert section_path_for_page(index, 77) == "TFT仪表（根据配置） / 仪表指示灯"


def test_section_path_is_empty_when_page_has_no_unique_preceding_toc_entry():
    index = build_toc_section_index(TOC)

    assert section_path_for_page(index, 1) == ""
