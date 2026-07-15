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
| 阶段 1 | 移除脚本服务管理副作用 | 阶段 0 完成 | 脚本不启动/重启/关闭服务，不清理共享运行目录 | 已完成 |
| 阶段 2 | 修复自动重跑失败兜底 | 阶段 1 完成 | 模拟 `mineru` 非 0 后仍生成诊断或 review | 已完成 |
| 阶段 3 | 图片冲突检测和运行手册同步 | 阶段 2 完成 | 同名不同内容图片不静默错配，运行手册可复现 | 已完成 |

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

### 阶段 1 完成证据（2026-07-03）

- `scripts/pdf-seg`：移除 `MINERU_API_RESTART` 整段（kill + output/ 清理 + "mineru-api 已停" 提示）；`_api_arg` 和 `if/else` 分支合并为单一 `mineru --api-url "$api_url"` 调用；无 API 时明确报错退出。
- `scripts/pdf-auto`：两处 `trap` 改为只清理 `mktemp` 文件和 `_rerun_names_file`，不再触碰项目 `output/`；重跑 `mineru` 调用合并为单一 `--api-url` 路径；无 API 时输出 JSON 错误（`PDF_AUTO_JSON=1`）或文本日志并退出。
- `scripts/pdf-rerun`：移除项目 `output/` 清理段落；`_api_arg` 改为无条件设置 `--api-url`；无 API 时明确报错退出。
- 三个脚本均通过 `bash -n`；`MINERU_API_RESTART`、`mineru-api 已停`、`kill.*_api_pid`、`rm -rf.*output` 全部零残留。
- 治理检查通过（`python3 scripts/check_plan_governance.py .`）；`git diff --check` 通过。
- 净变更：3 文件，+22 / -72 行。

### 阶段 2 完成证据（2026-07-03）

- `scripts/pdf-auto` 行 882 的 `mineru` 重跑调用从裸调用改为 `if mineru ... ; then mineru_rc=0; else mineru_rc=$?; fi` 包装。
- `if` 条件在 bash `set -e` 下不会触发提前退出；`else` 分支中 `$?` 正确捕获 mineru 退出码。
- 模拟测试验证：mineru 成功（`rc=0`→成功路径）和 mineru 失败（`rc=1`→失败兜底）均不会因 `set -e` 退出。
- `bash -n` 通过；其余脚本逻辑（二次验证、`review.md` 生成、JSON 输出）不受影响。

### 阶段 3 完成证据（2026-07-03）

- `scripts/pdf-merge` 内嵌 Python 增加 `hashlib` 导入和 `file_sha256(path)` 辅助函数。
- 图片收集逻辑改为三段式：不存在→复制；存在且 SHA-256 相同→跳过（幂等）；存在且 SHA-256 不同→收集冲突。
- 冲突图片输出源路径和目标路径到 stderr，`raise SystemExit` 非 0 退出。
- 幂等跳过时输出 `跳过幂等图片: N 张（同名同内容）`。
- fixture 验证：同名同内容（退出 0，1 复制 + 1 跳过）、同名不同内容（退出 1，输出冲突路径）。
- `bash -n` 通过。

## 阶段 3：可实施设计

阶段 3 聚焦 `scripts/pdf-merge` 的图片收集确定性。当前实现按文件名去重，目标文件已存在就跳过；如果不同分段生成同名但内容不同的图片，合并 Markdown 可能引用错误图片。阶段 3 初始策略采用“同名不同内容直接失败并输出冲突清单”，避免静默错配。

### 阶段 3 目标

- `scripts/pdf-merge` 收集图片时计算源文件和目标文件内容哈希。
- 同名且内容相同：视为幂等重复，不复制，不报错。
- 同名但内容不同：终止合并流程，输出冲突图片路径和目标路径。
- 不改变合并 Markdown 的默认输出路径、图片目录路径或 Markdown 内容拼接规则。
- 更新运行手册或计划完成证据，说明图片同名冲突的失败语义。

### 阶段 3 非目标

- 不实现自动重命名图片。
- 不重写 Markdown 图片引用。
- 不改变 `pdf-seg`、`pdf-auto`、`pdf-rerun` 的服务生命周期逻辑。
- 不处理远程图片 URL 或 Markdown 中未被复制的历史图片引用。

### 阶段 3 现状证据

| 文件 | 现状 | 阶段 3 处理 |
|---|---|---|
| `scripts/pdf-merge` | 行 100 起收集图片；当 `pkg_images / img.name` 已存在时直接跳过 | 增加 SHA-256 内容比较；相同跳过，不同失败 |
| `docs/plans/pdf-output-package-layout.md` | 已记录 `pdf-merge` 图片同名冲突可能静默跳过的风险 | 阶段 3 完成后更新为已解决或链接完成证据 |
| `docs/PLAN_MAP.md` | 当前阻塞项记录图片同名冲突风险 | 阶段 3 完成后同步状态 |

### 阶段 3 实施步骤

1. 对 `scripts/pdf-merge` 做 GitNexus 影响分析；如果图谱仅识别文件级 CLI，则记录文件级影响面。
2. 修改 `scripts/pdf-merge` 内嵌 Python：
   - 引入 `hashlib`。
   - 新增 `file_sha256(path)`。
   - 复制图片前判断 `dest.exists()`：
     - 不存在：照常复制并计数。
     - 存在且 hash 相同：跳过，作为幂等重复。
     - 存在且 hash 不同：记录冲突，循环结束后 `raise SystemExit`，输出冲突源和目标。
3. 增加最小 fixture 验证，不依赖 MinerU：
   - 创建临时包目录，包含两个分段 Markdown 和两个同名同内容图片，验证 `pdf-merge` 成功。
   - 创建两个同名不同内容图片，验证 `pdf-merge` 非 0 退出且输出冲突信息。
4. 运行静态检查、治理检查和 GitNexus `detect_changes`。
5. 更新阶段 3 完成证据、`PLAN_MAP` 当前阻塞项和相关风险记录。

### 阶段 3 验证方式

```bash
bash -n scripts/pdf-merge

tmp="$(mktemp -d)"
mkdir -p "$tmp/pkg/segments/p0001-0001/images" "$tmp/pkg/segments/p0002-0002/images"
printf '# A\n![x](images/a.png)\n' > "$tmp/pkg/segments/p0001-0001/a.md"
printf '# B\n![x](images/a.png)\n' > "$tmp/pkg/segments/p0002-0002/b.md"
printf 'same' > "$tmp/pkg/segments/p0001-0001/images/a.png"
printf 'same' > "$tmp/pkg/segments/p0002-0002/images/a.png"
scripts/pdf-merge "$tmp/pkg/segments"

tmp="$(mktemp -d)"
mkdir -p "$tmp/pkg/segments/p0001-0001/images" "$tmp/pkg/segments/p0002-0002/images"
printf '# A\n![x](images/a.png)\n' > "$tmp/pkg/segments/p0001-0001/a.md"
printf '# B\n![x](images/a.png)\n' > "$tmp/pkg/segments/p0002-0002/b.md"
printf 'one' > "$tmp/pkg/segments/p0001-0001/images/a.png"
printf 'two' > "$tmp/pkg/segments/p0002-0002/images/a.png"
if scripts/pdf-merge "$tmp/pkg/segments"; then
  echo "expected image conflict failure" >&2
  exit 1
fi

python3 scripts/check_plan_governance.py .
node .gitnexus/run.cjs detect_changes --repo mineru-pdf-workflow
```

### 阶段 3 完成条件

- 同名同内容图片保持幂等，不重复复制、不报错。
- 同名不同内容图片使 `pdf-merge` 非 0 退出，并输出冲突源文件和目标文件。
- 合并 Markdown 逻辑和默认输出路径不变。
- `bash -n scripts/pdf-merge` 通过。
- 最小 fixture 覆盖同名同内容和同名不同内容两条路径。
- 治理检查通过，`PLAN_MAP` 和相关风险记录同步。

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
| 图片同名不同内容时采用失败还是重命名 | 阶段 3 采用失败并输出冲突文件清单，避免静默错配；自动重命名留给后续需要时再设计 | 否 | 已确认 |

## 关联计划

- [自动化 PDF 解析流水线计划](automated-pdf-pipeline.md)
- [PDF 输出包目录结构计划](pdf-output-package-layout.md)
- [覆盖率验证口径优化计划](coverage-validation-optimization.md)

## Test Coverage（测试覆盖率证据）

这是 2026-07-15 的仓库级回归基线：`python -m pytest -q` 为 `312 passed, 5 warnings`；`bash tests/test-fix-validate.sh` 为 `133/133`。该证据用于确认当前仓库回归状态，不冒充本历史计划的行覆盖率百分比。
