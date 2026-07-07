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
| P2 | 拆分式 MCP 工具（5 个工具） | P1 已完成、MCP 工具设计已就绪 | `tools/list` 返回 6 个工具（1 旧 + 5 新）、端到端 CLI 封装验证 | 已完成 |
| P3a | 关键词检索 + 按页读取（无新依赖） | P2 已完成、有完整输出包样本（春风 150AURA） | `search_pdf_content` 返回页码/章节/原文片段、`read_page` 返回指定页 Markdown | 待实施 |
| P3b | 向量索引 + 语义检索 | P3a 已完成、确定向量存储和 embedding 方案 | 语义检索端到端可用、检索质量可量化 | 候选 |
| P4 | 评测体系 + 多模态增强 | P3a 或 P2 已完成、有表格和图片密集型 PDF 样本 | `table_accuracy.csv` 产出、TOC 条目级验证可用、VLM 描述产出 | 候选 |
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

## 当前阶段：P3a 关键词检索 + 按页读取

### 范围

新增 2 个 MCP 工具，补齐豆包第 3 层"关键词检索"和第 4 层"读页"能力：

- `search_pdf_content`：关键词检索已解析内容（合并 Markdown + quick_lookup_draft.csv），返回页码/章节/原文片段
- `read_page`：按 PDF 页码读取合并 Markdown 中对应片段

P3a 不引入任何新依赖，纯基于现有输出包文件的文本检索。

### 检索面

两个数据源覆盖不同类型的查询：

| 数据源 | 文件 | 格式 | 内容 |
|---|---|---|---|
| 合并 Markdown | `<package>/<stem>.md` | `<!-- pages N-M -->` 页锚 + 正文 | 全文段落、标题、表格文本 |
| 结构化草案 | `<package>/data/quick_lookup_draft.csv` | 16 字段 CSV | 键值对、规格参数、章节路径、证据文本、页码 |

### CLI-to-MCP 映射

| MCP 工具 | CLI 后端 | 说明 |
|---|---|---|
| `read_page` | `scripts/pdf-read-page`（需新建） | 按页码或页码范围从合并 Markdown 提取文本 |
| `search_pdf_content` | `scripts/pdf-search-content`（需新建） | 关键词搜索 Markdown + CSV，返回统一结果 |

### 前置条件

- [x] P2 已完成（6 个 MCP 工具就绪）
- [x] 有完整输出包样本：春风 150AURA（3212 行 Markdown + 390 行 CSV）
- [ ] `scripts/pdf-read-page` 新建
- [ ] `scripts/pdf-search-content` 新建

### 实施步骤

1. **`scripts/pdf-read-page`**：Python 脚本，读合并 Markdown，按 `<!-- pages N-M -->` 锚点定位页码范围，输出该段 Markdown 文本。若合并 Markdown 不存在，从 `segments/` 目录按分段名查找。
2. **`scripts/pdf-search-content`**：Python 脚本，对合并 Markdown + `quick_lookup_draft.csv` 做关键词匹配，返回统一结果列表（含来源、页码、章节、原文片段）。
3. **MCP 端实现 2 个工具**：在 `mcp/server/src/index.ts` 中新增 `read_page` 和 `search_pdf_content`，通过 `runScript` 调用对应 CLI。输入校验复用 `validateDir`。
4. **编译 + 工具列表验证**：`npm run build`，确认 `tools/list` 返回 8 个工具（6 旧 + 2 新）。
5. **端到端验证**：用春风 150AURA 输出包走通两个工具的调用→返回路径（正常 + 错误输入）。
6. **更新 MCP 文档**：同步 `mcp/README.md`。

### 工具契约设计

#### `read_page`

输入：

```json
{
  "package_dir": "/abs/path/pdf/春风 150AURA",
  "page": 14
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `package_dir` | string | 是 | 输出包根目录（含 `<stem>.md` 和 `segments/`） |
| `page` | number | 是 | PDF 页码（1-based），会定位到包含该页的 `<!-- pages N-M -->` 段 |
| `page_end` | number | 否 | 结束页码，指定后返回连续多段的 Markdown |

输出：

```json
{
  "status": "completed",
  "page": 14,
  "page_start": 9,
  "page_end": 16,
  "section_path": "150 AURA 使用说明书 / 序列号",
  "markdown": "## 序列号\n\n| 项目 | 规格 |\n| ..."
}
```

失败模式：输出包目录不存在、合并 Markdown 不存在且无分段目录、页码超出范围。

#### `search_pdf_content`

输入：

```json
{
  "package_dir": "/abs/path/pdf/春风 150AURA",
  "query": "最大净功率",
  "max_results": 10,
  "source": "all"
}
```

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `package_dir` | string | 是 | 输出包根目录 |
| `query` | string | 是 | 搜索关键词（支持空格分隔的多个词） |
| `max_results` | number | 否 | 最大返回数，默认 10 |
| `source` | enum | 否 | `all` / `markdown` / `csv`，默认 `all` |

输出：

```json
{
  "status": "completed",
  "query": "最大净功率",
  "total_matches": 3,
  "results": [
    {
      "source": "csv",
      "key": "最大净功率",
      "value": "11.8 Kw / 8500",
      "unit": "rpm",
      "page_start": 14,
      "page_end": 14,
      "section_path": "150 AURA 使用说明书 / 序列号",
      "evidence_text": "最大净功率: 11.8 Kw / 8500 rpm",
      "confidence": "medium"
    },
    {
      "source": "markdown",
      "page_start": 14,
      "page_end": 14,
      "section_path": "150 AURA 使用说明书 / 序列号",
      "snippet": "最大净功率 11.8 Kw / 8500 rpm..."
    }
  ]
}
```

### Step 0 证据

**P2 完成证据**：
- 提交 `5b61c77`：P2 拆分式 MCP 工具 + review 遗留修复。
- 6 个 MCP 工具 + 2 个新 CLI JSON 模式 + `lib/review_report.py` 提取。
- 端到端验收通过（all_passed + needs_review 两条路径）。
- 治理检查通过。

**P3a 基线（2026-07-08）**：
- 输出包检索面已核实：
  - 春风 150AURA：合并 Markdown 3212 行，`<!-- pages N-M -->` 页锚按 8 页间隔分布
  - `quick_lookup_draft.csv`：390 行，16 字段含 `key`/`value`/`page_start`/`section_path`/`evidence_text`
- 无需新增 Python/系统依赖，纯文本检索。

### 验证方式

```bash
# CLI 验证
scripts/pdf-read-page pdf/春风\ 150AURA 14
scripts/pdf-read-page pdf/春风\ 150AURA 14 16
scripts/pdf-search-content pdf/春风\ 150AURA "最大净功率"
scripts/pdf-search-content pdf/春风\ 150AURA "最大净功率" --source csv --max 5

# MCP 编译
cd mcp/server && npm run build

# 工具列表验证（期望 8 个工具）
# 治理检查
python3 scripts/check_plan_governance.py .
```

### 完成条件

- [ ] `tools/list` 返回 8 个工具（6 旧 + `read_page` + `search_pdf_content`）
- [ ] `read_page` 按页码正确返回 Markdown 段（含 `<!-- pages -->` 锚点对应的章节）
- [ ] `read_page` 超范围页码返回明确错误
- [ ] `search_pdf_content` 对 CSV 数据返回 key/value/page/section/evidence 结果
- [ ] `search_pdf_content` 对 Markdown 全文返回页码/snippet 结果
- [ ] `search_pdf_content` 多词搜索（空格分隔）支持 AND 逻辑
- [ ] 非法输入（不存在的目录、空 query）返回明确错误
- [ ] TypeScript 编译通过，`npm run build` 无错误
- [ ] 治理检查通过

## P3b-P5 后续阶段（粗粒度）

### P3b：向量索引 + 语义检索

**范围**：

- 对合并 Markdown 按 `<!-- pages N-M -->` 分段建 embedding
- 向量存储选型（候选：ChromaDB / SQLite + sqlite-vec / numpy-only）
- `search_pdf_content` 增加 `mode: "semantic"` 参数
- embedding 模型选型（候选：本地 sentence-transformers / API）

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
P1（收尾）→ P2（MCP 拆分）→ P3a（关键词+读页）→ P3b（向量语义检索）→ P4（评测+多模态）
                                                              ↘ P5（远期）
```

P3a 不依赖 P3b，但 P3b 在 P3a 的检索工具基础上增加语义模式。

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| P2 是否需要拆分 tools/ 目录 | 初期单文件实现，等工具数 ≥6 再拆分 | 否 | 已记录 |
| 向量索引选型（ChromaDB vs sqlite-vec） | P3b 阶段 0 评估，优先选无服务依赖的方案 | 否 | 已延后 |
| 多模态 VLM 选型（Claude Vision vs 本地模型） | P4 阶段 0 评估，取决于成本和精度要求 | 否 | 已延后 |
| `pdf-auto` 的 `--rerun-only` 模式是否存在 | 已确认：`scripts/pdf-rerun` 已实现独立重跑+合并功能，可作为 `rerun_segments` MCP 工具的后端 | 否 | 已解决 |
| `pdf-seg` / `pdf-rerun` 缺少 JSON 输出模式 | P2 实施 step 1/2 分别增加 `PDF_SEG_JSON=1` 和 `PDF_RERUN_JSON=1` | 是 | P2 实施中解决 |
| review 生成无独立 CLI | P2 已创建 `scripts/pdf-review` + `lib/review_report.py`，`pdf-auto` 已重构为调用 lib | 否 | 已解决 |
| `pdf-rerun` 使用 1-based 页码 vs MCP 设计 0-based | MCP 工具统一使用 1-based（与 CLI 一致），更新 MCP README 中的 schema 示例 | 否 | 设计决策已记录 |
| `pdf-auto` review 代码已重构为 lib | 3 处内联 review 生成替换为 `from lib.review_report import generate_review_report`（共 -424 行），`lib/review_report.py` 为唯一事实源 | 否 | 已解决 |

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
