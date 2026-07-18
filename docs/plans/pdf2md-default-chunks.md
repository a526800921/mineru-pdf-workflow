# 计划：pdf2md 默认生成 chunks

## 计划状态

- 状态：已完成
- 当前阶段：阶段 1：默认交付契约同步（已完成）
- 最后更新：2026-07-18

## 目标

将阶段 9 的 `data/chunks.jsonl` 从“需要向量化时才生成”的可选产物，调整为 pdf2md 标准流程默认生成的交付产物。

## 范围

- 更新项目级 `skills/pdf2md/SKILL.md` 的阶段 9、交付等级和下游消费契约。
- 同步更新 `/Users/jafish/.claude/skills/pdf2md/SKILL.md`。
- 继续使用既有 `scripts/pdf-export-chunks <package>`，不改变切块算法、字段、页锚点或 384 token 上限。
- 每次达到阶段 9 时，先生成/校验 `data/chunks.jsonl`，再生成或更新 `downstream_delivery.md`。

## 非目标

- 不修改 chunks 的切分算法或 schema。
- 不把 `toc.md`、`review.md` 或目录遍历结果作为 chunks 输入。
- 不自动执行下游数据库写入。
- 不为历史包批量重跑 PDF→Markdown；只有本轮交付或用户明确要求时生成 chunks。

## Step 0 证据

当前 Aura 包在修改前的标准事实源仍将 chunks 标为“可选”，但既有 CLI 已能按 `manifest.files.markdown` 安全生成。可执行基线：

```bash
scripts/pdf-export-chunks /Users/jafish/Documents/work/motofind/春风_manuals/春风_150_Aura
```

基线结果：生成 `data/chunks.jsonl` 365 条，页码范围 1–191，最大 379 token；canonical Markdown、manifest 和页码契约均可读取。该证据说明本次只需调整默认编排和交付契约，不需要新增算法或接口。

## 阶段 1：默认契约同步

1. 将阶段 9 改为必须执行 `pdf-export-chunks`。
2. 将最终交付等级和 `downstream_delivery.md` 改为明确要求 chunks 已生成；生成失败则阶段 9 阻断。
3. 同步项目级和用户级 skill。
4. 用当前 Aura 包重新生成 chunks 和交付入口，记录真实数量、页码范围、最大 token、批次数量和 hash。

## 验证方式

- `scripts/pdf-export-chunks <package>` 成功生成 `data/chunks.jsonl`。
- 每行包含 `id`、`content`、`page`、`section`、`token_count`，且最大 token 不超过 384。
- chunks 输入等于 `manifest.files.markdown` 指定的 canonical Markdown。
- `downstream_delivery.md` 与当前文件、manifest、chunks 和入库批次数量一致。
- `cmp skills/pdf2md/SKILL.md /Users/jafish/.claude/skills/pdf2md/SKILL.md` 通过。
- `plan-governance-cli check . --strict-readiness` 通过。

## 完成条件

- 两份 skill 对“默认生成 chunks”的表述一致。
- 当前 Aura 包存在可消费的 `data/chunks.jsonl` 和更新后的 `downstream_delivery.md`。
- chunks 生成失败时的阻断边界、输入来源和回滚方式已写入 skill。
- 不改变现有入库批次、审核状态或下游数据库边界。

## 失败与回滚边界

- manifest 缺失、canonical Markdown 路径非法或 chunks 生成失败时，不生成新的交付入口，并将阶段 9 标记为阻断。
- 回滚只撤销“默认执行”契约，保留既有 `scripts/pdf-export-chunks` 和已生成 chunks；不删除用户已有产物。

## 阶段 1 独立验收复核（2026-07-18，通过）

结论：阶段 1 完成，默认 chunks 契约已生效。

- 两份 skill 已同步：`cmp skills/pdf2md/SKILL.md /Users/jafish/.claude/skills/pdf2md/SKILL.md` 通过。
- 当前 Aura 已执行 `scripts/pdf-export-chunks <package>`：365 条 chunks，页码 1–191，最大 379 token。
- `data/chunks.jsonl` 每行字段完整，输入由 `manifest.files.markdown` 指定，未超过 384 token 上限。
- `downstream_delivery.md` 已按当前 manifest、chunks 和入库批次重新生成。
- 结构化批次当前 458 条，`ingest_ready.csv` hash 与 `ingest_manifest.json` 一致。
- `scripts/pdf-audit-extraction-coverage <package> --gate`：源行 567，未解决缺口 0。
- 相关回归测试：`pytest -q tests/test_pdf_prepare_ingest.py tests/test_pdf_enrich_parent_context.py tests/test_pdf_export_ingest.py` 为 27 passed。
- 文档变更后的 `cmp`、chunks 字段/上限校验和 `git diff --check` 已通过。

## Test Coverage（测试覆盖率证据）

本计划不新增业务代码，使用现有结构化入库与导出回归作为行为覆盖证据：

```text
pytest -q tests/test_pdf_prepare_ingest.py tests/test_pdf_enrich_parent_context.py tests/test_pdf_export_ingest.py
27 passed
```

另有当前真实包 chunks 契约校验：365 条记录均包含 `id/content/page/section/token_count`，最大 `token_count=379`，不超过 384 上限。
