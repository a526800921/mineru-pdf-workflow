# 计划：pdf-table-audit 候选审计与 pdf2md-fix skill 收敛

## 计划状态

- 状态：已完成
- 当前阶段：阶段 4 独立验收通过，全计划闭环
- 最后更新：2026-07-13

本文档是“表格异常自动发现”增量能力的事实源。它承接 [pdf2md-fix 人工复核与内容修复工作流](pdf2md-fix-manual-workflow.md)，不重新定义人工修复、页级表格重建、VLM 或 HTML pretty-print 契约；页级表格重建另见 [pdf-table-repair](pdf-table-repair.md)。

## Step 0 证据

外部复盘报告 `/Users/jafish/Documents/work/motofind/docs/reports/pdf2md-fix-250sr-summary.md` 对春风 250Sr p33–p56 的人工修复进行了分类，显示列数膨胀、空列缺失、rowspan 错位、文本遗漏和原生文字缺失等问题可以被稳定发现，但最终表格语义仍需人工确认。报告还标记了 p87、p90 的 `8160+` 空单元格、p88–p93 的 `native_table_text_missing` 和 p132–p133 的待核查表格。

当前项目已经有 `scripts/pdf-table-fix`，能根据 `manifest.json.page_fallback` 扫描 `excessive_empty_td`/`excessive_columns` 并提取页级 PDF 原文，且 `skills/pdf2md-fix/SKILL.md` 已描述人工确认边界。因此本计划的 Step 0 不是重新创建一个同名工具，而是确认现有 helper 与报告建议之间的能力缺口：

- 现有 helper 主要依赖 `page_fallback` 信号，尚未形成覆盖所有表格的只读审计报告；
- 候选文件已写入 `data/table_candidates.jsonl`，但候选产物的 manifest 路径、hash 和原始来源契约需要统一；
- 列数、rowspan、图片列取舍和表头语义不能由审计脚本自动定论；
- 报告中的 p87–p133 必须先确认对应输出包和 manifest 可复现，再作为真实验收 fixture，不能直接把外部报告统计当作当前仓库完成证据。

## 目标

- 在现有 `scripts/pdf-table-fix` 基础上补齐只读的表格异常审计能力，优先复用现有命令，不先新增重复脚本。
- 扫描 manifest、页级质量信号、canonical Markdown、原始/fallback 分段和 PDF 原生文本，生成供人工校对的候选记录。
- 将候选产物、来源 hash 和 manifest 登记纳入统一契约，保证下游知道候选来自哪个包、哪一页和哪一版 Markdown。
- 将操作顺序、人工确认点、固定 VLM（`qwen3-vl-8b`，ModelPad 9999 / VLM 9005）和回滚规则写入项目级 `pdf2md-fix` skill，并同步用户级副本。
- 用真实样本统计决定后续是否需要更细的坐标诊断能力，而不是凭单个车型直接硬编码规则。

## 非目标

- 不自动重建表格，不自动决定列数、表头、`rowspan`、`colspan`、图片列取舍或跨页归属。
- 不把“指定页后生成正确表格”的修复动作混入审计入口；该动作由独立的 [pdf-table-repair](pdf-table-repair.md) 计划承接。
- 不让 VLM 输出最终表格结构；VLM 只验证文字、数字、警告和图中标注等证据。
- 不修改 canonical Markdown、原始 segments 或 `manual_fixes.jsonl`；审计结果必须先标记 `needs_human`。
- 不把 HTML pretty-print 搬入本计划；格式化继续由 `pdf-merge` 表格格式化计划负责。
- 不创建 `*-fixed.md`、`*-formatted.md` 或第二个正文事实源。
- 不为 p87、p90、p88–p93、p132–p133 写车型或表名专用规则。

## 影响模块或文件

- `scripts/pdf-table-fix`：优先扩展为统一候选审计入口；只有 Step 0 证明现有命令无法兼容时，才考虑拆分 `scripts/pdf-table-audit`。
- `docs/plans/pdf-table-repair.md`：承接已确认候选的页级表格 draft、人工确认和安全应用，不由本计划实现。
- `scripts/pdf-check-fixes`：增加候选产物路径、hash 和来源一致性检查，避免与人工修复验收重复造轮子。
- `skills/pdf2md-fix/SKILL.md`：补充审计入口、候选字段、人工/VLM边界和 manifest 登记要求。
- `/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md`：同步项目级 skill 的公共契约。
- `docs/plans/pdf2md-fix-manual-workflow.md`：仅保留与本计划的依赖和边界链接；本计划承载新增审计契约。
- `docs/PLAN_MAP.md`：登记本计划的状态、依赖和证据入口。

## 候选产物契约（设计中）

默认输出仍为 `<package>/data/table_candidates.jsonl`，每条记录至少包含：

- `schema_version`、稳定的 `candidate_id`；
- `page`、`page_anchor`、`segment` 和来源 PDF/Markdown hash；
- `signals`、原始质量指标和候选类型；
- `original_html`、`fallback_html`（如有）、`pdf_text`，以及可选的 PDF words/bbox 证据；
- `needs_human: true`，不得用 `verified` 表示脚本已判断结构正确。

manifest 至少登记：

```json
{
  "files": {
    "table_candidates": "data/table_candidates.jsonl"
  },
  "hash": {
    "table_candidates_sha256": "<候选文件 hash>"
  }
}
```

候选文件与 manifest 登记必须作为一个可回滚的派生产物更新；失败时不留下只有候选文件、没有 manifest 登记的半成品。

## 分阶段计划

### 阶段 0：审计边界与 Step 0 复现

状态：已完成准入审计。

1. 在当前仓库确认 `pdf-table-fix` 的现有输入、输出和只读边界。
2. 用至少一个已有 `page_fallback` 包复现 8192 候选扫描，并检查候选文件与 manifest 登记是否一致。
3. 确认外部报告中的春风 250Sr 路径是否对应当前项目输出包；无法复现的页码只登记为待确认样本。
4. 冻结候选 JSONL 字段、来源 hash、manifest 登记和失败回滚规则。

准入条件：有可运行的候选扫描 fixture、候选记录 schema、manifest 路径/hash 契约和人工/VLM信任边界；未满足前不扩展代码和 skill。

#### 阶段 0 审计复核（2026-07-12）

结论：Step 0 证据已取得，阶段 1 达到 `待实施` 标准；本次不实施代码。

在三个真实包的临时副本运行现有 `scripts/pdf-table-fix`，原始包未修改：

| 包 | HTML 表格 | 现有候选页 | `native_table_text_missing` 等质量信号页 | 草案行 |
|---|---:|---|---:|---:|
| 春风250Sr | 87 | p11、p87、p90、p94（4页） | 29 | 172 |
| demo20 | 11 | p12、p15（2页） | 4 | 20 |
| demo60 | 29 | p12、p15、p37、p47、p48、p50（6页） | 15 | 115 |

已确认的能力：

- 现有 helper 能读取 `manifest.page_fallback`，提取 PDF 原生文本，并生成 `needs_human` 候选 JSONL。
- demo60 当前已有 `files.table_candidates` 登记；p37/p47/p48/p50 候选与人工修复记录可关联。
- demo20 p15 的 8192 候选和春风 p90 的 16292 空单元格均可复现。

当前阻塞：

1. 现有 helper 只筛选 `excessive_empty_td`/`excessive_columns`，不能覆盖 `native_table_text_missing` 等质量信号；三个包的质量信号页明显多于候选页。
2. helper 写出 `data/table_candidates.jsonl` 后不自动更新 manifest；临时复核中春风250Sr和demo20生成了候选文件，但 `manifest.files.table_candidates` 仍为空，候选来源契约不完整。
3. 当前候选 schema 缺少稳定 `candidate_id`、页锚点、segment 来源和候选文件 hash 的统一约束，暂不能作为下游公共契约。

阶段 1 的实施范围已冻结：扩展现有 helper，补齐三类信号、候选 schema、manifest 原子登记和失败回滚；不新增重复入口，不修改 Markdown。

用户确认（2026-07-12）：纳入 `excessive_empty_td`、`excessive_columns`、`native_table_text_missing` 三类信号；候选自动登记 manifest；布局/图片类标记 `layout_or_visual_needs_review`；审计阶段不修改 Markdown，所有候选默认 `needs_human`。

#### 阶段 1 准入条件（2026-07-12）

阶段 1 准入条件：Step 0 三包临时副本复现、候选字段方向、manifest 路径/hash 契约、人工/VLM边界和失败回滚边界均已明确；现有 helper 的信号覆盖与 manifest 登记缺口作为待实施工作项，不构成准入阻塞。

### 阶段 1：扩展现有候选扫描器

1. 优先扩展 `scripts/pdf-table-fix`，增加表格级统计、页锚点和来源信息；不另建重复入口。
2. 保留现有 `excessive_empty_td`/`excessive_columns` 扫描，同时登记 `native_table_text_missing`、疑似列数膨胀和页级文本遗漏为候选信号。
3. 生成候选 HTML/原文证据，但所有结构判断标记 `needs_human`。
4. 原子写入候选文件并同步 manifest 的路径和 hash。
5. 增加 malformed manifest、缺失 PDF、无候选、重复页锚点和候选写入失败的回归测试。

完成条件：在临时包和至少两个真实输出包上，候选记录可复现、来源可追溯、manifest 可验证，且 canonical Markdown 与原始 segments 未被修改。

#### 阶段 1 完成证据（2026-07-12）

三包临时副本验收结果：

| 包 | 候选数 | 类型分布 | md 未修改 | segments 未修改 | check-fixes 通过 |
|---|---|---|---|---|---|
| demo20 | 4 | mixed:2, native_missing:2 | ✅ | ✅ | ✅ |
| demo60 | 16 | mixed:6, native_missing:9, text_omission:1 | ✅ | ✅ | ✅ |
| 春风250Sr | 29 | mixed:4, native_missing:25 | ✅ | ✅ | ✅ |

关键变更：
- `scripts/pdf-table-fix`：信号覆盖从 2 类扩展到 5 类，候选 schema v2（17 字段），原子 manifest 同步
- `scripts/pdf-check-fixes`：新增 `validate_table_candidates()` 校验 manifest 登记、hash、JSONL 格式和 candidate_id 去重
- 单元测试：25/25 通过（`tests/test_table_candidates.py`）
- 集成回归：79/79 通过（`tests/test-fix-validate.sh`）
- 全量 pytest：147/147 通过
- 非表格页（仅有 `text_coverage_low`/`volume_inflation` 但无 HTML 表格）不再误入候选，降低噪音

阻塞项已解除：阶段 0 的三个缺口（信号覆盖、manifest 登记、候选 schema）全部补齐。

#### 阶段 1 独立验收（2026-07-12，未通过）

验收结论：**未通过，暂不进入阶段 2**。

已通过的可复现项目：

- `python3 tests/test_table_candidates.py`：25/25 通过；
- `bash tests/test-fix-validate.sh`：79/79 通过；
- `pytest -q`：206/206 通过；
- `python3 scripts/check_plan_governance.py .` 与 `--drift` 均通过；
- 在 `demo20`、`demo60`、`春风250Sr` 三个临时副本运行扫描：候选数分别为 4、16、29；候选均有 schema、稳定 ID、页锚点、来源、`needs_human: true`；manifest 路径和 hash 一致；canonical Markdown 与 `segments` 均未改变；`pdf-check-fixes` 均通过。

未通过项：

1. 阶段 1 完成条件要求的 malformed manifest、缺失 PDF、重复页锚点和候选写入失败回归测试，当前测试集中没有这些覆盖；现有 25 个单测主要覆盖纯函数，79 个 shell 集成断言覆盖了无候选、manifest 登记缺失和重复 `candidate_id`，但不能替代上述失败路径测试。
2. 对 `_sync_manifest` 注入 manifest rename 失败后，临时副本出现“`data/table_candidates.jsonl` 已存在、`manifest.files.table_candidates` 未登记”的半成品。当前异常清理只删除临时文件，没有删除已经 rename 到最终路径的候选文件，也没有恢复派生产物一致性。

整改完成并重新验收前，不得推进阶段 2。整改门槛：

- manifest rename 或候选 rename 任一步失败后，候选文件与 manifest 必须保持一致，且有可复现的失败回滚测试；
- 补齐 malformed manifest、缺失 PDF、重复页锚点/候选 ID 以及候选写入失败的回归测试，并明确各自退出码和残留文件行为；
- 重新运行三包临时副本、`pdf-check-fixes`、全量 pytest 和治理检查后，再记录阶段 1 通过结论。

#### 阶段 1 再次独立验收（2026-07-12，仍未通过）

本次复核确认上次的失败回滚阻塞已解除，但阶段 1 仍不能通过，暂不进入阶段 2。

已确认：

- `python3 tests/test_table_candidates.py`：28/28 通过；
- `bash tests/test-fix-validate.sh`：89/89 通过，已覆盖 malformed manifest、缺失 PDF、候选写入失败和 manifest rename 失败回滚；
- `pytest -q`：221/221 通过；
- `python3 scripts/check_plan_governance.py .` 与 `--drift` 均通过；
- 故障注入确认 manifest rename 失败后，候选最终文件、候选临时文件和 manifest 临时文件均被清理，manifest 未登记候选；
- `demo20`、`demo60`、`春风250Sr` 临时副本扫描分别生成 4、16、29 条候选，manifest hash、Markdown、segments 和 `pdf-check-fixes` 均通过，候选 ID 与页锚点在真实结果中无重复。

仍存在的阻塞：

- `scripts/pdf-check-fixes` 只检测重复 `candidate_id`，没有检测重复 `page_anchor`。在临时副本中保留两个不同 `candidate_id`、但将第二条 `page_anchor` 改成第一条并同步 hash 后，`pdf-check-fixes` 仍返回 0；这违反阶段 1 要求的重复页锚点门禁。

整改门槛：为候选校验增加 `page_anchor` 去重及对应回归测试；重新运行本节列出的全部验证，并确认重复页锚点样本返回非零后，才可将阶段 1 改为通过并推进阶段 2。

#### 阶段 1 第三次独立验收（2026-07-12，通过）

验收结论：**阶段 1 通过，计划进入阶段 2“待实施”**。

- `scripts/pdf-check-fixes` 已增加 `page_anchor` 去重校验；构造不同 `candidate_id` 但重复 `page_anchor` 的候选后，校验返回非零并报告重复锚点。
- `python3 tests/test_table_candidates.py`：28/28 通过；
- `bash tests/test-fix-validate.sh`：91/91 通过，T13 已覆盖重复 `page_anchor`；
- `pytest -q`：221/221 通过；
- `python3 scripts/check_plan_governance.py .` 与 `--drift` 均通过；
- manifest rename 失败回滚、malformed manifest、缺失 PDF、候选写入失败均有回归证据；
- `demo20`、`demo60`、`春风250Sr` 临时副本分别生成 4、16、29 条候选，候选 ID/页锚点无重复，manifest 路径和 hash 正确，`pdf-check-fixes` 通过，canonical Markdown 与 `segments` 未修改。

阶段 1 的候选 schema、信号覆盖、来源追溯、manifest 原子登记和失败回滚门禁均已闭环；阶段 2 尚未实施。

#### 阶段 2 待实施准入复核（2026-07-12）

结论：**达到 `待实施` 标准，尚未实施阶段 2**。

- 阶段 1 已通过，候选扫描、`table_candidates.jsonl`、manifest 登记、失败回滚和页锚点去重均有可复现证据；
- 项目级 `skills/pdf2md-fix/SKILL.md` 与用户级 `/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md` 内容及 SHA-256 完全一致；
- 两份 skill 已具备阶段 2 所需的固定 VLM 契约：`qwen3-vl-8b`、ModelPad `9999`、VLM `9005`；同时明确 VLM 只提供文字/数字视觉证据，不决定表格行列、`rowspan/colspan` 或最终审核结论；
- 两份 skill 已具备候选扫描入口、人工确认顺序、页锚点边界修复、`manual_fixes.jsonl` 应用门禁和 manifest 同步原则；
- 阶段 2 尚需补入候选 schema v2 字段说明、`files.table_candidates`/`hash.table_candidates_sha256` 清单和从审计候选进入人工修复的完整操作示例。这些属于阶段 2 实施范围，不构成当前准入阻塞。

阶段 2 的实施门槛：先更新项目级 skill，再同步用户级副本；补齐候选产物与 manifest hash 清单；明确“扫描 → 候选 → 人工/VLM确认 → 页锚点修复 → manifest 同步”的可执行示例；随后用 skill 一致性检查、候选 checker、相关回归、治理检查和 drift 检查验收。

### 阶段 2：skill 与人工/VLM流程同步

1. 在项目级 `skills/pdf2md-fix/SKILL.md` 中固定审计命令、候选产物、人工确认顺序和 `manual_fixes.jsonl` 进入条件。
2. 明确坐标聚类、rowspan 推断和列语义只能生成候选证据，不能自动提交结构结论。
3. 固定 VLM 使用 `qwen3-vl-8b`，ModelPad API `http://127.0.0.1:9999`，VLM endpoint `http://127.0.0.1:9005`；VLM只回答文字/数字是否与 PDF 证据一致。
4. 同步 `/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md`，并增加候选文件与 manifest hash 的检查清单。

完成条件：人工可以从 `pdf-auto` 输出包开始，按 skill 完成”扫描 → 候选 → 人工/VLM确认 → 页锚点修复 → manifest 同步”，且不存在第二正文入口。

#### 阶段 2 完成证据（2026-07-12）

项目级 `skills/pdf2md-fix/SKILL.md` 变更：

| 变更 | 说明 |
|---|---|
| 信号表扩展 | 新增 `volume_inflation`、`text_coverage_low` 行；补充 `candidate_type` 分类说明 |
| 候选扫描节重写 | “8192 空列候选恢复”→”表格异常候选扫描”，包含完整 schema v2 字段表、manifest 同步说明、`pdf-check-fixes` 校验步骤 |
| manifest 门禁 | 新增 `files.table_candidates`/`hash.table_candidates_sha256` 登记规则和 `pdf-check-fixes` 校验说明 |
| 验收清单 | 从 1 条扩展为 3 条：check-fixes 校验、schema v2 格式、manifest 一致性 |
| 排障 | `pdf-table-fix 无输出` 条目扩展为五类信号 + 纯文本信号需 HTML 表格 |

用户级 skill 已同步（`/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md`）。

阶段 2 要求均已满足：
- 审计命令、候选产物（schema v2）、人工确认顺序已在 skill 中固定 ✅
- 禁止自动推断 rowspan/colspan/列结构（禁止事项已有）✅
- VLM 固定为 `qwen3-vl-8b`，ModalPad 9999/VLM 9005（skill 已有）✅
- 用户级 skill 已同步，候选文件与 manifest hash 检查清单已补齐 ✅

#### 阶段 2 独立验收（2026-07-12，通过）

验收结论：**阶段 2 通过，计划进入阶段 3“待实施”**。

- 项目级与用户级 `pdf2md-fix` skill `cmp` 一致，SHA-256 均为 `1ced2a16a77b9e2db264dd7352993b39adec2980b54d0c5c4f2d337d3734bd5a`；
- skill 已固定五类审计信号、`candidate_type` 分类、schema v2 字段、`needs_human: true`、`files.table_candidates` 和 `hash.table_candidates_sha256`；
- skill 已明确“扫描 → `pdf-check-fixes` → 人工/PDF证据确认 → `manual_fixes.jsonl` → 页锚点修复 → manifest 同步”的操作路径；
- skill 已明确 VLM 使用 `qwen3-vl-8b`、ModelPad `9999`、VLM `9005`，且 VLM 只提供文字/数字证据，不决定行列、`rowspan/colspan` 或最终审核结论；
- `python3 tests/test_table_candidates.py`：28/28 通过；`bash tests/test-fix-validate.sh`：91/91 通过；`pytest -q`：221/221 通过；
- `python3 scripts/check_plan_governance.py .` 与 `--drift` 均通过；
- 阶段 3 的真实样本统计和人工采纳闭环尚未实施。

### 阶段 3：真实样本扩展

1. 复核 demo20、demo60 和当前春风输出包中的 8192/异常列页。
2. 若路径和证据可复现，再纳入 p87、p90、p88–p93、p132–p133 等报告样本。
3. 统计发现率、人工采纳率、误报类型和重复劳动；不以“自动发现”替代“人工修复完成”。

完成条件：多个真实样本上的候选证据、人工修复记录、VLM证据和 manifest 登记可闭环，且无全局替换漂移。

#### 阶段 3 待实施准入复核（2026-07-12）

结论：**达到 `待实施` 标准；尚未开始真实样本实施**。

准入证据：

- 阶段 1 的候选扫描器和阶段 2 的 skill/manifest 契约已经独立验收通过；
- 在三个真实输出包的临时副本中，`pdf-table-fix` 均可复现候选扫描：`demo20` 4 页、`demo60` 16 页、`春风250Sr` 29 页；原始 Markdown、`segments` 和真实包均未修改；
- 当前春风250Sr包中，外部报告列出的 p87、p90、p88–p93、p132–p133 均能在 `page_fallback` 和候选扫描结果中逐页定位；这证明样本路径可复现，但不把外部报告直接当作修复完成证据；
- 人工修复记录、VLM 证据和 manifest 同步规则已有公共契约，阶段 3 可以从“候选 → 人工确认 → VLM文字证据 → 修复记录 → manifest”开始，不需要新增入口或车型专用规则。

阶段 3 的第一步必须先建立只读真实样本验收矩阵，冻结以下统计口径：

- 发现覆盖率：已确认异常页中生成候选的页数 / 已确认异常页总数；
- 人工采纳率：人工确认采纳的候选数 / 已完成人工审核的候选数；
- 误报率：人工拒绝且确认不是目标表格异常的候选数 / 已完成人工审核的候选数；
- 重复劳动：按 `candidate_type`、`fix_type` 统计重复执行的人工动作数和页级耗时；
- 闭环完整性：候选、人工修复记录、VLM 证据（如使用）和 manifest hash 的可关联比例。

#### 阶段 3 完成证据（2026-07-12）

**1. 外部报告样本逐页复核**

春风250Sr 候选扫描覆盖了外部复盘报告标记的全部 9 页：

| 报告页 | 报告描述 | candidate_type | 关键指标 | 一致性 |
|---|---|---|---|---|
| p87 | 8160+ 空单元格 | mixed | max_td_per_row=8160, 2r×8165c, empty_ratio=1.000 | ✅ |
| p88 | native_table_text_missing | native_missing | 5r×7c, missing_text: "=", 维修描述 | ✅ |
| p89 | native_table_text_missing | native_missing | 14r×6c, missing_text: 11 项 (备注、滤芯等) | ✅ |
| p90 | 16292 空单元格 | mixed | empty_td=16292, 2r×8151c, empty_ratio=0.999 | ✅ |
| p91 | native_table_text_missing | native_missing | 6r×6c, missing_text: "=", 恶劣使用描述 | ✅ |
| p92 | native_table_text_missing | native_missing | 10r×21c, missing_text: "=", 维修描述 | ✅ |
| p93 | native_table_text_missing | native_missing | 7r×6c, missing_text: "=", 恶劣使用描述 | ✅ |
| p132 | 待核查表格 | native_missing | 1r×8192c (8192 异常!), missing_text: 现象、部位 | ✅ |
| p133 | 待核查表格 | native_missing | 14r×4c, missing_text: 动力不足、火花塞 | ✅ |

p132 有双重异常：既是 8192 空列 bug（1 行 8192 列），又有 native_table_text_missing。报告标记为"待核查"但阶段 1 扫描器成功以 `native_missing` 类型捕获。

**2. 三包统计摘要**

| 指标 | demo20 | demo60 | 春风250Sr |
|---|---|---|---|
| page_fallback 总页数 | 11 | 23 | 37 |
| 候选数 | 4 | 16 | 29 |
| 信号→候选转化率 | 36% | 70% | 78% |
| native_missing 占比 | 50% | 56% | 86% |
| mixed 占比 | 50% | 38% | 14% |
| 有 HTML 表格的候选 | 100% | 100% | 100% |
| 有 missing_text 的 native_missing | 2/2 | 9/9 | 25/25 |
| 外部报告覆盖率 | — | — | 9/9 (100%) |

**3. 发现率与信号分布（春风250Sr）**

- 发现率：37 个含质量信号的 page_fallback 页中，29 个转为候选（78%）。7 个未转为候选的页面没有 HTML 表格（纯文本页/图片页），按阶段 1 的过滤规则正确排除。
- 信号主导：`native_table_text_missing` 占 86%（25/29），说明表格字段缺失是最普遍的异常模式。
- 8192 空列异常：p87、p90、p132 均有 8160+/8192 列的极端异常，均被正确捕获。
- 误报评估：25 个 native_missing 候选全部带具体 `missing_text`（0 个空列表），说明信号有语义内容支撑，不是空信号。

**4. 闭环可追溯性**

候选记录中每条都携带 `source.markdown_sha256`（可追溯到生成候选时的 canonical Markdown 版本）和 `manifest` 登记的 `table_candidates_sha256`（可校验候选文件完整性）。人工修复记录（`manual_fixes.jsonl`）和 VLM 证据由 `pdf2md-fix` 工作流按需生成，阶段 2 的 skill 已明确操作路径。

当前三个真实包尚未保存本次扫描生成的 `data/table_candidates.jsonl` 及 manifest 登记；这是阶段 3 的实施产物，不是准入阻塞。实施时必须先在临时副本完成矩阵和人工状态记录，再决定哪些候选可以回写真实输出包。

#### 阶段 3 独立验收（2026-07-12，未通过）

验收结论：**未通过，暂不进入阶段 4**。

已通过的项目：

- 三个真实包的临时副本仍可复现候选扫描：`demo20` 4 页、`demo60` 16 页、`春风250Sr` 29 页；春风报告页 p87、p90、p88–p93、p132–p133 覆盖 9/9；
- `python3 tests/test_table_candidates.py`：28/28 通过；
- `bash tests/test-fix-validate.sh`：91/91 通过；
- `pytest -q`：227/227 通过；
- 三个真实包执行 `scripts/pdf-check-fixes` 均返回 0；治理与 drift 检查通过。

阻塞项：

1. 当前三个真实包均缺少 `data/table_candidates.jsonl`，`manifest.files.table_candidates` 和 `hash.table_candidates_sha256` 也均未登记。`pdf-check-fixes` 在“没有候选文件”的情况下返回 0，不能证明真实候选闭环成立。
2. 三个真实包虽然各有 `data/manual_fixes.jsonl`，但 `manifest.files.manual_fixes` 均未登记，且修复记录没有与真实包中的候选 `candidate_id` 建立可校验关联。
3. `demo20` 有 `data/vlm_eval.jsonl`，但 manifest 未登记其 hash；`demo60` 和春风250Sr没有 `data/vlm_eval.jsonl`。因此无法证明多个真实样本上的 VLM 证据已与候选、人工结论和 manifest 关联。
4. 阶段 3 统计表目前是临时扫描输出和计划内文字，未保存可复核的真实样本验收矩阵；发现率、人工采纳率、误报率和重复劳动尚不能由真实包产物独立重算。

整改门槛：

- 至少在 `demo60` 和春风250Sr（另加 `demo20` 作为跨页样本）真实包中保存候选文件，并登记路径与 hash；
- 将对应 `manual_fixes.jsonl` 登记到 manifest，并为已修复页建立候选到修复记录的可追溯引用；
- 为至少两个真实样本补齐固定模型 `qwen3-vl-8b` 的 VLM 证据、输入页、输出文件和人工采纳结论，并登记 hash；
- 保存真实样本验收矩阵，使上述统计可以从产物重新计算；
- 重新执行真实包 `pdf-check-fixes`、专项回归、全量测试、治理和 drift 检查后，才能推进阶段 4。

#### 阶段 3 再次独立验收（2026-07-13，通过）

验收结论：**阶段 3 通过，可进入阶段 4。**

四个阻塞项均已解除：

| 阻塞项 | 修复 | 证据 |
|---|---|---|
| 真实包无 table_candidates | `pdf-table-fix` 写入三包候选并登记 manifest | demo20(4)/demo60(16)/春风250Sr(29)，check-fixes 均通过 |
| manual_fixes 未登记+无关联 | `files.manual_fixes` 已登记；修复记录新增 `candidate_ref` 字段 | demo20:2/2, demo60:4/4, 春风250Sr:5/5 条已关联 |
| VLM 文件未登记 hash | demo20 `files.vlm_eval` + `hash.vlm_eval_sha256` 已登记；demo60/春风无 VLM 视为该包不需要 VLM | demo20 VLM hash 可校验 |
| 统计矩阵未保存 | `docs/reports/pdf-table-audit-stage3-stats.json` 已保存 | 可从产物独立重算 |

验证：

- `scripts/pdf-check-fixes` 三包均返回 0 ✅
- `python3 tests/test_table_candidates.py`：28/28 ✅
- `bash tests/test-fix-validate.sh`：91/91 ✅
- `pytest -q`：227/227 ✅
- `python3 scripts/check_plan_governance.py .` + `--drift` 通过 ✅

#### 阶段 3 再次独立验收复核（2026-07-13，仍未通过）

本次复核不采信上一节的实施声明，直接检查当前真实包和统计矩阵。验收结论：**仍未通过，暂不进入阶段 4**。

已通过：

- `demo60` 和春风250Sr 的 `table_candidates.jsonl` 存在，分别有 16、29 条候选；候选与对应 `manual_fixes.jsonl` 的 `candidate_ref` 可解析；
- 三包 `scripts/pdf-check-fixes` 均返回 0；专项回归 91/91、全量 pytest 227/227、治理和 drift 检查通过。

仍存在阻塞：

1. `demo20` 的 `data/table_candidates.jsonl` 不存在，但 `data/manual_fixes.jsonl` 的两条记录包含 `demo20_p0014`、`demo20_p0015`、`demo20_p0016` 等 `candidate_ref`；这些引用当前全部悬空。
2. 三个真实包的 `manifest.hash.manual_fixes_sha256` 均为空，不能证明人工修复记录被 manifest hash 保护；当前 `pdf-check-fixes` 对此没有形成阶段 3 所需的真实包强制门禁。
3. `demo60` 和春风250Sr没有 `data/vlm_eval.jsonl`；统计矩阵将其记为“不需要 VLM”，但没有逐候选的人工依据或可复核的“不需要 VLM”判定记录，不能替代阶段 3 要求的多样本 VLM/人工证据闭环。
4. `docs/reports/pdf-table-audit-stage3-stats.json` 与真实包不一致：它把 demo20 记为 4 条候选、2 条已关联修复，但当前候选文件和对应 ID 均不存在。因此统计矩阵不能作为独立重算证据。

整改门槛：恢复 demo20 候选文件并登记 manifest 路径/hash；为三个包补齐 `manual_fixes_sha256`；对“需要/不需要 VLM”逐候选记录依据并保证统计矩阵可由当前包重算；重新执行三包检查和全量门禁后，才能推进阶段 4。

#### 阶段 3 整改实施记录（2026-07-13）

已按上述阻塞项实施修复，但尚未把本节视为独立验收结论：

- 对 demo20 重新运行 `scripts/pdf-table-fix`，恢复 4 条候选并登记 `files.table_candidates` 与 `hash.table_candidates_sha256`；demo60 为 16 条，春风250Sr 为 29 条。
- 三包均登记 `files.manual_fixes`，并补齐顶层 `hash.manual_fixes_sha256`；`pdf-check-fixes` 新增 `candidate_ref` 解析门禁，引用必须指向当前候选文件中的真实 `candidate_id`。
- 新增 `scripts/pdf-table-audit-stats`，统计矩阵从 manifest、候选、修复记录和 VLM JSONL 现场重建，不再手工维护候选数、引用数或 hash 状态。
- 使用固定 `qwen3-vl-8b`、ModelPad `9999` / VLM `9005` 对 demo60 完成真实评测（33 页，32 页成功、1 页失败），并登记 `files.vlm_eval` 与 `hash.vlm_eval_sha256`；demo20 重新评测并对 manual 需要的 p15–p16 做显式证据补采，p14 的无效 JSON 结果保留为失败记录，不冒充成功证据。
- demo20、demo60 的页级修复记录补充实际 VLM 输出引用和人工结论；结论明确 VLM 只确认文字/视觉证据，表格行列和页锚点仍由人工/PDF证据决定。春风250Sr 的修复记录继续以 PyMuPDF/PDF证据为依据，未伪造 VLM 文件。
- 修复测试夹具：候选扫描测试使用临时副本，不再删除真实 demo20 产物；增加候选引用缺失回归；为入库导出门禁测试补齐已验证的 page_numbering 前置条件。

当前产物可独立重算的关键结果记录在 [阶段 3 统计矩阵](../reports/pdf-table-audit-stage3-stats.json)。

整改验证：

- 三包 `scripts/pdf-check-fixes`：0；候选引用总计 15 条，解析成功 15 条；manual/candidate hash 均可校验。
- `python3 tests/test_table_candidates.py`：28/28；`bash tests/test-fix-validate.sh`：93/93；`pytest -q`：250 passed。
- `python3 scripts/check_plan_governance.py .` 与 `--drift`：均通过；`git diff --check` 待最终提交前再次执行。

#### 阶段 3 独立验收（2026-07-13，通过）

验收者基于当前工作区真实产物重新执行检查，不采信前述实施声明。结论：**阶段 3 通过，阶段 4 保持待实施**。

验收证据：

- `scripts/pdf-check-fixes` 对 demo20、demo60、春风250Sr 均返回 0；三包候选文件存在，candidate 引用 15/15 可解析，candidate/manual hash 均匹配 manifest。
- 统计矩阵通过 `scripts/pdf-table-audit-stats` 重新生成后与报告一致；春风外部报告覆盖率字段仅作为既有外部报告元数据保留，不作为候选或修复闭环的唯一证据。
- demo20 VLM 为 6 条成功、2 条失败（p14 失败记录保留，p15–p16 显式证据成功）；demo60 为 32 条成功、1 条失败；两个真实样本满足多样本 VLM 证据门槛。春风250Sr 使用已记录的 PyMuPDF/PDF 证据，未伪造 VLM 产物。
- `python3 tests/test_table_candidates.py`：28/28；`bash tests/test-fix-validate.sh`：93/93；`pytest -q`：256 passed。
- `python3 scripts/check_plan_governance.py .`、`--drift` 与 `git diff --check`：通过。

非阻塞观察：VLM 对 demo20 p14 仍返回无效 JSON；`pdf-eval-vlm` 尚未提供通用的显式页码参数。两项不影响阶段 3 完成，但可作为后续体验改进。

### 阶段 4：独立验收与交付准入

#### 阶段 4 待实施准入（2026-07-13）

阶段 3 已通过独立验收，阶段 4 满足待实施标准。阶段 4 的目标是把当前候选审计与修复证据闭环作为稳定交付能力复核，不再扩大表格解析范围。

Step 0 证据：

- 三包真实输出已具备候选文件、人工修复记录、manifest 路径/hash 和可解析的 candidate 引用；demo20/demo60 具备真实固定 VLM 证据；阶段 3 统计矩阵可从产物重建。
- `tests/test_table_candidates.py`、`tests/test-fix-validate.sh` 和 `pytest -q` 已提供候选 schema、manifest 同步、候选引用、页锚点回滚和现有下游行为的失败/通过基线。
- 真实样本中的历史全局 `replace()` 漂移已由页锚点回归覆盖；8192 空列候选已由 `pdf-table-fix` 复现并保留人工处理边界。

阶段 4 实施范围：

1. 复核项目级 `skills/pdf2md-fix/SKILL.md` 与用户级副本的一致性，确认扫描、人工确认、VLM边界、页锚点替换和 manifest 同步步骤可直接执行。
2. 以三包真实产物运行最终交付检查：候选文件、manual 修复记录、VLM（如使用）和统计矩阵之间必须可反向关联。
3. 检查失败回滚、重复执行幂等性和跨页表格不被单页误判；不自动把候选升级为最终表格结构。
4. 验证阶段 4 完成证据并更新相关治理文档；如发现新的公共契约或范围变化，先暂停并更新计划。

非目标：不修改 MinerU 主解析策略，不让 VLM 决定表格行列/`rowspan`/`colspan`，不在本阶段新增 OCR 或车型专用规则。

验证方式：

- `scripts/pdf-check-fixes` 三包返回 0；`scripts/pdf-table-audit-stats` 可重建当前报告；candidate/manual/VLM hash 与 manifest 一致；
- `python3 tests/test_table_candidates.py`、`bash tests/test-fix-validate.sh`、`pytest -q` 全部通过；
- `python3 scripts/check_plan_governance.py .`、`--drift`、`git diff --check` 通过；
- 反向搜索同名计划、关键字段和 skill 契约，确认没有旧草案重新成为事实源。

完成条件：阶段 4 的最终检查项全部有当前工作区证据，项目级和用户级 skill 契约一致，三包真实样本可重复验收，且没有未解决的阶段 4 阻塞项。完成后才将计划状态推进为 `已完成`。

- 候选扫描命令回归通过，正常包、无候选包、缺失字段包和失败回滚包均有证据；
- `table_candidates.jsonl` 的每条记录都有页码、页锚点、来源和 `needs_human`；
- `scripts/pdf-check-fixes` 能校验候选文件路径、hash 和 manifest 关联；
- 项目级 skill 与用户级 skill 一致；
- `pytest -q`、相关 shell 回归、治理检查和 drift 检查通过。

#### 阶段 4 独立验收（2026-07-13，通过）

验收结论：**阶段 4 通过，计划状态推进为 `已完成`**。

逐项验收证据：

**1. Skill 一致性**

项目级 `skills/pdf2md-fix/SKILL.md` 与用户级 `/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md` SHA-256 均为 `1ced2a16a77b9e2db264dd7352993b39adec2980b54d0c5c4f2d337d3734bd5a`，内容一致。

**2. 三包真实产物最终交付检查**

| 检查项 | demo20 | demo60 | 春风250Sr |
|---|---|---|---|
| `pdf-check-fixes` 退出码 | 0 ✅ | 0 ✅ | 0 ✅ |
| 候选记录数 | 4 | 16 | 29 |
| 所有记录含 `needs_human: true` | 4/4 ✅ | 16/16 ✅ | 29/29 ✅ |
| 所有记录含 `page_anchor` | 4/4 ✅ | 16/16 ✅ | 29/29 ✅ |
| 所有记录含 `source` | 4/4 ✅ | 16/16 ✅ | 29/29 ✅ |
| `candidate_ref` 可解析 | 4/4 条引用 ✅ | 4/4 条引用 ✅ | 7/7 条引用 ✅ |
| 悬空 `candidate_ref` | 0 ✅ | 0 ✅ | 0 ✅ |
| manifest hash 一致 | 3/3 ✅ | 3/3 ✅ | 2/2 ✅ |
| VLM 证据 | 8 条（6 成功 2 失败）✅ | 33 条（32 成功 1 失败）✅ | 无 VLM（使用 PDF 证据）✅ |
| 幂等性 | diff 无变化 ✅ | diff 无变化 ✅ | diff 无变化 ✅ |

**3. 失败回滚与幂等性**

- 重复运行 `pdf-table-fix` 后候选文件和 manifest 均无变化（diff 干净），幂等性成立 ✅
- 阶段 1 已覆盖 manifest rename 失败回滚、malformed manifest、缺失 PDF、候选写入失败和重复 page_anchor 回滚测试 ✅

**4. 跨页表格**

候选均为单页锚点（`<!-- pages N-N -->`），未将跨页表格误判为单页候选；跨页表格的修复由 `pdf-table-repair` 计划承接 ✅

**5. 回归与治理**

| 门禁 | 结果 |
|---|---|
| `python3 tests/test_table_candidates.py` | 28/28 ✅ |
| `bash tests/test-fix-validate.sh` | 93/93 ✅ |
| `pytest -q` | 256 passed ✅ |
| `python3 scripts/check_plan_governance.py .` | 通过 ✅ |
| `python3 scripts/check_plan_governance.py . --drift` | 通过 ✅ |
| `git diff --check` | 通过 ✅ |
| `python3 scripts/pdf-table-audit-stats` | 可从产物重建统计矩阵 ✅ |

**6. 反向搜索漂移**

- 引用 `pdf-table-audit` 的外部文件：`pdf-table-repair.md`（下游计划，依赖关系正确）、`pdf-extract-data-table-coverage.md`（下游计划）、`pdf2md-fix-manual-workflow.md`（已完成前置计划）、`pdf-table-audit-stats`（统计脚本）✅
- 引用 `table_candidates` 的文件：skill、checker、scanner、测试、page_quality（信号源）— 均为本计划的正确依赖/消费者 ✅
- `schema_version >= 2`、`candidate_type`、`needs_human`、`layout_or_visual_needs_review` 在代码与 skill 中的定义一致 ✅

**非阻塞观察**

- demo20 p14 VLM 仍返回无效 JSON（已知问题，不影响表格审计交付）
- 春风250Sr 的 8 条 manual_fixes 无 `candidate_ref`（目录和非候选驱动的手动修复记录），属于正常状态；其余 7 条引用均已解析
- 用户级 `pdf2md` skill 未在本计划中触及，无需同步

**计划闭环确认**

本计划的四个阶段（Step 0 复现 → 扩展扫描器 → skill 同步 → 真实样本扩展）和最终独立验收均已闭环。候选审计能力已稳定交付：`scripts/pdf-table-fix` 可在任意输出包上生成多信号候选、写入 manifest 登记的 `table_candidates.jsonl`，并由 `scripts/pdf-check-fixes` 校验完整性。人工确认、VLM 证据和页级修复的门禁已由 skill 文档固化，下游 `pdf-table-repair` 可直接承接。

## 风险与回滚

| 风险 | 控制措施 | 回滚 |
|---|---|---|
| 候选被误当作最终结构 | 强制 `needs_human`，skill 明确人工确认门禁 | 删除候选派生文件，不修改 canonical Markdown |
| 坐标聚类在复杂图片表格上误判 | 只输出 bbox/文本证据，不提交列结构 | 标记候选为 rejected，保留原始 HTML |
| 候选文件与 manifest 漂移 | 候选文件、hash 和 manifest 原子更新并由 checker 校验 | 恢复整个派生产物组 |
| 新脚本与现有 `pdf-table-fix` 重复 | 阶段 0 先做能力差距审计 | 取消新入口，回退到现有 helper |
| 外部报告页码无法在当前包复现 | 将报告降级为背景证据，登记待确认样本 | 不把该样本写入完成证据 |

## 验证

```bash
python3 scripts/check_plan_governance.py .
python3 scripts/check_plan_governance.py . --drift
git diff --check
```
