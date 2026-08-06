# 重跑保护 Step 0 复现记录

**日期**：2026-08-05
**样本**：`/Users/jafish/Documents/work/motofind/春风_manuals/春风_150_Aura` 只读副本
**目的**：验证普通 `pdf-extract-data` 是否会覆盖已有审核/人工修改后的结构化草案。

## 执行边界

- 原始 Aura 包未修改。
- 使用 `mktemp -d` 创建临时副本后直接执行：

```bash
scripts/pdf-extract-data <temporary-aura-package>
```

## 结果

| 文件 | 执行前 | 执行后 | 结论 |
|---|---:|---:|---|
| `quick_lookup_draft.csv` | 488 行，SHA-256 `ace20fc186dfffe63fef0099b4b1a13002a0684cc7a3b095c5a6c51264b4e06a` | 474 行，SHA-256 `80701cd14764020e42bfdf4293332636b28133d29e8e894969caef055432bb2e` | 被静默重建，减少 14 行 |
| `review_decisions.jsonl` | SHA-256 `08d68c4bab090e58077bae9e621fcf9a9814eaffc15c6494338dfcea61114044` | 不变 | 脚本未修改 |
| `review_overrides.csv` | 356 行 | 356 行，不变 | 脚本未修改 |
| `manual_fixes.jsonl` | SHA-256 `e48d3c7087a61830d43a1984e38e331bfc4872fc74c76126c18adfc6896e0b41` | 不变 | 脚本未修改 |
| `parent_context_overrides.csv` | 417 行 | 417 行，不变 | 脚本未修改 |
| `ingest_ready.csv` | 488 行 | 488 行，不变 | 脚本未修改 |
| `ingest_batch.jsonl` | SHA-256 `ec2cc6bee4e0cb4c882696cb1b48c58b1e91be899fd74bdd385c2112539a19c5` | 不变 | 脚本未修改 |

脚本返回码为 `0`，并生成新的 `verification.csv`、`fixtures_result.md`。因此当前缺陷是“已审核草案被静默覆盖且命令成功”，而不是下游门禁主动拒绝。

## Step 0 结论

达到阶段 1 的最小准入条件：只需在 `pdf-extract-data` 生成草案前检查已有审核/人工修正产物；发现保护对象时非零退出，不写入原包，并提示 LLM 使用临时副本处理局部修正。当前不需要自动候选合并、公共身份迁移或 parent_key Schema 改造。

## 修复后复验

2026-08-05 在同一 Aura 包的临时副本中再次运行普通命令：

```bash
scripts/pdf-extract-data <temporary-aura-package>
```

结果：返回码为 `1`，提示普通重跑已阻断；`data/quick_lookup_draft.csv` 前后 SHA-256 均为 `ace20fc186dfffe63fef0099b4b1a13002a0684cc7a3b095c5a6c51264b4e06a`，没有进入任何抽取产物写入流程。原始 Aura 包未修改。
