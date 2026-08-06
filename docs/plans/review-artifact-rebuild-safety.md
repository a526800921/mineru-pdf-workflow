# 计划：结构化审核产物重跑安全修复

## 计划状态

- 状态：已完成
- 当前阶段：阶段 2：LLM 兜底与真实包验收（已完成）
- 最后更新：2026-08-05
- 计划定位：给 PDF 结构化抽取增加最小重跑保护，防止普通重跑覆盖已经审核、确认或人工修改过的成果。

本计划的状态、依赖、推荐顺序和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准；本文件承载范围、兼容契约、Step 0、样本矩阵、阶段准入和验收证据。

本计划复用 [data-ingestion-pipeline](data-ingestion-pipeline.md)、[llm-first-review-workflow-hardening](llm-first-review-workflow-hardening.md)、[pdf2md-fix-manual-workflow](pdf2md-fix-manual-workflow.md) 和 ADR 0003 的现有审核/回滚边界；`parent-context-upstream-enrichment`、`extraction-coverage-reconciliation` 只作为下游验证背景，不在本计划第一阶段改造。150 Aura 运行报告作为背景证据，不替代本计划的可执行 Step 0。

本计划与现有“最终 Markdown 与入库前结果质量门禁”计划有实现文件重叠，但职责不同：后者负责最终 Markdown 异常是否阻断入库，本计划只负责重跑时保护已完成审核成果；不得把两个计划的字段、阈值或完成条件互相复制。

### 核心控制点

重跑流程的默认行为必须是“保护已完成成果”：凡是已经审核、用户确认或人工修改过的内容，都不能被普通重跑直接覆盖、删除或重新解释。任何需要替换历史产物的操作都必须显式触发，并由调用者在备份或临时副本中提供回滚边界；本计划不建设自动合并或自动迁移。

## 需求探索

### 来源与已确认观察

- 来源报告：`/Users/jafish/Documents/work/motofind/docs/reports/150aura-maintenance-fix-2026-08-05.md`。
- 直接重跑 `pdf-extract-data` 会覆盖 `data/quick_lookup_draft.csv`，报告记录的 118 条历史补充候选会丢失，并可能重新引入历史已拒绝候选。
- 当前 `pdf-prepare-ingest` 的 `record_id` 和 `candidate_hash` 与候选内容绑定；内容修改后，旧审核决定必须显式迁移或拒绝应用。`candidate_id` 目前主要绑定来源位置，但其规则仍包含 `parent_key`，不能假定所有字段修改都保持候选身份稳定。
- 当前 `pdf-enrich-parent-context` 只补空 `parent_key`，已有非空值不能被覆盖；覆盖文件也不允许用空值表达“明确清空”。这无法安全表达报告中“历史正确值为空、draft 残留错误值”的场景。
- 报告还记录了 CLI 误用和页码字符串排序问题；它们属于运行手册和验证门禁缺口，不应继续依赖操作者记忆。
- 报告的“9 处候选修正”和最终 `manual_fixes.jsonl` 增加 10 条记录之间存在计数口径差异，需要在阶段 0 固定“候选身份变更数”和“字段修复数”的分别统计。

### 用户确认的需求结论（2026-08-05）

- 核心目标是让 LLM 在重跑流程时保护之前已经审核、确认和修改过的内容，降低已完成数据失控风险。
- 本轮只优先解决“默认不覆盖”这一流程控制点；身份、parent_key、兼容和验证细节不预先扩展，只有真实回归证明无法由 LLM 和现有门禁兜底时才追加。
- 对少量内容修正、审核身份更新和运行小瑕疵，优先由 LLM 在临时副本中编排现有 CLI 和精确脚本处理，不为每种异常建设新的通用自动化。
- 用户已授权直接推进到结束；本轮只实现写入前保护、显式 force 边界、最小回归和操作说明，不扩展自动化范围。

### 目标

1. 重新抽取或局部重跑时，默认不破坏已有草案、审核决定、补充候选、拒绝记录和人工修正。
2. 被保护的输出包遇到重跑时，在写入前明确失败并提示 LLM 转入临时副本/局部修复流程。
3. 使用 150 Aura 真实包和最小 fixture 证明：普通重跑不会改变历史成果，保护失败后由 LLM 在临时副本中继续处理。

### 范围

- `pdf-extract-data` 的重跑前置检查、暂存提示和显式覆盖边界。
- 现有审核/修改/交付产物的识别：包根目录的 `review.md`、`downstream_delivery.md`，以及 `data/` 下的 `manual_fixes.jsonl`、`review_decisions.jsonl`、`review_overrides.csv`、`parent_context_overrides.csv`、`ingest_ready.csv`、`ingest_batch.jsonl`、`ingest_manifest.json` 和 `chunks.jsonl`。
- 最小回归 fixture、150 Aura 真实包只读回放和 `skills/pdf2md/SKILL.md` 双份同步。

### 非目标

- 不新增 MCP Server、MCP 兼容层或数据库导入逻辑；继续遵守 CLI-only 边界。
- 不修改原始 PDF、`segments/`、`content_list*.json`；没有单独用户确认时不改 canonical Markdown。
- 不在本计划中重新设计业务字段抽取、跨页表格语义或 parent_key 的自动推理规则。
- 不通过全局替换或直接编辑审核/入库产物绕过身份和 hash 门禁。
- 不实现自动候选合并、新的公共身份键、完整 `parent_key` clear Schema、页码校验重构或版本化审核迁移；这些都只有后续证据证明必要时才另建/扩展计划。
- 不把所有小瑕疵都转化为通用脚本；允许 LLM 在临时副本中按现有门禁完成一次性处理。

### 暂定推荐方案与取舍

| 方案 | 做法 | 取舍 |
|---|---|---|
| A（推荐） | 抽取前检查审核/修改产物；发现保护对象时默认非零退出，不写入原包，并提示 LLM 使用临时副本做局部修复 | 改动最小、风险最低；少量修正仍依赖 LLM 编排 |
| B | 自动按来源位置保留/合并旧审核结果 | 需要更多身份和冲突规则，当前不做 |
| C | 全量重抽后按相似度自动合并 | 容易重新引入历史拒绝或错误候选，不采用 |

用户已确认采用 A；阶段 0 只需验证保护对象识别范围和“不写入原包”的失败边界。

### 未决问题与阻塞级别

| 问题 | 级别 | 处理时点 |
|---|---|---|
| 重跑保护的 CLI 参数名和提示文案 | 低 | 阶段 0/1 实施设计 |
| 具体一次性修正是否需要身份迁移 | 低 | 由 LLM 和现有 hash 门禁处理；只有重复出现才另建计划 |
| 报告中的 9/10 修正计数如何拆分 | 低 | Aura 回放记录，不作为新通用契约 |
| 当前项目是否提交小型 fixture，还是只使用外部包的只读副本 | 中 | 阶段 0；影响 CI 可复现性 |

需求探索已完成；以上仅保留实施层面的待验证细节，不改变“默认保护已完成成果”的已确认核心。

## 不变量与安全边界

- 默认重跑不得静默删除、覆盖或重新解释历史候选、审核决定、补充候选、拒绝记录或人工修正。
- 保护检查必须在任何写入 `quick_lookup_draft.csv` 之前失败；失败时原包 hash 不变。
- 全量重建必须显式使用 `--force-rebuild`；调用者应先备份或使用临时副本，且不自动应用旧审核决定。
- 小范围修正允许由 LLM 在临时副本中编排现有脚本，但仍必须经过现有 `record_id`/`candidate_hash`、`pdf-check-fixes` 和 batch 门禁。
- 身份、parent_key 和页码的额外契约不在本阶段新增；出现无法兜底的真实失败时暂停并更新计划。

## 影响模块或文件

- `scripts/pdf-extract-data`
- `scripts/pdf-prepare-ingest`、`scripts/pdf-enrich-parent-context`、`scripts/pdf-export-ingest`（第一阶段只作为下游只读验证入口）
- `tests/test_pdf_extract_data.py`
- `tests/` 中新增的重跑保护 fixture；现有入库测试只在回归验证中复用
- `skills/pdf2md/SKILL.md`
- `/Users/jafish/.claude/skills/pdf2md/SKILL.md`
- `docs/PLAN_MAP.md`

涉及结构化抽取、审核、入库导出或阶段 9 交付契约的实现变更，实施前必须先更新本计划；若公共字段、状态或 CLI 行为发生变化，先补充正式迁移/ADR，再同步项目级和用户级 `pdf2md` skill。

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 主要产物 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 复现重跑覆盖并冻结最小保护边界 | 150 Aura 只读副本或等价 fixture 可复现报告问题 | Step 0 证据、最小契约和回滚边界 | 已完成 |
| 阶段 1 | 增加重跑前置保护 | 阶段 0 通过；默认不覆盖策略已冻结 | 前置检查、显式 force 入口、最小回归 | 已完成 |
| 阶段 2 | 同步 LLM 操作说明和真实包验收 | 阶段 1 通过 | skill 更新、Aura 回放、治理收尾 | 已完成 |

## 当前阶段

阶段 2：LLM 兜底与真实包验收（已完成）。

### 阶段准入摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 已完成 |
| Step 0 | 已完成：150 Aura 临时副本中，`pdf-extract-data` 返回码 0，但 `quick_lookup_draft.csv` 从 488 行变为 474 行，原审核/修正/ready/batch 文件 hash 保持不变。详见 [Step 0 复现记录](../reports/review-artifact-rebuild-safety-step0-2026-08-05.md)。 |
| 样本矩阵 | F0 150 Aura 外部真实包；F1 具有少量审核/人工修正文件的最小 fixture；F2 无审核成果的首次抽取；F3 显式 force 重建。 |
| 验证方式 | 保护回归、全量测试、Aura 临时副本回放、两份 skill 同步检查、治理严格检查和 GitNexus 变更范围检查。 |
| 失败/回滚边界 | 普通重跑在任何写入前失败，原包 hash 不变；force 只在已备份或临时副本中使用，失败时丢弃临时副本，不交付新 batch；本计划不提供自动回滚。 |
| 当前阻塞项 | 无。 |
| 最新独立准入复核 | 2026-08-05：通过，阶段 2 已完成；381 个测试通过，Aura 临时副本返回码为 1 且 draft hash 不变，两份 skill 已同步。 |

## Step 0 证据

基线类型：真实运行报告 + 外部 150 Aura 输出包只读副本 + 最小失败回归 fixture。报告是现象证据；可执行重现和 hash 快照是实施准入证据。

阶段 0 实际证据已写入 [Step 0 复现记录](../reports/review-artifact-rebuild-safety-step0-2026-08-05.md)：普通重跑返回 0，但草案由 488 行变为 474 行；保护文件未变。

| 样本 | 输入/基线 | 可执行命令 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|---|
| F0 真实包快照 | `/Users/jafish/Documents/work/motofind/春风_manuals/春风_150_Aura` | 在 `mktemp -d` 副本中记录 `quick_lookup_draft.csv` hash，运行 `scripts/pdf-extract-data <package>` | 修复前复现 draft 被覆盖；修复后发现保护文件时在写入前退出，原 hash 不变 | 原包 draft 被改写、审核文件被删除或产生半成品 | 临时目录 hash 清单和 stderr |
| F1 最小保护 fixture | draft + 任一审核/人工修正标记文件 | 直接运行 `scripts/pdf-extract-data <package>` | 非零退出且没有替换 draft、verification 或 fixtures | 任一受保护文件被覆盖 | pytest 临时目录 |
| F2 首次抽取 | 只有 manifest、Markdown、segments，无审核成果 | 运行 `scripts/pdf-extract-data <package>` | 正常生成 draft 和现有验证产物 | 被误判为受保护包或无法首次生成 | pytest 临时目录 |
| F3 显式 force | 带审核成果的临时副本 | 运行显式 force 参数并记录备份 hash | 只在显式模式执行，失败可恢复，旧审核决定不自动应用 | force 仍静默应用旧决定或失败破坏旧文件 | 临时备份和回滚报告 |

### Step 0 可复现命令草案

以下命令只允许在临时副本中执行；正式包路径和备份 hash 需在执行前再次确认：

```bash
PKG=/Users/jafish/Documents/work/motofind/春风_manuals/春风_150_Aura
TMP_DIR=$(mktemp -d)
cp -a "$PKG" "$TMP_DIR/package"

python3 - <<'PY' "$TMP_DIR/package"
import csv, json, sys
from pathlib import Path

pkg = Path(sys.argv[1])
data = pkg / "data"
for name in ("quick_lookup_draft.csv", "review_decisions.jsonl",
             "review_overrides.csv", "ingest_ready.csv", "ingest_batch.jsonl"):
    path = data / name
    print(name, path.exists(), path.stat().st_size if path.exists() else 0)
if (data / "quick_lookup_draft.csv").exists():
    with (data / "quick_lookup_draft.csv").open(newline="", encoding="utf-8") as f:
        print("draft_rows", sum(1 for _ in csv.DictReader(f)))
PY
```

该命令是历史基线入口；实施后的可执行证据由最小 fixture、全量 pytest 和 Aura 临时副本回放补充。

## 阶段 1～2 计划要点

### 阶段 1：抽取重跑保护（核心）

- 在写入任何抽取产物前检查保护文件；已存在审核/补充/交付产物时，默认明确失败，不做自动合并。
- 全量覆盖必须显式使用 `--force-rebuild`，并由调用者在备份或临时副本中执行。
- 失败提示说明：复制到临时目录后，由 LLM 按用户确认的局部修正流程继续，不要在原包上重抽。
- 只增加“写入前保护”和最小回归，不增加来源定位、候选合并或自动迁移平台。

本阶段优先级高于后续身份和 parent_key 扩展：只要普通重跑仍能直接覆盖已完成成果，后续阶段不得宣称完成。

### 阶段 2：LLM 兜底与真实包验收

- LLM 继续负责小范围内容修正、审核身份更新和一次性运行瑕疵的编排；必须在临时副本中完成，并使用现有 hash、`pdf-check-fixes` 和入库门禁。
- 不把一次性身份迁移或 parent_key 清空提升为新的通用契约；同类问题重复出现时另建小计划。
- 在 150 Aura 临时副本验证：普通重跑被阻断，原包成果不变；局部修正继续由 LLM 和既有门禁负责，本计划不新增自动化编排。
- 若新增字段、状态、CLI 参数或输出文件，先更新项目级 `skills/pdf2md/SKILL.md`，再同步 `/Users/jafish/.claude/skills/pdf2md/SKILL.md`。
- 完成后更新本计划、`PLAN_MAP.md` 和验证证据；运行 `plan-governance-cli check . --strict-readiness`。

## 验证方式

已执行定向回归、全量 pytest、150 Aura 临时副本回放、两份 skill 同步检查、治理严格检查和 `git diff --check`；结果记录在本计划最新复核和 Step 0 报告中。

### 定向验证

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q \
  tests/test_pdf_extract_data.py \
  tests/test_pdf_rebuild_protection.py
```

### 全量与治理验证

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q
plan-governance-cli check . --strict-readiness
git diff --check
```

真实包验收只需直接执行 `scripts/pdf-extract-data <package>` 验证保护前置检查，并在 LLM 临时修正流程结束后复用现有 `pdf-check-fixes` 和阶段 8/9 验收。若修改了符号，实施前按项目 GitNexus 规则运行 upstream impact；提交前运行 `detect_changes()`。

## 完成条件

- 普通重跑已有审核包不会静默覆盖、删除或重新解释历史候选、审核决定、拒绝项和人工修正；这是本计划的首要完成条件。
- 保护检查在写入前失败，原包 `quick_lookup_draft.csv`、审核文件和既有交付产物 hash 不变。
- 无审核成果的首次抽取仍正常工作；显式 force 才允许重建，并且有备份和回滚边界。
- 保护失败后 skill 明确指导 LLM 使用临时副本；既有 hash、`pdf-check-fixes` 和阶段 8/9 门禁保持不变，本计划不重复建设这些门禁。
- 150 Aura 真实包验证历史 118 条补充候选未因普通重跑丢失；9/10 修正计数仅需在报告中说明，不新增通用字段。
- 项目级与用户级 `pdf2md` skill、专项计划、`PLAN_MAP.md` 已同步。
- 最新独立准入/验收复核明确写出通过，且 `plan-governance-cli check . --strict-readiness` 通过。

## 风险与回滚

| 风险 | 影响 | 缓解 | 回滚 |
|---|---|---|---|
| 保护条件过宽 | 首次抽取被误阻断 | 只在 draft 与审核/修改标记同时存在时触发；用首次抽取 fixture 验证 | 关闭保护分支，恢复原入口 |
| force 被误用 | 已完成成果被覆盖 | 显式参数、备份、用户确认和不自动应用旧审核 | 恢复备份，删除重建产物 |
| LLM 临时修正失败 | 局部修复无法交付 | 继续使用现有 hash、`pdf-check-fixes` 和阶段 8/9 门禁 | 丢弃临时副本，不动正式包 |
| 真实 Aura 不在当前仓库 | CI 无法复现完整样本 | 最小 fixture 做 CI，Aura 只做只读阶段验收 | 保持计划在阶段 0，不宣称完成 |

## 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 日期 | 2026-08-05 |
| 阶段 | 阶段 2 |
| 结论 | 通过：阶段 2 已完成，计划达到完成条件 |
| 证据 | 381 个 pytest 通过；Aura 临时副本普通重跑返回码 1，`quick_lookup_draft.csv` 前后 SHA-256 均为 `ace20fc186dfffe63fef0099b4b1a13002a0684cc7a3b095c5a6c51264b4e06a`；普通重跑未写入任何文件；两份 skill `cmp` 一致；治理严格检查通过 |
| 复核者 | Codex（独立只读验收复核） |

## 独立复核记录

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-08-05 | Codex（只读准入复核） | 阶段 0 | 通过：达到阶段 1 `待实施` 标准 | 150 Aura 临时副本复现：返回码 0 但 draft 488→474；原审核、人工修正、ready 和 batch 文件未被脚本修改；用户已确认最小保护方案 |
| 2026-08-05 | Codex（只读准入复核） | 阶段 1 | 通过：达到阶段 1 `待实施` 标准 | 用户已确认只实现写入前保护和最小回归，不建设自动合并或新的公共契约；当前进入实施 |
| 2026-08-05 | Codex（独立只读验收复核） | 阶段 2 | 通过：阶段 2 已完成，计划达到完成条件 | 381 个 pytest 通过；Aura 临时副本普通重跑返回码 1 且 draft hash 不变；两份 skill 同步；治理严格检查通过 |

## Test Coverage（测试覆盖率证据）

- 阶段 0：已完成；证据见 [Step 0 复现记录](../reports/review-artifact-rebuild-safety-step0-2026-08-05.md)。
- 阶段 1：已完成；保护条件、首次抽取、显式 force、失败不写入和根目录审核文件 fixture 均通过。
- 阶段 2：已完成；150 Aura 临时副本回放、skill 双份同步和治理严格检查通过。LLM 局部修正继续复用既有门禁，未新增自动化。

实际验证命令及结果：

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q
# 381 passed, 5 warnings
```
