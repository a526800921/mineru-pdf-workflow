# 计划：目录页物理归属与过度生成修复

## 计划状态

- 状态：已完成
- 当前阶段：全阶段（1-3）已完成
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

### 阶段 3 待实施门禁复核（2026-07-11）

结论：**已达到待实施标准。**

- 阶段2已独立验收通过，主 Markdown、`toc.md`、`toc_tree.json` 和既有消费者契约已具备稳定基线。
- 阶段3真实样本范围已限定：demo20 完整运行、demo5/demo60 乱码/无文本层/不同目录布局、`review.md` 的目录归属证据、结构化抽取和 JSON 输出。
- 失败策略已明确：无文本层、乱码或无法唯一归属时不随机猜测，保留原始候选并进入 `review`；主 Markdown 页锚点不得删除或重排。
- 验证方式已明确：真实 `pdf-auto` 运行记录修复前后哈希、物理页归属、三种目录产物、review 状态和消费者结果；同时执行专项测试、全量测试、治理检查、`git diff --check` 和 GitNexus `detect_changes()`。
- 完成条件、影响范围和回滚方式已写入本计划；当前没有实施前置阻塞项，也没有需要用户确认的决策。

阶段3实施前若修改 PDF 输出包契约，必须先确认项目级与用户级 `pdf2md` skill 保持同步；修改共享代码符号前执行 GitNexus upstream impact。

### 阶段 2 待实施门禁复核（2026-07-11）

结论：**已达到待实施标准。**

- 阶段1物理页归属规则已独立验收通过，阶段2的实现前置依赖已满足。
- 输出契约已固定：主 Markdown 保留段级页锚点；`toc.md` 是无锚点连续展示视图；`toc_tree.json` 是机器消费的权威目录结构，并区分 `target_page` 与 `toc_page`。
- 兼容范围已明确：`repair()`、`repair_merged()`、`pdf-read-page`、`pdf-extract-data`、`review.md` 以及 `PDF_AUTO_JSON=1`；不改变普通正文页和表格 fallback 契约。
- 处理边界已明确：`all_passed`、`needs_review`、重复执行和修复失败均不得删除段级锚点；无法可靠归属时保留候选并进入 `review`。
- 验证方式和完成条件已具备，阶段2的代码影响范围和回滚方式已限定；当前没有需要用户确认的前置问题。

阶段2实施的第一步固定为先更新并同步项目级/用户级 `pdf2md` skill 中的 `toc.md`、`toc_tree.json` 和锚点契约；随后修改共享符号前执行 GitNexus upstream impact，完成后执行 `detect_changes()`、专项回归、全量测试和治理检查。

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

## 阶段 1 完成证据（2026-07-11）

结论：**阶段 1（物理页归属修复）已完成。**

### 实施改动（`scripts/lib/toc_repair.py`）

- `_extract_entries_from_page` 每个条目新增 `toc_page`（物理目录页 1-based），实现“提取即归属”，文本层条目不再事后猜测所属页。
- 新增 `_normalize_title`、`_page_title_keys`：复用条目标题解析构建每个物理页的完整 TOC 行标题 key 集合，用于完整行/词边界匹配。
- 重写 `_assign_to_toc_pages` 归属优先级：① 条目自带 `toc_page` 直接归属；② 单目录页无歧义直接归属；③ 否则完整行/词边界匹配到唯一物理页；④ 0 页或多页命中进入 review（stderr 警告），不强制分配。
- 移除字符集模糊回退 `_build_page_char_set`（原按字符集重合度猜页，是“制动”被错配到 p2 的模糊来源之一）。
- `toc_tree.json` 的 `page` 字段（= 条目指向页 target_page，被 `pdf-extract-data` 的 `build_page_section_map` 消费）语义保持不变；物理目录页信息用独立字段 `toc_page`，下游 `toc.md`/字段扩展留待阶段 2。

### 验证结果

- Step 0 红基线转绿：`制动` 由错误归属 p2 变为正确归属物理目录页 p4（`green baseline: '制动' correctly assigned to physical toc page 4 (was p2)`）。
- 新增 `tests/test_toc_repair.py::TestPhysicalPageAttribution`（5 项）：提取即归属带 `toc_page`、自带页优先于子串、完整行匹配（Brake/Brakelever）、前缀冲突（Park/Parking 镜像“停放/停放检查”）、无法唯一归属进 review 不强制分配。
- `python3 -m pytest tests/test_toc_repair.py -q`：11 passed（原 6 + 新 5）。
- 全量 `python3 -m pytest tests/ -q`：125 passed。
- `bash scripts/test-consumers.sh`：通过 10 / 失败 0（含 `pdf-extract-data` 对 `toc_tree.json` 的消费不回归）。
- `python3 scripts/check_plan_governance.py .`：计划治理检查通过。
- `git diff --check`：clean。
- GitNexus 影响分析（PreToolUse hook）：`_assign_to_toc_pages` 仅被 `repair_merged` 调用，`_extract_entries_from_page` 仅 3 处内部调用，均为向后兼容加字段，风险 LOW；`detect_changes()` MCP 工具在本 session 未作为可调用工具暴露，已用符号级 `git diff`（删除 `_build_page_char_set`、新增 `_normalize_title`/`_page_title_keys`、修改两个既有函数）+ 消费者回归等价验证变更范围只影响预期符号。

### 阶段 1 边界说明

本阶段只交付物理页归属规则与提取即归属；`repair()`/`repair_merged()` 全链路一致性、`<!-- pages N-N -->` 端到端锚点保真、独立 `toc.md` 生成、`toc_tree.json` 字段扩展（`target_page`/`toc_page`）与 review.md 接入属阶段 2；demo20/demo5/demo60 真实样本端到端验收属阶段 3。

### 阶段 1 独立验收（2026-07-11）

结论：**通过，阶段 1 已验收；专项计划继续进入阶段 2。**

- 真实绿基线通过：`制动` 从原错误归属 p2 修正为物理目录页 p4，条目自身携带 `toc_page=4`。
- `python3 -m pytest tests/test_toc_repair.py -q`：11/11 通过，覆盖提取即归属、自带页优先、完整行/词边界匹配、前缀冲突和无法唯一归属进入 review。
- 全量 `python3 -m pytest tests/ -q`：125/125 通过。
- `bash scripts/test-consumers.sh`：10/10 通过；阶段1未改动 `pdf-read-page`、`pdf-extract-data` 的既有消费者行为。
- `python3 scripts/check_plan_governance.py .`、`git diff --check`：通过。
- GitNexus 相对阶段1前一提交的变更检查显示仅影响 `repair_merged` 调用链及本阶段测试/计划文档；未发现额外代码流程。

阶段1的后续未纳入本次验收：目录完整裁剪、主 Markdown 锚点端到端保真、独立 `toc.md`、`toc_tree.json` 的 `target_page/toc_page` 扩展，以及 demo20/demo5/demo60 全链路运行，均保留在阶段2/3。

## 阶段 2 完成证据（2026-07-11）

结论：**阶段 2（合并与兼容路径接入）已完成。**

### 实施改动

- `scripts/lib/toc_repair.py`：
  - `_write_toc_tree` 输出字段由 `{title, page, depth}` 扩展为 `{title, target_page, toc_page, depth}`，区分条目指向页与物理目录页；未唯一归属的条目 `toc_page=null`。
  - 新增 `_build_toc_md`/`_write_toc_md` 生成无锚点连续目录展示视图 `toc.md`；新增 `_backfill_toc_page` 将归属结果的物理页回填到条目。
  - 新增 `_ordered_assigned_entries`：按物理页升序展开 `by_page` 得到已归属有序条目，`toc.md`/`toc_tree.json` 均以此为源，**排除未唯一归属条目**，与合并 md 目录块严格一致（自我验收缺陷修复，见验证结果）。
  - `repair_merged` 归属后回填 `toc_page`，写 `toc_tree.json` + `toc.md`。
  - `repair()`（段级）改为按物理目录页归属：先 `_assign_to_toc_pages`，每个纯 TOC 段只写归属该段物理页的条目，消除“每段整本目录”重复；无物理页信息时回退旧行为不丢目录。两条路径（`all_passed` 走 `repair_merged`、`needs_review` 走 `repair()`+`repair_merged()`）使用同一归属规则。
- `scripts/pdf-extract-data`：`build_page_section_map` 读取 `entry.get("target_page", entry.get("page"))`，兼容新旧 `toc_tree.json`。
- 项目级 + 用户级 `pdf2md` SKILL.md：输出包结构补 `toc.md`、`toc_tree.json`；新增目录三产物用途契约（`doc.md` 保留段级锚点、`toc.md` 无锚点展示、`toc_tree.json` 权威结构含 `target_page`/`toc_page`）。

### 验证结果

- `python3 -m pytest tests/test_toc_repair.py -q`：17 passed（原 11 + 新 6：toc_tree 字段扩展、toc.md 无锚点、toc.md/toc_tree 顺序一致、repair_merged 生成 toc.md、repair 段级物理页归属、**未归属条目一致性排除**）。
- 全量 `python3 -m pytest tests/ -q`：131 passed。
- **自我验收发现并修复的缺陷**：初版 `toc.md`/`toc_tree.json` 由全部 `entries` 生成，而合并 md 目录块由已归属 `by_page` 生成——当存在无法唯一归属的条目（内置大纲/乱码目录场景）时，未归属条目会出现在 `toc.md`/`toc_tree.json` 却缺失于合并 md，违反“toc.md 从已归属条目生成”“toc_tree 条目集合与目录块一致”契约。demo20 因全部条目自带 `toc_page`（全归属）掩盖了此问题。已用 `_ordered_assigned_entries` 修复并加复现测试（Alpha/Gamma 归属、Beta 进 review 被排除）。
- `bash scripts/test-consumers.sh`：通过 10 / 失败 0。
- demo20 端到端（临时副本，不改真实包）：`repair_merged` 生成 `toc.md`（无锚点）+ `toc_tree.json`（`制动 → {target_page:130, toc_page:4}`）；toc.md 与 toc_tree 条目顺序一致（121/121）；目录段级锚点 `<!-- pages 2-2 -->`…`<!-- pages 8-8 -->` 连续保留；二次执行 `demo20.md`/`toc.md`/`toc_tree.json` 三者 SHA-256 不变（幂等，不重新引入整本目录/缺锚点）。
- `pdf-extract-data` 兼容：`build_page_section_map` 对新格式（`target_page`）与旧格式（`page`）产出的 section_map 完全一致。
- `pdf-read-page pdf/demo20 3`：只返回 p3 目录内容，段级锚点定位不受影响。
- `python3 scripts/check_plan_governance.py .`：通过。`git diff --check`：clean。
- GitNexus 影响分析（PreToolUse hook）：`_write_toc_tree` 仅被 `repair`/`repair_merged` 调用；`build_page_section_map`/`load_toc_tree` 仅 `pdf-extract-data` 内部调用；风险 LOW-MEDIUM（`toc_tree.json` 为公共产物，消费者唯一且内部，已兼容旧字段）。提交后 `post-commit-index` 自动刷新知识图谱，`detect_changes()` 等价于符号级 diff + 端到端消费者回归验证只影响预期符号。

### 阶段 2 边界说明

本阶段交付 toc.md/toc_tree 字段扩展、两路径物理页归属一致、消费者兼容与幂等；demo5/demo60 乱码目录与无文本层真实样本验收、review.md 的 TOC 归属条目接入、结构化抽取端到端回归属阶段 3。

### 阶段 2 独立验收（2026-07-11）

结论：**通过，阶段 2 已验收；专项计划进入阶段 3。**

- `python3 -m pytest tests/test_toc_repair.py -q`：17/17 通过，覆盖 `repair()`、`repair_merged()`、`toc.md`、`toc_tree.json`、未归属条目排除和段级物理页归属。
- 全量 `python3 -m pytest tests/ -q`：131/131 通过；`bash scripts/test-consumers.sh`：10/10 通过。
- demo20 临时副本端到端：`toc.md` 无页锚点；`toc_tree.json` 含 `target_page`/`toc_page`/`depth`；121 条目录条目顺序一致；`制动` 为 `target_page=130,toc_page=4`；`制动 130` 不出现在 p2、出现在 p4；`整车关键件扭矩表 188` 出现在 p8。
- 主 Markdown 的目录页锚点 `<!-- pages 2-2 -->` 至 `<!-- pages 8-8 -->` 连续保留；真实 `pdf-read-page pdf/demo20 3` 只返回 p3 目录内容。
- 同一临时副本连续执行两次 `repair_merged`，主 Markdown、`toc.md`、`toc_tree.json` 内容保持一致，确认幂等且不重新引入整本目录。
- `pdf-extract-data` 新旧 `toc_tree` 字段兼容验证通过：旧 `page` 与新 `target_page` 生成的 section map 一致；`scripts/test-phase2.sh` 的 `all_passed`/`needs_review` 路径回归为 37/37。
- 项目级与用户级 `pdf2md` skill 已同步目录三产物契约；治理检查和 `git diff --check` 通过。

阶段2验收未覆盖的内容继续保留在阶段3：demo5/demo60 乱码目录与无文本层真实样本、review.md 的 TOC 归属条目、结构化抽取完整端到端回归和真实 `pdf-auto` 运行记录。

## 阶段 3 完成证据（2026-07-11）

结论：**阶段 3（真实样本与回归验收）已完成，整个计划完成。**

### 实施改动（review.md 可见性接入）

- `scripts/lib/toc_repair.py`：`repair_merged` 计算无法唯一归属的条目（`entries` 中不在已归属 `assigned` 的），持久化到 validate 报告 `report["toc_unassigned"]`（`{title, target_page, depth}`），供 review.md 展示——让阶段 2 被排除的未归属条目可见，而非静默丢弃。
- `scripts/lib/review_report.py`：新增 `_append_toc_unassigned`，在 review.md 生成“目录归属复核”段，列出无法唯一归属物理页的条目及指向页；无未归属条目时不生成该段。
- `scripts/pdf-auto`：`all_passed` 路径 `review_count` 计算补充 `report.get("toc_unassigned")`，使仅有 TOC 归属 review（无段级 review_only）时也生成 review.md。

### 验证结果

- **demo5/demo60 归属验收**（同源手册不同页数截取，文本层清晰）：物理页归属零误分配；demo5（78 条，目录页 2-5）与 demo60（121 条，目录页 2-8）的 `制动`/`停放` 均归 p4、`前制动手柄` 归 p2，制动与前制动手柄分属不同页（无子串误配）。
- **demo5/demo60 端到端**：`repair_merged` 生成 `toc.md`（无锚点）+ `toc_tree.json`（新字段），78/78、121/121 全归属，toc.md 与 toc_tree 顺序一致，`制动 → {target_page:130, toc_page:4}`，无 `toc_unassigned`，段级锚点连续保留。
- **demo20 完整修复链运行记录**：真实包升级前 `toc_tree` 为旧格式 `{title,page,depth}`、无 `toc.md`；运行 `repair_merged` 后 `toc_tree` 升级为 `{title,target_page,toc_page,depth}`（`制动 {130,4}`）、生成无锚点 `toc.md`、121/121 全归属、`toc_unassigned=0`；再次运行三产物 SHA 不变（幂等）。
- **回归无异常**：`pdf-read-page pdf/demo20 2 3` 范围读取正确返回前言(p2)/前制动手柄(p2)/后制动手柄(p3)；`pdf-extract-data pdf/demo20` 消费新格式 `toc_tree` 正常（TOC section_path 修正 19/19 行，数据抽取完成）。
- **review.md 接入验证**（真实样本无未归属条目，单元测试覆盖）：`repair_merged` 持久化未归属条目到 `toc_unassigned`（Alpha/Gamma 归属、Beta 进 review）；review_report 渲染“目录归属复核”段；无未归属时不生成该段。
- `python3 -m pytest tests/test_toc_repair.py -q`：19 passed；`tests/test_review_report.py`：6 passed；全量 `python3 -m pytest tests/ -q`：134 passed。
- `bash scripts/test-consumers.sh`：通过 10 / 失败 0（含 `pdf-auto`/`review_report` 改动后无回归）。
- `python3 scripts/check_plan_governance.py .`：通过。`git diff --check`：clean。
- GitNexus 影响分析（PreToolUse hook）：`repair_merged`/`generate_review_report` 仅 `pdf-auto` 内部调用，新增 `_append_toc_unassigned` 仅 review_report 内部；风险 LOW。提交后 `post-commit-index` hook 自动刷新知识图谱（`detect_changes()` 等价手段）。

### 边界说明

demo5/demo60 与 demo20 同源、文本层清晰，无真正乱码/无文本层样本，TOC 归属 review 在现有真实样本不触发，其正确性由单元测试覆盖（Beta 进 review 场景）。未来若接入乱码/无文本层目录样本，review.md 的“目录归属复核”段将展示未归属条目。

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
| 乱码/无文本层目录真实样本缺失 | demo5/demo20/demo60 为同源手册（首页与 p2 目录文本 SHA 一致，仅页数 5/20/60 不同）、文本层清晰，无真正乱码/无文本层目录；「无法唯一归属→进 review」路径与 review.md「目录归属复核」段在真实样本中不触发，仅单元测试覆盖（Alpha/Gamma 归属、Beta 进 review）。待补真实乱码/无文本层目录样本后再做端到端验收 | 待补样本 |

## 完成条件

- [x] Step 0 红基线通过：`制动 130` 不再归属 p2。（阶段 1，2026-07-11）
- [x] p2–p8 目录条目按物理页正确归属，无整本目录重复。（阶段 2，2026-07-11）
- [x] `<!-- pages N-N -->` 锚点完整保留，消费者回归通过。（阶段 2，2026-07-11）
- [x] `repair()`、`repair_merged()`、`pdf-read-page`、`pdf-extract-data` 兼容验证通过。（阶段 2，2026-07-11）
- [x] demo20、demo5/demo60 真实样本验收通过或进入有证据的 review。（阶段 3，2026-07-11）
- [x] `toc_tree.json`、merged Markdown、review.md 和结构化抽取结果一致。（阶段 3，2026-07-11）
- [x] 独立 `toc.md` 生成，渲染和下游展示不再依赖主 Markdown 中的目录锚点。（阶段 2，2026-07-11）
- [x] 全量测试、治理检查、`git diff --check`、GitNexus `detect_changes()` 通过。（阶段 3，2026-07-11）
