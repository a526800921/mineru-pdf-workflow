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

P2（已完成）：

- `mcp/server/src/index.ts`：新增 5 个拆分工具
- `mcp/README.md`：更新工具契约文档
- `scripts/pdf-rerun`：PDF_RERUN_JSON=1
- `scripts/pdf-seg`：PDF_SEG_JSON=1
- `scripts/pdf-review` + `scripts/lib/review_report.py`：新建

P3a（已完成）：

- `mcp/server/src/index.ts`：新增 `read_page` + `search_pdf_content`
- `scripts/pdf-read-page` + `scripts/pdf-search-content`：新建

P3b（当前阶段）：

- `mcp/server/src/index.ts`：新增 `export_chunks`
- `scripts/pdf-export-chunks` + `scripts/lib/chunk_utils.py`：新建

## 公共契约变化

P1 无公共契约变化（纯重构 + 内部增强，不影响 CLI/MCP 接口）。

P2 将新增 5 个 MCP 工具，设计已就绪于 [MCP 接入设计](../../mcp/README.md#后续扩展工具草案)。现有 `run_pdf_auto` 工具保持不变。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| P1 | 提交未完成改动，清理工作区 | 有两个未提交的脚本改动 | 语法检查通过、detect_changes 低风险、提交成功 | 已完成 |
| P2 | 拆分式 MCP 工具（5 个工具） | P1 已完成、MCP 工具设计已就绪 | `tools/list` 返回 6 个工具（1 旧 + 5 新）、端到端 CLI 封装验证 | 已完成 |
| P3a | 关键词检索 + 按页读取（无新依赖） | P2 已完成、有完整输出包样本（春风 150AURA） | `search_pdf_content` 返回页码/章节/原文片段、`read_page` 返回指定页 Markdown | 已完成 |
| P3b | 向量化前置准备（无新依赖） | P3a 已完成 | `<package>/data/chunks.jsonl` 产出、每块含页码/章节/纯文本/字数 | 已完成 |
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

## 当前阶段：P3b 向量化前置准备

### 范围

将合并 Markdown 预处理为下游可直接向量化的纯文本块。不引入 embedding 模型或向量数据库，只做数据准备。

预处理规范对齐 [motorcycle-manual-app PC 端构建流程](../../motorcycle-manual-app/ios-agent-方案设计.md#10-pc-端构建流程)（第 10 节），确保产出可直接输入其 build pipeline。

- `scripts/pdf-export-chunks`（需新建）：导出 `data/chunks.jsonl`
- `scripts/lib/chunk_utils.py`（需新建）：chunk 预处理核心逻辑（切分、表格展开、图片替换、token 裁剪）
- MCP `export_chunks`（可选）：封装上述脚本

### 设计原理

不同项目对 embedding 模型和向量存储的选择不同。本阶段只做**向量化前置准备**——产出结构化纯文本块，下游项目按需建索引。

### Chunk 策略（对齐 motor-app §10）

```
合并 Markdown
  │
  ├─ 1. 按 ## 标题切分 chunk（语义小节粒度，非固定页段）
  │     · 单 chunk 上限 384 token（约 200-256 字，为 BGE 512 token 上限留余量）
  │     · 章节超限时按 ### 三级标题或段落继续切分
  │     · 相邻 chunk 保留 1-2 句 overlap，避免语义断裂
  │
  ├─ 2. 表格 → 自然语言展开（规则转换，不调 LLM）
  │     · | 机油容量 | 5.25L |  →  "机油容量：5.25L"
  │     · | 最大净功率 | 11.8 Kw |  →  "最大净功率：11.8 Kw"
  │
  ├─ 3. 图片占位符 → 文字标注
  │     · ![](oil-level.png)  →  [示意图：机油尺刻度位置]
  │     · 标注由人工或后续阶段补充，当前用文件名作为占位
  │
  ├─ 4. 清洗 Markdown 标记（##、**、HTML 标签等）
  │
  └─ 5. 导出 chunks.jsonl
```

### 输出契约

`<package>/data/chunks.jsonl`，每行一个 JSON 对象：

```json
{
  "id": "春风 150AURA@seq_003",
  "content": "序列号\n车架号：XXXXXX\n发动机号：XXXXXX\n车辆铭牌位于车架管右侧。（第12-14页）",
  "page": "12-14",
  "section": "序列号",
  "token_count": 42
}
```

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | string | 唯一标识，格式 `<model>@seq_NNN` |
| `content` | string | 纯文本内容（已去 Markdown 标记、表格已展开、图片已替换） |
| `page` | string | 页码范围，如 `"12-14"`（1-based） |
| `section` | string | 所属 `##` 标题 |
| `token_count` | int | 中文字数（中文按单字、英文按空格分词） |

### CLI-to-MCP 映射

| MCP 工具 | CLI 后端 | 说明 |
|---|---|---|
| `export_chunks` | `scripts/pdf-export-chunks`（需新建） | 导出 chunks.jsonl |

### 前置条件

- [x] P3a 已完成（`read_page` + `search_pdf_content` 可用）
- [x] 有完整输出包样本：春风 150AURA（3212 行 Markdown，含 ## 标题和 HTML 表格）
- [x] 下游 chunk 规范已对齐（[motor-app §10](../../motorcycle-manual-app/ios-agent-方案设计.md#10-pc-端构建流程)）
- [x] `scripts/lib/chunk_utils.py` 新建
- [x] `scripts/pdf-export-chunks` 新建

### 实施步骤

1. **`scripts/lib/chunk_utils.py`**：实现 5 项预处理逻辑——标题切分 + token 上限裁剪（含 overlap）、表格展开、图片替换、Markdown 清洗。
2. **`scripts/pdf-export-chunks`**：读取合并 Markdown + `manifest.json`（取 model 名），调用 chunk_utils，输出 `data/chunks.jsonl`。
3. **MCP `export_chunks`**（可选）：在 `mcp/server/src/index.ts` 中注册，通过 `runScript` 调用 CLI。
4. **编译 + 工具列表验证**：确认 tools/list 返回 9 个工具（8 旧 + 1 新）。
5. **端到端验证**：用春风 150AURA 验证 chunk 切分粒度、表格展开质量、token 上限合规。
6. **更新文档**：同步 `mcp/README.md`。

### Step 0 证据

**P3a 完成证据**：
- 提交 `0fc6e19`：P3a 关键词检索 + 按页读取，8 个 MCP 工具。

**P3b 基线**：
- 合并 Markdown 结构已核实：春风 150AURA 含 ##/### 标题、HTML table、图片引用
- 下游规范已对齐：[motor-app §10 chunk 预处理](../../motorcycle-manual-app/ios-agent-方案设计.md#10-pc-端构建流程)
- 无需新增依赖（表格展开为纯规则，无 LLM 调用）

### 验证方式

```bash
# CLI 验证
scripts/pdf-export-chunks "pdf/春风 150AURA"

# 检查输出
python3 -c "
import json
with open('pdf/春风 150AURA/data/chunks.jsonl') as f:
    chunks = [json.loads(l) for l in f if l.strip()]
print(f'chunks: {len(chunks)}')
c = chunks[0]
print(f'fields: {sorted(c.keys())}')
print(f'id: {c[\"id\"]}')
print(f'page: {c[\"page\"]}')
print(f'section: {c[\"section\"]}')
print(f'token_count: {c[\"token_count\"]}')
print(f'content_preview: {c[\"content\"][:120]}')
# 验证无残留标记
import re
for c in chunks:
    assert '##' not in c['content'], f'{c[\"id\"]}: 残留 ##'
    assert '<td>' not in c['content'], f'{c[\"id\"]}: 残留 HTML'
    assert c['token_count'] <= 384, f'{c[\"id\"]}: token {c[\"token_count\"]} 超 384'
print('全部通过: 无残留 Markdown/HTML, token 上限合规')
"

# MCP 编译
cd mcp/server && npm run build

# 治理检查
python3 scripts/check_plan_governance.py .
```

### 完成条件

- [x] `data/chunks.jsonl` 产出，每行有效 JSON。→ 春风 150AURA：335 chunks。
- [x] 每个 chunk 含 5 个字段：`id`、`content`、`page`、`section`、`token_count`。→ 字段完整性验证通过。
- [x] `id` 格式为 `<model>@seq_NNN`。→ 正则验证通过。
- [x] `content` 无残留 Markdown 标记（`##`、`**`）和 HTML 标签（`<td>`、`<tr>`）。→ 0 残留。
- [x] HTML 表格数据已展开为自然语言键值对。→ 参数表"最大净功率 / 11.8 Kw / 8500 rpm"等已展开。
- [x] `token_count` ≤ 384。→ max=384，0 超限。
- [x] 超限章节已按 ### 或段落/句子/字符级再切分。→ 三级 fallback 切分逻辑已实现。
- [x] 相邻 chunk 有 1-2 句 overlap。→ OVERLAP_SENTENCES=2。
- [x] 非法输入返回明确错误。→ 不存在目录返回 error JSON。
- [x] TypeScript 编译通过。→ `tsc` 编译成功，9 个工具注册。
- [x] 治理检查通过。→ `python3 scripts/check_plan_governance.py .` 通过。

## P4-P5 后续阶段（粗粒度）

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
P1（收尾）→ P2（MCP 拆分）→ P3a（关键词+读页）→ P3b（向量化前置）→ P4（评测+多模态）
                                                           ↘ P5（远期）
```

P3b 不引入新依赖，只做数据准备。下游项目拿 `chunks.jsonl` 自行向量化。

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| P2 是否需要拆分 tools/ 目录 | 初期单文件实现，等工具数 ≥6 再拆分 | 否 | 已记录 |
| 向量索引选型（ChromaDB vs sqlite-vec） | P3b 已重定位为"向量化前置准备"，只产出 chunks.jsonl，不做索引。下游项目自行选型 | 否 | 设计决策：不在此项目做向量存储 |
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
