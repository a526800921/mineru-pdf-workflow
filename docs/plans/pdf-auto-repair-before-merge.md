# 计划：PDF 自动流程先修复再合并

## 计划状态

`待实施`（阶段 0-2 已完成，待阶段 3 验收）

## 背景

`demo5.pdf` 暴露出当前 `pdf-auto` 的流程时序问题：MinerU 输出的 TOC 分段可能包含乱码，`pdf-validate` 将目录页和图片/稀疏页标记为 `review_only`；当前 `needs_review` 分支虽然会调用 `toc_repair.repair()`，但不执行 `pdf-merge`，因此人工既拿不到修复后的合并 Markdown，`manifest.json` 也可能声明了实际不存在的 Markdown 文件。

现有问题证据见 [TOC 覆盖率问题记录](../issues/toc-coverage-merge-block.md)。当前实现位于 [`scripts/pdf-auto`](../../scripts/pdf-auto) 和 [`scripts/lib/toc_repair.py`](../../scripts/lib/toc_repair.py)。

## 目标

将 PDF 自动解析流程统一为：

```text
MinerU 分段解析
→ 初次验证和页面分类
→ 自动修复可修复内容（优先 TOC）
→ 必要时重跑可重跑段并再次验证
→ 无硬错误时合并 Markdown
→ 合并级兜底修复和最终校验
→ 按质量状态输出 Markdown、review.md 和 manifest.json
```

其中 `needs_review` 的语义调整为“已生成合并 Markdown，但仍有段需要人工复核”，而不是“完全不合并”。

## 非目标

- 不更换 MinerU、PDF 文本层或 VLM 引擎。
- 不因目录页低覆盖率强制触发 high 重跑。
- 不把低覆盖率自动修复结果当作全部通过。
- 不在本计划内扩展 MCP 第一版工具边界；`run_pdf_auto` 仍是唯一第一版入口。
- 不删除或覆盖原始 PDF 和原始分段数据；修复后的 Markdown 必须可回滚或重建。

## 核心不变量

- `pdf-merge` 的输入必须是经过段级修复/重跑决策后的分段结果。
- TOC 修复优先读取 PDF 内置大纲，缺失时回退到 PDF 文本层和 x 坐标层级推断。
- `review_only`、`rerun`、硬错误三类状态必须分开：前两者允许产出带风险标记的合并结果，硬错误不产出声称完成的结果。
- `all_passed` 必须同时具备合并 Markdown 且无未解决质量问题。
- `needs_review` 必须同时具备合并 Markdown 和 `review.md`；`manifest.json.files.markdown` 必须指向真实存在的文件。
- 合并级 TOC 修复不能覆盖非 TOC 页，也不能重复破坏已经完成的段级修复。
- `content_list.json` 等 MinerU 原始中间结果不因只改 Markdown 的 TOC 修复而被伪造同步；需要明确记录这种后处理边界。

## 当前实现与目标实现

| 阶段 | 当前行为 | 目标行为 |
|---|---|---|
| MinerU 解析 | 产出分段 Markdown 和中间 JSON | 保持不变 |
| 初次验证 | 识别 `toc`、`review_only`、`rerunnable` | 保持识别职责，作为修复前分类门禁 |
| TOC 修复 | `needs_review` 中写回纯 TOC 段；`all_passed` 中主要做合并级修复 | 初次分类后先完成段级 TOC 修复；混合段保留合并级兜底 |
| 重跑 | 只对 `rerunnable == true` 的段 high 重跑 | 保持不变，TOC 不进入无效重跑 |
| 合并 | 只有 `all_passed` 或部分旧分支会合并 | 无硬错误时都合并；`needs_review` 产出草稿级合并结果 |
| 状态 | `needs_review` JSON 的 Markdown 路径为空 | `needs_review` 返回 `merged_markdown` 和 `review_markdown` |
| manifest | 可能声明不存在的 Markdown | 产物字段与文件系统实际结果一致 |

## 分阶段计划

### 阶段 0：固定 Step 0 基线

状态：`已完成`

#### Step 0 证据（`pdf/demo5/`）

- `demo5.pdf` 5 页样本在阈值 `0.82` 下为 1 段通过、4 段 `review_only`。
- p0002 MinerU 原始 TOC Markdown 覆盖率约 `2.49%`，包含重复”言”乱码。
- `pdf-auto` 执行后 `repair()` 成功修复全部 4 个 TOC 段（78 条目，来源：文本层 x 坐标）。
- 当前 `needs_review` 路径执行 TOC 段修复并生成 `review.md`，但不生成合并 Markdown。
- `cli_json.status == “needs_review”`, `merged_markdown == null`（CLI JSON），`exit_code == 2`。
- `manifest.json.files.markdown == “demo5.md”` 但文件真实不存在（manifest 声明不一致 bug）。
- 当前 `scripts/lib/toc_repair.py` 已具备 PDF 内置大纲和文本层 fallback 两种修复来源。

基线命令（已执行，证据保存于 `pdf/demo5/.step0.*`）：

```bash
PDF_VALIDATE_THRESHOLD=0.82 PDF_AUTO_JSON=1 \
  scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments
```

基线完成条件验证：

| 验收项 | 结果 |
|--------|------|
| 退出码 | ✅ 2 |
| `stdout.status` | ✅ `needs_review` |
| `stdout.merged_markdown` | ✅ `null` |
| `stdout.review_markdown` | ✅ 非空且文件存在 |
| `manifest.json.parse_status` | ✅ `needs_review` |
| `manifest.json.files.markdown` | ⚠️ 声称 `”demo5.md”` 但文件不存在（已记录为 bug） |
| p0002 原始内容 | ✅ 乱码 “前言言言...” |
| p0002 修复后内容 | ✅ 结构化 78 条目缩进列表 |
| `review.md` | ✅ 非空，列出 4 个 `review_only` 段 |
| `toc_tree.json` | ✅ 78 条目，包含 title/page/depth |

### 阶段 1：固化修复—合并顺序和状态契约

状态：`已完成`

#### 1. pdf-auto 状态机

对当前实现（`scripts/pdf-auto`）逆向建模，以下为正式契约。

```text
入口（pdf + segments_dir）
  │
  ├─ 输入错误（缺参数/文件/目录）────→ error ──→ exit 1
  │
  ├─ 初次验证
  │   ├─ all_passed → 段级 repair() → merge → repair_merged()
  │   │                                │
  │   │                              复审 review_only 段
  │   │                              ├─ 无 review_only → all_passed, exit 0
  │   │                              └─ 有 review_only → 生成 review.md → all_passed, exit 0*
  │   │
  │   ├─ needs_review （无 rerunnable，有 review_only）
  │   │   → 段级 repair() → 生成 review.md ──→ needs_review, exit 2（当前不合并）
  │   │
  │   └─ rerun（有 rerunnable 段）
  │       → 高精度重跑 rerunnable 段
  │       → 二次验证
  │           ├─ all_passed → 覆盖重跑结果 → merge → repair_merged()
  │           │                                 → all_passed, exit 0
  │           │
  │           └─ has_issues → 段级 repair() → 生成 review.md
  │                                            → needs_review, exit 2（当前不合并）
  │
  └─ 脚本/API 故障 ──────────────────→ error ──→ exit 1
```

**目标状态机**（阶段 2 实施后）：

```text
入口
  │
  ├─ 输入错误 ──────────→ error ──→ exit 1
  │
  ├─ 初次验证
  │   → 段级 repair()（所有 TOC 段）
  │   → 高精度重跑 rerunnable 段（如有）
  │   → 二次验证
  │   → merge（合并就是执行 pdf-merge，无论验证结果）
  │   → repair_merged() 兜底
  │   → 质量判定
  │       ├─ 无 review_only → all_passed, exit 0
  │       └─ 有 review_only → 生成 review.md → needs_review, exit 2
  │
  └─ 脚本/API 故障 ──────→ error ──→ exit 1
```

**变更要点**：

| 当前行为 | 目标行为 |
|---|---|
| `needs_review` 路径不执行 merge | `needs_review` 路径也执行 merge，产出合并 md |
| `needs_review` 路径的 `merged_markdown=null` | `needs_review` 路径的 `merged_markdown` 非空 |
| `manifest.json.files.markdown` 写入 "demo5.md" 但文件不存在 | 只有 merge 后才写入 markdown 字段；写入时文件必须真实存在 |
| TOC 段级修复只在 `needs_review` 路径执行 | 段级修复统一在验证后、合并前执行（单一路径） |

\* 当前实现中 `all_passed` 路径其实也可能有 `review_only` 段（首次验证全部通过但阈值低），此时同样生成 review.md。目标状态机统一在 merge 后判质量，更清晰。

---

#### 2. 状态枚举与退出码契约

| CLI JSON status | MCP 映射 status | exit_code | merged_markdown | review_markdown | 含义 |
|---|---|---|---|---|---|
| `all_passed` | `passed` | 0 | 路径（非空，文件存在） | `null` 或路径（有 review_only 段时存在） | 合并完成，无未决质量问题 |
| `needs_review` | `needs_review` | 2 | 路径（非空，文件存在） | 路径（非空，文件存在） | 合并完成，有段需人工复核 |
| `error` | `failed` | 1 | `null` | `null` | 输入错误或脚本故障 |

**约束**：

- `all_passed`: `merged_markdown` 必须非空且文件系统真实存在；`review_markdown` 可选（当有 review_only 段但决策已经人工判断无需复核时可为 `null`）。实际上当前会在 `all_passed` 且有 review_only 段时生成 review.md，所以常非空。
- `needs_review`: `merged_markdown` 和 `review_markdown` 都必须非空且文件系统真实存在。
- `error`: 两个路径字段都必须为 `null`（不指向不存在的文件）。

---

#### 3. manifest.json 契约

```json
{
  "parse_status": "all_passed" | "needs_review" | "error",
  "files": {
    "markdown": "<stem>.md" | null,     // 仅当文件真实存在时写入
    "review": "review.md" | null,
    "segments": "segments",
    "images": "images",
    "data": "data"
  }
}
```

**约束**：

- `parse_status == "needs_review"` 时：`files.markdown` 和 `files.review` 都必须写入且文件真实存在。
- `parse_status == "all_passed"` 时：`files.markdown` 必须写入且文件真实存在；`files.review` 可选。
- `parse_status == "error"` 时：`files.markdown` 为 `null`；`files.review` 为 `null`。
- 修正 Step 0 发现的 bug：`update_manifest` 在 `needs_review` 路径不得在未执行 merge 前写入 `markdown` 字段。

---

#### 4. repair_merged() 契约

**输入边界**：

- 只接收合并后的 Markdown 路径（必须已存在）。
- 只读取 `validate_tmp` JSON 中 `page_type_summary.toc > 0` 的段。
- 只替换这些段在合并 md 中对应的 `<!-- page N -->` → `<!-- page M -->` 范围的锚点内容。
- 非 TOC 段的内容完全保留，不做任何修改。

**处理优先级**（与段级 `repair()` 一致）：
1. PDF 内置大纲（`fitz.get_toc()`）——最可靠，零消耗。
2. PDF 文本层 x 坐标——需要逐页解析，计算缩进层级。
3. 都不成功 → 不修改，返回 0。

**幂等性**：

- 第二次在相同合并 md 上运行，解析同样的 PDF 和文本层，应输出语义相同的结果。
- 除非 PDF 文本层被修改（不可能），否则同一输入的多重调用不应改变输出。
- 实践保障：`_extract_entries_from_page()` 从不变文本层提取，`_build_merged_toc_block()` 接受相同的 entries 列表产生相同的 md 块。

**适用范围**：

- 纯 TOC 段：段级 `repair()` 已在合并前完成修复，`repair_merged()` 不需要再改它们（但运行时检测到会覆写一次，内容应一致）。
- TOC 混合段（toc 页 + 非 toc 页在同一分段）：段级 `repair()` 跳过（`toc_pages < total_pages` 条件），`repair_merged()` 只替换 TOC 页范围的锚点内容，非目录页完全保留。
- 非 TOC 段：`repair_merged()` 根本不处理。

**失败策略**：

- 合并 md 找不到锚点 `<!-- page N -->` → 输出警告到 stderr，返回 0，不修改文件。
- entries 为空（PDF 无大纲 + 文本层无可解析 TOC）→ 返回 0，不修改文件。
- 任何异常 → 捕获到 stderr，返回 0，保留原始合并 md 不变。
- 不抛出异常中断主流程。

---

#### 5. 未决问题明确

基于阶段 1 分析：

**问题 1：合并文件命名**

沿用 `<stem>.md`（稳定主文件名），由 `parse_status` 区分质量。不引入 `<stem>-draft.md`。
理由：（a）退出码 2 已在下游区分通过状态；（b）引入-draft 需要改变 manifest 字段方案、MCP 返回路径和所有下游调用方；（c）当前 `mcp/README.md` 和 `automated-pdf-pipeline.md` 均未引用 draft 命名。

**问题 2：manifest warnings 字段**

暂不扩展 `manifest.json` schema。TOC 后处理来源在 `review.md` 记录即可（review.md 已经包含分段状态和覆盖率信息）。如需未来扩展，计划单独开 plan。
理由：（a）manifest 当前字段方案不改现有下游调用；（b）review.md 已经结构化记录。

**问题 3：`repair_merged()` 定位**

保留为所有 TOC 的最终兜底，不仅限于混合段。纯 TOC 段的段级修复和合并级兜底可能重复写入但内容一致（来自相同文本层），幂等性保障不影响正确性。用 demo60 和混合段样本在阶段 3 验收确认。

---

#### 6. 对照清单：与其他文档的一致性

| 文档 | 需同步的内容 | 与阶段 1 契约的一致性 | 阶段 2 操作 |
|---|---|---|---|
| `skills/pdf2md/SKILL.md` | 结果解读（148-149 行）提到 `needs_review` 语义 | ❌ 当前写 "生成 `review.md`，需要人工复核"——未提及合并产物。改为 "已生成合并 Markdown + `review.md`，需要人工复核" | 阶段 2 实现后同步 |
| `skills/pdf2md/SKILL.md` | run_pdf_auto 参数和结果解读 | ❌ 与 `needs_review` 状态语义同步更新 | 阶段 2 实现后同步 |
| `mcp/README.md` | 退出码和状态映射表（495-498 行） | ⚠️ 映射表中 `needs_review` 对应 `merged_with_issues`，但当前 CLI 输出中没有 `merged_with_issues` status。实际从 `emit_json` 看 CLI 输出是 `needs_review` 和 `all_passed` | 修正映射表：CLI `needs_review` → MCP `needs_review`，删除 `merged_with_issues` 词汇 |
| `mcp/server/src/index.ts` | `CLIStatus` 类型定义（12 行） | ✅ 已定义 `all_passed \| needs_review \| error`，与阶段 1 契约一致 | 无变更需要 |
| `mcp/server/src/index.ts` | 工具说明（408 行） | ❌ 写 "needs_review：存在需人工复核的段，未合并"——与目标语义不符 | 阶段 2 实现后更新 |
| `docs/plans/automated-pdf-pipeline.md` | 状态映射（129 行） | ⚠️ 写 "`merged_with_issues` → `needs_review`"，但 CLI 没有 `merged_with_issues` | 统一到《CLI status → MCP status》映射，删除 `merged_with_issues` |
| `docs/plans/per-page-anchors.md` | TOC 段与逐页锚点交互 | ✅ TOC 段修改是 `toc_repair` 职责，逐页锚点只插入注释行，不冲突 | 无变更需要 |
| `docs/PLAN_MAP.md` | 本计划状态 | ✅ 已同步 | 每个阶段完成时同步 |
| `/Users/jafish/.claude/skills/pdf2md/SKILL.md` | 用户级 skill 副本 | ❌ 需要从项目级 skill 同步 | 阶段 2 实现后同步（若当次无法同步，记录原因） |

#### 7. 阶段 1 完成条件

- ✅ 状态机已建模（当前 4 条 exit 路径 + 目标 2 条 exit 路径，变更要点已对照）。
- ✅ 状态枚举与退出码契约已规定（3 种 status + 对应 exit_code + 文件存在性约束）。
- ✅ manifest.json 契约已规定（3 种 parse_status 对应的 files 字段约束）。
- ✅ repair_merged() 的输入边界、幂等性、适用范围和失败策略已规定。
- ✅ 未决问题已明确（命名、warnings、repair_merged 定位）。
- ✅ 对照清单已完成（9 个文档/文件，标注一致性状态）。
- ⬜ 阶段 2 实施后，按对照清单逐项同步已在计划中。

#### 阶段 1 验收记录（2026-07-11）

独立复核结果：

- ✅ 目标流程明确为“段级 TOC 修复 → 必要时重跑 → 合并 → 合并级兜底 → 质量判定”。
- ✅ `needs_review` 明确要求同时返回真实存在的 `merged_markdown` 和 `review_markdown`，退出码保持 `2`。
- ✅ `manifest.json` 明确了 `parse_status` 与文件存在性的对应关系，覆盖 Step 0 的 manifest 缺陷。
- ✅ `repair_merged()` 已明确输入边界、TOC/非 TOC 修改范围、幂等性和失败不阻断策略。
- ✅ 已使用 `rg` 对照项目级 skill、用户级 skill、MCP 文档、自动化流水线计划、输出包计划、逐页锚点计划和 MCP 实现；发现的旧语义已登记为阶段 2 同步项。
- ✅ 当前代码仍保留旧 `needs_review` 不合并行为，未误判为阶段 1 已实现；实现变更留给阶段 2。

验收结论：阶段 1 通过。阶段 2 可进入 `待实施`，但开始修改代码前必须重新确认实现范围，并按项目 GitNexus 规则对目标符号执行影响分析。

### 阶段 2：实现流程调整

状态：`已完成`

| 文件 | 变更 |
|---|---|
| `scripts/pdf-auto` | 首次验证 `needs_review` 路径和重跑后 `has_issues` 路径均新增 `pdf-merge` + `repair_merged()` 步骤；usage 文本更新；`update_manifest` 修复：空 review/merged 参数显式置 null，避免跨运行状态泄漏 |
| `scripts/lib/toc_repair.py` | 修复 `repair_merged()` 中 TOC 页号计算：`p["page"]` 是文档级 0-based 索引，使用 `p["page"] + 1` 而非 `start + p["page"]` |
| `skills/pdf2md/SKILL.md` | `needs_review` 语义更新；删除 `merged_with_issues` 词汇 |
| `/Users/jafish/.claude/skills/pdf2md/SKILL.md` | 同步项目级 skill |
| `mcp/README.md` | 状态映射表修正：CLI `needs_review` → MCP `needs_review` |
| `mcp/server/src/index.ts` | 工具说明 `needs_review` 从"未合并"改为"已合并" |
| `docs/plans/automated-pdf-pipeline.md` | 状态映射中 `merged_with_issues` → `needs_review` |

**阶段 2 补充修复（manifest 状态泄漏）**：

发现：连续运行先 `needs_review` 再 `all_passed` 时，manifest 的 `files.review` 未从 `"review.md"` 清理为 `null`。根因：`update_manifest()` 中 `if review:` 条件判断空字符串为 falsy 时直接跳过赋值，保留了上一轮的字段值。修复：改为无条件赋值，空值或空字符串时显式写入 `null`。

**验收结果**：

| 测试 | status | exit_code | merged_markdown | review_markdown | manifest.files.review | 结果 |
|---|---|---|---|---|---|---|
| demo5 threshold=0.82 | `needs_review` | 2 | 非空且文件存在 | 非空且文件存在 | `"review.md"` | ✅ |
| demo5 threshold=0.4（后运行） | `all_passed` | 0 | 非空且文件存在 | `null` | `null` | ✅ |
| 连续运行 manifests 一致 | — | — | — | — | 无泄漏 | ✅ |

#### 阶段 2 再次验收记录（2026-07-11）

针对 manifest 状态泄漏修复重新执行连续运行回归：

1. `threshold=0.82`：`needs_review`、退出码 `2`，合并 Markdown 和 `review.md` 均存在，manifest 同步写入 `"demo5.md"` 和 `"review.md"`。
2. `threshold=0.4`：`all_passed`、退出码 `0`，合并 Markdown 存在，CLI 返回 `review_markdown: null`，manifest 已将 `files.review` 清理为 `null`。

同时确认 shell 语法、MCP 构建、治理检查和 TOC 内容检查均通过。验收结论：阶段 2 通过，阶段 3 可以进入 `待实施`。

### 阶段 3：真实样本验收和治理收尾

状态：`已完成`

验收样本至少包括：`demo5`、`demo20`、`demo60` 和一个含混合 TOC/正文段的真实输出包。

验证方向：

- 低阈值 `all_passed`：合并 Markdown 存在，TOC 可读，状态为通过。
- 高阈值 `needs_review`：合并 Markdown 和 `review.md` 同时存在，退出码为 2，TOC 修复内容进入合并结果。
- 有可重跑段：先重跑、再修复/合并，确认 rerun 结果和 TOC 修复不互相覆盖。
- TOC 混合段：确认非目录页内容未被 `repair_merged()` 丢失。
- 幂等性：重复执行不新增重复 TOC、重复锚点或不稳定 manifest 差异。
- MCP `run_pdf_auto` 返回路径和 CLI JSON 一致。

## 验证方式

静态检查：

```bash
bash -n scripts/pdf-auto scripts/pdf-merge scripts/pdf-seg
cd mcp/server && npm run build
python3 scripts/check_plan_governance.py .
```

动态检查：

```bash
PDF_VALIDATE_THRESHOLD=0.82 PDF_AUTO_JSON=1 \
  scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments

PDF_VALIDATE_THRESHOLD=0.4 PDF_AUTO_JSON=1 \
  scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments
```

必须检查：

- `needs_review` 的 `merged_markdown` 非空且文件存在；
- `review.md` 非空且列出需复核段；
- 合并 Markdown 中 TOC 不再出现已知重复乱码；
- `manifest.json.files.markdown` 与 `parse_status` 和实际产物一致；
- 失败路径不伪造 `all_passed`，并保留可诊断信息。

#### 阶段 3 验收记录（2026-07-11）

**静态检查**：

| 检查项 | 结果 |
|---|---|
| `bash -n pdf-auto` | ✅ |
| `bash -n pdf-merge` | ✅ |
| `bash -n pdf-seg` | ✅ |
| MCP `npm run build` | ✅ |
| 治理检查 | ✅ |

**样本 1：demo5（5 页，纯 TOC 段）**

| 阈值 | status | exit | merged_md | review_md | manifest.parse | manifest.review |
|---|---|---|---|---|---|---|
| 0.82 | `needs_review` | 2 | ✅ 2317 bytes | ✅ 4677 bytes | needs_review | review.md |
| 0.5 | `all_passed` | 0 | ✅ | null | all_passed | null |
| 幂等性 0.5 | `all_passed` | 0 | ✅（一致） | null | all_passed | null |

TOC 乱码检测：已清除，`言` 仅出现在 `前言` 中（合法内容）。✅

**样本 2：demo20（20 页，新 pdf-seg + pdf-auto 完整链路）**

| 阈值 | status | exit | merged_md | review_md | manifest.parse | manifest.review |
|---|---|---|---|---|---|---|
| 0.82 | `needs_review` | 2 | ✅ 234KB | ✅ 4.6KB | needs_review | review.md |
| 0.5 | `all_passed` | 0 | ✅ | ✅ 4.6KB | all_passed | review.md |

**样本 3：demo60（60 页，8 段含 TOC 混合段）**

段 p0001-0008 为混合段：7/8 页目录，1 页正文。

| 阈值 | status | exit | merged_md | review_md | manifest.parse | manifest.review |
|---|---|---|---|---|---|---|
| 0.82 | `needs_review` | 2 | ✅ 55KB | ✅ 3.3KB | needs_review | review.md |
| 0.4 | `all_passed` | 0 | ✅ | null | all_passed | null |
| 幂等性 0.4 | `all_passed` | 0 | ✅（一致） | null | all_passed | null |

混合段验证：
- 段级 `repair()`：跳过混合段（✅ `跳过混合段（7/8 页目录），保留 MinerU 原始输出`）
- 合并级 `repair_merged()`：锚点感知修复页码 2–8（✅ 121 条目，来源：文本层 x 坐标）

**样本 4：春风 150AURA（191 页，真实输出包，含可重跑段和混合 TOC 段）**

| 阈值 | status | exit | merged_md | review_md | rerun_segments | manifest.parse |
|---|---|---|---|---|---|---|
| 0.82 | `needs_review` | 2 | ✅ 192KB | ✅ 3.9KB | p0185-0191（passed） | needs_review |

可重跑段验证：
- p0185-0191 被识别为 rerunnable（覆盖率 0.9748，low_text_coverage）
- 首次验证后执行 high 重跑，二次验证通过
- TOC 修复不覆盖重跑结果 ✅

MCP 文档一致性：

| 文档 | 内容 | 一致性 |
|---|---|---|
| `mcp/server/src/index.ts` | 工具说明 `needs_review：已合并 Markdown，存在需人工复核的段` | ✅ |
| `mcp/README.md` | 状态映射 `needs_review → needs_review`，退出码 2 | ✅（已修复 `merged_with_issues` 残留） |
| `skills/pdf2md/SKILL.md` | `已合并 Markdown，同时生成 review.md，需要人工复核` | ✅ |
| `/Users/jafish/.claude/skills/pdf2md/SKILL.md` | 用户级已同步 | ✅ |

连续运行回归（manifest 无泄漏）：

| 运行顺序 | manifest.review |
|---|---|
| demo60 0.82 → needs_review | `review.md` |
| demo60 0.4 → all_passed | `null`（已清理） |

验收结论：阶段 3 通过。全计划（阶段 0–3）已完成。

## 风险与回滚

| 风险 | 缓解 | 回滚 |
|---|---|---|
| TOC 修复误覆盖混合段正文 | 段级修复只处理纯 TOC 段；混合段用锚点感知替换 | 恢复原始分段 Markdown，重新执行旧版 merge |
| 合并草稿被下游误当作已通过结果 | `needs_review` 保留退出码 2，并在 manifest/JSON 中显式标记 | 下游继续以状态而非文件存在性作为放行门禁 |
| `repair()` 与 `repair_merged()` 重复修复 | 固化输入边界和幂等测试 | 暂时只启用合并级修复，保留原始 segments |
| 只改 Markdown 导致 content_list 与 md 不一致 | 将 TOC 后处理边界写入文档和 manifest warning | 使用原始 content_list 重新生成分段结果 |
| 旧 MCP/脚本调用方期待 needs_review 无合并文件 | 保留状态和退出码，只增加非空产物路径；补兼容测试 | 通过环境开关或版本化契约暂时恢复旧返回 |

## 未决问题

- `needs_review` 的合并文件命名是否继续使用 `<stem>.md`，还是另设 `<stem>-draft.md`；当前建议继续使用稳定主文件名，由状态字段区分质量。
- 是否为只改 Markdown 的 TOC 修复增加 manifest 的 `warnings` 字段；如果不扩展 Schema，至少在 `review.md` 记录后处理来源。
- `repair_merged()` 是否保留为所有 TOC 的最终兜底，还是仅处理混合段；需要阶段 1 用 demo60 和混合段样本确认。
- 项目级 `skills/pdf2md/SKILL.md` 与用户级副本的同步必须在实现阶段完成；若当次无法写入用户级副本，须记录补同步动作和阻塞原因。

## 参考

- [TOC 覆盖率问题记录](../issues/toc-coverage-merge-block.md)
- [自动化 PDF 解析流水线](automated-pdf-pipeline.md)
- [PDF 输出包目录结构](pdf-output-package-layout.md)
- [逐页锚点](per-page-anchors.md)
- [项目级 pdf2md skill](../../skills/pdf2md/SKILL.md)

## Test Coverage（测试覆盖率证据）

这是 2026-07-15 的仓库级回归基线：`python -m pytest -q` 为 `312 passed, 5 warnings`；`bash tests/test-fix-validate.sh` 为 `133/133`。该证据用于确认当前仓库回归状态，不冒充本历史计划的行覆盖率百分比。
