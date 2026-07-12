# 计划：pdf-table-audit 候选审计与 pdf2md-fix skill 收敛

## 计划状态

- 状态：实施中
- 当前阶段：阶段 1 验收未通过 — 候选/manifest 写入失败回滚补强
- 最后更新：2026-07-12

本文档是“表格异常自动发现”增量能力的事实源。它承接 [pdf2md-fix 人工复核与内容修复工作流](pdf2md-fix-manual-workflow.md)，不重新定义人工修复、页级表格重建、VLM 或 HTML pretty-print 契约；页级表格重建另见 [pdf-table-repair](pdf-table-repair.md)。

## 背景与 Step 0 证据

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

### 阶段 2：skill 与人工/VLM流程同步

1. 在项目级 `skills/pdf2md-fix/SKILL.md` 中固定审计命令、候选产物、人工确认顺序和 `manual_fixes.jsonl` 进入条件。
2. 明确坐标聚类、rowspan 推断和列语义只能生成候选证据，不能自动提交结构结论。
3. 固定 VLM 使用 `qwen3-vl-8b`，ModelPad API `http://127.0.0.1:9999`，VLM endpoint `http://127.0.0.1:9005`；VLM只回答文字/数字是否与 PDF 证据一致。
4. 同步 `/Users/jafish/.claude/skills/pdf2md-fix/SKILL.md`，并增加候选文件与 manifest hash 的检查清单。

完成条件：人工可以从 `pdf-auto` 输出包开始，按 skill 完成“扫描 → 候选 → 人工/VLM确认 → 页锚点修复 → manifest 同步”，且不存在第二正文入口。

### 阶段 3：真实样本扩展

1. 复核 demo20、demo60 和当前春风输出包中的 8192/异常列页。
2. 若路径和证据可复现，再纳入 p87、p90、p88–p93、p132–p133 等报告样本。
3. 统计发现率、人工采纳率、误报类型和重复劳动；不以“自动发现”替代“人工修复完成”。

完成条件：多个真实样本上的候选证据、人工修复记录、VLM证据和 manifest 登记可闭环，且无全局替换漂移。

### 阶段 4：独立验收

- 候选扫描命令回归通过，正常包、无候选包、缺失字段包和失败回滚包均有证据；
- `table_candidates.jsonl` 的每条记录都有页码、页锚点、来源和 `needs_human`；
- `scripts/pdf-check-fixes` 能校验候选文件路径、hash 和 manifest 关联；
- 项目级 skill 与用户级 skill 一致；
- `pytest -q`、相关 shell 回归、治理检查和 drift 检查通过。

## 风险与回滚

| 风险 | 控制措施 | 回滚 |
|---|---|---|
| 候选被误当作最终结构 | 强制 `needs_human`，skill 明确人工确认门禁 | 删除候选派生文件，不修改 canonical Markdown |
| 坐标聚类在复杂图片表格上误判 | 只输出 bbox/文本证据，不提交列结构 | 标记候选为 rejected，保留原始 HTML |
| 候选文件与 manifest 漂移 | 候选文件、hash 和 manifest 原子更新并由 checker 校验 | 恢复整个派生产物组 |
| 新脚本与现有 `pdf-table-fix` 重复 | 阶段 0 先做能力差距审计 | 取消新入口，回退到现有 helper |
| 外部报告页码无法在当前包复现 | 将报告降级为背景证据，登记待确认样本 | 不把该样本写入完成证据 |

## 治理验证

```bash
python3 scripts/check_plan_governance.py .
python3 scripts/check_plan_governance.py . --drift
git diff --check
```
