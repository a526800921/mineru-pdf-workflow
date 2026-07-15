# PDF 到入库前数据准备流程复盘与优化建议

日期：2026-07-15  
范围：`pdf2md` skill、`scripts/` 下的 PDF 处理脚本，以及本次春风 150 Aura 手册的完整协作流程。  
结论性质：复盘与拟议变更，尚未修改实现、skill 或已有 PDF 产物。

## 1. 结论先行

这次流程已经证明了“人只审批，LLM 负责执行、修复、配置和复核”的模式可行。实际工作中，用户主要做了三类事情：

- 确认 PDF 与 Markdown 的语义差异；
- 确认跨页表格、缺失内容等确实需要修复；
- 对少量无法仅凭结构判断的内容做最终裁决。

其余工作，包括定位文件、生成备份、修改 Markdown、生成 extraction overrides、重新抽取、修复候选、生成 ingest_ready.csv、检查冲突、审核剩余候选和导出 chunks，均由 LLM 完成。

因此，下一版流程不应继续把所有 `needs_review` 都交给用户。更合适的边界是：

> LLM 自动完成证据明确、规则可解释、来源稳定的审核；只有存在多种合理解释、表格语义仍不确定、来源冲突或身份不稳定时，才生成用户审核队列。

脚本仍然只负责确定性工作，不负责臆测业务语义。LLM 负责理解、决策、编排脚本和记录决策依据。

本次最值得优先修复的通用问题有五个：

1. `pdf-export-chunks` 没有使用 manifest 指定的主 Markdown，实际误读了 `toc.md`；
2. 冒号抽取器会把时间、URL、邮箱和说明性句子误识别为业务记录；
3. 双键值对表格需要临时动态脚本，缺少通用的配置表达；
4. `record_id` 不能稳定区分重复来源，导致审核覆盖可能误作用于多行；
5. 审核记录缺少 `LLM/用户`、决策依据和规则版本，无法完整审计协作过程。

## 2. 本次真实流程复盘

### 2.1 实际执行链路

本次处理的是春风 150 Aura 手册，流程大致如下：

```text
PDF
  ↓
MinerU / pdf-auto
  ↓
Markdown、页面片段、HTML 表格
  ↓
LLM 对照 PDF 逐页发现问题
  ↓
修 Markdown、配置 extraction_overrides、必要时编排动态辅助脚本
  ↓
重新抽取 quick_lookup_draft.csv
  ↓
LLM 逐批复核候选
  ↓
review_overrides.csv
  ↓
pdf-prepare-ingest
  ↓
ingest_ready.csv、conflicts.csv、ingest_manifest.json
  ↓
LLM 独立检查并清理异常
  ↓
pdf-export-chunks
  ↓
chunks.jsonl
```

本次没有执行数据库导入，流程停在入库前数据准备和向量化前置数据生成。

### 2.2 用户实际参与内容

用户参与的内容主要是语义确认，而不是脚本操作。例如：

- 确认 p14-p16、p75-p77、p137-p145、p187-p190 等是否属于同一张跨页表；
- 指出缺失的标题、警示表、字段和表格内容；
- 确认“磨合期内保养间隔”应跨四列，以及具体字段和值的对应关系；
- 确认 p189-p190 中 key 应取部件名称，而不是整行规格串；
- 最后授权 LLM 自行审核与参数无关的候选，以及剩余候选。

这说明用户最适合承担“事实裁决”和“边界确认”，不适合被要求逐条确认所有已经有明确证据的候选。

### 2.3 LLM 实际完成内容

LLM 完成了以下工作：

- 对照 PDF 和 Markdown 定位缺失、错位、跨页、列错配和多余占位页；
- 修改主 Markdown 和目录页；
- 生成并维护包级 `data/extraction_overrides.json`；
- 根据当前 PDF 的特殊结构编排临时动态脚本；
- 在运行变更前生成备份，并重新抽取候选；
- 逐批处理 `quick_lookup_draft.csv`；
- 处理 p189 双键值对表格；
- 修复 p116/p117 时间值中的冒号误切分；
- 将不属于业务记录的页脚、地址、联系方式、HTML 残片、分类行和脚注标记为跳过；
- 检查空 key、空 value、数字 key、冲突和证据缺失；
- 生成正确的 365 个向量化 chunks。

### 2.4 本次最终结果

本次真实包的最终状态如下：

| 项目 | 结果 |
|---|---:|
| `ingest_ready.csv` 总行数 | 386 |
| `ready / approved` | 353 |
| `skipped / rejected` | 33 |
| `not_ready` | 0 |
| 冲突记录 | 0 |
| 数字 key | 0 |
| 空 key/value/evidence | 0 |
| 主 Markdown 覆盖页码 | 1-191 |
| 正确 chunks | 365 |
| chunks 超过 384 token | 0 |

最终生成的 chunks 曾出现一次错误：标准命令选择了 `toc.md`，只得到 6 个目录 chunks。确认原因后，使用主 Markdown 重新生成，得到 365 个 chunks。这是一个通用脚本问题，不是本 PDF 的偶发问题。

## 3. 哪些地方已经做得比较好

### 3.1 主 Markdown 仍然是人工/LLM 可审的事实载体

没有把所有语义修复都塞进 Python。跨页表格、标题缺失、警示表、字段含义等先在 Markdown 层修正，便于 LLM 和用户直接对照 PDF 验收。这符合“产出正确 Markdown，再进入结构化数据准备”的目标。

### 3.2 包级配置优于 PDF 专用代码

`extraction_overrides.json` 用于描述表头、key 列、value 列和跨页表关系，比直接在通用脚本里写 p189、p190 或某个 PDF 页码更通用。当前方向是正确的，后续应继续扩展配置表达能力，而不是添加 PDF 名称或页码分支。

### 3.3 动态脚本确实降低了 LLM 的工作量

本次动态脚本解决了两个通用类型的问题：

- 一行中存在两个独立 key/value 对；
- key 中包含时间冒号，不能按第一个冒号简单切分。

这类脚本适合作为临时的、带备份和校验的辅助工具。它们不应沉淀为针对春风 150 Aura 的永久硬编码。

### 3.4 入库门禁和冲突检查仍然保守

当前 `pdf-prepare-ingest` 对空字段、未审核、冲突和证据缺失保持保守，能够阻止明显不完整的数据进入 `ready`。这个安全边界应该保留，只需要调整“谁可以完成审核”的策略。

## 4. 当前 skill 和 Python 的主要问题

## 4.1 skill 的审核边界过于保守

当前 skill、相关计划和 ADR 的共同假设是：`needs_review` 不能由 LLM 自动处理，用户需要确认候选状态。

这与本次实际协作方式已经不一致。用户明确授权后，LLM 已经能够独立完成大量候选审核，而且最终检查没有发现冲突、空字段或数字 key。

建议把边界改成“LLM 默认审核，用户审核例外”：

- LLM 可以批准证据明确且来源稳定的业务记录；
- LLM 可以拒绝明确的非业务记录或抽取残片；
- LLM 不得批准存在语义歧义、来源冲突、证据缺失或身份不稳定的候选；
- 用户只接收 `escalation_queue`，而不是接收全部 `needs_review`。

这不是放宽数据质量门禁。`ready` 仍然必须满足字段完整、证据存在、无冲突、来源可追溯等条件；变化只是将“明确候选的审核动作”从用户转移给 LLM。

## 4.2 `pdf-export-chunks` 选择 Markdown 的方式不可靠

`scripts/lib/chunk_utils.py` 当前遍历目录并选择第一个非 `review.md` 的 Markdown。一个标准包中同时存在：

- `toc.md`；
- 主 Markdown；
- 可能还有 review 或辅助 Markdown。

因此它实际选择了 `toc.md`，导致只生成 6 个 chunks。`pdf-extract-data` 已经使用 manifest 中的 `files.manual`，chunks 导出也应使用同一事实源。

建议：

1. 优先读取 `manifest.files.manual`；
2. 校验该文件位于包内且不是 `toc.md`、`review.md`；
3. 只有在旧包没有 manifest 路径时，才允许回退；
4. 回退时若存在多个候选 Markdown，应直接报错并要求 LLM 选择；
5. 增加同时含 `toc.md` 和主 Markdown 的回归测试；
6. 增加页码覆盖和“不得只包含目录标题”的输出校验。

## 4.3 冒号解析器产生了可避免的假候选

当前 `extract_colon_rows` 对冒号进行过于机械的切分。本次出现了以下类型：

- `16:32`、`06:32` 被拆成错误的 key/value；
- `容量为:10 Ah` 被识别为疑似业务记录，但实际是说明性句子；
- URL、邮箱等页脚内容被部分识别；
- `“/”：表示非标准件` 被生成了无业务意义的 key；
- 企业地址、电话、邮箱等页脚元数据进入候选。

建议新增通用的 `needs_review_reason` 或 `classification_reason`，至少区分：

- `colon_ambiguous`：冒号可能属于时间、URL、邮箱或句内标点；
- `non_business_footer`：页脚、联系方式、企业信息；
- `non_business_footnote`：脚注标记或符号解释；
- `sentence_fragment`：说明句而不是 key/value 记录；
- `missing_evidence`：无法保留完整原文证据。

处理原则应是“先保留证据，再降低自动批准资格”：

- 明确不属于业务记录的内容可以由 LLM 自动拒绝；
- 无法判断是否为业务记录的内容进入用户升级队列；
- 不能因为解析器看到了冒号就直接当作业务候选；
- 时间、URL、邮箱和句内冒号不应通过 PDF 页码硬编码排除。

## 4.4 双 key/value 对表格缺少通用配置

本次 p189 的一行包含两组独立的 key/value，临时脚本将其拆成独立候选。当前抽取器主要支持一行一个 key 和多个 value 列，不支持一行多个 pair group。

建议增加配置能力，例如：

```json
{
  "html_table:117": {
    "header_rows": 1,
    "pair_groups": [
      {"key_column": 0, "value_columns": [1]},
      {"key_column": 2, "value_columns": [3]}
    ]
  }
}
```

输出时应增加稳定的 `pair_index` 或 `subrow_index`，保证每个拆出的候选仍能追溯到原始表格、原始行和原始列。

这样可以保留 LLM 动态判断和配置能力，同时减少每个 PDF 都重新编写一次临时脚本的需要。

## 4.5 `record_id` 不能充分表达候选身份

本次最终检查仍发现 5 个重复 `record_id`。原因是当前 `record_id` 主要由内容字段和来源行哈希组成，同样内容出现在不同位置时可能得到相同 ID。

这会带来两个风险：

- 审核覆盖表按 `record_id` 应用时，可能同时影响多个来源不同的候选；
- 修改抽取配置或动态拆分后，key/value 改变会导致新的 `record_id`，原有审核无法稳定绑定。

建议保留现有 `record_id` 的兼容语义，同时增加独立的候选身份：

```text
candidate_id = source_pdf_hash + source_block_id + table_id + row_index + pair_index + page
```

具体字段不必固定为上述字符串，但必须满足：

- 同一来源位置的候选在重新抽取后尽量稳定；
- 同一内容出现在不同位置时可以区分；
- 能回到 Markdown、HTML 表格或 PDF 页码；
- 动态拆分后的子候选有独立身份。

`review_overrides` 应优先按 `candidate_id` 应用，旧的 `record_id` 只能作为兼容回退，并在存在重复时拒绝静默批量应用，改为进入升级队列。

## 4.6 审核记录缺少 LLM/用户和决策依据

当前 `review_overrides.csv` 只有：

```text
record_id,review_status,notes
```

这足以驱动当前脚本，但不足以审计“为什么这个候选可以由 LLM 自动批准”。本次 notes 中已经出现了“用户确认”和“LLM 独立复核”两种不同来源，说明元数据需要结构化。

建议增加以下信息：

- `candidate_id`；
- `review_actor`：`llm` 或 `user`；
- `decision_basis`：`evidence_exact`、`rule_based_non_business`、`user_confirmed`、`ambiguous` 等；
- `review_rule_version`；
- `source_hash` 或 `candidate_hash`；
- `reason`；
- `reviewed_at`。

可以先保留现有 CSV 作为脚本兼容接口，再增加 `review_decisions.jsonl` 作为完整审计记录，由 LLM 生成 CSV 投影。这样不会把富结构审计字段硬塞入旧接口，也便于未来回放和复核。

## 4.7 动态辅助脚本的实际使用没有完全走标准入口

本次确实做了备份，也使用了临时脚本，但部分动态脚本是在 `/tmp` 中直接运行的，没有统一经过 `pdf-run-helper` 的备份、hash、dry-run 和结果校验入口。

这没有影响本次结果，但流程上存在不一致。后续应让 LLM 编排动态脚本时自动完成：

1. 记录输入文件和 hash；
2. 生成备份；
3. 先 dry-run 或输出 diff；
4. 只允许修改明确的候选层文件或包级配置；
5. 执行结构校验；
6. 失败时回滚；
7. 记录脚本路径、命令、输入输出和原因。

动态脚本应默认是一次性辅助工具，不应自动沉淀为通用脚本；只有同类问题在多个 PDF 中重复出现，并且能够抽象为稳定契约时，才升级为正式能力。

## 5. 建议的目标工作流

### 5.1 目标流程

```text
1. LLM 启动 pdf2md
2. 检查 manifest、主 Markdown、toc、页面片段
3. LLM 对照 PDF 做结构修复
4. 需要时生成 extraction_overrides 或动态辅助脚本
5. 备份、执行、校验并重新抽取
6. LLM 自动审核候选
7. 只把 escalation_queue 交给用户
8. 用户确认歧义项
9. 合并 LLM 决策和用户决策
10. 生成 ingest_ready.csv
11. 自动检查门禁、冲突、重复身份、证据和字段完整性
12. 生成 chunks.jsonl
13. 停在入库前，不自动导入数据库
```

### 5.2 LLM 可以自动批准的候选

满足以下条件时，LLM 可以自动标记为 approved：

- key、value 与完整证据文本一致；
- 来源页码、表格、行号或段落定位明确；
- 没有冲突候选；
- 没有未解决的跨页或列语义问题；
- key 不是纯数字、页码、单位、符号或分类标题；
- value 不是空值，且没有明显错列；
- 当前候选不是时间、URL、邮箱或说明性句子的冒号残片；
- candidate identity 唯一且稳定；
- 抽取规则属于已知、可解释的规则。

例如本次 p82 的非参数操作说明、已经对齐证据的保养字段、p189-p190 已明确列义的扭矩记录，都可以由 LLM 自动完成审核，并留下 `evidence_exact` 或相应的规则依据。

### 5.3 LLM 可以自动拒绝的候选

满足以下条件时，LLM 可以自动标记为 rejected/skipped：

- 明确是页脚、地址、电话、邮箱或企业元数据；
- 明确是表格分类行、表头、脚注符号解释或 HTML 残片；
- key 只有页码、单位、数字或无业务含义的标记；
- 证据明确表明该行不是可入库的业务记录。

自动拒绝也必须保留证据和理由，不能直接删除候选。

### 5.4 必须交给用户的情况

以下情况不应由 LLM 静默决定：

- 两种以上 key/value 解释都合理；
- 跨页表格是否连续仍无法确认；
- `rowspan`、`colspan` 或合并单元格的语义无法从 PDF 和 Markdown 确定；
- 同一候选有不同值，且无法判断哪个版本正确；
- 证据不完整或 PDF 与 Markdown 不一致；
- 同一 `record_id` 对应多个来源且无法用 candidate identity 区分；
- 涉及关键参数、型号、容量、扭矩等高风险数据，且列义不确定；
- 动态变换会改变原始业务语义，而不是只修复结构表达。

用户看到的应是一个短的升级清单，每条包含：候选内容、PDF 页码、证据、冲突/歧义原因、LLM 的两个或多个候选解释，以及建议选项。

## 6. 对 skill 的调整建议

以下是建议修改方向，不在本次复盘中直接执行：

### 6.1 把人工确认边界改为升级边界

当前“所有待审核项都需要用户确认”应改为：

- 默认由 LLM 进行候选审查；
- LLM 可自动批准明确候选、自动拒绝明确非业务候选；
- 只有 `escalation_queue` 需要用户确认；
- 用户可以通过会话显式切换为“全部需要人工确认”模式。

### 6.2 明确 LLM 审核必须输出审计信息

skill 中应要求每次 LLM 决策记录：

- 候选身份；
- 决策状态；
- 决策依据；
- 证据定位；
- 使用的规则版本；
- 是否需要用户升级。

### 6.3 增加“候选审核报告”作为标准中间产物

建议增加：

```text
data/review_decisions.jsonl
data/escalation_queue.jsonl
```

其中：

- `review_decisions.jsonl` 保存全部 LLM 和用户决定；
- `escalation_queue.jsonl` 只保存尚未解决的歧义项；
- `review_overrides.csv` 继续作为 `pdf-prepare-ingest` 的兼容输入，或由前者生成。

### 6.4 把动态脚本定位为 LLM 的受控工具

skill 应明确：

- LLM 可以动态生成辅助脚本；
- 运行前必须备份和记录 hash；
- 脚本只处理结构性转换，不自行决定业务含义；
- 运行后必须校验 row count、字段、来源和 hash；
- 失败自动回滚；
- 一次性脚本默认不进入 `scripts/` 正式目录。

### 6.5 明确 chunks 的输入事实源

skill 应规定 chunks 始终从 manifest 的 `files.manual` 读取主 Markdown，并禁止把 `toc.md`、`review.md` 或临时报告当作主文档。若 manifest 缺失或有多个候选，应停止并要求 LLM 处理，而不是静默猜测。

## 7. 对 Python 和脚本的调整建议

### P0：必须优先修复

1. 修复 `chunk_utils` 的主 Markdown 选择逻辑，并增加 `toc.md + 主 Markdown` 回归测试；
2. 增加稳定 `candidate_id`，解决重复 `record_id` 和审核覆盖误绑定；
3. 增加审核决策元数据，至少区分 LLM 决策和用户决策；
4. 将 `needs_review` 从单一状态改为带原因的升级队列。

### P1：提升通用抽取质量

1. 冒号解析增加时间、URL、邮箱、脚注和说明句识别；
2. 增加 `pair_groups` 配置，支持一行多组 key/value；
3. 为动态拆分增加 `pair_index` 或 `subrow_index` 来源信息；
4. 对重复候选进行自动诊断，不能静默按 `record_id` 批量应用 override；
5. 增加抽取后自动报告：空字段、数字 key、低置信度、重复身份、未覆盖页码、冲突和待升级原因。

### P2：提升协作体验

1. 增加一个统一的 LLM 编排入口，串起备份、脚本、抽取、审核和校验；
2. 让 LLM 只需读取短报告和升级队列，不需要手工扫描几百行 CSV；
3. 让每次重跑都能根据 source hash 检查旧决策是否仍然有效；
4. 为每个 PDF 包生成 `run_manifest`，记录命令、版本、输入输出和验证结果；
5. 把本次暴露出的测试样例加入通用 fixture，而不是加入 Aura 专用分支。

## 8. 不建议做的调整

以下方向会损害通用性或人/LLM 协作边界，不建议采用：

- 在脚本中写死“春风 150 Aura”或固定页码；
- 用模型名称、PDF 文件名或品牌名判断表格语义；
- 让 Python 根据模糊文本自动猜 key/value；
- 通过一个“全部 approve”开关绕过升级队列；
- 为了少显示问题而删除低置信度候选或证据；
- 让动态脚本直接修改 `ingest_ready.csv`、`conflicts.csv` 或最终入库批次；
- 为当前流程引入 MCP Server。现有 CLI 边界已经足够，主要问题是编排和审核契约，而不是缺少服务协议。

## 9. 建议的实施顺序

本报告不直接改变计划状态。若用户确认进入实施，建议另行建立或修订专项计划，并按以下顺序推进：

### 阶段 0：冻结本次基线

以本次 Aura 包作为回归基线，保留：

- 386 条候选；
- 353 条 ready；
- 33 条 skipped；
- 0 冲突；
- 365 个 chunks；
- 主 Markdown 191 页覆盖；
- p116/p117、p189/p190 等已确认修复。

### 阶段 1：审核契约和升级队列

先定义 `review_decisions`、`escalation_queue`、`candidate_id` 和兼容的 `review_overrides` 关系，再改 skill 和 `pdf-prepare-ingest`。

完成条件：LLM 能自动处理明确候选，用户只看到升级项；所有决策可追溯到来源和规则版本。

### 阶段 2：候选身份和兼容迁移

解决重复 `record_id`、重抽取后 override 失效以及同 ID 多来源的问题。

完成条件：同一来源候选可稳定重放，不同来源候选不会被同一个 override 误批量修改。

### 阶段 3：通用抽取能力

实现冒号歧义分类、`pair_groups`、子行来源和结构化 `needs_review_reason`。

完成条件：本次时间冒号和双 key/value 对问题可以由通用规则/配置处理，不需要 Aura 专用临时脚本。

### 阶段 4：chunks 和端到端回归

修复 canonical Markdown 选择，补充包级回归 fixture，并跑完整流程。

完成条件：不会再次误读 `toc.md`，chunks 覆盖主 Markdown 全部页码，字段和 token 门禁通过。

### 阶段 5：真实包验收

在 Aura 包上重新运行并对比阶段 0 基线，再使用一个结构不同的手册验证通用性。

完成条件：第二个 PDF 不需要新增品牌、文件名或页码硬编码；用户只需处理真实歧义项。

## 10. 最终判断

这个 `pdf2md` 流程不需要推倒重来。核心架构是对的：

- Markdown 负责可读、可对照的修复结果；
- 包级 JSON 负责文档特定的结构配置；
- Python 负责确定性抽取、校验和门禁；
- LLM 负责理解、编排和候选审核；
- 用户负责少量不可分辨事实的最终确认。

真正需要调整的是审核策略、候选身份、审计信息和两个通用抽取/导出缺陷。调整后，用户不需要再逐页或逐条审 `ingest_ready.csv`；LLM 应先完成全量筛查，只把“它确实无法从证据中确定”的内容交给用户。

本报告完成后，若进入实施，应先把上述目标写入正式专项计划，并同步 `docs/PLAN_MAP.md`、`skills/pdf2md/SKILL.md`、相关 ADR/迁移说明，再开始代码修改和独立验收。
