# 计划：LLM/人工协作入口迁移

## 计划状态

- 状态：设计中
- 当前阶段：阶段 0：协作契约与基线冻结
- 最后更新：2026-07-14

本文档是 `llm-human-collaboration-migration` 的实施细节事实源。计划状态、依赖、推荐顺序、阻塞项和证据入口以 [PLAN_MAP](../PLAN_MAP.md) 为准。本计划承接已完成的 [cli-only-migration](cli-only-migration.md)，不重新打开其 CLI-only 结论。

## 背景

本次 `春风250Sr` 实际协作已经验证了目标使用方式：用户主要确认 PDF 中的事实、表格关系和结构化候选是否正确；LLM 负责读取产物、分析异常、编排现有 CLI、生成或更新包内配置、在必要时创建一次性辅助脚本、重新执行验证并维护最终产物。

当前系统仍存在入口和职责不一致：

- `pdf2md` 与 `pdf2md-fix` 是两个独立 skill，用户需要知道何时切换入口；
- 现有脚本已经覆盖大多数确定性操作，但遇到单个 PDF 的特殊异常时，缺少“由 LLM 生成受控临时辅助脚本”的正式流程；
- 动态脚本、人工确认、配置更新、回滚和结果验证尚未形成一个统一的迁移契约；
- 当前项目已经完成 CLI-only 迁移，不提供 MCP Server，因此本计划不重新引入 MCP 工具兼容层。

本计划把“PDF 到入库前数据准备”收敛为一个由 `pdf2md` skill 编排的协作流程，而不是把所有判断继续堆进通用自动修复代码。

## 目标

- 让 `pdf2md` 成为用户面对的唯一主入口，覆盖解析后的复核、修复、结构化抽取、人工审核和入库前导出。
- 明确用户只负责 PDF 事实确认和审批；LLM 负责诊断、编排、配置维护、脚本调用、验证和文档留痕。
- 保留 `scripts/` 作为确定性执行层，不把 PDF 特定业务语义硬编码进通用脚本。
- 建立动态辅助脚本的安全契约：备份、dry-run、作用域、hash、幂等、原子回滚和晋升规则。
- 将 `pdf2md-fix` 的流程能力迁移到 `pdf2md`，并在迁移窗口内保留兼容入口，避免已有触发方式失效。
- 保留 `manual_fixes.jsonl`、`extraction_overrides.json`、`review_overrides.csv` 三类产物的职责分离，使人工校对期间 Markdown、配置和审核状态能够同步推进。
- 保持最终边界为入库前数据准备，不执行数据库导入。
- 以真实 PDF 验收“用户不执行脚本，LLM 完成全流程”的协作闭环。

## 非目标

- 不自动批准 `needs_review`、`approved`、`ready` 或任何业务事实；用户确认仍是放行条件。
- 不删除已有确定性 CLI；脚本只在无必要时被动态辅助脚本替代，重复出现的问题仍按晋升规则进入通用实现。
- 不把单个 PDF 的页码、表头、业务字段或修复模板写死到通用脚本中；这类信息进入输出包配置或 LLM 生成的修复记录。
- 不修改原始 PDF、原始 `segments/`、`content_list*.json` 等证据源。
- 不在本计划中新增 MCP Server、MCP 兼容层、远程队列或数据库导入服务。
- 不在本计划中重做 MinerU 解析、ModelPad 生命周期或已完成的表格修复计划；只定义它们如何被统一入口编排。
- 不因入口合并而抹去 `pdf2md-fix` 的历史治理记录；兼容 skill 的删除必须在独立验收后进行。

## 协作职责契约

| 参与者 | 负责事项 | 不负责事项 |
|---|---|---|
| 用户 | 确认 PDF 原文事实；确认跨页表格关系、表头和列语义；批准/拒绝结构化候选；确认无法自动判断的异常 | 不需要学习 CLI 参数；不需要手写或执行脚本；不直接维护 hash、manifest 或批次状态 |
| LLM | 识别当前阶段；读取 PDF、Markdown、manifest、review 和配置；解释异常；选择/组合 CLI；生成配置和修复记录；必要时生成动态辅助脚本；备份、dry-run、执行、回滚、复跑、验证和更新治理文档 | 不把推断当用户事实；不跳过用户审批；不直接写数据库；不把 VLM 输出当最终结论 |
| 现有 CLI | 执行解析、合并、TOC 处理、页级修复、格式化、检查、结构化抽取、审核门禁和入库前导出 | 不判断 PDF 特定业务语义；不自动批准待审核记录；不承担 LLM 的流程选择 |
| 动态辅助脚本 | 处理一个明确、有限、可验证且现有 CLI 无法直接覆盖的异常 | 不修改原始证据；不成为隐含的长期业务规则；不绕过备份、dry-run、审批或 manifest 校验 |

## 目标协作流程

```text
用户提供 PDF
  → pdf2md skill 识别/确认输出包
  → LLM 编排 pdf-auto / 现有 CLI
  → 自动生成 review.md 和候选配置
  → LLM 展示异常与 PDF 证据
  → 用户确认事实、表格关系和候选状态
  → LLM 更新 manual_fixes.jsonl / extraction_overrides.json / review_overrides.csv
  → 现有 CLI 或受控动态辅助脚本执行
  → LLM 校验 hash、页锚点、manifest、TOC、表格和记录集合
  → pdf-extract-data
  → 用户审批结构化候选
  → pdf-prepare-ingest
  → pdf-export-ingest
  → 交付入库前数据包，不导入数据库
```

每一轮协作都必须能回答四个问题：当前发现了什么、依据哪一页或哪条记录、需要用户确认什么、确认后将更新哪些产物。

## Step 0：协作契约与基线冻结

状态：设计中。

### Step 0 证据

当前真实基线已经证明：

- `pdf/春风250Sr` canonical Markdown 已覆盖 138/138 个非空页面，TOC 为 120/120；
- 包级 `policies.numeric_key=skip` 过滤 29 条纯数字 key 后，抽取保留 182 行；
- 用户确认后，入库前批次为 179 条 ready、3 条 skipped、0 条 not_ready、0 条冲突；
- 未执行数据库导入；
- `pdf-check-fixes` 通过，`python -m pytest -q` 为 304 passed，`tests/test-fix-validate.sh` 为 133/133；
- 当前项目已有 [ADR 0002：CLI-only 工作流](../adr/0002-cli-only-workflow.md) 和 [ADR 0003：LLM 编排与受控动态辅助脚本](../adr/0003-llm-orchestrated-dynamic-assistants.md)；
- `skills/pdf2md/SKILL.md` 与 `skills/pdf2md-fix/SKILL.md` 仍是两个独立入口，尚未完成合并；项目级和用户级 `pdf2md` skill 当前已同步。

以上是迁移前基线，不代表本计划的实施完成。

### Step 0 样本/fixture 矩阵

| 样本/场景 | 可执行命令 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|
| 现有完整真实包 | `scripts/pdf-check-fixes pdf/春风250Sr` | 138 页产物、TOC、manifest、修复记录一致 | 任一页锚点/TOC/hash/修复记录不一致 | `pdf/春风250Sr/` |
| 结构化抽取与审核门禁 | `scripts/pdf-extract-data pdf/春风250Sr && scripts/pdf-prepare-ingest pdf/春风250Sr` | 182 行候选；未确认项保持 `not_ready`；无纯数字 key | 出现静默漏抽、未审批记录进入 ready、冲突错误放行 | `pdf/春风250Sr/data/` |
| 入库前导出 | `scripts/pdf-export-ingest pdf/春风250Sr` | 只生成入库前 JSONL/manifest，不连接数据库 | 记录集合与 ready 集合不一致，或发生数据库写入 | `pdf/春风250Sr/data/ingest_batch.jsonl`、`ingest_manifest.json` |
| 全量回归 | `python -m pytest -q` | 当前基线 304 passed 或迁移后无计划外回归 | 既有测试失败且无法归因于预期迁移变化 | 测试输出 |
| 修复契约回归 | `bash tests/test-fix-validate.sh` | 133/133 通过 | 页级修复、配置、manifest、回滚或幂等断言失败 | 测试输出 |
| 动态辅助脚本最小 fixture | 由阶段 2 固化的 dry-run/失败回滚 fixture 执行 | 备份可恢复、范围外 hash 不变、重复运行无扩大修改 | 未备份即执行、部分回滚、范围漂移或重复写入 | `tests/fixtures/` 及临时工作目录 |
| 兼容入口 | 触发 `pdf2md-fix` 兼容说明并进入统一流程 | 不要求用户改记忆，最终仍由 `pdf2md` 编排 | 触发旧入口后进入另一套不一致流程 | skill 文档与会话输出 |

### Step 0 验证方式

- 核对项目级和用户级 `pdf2md` skill 内容及 hash 一致；
- 核对 `pdf2md-fix` 的兼容策略、迁移窗口和目标章节只有一个事实源；
- 用 `rg` 搜索 `pdf2md-fix`、本计划名称、`pdf2md` 入口、`manual_fixes.jsonl`、`extraction_overrides.json`、`review_overrides.csv`、`ready`、`动态辅助脚本` 和 `MCP`，确认没有互相矛盾的入口或状态定义；
- 在不改动真实包的前提下，复现 Step 0 矩阵中的现有结果；
- 在阶段 0 结束前形成一份“用户确认提示格式”和“LLM 每轮交付摘要格式”。

### Step 0 完成条件

- 单一主入口、兼容入口、用户审批边界、配置职责和最终交付边界均有明确文字契约；
- 现有真实包基线可复现；
- 动态脚本的安全要求已成为后续阶段的验收条目；
- `PLAN_MAP.md` 已同步，且最新独立准入复核明确达到阶段 1 设计/实施准入标准。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 主要产物 | 状态 |
|---|---|---|---|---|
| 阶段 0：协作契约与基线冻结 | 冻结人/LLM/CLI/动态脚本边界和基线 | 本计划建立，已有 ADR 0002/0003 | 协作提示契约、基线矩阵、迁移验收清单 | 设计中 |
| 阶段 1：统一 `pdf2md` 编排入口 | 把解析后复核、修复、抽取和入库前准备编排到 `pdf2md` | 阶段 0 完成 | `pdf2md` 主流程章节、阶段状态和用户确认模板 | 待实施 |
| 阶段 2：动态辅助脚本安全执行层 | 把一次性脚本纳入备份、dry-run、hash、范围和回滚闭环 | 阶段 0 契约冻结 | helper harness/约定、最小失败回滚 fixture、运行留痕 | 待实施 |
| 阶段 3：`pdf2md-fix` 兼容迁移 | 将人工复核能力迁入 `pdf2md`，保留短期兼容入口 | 阶段 1 和阶段 2 通过 | 项目级/用户级 skill 同步、兼容说明、旧入口回归 | 待实施 |
| 阶段 4：真实 PDF 协作验收 | 验证用户只审批、LLM 完成全流程 | 阶段 3 完成 | 春风250Sr 及代表性样本验收记录 | 待实施 |
| 阶段 5：治理收尾与兼容策略决策 | 独立验收并决定兼容 skill 后续状态 | 阶段 4 通过 | 验收报告、PLAN_MAP 更新、`pdf2md-fix` 合并/废弃决策 | 设计中 |

阶段 1–5 不因阶段 0 完成自动变为 `待实施`；每个阶段都要有自己的 Step 0、验证方式、完成条件和独立准入复核。

## 阶段 1：统一 `pdf2md` 编排入口

### 设计原则

- `pdf2md` 只负责协作编排和决策呈现；确定性变换继续由 CLI 执行。
- 每个阶段先读产物再行动：`manifest.json`、`review.md`、canonical Markdown、`data/` 和修复记录。
- LLM 先列候选和证据，再向用户提出最小必要确认；不要求用户了解内部脚本名。
- 用户确认必须写入对应产物：内容事实写 `manual_fixes.jsonl`，列语义写 `extraction_overrides.json`，审核状态写 `review_overrides.csv`。
- 每次写入后重新运行受影响的下游步骤，并展示变更前后记录数、状态数、冲突数和 hash。

### 计划中的统一阶段

1. 解析与初检：运行 `pdf-auto`，收集页面质量、TOC、表格和 manifest 结果。
2. 异常分类：区分可由现有 CLI 处理、需要用户确认、需要动态脚本和只能保留 `needs_review` 的异常。
3. 内容修复：按页锚点执行 TOC、表格和缺失文本修复，更新 `manual_fixes.jsonl`。
4. 表格格式化与校对：保持语义不变地格式化 canonical Markdown，必要时按用户确认重建跨页逻辑表。
5. 结构化抽取：依据 Markdown 和包内 `extraction_overrides.json` 生成候选。
6. 人工审核：展示候选、来源页、证据和冲突，用户明确批准/拒绝/保留待复核。
7. 入库前准备：运行 `pdf-prepare-ingest` 和 `pdf-export-ingest`，只交付文件产物。

### 完成条件

- 用户可以只提供 PDF 和确认意见，不需要自行执行脚本；
- LLM 能给出每个异常的证据、待确认问题、将更新的文件和验证结果；
- 任意未确认事实不会自动进入 `approved`/`ready`；
- `pdf2md` 与现有 CLI 的公共边界没有计划外变化。

## 阶段 2：动态辅助脚本安全执行层

### 调度优先级

```text
现有 CLI
  → 组合现有 CLI
  → 生成临时动态辅助脚本
  → 若同类问题重复出现，晋升为通用脚本并补测试
```

LLM 只有在前两级不足以安全完成明确操作时，才生成动态脚本。动态脚本必须声明：目的、输入文件、输出文件、目标页/record_id、预期命中数、来源 hash、是否 dry-run、回滚目录和验证命令。

### 运行前后安全契约

- 运行前备份 Markdown、manifest、相关 JSON/CSV、修复记录和即将被替换的局部内容，并记录 hash；
- 先 dry-run，输出文件清单、页范围、record_id、命中数、前后 hash 和变更摘要；
- 只能修改用户授权的派生产物，禁止修改 PDF、原始 `segments/` 和 `content_list*.json`；
- 必须使用页锚点、块 hash、record_id 或等价定位，禁止无边界全局字符串替换；
- 采用临时文件和原子替换；一组文件中任一文件失败时整组回滚；
- 重复运行同一输入 hash 和修复记录必须幂等，不能重复追加内容或扩大范围；
- 运行后重新校验 manifest、TOC、页锚点、记录集合、冲突和下游状态；
- 默认脚本保存在临时目录；只有需要复现或再次使用时，才登记为包内辅助脚本并记录命令、输入、输出和 hash。

### 动态脚本晋升规则

- 单个 PDF、单次异常：保留临时脚本或包内配置，不进入通用 `scripts/`；
- 多个 PDF 出现同类问题：先补最小 fixture 和回归测试，再晋升通用脚本；
- 修改已有函数、类或方法前，必须先执行 GitNexus upstream impact analysis；风险为 HIGH/CRITICAL 时先报告并暂停实施；
- 晋升后执行 `detect_changes()`、回归测试、`pdf-check-fixes` 和治理检查。

### 完成条件

- 至少一个“成功、失败整组回滚、重复运行”fixture 通过；
- 证明范围外文件 hash 不变；
- 证明动态脚本不会绕过用户审批或入库前门禁；
- 明确临时脚本、包内配置和通用脚本三者的留存规则。

## 阶段 3：`pdf2md-fix` 兼容迁移

### 迁移策略

1. 在项目级 `skills/pdf2md/SKILL.md` 中加入解析后人工协作、动态辅助脚本和入库前准备章节；
2. 将 `skills/pdf2md-fix/SKILL.md` 收敛为兼容说明，指向 `pdf2md` 的统一流程，不再维护第二套事实；
3. 同步 `/Users/jafish/.claude/skills/pdf2md/SKILL.md` 和 `/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md`；
4. 更新 `docs/plans/pdf2md-fix-manual-workflow.md` 与 `PLAN_MAP.md`，记录“能力已合并、兼容入口保留”的关系；
5. 验证旧的 `pdf2md-fix` 触发方式仍能进入同一流程；
6. 兼容窗口结束后，依据独立验收决定将兼容入口标记为 `已合并` 或 `已废弃`，不得未经验证直接删除。

### 不能合并的内容

- `pdf2md-fix` 的历史完成证据不复制到新的入口文档；
- VLM 证据规则、人工修复记录契约和结构化审核门禁仍以专项计划/ADR 为事实源；
- 单个 PDF 的修复配置不写入 skill；
- 不因 skill 合并改变 CLI 契约或自动批准策略。

## 阶段 4：真实 PDF 协作验收

### 验收场景

- `春风250Sr`：覆盖 TOC、跨页保养表、表格格式化、纯数字 key 过滤、用户审批和入库前导出；
- 至少一个含异常 `<td>`/跨页表格的历史样本：验证动态辅助脚本的 dry-run、回滚和幂等；
- 至少一个没有业务表格或只有布局/图片表格的页面：验证不强行结构化；
- 旧 `pdf2md-fix` 触发方式：验证兼容入口不产生第二套结果。

### 验收判定

- 用户只需要确认事实和候选状态；
- LLM 完成 `pdf-auto → 修复/配置 → 抽取 → 审核 → 入库前导出`；
- 最终 Markdown、manifest、配置和审核文件互相一致；
- 所有 `ready` 记录均可回溯到 PDF 页和用户确认；
- 未执行数据库导入；
- 全量测试、修复回归、真实包检查和治理检查均有证据。

## 阶段 5：治理收尾与兼容策略决策

阶段 5 不能只依据实施者自述完成。独立验收者需要反向检查：

- 当前仓库的 skill、CLI、测试和输出包是否真的符合本计划；
- 是否有计划外自动批准、全局替换、原始证据修改或数据库写入；
- 是否仍存在重复的 `pdf2md`/`pdf2md-fix` 事实源；
- 动态脚本是否留下可复现命令、输入、输出、hash 和回滚证据；
- `PLAN_MAP.md`、ADR、专项计划和报告之间是否发生漂移。

通过后才可更新计划状态为 `已完成`，并单独决定 `pdf2md-fix` 兼容入口的最终状态。

## 影响模块或文件

本轮计划阶段 0 只修改治理文档。后续实施候选范围：

- `skills/pdf2md/SKILL.md`
- `skills/pdf2md-fix/SKILL.md`
- `/Users/jafish/.claude/skills/pdf2md/SKILL.md`
- `/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md`
- `scripts/`
- `manual_fixes.jsonl`
- `extraction_overrides.json`
- `review_overrides.csv`
- `manifest.json`
- `tests/`
- `docs/PLAN_MAP.md`
- `docs/plans/`
- `docs/adr/`

如果后续需要修改函数、类或方法，必须先按项目 AGENTS 规则执行 GitNexus impact analysis；本计划本轮没有代码实现，因此不触发该步骤。

## 失败策略、回滚和安全边界

| 风险 | 控制措施 | 回滚 |
|---|---|---|
| 用户需要记忆两个 skill | `pdf2md` 单一主入口，`pdf2md-fix` 仅保留兼容跳转 | 恢复兼容 skill，保留统一流程不变 |
| 动态脚本误改派生产物 | dry-run、页锚点/record_id、hash、原子替换 | 整组恢复备份，不只恢复 Markdown |
| LLM 把推断当事实 | 所有业务事实必须由用户确认并写入对应配置/审核文件 | 删除未确认 override，重新生成 `not_ready` |
| 临时脚本变成隐含业务逻辑 | 临时/包内/通用三级留存和晋升规则 | 删除临时脚本，保留配置和审计记录 |
| skill 与用户级副本漂移 | 项目级为事实源，修改后 hash 对比同步 | 暂停迁移，先完成同步 |
| 入口合并造成 CLI 行为变化 | 只迁移编排说明，保持 CLI-only 契约和现有脚本行为 | 回退 skill 文档，继续使用现有 CLI 链路 |

## MCP 决策

本计划沿用 ADR 0002 和 ADR 0003：当前不引入 MCP。原因是 LLM 与 CLI 在同一工作区，工具调用、文件读取和验证已经可用；当前瓶颈是 PDF 事实确认，不是远程工具发现。

只有在出现跨机器调用、多个外部客户端、队列/异步任务、权限隔离或稳定服务契约需求时，才另立计划重新评估 MCP 或其他服务接口。该评估不得作为本计划的隐含实施项。

## 当前阻塞项与未决问题

- 当前没有业务阻塞；迁移尚未实施。
- 需要在阶段 0 决定动态脚本默认只保留在临时目录，还是对可复现案例保留包级副本；两者都必须保留 hash 和命令。
- 需要在阶段 1 决定 LLM 每轮交付摘要是否固定为机器可读 JSON；如果形成公共契约，需单独记录 Schema。
- 需要在阶段 3 确定 `pdf2md-fix` 兼容窗口的结束条件；不能按时间直接删除，至少要通过旧入口回归和一次真实 PDF 验收。

## 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 日期 | 2026-07-14 |
| 阶段 | 阶段 0：协作契约与基线冻结 |
| 结论 | 设计中：已具备基线和决策依据，尚未达到阶段 1 实施准入 |
| 证据 | `春风250Sr` 真实包完成 138/138 页、TOC 120/120、179 ready/3 skipped/0 not_ready/0 conflicts；ADR 0002/0003 已记录 CLI-only 与动态辅助脚本决策；两个 skill 入口尚未完成迁移 |
| 复核者 | 独立治理复核 |

## 验证方式

阶段完成后至少执行：

```bash
plan-governance-cli check .
git diff --check
python -m pytest -q
bash tests/test-fix-validate.sh
scripts/pdf-check-fixes pdf/春风250Sr
```

真实样本验收还必须记录：输入 PDF hash、输出包路径、Markdown/manifest/config/review 文件 hash、候选和 ready 数量、冲突数量、用户确认记录、动态脚本（如有）的备份与回滚证据，以及明确的“未执行数据库导入”结论。

## 相关文档

- [PDF 工作流与 LLM 协作复盘](../reports/pdf-workflow-llm-collaboration-review-2026-07-14.md)
- [ADR 0002：CLI-only 工作流](../adr/0002-cli-only-workflow.md)
- [ADR 0003：LLM 编排与受控动态辅助脚本](../adr/0003-llm-orchestrated-dynamic-assistants.md)
- [pdf2md-fix 人工复核与内容修复计划](pdf2md-fix-manual-workflow.md)
- [pdf-table-repair](pdf-table-repair.md)
- [pdf-extract-data 表格覆盖与审核候选补全](pdf-extract-data-table-coverage.md)
- [入库前数据准备管线](data-ingestion-pipeline.md)
