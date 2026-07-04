# 计划：ModelPad 动态环境变量传递与临时输出自动清理

## 背景

当前 workflow 采用“按需启动、用完即停”模式：每次脚本运行通过 ModelPad API 启动 PDF 服务，处理完成后立即停止。这暴露出两个问题：

1. MinerU API 服务端将任务输出写入 `MINERU_API_OUTPUT_ROOT`，当前持久化配置指向 `/Users/jafish/Documents/models/mineru-api-output`。每次 API 调用会产生一个 UUID 目录，但服务停得太快，`MINERU_API_TASK_RETENTION_SECONDS` 的服务端自动清理很难触发，历史目录会持续堆积。
2. `MINERU_API_OUTPUT_ROOT` 写在 ModelPad `pdf.env` 中时是全局共享目录，脚本按需启动的短生命周期服务无法按运行隔离输出。

ModelPad start API 已支持在请求体中传入 `env` 覆盖。`StartModelRequest.env` 会传入进程启动逻辑，`ModelProcessManager.start(config:envOverrides:)` 会将覆盖合并到进程环境中，且优先级高于持久化配置。本计划在 workflow 侧利用该能力，不修改 ModelPad Swift 代码。

## 事实源职责

本文档是 `modelpad-dynamic-env-cleanup` 的实施细节事实源，记录动态 env 传递、临时输出目录清理、历史堆积目录处置、验证方式、完成条件、风险和回滚。

计划状态、依赖、推荐顺序、阻塞项和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准。既有 ModelPad 按需启停编排以 [ModelPad PDF 服务按需编排](modelpad-pdf-service-orchestration.md) 为前置事实源。PDF 输出包、MCP `run_pdf_auto` 和结构化数据流程不在本计划内变更。

## 目标

- 每次 workflow 自行启动 PDF 服务时，通过 ModelPad start API 动态传入 `MINERU_API_OUTPUT_ROOT`，指向本次运行专属临时目录。
- workflow 停止本次启动的 PDF 服务后，自动清理本次临时输出目录，避免服务端任务输出长期堆积。
- 复用脚本启动前已存在的 PDF 服务时，不创建临时目录、不传动态 env、不清理目录，保持现有复用行为不变。
- 保持 `pdf-seg`、`pdf-auto`、`pdf-rerun` 的调用方式不变。
- 将历史堆积目录清理作为独立人工步骤，避免与代码改动混在同一验收动作中。

## 非目标

- 不修改 ModelPad Swift 代码。
- 不改变 ModelPad start/stop API 契约，只消费现有 `env` 覆盖能力。
- 不改变 mineru CLI 的 zip 下载和输出包落盘行为。
- 不改变 MCP 第一版 `run_pdf_auto` 工具边界。
- 不清理脚本开始前已有服务正在使用的持久化输出目录。
- 不在实现阶段自动执行历史目录的破坏性清理命令。

## 范围

| 范围项 | 决策 |
|---|---|
| 代码改动范围 | 仅计划修改 `scripts/lib/modelpad-pdf-service`；`pdf-seg`、`pdf-auto`、`pdf-rerun` 继续通过现有 helper 间接受益 |
| 动态 env key | `MINERU_API_OUTPUT_ROOT` |
| 临时目录位置 | 默认 `${TMPDIR:-/tmp}/mineru-pdf-output-XXXXXXXX`，由 `mktemp -d` 创建 |
| 清理触发点 | `modelpad_stop_pdf_if_started` 停止本次启动的服务后 |
| 历史目录 | `/Users/jafish/Documents/models/mineru-api-output` 只做单独人工清理步骤 |
| 端口来源 | 通过 ModelPad 模型状态接口获取 `pdf` 模型 `status` 和 `port`；不再扫描本地 9000/9001/9002 端口推断 PDF 服务 |
| 文档同步 | 若实现改变已发布的 ModelPad PDF 服务使用说明，需同步 `skills/pdf2md/SKILL.md` 和 `/Users/jafish/.claude/skills/pdf2md/SKILL.md` |

## 关键语义

| 场景 | 行为 |
|---|---|
| 服务已运行，脚本复用 | `modelpad_start_pdf` 提前返回，不创建临时目录，不传动态 env；退出时不停止也不清理 |
| 脚本启动新服务 | 创建临时目录，start 请求体传入 `{"env":{"MINERU_API_OUTPUT_ROOT":"<temp-dir>"}}`，服务端任务输出进入该目录 |
| 脚本退出 | 仅当 `_MODELPAD_PDF_STARTED_BY_SCRIPT=1` 时调用 stop；stop 后清理本次临时目录 |
| stop API 失败 | 仍记录警告；实现阶段需明确是否清理本次临时目录，推荐先清理本次目录，因为 workflow 产物已下载到输出包 |
| 常驻服务 | 使用 ModelPad `pdf.env` 持久化的 `MINERU_API_OUTPUT_ROOT`，继续依赖服务端 retention 策略 |
| `pdf-seg` 到 `pdf-auto` 串联 | 每个入口只管理自己启动的服务和临时目录；若中间服务被停止，下一入口创建新的临时目录 |
| 端口判定 | `detect_pdf_api` 以 ModelPad `pdf` 模型状态为准，只有 `status=running` 且 `port` 为数字时才返回 `http://127.0.0.1:<port>`，避免 fanyi 等其他模型占用相邻端口时被误判为 PDF 服务 |

## 拟议阶段

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 固化现状证据和可实施边界 | 已确认 ModelPad start API 支持 `env` 覆盖 | 文档与 PLAN_MAP 同步 | 已完成 |
| 阶段 1 | 在 helper 中实现动态 env 与临时目录状态 | 阶段 0 完成，完成 GitNexus 影响分析 | `bash -n`、mock start body、已有服务不创建目录 | 已完成 |
| 阶段 2 | 真实 workflow 路径验收 | 阶段 1 完成 | 无服务路径创建并清理临时目录；已有服务路径不清理 | 已完成 |
| 阶段 3 | 历史堆积目录人工清理 | 阶段 2 真实验收通过，确认无常驻服务使用该目录 | 清理前后目录计数记录 | 已完成 |
| 阶段 4 | 治理和 skill 收尾同步 | 阶段 1-3 完成 | `check_plan_governance`、`detect_changes`、文档证据回填 | 已完成 |

## Step 0 证据

- ModelPad start API：`POST /api/models/:id/start` 接受 `{"env":{"KEY":"VALUE"}}` 请求体。
- ModelPad `StartModelRequest.env` 已存在，`ModelProcessManager.start(config:envOverrides:)` 会将 `envOverrides` 合并到进程环境，优先级高于持久化 `config.effectiveEnv()`。
- `scripts/lib/modelpad-pdf-service` 当前 `modelpad_start_pdf` 的 start 请求为裸 `POST`，未传请求体。
- `scripts/lib/modelpad-pdf-service` 当前 `modelpad_stop_pdf_if_started` 只负责停止本次脚本启动的服务，未记录或清理本次服务端输出目录。
- `scripts/pdf-seg`、`scripts/pdf-auto`、`scripts/pdf-rerun` 均通过 `modelpad-pdf-service` helper 管理 PDF 服务，因此实现可集中在 helper。
- 当前 `/Users/jafish/Documents/models/mineru-api-output` 下存在历史 UUID 子目录，属于已完成任务残留，需要在代码上线后另行清理。
- 阶段 2 实现发现端口扫描会把非 PDF 模型（如 `fanyi` 在 9001）纳入探测范围；端口获取已改为通过 ModelPad 模型状态接口读取 `pdf` 模型 `port`，以 ModelPad 作为服务身份事实源。

## 阶段 1：可实施设计

### 阶段 1 目标

- 在 `scripts/lib/modelpad-pdf-service` 增加内部状态变量，记录本次启动创建的临时输出目录。
- 在“未检测到已有服务、需要通过 ModelPad 启动服务”的分支中创建临时目录。
- 调用 ModelPad start API 时传入 JSON body：

```json
{"env":{"MINERU_API_OUTPUT_ROOT":"<本次临时输出目录>"}}
```

- 在停止本次启动的服务后清理该临时目录。
- 失败路径不能清理用户或常驻服务目录，只能处理 helper 自己创建且记录下来的临时目录。

### 阶段 1 实施步骤

1. 按 GitNexus 规则对即将修改的 `modelpad_start_pdf` 和 `modelpad_stop_pdf_if_started` 做影响分析，并向用户报告直接调用方、影响流程和风险等级。
2. 在 `_MODELPAD_PDF_STARTED_BY_SCRIPT` 附近增加 `_MODELPAD_PDF_OUTPUT_DIR=""`，只用于记录本次 helper 创建的目录。
3. 在 `modelpad_start_pdf` 中保持“已有服务直接复用”作为第一分支，确保复用路径不创建目录、不改变 env。
4. 在真正调用 start API 前执行 `mktemp -d "${TMPDIR:-/tmp}/mineru-pdf-output-XXXXXXXX"`；若创建失败，返回非零并输出明确错误。
5. 将 start 请求改为 `Content-Type: application/json`，并在 body 中传入 `MINERU_API_OUTPUT_ROOT`。
6. 如果 start API 失败或等待 MinerU API 超时，清理刚创建的临时目录并清空 `_MODELPAD_PDF_OUTPUT_DIR`，避免失败路径残留。
7. 在 `modelpad_stop_pdf_if_started` 中，在 stop API 调用完成后清理 `_MODELPAD_PDF_OUTPUT_DIR`，并将状态变量清空，保证重复调用幂等。
8. 增加或执行 helper mock 验证：已有服务不调用 start、不创建目录；无服务时 start body 包含 env；失败路径会清理本次临时目录。

### 阶段 1 完成条件

- `modelpad_start_pdf` 仅在启动新服务时创建临时目录并传入 `MINERU_API_OUTPUT_ROOT`。
- `modelpad_start_pdf` 失败路径不会留下本次创建的临时目录。
- `modelpad_stop_pdf_if_started` 仅清理 helper 自己创建的目录，且重复调用不报错。
- `bash -n scripts/lib/modelpad-pdf-service scripts/pdf-seg scripts/pdf-auto scripts/pdf-rerun` 通过。
- GitNexus `detect_changes()` 结果只包含预期 helper 符号和依赖入口影响。

### 阶段 1 完成证据

2026-07-04 完成阶段 1 代码实现：

- **文件变更**：仅 `scripts/lib/modelpad-pdf-service`（+30 行），`pdf-seg`/`pdf-auto`/`pdf-rerun` 无需改动。
- **语法检查**：`bash -n` 四个文件全部通过。
- **detect_changes**：仅检出 `docs/PLAN_MAP.md` 文档区段变更，无脚本级符号影响，风险 LOW。
- **check_plan_governance**：通过。
- **关键逻辑验证**：
  - 复用已有服务路径：第 67-71 行提前返回，不创建临时目录、不传动态 env（代码审查确认）。
  - 启动新服务路径：第 74 行 `mktemp -d` 创建临时目录，第 84-86 行 JSON body 传入 `MINERU_API_OUTPUT_ROOT`。
  - 失败路径清理：三处失败分支（ModelPad API 无响应、start 失败、等待超时）均 `rm -rf` 并清空变量。
  - 退出清理幂等：`modelpad_stop_pdf_if_started` 第 136 行双重检查后清理，第 139 行清空变量保证重复调用不报错。
- **入口不变**：`ensure_pdf_api` 和 `modelpad_stop_pdf_if_started` 签名不变，三个入口脚本无需改动。

### 阶段 0-1 复验记录（2026-07-04）

复验结论：阶段 0 和阶段 1 通过，可进入阶段 2 真实 workflow 路径验收。

阶段 0 门禁：

- Step 0 证据已记录 ModelPad start API 的 `env` 覆盖能力、helper 当前切入点、三个入口脚本依赖关系和历史堆积目录现状。
- `PLAN_MAP` 已同步该计划状态、依赖和阶段 1 完成证据链接。
- 反向引用检查未发现“草案为准”“以草案为事实源”“详见草案”等治理漂移表述。

阶段 1 静态验收：

- `bash -n scripts/lib/modelpad-pdf-service scripts/pdf-seg scripts/pdf-auto scripts/pdf-rerun` 通过。
- `python3 scripts/check_plan_governance.py .` 通过。
- `git diff --check` 通过。
- `node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow` 返回 `Changes: 2 files, 4 symbols`、`Affected processes: 0`、`Risk level: low`；但 GitNexus 只映射到 `docs/PLAN_MAP.md` 文档符号，未识别 Bash helper 变更。

阶段 1 代码核对：

- `scripts/lib/modelpad-pdf-service` 第 24-26 行新增 `_MODELPAD_PDF_OUTPUT_DIR`，仅记录 helper 自己创建的临时输出目录。
- 第 67-71 行保持“已有服务直接复用”分支，复用路径不会创建临时目录、传动态 env 或停止服务。
- 第 74-86 行在启动新服务前创建 `${TMPDIR:-/tmp}/mineru-pdf-output-XXXXXXXX`，并以 `Content-Type: application/json` 传入 `MINERU_API_OUTPUT_ROOT`。
- 第 89-109 行在 ModelPad API 无响应、start 失败、等待 MinerU API 超时三类失败路径中清理本次临时目录并清空状态变量。
- 第 120-140 行只在 `_MODELPAD_PDF_STARTED_BY_SCRIPT=1` 时停止服务，并仅清理 `_MODELPAD_PDF_OUTPUT_DIR` 指向的本次目录；清理后清空变量，重复调用保持幂等。
- `detect_pdf_api` 通过 ModelPad 模型状态接口获取 `pdf` 模型的 `status` 和 `port`，不再依赖本地端口扫描；`wait_pdf_api` 等待的是 ModelPad 报告 `pdf` 模型进入 `running` 状态。

阶段 1 blast radius：

- GitNexus `impact modelpad_start_pdf` 和 `impact modelpad_stop_pdf_if_started` 均返回 `Target not found`，说明当前索引未覆盖这两个 Bash 函数，不能作为有效影响面依据。
- `rg` 调用点补充确认：`modelpad_start_pdf` 仅由 `ensure_pdf_api` 调用；`ensure_pdf_api` 被 `scripts/pdf-seg`、`scripts/pdf-auto`、`scripts/pdf-rerun` 调用；`modelpad_stop_pdf_if_started` 注册在这三个入口脚本的 `EXIT` trap 中。
- 实际影响范围为三个 PDF workflow 入口的 ModelPad 按需启动和退出清理路径；MCP `run_pdf_auto` 仅通过 `pdf-auto` 间接受影响，入参/出参契约不变。

## 阶段 2：真实路径验收

### 阶段 2 目标

- 证明无服务路径会通过 ModelPad start env 覆盖隔离服务端输出目录。
- 证明脚本退出后本次临时目录被清理。
- 证明已有服务复用路径不创建、不传、不删任何临时目录。
- 证明 `PDF_AUTO_JSON=1` 和 MCP `run_pdf_auto` 消费 stdout JSON 的行为不受日志影响。

### 阶段 2 验证命令

```bash
bash -n scripts/lib/modelpad-pdf-service scripts/pdf-seg scripts/pdf-auto scripts/pdf-rerun
python3 scripts/check_plan_governance.py .
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

真实路径建议：

```bash
# 前置：ModelPad app/API 在线，pdf 模型未运行
scripts/pdf-seg pdf/demo5/demo5.pdf

# 前置：已有 PDF 服务正在运行
scripts/pdf-seg pdf/demo5/demo5.pdf

# JSON/MCP 等价路径
PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments
```

### 阶段 2 完成条件

- 无服务路径日志显示创建了 `${TMPDIR:-/tmp}/mineru-pdf-output-*`，服务运行期间该目录存在并产生服务端任务输出。
- 脚本结束后，该临时目录不存在。
- 已有服务路径日志显示复用服务，未创建新临时目录，脚本结束后未停止已有服务。
- `PDF_AUTO_JSON=1` stdout 仍为机器可读 JSON；人类日志仍走既有日志通道。

### 阶段 2 完成证据

2026-07-04 阶段 2 验收通过：

- **无服务路径** (pdf 已停止，fanyi 在 9001)：
  - `detect_pdf_api` 通过 ModelPad API 正确返回「未检测到」（fanyi 在 9001 不干扰）。
  - 日志输出 `本次临时输出目录: /var/.../mineru-pdf-output-4BWTbqWm`，临时目录创建成功。
  - 日志输出 `正在通过 ModelPad 启动 PDF 服务...`，start API 被调用且携带动态 env。
  - `detect_pdf_api` 等待后通过 ModelPad API 检测到 `running`，获取正确端口 9000。
  - 5 段全部处理完成。
  - 日志输出 `PDF 服务已停止` → `已清理临时输出目录: .../mineru-pdf-output-4BWTbqWm`。
  - 脚本退出后 `/tmp` 和 `$TMPDIR` 均无 `mineru-pdf-output-*` 残留。
- **已有服务路径** (pdf 预先通过 ModelPad 启动)：
  - 日志输出 `PDF 服务已在运行: http://127.0.0.1:9000（复用，不启动）`。
  - 无 `本次临时输出目录` 日志，无临时目录创建。
  - 脚本退出后服务仍保持 `running`，未被停止。
- **JSON 路径**：
  - `PDF_AUTO_JSON=1 scripts/pdf-auto` stdout 为有效 JSON（`{"status":"needs_review",...}`）。
  - 人类日志走 stderr，stdout 未被污染。

### 阶段 2 复验记录（2026-07-04）

复验结论：阶段 2 通过，可进入阶段 3 历史堆积目录人工清理门禁。

静态和治理验收：

- `bash -n scripts/lib/modelpad-pdf-service scripts/pdf-seg scripts/pdf-auto scripts/pdf-rerun` 通过。
- `python3 scripts/check_plan_governance.py .` 通过。
- `git diff --check` 通过。
- `node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow` 返回 `No changes detected`。

真实路径复验：

- 复用服务路径：验收前 `pdf` 在 `http://127.0.0.1:9000` 运行，`fanyi` 在 `http://127.0.0.1:9001` 运行；执行 `scripts/pdf-seg pdf/demo5/demo5.pdf` 后日志输出 `PDF 服务已在运行: http://127.0.0.1:9000（复用，不启动）`，未出现 `本次临时输出目录`、`正在通过 ModelPad 启动 PDF 服务` 或 `已清理临时输出目录`，执行后 `pdf` 仍为 `running`。
- JSON 路径：执行 `PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments`，stdout 可被 `python3 -m json.tool` 解析，业务状态为 `needs_review`，stderr 承载人类日志，stdout 未被污染。
- 无服务路径：先通过 ModelPad API 停止 `pdf`，确认 `pdf stopped` 且 `fanyi running`；执行 `scripts/pdf-seg pdf/demo5/demo5.pdf` 后日志输出 `本次临时输出目录: /var/folders/.../mineru-pdf-output-BzkqVV53`、`正在通过 ModelPad 启动 PDF 服务...`、`PDF 服务已就绪: http://127.0.0.1:9000`、`PDF 服务已停止`、`已清理临时输出目录: .../mineru-pdf-output-BzkqVV53`。
- 端口身份判定：验收期间 `fanyi` 持续运行在 `9001`，`pdf` 停止时不会被相邻端口误判为可用 PDF 服务；`pdf` 启动后通过 ModelPad 返回的 `port=9000` 生成 `api_url`。
- 临时目录清理：脚本退出后，在 `/tmp` 和 `$TMPDIR` 下未发现 `mineru-pdf-output-*` 残留。
- 状态恢复：无服务路径验收结束后 `pdf` 为 `stopped`，随后已按验收前状态恢复为 `running`；`fanyi` 全程保持 `running`。


## 阶段 3：历史堆积目录人工清理

### 阶段 3 进入条件

- 阶段 2 已通过，确认新运行不再向持久化共享目录追加短生命周期残留。
- 确认当前没有常驻 PDF 服务正在使用 `/Users/jafish/Documents/models/mineru-api-output`。
- 用户明确批准执行破坏性清理命令。

### 阶段 3 建议步骤

1. 记录清理前目录计数和体积：

```bash
find /Users/jafish/Documents/models/mineru-api-output -mindepth 1 -maxdepth 1 -type d | wc -l
du -sh /Users/jafish/Documents/models/mineru-api-output
```

2. 用户确认后执行清理：

```bash
rm -rf /Users/jafish/Documents/models/mineru-api-output/*
```

3. 记录清理后目录计数和体积。

### 阶段 3 完成条件

- 历史 UUID 子目录已清理，清理前后计数写回本计划。
- 常驻服务下次启动时仍可按 `pdf.env` 中的持久化 `MINERU_API_OUTPUT_ROOT` 写入该目录。

### 阶段 3 完成证据

2026-07-04 阶段 3 完成：

- **清理前**：子目录数 7、总大小 4.3M，PDF 服务已停止，无常驻服务使用该目录。
- **清理命令**：`rm -rf /Users/jafish/Documents/models/mineru-api-output/*`（用户已确认）。
- **清理后**：子目录数 0、总大小 0B。
- `pdf.env` 持久化 `MINERU_API_OUTPUT_ROOT` 路径保留，常驻服务下次启动仍可按原路径写入。

### 阶段 3 复验记录（2026-07-04）

复验结论：阶段 3 通过，历史堆积目录已清理，可进入阶段 4 治理收尾。

- `/Users/jafish/Documents/models/mineru-api-output` 当前子目录数为 0。
- `/Users/jafish/Documents/models/mineru-api-output` 当前总大小为 0B。
- ModelPad 当前状态：`pdf stopped`，`fanyi running http://127.0.0.1:9001`。
- 未执行额外清理命令；本次仅核对阶段 3 已完成后的目录和服务状态。

## 阶段 4：治理和说明同步

### 阶段 4 目标

- 将阶段 1-3 的实现和验收证据回填到本文档。
- 同步 `docs/PLAN_MAP.md` 的状态、阶段和证据链接。
- 如果实现后的用户可见行为改变了 PDF 服务编排说明，同步项目级 `skills/pdf2md/SKILL.md`，再覆盖 Claude Code 用户级 skill。

### 阶段 4 完成条件

- `python3 scripts/check_plan_governance.py .` 通过。
- `git diff --check` 通过。
- `node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow` 已执行并记录结果。
- 本计划状态更新为 `已完成`，PLAN_MAP 证据链接指向阶段完成证据。

### 阶段 4 完成证据（2026-07-04）

2026-07-04 完成治理和说明同步收尾：

- 本计划已回填阶段 0-3 的实现、复验和清理证据，阶段状态均为 `已完成`。
- `docs/PLAN_MAP.md` 已同步 `modelpad-dynamic-env-cleanup` 状态为 `已完成`，证据链接指向本节。
- 项目级 `skills/pdf2md/SKILL.md` 已更新 ModelPad PDF 服务说明：端口来源以 ModelPad `pdf` 模型状态接口为准，不再扫描相邻本地端口。
- Claude Code 用户级 skill `/Users/jafish/.claude/skills/pdf2md/SKILL.md` 已由项目级 skill 覆盖同步。
- `python3 scripts/check_plan_governance.py .` 通过。
- `git diff --check` 通过。
- `node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow` 已执行，风险等级为 LOW，未发现受影响执行流程。

## 验证方式

| 验证项 | 命令或观察点 | 预期 |
|---|---|---|
| Shell 语法 | `bash -n scripts/lib/modelpad-pdf-service scripts/pdf-seg scripts/pdf-auto scripts/pdf-rerun` | 无语法错误 |
| 治理检查 | `python3 scripts/check_plan_governance.py .` | 通过 |
| GitNexus 变更检查 | `node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow` | 只影响预期 helper 和入口流程 |
| 无服务真实路径 | `scripts/pdf-seg pdf/demo5/demo5.pdf` | 创建临时目录、传 env、结束后清理 |
| 已有服务真实路径 | `scripts/pdf-seg pdf/demo5/demo5.pdf` | 复用服务，不创建也不清理临时目录 |
| JSON 路径 | `PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments` | stdout 保持 JSON 可读 |

## 风险和回滚

| 风险 | 影响 | 缓解 | 回滚 |
|---|---|---|---|
| `mktemp -d` 失败 | PDF 服务无法按需启动 | 返回非零并输出明确错误；不调用 start | 恢复裸 start 请求，临时要求依赖持久化 `pdf.env` |
| JSON body 拼接转义错误 | ModelPad start 失败或 env 未生效 | 使用 `python3` 或可靠 JSON 生成方式，避免手写复杂转义 | 回退到无 body start |
| start 成功但等待 API 超时 | 可能留下服务或临时目录 | stop 本次启动服务，并清理本次临时目录 | 恢复已有按需启停逻辑 |
| stop API 失败但目录被清理 | 服务可能仍在运行且输出目录消失 | 当前脚本用完即停且 workflow 产物已下载；若真实验收发现风险，改为 stop 成功后才清理 | 临时保留目录，交由人工清理 |
| 误清理非本次目录 | 可能删除用户服务输出 | 只清理 `_MODELPAD_PDF_OUTPUT_DIR` 记录的 `mktemp` 目录，并清空状态 | 移除自动清理，只记录待清理路径 |
| 历史目录清理误删 | 丢失仍需保留的服务端残留 | 阶段 3 必须用户确认，清理前记录目录计数和服务状态 | 不执行阶段 3，保留历史目录 |

## 回滚方案

- 代码回滚：撤销 `scripts/lib/modelpad-pdf-service` 中动态 env、临时目录创建和清理逻辑，恢复裸 `POST /start`。
- 运行回滚：保留 ModelPad `pdf.env` 中的 `MINERU_API_OUTPUT_ROOT`，让常驻服务继续写入持久化目录。
- 数据回滚：自动清理只针对本次临时目录，清理后不承诺恢复服务端中间输出；workflow 正式产物仍以 PDF 输出包为准。

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| stop API 失败时是否仍清理本次临时目录 | 保持阶段 1 实现：记录 stop 警告后仍只清理本次 helper 创建的临时目录；阶段 2 真实路径未暴露问题 | 否 | 已确认 |
| JSON body 生成方式 | 当前路径仅传入 `mktemp` 生成的本地目录，Bash JSON body 已通过阶段 2 真实启动验收；如后续支持任意 env 值再改为结构化 JSON 生成 | 否 | 已确认 |
| 历史目录是否立即清理 | 已作为阶段 3 单独动作完成，清理后目录数 0、大小 0B | 否 | 已完成 |
| 是否需要同步 `skills/pdf2md/SKILL.md` | 已同步项目级 `skills/pdf2md/SKILL.md`，并覆盖 Claude Code 用户级 skill | 否 | 已完成 |

## 关联计划

- [ModelPad PDF 服务按需编排](modelpad-pdf-service-orchestration.md)
- [ModelPad 托管 PDF 服务与脚本副作用收敛](modelpad-pdf-service-lifecycle.md)
- [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md)
- [PDF 输出包目录结构计划](pdf-output-package-layout.md)
