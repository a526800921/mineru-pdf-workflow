# 计划：默认整页图片与页图 Manifest 交付

## 计划状态

- 状态：已完成
- 当前阶段：阶段 3（已完成）
- 最后更新：2026-07-25

本计划承载 PDF 原始整页图片的生成、校验、默认编排和输出包入口登记契约。它是当前 `pdf-output-package-layout` 完成计划的增量专项，不把整页图片重新并入 `pdf2md` 的 Markdown 质量验收链路。

## 需求探索

### 已确认事实

- 下游 App 的原文页直接展示原始 PDF 整页图片，不在设备端解析或渲染 PDF，也不以 Markdown 文字替代缺失图片。
- 每个车型必须交付 PDF 全部物理页的整页图片和同批次 JSON manifest；封面、目录、无文字页、图片页和末页均不能遗漏。
- 图片是上游标准输出包的默认产物，不再是 `<package>/images/` 占位目录或仅供 VLM 评测使用的可选 sidecar。
- 机器入口是输出包根 `manifest.json` 加上 `data/page_images/manifest.json`；人类交付入口 `downstream_delivery.md` 也必须登记页图包的实际路径、状态、版本和校验结果。
- 页图生成直接读取原始 PDF，不依赖 Markdown、MinerU 分段、TOC 修复、表格修复、VLM、结构化抽取、入库候选或 chunks。
- 页图生成不经过 `pdf2md` 阶段 0～9 的完整业务验收；它拥有独立的页数、路径、尺寸、字节数、hash 和人工抽样验收。
- 若页图生成或校验失败，不能伪装成可交付；Markdown 解析产物可以保留独立状态，但最终 `downstream_delivery.md` 必须将页图交付标记为阻塞/不可用。

### 已确认方案与实现边界

- 默认生产入口属于现有流程阶段 1：`pdf-seg` 在确认源 PDF 页数和 hash 后启动页图生成；实现上先完成页图独立校验，再进入 MinerU 分段。阶段 2 的 `pdf-auto` 只复用并校验，不重复渲染。
- 页图目录固定为 `<package>/data/page_images/`，资源固定为 `<package>/data/page_images/assets/`，页图 manifest 固定为 `<package>/data/page_images/manifest.json`。
- 默认规格冻结为 JPEG、160 DPI、quality 88；后续如要改规格，必须以独立样本报告和 manifest 版本变更为依据。
- `model_slug`、`display_name` 和 `data_version` 必须由调用方显式提供，或来自已登记的车型/批次元数据；本项目没有下游车型 Registry，禁止从 PDF 文件名静默猜测。`pdf-seg` 缺少必需元数据时仍保留解析产物，但页图状态必须为 `error`，不得标记为可交付。
- 根 manifest 的 `files.page_images` 和 `files.page_images_manifest` 是下游发现页图的机器入口；页图 manifest 的 `asset` 只允许相对 manifest 的可移植路径。
- `data/page_images/validation.json` 默认随图包发布；validator 同时将相同结果输出到机器可读 stdout。
- 阶段 1 只更新根 `manifest.json` 的页图入口和状态；`downstream_delivery.md` 继续由最终交付阶段生成/更新，但必须读取并登记页图状态，不能把 Markdown 状态当成页图状态。
- `pdf-seg` 的默认元数据注入变量固定为 `PDF_PAGE_IMAGE_MODEL_SLUG`、`PDF_PAGE_IMAGE_DISPLAY_NAME`、`PDF_PAGE_IMAGE_DATA_VERSION`；缺失时写入页图 `error` 状态并继续保留独立解析产物。

本计划依赖 `automated-pdf-pipeline` 的默认 PDF 输出编排、`pdf-output-package-layout` 的包目录契约、`pdf2md-skill-sequential-workflow` 的入口顺序和 `pdf2md-default-chunks` 的最终交付入口约定；这些计划的字段细节仍以各自事实源为准。

### 范围与非目标

范围：

- 新增全量物理页渲染器和独立页图校验器。
- 固定页图 manifest schema、稳定 `page_id`、图片规格、源 PDF hash 和版本关联。
- 将页图生成接入默认 PDF 输出包，并更新根 `manifest.json` 和 `downstream_delivery.md`。
- 建立 150 AURA 以及当前仓库可复现 fixture 的页数、清晰度、体积、幂等和映射验证。
- 更新项目级 `skills/pdf2md/SKILL.md`，再同步 `/Users/jafish/.claude/skills/pdf2md/SKILL.md`，明确默认页图产物与独立验收边界。

非目标：

- 不把页图生成改造成 Markdown 解析质量、TOC、表格、VLM、结构化抽取或入库门禁。
- 不在 App 端实现图片浏览、下载、缓存或 UI 状态。
- 不修改 SQLite schema，不从 Markdown 或 `source_ref` 推导图片路径。
- 不从低清截图、Markdown 或 MinerU 图片反向生成整页图片。
- 不批量重建历史 PDF 包；历史包只在显式重跑时补齐默认页图产物。

## 公共交付契约

### 输出目录

```text
<package>/
  manifest.json
  downstream_delivery.md
  data/
    page_images/
      manifest.json
      validation.json
      assets/
        pdf-0001.jpg
        pdf-0002.jpg
        ...
```

`validation.json` 默认作为最终发布文件；校验结果至少必须能通过机器可读 stdout 获取，并由根 `manifest.json` 和 `downstream_delivery.md` 登记摘要。

### 页图 manifest 最低字段

```json
{
  "manifest_version": "1",
  "model_slug": "<registry-model-slug>",
  "display_name": "<display-name>",
  "data_version": "<data-version>",
  "source_pdf": "<pdf-basename>",
  "source_pdf_sha256": "<sha256>",
  "page_count": 128,
  "image_format": "jpeg",
  "generation": {
    "tool": "<tool-name>",
    "tool_version": "<version>",
    "dpi": 160,
    "quality": 88,
    "generated_at": "<iso-8601>"
  },
  "pages": [
    {
      "page_id": "pdf-0001",
      "pdf_page": 1,
      "markdown_page": null,
      "source_page": null,
      "asset": "assets/pdf-0001.jpg",
      "format": "jpeg",
      "width": 1600,
      "height": 2263,
      "size_bytes": 245678,
      "sha256": "<sha256>"
    }
  ]
}
```

固定规则：

- `pdf_page` 从 1 开始，连续覆盖 `1..page_count`；程序内部可以使用 0-based 下标，但不得写入交付 manifest。
- 默认 `page_id = "pdf-" + 四位十进制 PDF 物理页码`，同一车型和同一 PDF 版本中不可重复、不可因重跑改变。
- `markdown_page`、`source_page` 无可靠映射时必须为 `null`，不得猜测。
- `asset` 必须相对于页图 manifest，禁止绝对路径、临时目录和随机 UUID。
- 每个资源的格式、宽高、字节数和 SHA-256 必须与实际文件一致。
- `source_pdf` 使用可移植的 PDF 文件名；源文件真实性由 `source_pdf_sha256` 保证。

根 `manifest.json` 至少登记：

```json
{
  "files": {
    "page_images": "data/page_images",
    "page_images_manifest": "data/page_images/manifest.json",
    "page_images_validation": "data/page_images/validation.json"
  },
  "page_images": {
    "status": "generated|not_generated|error|validated",
    "manifest_version": "1",
    "source_pdf_sha256": "<sha256>",
    "page_count": 128,
    "validated_pages": 128,
    "manifest_sha256": "<sha256>"
  }
}
```

根 manifest 的具体字段命名若与既有包字段冲突，阶段 0 必须在本计划中追加兼容方案；不得让下游通过目录遍历、PDF 文件名或 Markdown 标题猜测页图路径。

## 影响模块或文件

- `scripts/pdf-seg`
- `scripts/pdf-render-page-images`（阶段 1 新增）
- `scripts/pdf-validate-page-images`（阶段 1 新增）
- `scripts/pdf-auto`
- `skills/pdf2md/SKILL.md`
- `/Users/jafish/.claude/skills/pdf2md/SKILL.md`
- `docs/plans/automated-pdf-pipeline.md`（如默认产物入口需要同步）
- `docs/plans/pdf-output-package-layout.md`（仅在兼容说明需要补充时）
- 输出包根 `manifest.json`、`downstream_delivery.md` 和 `data/page_images/`

## 与 pdf2md 流程的边界

| 能力 | 是否属于页图默认产物门禁 | 说明 |
|---|---:|---|
| 源 PDF 存在、hash 和物理页数 | 是 | 页图的输入真实性和完整性 |
| 全量页渲染、路径、尺寸、字节数、单页 hash | 是 | 独立页图校验器负责 |
| Markdown 覆盖率 | 否 | 页图不能以 Markdown 页集合为输入 |
| TOC 修复与页码归属 | 否 | `markdown_page/source_page` 无可靠值时写 `null` |
| 表格修复、VLM、结构化抽取、入库、chunks | 否 | 不影响原始 PDF 页图生成 |
| `manual_sections.pdf_page` / `page_index.pdf_page` 映射 | 外部关联验收 | 下游适配或交付验收校验，不驱动渲染 |
| `downstream_delivery.md` 登记 | 是 | 只登记页图实际状态和入口，不复跑全文验收 |

页图失败时，根 manifest 必须保留明确的 `not_generated` 或 `error` 状态；不得用 `parse_status=all_passed` 掩盖页图不可用，也不得用 Markdown 文字作为页图交付替代。

## 阶段 0 完成回顾：默认产物与入口契约设计

### 阶段 0 准入摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 已完成 |
| Step 0 | 已确认当前只有 `<package>/images/` 占位目录和 VLM 评测用可选 `data/page_images/`，没有全量页图 manifest 生产契约；详见下方 Step 0 证据 |
| 样本矩阵 | 详见下方样本矩阵 |
| 验证方式 | 独立页图生成/校验命令、真实样本抽样、根 manifest 与交付入口反向检查 |
| 失败/回滚边界 | 页图失败标记为 `error/not_generated`，阻断最终页图交付；不回滚或删除原始 PDF、segments、Markdown 和结构化产物 |
| 当前阻塞项 | 无；150 AURA PDF、默认规格、元数据注入边界、根 manifest 兼容方案和失败策略均已确认 |
| 最新独立准入复核 | 2026-07-25：通过，阶段 1 达到 `待实施` 标准后进入实施 |

## Step 0 证据

当前仓库基线已确认：

- `scripts/pdf-seg` 只创建 `<package>/images/` 和 `<package>/data/` 占位目录，并在根 `manifest.json` 中登记 `files.images: "images"`；没有生成页级 `pages[]` 清单。当前输出包没有车型 Registry 元数据文件，因此生产入口必须显式注入页图元数据。
- `scripts/pdf-eval-vlm` 的 `VLM_KEEP_IMAGES=1` 只为检测出的 `image_or_sparse` 页保留 PNG，依赖 VLM 评测路径，不能覆盖全部物理页，也没有页图交付 manifest。
- `scripts/lib/vlm_eval.py` 已有 PyMuPDF `fitz` 单页渲染能力，可作为实现参考，但现有输出命名、格式、范围和生命周期均不满足本计划契约。
- 现有 `pdf-output-package-layout` 只把 `<package>/images/`定义为后续 V2 预留目录；本计划新增并明确 `data/page_images/` 为默认整页图产物，不改变 MinerU 提取图片的历史兼容边界。

可复现的静态基线检查：

```bash
rg -n 'mkdir -p .*images|VLM_KEEP_IMAGES|page_images|files.*images' \
  scripts/pdf-seg scripts/pdf-eval-vlm scripts/lib/vlm_eval.py
```

预期：能找到占位目录和 VLM 可选保留路径，但找不到生产级全量页图 manifest 生成/校验入口；若现状已变化，必须先更新本计划假设和 Step 0 证据。

### 样本矩阵

| 输入/基线 | 可执行命令 | 预期结果 | 失败判定 | 输出位置 |
|---|---|---|---|---|
| `pdf/demo5/demo5.pdf` 小型多页 fixture | `scripts/pdf-render-page-images --pdf pdf/demo5/demo5.pdf --model-slug demo5 --display-name 'Demo 5' --data-version test-1 --output-dir <tmp>/data/page_images --dpi 160 --quality 88` | 全部物理页生成，页 ID 从 `pdf-0001` 连续开始 | 页数不一致、缺页、路径越界或渲染失败 | 临时输出包 |
| 同一 fixture 的页图包 | `scripts/pdf-validate-page-images --pdf pdf/demo5/demo5.pdf --manifest <tmp>/data/page_images/manifest.json --validation-output <tmp>/data/page_images/validation.json` | JSON `status=passed`，`validated_pages=page_count` | 任意文件缺失、尺寸/字节数/hash 不一致 | stdout 和 `validation.json` |
| `pdf/demo20/demo20.pdf` 含图文真实样本 | 同上，使用独立临时输出目录 | 封面、目录、正文、表格/插图页和末页均覆盖 | 只生成有 Markdown 内容的页面或图像明显裁切 | 临时输出包及抽样记录 |
| 150 AURA 下游实际源 PDF | `scripts/pdf-render-page-images --pdf 'pdf/春风 150AURA/春风 150AURA.pdf' --model-slug cf150t32_32a_150_aura --display-name '150 AURA' --data-version 20260719 --output-dir <tmp>/page_images --dpi 160 --quality 88`；随后运行独立 validator | 191/191 页，`status=passed`，入口元数据和 PDF hash 一致 | manifest 与 PDF hash 不一致、页码映射缺失或体积/可读性不达标 | `/tmp/mineru-page-images-aura.wnmVjG/page_images`，22,006,946 bytes，人工抽查记录 |
| 同一 PDF 连续两次生成 | 连续执行 renderer 到两个空临时目录并比较清单 | `page_id`、资源集合、图片 hash 和尺寸稳定；时间字段变化不影响资源稳定性 | 无理由的页 ID/资源 hash 漂移或重跑叠加文件 | 两个临时输出目录和比较报告 |

### 阶段 0 工作项

1. 冻结生产入口、`model_slug/display_name/data_version` 注入边界和默认规格。
2. 冻结页图 manifest 与根 manifest 的字段、版本、状态和 hash 语义。
3. 确认 `scripts/pdf-seg` 的默认调用顺序：先确定源 PDF 页数和 hash，再启动页图生成与 MinerU 分段，最终以页图校验结果更新根 manifest；失败时写入明确错误状态。
4. 确认 `pdf-auto`、阶段 9 和 `downstream_delivery.md` 只校验/登记页图产物，不触发 Markdown 全量验收替代逻辑。
5. 建立 150 AURA 页图样本和体积/可读性报告。
6. 已完成独立准入复核，阶段 1 进入实施。

## 阶段路线图

| 阶段 | 目标 | 主要产物 | 状态 |
|---|---|---|---|
| 阶段 0 | 冻结默认产物、schema、规格、入口和独立验收门禁 | 计划契约、样本矩阵、准入复核 | 已完成 |
| 阶段 1 | 实现 renderer、validator 和原子写入/失败状态 | 两个 CLI、页图 manifest、根 manifest 登记 | 已完成 |
| 阶段 2 | 接入默认输出包并同步可消费入口 | `data/page_images/`、根 `manifest.json`、阶段 9 的 `downstream_delivery.md` 登记契约 | 已完成 |
| 阶段 3 | 真实车型验收和交付闭环 | 150 AURA 图包、校验报告、独立验收 | 已完成 |

## 验证方式

已执行的最终验证命令和结果：`scripts/pdf-validate-page-images` 对 `pdf/春风 150AURA/data/page_images/manifest.json` 返回 `status=passed`、`validated_pages=191`；`PDF_EXPORT_CHUNKS_JSON=1 scripts/pdf-export-chunks 'pdf/春风 150AURA'` 返回 `completed`、335 条；根 manifest 页图 hash、交付入口实际路径和 191 个资源已反向检查。

### 页图专用验证

- 生成命令可在干净临时目录运行，不依赖 MinerU 服务、ModelPad、Markdown 或开发机绝对路径。
- validator 校验 PDF 实际页数、`pages` 数量、页码连续性、稳定 page ID、资源路径、文件存在性、格式、宽高、字节数、单页 SHA-256 和源 PDF SHA-256。
- 生成器不得从 Markdown 页面列表决定渲染范围，必须按 PDF 物理页 `1..page_count` 遍历。
- 连续重建时资源集合、页 ID、尺寸和 hash 稳定；`generated_at` 只作为生成元数据，不参与资源身份。
- 人工抽查封面、目录、中文小字号、表格、警示框、结构图/插图和末页，保留验收记录。

### 输出入口验证

- 根 `manifest.json` 的 `files.page_images` 和 `files.page_images_manifest` 指向包内存在的相对路径。
- 根 manifest 的页图状态、页数、源 PDF hash、页图 manifest hash 与实际文件一致。
- `downstream_delivery.md` 记录实际页图入口、状态、版本、页数、大小、校验结果和失败原因；不得将未生成文件写成 0 或 `ready`。
- 下游可只读取根 manifest 和页图 manifest 发现资源，不遍历目录猜测文件名。
- `manual_sections.pdf_page` 和 `page_index.pdf_page` 的映射检查作为下游关联验收执行；映射失败不修改页图 manifest，不改用 Markdown fallback。

### 与现有回归的关系

- 页图专项不要求先通过 `pdf-validate` 覆盖率、TOC、表格、VLM 或结构化数据验收。
- 修改现有 `pdf-seg`、manifest 写入或交付入口代码前，仍须按项目规则执行 GitNexus upstream impact。
- 实现完成后须运行 GitNexus `detect_changes()`、页图专项测试、受影响的现有回归和 `plan-governance-cli check .`。

## 完成条件

- 默认 PDF 输出包自动生成完整页图，不再只创建占位目录。
- 页图 manifest schema、稳定 page ID、版本关联、图片规格和 hash 规则冻结并有可执行校验器。
- 根 `manifest.json` 能直接发现页图目录和页图 manifest；`downstream_delivery.md` 能直接说明消费入口和当前状态。
- 页图生成不依赖 pdf2md 全量业务验收，且失败时不会被 Markdown 状态掩盖。
- 至少一个真实车型样本完成全量页图、机器校验、稳定性比较、体积统计和人工抽样验收。
- 项目级 `skills/pdf2md/SKILL.md` 与 `/Users/jafish/.claude/skills/pdf2md/SKILL.md` 对默认页图产物、入口字段和独立验收边界表述一致。
- `plan-governance-cli check . --strict-readiness` 通过，且最新独立准入/验收记录写回本计划。

## 失败与回滚边界

- 任一页渲染失败、页数不一致、manifest 非法、资源缺失或 hash 不一致时，页图状态为 `error` 或 `not_generated`，不得标记为 `validated`。
- renderer 使用临时目录和原子 rename；失败时清理未完成的临时页图，不删除原始 PDF、segments、Markdown 或结构化产物。
- 若新默认页图逻辑影响既有 `pdf-seg` 主流程，可临时关闭页图子步骤并保留解析产物，但最终交付入口必须明确标记页图缺失，不得静默放行。
- 历史包不自动迁移；需要补齐时按指定 PDF 重新生成整套页图和 manifest，不能只增量猜测缺页。
- 发现 `model_slug`、`data_version`、源 PDF 或下游页码映射不一致时拒绝交付整包，修正配置或重新生成，不修改图片内容来适配错误映射。

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---:|---|
| `model_slug/display_name/data_version` 的默认来源 | 由调用方显式注入，或读取已登记的车型/批次元数据；禁止从 PDF stem 猜测 | 否 | 已确认；缺失时页图为 `error` |
| 默认 JPEG 规格 | JPEG、160 DPI、quality 88 | 否 | 已确认 |
| 根 manifest 是否保留旧 `files.images` | 保留旧字段表示 MinerU 图片目录，并新增 `files.page_images` 和 `files.page_images_manifest` | 否 | 已确认 |
| `validation.json` 是否随图包发布 | 默认保留，并与 stdout 输出同一份校验结果 | 否 | 已确认 |
| 150 AURA 源 PDF 是否可由当前仓库直接访问 | 使用 `pdf/春风 150AURA/春风 150AURA.pdf`，191 页，hash `ab5bec55765dfb89db4bca5830c0fa7f1a69f6a9602333be698fee1e2dd401ca` | 否 | 已确认 |

## 独立复核记录

| 日期 | 复核者 | 阶段 | 结论 | 证据 |
|---|---|---|---|---|
| 2026-07-25 | Codex 只读准入复核（实现前） | 阶段 0 | 通过；达到阶段 1 `待实施` 标准 | 150 AURA 191 页 PDF 及 hash；下游 manifest/交付要求；车型 Registry 字段；样本矩阵和回滚边界 |
| 2026-07-25 | Codex 只读准入复核（实现前） | 阶段 1 | 通过；阶段 1 已达到 `待实施` 标准并进入实施 | PyMuPDF 1.24.14；demo5 生成/校验、篡改失败和幂等验证；显式元数据、根 manifest 兼容和失败边界已冻结 |
| 2026-07-25 | Codex 独立验收复核（实现后） | 阶段 1 | 通过；renderer、validator、原子发布和失败状态完成 | `tests/test_page_image_manifest.py` 3/3；demo5 CLI 5/5；篡改资源失败；连续生成 hash 稳定；`git diff --check` 和全量 unittest 269/269 |
| 2026-07-25 | Codex 独立准入复核（实现前） | 阶段 2 | 通过；阶段 2 已达到 `待实施` 标准并进入实施 | 临时包 `pdf-seg` 联动：页图 5/5、分段 5/5、根 manifest 入口和 hash 一致、解析状态 `segmented`；阶段 9 继续负责 `downstream_delivery.md` |
| 2026-07-25 | Codex 独立验收复核（实现后） | 阶段 2 | 通过；默认接入、复用校验和失败隔离完成 | `pdf-auto` 复用校验通过且未重渲染；缺失 `pdf-0003.jpg` 时根状态为 `error`、validator 报告缺失资源，Markdown 和 `review.md` 仍生成；两次流程均保持原有 `needs_review` 语义 |
| 2026-07-25 | Codex 独立准入复核（实现前） | 阶段 3 | 通过；阶段 3 已达到 `待实施` 标准并进入实施 | 150 AURA 191 页正式页图包、根 manifest 同步、191/191 校验、160 DPI/quality 88、22,006,946 bytes 体积统计和人工抽样记录 |
| 2026-07-25 | Codex 独立验收复核（最终包） | 阶段 3 | 通过；150 AURA 正式页图包和阶段 9 交付入口完成，计划关闭 | `pdf/春风 150AURA/data/page_images/` 191/191 校验；根 manifest hash 一致；`data/chunks.jsonl` 335 条；`downstream_delivery.md` 已按实际状态登记为 `review_required`；包级反向引用检查通过 |

### 最新独立准入复核

| 字段 | 内容 |
|---|---|
| 日期 | 2026-07-25 |
| 阶段 | 阶段 3 |
| 结论 | 通过；阶段 3 已完成，计划关闭 |
| 证据 | 150 AURA 正式包页图 191/191 校验通过；根 manifest 状态和 hash 一致；160 DPI/quality 88；`data/chunks.jsonl` 335 条；`downstream_delivery.md` 已登记页图、Markdown、chunks 和入库门禁实际状态；包级路径和 hash 反向检查通过 |
| 复核者 | Codex 独立验收复核（最终包） |

### 历史复核：阶段 0（2026-07-25）

| 字段 | 内容 |
|---|---|
| 阶段 | 阶段 0：默认产物与入口契约设计 |
| 结论 | 通过；达到阶段 1 `待实施` 标准 |
| 证据 | 150 AURA 真实 PDF（191 页、SHA-256 已核对）；下游 manifest/交付要求；车型 Registry 中的 `model_slug`、`display_name`、`data_version`；根 manifest 兼容检查；失败/回滚边界和样本矩阵 |
| 复核者 | Codex 只读准入复核（实现前） |

### 阶段 0 完成证据（2026-07-25）

- 已确认页图属于现有 pdf2md 阶段 1 的默认输入产物分支，不经过 Markdown、TOC、表格、VLM、结构化数据或 chunks 门禁。
- 已确认页图元数据必须由调用方显式注入；本项目不维护下游 Registry，因此不会从 PDF 文件名猜测车型身份或数据版本。
- 已确认默认规格、根 manifest 向后兼容字段、`validation.json` 发布方式、`pdf-auto` 复用/校验行为和失败回滚边界。
- 已核对本地 150 AURA PDF：191 页，SHA-256 为 `ab5bec55765dfb89db4bca5830c0fa7f1a69f6a9602333be698fee1e2dd401ca`。

## 阶段 1：renderer/validator（已完成）

### 阶段 1 验收摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 已完成 |
| Step 0 | 阶段 0 基线确认无生产 renderer/validator；PyMuPDF 1.24.14 可用；现有 `pdf-seg`/`pdf-auto` 的根 manifest 写入点已定位 |
| 样本矩阵 | `demo5` renderer/validator、资源篡改失败、连续两次生成幂等、150 AURA 真实 PDF端到端 |
| 验证方式 | `bash -n`、Python fixture 测试、CLI 机器可读输出、失败状态和根 manifest 反向检查；阶段 3 再执行 150 AURA 全量验收 |
| 失败/回滚边界 | staging 目录校验通过后替换；失败清理 staging 并保留旧页图；根 manifest 标记 `error`，不删除 PDF、segments、Markdown 或结构化产物 |
| 当前阻塞项 | 无；150 AURA 端到端属于阶段 3，不阻塞 renderer/validator 阶段 |
| 最新独立准入复核 | 2026-07-25：通过，达到阶段 1 `待实施` 标准后进入实施 |

### Step 0 证据

- 阶段 0 静态基线确认当前没有生产级全量页图 renderer、页图 manifest 或独立 validator。
- 现有 PyMuPDF 可直接读取 PDF 页数并渲染 JPEG；无需新增依赖，实际版本为 1.24.14。
- `demo5` 已完成 5 页全量生成、独立校验、资源篡改失败和两次生成资源 hash 稳定性验证。

### 阶段 1 完成证据

- 已新增 `scripts/pdf-render-page-images`、`scripts/pdf-validate-page-images` 和 `scripts/lib/page_image_manifest.py`。
- 已将 `pdf-seg` 接入默认页图生成，`pdf-auto` 接入复用校验；元数据缺失和页图校验失败不会被 Markdown 状态掩盖。
- 已保留旧 `files.images`，并新增 `files.page_images`、`files.page_images_manifest`、`files.page_images_validation`。
- 150 AURA 真实样本已完成 191/191 页生成和独立校验：总 JPEG 体积 22,006,946 bytes（约 21.0 MiB），单页 34,491～206,935 bytes；抽查封面、目录、警示页、表格页、结构图页和末页，未见裁切、旋转或比例异常。
- 已完成真实包根 manifest/CLI 联动回归；150 AURA 体积、清晰度和人工抽样仍作为阶段 3 的正式验收，不以 demo5 联动替代。

## 阶段 2：默认输出包接入（已完成）

### 阶段 2 验收摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 已完成 |
| Step 0 | 已确认 `pdf-seg` 在页数/hash 后生成并校验页图，再进入 MinerU；`pdf-auto` 只复用校验，不重复渲染；阶段 9 继续生成 `downstream_delivery.md` |
| 样本矩阵 | demo5 临时 `pdf-seg` 5 页联动、缺失/篡改页图失败、历史 `files.images` 保留、150 AURA 真实页图 |
| 验证方式 | `PDF_SEG_JSON=1` 临时包联动、根 manifest 反向检查、页图 validator、现有测试和严格治理检查 |
| 失败/回滚边界 | 页图失败只将根 `page_images.status` 置为 `error`，保留 PDF、segments 和 Markdown；`pdf-auto` 不把 Markdown 当页图 fallback |
| 当前阻塞项 | 无；阶段 9 交付入口已在阶段 3 的正式包中完成登记 |
| 最新独立准入复核 | 2026-07-25：通过，达到阶段 2 `待实施` 标准后进入实施 |

### 阶段 2 实施进度

- `pdf-seg` 临时联动回归通过：命令使用 `PDF_SEG_JSON=1 MINERU_SEGMENT_SIZE=1 PDF_PAGE_IMAGE_MODEL_SLUG=demo5 PDF_PAGE_IMAGE_DISPLAY_NAME='Demo 5' PDF_PAGE_IMAGE_DATA_VERSION=test-1 scripts/pdf-seg <临时 PDF>`；输出包为 `/tmp/mineru-pdf-seg-integration.Npu7WE`。
- 临时包页图 `page_count=5`、`validated_pages=5`、5 个 page assets；5 个 MinerU 分段均完成，根 `manifest.json.page_images.status=validated`，页图 manifest hash 与根登记一致，`parse_status=segmented`。
- `pdf-auto` 复用校验通过且未重新渲染；页图缺失时根状态变为 `error`，Markdown 和 `review.md` 仍保留，原有 `needs_review` 返回语义不变。
- 临时包未生成 `downstream_delivery.md`，符合阶段边界：该入口只能在阶段 9 chunks 成功后生成或更新。

## 当前阶段：阶段 3

### 阶段准入摘要

| 字段 | 内容 |
|---|---|
| 准入状态 | 已完成 |
| Step 0 | 已确认 150 AURA 源 PDF 为 191 页、SHA-256 为 `ab5bec55765dfb89db4bca5830c0fa7f1a69f6a9602333be698fee1e2dd401ca`；页图正式临时包已完成根 manifest 同步和全量校验 |
| 样本矩阵 | 150 AURA 全量页图、封面、目录、警示页、表格页、结构图页和末页人工抽样；demo5 作为可复现联动 fixture |
| 验证方式 | `pdf-render-page-images`、`pdf-validate-page-images`、根 manifest hash/状态反向检查、体积统计和人工视觉抽样；阶段 9 继续执行 chunks 后交付入口生成 |
| 失败/回滚边界 | 任一资源缺失、hash/尺寸不一致或 PDF 页数不一致即保持 `error`；不修改原始 PDF，不用 Markdown 替代页图；正式包生成前只使用临时输出目录 |
| 当前阻塞项 | 无 |
| 最新独立准入复核 | 2026-07-25：通过；阶段 3 已完成，计划关闭 |

### 阶段 3 实施进度

- 150 AURA 页图正式样本已完成：191/191 页通过独立校验，191 个 JPEG 资源，体积 22,006,946 bytes（约 21.0 MiB），单页 34,491～206,935 bytes。
- 元数据已按确认的结构化批次写入：`model_slug=cf150t32_32a_150_aura`、`display_name=150 AURA`、`data_version=20260719`；规格为 JPEG、160 DPI、quality 88。
- 已生成临时交付包 `/tmp/mineru-page-images-aura.wnmVjG`，根 `manifest.json.page_images.status=validated`，`manifest_sha256` 与实际页图 manifest 一致，旧 `files.images` 字段保留。
- 已人工抽查封面、目录、两页警示、表格、结构图和末页，未见裁切、旋转或比例异常。
- 已完成：在用户确认的项目 demo 包 `pdf/春风 150AURA/` 内写入页图，重生成 chunks，并按实际审核/入库状态生成 `downstream_delivery.md`。

### 阶段 3 完成证据

- `scripts/pdf-validate-page-images` 对正式包返回 `passed`，191/191 页、191 个资源、源 PDF hash、尺寸、字节数和单页 hash 均一致。
- 根 `manifest.json.page_images.status=validated`，`manifest_sha256` 与 `data/page_images/manifest.json` 实际 hash 一致，旧 `files.images` 保留。
- `data/chunks.jsonl` 已重生成 335 条，最大 token 384；`downstream_delivery.md` 明确包状态为 `review_required`，未将未达门禁的候选或空入库批次写成可交付。
- `plan-governance-cli check . --strict-readiness`、`git diff --check` 和包级反向引用检查通过。

## 关联文档

- [上游手册整页图片与 JSON Manifest 交付要求](/Users/jafish/Documents/work/motorcycle-manual-app/docs/upstream-page-image-manifest-requirements.md)
- [下游 image-browser-v2 计划](/Users/jafish/Documents/work/motorcycle-manual-app/docs/plans/image-browser-v2.md)
- [PDF 输出包目录结构计划](pdf-output-package-layout.md)
- [pdf2md skill 顺序工作流计划](pdf2md-skill-sequential-workflow.md)
- [pdf2md 默认 chunks 计划](pdf2md-default-chunks.md)

## Test Coverage（测试覆盖率证据）

阶段 1 已有 renderer/validator fixture、失败路径和幂等测试，覆盖 3 个 unittest 用例；阶段 2 有真实 `pdf-seg`/`pdf-auto` 联动回归；阶段 3 正式 150 AURA 包已完成 191/191 页图校验、体积统计、人工抽样、chunks 重生成和交付入口反向检查。页图验收独立于 `pdf2md` 全量业务门禁。

```text
python3 tests/test_page_image_manifest.py                         3 passed
python3 -m unittest discover -s tests                            269 passed
scripts/pdf-validate-page-images <150 AURA package>                passed, 191/191
PDF_EXPORT_CHUNKS_JSON=1 scripts/pdf-export-chunks <150 AURA>      completed, 335 chunks
plan-governance-cli check . --strict-readiness                      passed
```
