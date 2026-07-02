# pdf2md 全管线运行总结

> 日期：2026-07-02 | 项目：mineru-pdf-workflow

## 运行记录

| # | 包 | 页数 | 大小 | API 状态 |
|---|---|---|---|---|
| 1 | demo5 | 5 | 380KB | 有 → 被杀 |
| 2 | demo20 | 20 | 2.2MB | 自动恢复 → 被杀 |
| 3 | demo5 | 5 | 380KB | 又恢复 → 被杀 |

## 各包结果

| 步骤 | demo5 (第1次) | demo5 (第2次) | demo20 |
|---|---|---|---|
| pdf-seg | 5 段完成 | 5 段完成 | 20 段完成 |
| pdf-auto | 1 pass / 4 review_only | 1 pass / 4 review_only | 13 pass / 7 review_only |
| pdf-merge | 手动 | 手动 | 手动 |
| pdf-extract-data | 0 行草案 | 0 行草案 | **53 行草案** |
| pdf-prepare-ingest | 0 行 / 0 冲突 | 0 行 / 0 冲突 | 53 行 / **1 组冲突** |
| pdf-export-ingest | 空批次 | 空批次 | 空批次（无审核覆盖） |

### review_only 分布

| 段 | 覆盖率 | 原因 | 页面类型 |
|---|---|---|---|
| p0002-0008 (7段) | ~45% | 覆盖率不达标，但不重跑 | TOC 目录页 |
| demo5 对应段 4段 | ~45% | 同上 | TOC 目录页 |

## 输出包结构

```text
pdf/<package>/
  <stem>.pdf           # 源 PDF
  <stem>.md            # 合并 Markdown（pdf-merge 产物）
  review.md            # pdf-auto 人工复核清单
  manifest.json        # 元数据（seg 生成，pdf-merge 未更新）
  segments/            # MinerU 分段解析结果
  images/              # 提取的图片
  data/
    quick_lookup_draft.csv   # 结构化草案
    verification.csv         # 验证报告
    fixtures_result.md       # 固定结果摘要
    ingest_ready.csv         # 入库候选
    conflicts.csv            # 冲突报告
    review_overrides.csv     # 人工审核覆盖（可选）
    ingest_batch.jsonl       # 可交付批次 (ready only)
    ingest_manifest.json     # 批次审计清单
```

## 9000 端口生命周期

```text
mineru-api 启动（终端守护进程）
  │
  ├─ pdf-seg 检测到 9000 端口 → 复用
  │   └─ 全部段解析完成 → lsof 定位 pid → kill
  │       └─ 日志: "mineru-api 已停，请在终端输入 pdf 重启服务"
  │
  ├─ 终端守护进程 → 自动拉起 mineru-api
  │
  ├─ 下一次 pdf-seg → 检测到 → 复用 → 杀掉
  │   ...
  └─ 循环
```

总结：**用完即杀、外部守护、不驻留**。`pdf-seg` 不会保持 9000 端口存活超过一次运行；每次恢复是终端环境自动行为，不是脚本逻辑。

## 发现的管线问题

### pdf-merge 不更新 manifest

**现象**：`pdf-auto` 输出 `needs_review` 时，`manifest.json` 中 `files.markdown` 为 `null`。手动执行 `pdf-merge` 后，manifest 未被更新。后续 `pdf-extract-data` 读取 manifest 时报错：

```
TypeError: unsupported operand type(s) for /: 'PosixPath' and 'NoneType'
```

**当前 workaround**：`pdf-merge` 后手动设 `files.markdown`：

```bash
python3 -c "
import json
m = json.load(open('pdf/<package>/manifest.json'))
m['files']['markdown'] = '<stem>.md'
json.dump(m, open('pdf/<package>/manifest.json', 'w'), ensure_ascii=False, indent=2)
"
```

**建议修复方向**：
- 方案 A：让 `pdf-merge` 自动回写 manifest 的 `files.markdown` 和 `parse_status`
- 方案 B：让 `pdf-extract-data` 对 null 做 fallback——探测 `<package>/<stem>.md`

## 管线脚本一览

| 脚本 | 输入 | 输出 | 状态 |
|---|---|---|---|
| `pdf-seg` | PDF | segments/ + manifest.json | 正常 |
| `pdf-auto` | PDF + segments/ | demo.md / review.md | 正常 |
| `pdf-merge` | segments/ | 合并 demo.md + images/ | manifest 未更新 |
| `pdf-extract-data` | demo.md + manifest | quick_lookup_draft.csv + verification.csv + fixtures_result.md | 正常 |
| `pdf-prepare-ingest` | quick_lookup_draft.csv | ingest_ready.csv + conflicts.csv | 正常 |
| `pdf-export-ingest` | ingest_ready.csv + conflicts.csv | ingest_batch.jsonl + ingest_manifest.json | 正常 |
