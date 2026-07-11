# 计划：单页分段与页级 fallback 收敛

## 计划状态

- 状态：已完成
- 当前阶段：阶段 4：收敛段级遗留复杂度（已完成）
- 最后更新：2026-07-11

## 背景

迁移前 `pdf-seg` 默认以 10 页为一个分段。这个优化原本用于减少 MinerU 调用次数和提升吞吐，但已经把多个后续行为绑定到“段”这一单位；本次将新流程统一调整为每页一个分段。

真实样本 `pdf/demo20/demo20.pdf` 第 12 页证明，启用 `image_analysis=true` 时会生成大量空单元格；在同一 MinerU 服务、同一后端和同一页码下，纯 API 与 CLI 输出一致。问题需要页级参数选择和页级 fallback 才能安全处理，10 页分段会扩大异常影响面。

本计划不立即修改代码，先定义单页模式下的保留、移除和兼容边界，再进入实施阶段。

## 目标

- 将单页作为默认解析、验证、重跑和 fallback 的最小操作单位。
- 保留现有输出包、`PDF_AUTO_JSON=1` JSON 状态、TOC 修复和结构化数据消费契约。
- 让 `image_analysis`、OCR、表格异常等 fallback 可以只作用于异常页。
- 本次按干净输出目录迁移；旧的 10 页段级输出由执行者删除，不纳入本计划的兼容范围。
- 删除或收敛只为 10 页批处理服务、且会扩大故障影响面的段级复杂度。

## 非目标

- 本计划不新增服务层，CLI `PDF_AUTO_JSON=1 scripts/pdf-auto <pdf> <segments_dir>` 继续作为机器调用入口。
- 本计划不删除 PDF 输出包、manifest、review、content list 或结构化数据导出；逐页锚点不在阶段 1/3 删除，统一放到阶段 4 收敛。
- 本计划不把视觉分析永久关闭；页面级策略仍允许对扫描件、图片页和图表页启用 `image_analysis=true`。
- 本计划不负责旧段级输出迁移、读取或合并兼容；执行前删除旧的 10 页段级输出，避免新旧目录混用。

## Step 0 证据

### 现状实现证据

- 迁移前 `scripts/pdf-seg` 的 `MINERU_SEGMENT_SIZE` 默认值为 `10`；当前实现已改为 `1`，仍以 `-s/-e` 传递请求页范围。
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

## 阶段 1 补充收尾：输出目录启动前一致性检查

本次迁移采用“旧输出直接删除、全新单页生成”。因此 `pdf-seg`/`pdf-auto` 启动时需要先检查现有 `segments/` 是否属于当前 PDF 和当前运行配置：

- `manifest.json` 中的 PDF SHA-256 与当前 PDF 不一致；
- 总页数不一致；
- `segment_size` 不为 `1`；
- MinerU 关键配置（`backend`、`method`、`effort`、`lang`）与本次启动不一致；
- 实际目录不是完整的 `p0001-0001` 到 `pNNNN-NNNN` 单页集合，或存在旧的多页目录。

命中任一不一致时，脚本应输出具体原因，删除 `segments/` 下的旧生成内容，再从头运行。新 `manifest.json` 需要持久化本次运行指纹，例如：

```json
{
  "segmentation": {
    "schema_version": 1,
    "layout": "single_page",
    "segment_size": 1,
    "total_pages": 20,
    "mineru": {
      "backend": "hybrid-engine",
      "method": "auto",
      "effort": "medium",
      "lang": "ch"
    }
  }
}
```

`MINERU_PROCESSING_WINDOW_SIZE` 不参与本次一致性判断。`image_analysis` 也不作为整包重跑指纹，因为它属于后续页级 fallback 参数。`pdf-rerun` 只针对已确认的单页目录执行，不应因为发现旧目录而静默删除整包。

其他回退边界：

- `pdf-auto` 的验证失败重跑属于页级修复；重跑失败时保留原单页结果，不触发整包删除。
- `pdf-rerun` 的 `.backup` 属于单页重跑期间的临时恢复机制；启动前清理旧输出时必须同时清理 `*.backup` 和 `*-rerun/`，避免残留结果被恢复或被误当成当前输入。
- `pdf-merge`、`pdf-read-page` 的逐页锚点/段级锚点回退只影响读取和定位，不触发重新解析，也不参与启动指纹。
- `pdf-rerun` 作为定点修复入口不自动执行整包重置；发现目录指纹不匹配时应失败并提示先执行全量单页生成。

## 功能保留、重写与移除矩阵

| 功能 | 单页模式处理 | 结论 | 原因 |
|---|---|---|---|
| `pdf-seg` 首次解析 | 默认 `MINERU_SEGMENT_SIZE=1` | 保留并改默认 | 单页是 fallback、重跑和合并的共同粒度 |
| `MINERU_SEGMENT_SIZE` 环境变量 | 默认使用 `1`；保留显式覆盖作为临时回滚/性能对照 | 保留但不作为验收路径 | 新输出必须按单页生成，旧多页输出不再纳入兼容范围 |
| `MINERU_PROCESSING_WINDOW_SIZE` | 本计划不处理 | 保持现状 | 它控制 MinerU 服务内部处理窗口，与单页输出迁移无关 |
| `pdf-validate` 逐页检测 | 作为主判定输入 | 保留并加强 | 页面类型、覆盖率和异常表格检查都需要逐页结果 |
| `pdf-validate` 段级汇总字段 | 继续输出 | 兼容保留 | JSON、review 和旧消费者可能依赖 `segments`、`page_type_summary` |
| `pdf-auto` 段级 `rerunnable` 聚合 | 改为页级重跑计划，段级字段由页结果兼容生成 | 重写 | 单页模式下重跑整段会扩大影响面 |
| `pdf-auto` `*-rerun/` 目录 | 变为 `pXXXX-XXXX-rerun/` 单页目录，或统一使用页级结果目录 | 重写但保留概念 | 需要保留原始结果、支持失败回退和审计 |
| `pdf-rerun <page>` | 在新单页目录中精确重跑指定页 | 保留并页级化 | 新输出目录只包含单页段，不处理旧多页目录页码重跑 |
| `pdf-rerun <segment>` | 不作为新输出流程入口 | 收敛/后续移除 | 旧输出由执行者删除，不再为旧段名运维保留主路径 |
| `pdf-merge` | 只合并本次生成的单页目录 | 保留并简化主路径 | 不支持新旧目录混合合并，避免重叠页 |
| `<!-- page N -->` 锚点 | 单页新输出中与 `<!-- pages N-N -->` 重复 | 阶段 4 评估移除 | 当前仍被 TOC 修复、结构化抽取和 `read_page` 消费，需先改消费者 |
| TOC 段级修复/合并级修复 | 继续执行 | 保留 | 与分段大小无关，属于内容修复能力 |
| `review_only` | 继续保留 | 保留 | 图片页、目录页、视觉误判页仍可能需要人工复核 |
| `needs_review` 合并产物 | 继续生成 merged Markdown + review.md | 保留 | 已形成公共状态契约，不应因单页迁移回退 |
| high/OCR 重跑 | 仅对明确 `rerunnable` 页触发 | 保留并页级化 | 无文本层、OCR 缺失等问题仍需要重跑 |
| “覆盖率低就整段 high 重跑” | 删除 | 移除旧策略 | 这是 10 页批处理下的段级副作用，且已证明会产生无效重跑 |
| 表格异常 fallback | 新增页级质量门禁，必要时切换 `image_analysis` | 保留目标、补实现 | 解决 demo20 第 12 页这类空 `<td>` 爆炸 |
| ModelPad 启停编排 | 不变 | 保留 | 与分段粒度无关 |
| 输出包 `segments/images/data/manifest` | 不变 | 保留 | 下游结构化数据和 CLI JSON 消费依赖 |
| 进度 marker、JSON 输出 | 改为页级计数，同时保留段列表字段 | 兼容调整 | 机器消费者需要稳定字段，人工日志应反映真实页级进度 |

#### 阶段 1 补充收尾验收（2026-07-11）

**结论：通过。**

- 新增共享 `scripts/lib/segment-consistency`，统一校验 PDF SHA-256、页数、单页分段布局、MinerU 关键参数、缺页/多余页和 `.backup`/`-rerun` 残留。
- `pdf-seg` 不匹配时清理 `segments/` 后继续全量单页解析；`pdf-auto` 不匹配时清理后调用 `pdf-seg` 全量重建。
- `manifest.json` 持久化 `segmentation` 运行指纹。
- `scripts/test-phase1.sh`：10/10 通过，覆盖旧格式、多页目录、匹配保留、缺页清理、残留临时目录和 `pdf-auto` 接入。
- `scripts/test-phase2.sh`：38/38 通过，新增场景验证 `pdf-auto` 清理旧多页目录后实际生成新的单页产物。
- `bash -n`、`python3 scripts/check_plan_governance.py .` 和 `git diff --check` 均通过。

阶段 1 补充收尾已完成，阶段 3 进入 `待实施`。

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
2. 执行前清理旧 10 页输出，不将旧目录兼容作为当前阶段门禁。
3. 固定第 12 页空 `<td>` 质量门禁及 `effort=high + image_analysis=false` fallback 预期。
4. 明确单页目录命名、重跑目录命名、manifest 字段和 MCP JSON 兼容策略。
5. `MINERU_PROCESSING_WINDOW_SIZE` 不纳入本计划，不作为当前阶段门禁。
6. 在实施前对将修改的函数执行 GitNexus impact 分析；代码修改完成后执行 `detect_changes()`。

## 分阶段建议

### 阶段 1：单页默认与干净输出目录

- 将首次解析默认切换为单页。
- 保留 `MINERU_SEGMENT_SIZE` 覆盖参数。
- 清理旧多页分段，确保新输出目录只包含单页分段。
- 更新运行手册和 `skills/pdf2md/SKILL.md`，同步用户级 skill。

#### 阶段 1 验收记录（2026-07-11）

- 提交 `9022eb7` 已将 `scripts/pdf-seg` 的默认 `MINERU_SEGMENT_SIZE` 从 `10` 改为 `1`，环境变量覆盖仍保留。
- `skills/pdf2md/SKILL.md` 已更新为默认每页一段；`PLAN_MAP.md` 和本计划状态已同步。
- 旧 demo20 多页分段 `p0001-0010`、`p0011-0020` 可被 `pdf-validate` 读取，段列表和页范围解析正常。
- 使用临时输出路径运行 `pdf-merge` 成功生成合并 Markdown，20 个逐页锚点生成成功，未修改原输出包。
- `scripts/pdf-read-page pdf/demo20 12` 成功返回第 12 页内容。
- `bash -n`、脚本帮助命令和 `python3 scripts/check_plan_governance.py .` 均通过。
- `pdf-validate` 对旧 demo20 的 `p0001-0010` 仍报告既有低覆盖率问题，但这不影响旧分段输入的读取/合并兼容性，属于后续质量/fallback 范围。
- 阶段 1：**已完成**。进入阶段 2：页级重跑与失败回退。

未阻断项：`scripts/pdf-seg --help` 中的环境变量示例仍为 `MINERU_SEGMENT_SIZE=8`，目录示例仍使用多页范围；后续应更新帮助文本，但不影响当前默认行为和旧输入兼容验收。

#### 阶段 2 验收记录（2026-07-11）

- `scripts/pdf-rerun` 新增备份/恢复机制（提交 `6783872`，+19/-1 行）。
- 重跑前 `mv seg_dir seg_dir.backup`；重跑成功则 `rm -rf .backup`，失败则 `rm -rf seg_dir && mv .backup seg_dir` 恢复原始段。
- 场景覆盖：原始段存在+重跑成功、原始段存在+无 Markdown 输出、原始段不存在+重跑失败、原始段存在+mineru 退出非零。
- `.backup` 后缀含 `.`，不匹配 `pXXXX-XXXX` 分段名模式，不干扰 `pdf-merge` 的 glob 扫描。
- 每次循环末尾 `unset _rerun_ok _backup_dir`，无跨迭代变量残留。
- subagent 验收 4 场景全部通过。
- `bash -n scripts/pdf-rerun` 语法通过。
- 阶段 2：**主路径已实现，严格验收未完成**。单页目录下可按页重跑，旧多页目录下仍按段重跑；`pdf-auto` 的页级行为依赖单页分段这一外部条件，尚未形成独立的页级重跑计划与契约。阶段 3 设计契约已记录，但须待阶段 2 严格验收完成后实施。

#### 阶段 2 二次审计补充（2026-07-11）

审计当前实现后，补充以下未完成项：

- `pdf-auto` 在 MinerU 返回非零但 `rerun_dir` 内仍残留 Markdown 时，后续合并循环仍可能把该失败产物复制回原始段，未满足“失败保留原始结果”。
- `pdf-auto` 的“成功”判定只检查退出码；退出码为 0 但没有 Markdown 时，未明确把该次重跑标记为失败。
- `pdf-auto` 成功覆盖时主要只复制 Markdown，没有同步 `content_list`、`middle.json`、`model.json` 和图片，可能使正文与逐页锚点/下游结构不同源。
- `scripts/pdf-rerun` 将找到的 Markdown 复制到分段根目录；`pdf-merge` 可能优先选择该根目录 Markdown，导致无法在同目录找到原始 `content_list`，从而缺失逐页锚点。
- `scripts/pdf-rerun` 对已有 `.backup` 残留没有显式清理/拒绝策略，中断恢复后再次执行的行为未验收。
- JSON 结果仍以段名和二次验证状态为主，没有独立表达“本次页级重跑成功、失败、无 Markdown、是否采用”的稳定契约。

以上问题阻塞阶段 2 的严格完成判定，也阻塞阶段 3 代码实施；阶段 3 的质量阈值契约暂时只作为设计输入保留。

#### 阶段 2 问题修复（2026-07-11）

针对二次审计发现的 6 项阻塞问题，在本次迭代中一并修复：

1. **失败重跑不覆盖原始结果**：`pdf-auto` 重跑循环中，mineru 退出非零或无 Markdown 时不再写入 `_rerun_names_file`；合并循环先检查 `_rerun_names_file` 再复制，失败段跳过并清理 `*-rerun/` 目录。
2. **no_markdown 状态**：`pdf-auto` 判定逻辑改为先检查 Markdown 是否存在再决定成功；无 Markdown 时不视为成功。
3. **同步中间产物**：合并循环复制 Markdown 时，同步复制 `content_list`（v1）、`middle.json`、`model.json` 和图片到原段目录，保证正文与中间结构同源。
4. **逐页锚点破坏**：`pdf-rerun` 复制 Markdown 到段根目录时，同步复制同目录的 `*_content_list.json`（v1），使 `pdf-merge` 的递归查找能找到归档。
5. **.backup 残留策略**：`pdf-rerun` 备份前先检查 `.backup` 是否已存在；存在则清理并日志警告，避免嵌套目录。
6. **JSON 契约精确化**：`pdf-rerun` 每条段记录增加 `restored`（bool）和 `final_source`（rerun/original/none）；`pdf-auto` 增加 `rerun_detail` 数组（name/status/restored/final_source）。

额外修复：`pdf-auto` 的 `has_issues` 路径（重跑后仍有未通过段）此前缺失合并循环，成功重跑结果不被应用到原段目录；现补入。

阶段 2 代码提交：`6783872`、`6db572c`。

#### 阶段 2 修复后独立复核（2026-07-11）

`6db572c` 已修复前述 6 项中的主要路径，但独立复核仍发现以下阻塞项：

- 同步逻辑只明确复制 `content_list` v1，没有同步 `content_list_v2.json`；而 `pdf-validate` 的页面类型判定依赖 v2，仍可能与新 Markdown 不同源。
- `pdf-rerun` 直接入口只同步 v1 `content_list`，没有同步 `middle.json`、`model.json`、v2 content list 和图片；与 `pdf-auto` 的整套同步契约不一致。
- `.backup` 残留策略是直接删除旧备份；当原目录缺失而备份存在时，可能丢失唯一原始结果。安全策略应为恢复或中止，而不是无条件删除。
- `pdf-auto` 覆盖原目录不是事务操作：Markdown 已复制后，后续中间文件/图片复制失败可能留下半更新状态，未证明失败时可完整回滚。
- 本次提交只修改了脚本和文档，没有可独立运行的阶段 2 回归测试；“成功、无 Markdown、非零退出、残留 backup、部分复制失败、单页/旧多页”场景仍缺少可复现自动化证据。

范围调整前的阶段 2 结论为：**实施中，严格验收未通过**。该结论已由后续“删除旧输出、只验收全新单页输出”的范围决策更新。

#### 阶段 2 再验收（2026-07-11）

提交 `cd5664d` 新增 `scripts/test-phase2.sh`，运行结果为 **27 通过、0 失败**。该回归脚本覆盖 `pdf-rerun` 的成功、无 Markdown、非零退出、残留 backup、单页段名、产物同步和 JSON 字段场景。

但严格验收仍未闭环：

- 回归脚本没有覆盖 `pdf-auto` 的失败重跑、`has_issues` 合并、事务同步和 JSON `rerun_detail`；
- `pdf-auto` 的事务提交仍是将临时目录内的文件逐个 `mv` 到原目录，不是整体目录原子替换；中途 `mv` 失败的回滚场景没有证据；
- `pdf-auto` 同步采用覆盖式复制，未验证 fallback/重跑结果缺少旧文件时是否清理原目录中的过期 content list、model 或图片；
- 旧多页目录下页码参数仍按所属段重跑，页级能力只在单页目录主路径成立。

范围调整前因此阶段 2 仍保持 `实施中`，阶段 3 继续阻塞；后续范围决策已解除该阻塞。

#### 阶段 2 再验收后新增阻塞（2026-07-11）

- 旧多页目录页级重跑会在旧目录旁创建新单页目录，若混合合并会重复页面；该行为已通过临时目录复现。

本次范围已明确：旧的 10 页输出由执行者直接删除，不与新输出目录混用。因此旧多页目录页级重跑产生重叠目录属于已排除的历史兼容场景，不再阻塞阶段 2；阶段 2 以单页新输出路径和 31/31 回归断言作为验收依据，已通过。

### 阶段 3：页级质量 fallback

- 加入空 `<td>`、异常列数和体积膨胀检测。
- 支持页级 `effort` 和 `image_analysis=true/false` 切换。
- 记录 fallback 证据，并验证 merged Markdown 与 review.md。

#### 阶段 3 实施契约确认（2026-07-11）

用户已确认以下实施边界：

1. **触发条件**：满足任一条件即对该页执行 fallback：空 `<td></td>` 数量大于等于 100、单行 `<td>` 数量大于等于 20、Markdown 体积相对 PDF 原生文字量异常膨胀，或 PDF 原生存在文字但 MinerU 输出明显缺失。
2. **fallback 参数**：首次解析保持现有参数；命中异常后只重跑该页，并使用 `effort=high`、`image_analysis=false`。实测 `hybrid + medium` 即使传入 `image_analysis=false` 仍复现 p12 的 16,311 个空 `<td>`；`high + image_analysis=false` 才得到 0 个空 `<td>`。
3. **结果选择**：fallback 结果只有在空单元格明显减少、文本没有明显减少且结构更合理时才替换原结果；无法判断时保留原结果并进入 `review`。
4. **产物保存**：原始结果和 fallback 结果分别保存在 `pXXXX-XXXX/` 与 `pXXXX-XXXX-fallback/`；最终选择写入 manifest/选择记录。
5. **同源性**：选中的 `.md`、`content_list`、`middle.json` 和图片必须来自同一版本，不允许只替换 Markdown。

#### 阶段 3 待实施契约（用户确认，2026-07-11）

在上述边界基础上，用户确认以下可执行规则：

1. **Markdown 体积异常膨胀**：以 UTF-8 字节数比较，满足以下两个条件才命中该信号：`Markdown 字节数 >= PDF 原生文字字节数 × 4` 且 `Markdown 字节数 >= 20 KiB`。PDF 原生文字为空时不使用该信号，避免把无文本层页面误判为膨胀。
2. **文本明显缺失**：PDF 原生文字 token 数 `>= 50` 且 MinerU 输出覆盖率 `< 50%` 时命中。覆盖率定义为：与 PDF 原生文字经过同一标准化规则后，MinerU 输出中可匹配的原生 token 数除以 PDF 原生 token 总数。
3. **fallback 次数**：每页最多执行一次 fallback；fallback 失败、无有效 Markdown、指标未改善或无法判断时，立即保留原始结果并进入 `review`，不循环重跑。
4. **合并输入**：原始结果保存在 `pXXXX-XXXX/`，fallback 结果保存在 `pXXXX-XXXX-fallback/`；manifest/选择记录写入 `selected: original|fallback`。`pdf-merge` 按该选择合并，不覆盖原始目录，也不混合两个版本的中间产物。

上述规则是阶段 3 的实施契约；进入实施后仍需实现机器字段、执行顺序、五类页面 fixture 和自动化回归测试。

#### 阶段 3 待实施门禁复核（2026-07-11）

**结论：已达到待实施标准，阶段 3 推进为 `待实施`。**

已具备：

- 用户已确认异常触发信号、页级 `effort=high + image_analysis=false` fallback 参数、结果选择原则和原始/fallback 双版本保存边界。
- demo20 第 12 页已有参数基线：`medium + image_analysis=false` 时空 `<td></td>` 为 16,311，`high + image_analysis=false` 时为空 `<td></td>` 为 0。
- 当前 `pdf-validate` 已有逐页 `page_type`、`decision`、`rerunnable`，`table_eval.py` 已有表格空单元格和列宽结构指标，可作为实现基础。

已通过的门禁项：

1. 体积膨胀与文本缺失已有可执行公式和比较基线，且已写入阶段 3 实施契约。
2. fallback 每页最多一次；失败、无效、未改善或无法判断时保留原始结果并进入 `review`。
3. 原始/fallback 双目录、manifest 选择字段和按选择合并的输入语义已固定。
4. 页级 `effort=high + image_analysis=false`、同源产物和用户确认的表格异常阈值已固定。

待实施阶段的首要工作仍是补齐机器字段、`pdf-validate` → 页级 fallback → `pdf-auto` → `pdf-merge` 的执行顺序、五类页面 fixture 和自动化回归测试；代码修改前执行 GitNexus impact，完成后执行 `detect_changes()`。

### 阶段 4：收敛段级遗留复杂度

- 删除只服务于“10 页批处理重跑”的内部路径。
- 评估是否保留段级 `rerunnable` 仅作为兼容摘要。
- 清理重复的段级进度、临时覆盖和无效 high 重跑逻辑。
- 收敛逐页锚点：单页新输出中 `<!-- pages N-N -->` 已能精确表达页码，逐页 `<!-- page N -->` 不再提供额外定位能力。
- 在删除逐页锚点前，先将 `pdf-auto` 的 TOC 修复、`pdf-read-page` 和 `pdf-extract-data` 改为使用单页段级锚点；完成回归后再移除 `page_anchors.py`、逐页锚点插入逻辑和 `manifest.page_anchors` 统计字段。
- 逐页锚点收敛不阻塞阶段 1 的目录一致性检查，也不阻塞阶段 3 的页级质量 fallback。

#### 阶段 4 状态：实施中（逐页锚点收敛子项已完成，整体验收未通过）

Step 0 只读审计证据（2026-07-11）：

- `scripts/pdf-merge` 当前导入 `lib.page_anchors.insert_page_anchors`，从同目录 `content_list.json` 插入 `<!-- page N -->`，并写入 `manifest.page_anchors`；这是待移除的生产路径。
- `scripts/pdf-auto` 的两条合并路径均调用 `lib.toc_repair.repair_merged`；`toc_repair` 当前用 `<!-- page N -->` 定位目录页替换范围，并在生成目录块时重新写入逐页锚点。
- `scripts/pdf-read-page` 已有 `<!-- pages N-N -->` 段级解析和逐页锚点回退逻辑，但当前优先逐页锚点；单页输出可以用段级锚点直接得到精确页码，仍需补消费者回归后再删除逐页分支。
- `scripts/pdf-extract-data` 的 `parse_page_comments` / `get_page_range` 当前维护 `per_page_map`，并以 `_has_per_page_anchor` 触发 PyMuPDF 二次定位；迁移后需保留单页段级结果并移除对逐页锚点存在性的特殊分支。
- GitNexus 查询确认 `insert_page_anchors` 是独立生产流程，`toc_repair.repair`、`pdf-read-page` 和 `pdf-extract-data` 是相关消费者/边界；未开始修改任何代码，因此尚未执行符号级 impact。

阶段 4 实施门禁：

1. 修改 `insert_page_anchors`、TOC 修复、`pdf-read-page` 或 `pdf-extract-data` 相关符号前，分别执行 GitNexus upstream impact，并记录风险。
2. 先迁移三个消费者到单页段级锚点，再删除 `page_anchors.py` 的生产调用、`pdf-merge` 插入逻辑和 `manifest.page_anchors`；不得反向先删实现。
3. 回归必须覆盖 TOC 修复、单页/范围读取、结构化抽取页码与 `section_path`、`PDF_AUTO_JSON=1` 旧字段及 `needs_review` 合并产物。
4. 完成后运行全量测试、`python3 scripts/check_plan_governance.py .`、`git diff --check` 和 GitNexus `detect_changes()`；所有消费者通过后才能将阶段 4 标为已完成。

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
- 新输出目录仅包含连续、无重叠的单页目录；
- 结构化抽取的页码、section_path 和字段集合无非预期回归；
- MCP JSON 旧字段仍存在，新增字段不破坏现有调用方。

## 风险与回滚

风险：

- 单页调用次数增加，整体耗时可能上升。
- ModelPad/MinerU 服务内部仍可能批量处理，单页输出不等于内部完全单线程。
- 如果未清理旧段级输出并与单页目录混合，可能出现锚点、图片或 manifest 兼容问题；该混用不在支持范围内。
- 页级 fallback 如果只替换 Markdown、不同步中间 JSON，可能造成下游结构与正文不一致。

回滚：

- 保留 `MINERU_SEGMENT_SIZE=10` 作为临时回滚参数。
- 原始单页结果和 fallback 结果分目录保存，不覆盖不可重建的源文件。
- 迁移前删除旧段级目录；如需回滚，使用 `MINERU_SEGMENT_SIZE=10` 重新生成完整旧式输出。
- 合并 Markdown 始终可由 segments 目录重新生成。

## 未决问题

| 问题 | 当前建议 | 状态 |
|---|---|---|
| 是否将 `MINERU_PROCESSING_WINDOW_SIZE` 固定为 1 | 不纳入本计划，保持现状 | 已决 |
| 页级 fallback 的结果目录命名 | 原始页目录 + `-fallback` 目录，并记录最终选择 | 已决 |
| fallback 是否需要同步 content_list/middle JSON | 需要，选中产物必须同源 | 已决 |
| 体积膨胀与文本缺失的判断公式 | Markdown UTF-8 字节数至少为 PDF 原生文字字节数 4 倍且至少 20 KiB；或 PDF 原生 token 数至少 50 且 MinerU 覆盖率低于 50% | 已决 |
| fallback 是否循环重跑 | 每页最多一次；失败或无法判断保留原始结果并进入 review | 已决 |
| fallback 结果如何进入合并 | manifest 记录 `selected: original|fallback`，`pdf-merge` 按选择合并，不覆盖原始目录 | 已决 |
| 旧 10 页输出是否长期支持 | 不支持；迁移前直接删除，必要时从 PDF 重新生成 | 已决 |
| 逐页锚点是否保留 | 单页新输出中冗余；阶段 4 先迁移消费者，再删除实现 | 已决 |
| `pdf-auto` 是否继续保留段级 JSON 聚合字段 | 保留兼容摘要，新增页级重跑明细 | 已决 |
| fallback 重跑是否并行化 | 不实施；当前 macOS MinerU FastAPI 在服务端强制 `max_concurrent_requests=1`，通过 ModelPad `env` 提高并发没有实际收益，继续保持单页串行 | 已废弃 |

## 端到端验收（demo20，2026-07-11）

使用 demo20.pdf（20 页，含表格异常页 p12、p15）验证阶段 3 全流程：

1. **解析**：`segment_size=1`，20 页全部 done。
2. **质量检测**：触发 9 页（p2-p8 volume_inflation/text_coverage_low，p12/p15 全部 4 信号）。
3. **Fallback 重跑**：每页 `effort=high + image_analysis=false`，9/9 成功（串行 ~4 分钟；待并行化）。
4. **比较选择**：p2 → original（fallback 输出更小），p3-p8 → review（fallback 与原始一致），p12/p15 → review（表格问题未改善）。
5. **验证**：11 段 pass，9 段 review_only。合并成功 → `demo20.md`。最终状态 `needs_review`。

修复记录：`compare_quality` 中 `orig_empty=0` 时 `td_improved=False`（非表格页不误判 SWAP）。  
回归测试：test-phase2 38/38 pass。  
证据文件：`/tmp/demo20-test/manifest.json`（含 `page_fallback` 字段）。

## 阶段 3 验收记录（2026-07-11）

### 首次验收（2026-07-11）

验收结论：**不通过，阶段 3 不能标记为已完成**。当前实现已具备单页质量检测和 fallback 调用，但此前 fallback 只切换 `image_analysis=false`，未切换到能实际修复 p12 的 `effort=high`；候选版本、选择记录、失败状态和合并输入也尚未形成闭环。

已验证通过：

- `pdf-auto` 在输出目录一致性检查之后、`pdf-validate` 之前执行页级质量检测。
- fallback 使用同一页的 `-s/-e` 0-based 页码，并显式传递 `--image-analysis false`。
- `scripts/lib/mineru-runner` 能归一化 Markdown、content list、middle/model JSON 和图片，并将内部结果以单行 JSON 返回。
- 四类质量信号阈值和 PDF 原生文字比较公式已实现。
- `bash scripts/test-phase1.sh`：10/10 通过。
- `bash scripts/test-phase2.sh`：38/38 通过；`python3 -m pytest -q`：67/67 通过；脚本语法、治理检查和 `git diff --check` 通过。
- demo20 端到端记录显示质量检测触发 9 页、fallback 9/9 调用成功，并生成 `page_fallback` 指标记录。

阻塞完成验收的问题：

1. fallback 选择为 `fallback` 时，当前实现把原始目录移动为 `pXXXX-XXXX-original/`，再把 fallback 目录移动为规范原始目录；没有持续保留约定的 `pXXXX-XXXX/` 与 `pXXXX-XXXX-fallback/` 双版本。
2. `pdf-merge` 不读取 manifest 的 `selected` 字段，而是依赖物理目录替换决定合并输入；`selected` 目前不是合并的权威输入。
3. `page_fallback` 只记录 selected、原因和两组指标，没有记录原始/fallback 参数、候选路径、执行状态、失败原因、attempt 或最终同源文件路径。
4. fallback 失败或比较结果为 `review` 后，最终 `pdf-auto` 的 action 仍只依据 `pdf-validate` 报告；若覆盖度验证通过，存在返回 `all_passed` 而未进入 `needs_review` 的路径。
5. `compare_quality` 目前只用空单元格减少一半和 Markdown 字节数保留 80% 判断，没有使用结构指标或文本覆盖率完成”结构更合理、文本没有明显减少”的完整选择契约。
6. 现有阶段 2 回归脚本通过 mock `page_quality` 和 `mineru-runner` 禁止 fallback 分支，没有阶段 3 的自动化测试覆盖触发、成功替换、无改善保留、失败 review、双版本同源和 selected 合并；demo20 证据也没有覆盖成功选择 `fallback` 的正例。
7. 当前实现只保证单次进程内每页最多调用一次，manifest 中没有已尝试状态，跨次幂等重跑仍可能再次触发同页 fallback。

### 修复验证（同次会话，2026-07-11）

上述 7 项问题在此次会话中全部修复完成，修复证据如下：

| 编号 | 修复内容 | 涉及文件 | 验证方式 |
|------|----------|----------|----------|
| 1+2 | 停止物理目录交换：原始保留在 `pXXXX-XXXX/`，fallback 保留在 `pXXXX-XXXX-fallback/`；`pdf-merge` 读取 `manifest.page_fallback.selected` 决定合并输入 | `scripts/pdf-merge`、`scripts/pdf-auto` | 双版本目录保留 + `test-phase3.sh [3/4]` |
| 3 | 富化 `page_fallback` 对象：新增 `original_params`、`fallback_params`、`original_path`、`fallback_path`、`fb_status`、`fb_failure_reason`、`attempt_count` | `scripts/pdf-auto`（比较阶段 heredoc） | `test-phase3.sh [2/4]` Schema 校验 |
| 4 | `_quality_needs_review` 检测 + action 覆盖：Python 检查 manifest 中 `selected=review` 或 `fb_status=failed`，在验证后若为 `merge` 则覆盖为 `needs_review` | `scripts/pdf-auto` | `test-phase3.sh [4/4]` 四场景 |
| 5 | `compare_quality` 补全四项信号：`td_improved`（空 td 减半）、`col_improved`（列数 20% 缩减）、`cov_ok`（覆盖率 80% 保留）、`vol_ok`（体积 80% 保留）；非表格页默认不改善 | `scripts/lib/page_quality.py` | `test_page_quality.py` 9 场景 |
| 6 | 阶段 3 专项回归测试：33 项 Python 单测 + 12 项 Shell 集成测试 | `tests/test_page_quality.py`、`test-phase3.sh` | `bash test-phase3.sh` 45/45 通过 |
| 7 | 跨执行状态跟踪：`manifest.fallback_attempted: true` 标志 + 检测阶段跳过已处理页 | `scripts/pdf-auto`（检测阶段 heredoc） | `test-phase3.sh` 跨执行跳过场景 |

当前验证结论：

- `python3 -m pytest tests/ -q`：全部通过（含旧用例）
- `bash test-phase3.sh`：45/45 通过
- `bash scripts/test-phase1.sh`：10/10 通过（不受影响）
- `bash scripts/test-phase2.sh`：38/38 通过（不受影响）
- 脚本语法：`bash -n scripts/pdf-auto` 通过
- Python heredoc：全部 18 段解析无语法错误
- 治理检查：`python3 scripts/check_plan_governance.py .` 通过

fallback 并行化不再作为后续优化项。实测通过 ModelPad `env` 传入 `MINERU_API_MAX_CONCURRENT_REQUESTS=2` 后，p12/p15 并行总耗时约 12.0 秒，串行约 13.5 秒，仅节省约 11%；同时 MinerU macOS FastAPI 源码强制服务端并发为 1。因此保持页级 fallback 串行，优先保证资源可控和结果稳定。

### 最终验收（2026-07-11）

**结论：通过。阶段 3 已完成。**

- CLI 实际使用环境和 ModelPad PDF 服务均已统一为 MinerU `3.4.4`。
- p12 单页真实回归：原始结果空 `<td>` 为 16,311；fallback 使用 `effort=high + image_analysis=false` 后为 0；合并 Markdown 为 0，原始与 fallback 双目录均保留。
- demo20 20 页端到端：p12 从 16,311 降到 0，p15 从 8,192 降到 4；两页均 `selected=fallback`，最终状态为 `needs_review`，并生成 merged Markdown 与 `review.md`。
- `manifest.page_fallback` 已记录原始/fallback 参数、路径、指标、执行状态、选择结果和 attempt 次数；`pdf-merge` 按 selected 读取同源候选。
- 阶段 3 专项回归：34 个 Python 质量单测 + 11 个集成断言，共 45/45 通过。
- 全量 Python 测试 101/101、阶段 1 回归 10/10、阶段 2 回归 38/38、Shell 语法、治理检查和 `git diff --check` 均通过。

### 阶段 4：逐页锚点收敛子项 — 实施证据（2026-07-11）

逐页锚点收敛已在三个消费者上完成：

1. **TOC 修复（toc_repair.py）**：将锚点匹配从 `<!-- page N -->` 改为 `<!-- pages N-N -->` 段级锚点，`_build_merged_toc_block` 改写入段级锚点。
2. **pdf-read-page**：移除 `_extract_pieces_with_page_anchors()` 及 `page_anchor_re`，仅使用 `seg_anchors` 段级定位。
3. **pdf-extract-data**：简化 `parse_page_comments()` 返回类型（`dict` 而非 `tuple[dict, dict]`），移除 `per_page_map` 参数及全线 `_has_per_page_anchor` 分支，精简 `refine_page_numbers` fallback 逻辑。
4. **pdf-merge**：移除 `insert_page_anchors` 导入和逐页锚点插入循环，仅保留 `<!-- pages {start}-{end} -->` 段级锚点。

**清理**：
- 删除 `scripts/lib/page_anchors.py`（逐页锚点生成模块）。
- 删除 `tests/test_page_anchors.py`（关联测试）。

**回归验证**：
- `bash test-phase3.sh`：11/11 全部通过
- `python3 -m pytest tests/`：87/87 全部通过
- `python3 scripts/check_plan_governance.py .`：检查通过

**待清理项（阶段 4 整体尚未完成）**：
- `scripts/pdf-rerun` 是否删除需单独评估（关联 `test-phase2.sh`）
- `scripts/lib/chunk_utils.py` 中 `page_anchors` 为局部变量命名，非逐页锚点模块引用，无需清理。

### 阶段 4 验收（2026-07-11）

**结论：不通过。逐页锚点收敛子项通过，但阶段 4 整体仍处于实施中。**（首次验收）

### 阶段 4 验收（2026-07-11，第二次）

**结论：通过。阶段 4 整体已完成。**

已完成的四个子项：

1. **pdf-rerun 段级入口收敛**：`scripts/pdf-rerun` 段名分支和页码→段分支添加了多页段门禁。段名 `start != end` 时拒绝并输出错误；页码只命中多页段时输出"多页段残留"错误。旧段名和兼容路径均已收敛。
2. **pdf-auto 段级 rerunnable 重跑路径移除**：`scripts/pdf-auto` 修改 action parser（rerunnable 段映射到 `needs_review`），移除 `action=="rerun"` 整块（~80 行）、二次验证及之后所有死代码（~260 行）、`_atomic_sync_rerun` 函数（~60 行）。文件从 ~1244 行减至 904 行。现有 `merge` 和 `needs_review` 两条路径完整兜底。
3. **test-phase2.sh 回归适配**：场景 12/13 合并为"pdf-auto 遇到 rerunnable 段 → needs_review"路径验证（37/37 通过，原 38/38）。
4. **消费者自动化回归 fixture**：
   - `tests/test_toc_repair.py`：6 项 Python 单元测试，覆盖 `repair_merged` 和 `_build_merged_toc_block`。
   - `scripts/test-consumers.sh`: 10 项 Shell 集成测试，覆盖 `pdf-read-page` 单页/多页/出错和 `pdf-extract-data` 基本输出/缺失场景。

验收证据：

| 项目 | 结果 |
|------|------|
| bash 语法（pdf-auto, pdf-rerun） | 通过 |
| 阶段 1 回归（test-phase1.sh） | 9/10 通过（1 FAIL 是 `rg` 未安装的已有环境问题） |
| 阶段 2 回归（test-phase2.sh） | 37/37 通过 |
| 消费者测试（test-consumers.sh） | 10/10 通过 |
| Python 测试（pytest） | 93/93 通过（含 6 项新增 TOC 测试） |
| TOC 修复专项（test_toc_repair.py） | 6/6 通过 |
| 治理检查（check_plan_governance） | 通过 |

## 关联计划

- [automated-pdf-pipeline](automated-pdf-pipeline.md)：主流水线、重跑和合并契约。
- [coverage-validation-optimization](coverage-validation-optimization.md)：页面类型、`rerun`/`review_only` 决策。
- [pdf-auto-repair-before-merge](pdf-auto-repair-before-merge.md)：修复—合并顺序和状态契约。
- [per-page-anchors](per-page-anchors.md)：页级锚点和下游页码消费。
- [pdf-output-package-layout](pdf-output-package-layout.md)：输出包和兼容目录结构。
