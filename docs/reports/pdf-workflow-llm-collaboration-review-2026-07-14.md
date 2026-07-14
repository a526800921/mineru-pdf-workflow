# PDF → MinerU → 修复 → 入库前准备：本次会话复盘与 LLM 协作方案

日期：2026-07-14

## 一、结论先行

这次会话的实际协作模式已经比较明确：

- 用户不需要学习或执行脚本。
- 用户主要负责查看 PDF/Markdown 后确认事实、确认表格关系、批准或拒绝候选数据。
- LLM 负责定位问题、选择处理路径、调用脚本、修改包内配置、重新生成产物、运行校验并记录治理证据。
- 脚本负责确定性工作：解析、合并、校验、按页应用修复、抽取、审核状态计算和批次导出。
- PDF 特有的列语义、跨页关系、目录归属和最终数据是否正确，不能由脚本自行猜测，必须由 LLM 辅助用户完成确认。

因此，最合适的架构不是让用户操作更多 CLI，也不是继续增加自动修复逻辑，而是：

> 一个面向用户的 `pdf2md` 总 skill + 一组由 LLM 按需调用的确定性脚本 + 用户在关键节点进行审批。

现有 `pdf2md-fix` skill 可以并入 `pdf2md`，但应采用“统一入口、分阶段章节、旧 skill 兼容重定向”的迁移方式，而不是简单复制粘贴两份内容。

## 二、本次会话中用户和 LLM 实际分别做了什么

### 2.1 用户完成的工作

用户没有执行脚本，主要完成了以下几类人工工作：

1. 确认 PDF 与 Markdown 的对应关系。
   - 确认 p85–p94 属于保养类跨页表格。
   - 确认 p132–p133 是同一个跨页表格。
   - 确认部分页面的原始 PDF 内容确实应该补回 Markdown。

2. 提供语义判断。
   - 确认“磨合期内保养间隔”跨 4 列，备注与小时、月份、km 位于同一行。
   - 确认目录内容存在明显错误，需要进入修复流程。
   - 确认数字图示编号不能作为业务 `key`。

3. 批准修复和数据状态。
   - 批准补回 p85–p94、p132–p133 的内容。
   - 确认剩余候选没有问题，将 104 条 `not_ready` 记录批准为 `approved`。

这些判断是不可由通用脚本安全推断的事实，应该被记录为人工确认或用户审批，而不是隐藏在代码分支里。

### 2.2 LLM 完成的工作

LLM 承担了几乎全部机械和协调工作：

- 查找输出包、页面锚点、segments、manifest 和现有计划。
- 对比 PDF、canonical Markdown 和单页分段，定位空页根因。
- 发现旧版合并级 TOC 修复曾覆盖 p2–p137 中间正文。
- 修正 TOC 修复逻辑并从 138 个非空分段重建 canonical Markdown。
- 恢复并登记 p85–p94、p132–p133 的人工确认内容。
- 为非空页增加基于正文 hash 的通用整页替换能力。
- 重建 `manual_fixes.jsonl`、`extraction_overrides.json` 和 `review_overrides.csv`。
- 重跑结构化抽取、冲突检测、审核状态计算和入库前批次导出。
- 发现数字图示编号被抽取为 `key` 后，增加包级 `policies.numeric_key=skip` 配置。
- 运行 `pdf-check-fixes`、pytest、shell 回归和治理检查。
- 将结果同步回计划、路线图和 skill 文档。

### 2.3 本次最终产物状态

当前 `pdf/春风250Sr` 已达到入库前交付状态：

| 产物/指标 | 当前结果 |
|---|---|
| canonical Markdown | 138/138 页有正文，空页占位为 0 |
| TOC | 120/120 条目，`toc.md` 与 `toc_tree.json` 同步 |
| 结构化候选 | 182 条，纯数字 `key` 为 0 |
| 审核状态 | 179 条 `approved`，3 条联系方式 `rejected` |
| 入库准备 | 179 条 `ready`，0 条 `not_ready`，3 条 `skipped` |
| 冲突 | 0 组 |
| 入库前批次 | `ingest_batch.jsonl` 179 条 |
| 数据库导入 | 未执行，仍在项目边界之外 |

## 三、从 PDF 到入库前数据准备的完整流程

### 3.1 流程总览

```text
PDF
  ↓
MinerU / ModelPad PDF 服务
  ↓
pdf-seg：按页生成 segments
  ↓
pdf-auto：验证、fallback、合并、TOC、表格格式化、review.md
  ↓
LLM 读取 review.md / manifest / 页面 / segments
  ↓
pdf2md 人工协作阶段
  ├─ 目录问题确认
  ├─ 空页和表格异常确认
  ├─ 跨页表格关系确认
  ├─ 字段和列语义配置
  └─ 用户批准/拒绝修复
  ↓
manual_fixes.jsonl + extraction_overrides.json + manifest
  ↓
pdf-extract-data：生成结构化候选
  ↓
LLM 展示候选，用户审批
  ↓
review_overrides.csv
  ↓
pdf-prepare-ingest：计算 ready/not_ready/skipped/conflicts
  ↓
pdf-export-ingest：生成入库前 JSONL 批次和 manifest
  ↓
交给外部入库系统（不在本项目内执行）
```

### 3.2 阶段职责

| 阶段 | 主要职责 | 谁决定 | 主要产物 |
|---|---|---|---|
| PDF 服务 | 调用 MinerU 解析 PDF | 脚本/ModelPad | MinerU 原始解析结果 |
| 分页解析 | 生成单页或单段 Markdown | 脚本 | `segments/` |
| 自动管线 | 验证、fallback、合并、TOC、pretty-print | 脚本执行，LLM 解释结果 | canonical `.md`、`review.md`、TOC、manifest |
| 异常审计 | 找空 `td`、异常列、字段遗漏、目录异常 | 脚本扫描，LLM 排序 | `table_candidates.jsonl`、`review.md` |
| 内容修复 | 恢复缺失文字、表格、跨页关系 | 用户确认，LLM 组织修复 | `manual_fixes.jsonl`、canonical Markdown |
| 结构化抽取 | 从 HTML/Markdown 表格生成候选 | LLM 提供配置，脚本执行 | `quick_lookup_draft.csv` |
| 入库准备 | 应用用户审核状态、检查冲突和页码门禁 | 用户审批，脚本计算 | `ingest_ready.csv`、`conflicts.csv` |
| 入库前导出 | 生成可移交批次 | 脚本 | `ingest_batch.jsonl`、`ingest_manifest.json` |
| 数据库导入 | 外部系统消费批次 | 不属于本项目 | 不在本项目内 |

## 四、哪些脚本应作为 LLM 的辅助工具

### 4.1 应由 LLM 直接编排的脚本

这些脚本有明确输入、输出和失败门禁，适合由 `pdf2md` skill 根据当前状态自动选择调用。用户不需要直接接触它们。

| 脚本 | LLM 使用方式 | 用户看到的结果 |
|---|---|---|
| `scripts/pdf-auto` | 首次解析或完整重建时调用 | “解析完成，发现哪些页需要确认” |
| `scripts/pdf-table-fix` | 扫描表格异常和缺失字段 | 候选问题清单，不直接改正文 |
| `scripts/pdf-read-page` | 读取指定页或页段 | LLM 将 PDF、Markdown 和原文证据整理成对照项 |
| `scripts/pdf-search-content` | 检索关键词、字段和章节 | 快速定位异常来源 |
| `scripts/pdf-apply-fixes` | 应用用户确认后的 `manual_fixes` | 更新 canonical Markdown 并同步 manifest |
| `scripts/pdf-check-fixes` | 每个修复阶段后的门禁检查 | 告诉用户修复是否安全、是否有漂移 |
| `scripts/pdf-extract-data` | 读取包内 JSON 配置生成候选 | 输出结构化草案供 LLM 展示和解释 |
| `scripts/pdf-prepare-ingest` | 应用审核覆盖、计算状态和冲突 | 输出哪些数据可以进入 ready |
| `scripts/pdf-export-ingest` | 审核通过后生成批次 | 生成可交给下游的 JSONL 和 manifest |
| `scripts/pdf-eval-vlm` | 只在图像、扫描页或视觉证据不足时调用 | 提供辅助证据，不能代替用户审批 |

### 4.2 应保留为内部执行层的脚本

这些脚本仍然重要，但不应作为用户面对的主要入口：

- `scripts/pdf-seg`：解析初始化和分段细节由 LLM 根据输入包自动处理。
- `scripts/pdf-merge`：合并和格式化属于 `pdf-auto` 的内部阶段；只有重建或诊断时由 LLM 单独调用。
- `scripts/pdf-rerun`、`scripts/pdf-validate`：作为自动流程内部或异常回退工具。
- `scripts/lib/toc_repair.py`：库级实现，不直接暴露给用户。
- `scripts/pdf-export-chunks`：只有用户明确需要向量化前置数据时才调用。

### 4.3 不建议继续增加的方向

- 不要再增加“自动猜测某页缺失字段应该放哪一列”的脚本逻辑。
- 不要把某个车型、页码或表格的业务语义写死进通用脚本。
- 不要让脚本自行把 `needs_review` 批量改成 `approved`。
- 不要让 VLM 直接决定 rowspan/colspan、跨页关系或最终字段事实。
- 不要把用户需要做的判断拆成大量命令行参数。

## 五、`pdf2md-fix` 是否应该并入 `pdf2md`

### 5.1 结论：应该并入，但保留兼容入口

当前两个 skill 的边界在实现上是合理的，但在用户体验上是重复的：

- `pdf2md` 负责解析、输出包和结构化数据。
- `pdf2md-fix` 负责解析后的人工修复和下游准备。
- 用户实际只需要说“帮我处理这个 PDF”，并不会主动选择两个 skill。

因此建议：

> 将 `pdf2md-fix` 的操作流程并入 `pdf2md`，把 `pdf2md-fix` 改成兼容重定向 skill，而不是继续作为用户需要理解的第二入口。

### 5.2 合并后的 `pdf2md` 建议结构

```text
pdf2md
├─ 1. 解析前检查
├─ 2. MinerU / pdf-auto 自动解析
├─ 3. review.md 和候选问题归类
├─ 4. LLM 协助人工复核
│  ├─ TOC
│  ├─ 空页/缺失文字
│  ├─ 8192 td/异常列
│  ├─ 跨页表格
│  ├─ 字段和列语义
│  └─ VLM 辅助证据
├─ 5. 应用 manual_fixes 和 manifest 门禁
├─ 6. 生成结构化候选
├─ 7. 用户审批 review_overrides
├─ 8. 生成 ingest_ready 和冲突报告
└─ 9. 可选生成入库前 JSONL 批次
```

### 5.3 不应简单合并的内容

合并 skill 时应避免以下问题：

- 不把 `pdf2md-fix` 的字段 Schema 再复制一份到 `pdf2md`；Schema 继续以治理计划为事实源。
- 不把人工修复说明和自动解析说明混成一个无阶段边界的长清单。
- 不把 VLM 变成主解析阶段的默认依赖。
- 不把“用户已确认”误写成“脚本自动修复成功”。
- 不删除 `pdf2md-fix` 的历史计划和兼容说明，避免旧会话或旧引用失效。

## 六、建议的最终人机协作交互

用户未来只需要看到类似下面的几个节点：

### 节点 A：解析完成

LLM 汇报：

- PDF 是否解析完成。
- 哪些页是正常结果。
- 哪些页需要人工确认。
- 是否发现目录、空页、异常表格或字段遗漏。

用户只需要确认是否进入复核。

### 节点 B：异常复核

LLM 按问题类型展示对照项：

```text
问题：p86–p94 是否为同一类跨页保养表？
PDF 证据：……
当前 Markdown：……
建议修复：……
需要确认：表头、项目列、备注跨行关系
```

用户确认“是/否/按哪种解释”，LLM 负责生成 `manual_fixes.jsonl` 和配置。

### 节点 C：结构化候选审核

LLM 不要求用户看 CSV 原始格式，而是按业务语义展示：

```text
页码：86
项目：机油和机油滤清器
间隔：小时=-；月份=-；km=1000；备注=更换
证据：……
建议状态：approved
```

用户可以说“这些都确认”或指出某几条例外，LLM 负责更新 `review_overrides.csv` 并重跑门禁。

### 节点 D：交付前确认

LLM 汇报：

- ready 数量。
- not_ready 数量。
- rejected/skipped 数量。
- 冲突数量。
- 产物路径和 manifest hash。
- 是否只生成入库前批次，还是交给外部入库流程。

用户不需要执行任何命令。

## 七、建议的脚本分层

为了支持上述交互，脚本可以按三层理解：

### A 层：确定性核心

负责读写、校验、hash、状态计算和回滚。不得包含 PDF 特定业务语义。

### B 层：LLM 辅助工具

负责扫描、按页读取、搜索、候选生成、抽取和报告生成。LLM 根据结果决定下一步，不把候选直接当事实。

### C 层：用户事实输入

通过以下文件留痕：

- `manual_fixes.jsonl`：Markdown、表格、目录和字段修复事实。
- `extraction_overrides.json`：表格列语义和包级抽取策略。
- `review_overrides.csv`：结构化候选的人工审核状态。

这三类文件分别承担不同职责，不应合并成一个大而模糊的配置文件。

## 八、建议的后续迁移步骤

本报告只记录方案，未在本次会话直接迁移 skill。后续如实施，建议按以下顺序：

1. 在 `skills/pdf2md/SKILL.md` 增加“解析后人工协作与入库前准备”主章节，吸收 `pdf2md-fix` 的流程性内容。
2. 保留 `skills/pdf2md-fix/SKILL.md`，改为短兼容说明：触发后跳转到 `pdf2md` 的对应章节，并标注未来废弃窗口。
3. 同步更新 `/Users/jafish/.claude/skills/pdf2md/SKILL.md` 和 `/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md`。
4. 更新 `docs/plans/pdf2md-fix-manual-workflow.md` 和 `docs/PLAN_MAP.md`，将关系记录为“`pdf2md-fix` 已合并到 `pdf2md`，兼容入口保留”。
5. 增加一条端到端验收：用户只提供 PDF 和确认意见，LLM 完成 `pdf-auto → 人工修复 → 抽取 → 审核 → 入库前批次`，用户不执行脚本。
6. 验证旧 `pdf2md-fix` 触发词仍能正确进入统一流程，避免已有使用习惯失效。
7. 在兼容窗口结束后，再决定是否将 `pdf2md-fix` 状态改为 `已合并` 或 `已废弃`；不要在没有迁移验证前直接删除。

## 九、最终判断

本次会话已经证明当前系统最有价值的形态是：

- MinerU 和脚本负责把 PDF 变成可追溯的候选事实。
- LLM 负责理解异常、串联工具和维护配置。
- 用户只负责确认 PDF 中的真实语义以及结构化数据是否可接受。
- `pdf2md` 应成为整个流程的统一入口。
- `pdf2md-fix` 的能力应合并进 `pdf2md` 的“人工协作阶段”，但保留短期兼容入口和独立治理历史。

这样既保留了脚本的确定性和可审计性，也符合实际使用方式：用户不需要成为脚本操作者，只需要成为最终事实和数据的审批者。

## 十、动态辅助脚本与当前入口决策

### 10.1 动态脚本应该存在，但必须受控

当现有脚本不满足一个明确的 PDF 特定操作时，LLM 可以自己编排一个临时辅助脚本。这不是让 LLM 随意修改项目代码，而是提供一个受控的第三层能力：

```text
现有 CLI
  ↓ 不足
LLM 组合多个 CLI
  ↓ 仍不足
临时/包级动态辅助脚本
  ↓ 问题重复出现
补回通用脚本 + 回归测试
```

动态脚本运行前必须：

- 备份 Markdown、manifest、相关 JSON/CSV 和修复记录；
- 记录备份 hash；
- 先 dry-run 并展示变更摘要；
- 限定页锚点、record_id 或文件范围；
- 运行后执行一致性校验和幂等检查；
- 失败时整组回滚；
- 默认放在临时目录，不直接污染 `scripts/`。

只有当同类问题在多个 PDF 中重复出现时，才将动态脚本晋升为通用脚本，并补充影响分析、测试和治理证据。

### 10.2 当前继续使用 skill，不引入 MCP

当前推荐入口保持为：

```text
用户 → pdf2md skill → LLM 编排 CLI/动态辅助脚本 → 用户审批 → 入库前产物
```

目前没有引入 MCP 的必要，原因是：

- LLM 与脚本在同一工作区，已经可以直接调用 CLI；
- 当前核心难点是 PDF 事实确认，不是工具发现；
- MCP 会增加协议、服务进程、参数映射和兼容层维护；
- 项目已有 CLI-only 架构决策，且本次会话已验证该方式可完成全流程。

只有未来需要跨机器远程调用、任务队列、多客户端发现、权限隔离或异步服务契约时，才重新评估 MCP 或其他服务接口。

该决策已记录在 [ADR 0003：LLM 编排与受控动态辅助脚本](../adr/0003-llm-orchestrated-dynamic-assistants.md)。

本复盘对应的实施路线见 [LLM/人工协作入口迁移计划](../plans/llm-human-collaboration-migration.md)。
