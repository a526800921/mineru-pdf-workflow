# 问题总结：TOC 页覆盖率低导致 needs_review 路径不产出合并 Markdown

## 背景

对 demo5.pdf（5 页样本）运行 `pdf-seg` + `pdf-auto` 自动流水线时，流程卡在 `needs_review` 状态，未产出合并 Markdown。

## 流程路径

```text
pdf-seg (segment_size=1, effort=medium, hybrid-engine)
  → 每页单独分段 p0001-0005
  ↓
pdf-auto validate (threshold=0.82)
  → p0001-0001: 95.74% ✅ pass
  → p0002-0002:  2.49% 🔍 review_only (目录页)
  → p0003-0003:  0.71% 🔍 review_only
  → p0004-0004: 17.59% 🔍 review_only
  → p0005-0005: 44.94% 🔍 review_only
  → 0 段触发 rerun, 4 段 review_only
  ↓
needs_review 路径:
  1. ✅ repair() 修正 TOC 分段 md
  2. ✅ 生成 review.md
  3. ❌ 不执行 pdf-merge → 无合并产物
  4. ⛔ exit 2
```

**死锁**：`all_passed` 时才触发 `pdf-merge` → `repair_merged()`，但 `needs_review` 路径只修分段不合并。

## 三个场景的 TOC 输出对比

### 场景 A：`pdf-seg` 脚本输出（有问题的路径）

```
### 目录

前言言言言言言言言言言言言言言言言言言言言言言言言...
```

**effort=medium, segment_size=1。** MinerU 输出乱码（"言"字重复）。覆盖率 2.49% → `review_only`。

### 场景 B：直接 API 调用（effort=medium）

```
### 目录

.... 8

重要的注意事项 ............................... .......10

序列号 ........... .... 12
...
```

**直接调用 API, start_page_id=1, end_page_id=2, effort=medium。** 部分条目标题缺失（第 1 行".... 8"缺"前言"），后续正常。

### 场景 C：直接 API 调用（effort=high）

```
### 目录

.... 8

重要的注意事项 ............................... .......10

序列号 ........... .... 12
...
```

**直接调用 API, effort=high。** 与 medium 输出几乎一致，同样缺条目标题。VLM 不能改善虚线引导符的文本层提取。

### 参考基准：demo60（原始已跑通结果）

```
### 目录

前言....8  
重要的注意事项....10  
序列号....12  
...
```

**demo60 同一份 PDF，8 页合段（p0001-0008）处理。** 目录干净、条目标题+页码完整。原因：当时的旧流程中 `repair()` 在 merge 前写回分段 md，且 demo60 没有 `review_only` 阻断。

## 根因

1. **`effort=medium` 对目录页产生乱码输出** → `pdf-validate` 覆盖率 2.49% → `review_only`
2. **非文字页（p0003~p0005）覆盖率同样低** → 即使 TOC 修好，4/5 段仍是 `review_only` → 永远走不到 `all_passed`
3. **`needs_review` 路径不执行 merge** → `repair()` 修了分段但无最终合并产物

## 关键文件

| 来源 | 路径 |
|------|------|
| pdf-seg 乱码输出 | `pdf/demo5/segments/p0002-0002/demo5/hybrid_auto/demo5.md` |
| pdf-auto 验证结果 | `pdf/demo5/review.md` |
| API medium 输出 | `/Users/jafish/Documents/models/mineru-api-output/.../demo5/hybrid_auto/demo5.md` |
| API high 输出 | `/Users/jafish/Documents/models/mineru-api-output/.../demo5/hybrid_auto/demo5.md` |
| demo60 参考基准 | `pdf/demo60/segments/p0001-0008/demo60/hybrid_auto/demo60.md` |

## 待决策

- `needs_review` 路径是否也应执行 `pdf-merge`，输出合并 md 供人工复核参考？
- 或者先修 TOC 再验证，避免 TOC 页因乱码进入 review_only？
