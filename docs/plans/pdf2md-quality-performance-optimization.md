# 计划：pdf2md 质量与性能优化机会评估

## 计划状态

- 状态：实施中
- 当前阶段：阶段 2：VLM sidecar 按需覆盖优化
- 最后更新：2026-07-24
- 计划定位：协调既有 VLM 评测、质量分流和表格修复能力的后续优化，不替代已完成专项计划的事实源。

本计划的状态、当前阶段、依赖、推荐顺序和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准；本文件承载本计划的范围、样本矩阵、阶段门禁、验证方式和完成条件。

## 需求探索

### 已确认事实

- 用户希望评估并规划三类优化：
  1. 图片、图表、扫描页的 VLM sidecar 证据增强；
  2. 减少误报和无效 high fallback；
  3. 表格语义、表头、列关系和跨页表格关联增强。
- 单页 canonical 输出是既定边界：它服务于 page node、chunk、页级 fallback、来源追溯和下游结构化抽取；不因性能优化改成多页 canonical 输出。
- MinerU 当前固定为 3.4.4，主解析使用 `hybrid-engine + medium`，异常页使用页级 `high`；不以全量 `high` 作为默认优化方案。
- 当前项目只维护 CLI 执行层，不新增 MCP Server 或兼容层。

### 暂定假设

- 速度收益主要来自减少无效重跑、减少重复服务启动和评估是否存在安全的内部批处理，而不是改变 canonical 分页粒度。
- 视觉增强应继续保持 sidecar/证据边界，不直接覆盖 canonical Markdown，不直接改变 chunks 或入库状态。
- 表格语义和跨页关联只有在真实下游结构化消费中反复出现时，才值得进入高成本通用实现。

### 候选方案与取舍

| 方向 | 候选方案 | 主要收益 | 主要成本/风险 | 当前判断 |
|---|---|---|---|---|
| VLM 视觉增强 | 扩大现有 `pdf-eval-vlm` sidecar 覆盖，保持只读证据 | 补充图片、图表、截图和扫描页理解 | VLM 时间/内存；不能直接当最终事实 | 值得按需扩展 |
| fallback 分流 | 优化页面类型、触发信号和重跑预算 | 减少无效 high 调用，降低总耗时 | 误判可能漏掉真正异常页 | 优先评估 |
| 表格语义 | 针对真实跨页表格建立上下文证据和结构关联 | 提高结构化抽取和入库质量 | 需要样本标注、Schema 和人工边界 | 条件性推进 |
| canonical 多页化 | 解析、输出和 chunk 改为多页粒度 | 可能减少 API 调用 | 破坏 page node、来源追溯和既有消费者 | 明确不做 |

### 未决问题

- 当前真实 PDF 运行中，VLM sidecar 的调用量、耗时和人工采纳率是否足以证明需要扩大覆盖？
- 当前 `pdf-auto` 是否仍存在可通过规则消除的无效 fallback；现有历史计划已完成基础分流，但尚未形成新的持续运行统计。
- 跨页表格优化的目标是 Markdown 阅读、结构化抽取，还是入库字段完整性；不同目标会导致不同 Schema 和验收方式。

## 目标

1. 用可复现真实样本建立三类优化的速度、质量、资源和人工复核基线。
2. 优先落地低风险、高 ROI 的 fallback 分流和 sidecar 使用优化。
3. 仅在跨页表格样本证明收益足够时，设计受限的上下文关联能力。
4. 保持单页 canonical、page node、chunks、manifest、CLI JSON 和人工审核边界兼容。

## 非目标

- 不把 `MINERU_SEGMENT_SIZE` 默认改回多页。
- 不把所有页面切换为 `effort=high`。
- 不提高 macOS MinerU API 并发作为默认方案；现有服务端单并发证据仍有效。
- 不让 VLM 输出直接覆盖 MinerU Markdown、`content_list`、`middle.json` 或入库前审核状态。
- 不在本计划中实现数据库导入、远程队列或 MCP Server。
- 不复制已完成计划中的字段 Schema、表格修复契约或 VLM sidecar 契约；如需变更，更新对应事实源并在本计划引用。

## 不变量与安全边界

- 原始 PDF、原始 segments、MinerU 中间产物不可被优化实验覆盖。
- 所有性能实验使用临时副本或新的临时输出目录，保留输入 hash。
- canonical Markdown 只能由现有合并/修复契约生成；视觉证据和候选表格关联默认派生到 `data/`，不得成为第二个事实源。
- fallback 每页最多一次；失败、无法判断或证据冲突时保留原始结果并进入 `review`/`needs_review`。
- 任何新增输出包字段、状态或 CLI JSON 字段，必须先更新本计划、项目级 `skills/pdf2md/SKILL.md`，再同步 `/Users/jafish/.claude/skills/pdf2md/SKILL.md`。
- 任何代码符号修改前执行 GitNexus upstream impact；实现完成后执行 `detect_changes()`、专项回归、全量测试和治理检查。

## 影响模块或文件

### 可能涉及的实现

- `scripts/pdf-auto`
- `scripts/pdf-validate`
- `scripts/pdf-rerun`
- `scripts/pdf-eval-vlm`
- `scripts/lib/vlm_eval.py`
- `scripts/lib/page_quality.py`
- `scripts/pdf-table-fix`
- `scripts/pdf-extract-data`
- `scripts/pdf-prepare-ingest`
- `scripts/pdf-export-ingest`

### 事实源和验证入口

- `skills/pdf2md/SKILL.md`
- `docs/PLAN_MAP.md`
- `docs/plans/coverage-validation-optimization.md`
- `docs/plans/pdf-evaluation-suite.md`
- `docs/plans/table-text-omission-detection.md`
- `docs/plans/pdf-table-audit.md`
- `docs/plans/pdf-table-repair.md`
- `docs/plans/pdf-extract-data-table-coverage.md`
- `docs/plans/pdf2md-fix-manual-workflow.md`
- `tests/`
- `test-phase3.sh`
- `scripts/test-fix-validate.sh`

## 公共契约策略

当前阶段不新增公共字段或状态。

候选增量仅限于：

- 既有 `manifest.page_fallback` 中已有指标的统计汇总；
- 既有 `data/vlm_eval.jsonl` 的调用统计或外部报告，不改变已完成的 8 字段视觉描述契约；
- 临时基准报告，不进入 canonical 输出包。

如阶段 2/3 需要新增 Schema，必须在对应阶段单独冻结字段、枚举、hash、幂等和回滚契约，并同步项目级与用户级 skill。

## 价值与优先级

| 优先级 | 方向 | 预期投入 | 预期收益 | 准入原则 |
|---|---|---:|---:|---|
| P1 | fallback 误报/无效调用统计与分流 | 低～中 | 中～高，直接减少耗时 | 有真实运行统计证明仍存在可消除的无效调用 |
| P1 | VLM sidecar 按页面类型按需覆盖 | 低～中 | 中～高，增强视觉证据 | 不改变 canonical，Schema 和失败门禁沿用 P4c |
| P2 | 跨页表格上下文和语义关联 | 高 | 高，但只对结构化消费显著 | 至少一组真实跨页表格样本证明当前下游损失 |
| 禁止 | 多页 canonical 取代单页输出 | 高 | 不确定 | 会破坏 page node/chunk 契约，不进入候选 |

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 主要产物 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 固定 ROI 基线、样本矩阵和准入门槛 | 既有证据已复核，补充当前可复现实验 | 基准报告、指标定义、独立准入复核 | 已完成 |
| 阶段 1 | fallback 预算与误报分流复核 | 阶段 0 达到 `待实施` 标准 | 统计/规则调整、回归证据 | 已完成 |
| 阶段 2 | VLM sidecar 按需覆盖优化 | 阶段 0 证明视觉页收益超过资源成本 | sidecar 调度或报告增强 | 实施中 |
| 阶段 3 | 跨页表格上下文/语义关联 | 阶段 0 样本证明结构化收益，且独立准入通过 | 受限上下文证据或候选关联产物 | 设计中 |
| 阶段 4 | 全量验收与治理收尾 | 阶段 1～3 的实际实施范围确定 | 完成证据、回归、skill/PLAN_MAP 同步 | 设计中 |

阶段 1～3 不因阶段 0 完成而自动进入 `待实施`；每个阶段必须拥有独立 Step 0、样本矩阵、验证方式、完成条件和准入复核。

## 当前阶段

阶段 2：VLM sidecar 按需覆盖优化。阶段 1 已独立验收通过；阶段 2 已完成 Step 0、资源收益评估和独立准入复核，按用户确认的保守边界进入实施。

### 阶段准入摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 实施中 |
| Step 0 | V1/V2 已确认 23 页视觉样本的耗时、客户端/服务端资源参考、Schema/失败门禁、分类一致性和初步人工主要内容一致性；V3/V4 已完成失败门禁、canonical 不变性和固定响应幂等性验证。 |
| 样本矩阵 | V1 13 页 VLM 抽样；V2 春风 150AURA 97 个视觉页的按页面类型分层抽样；V3 VLM 失败/低置信度/Schema 异常 fixture；V4 canonical 不变性和 sidecar 幂等性检查。 |
| 验证方式 | 记录 sidecar 页数、单页/P95 耗时、峰值内存、Schema 成功率、失败率和人工主要内容一致性；对照不调用 sidecar、按需调用和扩大调用三组结果。 |
| 完成条件 | 明确按需筛选和资源门槛；失败不静默放行；不改变 canonical、page node、chunks 和 manifest 主状态；项目级与用户级 skill 边界保持同步。 |
| 失败/回滚边界 | VLM 服务失败、超时、Schema 失败或低置信度时写入失败/review 证据，不覆盖主输出；关闭 sidecar 调度即可回退，不删除原始解析结果。 |
| 当前阻塞项 | 无；按需调度实施不改变 canonical、page node、chunks 和 manifest 主状态。 |
| 最新独立准入复核 | 2026-07-24：用户确认保守调度边界，达到 `待实施` 标准；阶段 2 进入实施。 |

### 阶段 2 Step 0 证据（2026-07-24）

- V1 真实抽样：13 个 `image_or_sparse` 页，VLM sidecar 总墙钟时间 174.90 秒，约 13.5 秒/页；12 页 `ok`、1 页 `failed`；所有输出行包含既有必需字段，失败行明确为 `parse_status=failed`。
- V1 运行时 `/usr/bin/time -l` 记录客户端最大常驻内存 162,070,528 bytes（约 154 MiB）；VLM 服务端为本地 `qwen3-vl-8b` 8bit，沿用既有评测记录的约 10.99 GiB 峰值作为资源预算上限参考。
- 分类门禁：统一口径后，VLM helper 与 `pdf-validate` 的视觉页集合完全一致，均为 13 页；不会因分类漂移额外调用 sidecar。
- 不变性：实验只写 `/tmp/pdf2md-opt-dr90LS/vlm10`，未修改 canonical Markdown、page node、chunks、manifest 主状态或真实 PDF 包。
- 人工抽查：对 p43、p44、p48 做整页渲染核对。p43/p44 的标题、表格主题、操作步骤、注意事项和示意图用途与页面一致；p48 的关键字段“锁具/油箱锁/上电解锁/下电解锁/A/1”一致，但摘要将摩托车油箱锁泛化为“汽车油箱锁”，记录为措辞不精确的 review 风险，不作为自动采纳依据。
- 失败样本：p42 返回 `parse_status=failed`，错误为 VLM API 或 JSON 无效；该失败被显式保留，没有生成可误认为有效内容的视觉结论。
- V2 分层抽样：从 helper 实际识别的 97 个视觉页中跨文档位置抽取 p13、p31、p42、p61、p78、p94、p110、p146、p168、p186；10 页中 9 页 `ok`、1 页 `failed`，总墙钟时间 150.88 秒，约 15.1 秒/页，客户端最大常驻内存 172,933,120 bytes（约 165 MiB）。失败页为 p13，明确记录为 API/JSON 失败。
- V1+V2 合并样本共 23 页，21 页 `ok`、2 页 `failed`，成功率 91.3%；所有 23 行均保留既有必需字段，失败行没有伪造视觉结论。V2 人工抽查 p31、p78、p168：车辆部件视图、仪表截图说明、后制动油杯示意图与页面主要内容一致。
- V3 失败/Schema 门禁：`python -m pytest -q tests/test_vlm_eval.py` 为 40 passed；覆盖 API 异常、非 JSON、缺字段、字段类型错误、置信度越界和视觉元素结构错误。两次真实抽样的失败行均包含 `parse_status=failed` 与错误信息。
- V4 不变性：两次真实抽样只在临时包的 `data/vlm_eval.jsonl` 写入 sidecar 结果；canonical Markdown、page node、chunks、manifest 主状态和源 PDF 未被修改。固定上游响应的同一临时包连续运行两次，`vlm_eval.jsonl` SHA-256 相同、源 PDF hash 不变（10/10 `ok`）；真实 VLM 的随机响应不承诺字节级相同，仍按 sidecar 证据幂等和 canonical 不变性处理。
- 当前结论：按需 sidecar 有明确证据，但按本次均值全量处理 97 个视觉页约需 22 分钟，且还要承担服务端内存压力；不进入默认全量调度，按用户确认的单批最多 10 页保守策略实施。

### 阶段 2 实施契约（2026-07-24，用户确认）

- 调度范围：仅处理共享分类器识别出的 `image_or_sparse` 页，或用户显式指定的页；不对普通文本页和目录页自动调用 VLM。
- 批次上限：单次 sidecar 最多处理 10 页；超过上限时明确返回 `needs_review`/非零结果，不静默截断或扩大调用范围。
- 失败门禁：VLM 服务失败、超时、非 JSON、Schema 不完整或低置信度结果进入 `failed`/`review`，不自动升级为有效事实。
- 输出边界：只写 `data/vlm_eval.jsonl` 等 sidecar 证据；不覆盖 canonical Markdown、page node、chunks、manifest 主状态和入库状态。
- 回滚边界：关闭 sidecar 或删除 sidecar 派生产物即可回到现有 MinerU 主链，不删除原始解析结果；不新增并发，保持顺序调用。

### 阶段 2 实施证据（2026-07-24）

- `scripts/lib/vlm_eval.py` 新增显式页选择解析和单批上限门控：默认自动识别页超过 10 页时非零退出；`PDF_EVAL_VLM_PAGES` 覆盖自动识别但仍受 `PDF_EVAL_VLM_MAX_PAGES` 约束。
- 实测默认 97 页包返回 `exit=2`，未调用 VLM；显式 `PDF_EVAL_VLM_PAGES=31,78` 只处理 2 页，失败行仍保留 `parse_status=failed` 和错误信息。
- 失败/Schema 结果仍只写 sidecar JSONL；未增加 canonical、page node、chunks 或 manifest 主状态写入路径。
- 项目级 `skills/pdf2md/SKILL.md` 已更新并与用户级 `/Users/jafish/.claude/skills/pdf2md/SKILL.md` 字节同步。

### 阶段 1 历史实施矩阵

| 编号 | 输入/基线 | 可执行命令 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|---|
| S1 | `/tmp/pdf2md-opt-dr90LS` demo20 基线 | `jq` 统计 `auto.json` 的 `page_fallback`；对照 `segments/` 原始与 `*-fallback/` | 复现 11 次触发、2 次 fallback 选中、9 次 review | 统计无法从 manifest/JSON 复现，或原始/候选路径缺失 | `/tmp/pdf2md-opt-dr90LS/auto.json`、`manifest.json` |
| S2 | 春风 150AURA 191 页当前包 | `PDF_VALIDATE_JSON=1 scripts/pdf-validate ...` | 复现页面类型、review_only、rerunnable 分布 | 页类型缺失或与当前基线无法解释 | 阶段 0 临时 `aura-validate.json` |
| S3 | 14 页 VLM 抽样和同一 segments | 对照 `pdf-validate` 与 `scripts/lib/vlm_eval.py` 的视觉页集合 | 分类差异可定位；统一后调用集合不扩大到全量视觉页 | 差异无法定位，或统一导致文本页进入 sidecar | `/tmp/pdf2md-opt-dr90LS/vlm10/` |
| S4 | 现有单元、阶段和修复回归 fixture | `python -m pytest -q`；`bash test-phase3.sh`；`bash tests/test-fix-validate.sh` | 全部通过，输出契约不变 | 任一回归失败，暂停规则实施并回退 | pytest/脚本 stdout |

### 阶段 1 历史实施记录（2026-07-24）

- 新增 `scripts/lib/page_type.py`，统一中英文 token、目录页和 `image_or_sparse` 判定口径。
- `scripts/lib/vlm_eval.py` 改为复用共享视觉页判定；`scripts/pdf-validate` 改为复用共享 token/页面判定；`scripts/pdf-auto` 在质量 fallback 前跳过目录页和视觉/稀疏页，将其保留给 `review_only`/VLM sidecar 路径。
- demo20 同一份已完成单页分段的 A/B 结果：fallback 触发从 11 页降至 4 页（减少 7 次，约 63.6%）；最终 `selected=fallback` 仍为 2 页，未观察到纯文本页漏检；4 页分别为 p12、p14、p15、p16。
- VLM helper 与 `pdf-validate` 在 14 页抽样上的视觉页集合已完全一致，均为 13 页；中文连续文本 fixture 通过。
- 契约边界未变化：不新增 manifest/CLI JSON 字段，不改变 `data/vlm_eval.jsonl` 8 字段契约，不覆盖 canonical Markdown、page node、chunks 或入库状态，因此本阶段不触发 skill 契约同步。

### 阶段 1 历史实施验证与验收证据

- 已通过：`tests/test_vlm_eval.py` 40 passed；demo20 gated `pdf-auto` 返回 `needs_review`/exit 2，4 次 fallback 均完成，2 页选中 fallback、2 页 review；VLM/验证器视觉页集合一致。
- 已通过：全量 `python -m pytest -q` 为 `368 passed, 5 warnings`；`bash tests/test-fix-validate.sh` 为 `133/133`；`bash test-phase3.sh` 为 `4/4`；`git diff --check` 和严格治理检查通过。
- GitNexus `detect_changes()`：整体风险 `medium`（包含治理文档）；唯一受影响执行流为 `eval_vlm_package → _is_image_or_sparse_page`，代码路径风险为 LOW；未发现计划外高风险流程。
- 阶段 1 已完成独立实施验收；阶段 2 VLM sidecar 不进入默认调度，阈值和并发不继续调整。

## 阶段 0：ROI 基线与实施准入设计

### 当前阶段准入摘要

- 准入状态：已完成
- Step 0：已有历史基线，但需要用当前仓库和当前 ModelPad 配置重新确认可复现性。
- 样本矩阵：B1～B5 已执行，输入、命令、预期结果、失败判定和输出位置已追加证据。
- 验证方式：同时记录墙钟时间、MinerU 请求/重跑次数、fallback 选择结果、VLM 资源、表格结构指标和人工复核结果。
- 完成条件：已满足；阶段 0 关闭，不自动改变阶段 2/3 的准入状态。

### 阶段 0 执行记录（2026-07-24）

- 已开始执行 B1～B5 基线取证；实验仅使用临时副本和临时输出目录，不修改 canonical PDF 包和代码。
- 阶段 0 已形成基线结论；独立准入复核已通过，阶段 1 按用户确认进入实施。
- 失败/回滚边界：实验只写临时目录；任何候选实现失败时恢复原始 segments/canonical，不改变审批或入库状态。
- 当前阻塞项：无阶段 0 阻塞项。
- 最新独立准入复核：2026-07-24，阶段 0 通过；同时确认阶段 1 达到 `待实施` 标准。

### 阶段 0 基线证据（2026-07-24）

实验根目录：`/tmp/pdf2md-opt-dr90LS`。输入 PDF 的 SHA-256 为 `a69c1e4cecbedcbab870770cd577a0a2e4b40eccb55c0b4bee497380c6d4287a`；实验未覆盖仓库原始 PDF、segments、canonical Markdown 或入库文件。

| 编号 | 当前结果 | 解释 |
|---|---|---|
| B1 demo20 | 20/20 单页分段成功；20 次 MinerU 请求；分段请求时间跨度约 359 秒；`pdf-auto` 墙钟 85.91 秒，用户态 27.52 秒，系统态 4.44 秒，最大常驻内存 366,247,936 bytes（约 349 MiB）。11 页完成 fallback，最终 2 页选择 `fallback`、9 页选择 `review`；fallback 全部使用 `high + image_analysis=false`。 | high 调用确实能产生候选，但多数异常页不适合自动晋级；优化优先级应放在更早识别 `review_only`、减少无效 high，而不是全量 high。 |
| B2 春风 150AURA | 191 页、24 个分段；`image_or_sparse=97`、`table=63`、`text=24`、`toc=7`；`decision=review_only` 115 页、`pass` 75 页、`rerun` 1 页。 | 真实样本中视觉页很多，但现有分流已经把绝大部分视觉页放在 review 边界，默认全量 VLM 的成本收益不足。 |
| B3 VLM sidecar | 临时抽取 2 个真实分段，共 14 页 sidecar 调用；13 页 `ok`、1 页 `failed`；必需字段均存在，失败行有明确 `parse_status=failed`。 | sidecar 的证据链和失败门禁有效，但必须记录失败率和资源成本；不应覆盖 canonical。另发现 `pdf-validate` 将同一抽样识别为 13 个视觉页，VLM helper 识别为 14 个，分类口径存在漂移。 |
| B4 表格/结构化 | demo20 发现 4 个页级候选（`mixed=2`、`native_missing=2`），结构化草案 19 行；150AURA 临时副本抽取 379 行，其中 347 `draft`、32 `needs_review`，49 行覆盖多页范围；候选扫描因 manifest 无 `page_fallback` 未产生候选。 | 当前能力能提供候选、页锚点和人工门禁，但尚无足够证据证明自动跨页关联值得通用化；150AURA 的页码映射仍为 `needs_review`，跨页结果不能直接放行。 |
| B5 分阶段耗时 | B1 已保存分段请求日志、自动流程阶段耗时和 `/usr/bin/time -l` 资源数据；分段阶段远高于 merge/TOC/review 阶段。 | 当前主要成本在逐页 MinerU 请求；merge 与审核清单不是主要瓶颈。 |

补充记录：B1 的外层 zsh 采集脚本曾误用只读变量名 `status`，导致包装器返回 1；`auto.json` 内部结果仍明确为 `status=needs_review`、`exit_code=2`，不属于流水线自身失败，后续复现实验改用 `rc` 变量。

回归门禁：`python -m pytest -q` 为 `366 passed, 5 warnings`；`bash tests/test-fix-validate.sh` 为 `133/133`；`bash test-phase3.sh` 为 `4/4`；`plan-governance-cli check . --strict-readiness` 和 `git diff --check` 均通过。本轮没有代码、配置、构建产物或真实 PDF 包改动。

### 阶段 0 基线结论（暂定）

- 阶段 1（fallback 分流）：保持 P1，但先做分类口径统一和无效调用统计，不立即改阈值或放宽/收紧 fallback。
- 阶段 2（VLM sidecar）：保持 P1，继续按 `image_or_sparse`/用户指定页按需调用；新增的第一候选是统一验证器与 VLM helper 的页面分类函数或共享口径。
- 阶段 3（跨页表格）：降为条件性 P2；当前证据支持“候选/证据报告”，不足以支持自动关联或新增 Schema。
- 单页 canonical、page node、chunks 和 CLI-only 边界不变。

### 现有 Step 0 证据

- `demo20` 历史基线显示首次 20 页中 11 页通过，目录、图片主导页等低覆盖不适合用 high 直接修复；high/medium 普通文本覆盖率没有稳定差异。见 [coverage-validation-optimization](coverage-validation-optimization.md#step-0-证据已收集2026-06-28)。
- `demo20` 页级 fallback 已有真实证据：p12 空 `<td>` 从 16,311 降到 0，p15 从 8,192 降到 4；fallback 保留原始和候选双目录。见 [single-page-segmentation-migration](single-page-segmentation-migration.md#最终验收2026-07-11)。
- fallback 并发实验约节省 11%，macOS MinerU FastAPI 仍强制单并发，因此“提高并发”暂不作为默认优化。见 [single-page-segmentation-migration](single-page-segmentation-migration.md#端到端验收demo20-2026-07-11)。
- P4c 已完成 `image_or_sparse` 页 VLM sidecar：10 页混合抽样 JSON/Schema 10/10 通过；现有契约为 `data/vlm_eval.jsonl`，不覆盖 canonical。见 [pdf-evaluation-suite](pdf-evaluation-suite.md#验收记录p4c2026-07-10)。
- 当前单页 canonical 是既有 page node/chunk 和 fallback 的共同粒度，单页迁移计划已完成验收；本计划不重新打开该架构决策。

### 阶段 0 样本矩阵

以下命令均应使用临时副本，不能直接覆盖仓库内真实输出包。`<probe>` 表示本轮实验创建的临时目录。

| 编号 | 输入/基线 | 可执行命令 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|---|
| B1 | `pdf/demo20/demo20.pdf`，含目录、图片页、表格异常页 | `scripts/pdf-seg <probe>/demo20.pdf`；`PDF_AUTO_JSON=1 /usr/bin/time -l scripts/pdf-auto <probe>/demo20.pdf <probe>/segments > <probe>/auto.json` | 记录总耗时、分段数、fallback 次数、selected 结果、最终 action | 输出非法 JSON、输入 hash 变化、canonical/manifest 与候选不同源、流程非预期失败 | `<probe>/auto.json`、`<probe>/manifest.json`、`<probe>/review.md`、`<probe>/time.txt` |
| B2 | `pdf/春风 150AURA`，混合文本/表格/图片页 | `PDF_VALIDATE_JSON=1 scripts/pdf-validate <probe>/春风\ 150AURA.pdf <probe>/segments > <probe>/validate.json`；按需执行 `PDF_EVAL_VLM_JSON=1 scripts/pdf-eval-vlm <probe>` | 统计各 `page_type` 的数量、review、fallback 和 VLM sidecar 成本 | 页面分类缺失、VLM 失败未进入明确状态、输出包被覆盖 | `<probe>/validate.json`、`<probe>/data/vlm_eval.jsonl` |
| B3 | 至少 10 个 `image_or_sparse` 页 | `PDF_EVAL_VLM_JSON=1 scripts/pdf-eval-vlm <probe>` | JSON 解析成功率、Schema 完整率、人工主要内容一致性、每页耗时/峰值内存可记录 | 任一必填字段缺失、解析失败未标记、明显视觉误判未进入 review | `<probe>/data/vlm_eval.jsonl`、人工抽样报告 |
| B4 | 至少 10 个含表格页，其中包含跨页候选 | `scripts/pdf-table-fix <probe>`；`scripts/pdf-extract-data <probe>`；对照 `data/extraction-coverage.csv`、`data/table_accuracy.csv` 和 `manifest.page_fallback` | 记录空单元格、列数、表头、跨页身份、结构化候选缺口和人工处置 | canonical 被改写、候选无法追溯到页锚点/表行、跨页关联无证据却自动放行 | `<probe>/data/`、`<probe>/manifest.json`、差异报告 |
| B5 | 单页速度基线 | 在 B1 中分别记录首次服务启动、MinerU 请求、fallback、merge、VLM sidecar 的墙钟时间；不得先改变配置 | 得到分阶段耗时占比和 P95/单页均值 | 只记录总耗时，无法区分服务/解析/验证/重跑成本 | `<probe>/timing.json` |

### 阶段 0 指标

性能指标：

- 总墙钟时间、首次启动时间、服务复用时间；
- MinerU 请求次数、页数、单页平均耗时和 P95；
- fallback 尝试数、成功数、选中数、review 数、失败数；
- VLM sidecar 页数、平均耗时、P95、峰值内存和失败率；
- 输出包大小和中间产物数量。

质量指标：

- `page_type` 分类与人工抽样一致性；
- `selected=original|fallback|review` 分布；
- 文本覆盖率仅用于适用页面，不跨页面类型比较；
- 表格空 `<td>`、列数一致性、表头保留、跨页关联证据；
- VLM JSON/Schema 成功率和人工主要内容一致性；
- 结构化抽取的 covered/missing/needs_review 分布，不以“无候选”直接判定无业务意义。

阶段 0 不预先冻结性能提升百分比。完成 B1～B5 后，独立复核者再确认各阶段的收益门槛和是否进入 `待实施`。

## 阶段 1：fallback 预算与误报分流

### 目标

- 仅对有证据表明可以改善的页面执行 high fallback。
- 将重复失败、低覆盖但不可比较、视觉主导页的成本转为 review 或 sidecar。
- 保持现有 `manifest.page_fallback`、原始/候选双目录和 `needs_review` 契约。

### 候选范围

- 先统计当前 `rerunnable`、`review_only`、`selected` 和 `fb_status`；不先改变阈值。
- 对连续多次无改善的页面类型增加统计型豁免或更精确检测，必须有样本支持。
- 对服务启动/停止、重复验证和重复 sidecar 调用做缓存或批次编排评估；不改变用户可见输出路径。

### 不纳入本阶段

- 不提高 API 并发；已有 macOS 单并发证据保持有效。
- 不改为多页 canonical；不在这里解决跨页语义。
- 不把 `high + image_analysis=true` 作为文本/表格 fallback 的默认参数。

### 完成条件（阶段 1 Step 0 已冻结）

- 真实样本可复现统计 fallback 成本和收益；
- 无效 high 调用数或占比有可解释下降，且没有新增已知纯文本漏检；
- 原始/fallback/review 选择和跨次幂等回归全部通过；
- 失败仍保持原始结果和可诊断 review，不修改审批/入库状态。

## 阶段 2：VLM sidecar 按需覆盖优化

### 目标

- 复用已完成的 `pdf-eval-vlm` 与 `data/vlm_eval.jsonl` 契约；
- 只对 `image_or_sparse`、扫描件、图表密集页或用户指定页调用；
- 将视觉结果作为证据、摘要和人工复核入口，不成为 canonical 事实源。

### 候选范围

- 依据 B2/B3 的收益和成本，调整调用筛选或批次编排；
- 记录 VLM 失败、低置信度和 Schema 解析失败，进入 review；
- 评估 VLM sidecar 与结构化抽取的衔接，但不直接批准业务字段。

### 完成条件（阶段 2 实施契约已冻结）

- sidecar 不改变 canonical Markdown、page node、chunks 和 manifest 主状态；
- Schema 解析成功/失败路径可审计，失败不静默放行；
- 视觉页面人工抽样收益超过固定资源预算；
- 项目级 skill 与用户级 skill 对产物和边界同步。

## 阶段 3：跨页表格上下文与语义关联

### 目标

- 在不改变单页 canonical 的前提下，为跨页表格提供上下文证据；
- 支撑表头、续表、列关系和结构化抽取缺口的判断；
- 默认输出候选/证据，无法稳定确认时进入人工或 LLM 审核。

### 候选范围

- 仅针对真实样本中反复出现的跨页表格模式；
- 可使用相邻页窗口做只读上下文解析，但最终页级来源仍回写到原 page anchor；
- 关联结果必须保留来源 PDF、页锚点、table_id、行/列位置、原始/fallback hash 和置信度；
- 先支持候选关联和 coverage report，再考虑自动进入结构化抽取。

### 不纳入本阶段

- 不让多页解析结果替代单页 canonical；
- 不自动决定业务列语义或入库事实；
- 不使用无界 VLM 推断补齐缺失字段；
- 不修改已有 `candidate_id`、`record_id` 和审核状态语义，除非另建 Schema/迁移计划。

### 完成条件（待独立准入后冻结）

- 至少一组真实跨页表格 fixture 证明上下文解析能减少明确缺口；
- 错误关联、重复表头、图片表格和跨页边界均有失败样本；
- 候选可追溯、可回滚、幂等，未确认项不进入 `ready`；
- 下游结构化覆盖和审核门禁无回归。

## 验证方式

阶段 0：

```bash
python3 -m pytest -q
bash test-phase3.sh
bash scripts/test-fix-validate.sh
plan-governance-cli check . --strict-readiness
```

性能实验还必须保存每个临时 probe 的命令、输入 hash、配置快照、退出码、耗时和输出路径；不能只报告“感觉更快”。

阶段 1～3 实施时：

1. 修改任何函数、类或方法前执行 GitNexus upstream impact，并报告风险。
2. 对基线样本执行 A/B 或 before/after 对照。
3. 运行专项回归、全量 pytest、shell 回归、`detect_changes()`。
4. 如改变输出包、JSON、Schema 或 skill，执行项目级和用户级 skill 同步检查。
5. 完成阶段后运行 `plan-governance-cli check .`；阶段准入和最终验收使用独立复核记录。

## 风险与回滚

| 风险 | 影响 | 缓解 | 回滚 |
|---|---|---|---|
| 为了提速恢复多页 canonical | page node、chunk、图片和表格来源漂移 | 明确禁止；多页只做只读上下文实验 | 删除临时 probe，不触碰 canonical |
| VLM 幻觉进入主输出 | 事实错误、下游误入库 | sidecar only、Schema 校验、低置信度 review | 删除 sidecar 派生产物，保留原始 canonical |
| 误减少 fallback | 真实文本/表格缺失漏检 | 按页面类型比较，保留人工 review 和原始产物 | 恢复既有触发规则，重新运行原始 PDF |
| 跨页表格错误关联 | 结构化数据错配 | 候选态、来源 hash、页锚点和人工/LLM 审核 | 不应用候选，回到原始抽取结果 |
| VLM/批处理占用过多内存 | ModelPad 服务失败或 MPS 压力 | 记录峰值内存，限制页数和并发 | 关闭新增分支，保持现有单页主链 |
| 新字段与 skill 漂移 | 用户/LLM 消费错误 | 先更新事实源和两份 skill，再实施 | 回滚新增字段并恢复旧契约 |

## 依赖与关系

- 依赖 [coverage-validation-optimization](coverage-validation-optimization.md)：页面类型、`rerunnable` 和 `review_only` 分流事实源。
- 依赖 [pdf-evaluation-suite](pdf-evaluation-suite.md)：VLM sidecar、TOC 和表格评测事实源。
- 依赖 [single-page-segmentation-migration](single-page-segmentation-migration.md)：单页 canonical、页级 fallback 和 page node 边界。
- 依赖 [table-text-omission-detection](table-text-omission-detection.md)：原生表格字段缺失检测与 fallback 闭环。
- 依赖 [pdf-table-audit](pdf-table-audit.md)、[pdf-table-repair](pdf-table-repair.md) 和 [pdf-extract-data-table-coverage](pdf-extract-data-table-coverage.md)：表格候选、修复和结构化覆盖事实源。
- 沿用 [ADR 0002](../adr/0002-cli-only-workflow.md) 的 CLI-only 边界和 [ADR 0003](../adr/0003-llm-orchestrated-dynamic-assistants.md) 的证据、回滚和动态辅助脚本边界。

## 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 复核者 | 独立治理复核（基于当前仓库、临时 probe、回归命令和用户确认） |
| 日期 | 2026-07-24 |
| 阶段 | 阶段 2 |
| 结论 | 通过：达到 `待实施` 标准，进入实施；按用户确认的保守边界执行 |
| 证据 | V1/V2 共 23 页、21/23 `ok`、客户端峰值约 154–165 MiB、服务端约 10.99 GiB 预算参考、40/40 VLM 门禁测试、固定响应幂等性和 canonical 不变性均已有证据；用户确认视觉页/指定页、单批最多 10 页、失败 review、不覆盖主输出和顺序调用。 |

## 独立准入复核记录

### 最新有效复核

- 日期：2026-07-24
- 阶段：阶段 2
- 结论：通过：达到 `待实施` 标准，进入阶段 2 实施
- 证据：V1/V2 资源、Schema、人工抽查、失败门禁和固定响应幂等性已补齐；用户确认视觉页/指定页、单批最多 10 页、失败 review、不覆盖主输出和顺序调用
- 复核者：独立治理复核

### 历史复核

阶段 0 和阶段 1 的本轮复核已完成；阶段 2 已完成独立准入复核并进入实施。既有专项计划的独立验收不替代本计划阶段 2 的 Step 0。

## 独立复核记录

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-07-24 | 独立治理复核 | 阶段 0：ROI 基线与实施准入设计 | 通过：阶段 0 完成；阶段 1 达到 `待实施` 标准 | B1～B5 当前基线、366 pytest、133/133 修复回归、4/4 阶段回归、严格治理检查；用户确认下一阶段范围 |
| 2026-07-24 | 独立治理复核 | 阶段 1 | 通过：阶段 1 实施验收完成，阶段 1 关闭；阶段 2 保持设计中 | 368 pytest、133/133 修复回归、4/4 阶段回归、严格治理检查；VLM/验证器 13 页分类一致；gated demo20 fallback 11→4，selected fallback 保持 2 |
| 2026-07-24 | 独立治理复核 | 阶段 2 | 未通过 `待实施` 准入；保持设计中，不扩大默认调度 | V1/V2 共 23 页 21/23 成功；VLM 40/40 门禁测试；V2 150.88 秒、峰值约 165 MiB；固定响应幂等性通过；资源收益门槛、人工采纳指标、调度上限和真实服务失败矩阵仍未冻结 |
| 2026-07-24 | 独立治理复核（用户确认后） | 阶段 2 | 通过：达到 `待实施` 标准，进入实施 | 用户确认视觉页/指定页、单批最多 10 页、失败 review、不覆盖 canonical/page node/chunks/manifest 主状态和顺序调用；PLAN_MAP 已同步 |

## Test Coverage（当前基线）

本轮阶段 1+2 回归：`python -m pytest -q` 为 `374 passed, 5 warnings`；`bash scripts/test-vlm-service.sh` 为 `7/7`；`bash tests/test-fix-validate.sh` 为 `133/133`；`bash test-phase3.sh` 为 `4/4`。另有默认 97 页超限门禁 `exit=2`、显式 2 页调度实测通过。既有专项计划中记录的 `312 passed` 属于历史基线。阶段 2 尚待实施后独立验收，不代表阶段 3 已实施或验收通过。

## 完成定义

- 阶段 0 完成：ROI 基线、样本矩阵、候选门槛和独立准入复核齐备，并明确阶段 1～3 是否分别进入 `待实施`、`候选` 或 `已废弃`。
- 阶段 1 完成：fallback 成本/收益得到真实样本验证，规则调整、回归和文档同步完成。
- 阶段 2 完成：VLM sidecar 按需调度或明确维持现状，资源成本、Schema、失败策略和人工边界有证据。
- 阶段 3 完成：跨页表格优化仅在限定样本和下游目标内验收，候选关联可追溯、可回滚且不改变单页 canonical。
- 计划完成：阶段 0～3 的实际范围均有独立复核，未推进方向明确记录为 `候选` 或 `已废弃`，`PLAN_MAP`、相关计划和 skill 无漂移。
