# 计划：目录页物理归属与过度生成修复

## 计划状态

- 状态：待实施
- 当前阶段：阶段 1：物理页归属修复
- 最后更新：2026-07-11
- 依赖：`coverage-validation-optimization`、`per-page-anchors`、`pdf-auto-repair-before-merge`、PyMuPDF 原生文本层、demo20 目录页样本
- 背景缺陷：[toc-page-full-duplication.md](../issues/toc-page-full-duplication.md)

## 背景

demo20 的物理目录页为 PDF 第 2–8 页。每个单页段的 `origin.pdf` 与源 PDF 对应页一致，但 MinerU 对目录页自动补全整本目录，导致 7 个单页段生成逐字节相同的完整目录。

当前 `toc_repair` 还存在第二个归属问题：`_assign_to_toc_pages()` 使用 `title in page_text` 子串匹配。例如目录条目“制动”会命中 p2 原生文本中的“前制动手柄”，被错误分配到 p2，而实际独立条目位于 p4。

因此本计划同时处理：

1. MinerU 目录页过度生成后的物理页裁剪/重建；
2. TOC 条目按物理页归属时的子串误匹配。

本计划不修改已完成的表格字段遗漏检测计划，也不删除目录页的 `<!-- pages N-N -->` 段级锚点。

## 目标

- 目录条目只归属于 PDF 原生文本实际出现的物理目录页。
- 禁止短标题通过子串匹配命中更长正文词，例如“制动”不能命中“前制动手柄”。
- 保留每个目录页的 `<!-- pages N-N -->` 锚点，保证现有页读取、结构化抽取和 section 映射契约不变。
- 在 MinerU 输出过度生成时，生成正确的合并目录和 `toc_tree.json`；无法可靠判断时进入 `review`，不静默猜测。
- 为渲染和下游展示生成独立的无锚点目录清单 `toc.md`；主 Markdown 仍保留页级锚点，不让展示格式和页码机器契约互相牵制。
- 修复 `all_passed` 与 `needs_review` 两条路径的目录处理一致性。

## 非目标

- 不删除或弱化 `<!-- pages N-N -->` 段级锚点。
- 不把整本目录去重作为唯一修复；去重不能解决物理页归属。
- 不依赖 VLM 作为目录页码归属的主判据。
- 不修改 MinerU 本体；只在输出包解析/TOC 修复边界增加可靠裁剪和归属逻辑。
- 不改变普通正文页、表格 fallback、结构化数据字段 Schema 和 `PDF_AUTO_JSON=1` 契约。

## Step 0 证据

### 真实样本基线

- demo20 p2–p8 的 7 个单页 Markdown SHA-256 均为：`cb922a8dd1c07f20cba3de6b7f1774c4e28d2f8a0c6c2a8cee966c26d24a9d59`。
- p2 原生文本有 74 个非空行，不包含“整车关键件扭矩表”；p4 原生文本包含独立条目“制动”和“停放”；p8 包含“整车关键件扭矩表”。
- 当前合并 Markdown 的 `<!-- pages 2-2 -->` 段包含错误条目“制动 130”，说明物理归属已被污染。
- 当前 `_extract_entries_from_page()` 能从 PDF 原生页提取 `制动 → 130`，但 `_assign_to_toc_pages()` 会将其分配到 p2，因为 p2 含有更长词“前制动手柄”。

### 可复现红基线

```bash
python3 - <<'PY'
import sys
from pathlib import Path
import fitz
sys.path.insert(0, "scripts")
from lib.toc_repair import _extract_entries_from_page, _assign_to_toc_pages, _compute_depths

pdf = Path("pdf/demo20/demo20.pdf")
with fitz.open(pdf) as doc:
    entries = []
    for page_index in range(1, 8):
        entries.extend(_extract_entries_from_page(doc, page_index))
    _compute_depths(entries)
    hits = [e for e in entries if e["title"] == "制动"]
    assigned = _assign_to_toc_pages(hits, doc, list(range(2, 9)))
    actual = [p for p, rows in assigned.items() if rows]
    assert actual == [2], f"当前红基线应错误归属 p2，实际为 {actual}"
    assert "制动" in doc[1].get_text()  # 命中“前制动手柄”子串
print("red baseline: short TOC title incorrectly assigned to p2")
PY
```

## 阶段 0 完成与阶段 1 待实施门禁复核（2026-07-11）

结论：**阶段 0 已完成，阶段 1 已达到待实施标准。**

- Step 0 红基线已独立复现：当前“制动”因裸子串匹配错误归属 p2；命令输出 `red baseline: short TOC title incorrectly assigned to p2`。
- 物理页归属主数据源已确定为每个目录物理页的 PDF 原生文本行，MinerU 重复目录只作为待修复候选，不作为归属依据。
- 归属匹配规则已确定为规范化完整行/词边界匹配；字符集模糊匹配不得自动归属，只能生成 `review` 候选。
- 输出契约已确定：主 Markdown 保留段级页锚点，`toc.md` 提供无锚点展示视图，`toc_tree.json` 提供机器权威目录结构。
- 阶段 1 的修改范围、兼容消费者、失败策略、验证命令、完成条件和回滚方式均已明确；当前没有实施前置阻塞项。

进入阶段 1 实施后，修改 `toc_repair`、`pdf-auto` 或消费者相关符号前必须先执行 GitNexus upstream impact；完成后执行 `detect_changes()`、专项回归、全量测试和治理检查。

## 设计契约

### 归属优先级

1. 有可靠 PDF 原生文本层时，以每个物理目录页的原生 TOC 行作为归属证据。
2. 条目匹配必须基于规范化后的完整行/词边界，不能使用裸 `title in page_text`。
3. 目录页之间的层级可继续使用原生行的 x 坐标聚类，但页归属不得由全局字符集相似度单独决定。
4. 若条目无法唯一归属、PDF 无文本层或页面文本损坏，返回 `review` 证据，不自动分配到任意页面。

### 输出不变量

- 每个物理目录页最多生成一个对应的 `<!-- pages N-N -->` 锚点。
- 目录页锚点连续、有序，不允许因裁剪而缺页、重页或把相邻页内容吸收。
- `toc_tree.json` 条目集合与最终目录块一致；同一条目不因多个 MinerU 段重复而重复写入。
- `pdf-read-page`、`pdf-extract-data` 和 section 映射继续以段级锚点为边界。
- 目录修复失败时保留原始候选和 `review`，不删除锚点、不覆盖正文。

### 下游输出契约

目录输出分为三个用途，禁止下游混用：

| 产物 | 用途 | 是否含 `<!-- pages N-N -->` |
|---|---|---|
| `<pdf_stem>.md` | 主文档、按页读取、结构化抽取和 section 映射 | 保留 |
| `toc.md` | 人工阅读、前端渲染、下游展示的连续目录列表 | 不含 |
| `toc_tree.json` | 机器消费的权威目录结构和页码归属 | 不适用 |

`toc.md` 是从同一份已归属的 TOC 条目生成的干净视图，只移除页级锚点和段间隔离，不重新解析、不重新排序、不重新猜测页码。建议内容保持连续 Markdown 列表：

```markdown
## 目录

- 前言 8
- 操作部件 34
  - 前制动手柄 34
  - 后制动手柄 34
  - 制动 130
```

`toc_tree.json` 至少保留以下字段，区分“目录条目所在物理页”和“条目指向页”：

```json
{
  "title": "制动",
  "target_page": 130,
  "toc_page": 4,
  "depth": 1
}
```

下游规则：需要展示目录时读取 `toc.md`；需要机器检索、页码跳转或结构化关联时读取 `toc_tree.json`；需要读取原文页段时继续读取主 Markdown 并依赖 `<!-- pages N-N -->`。不允许通过删除主 Markdown 锚点来解决渲染问题。

## 实施阶段

### 阶段 1：物理页归属修复

- 先修 `_assign_to_toc_pages()` 的完整行/词边界匹配。
- 优先改为按物理目录页提取原生条目，避免将每页条目汇总后再猜测归属。
- 保留 x 坐标层级计算；移除或限制字符集模糊回退，模糊结果只能进入 `review`。
- 为“制动/前制动手柄”“停放/停放检查”等前缀冲突增加单元测试。

### 阶段 2：合并与兼容路径接入

- 验证 `repair()` 和 `repair_merged()` 两条路径都使用同一物理页归属规则。
- 保留 `<!-- pages N-N -->`，验证 `pdf-read-page` 单页/范围读取、`pdf-extract-data` 页码和 `toc_tree.json` 一致性。
- 由同一归属结果同时生成带锚点主 Markdown 和无锚点 `toc.md`，验证两者条目顺序和页码完全一致。
- 验证 `all_passed`、`needs_review` 和重复执行路径不会重新引入整本目录或缺失锚点。

### 阶段 3：真实样本与回归验收

- demo20 p2–p8：p2 不得出现 p4/p8 条目，p4 保留“制动/停放”，p8 保留“整车关键件扭矩表”。
- demo5/demo60：验证乱码目录、无文本层和不同目录布局不误分配。
- 验证结构化抽取、`pdf-read-page`、review.md 和 JSON 输出无非预期回归。
- 对实际 MinerU 过度生成输出做一次完整 `pdf-auto` 运行，记录修复前后哈希、条目归属和状态。

## 验证方式

```bash
python3 -m pytest tests/test_toc_repair.py -q
bash scripts/test-consumers.sh
python3 scripts/check_plan_governance.py .
git diff --check
```

新增验收至少包括：

- Step 0 红基线从错误 p2 归属变为正确 p4 归属；
- p2–p8 不再生成逐字节相同的整本目录；
- 目录页锚点连续保留，删除任一锚点的回归测试明确失败；
- `pdf-read-page 3` 只返回 p3 内容，`pdf-extract-data` 不把 p3 行归到 p2；
- `toc_tree.json` 与合并目录条目集合一致且无重复；
- `toc.md` 为连续列表、无页级锚点，且与 `toc_tree.json` 条目顺序和页码一致；
- 无文本层/模糊匹配场景进入 review，不随机归属；
- 全量 Python 测试、治理检查、`git diff --check` 和 GitNexus `detect_changes()` 通过。

## 风险与回滚

- 某些 PDF 原生文本可能乱码或目录行被拆成多个 span；无法可靠重组时宁可 review，不使用低置信度字符集分配自动覆盖。
- 目录页跳过 MinerU 或改用原生文本可能丢失原有层级；保留 x 坐标和原始候选用于复核。
- 目录修复范围涉及 `toc_repair`、`pdf-auto`、`pdf-read-page`、`pdf-extract-data` 多个消费者；代码修改前必须执行 GitNexus upstream impact。
- 回滚方式：恢复当前 `toc_repair` 行为，保留 `review_only` 作为人工兜底；不得回滚到删除段级锚点的方案。

## 未决问题

| 问题 | 当前建议 | 状态 |
|---|---|---|
| 目录归属主数据源 | 优先使用每个物理目录页的 PDF 原生文本行；MinerU 仅作为补充 | 已决 |
| 无文本层目录页如何处理 | 不自动猜测，进入 review；必要时另立 OCR/VLM 方案 | 已决 |
| 是否删除目录页段级锚点 | 不删除，锚点是现有消费者契约 | 已决 |
| 字符集模糊匹配是否保留 | 不作为自动归属依据；最多生成 review 候选 | 已决 |
| 是否改动 MinerU 服务参数 | 不改 MinerU 本体，先修输出边界 | 已决 |

## 完成条件

- [ ] Step 0 红基线通过：`制动 130` 不再归属 p2。
- [ ] p2–p8 目录条目按物理页正确归属，无整本目录重复。
- [ ] `<!-- pages N-N -->` 锚点完整保留，消费者回归通过。
- [ ] `repair()`、`repair_merged()`、`pdf-read-page`、`pdf-extract-data` 兼容验证通过。
- [ ] demo20、demo5/demo60 真实样本验收通过或进入有证据的 review。
- [ ] `toc_tree.json`、merged Markdown、review.md 和结构化抽取结果一致。
- [ ] 独立 `toc.md` 生成，渲染和下游展示不再依赖主 Markdown 中的目录锚点。
- [ ] 全量测试、治理检查、`git diff --check`、GitNexus `detect_changes()` 通过。
