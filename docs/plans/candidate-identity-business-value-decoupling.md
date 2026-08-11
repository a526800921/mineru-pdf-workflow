# 计划：候选身份与业务值解耦、审核修订通道与局部重抽

## 计划状态

| 字段 | 内容 |
|---|---|
| 状态 | 提案（待实施） |
| 计划类型 | 结构化抽取身份契约、审核修订、重跑保护和 section 归属迭代 |
| 最后更新 | 2026-08-11 |
| 来源 | [150Sc 交付会话问题复盘](../issues/150sc-session-feedback.md) |

本计划是对 150Sc 最终交付会话中实际踩到问题的系统性回应。根因集中在**候选身份与业务值耦合**：`candidate_id` 包含 `section_path`/`parent_key` 等业务字段，任何业务层面的修正（parent_key、拆分、归属）都触发全链身份重建，连带失效审核决定与 overrides。相关既有计划 `semantic-parent-context-pipeline.md` 因同类耦合问题回滚，本计划不重复其父级抽取语义，只聚焦身份、修订和重抽基础设施。

## Step 0 Evidence（150Sc 会话实录）

### 已确认的实际问题

1. **身份哈希耦合业务字段**：`compute_candidate_id` 的 location 含 `section_path`、`parent_key`、`key_role`。改 draft 的 parent_key → candidate_id 变 → 审核决定、overrides 全部失效。本次为改左手把开关 parent_key（数字 →「左手把开关」），删了 15 条旧决定、重算、重写。
2. **审核绑定 hash，无低成本修订通道**：review_decisions 绑 candidate_hash。蓄电池补充、火花塞归属修正都要删旧决定 → 重算 → 写新决定。
3. **pair_groups 拆分触发全链重建**：扭矩表 5 行拆 10 条，row_index `1`→`1.1` 使 candidate_id 全变。且 pair 候选默认 needs_review，LLM 不能推进，10 条机械拆分全走 user_confirmed。
4. **prepare-ingest 覆盖用户最终产物修改**：用户在 ingest_ready.csv 改的 parent_key，重跑 prepare-ingest 被 draft 覆盖。
5. **enrich 只补空、拒覆盖已有非空**：左手把开关数字值无法被 overrides 覆盖，必须手工清空再 enrich。
6. **enrich 对段落候选不生效**：火花塞 3 条是 colon_line 段落，section_path_fallback 只处理表格。
7. **同页 section 归属错误**：p129 火花塞/怠速都 target_page=129，后写「怠速」吞掉整页，火花塞 3 条归属错误。
8. **重跑保护粒度太粗**：局部修一张表也要复制整包 force-rebuild 重抽。
9. **表号双轨不透明**：源码表号 vs 候选表号差一，排查误判。

### 真实产物证据

- 150Sc 包：`/Users/jafish/Documents/work/motofind/春风_manuals/春风_150Sc/data/`
- 关键产物：`ingest_ready.csv`（314 行 ready 305）、`ingest_batch.jsonl`（305 条）、`review_decisions.jsonl`（314 条）、`parent_context_overrides.csv`（167 条）
- 会话提交：`afb86f7`（参数表 parent_key）、`16ad9f1`（蓄电池）、`31ce83e`（扭矩表拆分）、`fbd4a54`（火花塞归属）

### 当前代码基线

| 位置 | 当前观察 | 计划要求 |
|---|---|---|
| `scripts/pdf-extract-data` | `compute_candidate_id` location 含 section_path/parent_key/key_role | 身份只锁来源位置（source_pdf/model/table_id/row_index/page），业务字段从 location 移除 |
| `scripts/pdf-prepare-ingest` | `compute_candidate_hash` 绑内容，需删旧决定才能修订 | 支持"修订"语义（superseded 或版本化），用户确认的修正不摧毁既有审计链 |
| `scripts/pdf-enrich-parent-context` | 只补空、拒绝覆盖已有非空；不处理段落候选 | 支持用户显式确认的覆盖；补齐段落候选 parent_key 路径 |
| `scripts/pdf-audit-extraction-coverage` | 源码表号 ↔ 候选表号映射不透明 | 输出对照表或标注候选表号 |
| section 归属 | 纯页级 page → path | 同页多子节时支持行级边界或报警回退 |

## 目标

- 把 `candidate_id` 收敛为"来源位置身份"，与 `section_path`/`parent_key`/`key_role` 解耦，使业务修正不再触发全链身份重建。
- 为审核决定增加低成本修订通道（superseded / 版本化），用户确认的修正保留审计痕迹。
- 让 pair_groups 拆分、参数表 parent_key 补全等机械操作不再被迫走 user_confirmed 全量重建。
- 保留用户在最终 ingest_ready 上的业务修正，prepare-ingest 重跑不静默覆盖。
- enrich 支持用户显式确认的覆盖已有非空值，并覆盖段落候选。
- 解决同页多子节 section 归属，输出表号对照便于排查。
- 提供单表/单候选的局部重抽入口。

## 非目标

- 不重做 `parent_key` 的抽取语义（参考已废弃的 `semantic-parent-context-pipeline.md`，不重复其父级来源优先级）。
- 不修改 PDF、segments 或 canonical Markdown 内容。
- 不改变 `record_id`、`source_row_hash`、业务 key/value/unit 和来源锚点的既有契约。
- 不直连数据库；仍是 CLI-only。

## 不变量

- 来源位置（source_pdf/model/table_id/row_index/page）不变时，candidate_id 稳定；业务值变化不改变 candidate_id。
- 审核决定必须能定位到来源位置；内容变化用 candidate_hash 或修订版本阻断过期决定。
- 用户在最终 ingest_ready 上的业务修正优先于 draft 候选值，重跑不得静默覆盖。
- 未审核、冲突、证据缺失的候选继续保持 not_ready/needs_review。
- 代码改动前进行影响分析；完成后运行 `detect_changes()`。
- 更新结构化/入库契约时，先更新项目级 `skills/pdf2md/SKILL.md`，再同步用户级副本。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 冻结身份/修订/重抽契约与样本矩阵 | 本次会话实录、代码审计 | 文档、命令、预期结果和失败判定齐全 | 提案 |
| 阶段 1 | candidate_id 与业务值解耦 | 阶段 0 通过，影响分析完成 | 150Sc 重跑 identity 稳定、回归通过 | 待实施 |
| 阶段 2 | 审核修订通道（superseded/版本化） | 阶段 1 通过 | 蓄电池/火花塞类修正不再全链重建 | 待实施 |
| 阶段 3 | 机械操作（pair 拆分、parent_key 补全）批量批准 | 阶段 2 通过 | 扭矩表拆分不强制 user_confirmed | 待实施 |
| 阶段 4 | 用户修正回流 + enrich 覆盖 + 段落候选 + 同页 section + 表号对照 + 局部重抽 | 阶段 3 通过 | 150Sc 全链路回归、门禁与治理 | 待实施 |

## 阶段 0：契约与样本矩阵

### Step 0 样本矩阵

| 样本 | 输入/基线 | 可执行验证 | 预期结果 | 失败判定 |
|---|---|---|---|---|
| 身份解耦 | draft 改 parent_key 不改来源位置 | prepare-ingest 前后 candidate_id 不变 | candidate_id 稳定 | candidate_id 变化 |
| 审核修订 | 蓄电池补充/火花塞归属修正 | 修订决定应用 | 不删旧决定即可更新 | 必须删旧决定 |
| pair 拆分 | 扭矩表 5 行 → 10 条 | extract 后 prepare | 10 条可 LLM 批量 approved | 必须 user_confirmed |
| 用户修正回流 | 用户改 ingest_ready parent_key | 重跑 prepare-ingest | 用户值保留 | 用户值被覆盖 |
| enrich 覆盖 | 左手把开关数字 → 左手把开关 | enrich 应用 | 覆盖成功且有审计 | 报错拒覆盖 |
| 段落候选 | 火花塞 3 条 colon_line | enrich 应用 | parent_key=火花塞 | 补不上 |
| 同页 section | p129 火花塞/怠速 | extract | 火花塞行归火花塞 | 整页归怠速 |
| 表号对照 | html_table:84/85 双轨 | audit 报告 | 输出对照表 | 仍心算映射 |
| 局部重抽 | 单表修正 | 局部重抽命令 | 只重建目标表 | 整包 force-rebuild |

### 阶段 0 完成条件

- [ ] 身份只锁来源位置，业务字段从 location 移除；兼容旧 candidate_id 迁移策略已冻结。
- [ ] 审核修订语义（superseded / 版本化）和 hash 阻断规则已冻结。
- [ ] 机械操作批量批准的门禁规则（规则明确 + 证据充分）已冻结。
- [ ] 用户修正回流优先级和 enrich 覆盖规则已冻结。
- [ ] 同页 section、表号对照、局部重抽的边界已冻结。

## 阶段 1：candidate_id 与业务值解耦

实施范围：`scripts/pdf-extract-data`（`compute_candidate_id`）、相关测试。

重点工作：

1. `candidate_id` 的 location 收敛为：`source_pdf`、`model`、`source_block_id`、`table_id`、`row_index`、`page_start`、`page_end`（来源位置），移除 `section_path`、`parent_key`、`key_role`。
2. 兼容策略：旧 candidate_id 若被审核/override 引用，提供映射表或迁移脚本，按来源位置新旧一致自动映射，歧义拒绝。
3. 内容/业务变化继续由 `candidate_hash` 阻断过期决定。

### 验证

- 150Sc 重跑：改 parent_key 前后 candidate_id 稳定，审核决定/override 不失效。
- 回归：`tests/test_pdf_extract_data.py`、`tests/test_pdf_prepare_ingest.py`。

## 阶段 2：审核修订通道

实施范围：`scripts/pdf-prepare-ingest`（`apply_review_decisions`）、`review_decisions.jsonl` 契约。

重点工作：

1. 支持 `review_status=superseded`：新决定可标记旧决定作废，不需删除旧记录（保留审计链）。
2. 支持"修订版本"：同一 candidate_id 的多代决定，以 `reviewed_at` 或版本字段取最新。
3. 用户确认的修正（review_actor=user + decision_basis=user_confirmed）允许覆盖 needs_review，也允许覆盖旧 approved（带 superseded 标记）。

### 验证

- 蓄电池/火花塞类修正：追加 superseded 决定即可，不删旧决定。
- 回归 + 150Sc 真实场景重放。

## 阶段 3：机械操作批量批准

实施范围：`scripts/pdf-prepare-ingest` 状态门禁、pair_groups 生成规则。

重点工作：

1. pair_groups 拆分候选：当拆分由明确配置（key/value 逐格对应）且证据充分时，允许 LLM 用 `evidence_exact` 批量 approved，不强制 user_confirmed。
2. 明确歧义边界：只有真正有歧义（跨格、合并语义不确定）才升级用户。

### 验证

- 扭矩表 5 行拆 10 条：LLM 可一次批准，无需用户逐条确认。

## 阶段 4：修正回流、覆盖、段落、section、表号与局部重抽

### 4.1 用户修正回流

`scripts/pdf-prepare-ingest` 重跑时，若用户在最终 ingest_ready 上改过 parent_key 等业务字段，优先保留用户值；与 draft 冲突时提示而非静默覆盖。建议：比较旧 ingest_ready 与 draft，业务字段以最终文件为准。

### 4.2 enrich 覆盖已有非空

`scripts/pdf-enrich-parent-context`：overrides 带 `force` 或 `user_confirmed` 标记时可覆盖已有非空值，记录审计；默认仍拒绝静默覆盖。

### 4.3 段落候选 parent_key

`pdf-enrich-parent-context` 或抽取层：为 colon_line/paragraph 候选补充 parent_key 路径，来源为 canonical 标题层级（当前 section 标题）。

### 4.4 同页 section 归属

`pdf-extract-data` section 归属：同页多个同级子节指向同一 target_page 时，回退到行号级 `build_section_path`，或输出告警。

### 4.5 表号对照

覆盖审计报告输出源码表号 ↔ 候选表号对照表，draft/ingest_ready 标注候选表号。

### 4.6 局部重抽

提供按 table_id 的局部重抽入口（如 `pdf-extract-data --table html_table:84`），只重建目标表候选，不整包 force-rebuild。

### 验证

- 150Sc 全链路回归、门禁与治理检查；局部重抽只改目标表。

## 测试覆盖率

- 单元与流水线 fixture：`tests/test_pdf_extract_data.py`、`tests/test_pdf_prepare_ingest.py`、`tests/test_pdf_export_ingest.py`、`tests/test_parent_context_pipeline.py`，新增身份解耦/修订/批量批准 fixture。
- 真实样本：150Sc 全链路重跑，identity 稳定、审核修订不删旧决定、pair 拆分 LLM 批量批、用户修正保留。
- 治理：`plan-governance-cli check . --strict-readiness`、`git diff --check`、两份 skill `cmp`。

## 失败策略与回滚

- 身份解耦导致旧候选无法稳定迁移、门禁绕过或字段丢失：停止，保留 not_ready。
- 修订通道破坏既有审核链或 hash 校验：恢复提交前快照。
- 用户修正回流引入静默覆盖：回退为 draft 为准并提示冲突。
- 代码与配置改动通过版本控制回退；不修改 PDF、segments、canonical Markdown 或数据库。

## 相关计划与证据

- [150Sc 交付会话问题复盘](../issues/150sc-session-feedback.md)
- [结构化父级上下文统一处理（已废弃）](semantic-parent-context-pipeline.md)
- [pdf2md 顺序工作流](pdf2md-skill-sequential-workflow.md)
- [pdf2md 阶段中心化重组](pdf2md-skill-phase-centric-reorganization.md)
- [结构化数据抽取](structured-data-extraction.md)
- 真实产物：`/Users/jafish/Documents/work/motofind/春风_manuals/春风_150Sc/data/`
