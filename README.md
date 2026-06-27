# MinerU PDF Workflow

本项目用于把长 PDF 通过 MinerU 解析成 Markdown，并围绕“解析、验证、重跑、再验证、人工兜底”建立可重复的工作流。

## 目标

- 支持长 PDF 分段解析，降低 Mac 上 PyTorch/MPS 长任务内存累计问题。
- 自动验证 MinerU 输出和原 PDF 文本层的覆盖率，筛出可疑页段。
- 对可疑页段支持重跑更高精度配置。
- 生成最终合并 Markdown，保留人工兜底入口。
- 预留 MCP 接入 Claude Code 的工具边界。

## 脚本

```text
scripts/pdf
```

单次解析一个 PDF，输出到 PDF 同级目录的 `<文件名>-mineru-output/`。

```text
scripts/pdf-seg
```

分段解析一个 PDF，默认每 20 页一段，输出到 `<文件名>-mineru-segments/`。

```text
scripts/pdf-validate
```

对比分段 Markdown 和原 PDF 文本层，输出每段覆盖率，并标出可疑分段。

```text
scripts/pdf-merge
```

按 `p0000-0019` 这类分段目录顺序合并 Markdown。

## 推荐流程

```bash
cd /Users/jafish/Documents/work/mineru-pdf-workflow

scripts/pdf-seg /path/to/manual.pdf

scripts/pdf-validate \
  /path/to/manual.pdf \
  /path/to/manual-mineru-segments

scripts/pdf-merge /path/to/manual-mineru-segments
```

如果验证发现可疑分段，先针对该分段重跑高精度，再重新验证和合并。

## 文档

- [计划索引](docs/PLAN_MAP.md)
- [自动化流水线计划](docs/plans/automated-pdf-pipeline.md)
- [MCP 接入设计](docs/adr/0001-cli-first-mcp-ready.md)

