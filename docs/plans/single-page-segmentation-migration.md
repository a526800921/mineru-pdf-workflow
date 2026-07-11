# 计划：单页分段与页级 fallback 收敛

## 计划状态

- 状态：实施中
- 当前阶段：阶段 1：单页默认与旧段级输入兼容
- 最后更新：2026-07-11

## 背景

当前 `pdf-seg` 默认以 10 页为一个分段。这个优化原本用于减少 MinerU 调用次数和提升吞吐，但已经把多个后续行为绑定到“段”这一单位：覆盖率验证按段汇总、`pdf-auto` 按段 high 重跑、`pdf-rerun` 传入单页时仍会找到并重跑所属整段、`pdf-auto` 用 `*-rerun` 结果覆盖整段 Markdown。

真实样本 `pdf/demo20/demo20.pdf` 第 12 页证明，启用 `image_analysis=true` 时会生成大量空单元格；在同一 MinerU 服务、同一后端和同一页码下，纯 API 与 CLI 输出一致。问题需要页级参数选择和页级 fallback 才能安全处理，10 页分段会扩大异常影响面。

本计划不立即修改代码，先定义单页模式下的保留、移除和兼容边界，再进入实施阶段。

## 目标

- 将单页作为默认解析、验证、重跑和 fallback 的最小操作单位。
- 保留现有输出包、`run_pdf_auto`、JSON 状态、TOC 修复和结构化数据消费契约。
- 让 `image_analysis`、OCR、表格异常等 fallback 可以只作用于异常页。
- 保证旧的段级目录仍可被读取、验证和合并，作为迁移兼容输入。
- 删除或收敛只为 10 页批处理服务、且会扩大故障影响面的段级复杂度。

## 非目标

- 本计划不改变 MCP 第一版边界，仍使用 `run_pdf_auto` 包装 `PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>`。
- 本计划不删除 PDF 输出包、manifest、review、content list、逐页锚点或结构化数据导出。
- 本计划不把视觉分析永久关闭；页面级策略仍允许对扫描件、图片页和图表页启用 `image_analysis=true`。
- 本计划不在没有兼容样本和回归验证前删除旧段级目录读取能力。

## Step 0 证据

### 现状实现证据

- `scripts/pdf-seg` 的 `MINERU_SEGMENT_SIZE` 默认值为 `10`，并以 `-s/-e` 传递整段页范围。
- `scripts/pdf-auto` 根据 `pdf-validate` 的段级 `rerunnable` 结果创建 `pXXXX-YYYY-rerun/`，重跑后再覆盖原段 Markdown。
- `scripts/pdf-rerun` 接收页码，但会先定位页码所属段；在 10 页分段下，传入单页仍重跑整个所属段。
- `scripts/pdf-merge` 当前按 `pXXXX-YYYY` 目录读取一个 Markdown 文件，不能直接把 `p0012-0012` 覆盖到 `p0011-0020` 的中间页。
- `scripts/pdf-merge` 已生成 `<!-- page N -->` 逐页锚点，为页级消费和后续页级替换提供基础。
- `scripts/pdf-validate` 已输出逐页 `page_type`、`decision`、`rerunnable`，但段级 `rerunnable` 仍是页面结果的聚合。

### 真实差异证据

对 `pdf/demo20/demo20.pdf` 第 12 页，使用 MinerU 3.4.4、`hybrid-engine`、`medium`、`auto`、`ch`：

| 调用 | `image_analysis` | 第 12 页 Markdown | 空 `<td></td>` |
|---|---:|---:|---:|
| 纯 API | `false` | 226 字节 | 0 |
| 纯 API（复刻 CLI 默认参数） | `true` | 147,058 字节 | 16,311 |
| CLI/脚本调用 | `true` | 147,058 字节 | 16,311 |

纯 API（复刻 CLI 默认参数）和 CLI 输出 SHA-1 一致，证明当前主要问题是页级参数和输出质量，而不是 API/CLI 两条解析链路不一致。

## 功能保留、重写与移除矩阵

| 功能 | 单页模式处理 | 结论 | 原因 |
|---|---|---|---|
| `pdf-seg` 首次解析 | 默认 `MINERU_SEGMENT_SIZE=1` | 保留并改默认 | 单页是 fallback、重跑和合并的共同粒度 |
| `MINERU_SEGMENT_SIZE` 环境变量 | 继续接受 `1` 以上值 | 兼容保留 | 旧批处理和性能对照仍可能需要；不再作为默认路径 |
| `MINERU_PROCESSING_WINDOW_SIZE` | 本计划不处理 | 保持现状 | 它控制 MinerU 服务内部处理窗口，与单页输出迁移无关 |
| `pdf-validate` 逐页检测 | 作为主判定输入 | 保留并加强 | 页面类型、覆盖率和异常表格检查都需要逐页结果 |
| `pdf-validate` 段级汇总字段 | 继续输出 | 兼容保留 | MCP、review 和旧消费者可能依赖 `segments`、`page_type_summary` |
| `pdf-auto` 段级 `rerunnable` 聚合 | 改为页级重跑计划，段级字段由页结果兼容生成 | 重写 | 单页模式下重跑整段会扩大影响面 |
| `pdf-auto` `*-rerun/` 目录 | 变为 `pXXXX-XXXX-rerun/` 单页目录，或统一使用页级结果目录 | 重写但保留概念 | 需要保留原始结果、支持失败回退和审计 |
| `pdf-rerun <page>` | 精确重跑指定页 | 重写 | 当前实现虽然接受页码，但会重跑所属 10 页段 |
| `pdf-rerun <segment>` | 继续支持旧段名 | 兼容保留 | 旧输出包和人工运维仍可能按段操作 |
| `pdf-merge` | 单页目录自然排序合并；旧多页目录继续可读 | 保留并简化主路径 | 单页模式不需要页内覆盖拼接；旧段级输入仍需兼容 |
| `<!-- page N -->` 锚点 | 作为页级合并和读取基础 | 提升为核心契约 | 为 `read_page`、结构化抽取和页级 fallback 提供边界 |
| TOC 段级修复/合并级修复 | 继续执行 | 保留 | 与分段大小无关，属于内容修复能力 |
| `review_only` | 继续保留 | 保留 | 图片页、目录页、视觉误判页仍可能需要人工复核 |
| `needs_review` 合并产物 | 继续生成 merged Markdown + review.md | 保留 | 已形成公共状态契约，不应因单页迁移回退 |
| high/OCR 重跑 | 仅对明确 `rerunnable` 页触发 | 保留并页级化 | 无文本层、OCR 缺失等问题仍需要重跑 |
| “覆盖率低就整段 high 重跑” | 删除 | 移除旧策略 | 这是 10 页批处理下的段级副作用，且已证明会产生无效重跑 |
| 表格异常 fallback | 新增页级质量门禁，必要时切换 `image_analysis` | 保留目标、补实现 | 解决 demo20 第 12 页这类空 `<td>` 爆炸 |
| ModelPad 启停编排 | 不变 | 保留 | 与分段粒度无关 |
| 输出包 `segments/images/data/manifest` | 不变 | 保留 | 下游结构化数据和 MCP 契约依赖 |
| 进度 marker、JSON 输出 | 改为页级计数，同时保留段列表字段 | 兼容调整 | 机器消费者需要稳定字段，人工日志应反映真实页级进度 |

## fallback 处理契约

单页模式下，fallback 的优先级固定为：

```text
原始单页结果
  → 页级质量检查
  → 选择性重跑（参数变化）
  → 重跑成功且质量更好则替换
  → 重跑失败或质量不改善则保留原始结果并进入 review
  → 按页合并
```

首批需要纳入质量检查的信号：

- 空 `<td></td>` 数量超过阈值；
- 单行单元格数量异常；
- Markdown 体积相对 PDF 文本量异常膨胀；
- 原生文本存在但 MinerU 文本严重缺失；
- `content_list` 的表格结构与页面文字/版面明显不一致。

fallback 不得只依据页面类型自动覆盖结果，必须同时记录：原始参数、fallback 参数、质量指标、选择结果和失败原因。

## 当前阶段实施前门禁

在开始代码实施前必须完成：

1. 用 demo20 固定单页模式基线：至少覆盖普通文字页、目录页、表格页、图片/稀疏页、无文本层页。
2. 固定旧 10 页输出包兼容样本，验证 `pdf-validate`、`pdf-read-page`、`pdf-merge` 和结构化抽取仍可读取。
3. 固定第 12 页空 `<td>` 质量门禁及 `image_analysis=false` fallback 预期。
4. 明确单页目录命名、重跑目录命名、manifest 字段和 MCP JSON 兼容策略。
5. `MINERU_PROCESSING_WINDOW_SIZE` 不纳入本计划，不作为当前阶段门禁。
6. 在实施前对将修改的函数执行 GitNexus impact 分析；代码修改完成后执行 `detect_changes()`。

## 分阶段建议

### 阶段 1：单页默认与旧段级输入兼容

- 将首次解析默认切换为单页。
- 保留 `MINERU_SEGMENT_SIZE` 覆盖参数。
- 让旧多页分段继续被验证和合并。
- 更新运行手册和 `skills/pdf2md/SKILL.md`，同步用户级 skill。

### 阶段 2：页级重跑与失败回退

- `pdf-rerun <page>` 精确生成单页结果。
- `pdf-auto` 按页生成重跑计划和结果。
- 重跑失败时保留原始页，不影响其他页。
- 保持旧段名输入的兼容路径。

### 阶段 3：页级质量 fallback

- 加入空 `<td>`、异常列数和体积膨胀检测。
- 支持 `image_analysis=true/false` 页级切换。
- 记录 fallback 证据，并验证 merged Markdown 与 review.md。

### 阶段 4：收敛段级遗留复杂度

- 删除只服务于“10 页批处理重跑”的内部路径。
- 评估是否保留段级 `rerunnable` 仅作为兼容摘要。
- 清理重复的段级进度、临时覆盖和无效 high 重跑逻辑。

## 验证方式

Step 0 阶段只做只读/实验验证：

```bash
python3 scripts/check_plan_governance.py .
```

实施阶段至少需要：

```bash
bash -n scripts/pdf-seg scripts/pdf-auto scripts/pdf-rerun scripts/pdf-merge
MINERU_SEGMENT_SIZE=1 PDF_SEG_JSON=1 scripts/pdf-seg <pdf>
PDF_VALIDATE_JSON=1 scripts/pdf-validate <pdf> <segments_dir>
PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>
scripts/pdf-merge <segments_dir>
```

并验证：

- 单页目录连续、无重复页或漏页；
- 原始页、fallback 页和最终合并页可追溯；
- 第 12 页空 `<td>` 数量降为 0 或进入 review；
- `needs_review` 仍同时生成 merged Markdown 和 review.md；
- 旧 10 页目录仍可读取、验证和合并；
- 结构化抽取的页码、section_path 和字段集合无非预期回归；
- MCP JSON 旧字段仍存在，新增字段不破坏现有调用方。

## 风险与回滚

风险：

- 单页调用次数增加，整体耗时可能上升。
- ModelPad/MinerU 服务内部仍可能批量处理，单页输出不等于内部完全单线程。
- 旧段级输出与单页输出混合时，可能出现锚点、图片或 manifest 兼容问题。
- 页级 fallback 如果只替换 Markdown、不同步中间 JSON，可能造成下游结构与正文不一致。

回滚：

- 保留 `MINERU_SEGMENT_SIZE=10` 作为临时回滚参数。
- 原始单页结果和 fallback 结果分目录保存，不覆盖不可重建的源文件。
- 保留旧段级目录读取路径，直到兼容样本和下游验证完成。
- 合并 Markdown 始终可由 segments 目录重新生成。

## 未决问题

| 问题 | 当前建议 | 状态 |
|---|---|---|
| 是否将 `MINERU_PROCESSING_WINDOW_SIZE` 固定为 1 | 不纳入本计划，保持现状 | 已决 |
| 页级 fallback 的结果目录命名 | 优先采用原始页目录 + 独立 fallback 元数据，不伪造旧段名 | 待设计 |
| fallback 是否需要同步 content_list/middle JSON | 默认需要，至少记录正文与中间结构是否同源 | 待设计 |
| 旧 10 页输出是否长期支持 | 迁移期兼容，待下游确认后再决定是否废弃 | 待确认 |
| `pdf-auto` 是否继续保留段级 JSON 聚合字段 | 保留兼容摘要，新增页级重跑明细 | 待设计 |

## 关联计划

- [automated-pdf-pipeline](automated-pdf-pipeline.md)：主流水线、重跑和合并契约。
- [coverage-validation-optimization](coverage-validation-optimization.md)：页面类型、`rerun`/`review_only` 决策。
- [pdf-auto-repair-before-merge](pdf-auto-repair-before-merge.md)：修复—合并顺序和状态契约。
- [per-page-anchors](per-page-anchors.md)：页级锚点和下游页码消费。
- [pdf-output-package-layout](pdf-output-package-layout.md)：输出包和兼容目录结构。
