# MinerU PDF Workflow

本项目用于把长 PDF 通过 MinerU 解析成 Markdown，并围绕“解析、验证、重跑、再验证、人工兜底”建立可重复的工作流。

## 目标

- 支持长 PDF 分段解析，降低 Mac 上 PyTorch/MPS 长任务内存累计问题。
- 自动验证 MinerU 输出和原 PDF 文本层的覆盖率，筛出可疑页段。
- 对可疑页段支持重跑更高精度配置。
- 生成最终合并 Markdown，保留人工兜底入口。
- 以 CLI 为唯一运行入口，支持人类执行和机器可读 JSON 输出。

## 脚本

### ModelPad PDF 服务

`pdf-seg`、`pdf-auto`、`pdf-rerun` 依赖 ModelPad 托管的 PDF 服务。脚本通过 ModelPad API 查询 `pdf` 模型状态，只有 `status=running` 且返回数字 `port` 时才使用：

- 如果 PDF 服务已在运行，脚本只复用服务，结束时不停止它。
- 如果 PDF 服务未运行，脚本会通过 ModelPad API 启动 `pdf` 模型，等待 MinerU API 就绪，运行完成后只停止本次脚本启动的服务。
- ModelPad app/API 必须在线；默认 API 为 `http://127.0.0.1:9999`。

可选环境变量：

```bash
MODELPAD_API_BASE=http://127.0.0.1:9999
MODELPAD_PDF_MODEL_ID=40621169-461C-4018-974E-9FAC92A542E7
MODELPAD_PDF_START_TIMEOUT=120
```

```text
scripts/pdf
```

单次解析一个 PDF，输出到 PDF 同级目录的 `<文件名>-mineru-output/`。

```text
scripts/pdf-seg
```

分段解析一个 PDF，默认每 1 页一段，输出到 `<PDF所在目录>/segments/`。
分段完成后自动生成 `manifest.json` 和 `images/`、`data/` 占位目录。

```text
scripts/pdf-validate
```

对比分段 Markdown 和原 PDF 文本层，输出每段覆盖率，并标出可疑分段。

```text
scripts/pdf-merge
```

按 `p0000-0019` 这类分段目录顺序合并 Markdown，默认输出到 `<输出包名>.md`。

```text
scripts/pdf-extract-data
```

从输出包的 Markdown、`manifest.json` 和 `content_list_v2.json` 生成 `data/` 下的结构化草案：`quick_lookup_draft.csv`、`verification.csv`、`fixtures_result.md`。该步骤只生成可审核草案，不写入数据库。

## 推荐流程

```bash
# PDF 可放在任意路径，所有产物（segments/md/review/data）默认输出到 PDF 所在目录
# 确保 ModelPad app 已启动；PDF 服务由脚本按需 start/stop

# 1. 分段解析
scripts/pdf-seg /path/to/春风\ 150AURA.pdf
# 输出: /path/to/segments/

# 2. 验证覆盖率
scripts/pdf-validate \
  /path/to/春风\ 150AURA.pdf \
  /path/to/segments

# 3. 合并分段 Markdown
scripts/pdf-merge /path/to/segments
# 输出: /path/to/春风 150AURA.md

# 或一步到位（自动验证→重跑→合并→人工兜底）
scripts/pdf-auto /path/to/春风\ 150AURA.pdf /path/to/segments

# 4. 生成结构化数据草案
scripts/pdf-extract-data /path/to
# 输出: /path/to/data/
```

## 文档

- [计划索引](docs/PLAN_MAP.md)
- [自动化流水线计划](docs/plans/automated-pdf-pipeline.md)
- [CLI-only 工作流迁移计划](docs/plans/cli-only-migration.md)
- [ADR 0002：CLI-only 工作流，移除 MCP Server](docs/adr/0002-cli-only-workflow.md)
- [Claude Code pdf2md skill 源文件](skills/pdf2md/SKILL.md)
