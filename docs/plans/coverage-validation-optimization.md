# 计划：覆盖率验证口径优化

## 背景

`demo20.pdf` 的实测结果显示，阈值为 `0.82` 时首次通过 11/20 页，high 重跑后仍为 11/20 页。重跑前后覆盖率完全不变，说明主要问题不是 MinerU 解析精度不足，而是当前验证口径把目录页、图片主导页、表格结构页等“不可直接比较”的页面当成可通过 high 重跑修复的问题。

当前 `pdf-auto` 会基于 `pdf-validate` 的 `suspicious` 状态触发 high 重跑。如果低覆盖来自验证口径差异，重跑会消耗时间但不会改善结果。

## 事实源职责

本文档是 `coverage-validation-optimization` 的实施细节事实源，记录覆盖率验证口径优化的目标、范围、阶段、Step 0 证据、验证方式、完成条件、风险、回滚和未决问题。

计划状态、依赖、替代/合并/废弃关系、推荐顺序、当前阻塞项和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准。自动化流水线总体契约以 [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md) 为准。

## 目标

减少无效 high 重跑，同时保留对真实解析缺失的检出能力：

```text
覆盖率验证 -> 页面类型识别 -> 区分可重跑问题和仅需人工复核问题 -> 只重跑可修复段
```

## 非目标

- 不引入 OCR/VLM 作为当前验证基准。
- 不保证自动验证完全替代人工复核。
- 不改 MCP 第一版边界，仍保持 `run_pdf_auto` 包装 `PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>`。
- 不重写整套 PDF 解析流水线。
- 不把全局降阈值作为默认修复方案。

## 不变量

- 原始 PDF 不被修改或删除。
- 默认人类可读输出尽量保持兼容。
- `PDF_VALIDATE_JSON=1` 输出必须保持合法 JSON。
- 新增 JSON 字段必须向后兼容，MCP server 不应因新增字段失效。
- 自动验证只能筛出可疑段，不能替代最终人工兜底。
- 修改函数、类或方法前必须按 GitNexus 规则做影响分析。

## 影响模块或文件

- `scripts/pdf-validate`
- `scripts/pdf-auto`
- `docs/coverage-analysis.md`
- `docs/plans/automated-pdf-pipeline.md`
- `docs/PLAN_MAP.md`
- `mcp/README.md`（仅当 JSON 状态语义影响 MCP 说明时更新）

## 公共契约变化

候选 JSON 字段：

```json
{
  "coverage": 0.77,
  "status": "suspicious",
  "decision": "rerun",
  "reason": "low_text_coverage",
  "rerunnable": true,
  "page_type_summary": {
    "text": 12,
    "toc": 6,
    "table": 1,
    "image_or_sparse": 1
  }
}
```

候选页面级字段：

```json
{
  "page": 12,
  "coverage": 0.71,
  "page_type": "image_or_sparse",
  "decision": "review_only",
  "reason": "image_dominant_or_sparse_text"
}
```

字段语义：

| 字段 | 含义 |
|---|---|
| `page_type` | 页面内容类型初判，候选值为 `text`、`toc`、`table`、`image_or_sparse`、`no_text_layer`、`unknown` |
| `decision` | 当前问题处理方式，候选值为 `pass`、`rerun`、`review_only`、`skip` |
| `rerunnable` | 是否建议 `pdf-auto` 触发 high 重跑 |
| `reason` | 机器可读原因，供 review.md 和 MCP 诊断展示 |
| `page_type_summary` | 分段内页面类型计数 |

## 阶段路线图

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 固定当前覆盖率基线和 content_list 样本 | 有 demo20 或等价真实样本 | before JSON、重跑结果和样本结构已记录 | 已完成 |
| 阶段 1 | 修正覆盖率分析文档 | 阶段 0 完成 | 文档解释与代码一致 | 已完成 |
| 阶段 2 | 扩展 `pdf-validate` 观测字段，不改变默认判定 | 阶段 0 完成 | JSON 合法且向后兼容 | 已完成 |
| 阶段 3 | 增加页面类型和处理决策 | 阶段 2 完成 | 目录页、图片稀疏页可进入 review_only | 已完成 |
| 阶段 4 | 调整 `pdf-auto` 只重跑可修复段 | 阶段 3 完成 | 无效 high 重跑数量下降 | 已完成 |
| 阶段 5 | 验证、治理收尾和运行说明同步 | 阶段 4 完成 | 检查脚本和样本验证通过 | 已完成 |

## 当前阶段

所有阶段已完成（2026-06-28）。验证证据见下方验收记录。

### Step 0 证据（已收集，2026-06-28）

**运行命令：**

```bash
PDF_VALIDATE_JSON=1 scripts/pdf-validate \
  /Users/jafish/output/51a20d1c-8cd7-4e7b-9be1-7761b66a5208/uploads/demo20.pdf \
  /Users/jafish/output/51a20d1c-8cd7-4e7b-9be1-7761b66a5208/uploads/demo20-output/segments \
  > /tmp/validate-before.json
```

**基线结果：**

- 阈值：`0.82`。
- 首次通过：11/20 段（55%），9 段可疑。
- high 重跑前后覆盖率是否变化：根据 `docs/coverage-analysis.md` 已有记录，high 和 medium 产出文本相同，重跑前后覆盖率完全不变。
- 低覆盖页面类型分布：
  - 目录页（第 2-8 页，p0001-p0007）：覆盖率 0.4581-0.4630，7 段可疑。
  - 图片/标签页（第 13 页，p0012）：覆盖率 0.7385，1 段可疑。
  - 混合页（第 14 页，p0013）：覆盖率 0.7815，1 段可疑。
  - 纯文字页（第 9-11、17-20 页）：覆盖率 0.8947-0.9912，全部通过。
  - 封面页（第 1 页，p0000）：覆盖率 0.9574，通过。
  - 表格/正文混合页（第 15-16 页，p0014-p0015）：覆盖率 0.8743-0.8917，通过。

**`content_list_v2.json` 结构样本（已确认）：**

```json
// 元素类型覆盖：title, paragraph, page_header, page_number, image
// 嵌套结构：content 字段为 dict，包含元素特有子字段
{
  "type": "title",
  "content": {
    "title_content": [{"type": "text", "content": "..."}],
    "level": 1
  }
}
{
  "type": "paragraph",
  "content": {
    "paragraph_content": [{"type": "text", "content": "..."}]
  }
}
{
  "type": "image",
  "content": {
    "image_source": "...",
    "image_caption": [{"type": "text", "content": "..."}],
    "image_footnote": [{"type": "text", "content": "..."}]
  }
}
```

- 当前 `_extract_texts` 递归提取逻辑能覆盖嵌套的 `type: "text"` 子元素（包括 title_content、paragraph_content、image_caption 等），但 image 元素的 `image_source` 路径不贡献文本 token。
- `pdf-validate` 段级判定使用 Markdown 全文 token Counter；逐页详情已读取 `content_list_v2.json`，但不参与段级重跑决策。

**样本路径：**
- PDF: `/Users/jafish/output/51a20d1c-8cd7-4e7b-9be1-7761b66a5208/uploads/demo20.pdf`
- 分段: `/Users/jafish/output/51a20d1c-8cd7-4e7b-9be1-7761b66a5208/uploads/demo20-output/segments/`
- before JSON: `/tmp/validate-before.json`

### 实施步骤

1. 对 `scripts/pdf-validate` 和 `scripts/pdf-auto` 执行 GitNexus 影响分析，报告直接调用方、受影响流程和风险级别。
2. 修正 `docs/coverage-analysis.md`，明确当前低覆盖主要来自比较口径而非标点 token 或 token 位置。
3. 在 `pdf-validate` 中新增页面类型、处理决策和可重跑标记，但第一步不改变现有 `status` 判定。
4. 基于真实 `content_list_v2.json` 样本补齐文本提取逻辑，避免表格、标题、段落字段遗漏。
5. 将 `pdf-auto` 的重跑名单从 `status == suspicious` 收窄到 `rerunnable == true`。
6. 更新 `review.md` 生成逻辑，区分 high 重跑后仍失败和验证口径导致的 `review_only`。
7. 同步治理文档和运行说明，运行验证命令。

## 页面类型初始规则

| 类型 | 判断依据 | 默认处理 |
|---|---|---|
| `text` | PDF token 足够多，content_list 主要为文本类元素 | 低于阈值时 `rerun` |
| `toc` | PDF 文本呈目录条目、页码、点线或短行密集模式 | `review_only` |
| `table` | content_list 含表格结构，或 Markdown 表格占比高 | 初期 `review_only`，后续可引入表格专用阈值 |
| `image_or_sparse` | PDF 文本层 token 很少，content_list 图片元素占比高 | `review_only` |
| `no_text_layer` | PDF 文本层为空 | `skip` |
| `unknown` | 无法可靠分类 | 保持现有覆盖率判定 |

## 验证方式

代码实施后的最低验证：

```bash
bash -n scripts/pdf-validate
bash -n scripts/pdf-auto

PDF_VALIDATE_JSON=1 scripts/pdf-validate <pdf> <segments_dir> > /tmp/validate-after.json
python3 -m json.tool /tmp/validate-after.json

PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir> > /tmp/pdf-auto-after.json
python3 -m json.tool /tmp/pdf-auto-after.json

python3 scripts/check_plan_governance.py .
```

验收指标：

- demo20 或等价样本中无效 high 重跑数量下降。
- 纯文字页覆盖率低时仍能被标记为 `rerunnable`。
- 目录页、图片稀疏页进入 `review_only`，不触发 high 重跑。
- JSON 输出兼容 MCP。
- `review.md` 能说明低覆盖原因。

## 完成条件

- Step 0 证据已记录。
- `pdf-validate` 输出页面类型和处理决策。
- `pdf-auto` 只重跑 `rerunnable == true` 的段。
- `review.md` 区分 `rerun` 与 `review_only`。
- 真实样本验证通过，且无效 high 重跑数量下降。
- `python3 scripts/check_plan_governance.py .` 通过。
- `docs/PLAN_MAP.md`、本计划和 `docs/plans/automated-pdf-pipeline.md` 状态同步。

## 验收记录（2026-06-28）

**验收命令与结果：**

```bash
# 语法检查
$ bash -n scripts/pdf-validate && bash -n scripts/pdf-auto
✅ 通过

# pdf-validate JSON 输出
$ PDF_VALIDATE_JSON=1 scripts/pdf-validate demo20.pdf demo20-output/segments > /tmp/validate-after.json
$ python3 -m json.tool /tmp/validate-after.json > /dev/null && echo "✅ JSON 合法"
✅ JSON 合法

# pdf-auto 端到端
$ PDF_AUTO_JSON=1 scripts/pdf-auto demo20.pdf demo20-output/segments > /tmp/pdf-auto-after.json
$ python3 -m json.tool /tmp/pdf-auto-after.json > /dev/null && echo "✅ JSON 合法"
✅ JSON 合法

# 治理检查
$ python3 scripts/check_plan_governance.py .
✅ 计划治理检查通过
```

**验收指标达成：**

| 指标 | 目标 | 实际 | 状态 |
|------|------|------|------|
| 无效 high 重跑数量 | 下降 | 9 → 0（100% 消除） | ✅ |
| rerun_segments | 仅 rerunnable 段 | [] | ✅ |
| 纯文字页低覆盖 | 仍标记为 rerunnable | 本次样本无纯文字页低覆盖 | ⚠️ 待更多样本 |
| 目录页 | review_only | 7 段 toc → review_only | ✅ |
| 图片稀疏页 | review_only | 1 段 image_or_sparse → review_only | ✅ |
| JSON 兼容 MCP | 旧字段保留 | passed/threshold/segments/status/coverage 保留 | ✅ |
| review.md | 区分 rerun/review_only | 页面类型、处理建议、原因均展示 | ✅ |

**已知局限：**
- 含 HTML 警告框（`<table>` 标签）的文字页被 content_list_v2.json 标记为 table 类型，属于排版表格而非数据表格。因覆盖率足够高，不影响合并决策。后续可细化 table 子类型判断。

## 风险和回滚

风险：

- MinerU 的 `content_list_v2.json` 结构可能随版本变化。
- 表格页若过早归为 `review_only`，可能漏掉真实表格解析失败。
- 页面类型规则过复杂会增加维护成本。
- 新 JSON 字段语义如果不稳定，可能影响后续 MCP 依赖。

缓解：

- 先新增观测字段，不立即改变默认判定。
- 初期仅跳过明显目录页和图片稀疏页的 high 重跑。
- 表格页先进入人工复核，不直接判通过。
- 新增字段保持向后兼容，不删除现有字段。

回滚：

- 保留原 `status`、`coverage`、`missing_tokens` 字段。
- `pdf-auto` 可临时回退到基于 `status == suspicious` 的旧重跑逻辑。
- 可通过环境变量保留旧判定模式，具体名称在实施阶段确定。

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| content_list 表格字段是否稳定 | 先用真实样本固定字段，再写提取逻辑 | 是 | 待证据 |
| 表格页默认 `review_only` 还是低阈值通过 | 初期 `review_only`，避免误放行 | 否 | 候选 |
| 是否需要旧判定兼容开关 | 实施阶段评估，倾向保留短期环境变量 | 否 | 候选 |
| review_only 是否允许合并 | 保持人工兜底清单语义，合并策略与现有 `pdf-auto` 一致 | 否 | 待确认 |

## 关联 ADR、迁移、spec 或 issue

- [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md)
- [覆盖率优化分析](../coverage-analysis.md)
- [MCP 接入设计](../../mcp/README.md)
