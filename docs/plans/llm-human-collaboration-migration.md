# 计划：LLM/人工协作入口迁移

## 计划状态

- 状态：待实施
- 当前阶段：阶段 4：真实 PDF 协作验收
- 最后更新：2026-07-15

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

状态：已完成。

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

### 用户确认提示格式（阶段 0 冻结）

LLM 向用户提问时使用以下最小结构；一轮可以包含多个独立确认项，但每项必须有自己的来源和动作：

```text
【需要确认】<确认项标题>

问题：<只问一个可判断的问题>
PDF 证据：第 <页码> 页；<原文/截图/表格范围>
当前候选：<当前 Markdown、表格或结构化候选>
请确认：确认 / 修改为…… / 拒绝 / 保留待复核
确认后更新：<manual_fixes.jsonl | extraction_overrides.json | review_overrides.csv>
```

约束：

- 用户只确认 PDF 事实、表格关系、字段语义和候选状态，不需要执行脚本；
- LLM 必须把“候选推断”和“PDF 已确认事实”分开描述；
- 无法由 PDF 明确判断时，默认选择“保留待复核”，不得替用户批准；
- 用户确认后，LLM 才能写入对应产物并继续运行下游步骤。

### LLM 每轮交付摘要格式（阶段 0 冻结）

每轮执行结束后，LLM 使用以下结构向用户汇报：

```text
【本轮处理完成】<阶段/动作>

输入：<输出包路径>；输入 hash：<hash>
已执行：<CLI 或动态辅助脚本；动态脚本注明临时/包级>
已备份：<备份路径、文件数、hash；无写入时写“未发生派生物写入”>
用户确认：<本轮采纳/拒绝/待复核数量>
产物变化：<文件、记录数、状态数、前后 hash>
验证结果：<TOC、页锚点、manifest、表格、冲突、幂等和测试结果>
剩余异常：<按页/record_id 列出；没有则写“无”>
下一步：<继续自动处理 / 需要用户确认的问题>
入库边界：未写入数据库；交付物为入库前数据准备产物
```

LLM 不应只报告“脚本执行成功”，必须同时报告产物变化、验证结果和剩余人工决策。

### Step 0 实施复核（2026-07-14）

本阶段使用真实包和临时副本完成基线复核，未改动真实 `pdf/春风250Sr` 产物：

- `sha256sum skills/pdf2md/SKILL.md /Users/jafish/.claude/skills/pdf2md/SKILL.md`：两份 hash 均为 `7470187d5fc02771e64ba26c6e503fe3f3f16be9c2e76bae31a63e10df9b7195`；
- `scripts/pdf-check-fixes pdf/春风250Sr`：退出码 0；
- 真实包读取结果：138 个页锚点、0 个空页占位、TOC 120 项、`ingest_ready.csv` 182 行、179 ready、3 skipped、0 not_ready、0 冲突、0 个纯数字 key；
- 临时副本执行 `scripts/pdf-extract-data`、`scripts/pdf-prepare-ingest`、`scripts/pdf-export-ingest` 和 `scripts/pdf-check-fixes`：全部退出码 0，结果为 182 行、179 ready、3 skipped、0 not_ready、0 冲突、导出 179 条、0 个纯数字 key；
- 既有回归证据：`python -m pytest -q` 为 304 passed，`bash tests/test-fix-validate.sh` 为 133/133；
- 入库边界核对：仅生成 `ingest_batch.jsonl` 和 `ingest_manifest.json`，未执行数据库导入。

本次复核已作为阶段 0 的实施和独立准入证据；阶段 0 已关闭，阶段 1 进入实施。

### Step 0 完成条件

- 单一主入口、兼容入口、用户审批边界、配置职责和最终交付边界均有明确文字契约；
- 现有真实包基线可复现；
- 动态脚本的安全要求已成为后续阶段的验收条目；
- `PLAN_MAP.md` 已同步，且最新独立准入复核明确达到阶段 0 实施标准。

## 当前阶段

阶段 4：真实 PDF 协作验收。阶段 0、阶段 1、阶段 2 和阶段 3 已完成；阶段 3 已独立验收通过，阶段 4 Step 0 也已通过独立准入复核，达到 `待实施` 标准；阶段 4 尚未开始实施。

### 阶段准入摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 待实施 |
| 准入结论 | 阶段 4 Step 0 已完成并通过独立准入复核，达到 `待实施` 标准；尚未执行真实协作验收 |
| Step 0 | 已冻结春风250Sr 主样本、demo20 异常表格样本、demo20 p4/p10 无业务表格页、动态 helper 安全 fixture、旧入口兼容替代基线及 no-MCP/不入库边界 |
| 样本矩阵 | 每个场景均已登记输入或基线、可执行命令、预期结果、失败判定和输出位置 |
| 验证方式 | 阶段 4 实施时按矩阵执行真实 PDF 协作；重点验证用户只审批事实/候选，LLM 完成编排、配置同步、动态 helper、审核和入库前导出 |
| 失败/回滚边界 | 真实协作验收只在派生产物副本或明确备份边界内进行；动态 helper 继续使用整包快照回滚；不修改原始 PDF/segments/content_list，不写数据库 |
| 当前阻塞项 | 无阶段 4 准入阻塞；阶段 4 已达到 `待实施`，但尚未开始实施 |
| 最新独立准入复核 | 2026-07-15，结论通过：阶段 4 Step 0 达到 `待实施` 标准；阶段 4 尚未实施 |

### 阶段 2 Step 0：动态辅助脚本安全执行契约

状态：已完成，达到实施标准。

#### 基线与缺口

- 现有 `scripts/pdf-apply-fixes` 已具备页锚点、来源 hash、预期命中数、原子写入、失败不落部分状态和幂等跳过能力；`tests/test-fix-validate.sh` 已覆盖其失败回滚与重复运行基线。
- 现有 `scripts/pdf-table-repair` 已具备候选记录、局部范围、失败回滚和幂等基线；其安全性依赖具体脚本约定，不能直接约束 LLM 临时生成的任意命令。
- 当前缺口是一个与业务语义无关的事务包装层：统一控制动态命令的 dry-run、全包快照、授权路径、范围外变更检测、失败恢复和机器可读留痕。
- 阶段 2 只补通用安全执行层和最小 fixture，不把 `春风250Sr` 的页码、表头、字段或修复内容写入通用脚本。

#### 动态命令接口

动态辅助命令由 LLM 临时编排，事务包装器以参数和环境变量传递上下文，不解析或推断 PDF 业务语义：

- 命令必须能在 `PDF_HELPER_MODE=dry-run` 和 `PDF_HELPER_MODE=apply` 两种模式下运行；包装器同时提供 `PDF_HELPER_PACKAGE`、`PDF_HELPER_ALLOWLIST`、`PDF_HELPER_RUN_ID`。
- 包装器必须接收一个显式的只读验证命令，在 apply 成功后以 `PDF_HELPER_MODE=validate` 执行；验证命令失败或产生任何包内写入时，整组恢复快照，JSON 摘要记录验证退出码和回滚原因。
- LLM 必须显式声明包根目录、授权派生文件相对路径、目的、目标页/record_id、来源 hash、预期命中数和验证命令；包装器只执行 allowlist 与文件树安全检查。
- `dry-run` 必须只报告候选变更而不写包；包装器发现 dry-run 改变任意包内路径时立即失败并恢复快照，不进入 apply。
- `apply` 的新增、删除或修改路径必须完全属于 allowlist；路径穿越、绝对路径、PDF、`segments/`、`content_list*.json` 和其他原始证据路径一律拒绝。
- 动态 helper 不得授权修改 `review_overrides.csv`、`ingest_ready.csv`、`conflicts.csv`、`ingest_batch.jsonl`、`ingest_manifest.json` 等审核或入库前门禁产物；用户确认后的审核状态仍由 LLM 按既有流程更新，动态 helper 不能代替审批。
- 一次执行以整包快照为回滚边界；命令失败、范围越界、快照校验失败或下游验证失败时恢复整包，而不是只恢复 Markdown。
- 事务输出 JSON 摘要，至少包含 run_id、命令、模式退出码、allowlist、变更路径、前后 hash、结果和回滚状态；LLM 将其并入本轮交付摘要。

#### Step 0 样本/fixture 矩阵

| 样本/场景 | 可执行命令 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|
| 既有修复回滚/幂等基线 | `bash tests/test-fix-validate.sh` | 133/133 通过，既有页级修复契约不回归 | 任一既有回滚、幂等或 manifest 断言失败 | 测试输出 |
| 真实包只读门禁 | `scripts/pdf-check-fixes pdf/春风250Sr` | 退出码 0，真实包不被动态 fixture 修改 | 真实包检查失败或出现未授权变更 | `pdf/春风250Sr/` |
| 动态命令成功 | `python -m pytest -q tests/test_pdf_run_helper.py -k success` | dry-run 无写入，apply 只改变授权派生文件并输出 JSON 摘要 | dry-run 写入、授权范围外变更或摘要缺字段 | 临时 fixture 与 pytest 输出 |
| 动态命令越界 | `python -m pytest -q tests/test_pdf_run_helper.py -k out_of_scope` | 返回失败，授权文件和范围外文件均恢复到执行前 hash | 越界文件残留或授权文件部分保留 | 临时 fixture 与 pytest 输出 |
| 动态命令失败回滚 | `python -m pytest -q tests/test_pdf_run_helper.py -k rollback` | 返回失败，整组文件恢复，记录 rollback=true | 只恢复单文件、产生半成品或无法复跑 | 临时 fixture 与 pytest 输出 |
| 重复运行 | `python -m pytest -q tests/test_pdf_run_helper.py -k idempotent` | 同一输入 hash/修复记录第二次运行无扩大变更 | 重复追加、hash 继续变化或记录集合扩大 | 临时 fixture 与 pytest 输出 |
| apply 后验证失败 | `python -m pytest -q tests/test_pdf_run_helper.py -k validation` | 验证命令失败时整组回滚并记录验证结果 | 验证未执行、失败后残留派生产物或摘要缺失验证状态 | 临时 fixture 与 pytest 输出 |
| 审核/入库门禁产物 | `python -m pytest -q tests/test_pdf_run_helper.py -k gate` | protected 产物不能进入 allowlist，未审批状态不能被动态 helper 直接放行 | `review_overrides`/ingest 产物可被 helper 授权修改，或出现未审批导出 | 临时 fixture 与 pytest 输出 |

#### 阶段 2 Step 0 验证方式与完成条件

- 先运行现有回滚/幂等基线和真实包只读检查，再用临时 fixture 验证成功、dry-run 写入拦截、范围越界、整组失败回滚和重复运行。
- 验证包装器不接触 PDF、原始 `segments/`、`content_list*.json`，不改变审批状态，不执行数据库导入；测试只使用临时目录。
- 验证 JSON 摘要能让 LLM 在不要求用户执行脚本的情况下说明命令、输入/输出、hash、变更、回滚和下一步。
- 阶段 2 完成条件：安全执行包装器、动态命令约定和最小 fixture 均落地；成功、越界、失败回滚、dry-run 保护、apply 后验证失败回滚、审核/入库门禁保护和幂等用例通过；范围外 hash 不变；临时脚本与包内登记规则写入 `pdf2md` skill；治理检查和独立验收证据完成。

#### 阶段 2 Step 0 独立准入复核（2026-07-15）

结论：通过，达到 `待实施` 标准并进入实施。

证据：已核对本计划、ADR 0002/0003、现有 `pdf-apply-fixes`/`pdf-table-repair` 及 `tests/test-fix-validate.sh`；已明确动态命令接口、授权范围、原始证据保护、整包快照、dry-run、机器可读摘要、失败回滚、幂等和晋升规则；样本矩阵包含可执行命令、预期结果、失败判定和输出位置。当前没有阶段 2 业务阻塞，未决的包内留存选择已按“默认临时、复现时登记”冻结。

#### 阶段 2 实施证据（2026-07-15）

- 新增 `scripts/pdf-run-helper`，不包含 PDF 特定业务规则；LLM 动态命令通过 `PDF_HELPER_MODE`、`PDF_HELPER_PACKAGE`、`PDF_HELPER_ALLOWLIST` 和 `PDF_HELPER_RUN_ID` 接收事务上下文。
- 包装器在执行前创建整包临时快照，先运行 dry-run；dry-run 写入、apply 命令失败、allowlist 越界或文件树异常时恢复整包，并输出 JSON 摘要记录 run_id、命令、模式退出码、变更路径、前后清单 hash、结果和回滚状态。
- allowlist 拒绝绝对路径、路径穿越、目录、PDF、`segments/`、`content_list*.json` 和其他原始证据路径；`--log` 要求位于包目录外，避免日志污染事务范围。
- 新增 `tests/test_pdf_run_helper.py`，覆盖成功、dry-run 写入拦截、范围外变更整组回滚、apply 失败整组回滚、重复运行幂等和原始 PDF 不可授权，共 5 个 fixture 通过。
- 验证结果：`python -m pytest -q` 为 309 passed、5 warnings；`bash tests/test-fix-validate.sh` 为 133/133；`scripts/pdf-check-fixes pdf/春风250Sr` 退出码 0；`git diff --check` 通过。
- 已同步项目级和用户级 `pdf2md` skill，明确 `pdf-run-helper` 的调用边界、两阶段环境变量、整包回滚和动态脚本留存/晋升规则；两份 skill 内容保持同步。

本次实施没有修改 PDF、真实输出包、原始 `segments/`、`content_list*.json` 或数据库边界；阶段 2 已在修复后独立验收中关闭。

#### 阶段 2 独立验收（初次，2026-07-15）

结论：**不通过，阶段 2 不能标记为已完成。** 核心事务安全能力通过，但完成条件中的后置验证和审批/入库边界没有形成可复现的执行门禁。

| 验收项 | 结果 | 独立证据 |
|---|---|---|
| dry-run 不写入 | 通过 | `python -m pytest -q tests/test_pdf_run_helper.py` 的 dry-run mutation fixture 通过，命令不进入 apply 并恢复快照 |
| apply 只修改 allowlist | 通过 | out-of-scope fixture 检测 `manifest.json` 越界并恢复授权文件与越界文件 |
| 失败整组回滚 | 通过 | apply 失败 fixture 返回非零，包内文件恢复执行前 hash |
| 重复运行幂等 | 通过 | 第二次运行 `apply_changes=[]`，目标 hash 不再变化 |
| 原始证据保护 | 通过 | PDF allowlist 拒绝 fixture 通过；真实包 `scripts/pdf-check-fixes pdf/春风250Sr` 退出码 0 |
| 回归与同步 | 通过 | 309 pytest、133/133 修复回归、项目级/用户级 `pdf2md` skill `cmp` 通过；工作区干净 |
| apply 后验证命令 | **不通过** | `scripts/pdf-run-helper` 只有动态命令的 dry-run/apply 两次调用，没有 `--validate`/后置验证参数、验证结果字段或验证失败回滚 fixture；skill 中的“验证命令”目前只是 LLM 约定 |
| 审批/入库前门禁 | **不通过** | 包装器只按文件 allowlist 判断范围，未阻止或验证对 `review_overrides.csv`、`ingest_ready.csv`、`ingest_batch.jsonl` 等审核/下游产物的直接修改，也没有可复现的“未审批不能导出”动态脚本 fixture；因此不能独立证明动态脚本不会绕过审批或入库前门禁 |

补齐条件：为包装器增加只读、可审计的 apply 后验证入口，并在失败时整组回滚；明确动态脚本可写文件与审核/下游产物的边界，增加未审批状态不能进入导出的 fixture，再重新执行本节验收。补齐前不推进阶段 3，也不将阶段 2 标记为已完成。

#### 阶段 2 修复实施证据（2026-07-15）

- `scripts/pdf-run-helper` 新增必填 `--validate-command`，以 `PDF_HELPER_MODE=validate` 执行 apply 后只读验证；验证失败或验证阶段写入包内文件时恢复整包，并在 JSON 摘要中记录验证结果、变更和回滚。
- allowlist 现在拒绝 `review_overrides.csv`、`ingest_ready.csv`、`conflicts.csv`、`ingest_batch.jsonl`、`ingest_manifest.json`，动态 helper 不能直接修改审核状态、入库前候选、冲突或导出批次；用户确认后的审核状态仍由 LLM 按既有流程更新。
- 新增验证失败回滚、验证阶段写入回滚和 5 类门禁产物拒绝 fixture；helper fixture 共 8 passed。
- 项目级/用户级 `pdf2md` skill 与 ADR 0003 已同步新契约；未修改 PDF、真实输出包、原始 `segments/`、`content_list*.json` 或数据库边界。
- 修复后回归：`python -m pytest -q` 为 312 passed、5 warnings；`bash tests/test-fix-validate.sh` 为 133/133；`scripts/pdf-check-fixes pdf/春风250Sr` 退出码 0；skill `cmp` 和 `git diff --check` 通过。

#### 阶段 2 独立验收（修复后，2026-07-15）

结论：**通过，阶段 2 已完成并关闭。**

| 验收项 | 结果 | 独立证据 |
|---|---|---|
| apply 后验证命令 | 通过 | `--validate-command` 为必填；验证以 `PDF_HELPER_MODE=validate` 执行，失败 fixture 返回非零并恢复 apply 变更 |
| 验证阶段只读 | 通过 | validation mutation fixture 检测包内写入并恢复整包 |
| 审批/入库前门禁 | 通过 | 5 类审核/入库前产物均拒绝进入 allowlist；既有 F9 导出回归继续证明只有 `approved + ready` 记录可导出 |
| 核心事务安全 | 通过 | dry-run、allowlist 越界、失败整组回滚、重复运行幂等和原始 PDF 保护 fixture 全部通过 |
| 全量与真实包 | 通过 | 312 pytest、133/133 修复回归、`pdf-check-fixes pdf/春风250Sr`、skill `cmp` 全部通过 |
| 用户参与边界 | 通过 | helper 不生成或修改审核门禁产物；用户仍只需确认 PDF 事实和候选状态，阶段 3 另行处理兼容入口 |

验收结论只关闭阶段 2，不改变阶段 3 的准入状态；阶段 3 必须完成自己的 Step 0 和独立准入复核。

### 阶段 1 Step 0：统一入口契约与内容映射

状态：已完成，达到实施标准。

#### 现状基线

| 内容 | 当前事实源 | 迁移结论 |
|---|---|---|
| PDF 解析、ModelPad、输出包、CLI JSON | `skills/pdf2md/SKILL.md` | 保留在 `pdf2md`，作为主流程前半段 |
| TOC、表格、页级 fallback、结构化抽取、入库前导出 | `skills/pdf2md/SKILL.md` | 保留在 `pdf2md`，作为确定性执行层说明 |
| 人工复核顺序、表格异常候选、跨页表格确认 | `skills/pdf2md-fix/SKILL.md`、`pdf2md-fix-manual-workflow` | 将入口、职责和协作方式吸收到 `pdf2md`；字段契约继续引用专项计划 |
| VLM 使用边界 | `skills/pdf2md-fix/SKILL.md`、ADR 0003 | 在 `pdf2md` 中保留“证据/候选，不是事实”的边界 |
| Markdown/manifest 原子同步、页锚点和幂等 | `skills/pdf2md-fix/SKILL.md`、`pdf-table-repair` | 在 `pdf2md` 中作为人工修复安全门禁 |
| `manual_fixes.jsonl`、`extraction_overrides.json`、`review_overrides.csv` | 计划和现有输出包契约 | 三类文件职责不合并，按用户确认动作分别更新 |
| `pdf2md-fix` 触发入口 | 当前独立 skill | 阶段 1 保留现状；阶段 3 改为兼容跳转并完成旧入口回归 |

#### 阶段 1 Step 0 样本矩阵

| 场景 | 基线/命令 | 预期 | 失败判定 |
|---|---|---|---|
| 主入口现有能力 | `skills/pdf2md/SKILL.md`；`pdf/春风250Sr` 临时副本链路 | 解析、修复后检查、抽取、审核、导出边界完整 | 主入口缺少已有 CLI 或数据库边界改变 |
| 人工修复能力映射 | `skills/pdf2md-fix/SKILL.md` 与 `docs/plans/pdf2md-fix-manual-workflow.md` 反向核对 | 入口、VLM、安全门禁和产物职责均有唯一落点 | 迁移后丢失修复记录、页锚点、manifest 或 VLM 限制 |
| 用户确认边界 | 阶段 0 冻结的确认提示格式 | 用户只确认事实和状态，不执行脚本 | 出现要求用户手写/执行 CLI 或 LLM 自动批准 |
| 入库前边界 | `scripts/pdf-export-ingest <package>` | 只交付 JSONL/manifest，不连接数据库 | 入口文档出现数据库导入动作 |

#### 阶段 1 Step 0 完成条件

- `pdf2md` 有一个可执行的“解析后人工协作与入库前准备”主章节；
- 章节能从 `review.md`/manifest 进入人工修复、结构化抽取和审核，不复制字段级事实源；
- 用户确认格式、LLM 交付摘要、动态脚本安全契约和 no-MCP 决策均可从主入口找到；
- 项目级和用户级 `pdf2md` skill 内容 hash 一致；
- 阶段 3 的兼容迁移仍单独保留，不能在本阶段删除 `pdf2md-fix`。

#### 阶段 1 实施证据（2026-07-14）

- 已在项目级 `skills/pdf2md/SKILL.md` 增加“LLM/人工协作阶段（统一主入口）”，覆盖统一顺序、人工确认边界、三类配置职责、动态辅助脚本安全边界、LLM 交付摘要和 no-MCP 决策；
- 已同步用户级 `/Users/jafish/.claude/skills/pdf2md/SKILL.md`，两份文件 SHA-256 均为 `8eb2336ef5ba3a43dd575643b528339011f4775c247dbe00fd527ea0ef9accfc`，`cmp` 通过；
- `pdf2md-fix` 项目级和用户级 skill 未改写，仍保留完整人工修复事实源，符合阶段 3 兼容迁移边界；
- 本阶段没有修改 CLI、PDF 包、原始 segments 或数据库边界，`git diff --check` 通过；
- 阶段 0 的 304 pytest、133/133 修复回归和真实包临时副本链路继续作为主入口回归基线。

#### 阶段 1 独立验收（2026-07-15）

| 验收项 | 结果 | 证据 |
|---|---|---|
| 项目级/用户级 `pdf2md` skill 同步 | 通过 | SHA-256 均为 `8eb2336ef5ba3a43dd575643b528339011f4775c247dbe00fd527ea0ef9accfc`，`cmp` 通过 |
| 主入口内容 | 通过 | `skills/pdf2md/SKILL.md` 含统一顺序、人工确认边界、动态脚本边界、LLM 交付摘要和 no-MCP 决策 |
| `pdf2md-fix` 历史入口保护 | 通过 | 项目级/用户级 `pdf2md-fix` hash 均为 `6dbe598a6aec135782a23d503c33119c2d6a27920dbbd9066389e14312cb7a93`，未被阶段 1 改写 |
| 真实输出包检查 | 通过 | `scripts/pdf-check-fixes pdf/春风250Sr` 退出码 0 |
| 全量回归 | 通过 | `python -m pytest -q`：304 passed；`bash tests/test-fix-validate.sh`：133/133 |
| 计划外代码/产物变化 | 通过 | 本阶段提交只包含治理文档和 `pdf2md` skill；`git diff --check` 通过，未修改 PDF 包、CLI 或数据库边界 |

验收结论：阶段 1 已完成。该结论只关闭阶段 1，不代表阶段 2 动态辅助脚本安全层或阶段 3 `pdf2md-fix` 兼容迁移完成。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 主要产物 | 状态 |
|---|---|---|---|---|
| 阶段 0：协作契约与基线冻结 | 冻结人/LLM/CLI/动态脚本边界和基线 | 本计划建立，已有 ADR 0002/0003 | 协作提示契约、基线矩阵、迁移验收清单 | 已完成 |
| 阶段 1：统一 `pdf2md` 编排入口 | 把解析后复核、修复、抽取和入库前准备编排到 `pdf2md` | 阶段 0 完成 | `pdf2md` 主流程章节、阶段状态和用户确认模板 | 已完成 |
| 阶段 2：动态辅助脚本安全执行层 | 把一次性脚本纳入备份、dry-run、hash、范围和回滚闭环 | 阶段 0 契约冻结 | helper harness/约定、最小失败回滚 fixture、运行留痕 | 已完成 |
| 阶段 3：`pdf2md-fix` 兼容迁移 | 将人工复核能力迁入 `pdf2md`，保留短期兼容入口 | 阶段 1 和阶段 2 通过 | 项目级/用户级 skill 同步、兼容说明、旧入口回归 | 已完成 |
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

### 阶段 3 Step 0：兼容入口与唯一事实源冻结

状态：已完成，达到 `待实施` 标准。

#### 基线证据

- 项目级和用户级 `skills/pdf2md-fix/SKILL.md` 当前完全一致，SHA-256 均为 `6dbe598a6aec135782a23d503c33119c2d6a27920dbbd9066389e14312cb7a93`；两份仍保留完整旧人工复核流程，作为本阶段回滚基线。
- 项目级和用户级 `skills/pdf2md/SKILL.md` 当前完全一致，已包含统一入口、人工确认、动态 helper、结构化抽取和入库前准备；SHA-256 均为 `8f22ec7a995244e6c33347abb59c216894fbdd89101c84761c205712dfce7175`。
- `pdf2md-fix` 的能力事实源继续由 `docs/plans/pdf2md-fix-manual-workflow.md` 和既有专项计划承载；阶段 3 不复制字段、Schema、VLM 或修复规则，只把旧入口收敛为指向 `pdf2md` 的兼容说明。
- 当前没有可运行的 MCP 或远程 skill 服务；旧入口兼容基线采用文件存在、触发词保留、统一入口章节存在和内容反向引用检查的替代证据，不把不存在的运行时服务当作验收前提。

#### 阶段 3 兼容契约

- 用户继续可以使用 `pdf2md-fix` 这个名称触发流程；兼容 skill 必须明确提示“流程已统一到 `pdf2md`”，并链接统一主入口和本计划，不再维护第二套操作步骤。
- 项目级 `skills/pdf2md-fix/SKILL.md` 是兼容说明的事实源，用户级 `/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md` 必须逐字同步。
- 兼容窗口持续到阶段 4/5 独立验收完成；阶段 3 不删除 skill、不删除触发词、不修改 CLI、不修改真实 PDF 包、不改变数据库边界。
- 阶段 3 的唯一实施对象是两个 `pdf2md-fix/SKILL.md` 文件和必要的治理文档；`pdf2md` 主 skill 只在发现链接漂移时同步修正，不重新复制旧流程。

#### 阶段 3 Step 0 样本/fixture 矩阵

| 场景 | 可执行命令 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|
| 旧兼容入口基线 | `sha256sum skills/pdf2md-fix/SKILL.md /Users/jafish/.claude/skills/pdf2md-fix/SKILL.md && cmp -s skills/pdf2md-fix/SKILL.md /Users/jafish/.claude/skills/pdf2md-fix/SKILL.md` | 两份旧 skill hash 一致且文件存在 | hash 不一致、文件缺失或无法回滚 | 命令输出 |
| 主入口已具备迁移目标 | `rg -n '^## LLM/人工协作阶段|统一事务包装器|用户只确认|pdf-export-ingest' skills/pdf2md/SKILL.md` | 统一入口、用户确认、helper 和入库前边界均存在 | 主入口缺少任一目标章节或出现数据库导入表述 | `skills/pdf2md/SKILL.md` |
| 旧入口触发词基线 | `rg -n 'name: pdf2md-fix|# pdf2md-fix|pdf2md-fix|review_overrides|manual_fixes' skills/pdf2md-fix/SKILL.md` | 兼容名称、历史触发词和产物名称可被识别 | 迁移后旧名称完全消失或保留第二套事实源 | `skills/pdf2md-fix/SKILL.md` |
| 真实包边界 | `scripts/pdf-check-fixes pdf/春风250Sr` | 退出码 0，真实包不被 skill 迁移修改 | 真实包变化或检查失败 | `pdf/春风250Sr/` |
| 全量回归基线 | `python -m pytest -q && bash tests/test-fix-validate.sh` | 当前 312 pytest、133/133 修复回归继续通过 | 出现与 skill 迁移无关的计划外回归 | 测试输出 |

#### 阶段 3 Step 0 验证方式、完成条件与回滚

- 实施前保存两个 `pdf2md-fix` skill 的 hash；实施后逐字 `cmp`，并用 `rg` 检查旧触发词、统一入口链接和唯一事实源。
- 反向搜索 `pdf2md-fix`、本计划名称、`manual_fixes.jsonl`、`review_overrides.csv`、`pdf-export-ingest` 和 `草案为准` 等关键字，确认旧 skill 没有重新承载字段级事实，也没有入口/审批/入库边界漂移。
- 完成条件：项目级/用户级兼容 skill 同步；旧入口可识别并明确跳转到 `pdf2md`；没有第二套完整流程；真实包、CLI、数据库边界和阶段2回归不变；兼容窗口、回滚方式和阶段4/5决策条件写入治理文档。
- 失败时恢复两个 `pdf2md-fix/SKILL.md` 到 Step 0 hash；不回滚或重建 PDF 产物，不删除用户已有配置，不推进阶段 4。

#### 阶段 3 Step 0 独立准入复核（2026-07-15）

结论：通过，达到 `待实施` 标准；阶段 3 尚未实施。

证据：两份 `pdf2md-fix` skill hash/cmp 一致且保留完整旧流程；两份 `pdf2md` skill hash/cmp 一致且已有统一协作主入口；目标范围仅涉及兼容 skill 和治理文档；真实包检查、312 pytest、133/133 修复回归可复现；兼容窗口、回滚边界、唯一事实源和旧入口替代基线已明确；当前没有阶段 3 准入阻塞。

#### 阶段 3 实施证据（2026-07-15）

- 项目级和用户级 `pdf2md-fix/SKILL.md` 已收敛为兼容说明，均明确 `pdf2md` 是唯一主入口，保留 `pdf2md-fix` 名称和触发词，不再重复完整人工修复流程。
- 项目级和用户级 `pdf2md/SKILL.md` 已同步更新为“`pdf2md-fix` 已收敛为兼容入口”，两份仍保持逐字一致。
- 新 `pdf2md-fix` skill 保留 TOC、跨页表格、异常 td、VLM、`manual_fixes.jsonl`、manifest、`review_overrides.csv`、`pdf-export-ingest` 等旧触发词，并将字段/Schema/VLM/修复规则指向正式专项计划和 ADR。
- 本阶段没有修改 CLI、PDF、真实输出包、原始 `segments/`、`content_list*.json` 或数据库边界；旧版 `pdf2md-fix` hash `6dbe598a...` 已记录为回滚基线，新两份兼容 skill hash 均为 `a1728f44c08ac516c9180606f4ca9c426d19ffc0ffae7e1ad273ac97c3cc72ea`。
- 验证结果：`cmp` 通过；`python -m pytest -q` 为 312 passed、5 warnings；`bash tests/test-fix-validate.sh` 为 133/133；`scripts/pdf-check-fixes pdf/春风250Sr` 退出码 0；`git diff --check` 通过。

阶段 3 实施已完成，且独立验收已通过；阶段 4 Step 0 已完成并达到 `待实施`，但阶段 4 尚未开始实施。

#### 阶段 3 独立验收（2026-07-15，通过）

验收结论：通过。阶段 3 完成条件全部满足，`pdf2md-fix` 已成为指向 `pdf2md` 的兼容入口；阶段 4 不因本次验收自动进入实施。

- 入口一致性：项目级和用户级 `pdf2md-fix/SKILL.md` 逐字一致，SHA-256 均为 `a1728f44c08ac516c9180606f4ca9c426d19ffc0ffae7e1ad273ac97c3cc72ea`；项目级和用户级 `pdf2md/SKILL.md` 逐字一致，SHA-256 均为 `bc73810ae72646377a1aba73aa4ae84b687a351c3efe740db4f85e4415061c05`。
- 兼容契约：旧名称、TOC、跨页表格、异常 td、VLM、`manual_fixes.jsonl`、`extraction_overrides.json`、`review_overrides.csv`、manifest 和 `pdf-export-ingest` 触发词均保留；兼容文件明确 `pdf2md` 是唯一主入口。
- 唯一事实源：兼容 skill 只有兼容行为、用户确认、安全边界和事实源链接，没有旧版逐步操作手册、字段表或业务修复规则；反向检查未发现规范内容把草案作为事实源。
- 边界与回归：提交 `24d9725` 只修改 `PLAN_MAP.md`、本计划和两组 skill；未修改 CLI、PDF、原始 `segments/`、`content_list*.json` 或数据库边界。`scripts/pdf-check-fixes pdf/春风250Sr` 退出码 0；`python -m pytest -q` 为 312 passed、5 warnings；`bash tests/test-fix-validate.sh` 为 133/133；`git diff --check` 通过；GitNexus 变更风险 LOW、无受影响执行流。
- 失败策略核对：兼容窗口继续保留到阶段 4/5 独立验收完成；未删除旧入口，未改变 CLI 契约，回滚仍为恢复实施前的 `pdf2md-fix` skill hash。

### 阶段 4：真实 PDF 协作验收

#### 阶段 4 Step 0：真实样本与协作边界冻结（2026-07-15）

状态：已完成，达到 `待实施` 标准。

#### 基线证据

- `pdf/春风250Sr` 是主样本：canonical Markdown 有 138 个逐页锚点，`toc_tree.json` 有 120 个目录条目；`manifest.json` 的表格格式化状态为 `verified`；`ingest_ready.csv` 为 182 行，其中 179 条 `ready`、3 条 `skipped`、0 条 `not_ready`、0 个纯数字 key；`conflicts.csv` 无数据行；`ingest_batch.jsonl` 为 179 条；`scripts/pdf-check-fixes pdf/春风250Sr` 退出码为 0。
- `pdf/demo20` 是异常表格代表样本：`data/table_candidates.jsonl` 和 `data/manual_fixes.jsonl` 均存在且非空，覆盖 8192 空列、异常列数、跨页表格和人工修复记录；`tests/test_table_repair.py` 覆盖候选分类、跨页分组、草案 Schema、页锚点、格式化、幂等和失败边界。
- 无业务表格/布局页基线采用 demo20 PDF 的 p4 和 p10：`tests/test_page_quality.py::TestNativeTableTextOmission::test_p4_body_text_no_false_positive`、`test_p6_no_table_no_false_positive` 均验证无 HTML 表格时不触发结构化遗漏修复；不把布局或图片页强行当成业务表格。
- 动态 helper 安全基线采用 `tests/test_pdf_run_helper.py` 的 8 个临时目录 fixture：成功 allowlist、dry-run 写入拒绝、越界整组回滚、失败 apply 回滚、重复运行幂等、验证失败回滚、验证阶段写入回滚、审批/原始证据路径拒绝。
- 旧入口替代基线：项目级/用户级 `pdf2md-fix` 与 `pdf2md` skill 均已通过 hash/cmp；旧名称和触发词保留，兼容 skill 没有第二套详细流程；本项目不提供 MCP Server，最终边界仍为入库前文件产物。

#### 阶段 4 Step 0 样本/fixture 矩阵

| 场景 | 输入/基线 | 可执行命令 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|---|
| 主样本最终包 | `pdf/春风250Sr` | `scripts/pdf-check-fixes pdf/春风250Sr`；配套 Python 统计页锚点、TOC、ready/skipped、冲突和 batch | 检查退出 0；138 页锚点、120 TOC、179 ready、3 skipped、0 冲突、179 导出 | 任一门禁失败、数字 key 混入或数据库写入 | `pdf/春风250Sr/`、`data/ingest_batch.jsonl`、`data/ingest_manifest.json` |
| 异常 `<td>`/跨页表格 | `pdf/demo20`、`tests/test_table_repair.py`、`tests/test-fix-validate.sh` | `python -m pytest -q tests/test_table_repair.py`；`bash tests/test-fix-validate.sh` | 候选、人工修复记录、跨页分组、apply/reject、幂等和回滚契约通过 | 结构化候选丢失、未审批放行、重复写入或失败不回滚 | `pdf/demo20/data/`、临时 fixture 输出 |
| 无业务表格/布局页 | demo20 p4/p10 与页质量测试 | `python -m pytest -q tests/test_page_quality.py -k 'p4_body_text_no_false_positive or p6_no_table_no_false_positive'` | 无 HTML 表格时不触发 `native_table_text_missing`，不强行结构化 | 无表格页产生修复候选或漏报边界失效 | 测试输出 |
| 动态 helper 安全边界 | 临时目录 fixture，不触碰真实 PDF 包 | `python -m pytest -q tests/test_pdf_run_helper.py` | 8 个 fixture 全部通过，dry-run/apply/validate、快照回滚、allowlist 和门禁保护有效 | 原始证据或审批产物可被修改，或验证失败不能回滚 | 测试临时目录、JSON 摘要 |
| 旧入口兼容 | 项目级/用户级两组 skill | `cmp -s skills/pdf2md-fix/SKILL.md /Users/jafish/.claude/skills/pdf2md-fix/SKILL.md && cmp -s skills/pdf2md/SKILL.md /Users/jafish/.claude/skills/pdf2md/SKILL.md`；`rg` 兼容词和第二套流程标记 | 旧触发词存在且导向 `pdf2md`，无第二套详细流程 | skill 漂移、旧入口消失或产生第二套结果 | skill 文件与静态检查输出 |

#### 阶段 4 Step 0 验证方式、完成条件与回滚

- 阶段 4 实施前先复核主样本和代表性 fixture 的 hash、manifest、审核状态和入库前导出集合；真实协作中的每个用户确认必须能回溯到 PDF 页或记录。
- 完成条件：用户只确认 PDF 事实、表格关系和候选状态；LLM 完成脚本编排、配置同步、验证和交付摘要；最终 Markdown、manifest、`manual_fixes.jsonl`、`extraction_overrides.json`、`review_overrides.csv` 和入库前 batch 一致；没有数据库写入。
- 失败策略：任一自动处理、动态 helper、配置同步或导出门禁失败，保留失败 JSON 摘要并恢复最近备份；不把失败候选标为 `approved`/`ready`，不覆盖原始证据。
- 阶段 4 通过后才进入阶段 5 的兼容策略决策；阶段 4 不删除 `pdf2md-fix`，不新增 MCP。

#### 阶段 4 Step 0 独立准入复核（2026-07-15）

结论：通过，达到 `待实施` 标准；阶段 4 尚未实施。

证据：主样本最终包、异常表格样本、无业务表格页、动态 helper fixture 和旧入口兼容基线均有可执行命令与失败判定；主样本统计为 138 页锚点、120 TOC、179 ready、3 skipped、0 冲突、179 导出；`scripts/pdf-check-fixes`、175 个相关 pytest、8 个 helper fixture 和 133/133 修复回归均通过；阶段 4 的用户审批、no-MCP、no-database 和原始证据保护边界已冻结；无阶段 4 准入阻塞。

### 迁移策略

1. 在项目级 `skills/pdf2md/SKILL.md` 中加入解析后人工协作、动态辅助脚本和入库前准备章节；
2. 将 `skills/pdf2md-fix/SKILL.md` 收敛为兼容说明，指向 `pdf2md` 的统一流程，不再维护第二套事实；
3. 同步 `/Users/jafish/.claude/skills/pdf2md/SKILL.md` 和 `/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md`；
4. 更新本计划与 `PLAN_MAP.md`，记录“能力已合并、兼容入口保留”的关系；`pdf2md-fix-manual-workflow` 继续作为历史能力和字段事实源，不复制或改写；
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

- 阶段 1、阶段 2 和阶段 3 已完成；阶段 4 Step 0 已通过，当前没有实施阻塞，等待明确开始真实协作验收。
- 动态脚本默认只保留在临时目录；需要复现时登记包级副本，并保留 hash、命令和验证结果。
- LLM 每轮交付摘要继续使用事务包装器输出的机器可读 JSON；尚未形成需要独立版本化的外部 Schema。
- 阶段 3 兼容窗口结束条件已冻结为阶段 4/5 独立验收完成后再决定 `已合并` 或 `已废弃`；当前不删除兼容入口。

## 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 日期 | 2026-07-15 |
| 阶段 | 阶段 4：真实 PDF 协作验收 |
| 结论 | 通过：阶段 4 Step 0 达到 `待实施` 标准；阶段 4 尚未实施 |
| 证据 | 阶段 3 独立验收已完成；阶段 4 主样本、异常表格、无业务表格、动态 helper 和旧入口兼容矩阵均冻结并可执行；真实包检查、相关 pytest、133/133 修复回归通过 |
| 复核者 | 独立验收复核 |

## 独立复核记录

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-07-14 | 独立治理复核 | 阶段 0：协作契约与基线冻结 | 通过：达到阶段 0 实施标准；阶段 0 已关闭 | skill hash 一致；真实包 `pdf-check-fixes` 通过；临时副本抽取/审核/导出通过；182 行、179 ready、3 skipped、0 not_ready、0 冲突、0 数字 key |
| 2026-07-14 | 独立治理复核 | 阶段 1：统一 `pdf2md` 编排入口 | 通过：达到阶段 1 实施标准；阶段 1 进入实施 | 两个 skill 的内容映射完成；`pdf2md` 主入口、用户确认边界、LLM 交付摘要、动态脚本安全契约和阶段 3 兼容迁移边界已明确 |
| 2026-07-15 | 独立治理复核 | 阶段 1：统一 `pdf2md` 编排入口 | 通过：阶段 1 独立验收完成；阶段 2/3 尚未启动 | skill hash 同步；主入口章节存在；真实包检查、304 pytest、133/133 修复回归和 `git diff --check` 通过；`pdf2md-fix` 未被改写 |
| 2026-07-15 | 独立治理复核 | 阶段 2：动态辅助脚本安全执行层 | 通过：阶段 2 Step 0 达到实施标准，阶段 2 进入实施；阶段 3 尚未启动 | 现有回滚/幂等基线已复核；动态命令接口、allowlist、原始证据保护、整包快照、dry-run、JSON 留痕、失败回滚、幂等和晋升规则已冻结；成功/越界/失败/重复运行 fixture 命令已登记 |
| 2026-07-15 | 独立验收复核 | 阶段 2：动态辅助脚本安全执行层 | 不通过 | 5 个 helper fixture、309 pytest、133/133 修复回归和真实包检查通过；`pdf-run-helper` 缺少 apply 后验证入口，且没有审批/入库前门禁的可复现证明；已登记补齐条件，阶段 3 保持未启动 |
| 2026-07-15 | 独立验收复核 | 阶段 2：动态辅助脚本安全执行层 | 通过：修复后阶段 2 独立验收完成并关闭；阶段 3 尚未启动 | 8 个 helper fixture、312 pytest、133/133 修复回归、真实包检查和 skill 同步通过；`--validate-command`、验证失败回滚和 5 类审批/入库前门禁保护已验证 |
| 2026-07-15 | 独立准入复核 | 阶段 3：`pdf2md-fix` 兼容迁移 | 通过：阶段 3 Step 0 达到 `待实施` 标准；阶段 3 尚未实施 | 两份 `pdf2md-fix` skill hash/cmp 一致；`pdf2md` 统一主入口存在且同步；兼容窗口、唯一事实源、回滚边界和旧入口替代基线已冻结；真实包和回归基线通过 |
| 2026-07-15 | 独立验收复核 | 阶段 3：`pdf2md-fix` 兼容迁移 | 通过：阶段 3 独立验收完成；阶段 4 保持 `设计中` | 两份兼容 skill 及两份主入口 skill hash/cmp 一致；未发现第二套详细流程、规范性草案事实源或计划外文件变化；真实包检查、312 pytest、133/133 修复回归通过 |
| 2026-07-15 | 独立准入复核 | 阶段 4：真实 PDF 协作验收 | 通过：阶段 4 Step 0 达到 `待实施` 标准；阶段 4 尚未实施 | 主样本、异常表格、无业务表格、helper 安全和旧入口兼容矩阵均已冻结；真实包检查、175 个相关 pytest、133/133 修复回归通过；无阶段 4 准入阻塞 |

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
