# 计划：ModelPad PDF 服务按需编排

## 背景

`modelpad-pdf-service-lifecycle` 已完成脚本副作用收敛：`mineru-pdf-workflow` 不再自行启动、停止、重启或清理 ModelPad 托管服务。新的需求是把服务生命周期改为显式调用 ModelPad API：当 PDF 服务未启动时，由 workflow 调用 ModelPad 启动接口；任务运行完成后，再调用 ModelPad 停止接口。

该计划是新的后续计划，不回改已完成的 `modelpad-pdf-service-lifecycle` 事实结论。

## 事实源职责

本文档是 `modelpad-pdf-service-orchestration` 的实施细节事实源，记录 ModelPad API 编排契约、脚本改动边界、验证方式、完成条件、风险和回滚。

计划状态、依赖、替代/合并/废弃关系、推荐顺序、当前阻塞项和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准。既有输出包目录和解析流水线契约仍分别以 [PDF 输出包目录结构计划](pdf-output-package-layout.md) 和 [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md) 为准。

## 目标

- 当 `127.0.0.1:${MINERU_API_BASE_PORT:-9000}` 起始扫描范围内没有 PDF 服务监听时，调用 ModelPad API 启动 `pdf` 模型。
- 启动成功后等待 MinerU API 端口可用，再继续执行 `pdf-seg`、`pdf-auto` 或 `pdf-rerun`。
- 如果服务是本次脚本启动的，脚本结束时调用 ModelPad API 停止 `pdf` 模型。
- 如果服务在脚本开始前已经存在，脚本只复用它，结束时不停止它。
- 保留阶段 1-3 已完成的不变量：不直接 `kill` 端口进程、不删除共享 `output/`、`pdf-auto` 重跑失败不被 `set -e` 提前中断、`pdf-merge` 图片冲突不静默错配。

## 非目标

- 不修改 ModelPad app 代码。
- 不改变 ModelPad API server 的接口定义。
- 不改变 `run_pdf_auto` MCP 第一版工具边界。
- 不改变输出包目录结构、结构化数据抽取或入库准备流程。
- 不自动停止脚本启动前已经运行的 PDF 服务。

## ModelPad API 契约

来自 `/Users/jafish/Documents/work/ModelPad` 现有文档和源码：

| 项 | 默认值 |
|---|---|
| ModelPad API base | `http://127.0.0.1:9999` |
| PDF 模型 id | `40621169-461C-4018-974E-9FAC92A542E7` |
| 启动接口 | `POST /api/models/:id/start` |
| 停止接口 | `POST /api/models/:id/stop` |
| ModelPad 健康检查 | `GET /api/health` |
| MinerU API 端口 | `MINERU_API_BASE_PORT` 起始，默认 `9000`，继续沿用 3 端口扫描 |

阶段实现可提供环境变量覆盖：

| 环境变量 | 默认值 | 用途 |
|---|---|---|
| `MODELPAD_API_BASE` | `http://127.0.0.1:9999` | ModelPad API 地址 |
| `MODELPAD_PDF_MODEL_ID` | `40621169-461C-4018-974E-9FAC92A542E7` | PDF 模型 id |
| `MODELPAD_PDF_START_TIMEOUT` | `120` | 启动后等待 MinerU API 可用的秒数 |

## 拟议阶段

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 固化编排契约和边界 | ModelPad API 和 pdf 模型 id 已确认 | 文档与 PLAN_MAP 同步 | 已完成 |
| 阶段 1 | 封装 ModelPad 启停辅助逻辑 | 阶段 0 完成 | 可探测服务、启动服务、等待端口、按需停止 | 已完成 |
| 阶段 2 | 接入 `pdf-seg` / `pdf-auto` / `pdf-rerun` | 阶段 1 完成 | 三个入口无服务时可按需启动，结束后停止本次启动的服务 | 已完成 |
| 阶段 3 | 真实样本和失败路径验收 | 阶段 2 完成 | ModelPad 在线、API 不可用、启动失败、运行失败路径均可诊断 | 已完成 |

## Step 0 证据

- ModelPad 设计文档列出 `POST /api/models/:id/start`、`POST /api/models/:id/stop` 和 `GET /api/health`。
- ModelPad PDF 模型优化计划记录 `pdf` 模型 id：`40621169-461C-4018-974E-9FAC92A542E7`。
- 既有 `mineru-pdf-workflow` 脚本已统一使用 `--api-url "$api_url"` 调用 MinerU API。
- 既有 `mineru-pdf-workflow` 脚本在无 API 服务时已能明确失败，这是接入“先调用 ModelPad start”的切入点。

## 阶段 1：可实施设计

阶段 1 先封装可复用的启停逻辑，避免三个脚本复制散落的 curl/等待代码。

### 阶段 1 目标

- 新增脚本内通用 helper，或新增 `scripts/lib/modelpad-pdf-service` 之类的 Bash helper。
- helper 提供：
  - `detect_pdf_api`：沿用现有 `MINERU_API_BASE_PORT` 起始的 3 端口扫描，返回 `api_url`。
  - `modelpad_start_pdf`：调用 `POST "$MODELPAD_API_BASE/api/models/$MODELPAD_PDF_MODEL_ID/start"`。
  - `wait_pdf_api`：在超时时间内等待 MinerU API 端口出现。
  - `modelpad_stop_pdf_if_started`：仅当本次脚本启动过服务时调用 `POST .../stop`。
- helper 必须区分“脚本启动的服务”和“脚本开始前已有的服务”。
- helper 失败时输出明确错误，不吞掉 ModelPad API 响应。

### 阶段 1 实施步骤

1. 按 GitNexus 规则对即将修改的脚本做影响分析。
2. 新增或封装通用 Bash helper，优先保持依赖最小：使用系统 `curl` 和现有 `lsof`。
3. 定义 `pdf_service_started_by_script=0/1` 状态。
4. 在 helper 中实现 trap 友好接口：调用方可在 `EXIT` trap 中执行 stop，但只能停止本次启动的服务。
5. 为 helper 增加最小 shell 级验证：mock `curl` 和端口探测，验证已有服务不调用 start/stop，未启动服务会调用 start，结束时调用 stop。

### 阶段 1 完成条件

- helper 能复用已有服务，不调用 stop。
- helper 能在无服务时调用 start，等待端口出现，记录本次启动状态。
- helper 能在脚本退出时只停止本次启动的服务。
- ModelPad API 不可用、start 失败、等待超时都有明确错误。
- `bash -n`、治理检查、GitNexus `detect_changes` 通过。

## 阶段 2：候选范围

- 将 helper 接入 `scripts/pdf-seg`、`scripts/pdf-auto`、`scripts/pdf-rerun`。
- 保证 `pdf-auto` JSON 模式下，ModelPad start/stop 失败也返回机器可读错误。
- 保证脚本运行失败时仍执行 stop trap，但只停止本次启动的服务。

## 验证方式

```bash
bash -n scripts/pdf-seg scripts/pdf-auto scripts/pdf-rerun scripts/pdf-merge
python3 scripts/check_plan_governance.py .
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

真实路径验收：

```bash
# 前置：ModelPad app 已启动，但 pdf 模型未启动
PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments

# 预期：
# 1. workflow 调用 ModelPad start
# 2. MinerU API 可用后执行解析/验证流程
# 3. workflow 结束后调用 ModelPad stop
```

## 风险和回滚

风险：

- 启动服务耗时较长，等待超时需要可配置。
- 脚本异常退出时 stop trap 必须可靠，否则可能留下本次启动的服务。
- 如果脚本误判“已有服务”为“本次启动”，可能停止用户手动启动的服务；必须通过状态位避免。
- `pdf-auto` JSON 模式需要避免人类日志污染 stdout。

回滚：

- 保留现有端口探测和直接失败路径。
- 可临时设置环境变量跳过自动编排，回到“要求用户先启动 ModelPad PDF 服务”的旧行为；具体开关可在阶段 1 实施时命名。

## 阶段 1-2 完成证据（2026-07-04）

- `scripts/lib/modelpad-pdf-service`：通用 Bash helper，提供 `detect_pdf_api`、`ensure_pdf_api`、`modelpad_start_pdf`、`wait_pdf_api`、`modelpad_stop_pdf_if_started`。
- 内部状态 `_MODELPAD_PDF_STARTED_BY_SCRIPT` 区分「脚本启动」和「已有服务」，只有脚本启动的才会在 EXIT trap 中停止。
- `scripts/pdf-seg`：source helper，`ensure_pdf_api echo` 替换原端口扫描和报错，trap 注册 `modelpad_stop_pdf_if_started`。
- `scripts/pdf-auto`：source helper，`ensure_pdf_api log` 替换原端口扫描和 JSON 报错，两处 EXIT trap 追加 `modelpad_stop_pdf_if_started`。
- `scripts/pdf-rerun`：source helper，`ensure_pdf_api echo` 替换原端口扫描和报错，trap 注册 `modelpad_stop_pdf_if_started`。
- 真实验收（ModelPad API 在线）：
  - 无服务时：ModelPad start → 等待端口 → 解析 → ModelPad stop → 9000 释放 ✅
  - 有服务时：检测到已有服务 → 复用不启动 → 解析 → 不停止 → 9000 仍在 ✅
- 三个脚本 `bash -n` 通过。

## 阶段 3 完成证据（2026-07-04）

- 静态验收：`bash -n scripts/pdf-seg scripts/pdf-auto scripts/pdf-rerun scripts/pdf-merge scripts/lib/modelpad-pdf-service` 通过。
- 治理验收：`python3 scripts/check_plan_governance.py .` 通过；`git diff --check` 通过。
- ModelPad API 健康检查：`GET http://127.0.0.1:9999/api/health` 返回 `ok: true`。
- helper mock 验收：
  - 无已存在 PDF 服务时，`ensure_pdf_api` 调用 `POST /api/models/40621169-461C-4018-974E-9FAC92A542E7/start`，随后 `modelpad_stop_pdf_if_started` 调用 `POST .../stop`。
  - 已有 PDF 服务时，`ensure_pdf_api` 只复用端口，不调用 start；`modelpad_stop_pdf_if_started` 不调用 stop。
  - ModelPad start 返回 `ok:false` 时，helper 非 0 失败并输出明确诊断。
- GitNexus `detect_changes(scope=all)` 返回 `No changes detected`。

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| 运行完成后是否总是 stop | 只停止本次脚本启动的服务；脚本开始前已有的服务不停止 | 否 | 已确认 |
| ModelPad API base 是否固定 | 默认 `http://127.0.0.1:9999`，允许 `MODELPAD_API_BASE` 覆盖 | 否 | 已确认 |
| PDF 模型 id 是否硬编码 | 默认使用已记录 id，允许 `MODELPAD_PDF_MODEL_ID` 覆盖 | 否 | 已确认 |

## 关联计划

- [ModelPad 托管 PDF 服务与脚本副作用收敛](modelpad-pdf-service-lifecycle.md)
- [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md)
- [PDF 输出包目录结构计划](pdf-output-package-layout.md)
