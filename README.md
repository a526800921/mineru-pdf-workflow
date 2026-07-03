# MinerU PDF Workflow

本项目用于把长 PDF 通过 MinerU 解析成 Markdown，并围绕“解析、验证、重跑、再验证、人工兜底”建立可重复的工作流。

## 目标

- 支持长 PDF 分段解析，降低 Mac 上 PyTorch/MPS 长任务内存累计问题。
- 自动验证 MinerU 输出和原 PDF 文本层的覆盖率，筛出可疑页段。
- 对可疑页段支持重跑更高精度配置。
- 生成最终合并 Markdown，保留人工兜底入口。
- 预留 MCP 接入 Claude Code 的工具边界。

## 脚本

### ModelPad PDF 服务

`pdf-seg`、`pdf-auto`、`pdf-rerun` 依赖 ModelPad 托管的 PDF 服务。脚本会先探测 `MINERU_API_BASE_PORT`（默认 `9000`）起始的 3 个端口：

- 如果 PDF 服务已在运行，脚本只复用服务，结束时不停止它。
- 如果 PDF 服务未运行，脚本会通过 ModelPad API 启动 `pdf` 模型，等待 MinerU API 就绪，运行完成后只停止本次脚本启动的服务。
- ModelPad app/API 必须在线；默认 API 为 `http://127.0.0.1:9786`。

可选环境变量：

```bash
MODELPAD_API_BASE=http://127.0.0.1:9786
MODELPAD_PDF_MODEL_ID=40621169-461C-4018-974E-9FAC92A542E7
MODELPAD_PDF_START_TIMEOUT=120
MINERU_API_BASE_PORT=9000
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
cd /Users/jafish/Documents/work/mineru-pdf-workflow

# 1. 确保 ModelPad app 已启动；PDF 服务由脚本按需 start/stop
# 2. 把 PDF 放入目标车型目录，分段解析
scripts/pdf-seg pdf/春风\ 150AURA/春风\ 150AURA.pdf
# 输出: pdf/春风 150AURA/segments/

# 3. 验证覆盖率
scripts/pdf-validate \
  pdf/春风\ 150AURA/春风\ 150AURA.pdf \
  pdf/春风\ 150AURA/segments

# 4. 合并分段 Markdown
scripts/pdf-merge pdf/春风\ 150AURA/segments
# 输出: pdf/春风 150AURA/春风 150AURA.md

# 或一步到位（自动验证→重跑→合并→人工兜底）
scripts/pdf-auto pdf/春风\ 150AURA/春风\ 150AURA.pdf pdf/春风\ 150AURA/segments

# 5. 生成结构化数据草案
scripts/pdf-extract-data pdf/春风\ 150AURA
# 输出: pdf/春风 150AURA/data/
```

如果验证发现可疑分段，先针对该分段重跑高精度，再重新验证和合并。

## 文档

- [计划索引](docs/PLAN_MAP.md)
- [自动化流水线计划](docs/plans/automated-pdf-pipeline.md)
- [MCP 接入设计](mcp/README.md)
