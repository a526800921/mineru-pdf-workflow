# 计划：ModelPad 托管 PDF 服务与脚本副作用收敛

## 背景

当前 PDF 服务将由 `/Users/jafish/Documents/work/ModelPad` app 启动和管理。`mineru-pdf-workflow` 仓库中的脚本应作为调用方，只复用已存在的 PDF 服务，不再承担服务启动、重启、关闭或共享运行目录清理职责。

这个计划从 [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md) 中拆出，作为下一轮独立计划推进；不作为阶段 9。

## 事实源职责

本文档是 `modelpad-pdf-service-lifecycle` 的实施细节事实源，记录服务生命周期边界、脚本副作用收敛范围、Step 0 证据、验证方式、完成条件、风险和回滚。

计划状态、依赖、替代/合并/废弃关系、推荐顺序、当前阻塞项和证据索引以 [PLAN_MAP](../PLAN_MAP.md) 为准。自动化流水线总体契约以 [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md) 为准。

## 目标

- 将 PDF 服务生命周期边界收敛到 ModelPad app：`/Users/jafish/Documents/work/ModelPad` 负责服务启动、停止和长期存活。
- 移除本仓库脚本中的额外启动、重启、关闭服务行为，避免脚本和 app 争抢进程生命周期。
- 保留脚本对已有服务的端口探测和复用能力。
- 服务不可用时，脚本应明确失败，不做隐式进程管理，也不走 MinerU 默认本地启动或降级路径。
- 修复 `pdf-auto` 重跑失败路径在 `set -e` 下可能提前退出的问题。
- 优化 `pdf-merge` 图片收集逻辑，避免同名不同内容图片被静默跳过。

## 非目标

- 不在本仓库实现 ModelPad app 的服务启动逻辑。
- 不改变 `run_pdf_auto` 第一版 MCP 工具边界。
- 不把脚本改成长期守护进程。
- 不重做 MinerU 解析策略、覆盖率口径或输出包目录结构。

## 范围

- `scripts/pdf-seg`：不再在完成后重启或关闭 `mineru-api`，也不清理由服务进程拥有的运行态产物；只处理当前输出包产物。
- `scripts/pdf-auto`：重跑失败必须进入兜底分支，保留原始结果并生成可诊断输出。
- `scripts/pdf-rerun`：不应清理或影响 ModelPad 管理的服务进程和共享运行目录。
- `scripts/pdf-merge`：图片收集增加冲突检测策略，至少能识别同名不同内容。
- 文档和运行手册：明确“先启动 ModelPad app，再执行脚本”的操作顺序。

## Step 0 证据

- 现状脚本仍包含服务生命周期副作用：`pdf-seg` 完成后可能停止 `mineru-api` 并清理项目 `output/`；`pdf-rerun` 会清理项目 `output/`；`pdf-auto` 退出 trap 也会清理项目 `output/`。
- 已记录风险：`pdf-auto` 重跑分支可能因 `set -e` 在 `mineru` 非 0 时提前退出。
- 已记录风险：`pdf-merge` 图片同名不同内容时可能静默保留第一张。
- 新运行约束：PDF 服务由 `/Users/jafish/Documents/work/ModelPad` app 启动，本仓库脚本只作为调用方。

## 拟议阶段

| 阶段 | 目标 | 进入条件 | 验证方向 | 状态 |
|---|---|---|---|---|
| 阶段 0 | 固化服务生命周期边界和现状证据 | ModelPad 托管服务约束明确 | 文档和 PLAN_MAP 同步 | 已完成 |
| 阶段 1 | 移除脚本服务管理副作用 | 阶段 0 完成 | 脚本不启动/重启/关闭服务，不清理共享运行目录 | 待实施 |
| 阶段 2 | 修复自动重跑失败兜底 | 阶段 1 完成 | 模拟 `mineru` 非 0 后仍生成诊断或 review | 候选 |
| 阶段 3 | 图片冲突检测和运行手册同步 | 阶段 2 完成 | 同名不同内容图片不静默错配，运行手册可复现 | 候选 |

## 阶段 1：可实施设计

阶段 1 只收敛脚本服务生命周期副作用，不处理 `pdf-auto` 重跑失败兜底和 `pdf-merge` 图片冲突；后两项分别留给阶段 2、阶段 3。

### 阶段 1 目标

- `scripts/pdf-seg` 不再停止 `mineru-api`，不再提示用户手工重启服务。
- `scripts/pdf-seg` 不再删除项目根目录 `output/`。
- `scripts/pdf-auto` 的退出清理只删除自身创建的临时文件，不再删除项目根目录 `output/`。
- `scripts/pdf-rerun` 不再删除项目根目录 `output/`。
- 保持现有 API 端口发现方式：从 `MINERU_API_BASE_PORT`（默认 `9000`）开始扫描 3 个端口，发现服务后通过 `--api-url` 复用。
- 完全依赖 ModelPad 托管服务运行；无 API 服务时必须明确报错退出，不允许走 MinerU 默认本地启动或降级路径。

### 阶段 1 非目标

- 不修改 ModelPad app。
- 不修改 `scripts/pdf` 单次解析入口。
- 不改变输出包目录、manifest 字段、合并 Markdown 命名。
- 不调整重跑策略、覆盖率阈值或 `review_only` 判定。
- 不实现图片冲突检测。

### 阶段 1 现状证据

| 文件 | 现状 | 阶段 1 处理 |
|---|---|---|
| `scripts/pdf-seg` | 行 217 起存在 `MINERU_API_RESTART` 分支，会 `kill` 监听端口的进程，并删除项目根目录 `output/` | 删除整段服务停止和项目 `output/` 清理逻辑；`MINERU_API_RESTART` 不再作为脚本契约 |
| `scripts/pdf-auto` | 行 238、928 的 `trap` 删除临时 JSON 文件后还会删除项目根目录 `output/` | trap 只删除 `mktemp` 文件和 `_rerun_names_file` |
| `scripts/pdf-rerun` | 行 163 起删除项目根目录 `output/` | 删除项目 `output/` 清理逻辑 |
| `scripts/pdf-seg` / `pdf-auto` / `pdf-rerun` | 都会探测 `MINERU_API_BASE_PORT` 起始的 3 个端口并复用服务；无服务时部分路径会让 MinerU 走默认行为 | 保留端口探测；无服务时明确报错退出，不再允许默认本地启动或降级路径 |

### 阶段 1 实施步骤

1. 对将要修改的脚本按 GitNexus 规则做影响分析；这些脚本以文件级 CLI 为主，若无法解析到具体符号，则记录文件级影响面。
2. 修改 `scripts/pdf-seg`：移除尾部 `MINERU_API_RESTART` 分支，包括 `kill`、等待端口释放、提示“mineru-api 已停”和项目 `output/` 清理。
3. 修改 `scripts/pdf-seg`：端口扫描后如果 `api_url` 为空，输出“请先启动 ModelPad PDF 服务”一类明确错误并退出；执行 `mineru` 时始终传入 `--api-url "$api_url"`。
4. 修改 `scripts/pdf-auto`：把两处 `trap` 改成只清理 `validate_tmp`、`validate2_tmp` 和 `_rerun_names_file`，不触碰项目根目录 `output/`；端口扫描后如果 `api_url` 为空，明确报错并按脚本现有 JSON/人类输出模式返回失败。
5. 修改 `scripts/pdf-rerun`：移除“清理 mineru-api 临时产物”段落，不删除项目根目录 `output/`；端口扫描后如果 `api_url` 为空，明确报错退出；执行 `mineru` 时始终传入 `--api-url "$api_url"`。
6. 更新帮助文本或运行手册中与服务生命周期相关的描述：脚本完全依赖 ModelPad 托管服务，不负责启动、停止或重启服务。
7. 运行阶段 1 验证命令，并把结果写回本计划的阶段 1 完成证据。

### 阶段 1 验证方式

```bash
bash -n scripts/pdf-seg scripts/pdf-auto scripts/pdf-rerun
rg -n "MINERU_API_RESTART|mineru-api 已停|kill \"\\$_api_pid\"|rm -rf \"\\$\\(dirname \"\\$_d\"\\)/output\"|rm -rf \"\\$_project_root/output\"" scripts/pdf-seg scripts/pdf-auto scripts/pdf-rerun
rg -n "ModelPad|--api-url|未检测到.*API|未检测到.*服务" scripts/pdf-seg scripts/pdf-auto scripts/pdf-rerun
python3 scripts/check_plan_governance.py .
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

有 ModelPad 服务可用时补充真实路径验证：

```bash
# 前置：ModelPad app 已启动 PDF 服务
MINERU_SEGMENT_SIZE=5 scripts/pdf-seg pdf/demo5/demo5.pdf
PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments
```

### 阶段 1 完成条件

- `scripts/pdf-seg` 不再出现 `MINERU_API_RESTART`、`kill "$_api_pid"` 或“mineru-api 已停”提示。
- `scripts/pdf-seg`、`scripts/pdf-auto`、`scripts/pdf-rerun` 不再删除项目根目录 `output/`。
- 三个脚本仍能通过 `bash -n`。
- API 端口探测逻辑保留；未探测到服务时明确失败，不再隐式执行无 `--api-url` 的 MinerU 调用。
- 所有实际解析或重跑的 MinerU 调用都使用 ModelPad 服务 URL。
- 输出包结构不变：`manifest.json`、`segments/`、`images/`、`data/` 仍由既有流程生成或复用。
- 治理检查通过，`detect_changes` 结果被记录。

## 验证方式

```bash
bash -n scripts/pdf-seg scripts/pdf-auto scripts/pdf-rerun scripts/pdf-merge
python3 scripts/check_plan_governance.py .
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

阶段实现后补充真实服务路径验证：

```bash
# 前置：ModelPad app 已启动 PDF 服务
MINERU_SEGMENT_SIZE=5 scripts/pdf-seg pdf/demo5/demo5.pdf
PDF_AUTO_JSON=1 scripts/pdf-auto pdf/demo5/demo5.pdf pdf/demo5/segments
```

## 完成条件

- 脚本内不再启动、重启或停止 PDF 服务进程。
- 脚本内不再清理 ModelPad 服务可能复用的共享运行目录；只清理本次输出包内的确定性临时产物。
- ModelPad app 已启动服务时，`pdf-seg`、`pdf-auto`、`pdf-rerun` 能复用该服务。
- 服务不可用时，脚本输出明确诊断并退出，不隐式拉起、关闭服务，也不走 MinerU 默认本地启动或降级路径。
- `pdf-auto` 的 `mineru` 重跑失败路径可继续进入二次验证或人工兜底输出。
- `pdf-merge` 对同名不同内容图片给出确定行为：失败、重命名或记录冲突，不静默错配。
- 计划治理检查通过，相关运行手册同步。

## 风险和回滚

风险：

- 如果 ModelPad app 未启动或端口变化，脚本可能无法解析 PDF；需要明确诊断信息。
- 移除脚本内服务重启后，长时间运行的服务内存释放依赖 ModelPad app 自身策略。
- 共享运行目录归属不清时，仍可能误删服务侧状态；实施前必须先确认目录边界。
- 图片冲突处理若直接失败，可能让历史样本暴露旧的同名资源问题；需要给出可操作错误信息。

回滚：

- 保留脚本原有解析入口和输出包结构。
- 如 ModelPad 服务不可用，按新契约应先启动 ModelPad app；临时回退到旧版脚本只能作为人工应急，不写入脚本契约。
- 合并 Markdown 和入库草案可重新生成，不作为唯一源数据。

## 阶段 0 完成证据（2026-07-03）

- 已将 ModelPad 托管 PDF 服务约束写入本计划。
- 已定位当前脚本服务生命周期副作用：`scripts/pdf-seg` 停止服务和删除项目 `output/`，`scripts/pdf-auto` trap 删除项目 `output/`，`scripts/pdf-rerun` 删除项目 `output/`。
- 已将阶段 1 收敛为可实施范围：只移除服务管理和共享目录清理副作用，保留端口发现和输出包契约。
- `PLAN_MAP` 已新增 `modelpad-pdf-service-lifecycle` 计划索引。

## 未决问题

| 问题 | 推荐方案 | 是否阻塞当前阶段 | 状态 |
|---|---|---|---|
| ModelPad 暴露的 PDF 服务端口是否固定为 `9000` 起始 | 阶段 1 保留现有 `MINERU_API_BASE_PORT` 起始端口扫描契约，不新增固定端口要求 | 否 | 已确认 |
| 哪些 `output/` 目录属于服务共享运行目录 | 阶段 1 将项目根目录 `output/` 视为脚本不可清理的共享运行目录；脚本只清理自身 `mktemp` 文件和输出包内确定性临时产物 | 否 | 已确认 |
| 无 API 服务时是否允许 MinerU 默认本地运行 | 不允许；阶段 1 完全依赖 ModelPad 托管服务，未探测到服务即明确失败 | 否 | 已确认 |
| 图片同名不同内容时采用失败还是重命名 | 初始建议失败并输出冲突文件清单，避免静默错配 | 否 | 待确认 |

## 关联计划

- [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md)
- [PDF 输出包目录结构计划](pdf-output-package-layout.md)
- [覆盖率验证口径优化计划](coverage-validation-optimization.md)
