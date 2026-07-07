# 计划：PDF 工作流增强路线图

## 背景

2026-07-07 对照豆包分享的"PDF 转文本四层处理"架构，对当前 MinerU PDF 工作流做了逐层差距分析。现有流水线在分层解析（第 1 层）和结构还原（第 2 层）方面已较扎实，但在语义索引（第 3 层后半）和工具化 Agent 调用（第 4 层）方面存在明显差距。

本路线图记录从当前状态到补齐四层架构的阶段性计划。

## 事实源职责

本文档是 `pdf-workflow-enhancement-roadmap` 的实施细节事实源，记录阶段划分、目标、依赖和完成条件。

计划状态、依赖、替代/合并/废弃关系、推荐顺序、当前阻塞项和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准。各阶段专项计划 `docs/plans/*.md` 是实施细节事实源。

## 目标

- 补齐豆包四层架构中当前项目未覆盖的能力：拆分式 MCP 工具（第 4 层）、语义索引与检索（第 3 层）、评测体系与多模态增强（第 1 层）。
- 各阶段产出可独立验收、可与现有流水线集成的最小增量。
- 不破坏现有 CLI/MCP 契约，所有增强向后兼容。

## 非目标

- 不改变 MinerU 解析引擎本身。
- 不在当前阶段替换 PDF 文本层抽取方案。
- 不承诺数据库选型或下游入库接口。
- 不新增 Python 依赖（向量索引阶段再评估）。
- P2-P5 不做完整 MCP server 重写，只做增量工具扩展。

## 不变量

- 现有 CLI 脚本签名和 JSON 输出契约不变。
- `run_pdf_auto` MCP 工具保持向后兼容，拆分工具作为新增工具，不替换现有工具。
- 原始 PDF、分段结果、合并 Markdown 不被增强工具修改。
- 同一事实只在本文档或专项计划中定义一次，其他位置通过链接引用。

## 影响模块或文件

P1（已完成）：

- `scripts/pdf-auto`：TOC 修复重构 → `lib/toc_repair.py`
- `scripts/pdf-extract-data`：TOC 树 section_path 增强

P2（当前阶段）：

- `mcp/server/src/index.ts`：新增 5 个拆分工具
- `mcp/server/src/tools/`：各工具实现模块（如需拆分）
- `mcp/README.md`：更新工具契约文档
- `docs/plans/pdf-workflow-enhancement-roadmap.md`

P3-P5 的候选影响范围见各自阶段描述，实施前再细化。

## 公共契约变化

P1 无公共契约变化（纯重构 + 内部增强，不影响 CLI/MCP 接口）。

P2 将新增 5 个 MCP 工具，设计已就绪于 [MCP 接入设计](../../mcp/README.md#后续扩展工具草案)。现有 `run_pdf_auto` 工具保持不变。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| P1 | 提交未完成改动，清理工作区 | 有两个未提交的脚本改动 | 语法检查通过、detect_changes 低风险、提交成功 | 已完成 |
| P2 | 拆分式 MCP 工具（5 个工具） | P1 已完成、MCP 工具设计已就绪 | `tools/list` 返回 6 个工具（1 旧 + 5 新）、端到端 CLI 封装验证 | 待实施 |
| P3 | 内容检索 + 语义索引 | P2 已完成、有真实输出包样本（如 demo20） | `search_pdf_content` 返回页码/章节/片段、向量索引可检索 | 候选 |
| P4 | 评测体系 + 多模态增强 | P3 或 P2 已完成、有表格和图片密集型 PDF 样本 | `table_accuracy.csv` 产出、TOC 条目级验证可用、VLM 描述产出 | 候选 |
| P5 | 远期（数据库直连 + 批量处理） | 依赖外部系统配合 | — | 候选 |

## 当前基线

所有 11 个已有计划均为 `已完成`。核心能力基线：

- **分层解析**：MinerU hybrid-engine + OCR + 页面类型分类（text/toc/table/image_or_sparse/no_text_layer）
- **验证闭环**：分段解析 → 覆盖率验证 → 可疑段 high 重跑 → 再验证 → 合并 → 人工兜底清单
- **结构化抽取**：键值对 + 表格提取，15 字段含上下文元数据（页码/章节/块ID/表格ID/父级标签）
- **入库准备**：冲突检测 → 人工审核 → JSONL 导出（不直连数据库）
- **MCP 接入**：`run_pdf_auto` 单一高层工具

## 豆包四层差距总览

```
豆包四层              当前覆盖    关键缺口
──────────────────  ────────    ──────────────────────────
第1层 分层解析        ~85%       独立多模态视觉理解链路
第2层 结构还原        ~80%       TOC 条目级验证
第3层 语义切片建索引   ~55%       向量索引 + 关键词检索引擎
第4层 Agent 工具调度   ~35%       拆分式 MCP 工具 + 智能调度
生产评测             ~70%       表格解析精度专项指标
```

## 当前阶段：P2 拆分式 MCP 工具

### 范围

将单一 `run_pdf_auto` 工具拆分为 5 个独立 MCP 工具：

- `parse_pdf_segmented`：分段解析
- `validate_segments`：覆盖率验证
- `rerun_segments`：单段重跑
- `merge_segments`：合并 Markdown
- `create_review_report`：生成人工兜底清单

### CLI-to-MCP 映射

5 个拆分工具各对应一个已有 CLI 脚本：

| MCP 工具 | CLI 后端 | JSON 模式 | 备注 |
|---|---|---|---|
| `parse_pdf_segmented` | `scripts/pdf-seg` | 需新增 `PDF_SEG_JSON=1` | 当前无 JSON 输出，需仿照 `pdf-validate` 增加 |
| `validate_segments` | `scripts/pdf-validate` | `PDF_VALIDATE_JSON=1` ✅ | 已有完整 JSON 输出 |
| `rerun_segments` | `scripts/pdf-rerun` | 需新增 `PDF_RERUN_JSON=1` | 当前无 JSON 输出；CLI 使用 1-based 页码，MCP 设计需对齐 |
| `merge_segments` | `scripts/pdf-merge` | 无需 JSON（输出文件路径即可） | 简单工具 |
| `create_review_report` | `scripts/pdf-review` | **需新建脚本** | review 生成逻辑当前内联在 `pdf-auto` 中，P2 实施前需提取为独立脚本 + `lib/review_report.py` |

### 前置条件

- [x] P1 已完成
- [x] MCP 工具设计已就绪（mcp/README.md）
- [x] GitNexus 影响分析：`runPdfAuto` 仅被 `main` 调用，无爆炸半径，新增工具低风险
- [ ] **`create_review_report` 后端**：从 `pdf-auto` 提取 review 生成逻辑到 `scripts/pdf-review` + `scripts/lib/review_report.py`（P2 实施 step 0）
- [ ] **`pdf-seg` JSON 模式**：新增 `PDF_SEG_JSON=1` 输出（P2 实施 step 1）
- [ ] **`pdf-rerun` JSON 模式**：新增 `PDF_RERUN_JSON=1` 输出（P2 实施 step 2）

### 实施步骤

1. **提取 review 生成模块**：将 `pdf-auto` 中 3 处内联 review 生成 Python 提取到 `scripts/lib/review_report.py`，创建 `scripts/pdf-review` CLI 入口。
2. **给 `pdf-seg` 增加 JSON 模式**：仿照 `pdf-validate` 的 `PDF_VALIDATE_JSON=1` 模式，新增 `PDF_SEG_JSON=1`，输出分段名、页码范围、状态。
3. **给 `pdf-rerun` 增加 JSON 模式**：新增 `PDF_RERUN_JSON=1`，输出重跑段名和状态。
4. **MCP 端实现 5 个工具**：在 `mcp/server/src/index.ts` 中新增工具注册，每个工具通过 `spawn` 调用对应 CLI 脚本，复用现有 `validateInputs`/`parseCliOutput`/`formatOutput` 模式。`pdf-rerun` 的页码参数统一为 1-based（与 CLI 一致）。
5. **编译 + 工具列表验证**：`npm run build`，确认 `tools/list` 返回 6 个工具。
6. **端到端验证**：用 `demo5.pdf` 走通全部 5 个工具的调用→返回路径（正常 + 错误输入）。
7. **更新 MCP 文档**：同步 `mcp/README.md` 工具契约、运行手册和排障清单。

### Step 0 证据

**P1 完成证据**：

- 提交 `c227362`：`pdf-auto` TOC 修复重构为 `lib/toc_repair.py`（-381/+104 行），`pdf-extract-data` TOC 树 section_path（+82 行），修复 rerun 分支 `$validate_tmp`→`$validate2_tmp` bug。
- 语法检查通过（`bash -n`、`python3 -c ast.parse`）。
- `detect_changes` 风险级别 LOW，无受影响流程。
- 治理检查通过。

**P2 基线（2026-07-07）**：

- MCP 工具设计已就绪：[后续扩展工具草案](../../mcp/README.md#后续扩展工具草案)，含 5 个工具的完整 JSON Schema、输入输出契约和失败模式。
- CLI 脚本现状核实：
  - `pdf-seg` ✅ 存在，无 JSON 输出（需新增 `PDF_SEG_JSON=1`）
  - `pdf-validate` ✅ 存在，`PDF_VALIDATE_JSON=1` 已就绪
  - `pdf-rerun` ✅ 存在，无 JSON 输出（需新增 `PDF_RERUN_JSON=1`），使用 1-based 页码
  - `pdf-merge` ✅ 存在，简单工具无需 JSON
  - review 生成 ❌ 无独立 CLI（需从 `pdf-auto` 提取）
- GitNexus 影响分析：`runPdfAuto` 仅被 `main` 调用，无外部依赖，新增工具风险 LOW。

### 验证方式

```bash
# 编译
cd mcp/server && npm run build

# 工具列表验证
node dist/index.js  # 确认 tools/list 包含 run_pdf_auto + 5 个新工具

# 每个工具独立端到端（以 demo5.pdf 为例）
# parse_pdf_segmented
# validate_segments / rerun_segments / merge_segments / create_review_report
# 需确认每个工具在正常参数和错误参数下都能返回预期结构

# 治理检查
python3 scripts/check_plan_governance.py .
```

### 完成条件

- [ ] `tools/list` 返回 6 个工具（`run_pdf_auto` + 5 个拆分工具）。
- [ ] 每个拆分工具的 inputSchema 与 MCP README 设计一致。
- [ ] 至少一个真实 PDF 样本（如 demo5.pdf）走通全部 5 个拆分工具的完整流程。
- [ ] 每个工具在非法输入下返回明确错误（PDF 不存在、分段目录缺失等），不抛未捕获异常。
- [ ] `run_pdf_auto` 行为不变（向后兼容）。
- [ ] TypeScript 编译通过，`npm run build` 无错误。
- [ ] 治理检查通过。

## P3-P5 后续阶段（粗粒度）

### P3：内容检索 + 语义索引

**范围**：

- `search_pdf_content` MCP 工具：基于关键词检索已解析内容（Markdown + CSV），返回页码/章节/原文片段
- 向量索引：对合并 Markdown 分段建 embedding，支持语义检索（候选方案：ChromaDB 或 SQLite + sqlite-vec）
- `read_page` MCP 工具：按页码读取 Markdown 片段

**状态**：候选

### P4：评测体系 + 多模态增强

**范围**：

- 表格解析精度专项评测（参照 TEDS 指标，产出 `data/table_accuracy.csv`）
- TOC 条目级验证（`toc_entries` JSON 扩展，设计见 `coverage-validation-optimization.md:181-240`）
- 多模态图表理解（对 `image_or_sparse` 页调用 VLM 做视觉理解，产出结构化描述）

**状态**：候选

### P5：远期 / 依赖外部

| 事项 | 说明 |
|---|---|
| 数据库直连入库 | `ingest_manifest.json` 当前标注"未写入数据库"，需下游系统配合 |
| 多 PDF 批量处理 | `pdf-auto` 串行，批量需外层编排 |

**状态**：候选

## 依赖关系

```
P1（收尾）→ P2（MCP 拆分）→ P3（检索+索引）→ P4（评测+多模态）
                                    ↘ P5（远期）
```

P2 不依赖 P3，但 P3 的检索工具体验依赖 P2 的拆分式工具基础。P3 和 P4 可部分并行。

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| P2 是否需要拆分 tools/ 目录 | 初期单文件实现，等工具数 ≥6 再拆分 | 否 | 已记录 |
| 向量索引选型（ChromaDB vs sqlite-vec） | P3 阶段 0 评估，优先选无服务依赖的方案 | 否 | 已延后 |
| 多模态 VLM 选型（Claude Vision vs 本地模型） | P4 阶段 0 评估，取决于成本和精度要求 | 否 | 已延后 |
| `pdf-auto` 的 `--rerun-only` 模式是否存在 | 已确认：`scripts/pdf-rerun` 已实现独立重跑+合并功能，可作为 `rerun_segments` MCP 工具的后端 | 否 | 已解决 |
| `pdf-seg` / `pdf-rerun` 缺少 JSON 输出模式 | P2 实施 step 1/2 分别增加 `PDF_SEG_JSON=1` 和 `PDF_RERUN_JSON=1` | 是 | P2 实施中解决 |
| review 生成无独立 CLI | P2 实施 step 0 从 `pdf-auto` 提取为 `scripts/pdf-review` + `lib/review_report.py` | 是 | P2 实施中解决 |
| `pdf-rerun` 使用 1-based 页码 vs MCP 设计 0-based | MCP 工具统一使用 1-based（与 CLI 一致），更新 MCP README 中的 schema 示例 | 否 | 设计决策已记录 |

## 风险和回滚

风险：

- P2 新增工具可能让 MCP server 启动变慢；初期影响可忽略（<Node.js 加载 5 个工具注册的开销）。
- 拆分式工具如果 CLI 封装不完整，可能导致行为与 `run_pdf_auto` 不一致。
- P3 向量索引引入新依赖，可能与现有 venv 冲突。
- P4 VLM 调用增加外部 API 成本和延迟。

回滚：

- P2 拆分工具作为新增，不删除 `run_pdf_auto`；如有问题可仅移除拆分工具。
- P3 索引产物写入 `<package>/data/index/`，不影响现有输出包。
- 各阶段产物独立，可单独回滚而不影响其他阶段。

## 关联 ADR、迁移、spec 或 issue

- [ADR 0001：先 CLI 固化，再 MCP 接入](../adr/0001-cli-first-mcp-ready.md)
- [MCP 接入设计](../../mcp/README.md) — P2 工具契约事实源
- [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md) — P1-P5 均依赖其 CLI 契约
- [覆盖率验证口径优化计划](coverage-validation-optimization.md) — TOC 条目级验证设计（P4）
