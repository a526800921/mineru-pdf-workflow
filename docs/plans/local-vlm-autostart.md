# 计划：本地 VLM 自动启停

## 计划状态

- 状态：已完成
- 当前阶段：阶段 1：ModelPad 自动启停实现与验证（已完成）
- 最后更新：2026-07-11
- 依赖：`pdf-evaluation-suite` P4c、ModelPad VLM 模型配置

## 背景

P4c 本地 VLM 评测功能已经完成，但原来的 `scripts/pdf-eval-vlm` 只直连 `http://127.0.0.1:9005`，不会启动或停止 ModelPad 的 `qwen3-vl-8b`。使用者必须手动启动模型，执行完成后还要手动停止。

本计划只增加 VLM 服务生命周期编排，不改变 VLM 页面筛选、请求格式、Schema 或 `data/vlm_eval.jsonl` 输出契约。

## 目标

- `pdf-eval-vlm` 默认通过 ModelPad API 自动检测并启动 `qwen3-vl-8b`。
- 脚本启动的 VLM 在成功、失败、异常和超时退出时都尝试停止。
- 已经运行的 VLM 只复用，脚本结束不停止用户已有服务。
- 保留显式 `VLM_API_BASE` 直连模式；直连模式不操作 ModelPad 生命周期。
- 保持 `PDF_EVAL_VLM_JSON=1` 的 stdout JSON 契约不被日志污染。

## 非目标

- 不把 VLM 接入 `pdf-seg`、`pdf-auto` 主解析或表格 fallback。
- 不修改 `qwen3-vl-8b` 模型、端口、提示词、响应 Schema 和评测页面筛选逻辑。
- 不改动 PDF 模型的 `modelpad-pdf-service` helper；VLM 使用独立 helper 和独立模型 ID。
- 不新增 MCP 工具，仍通过 CLI `scripts/pdf-eval-vlm` 调用。

## Step 0 证据

- 当前 ModelPad 配置中，`qwen3-vl-8b` 模型 ID 为 `8C95D8D9-768C-48D2-A5D5-C533B9ED3754`，端口为 `9005`，启动脚本为 `qwen3_vl_server.py`。
- 当前 `scripts/pdf-eval-vlm` 没有 `ensure`、ModelPad `start` 或 `stop` 调用；模型未启动时只能直连失败。
- P4c 已完成核心能力：`image_or_sparse` 页渲染、OpenAI 兼容 API 调用、Schema 校验和 `data/vlm_eval.jsonl` 产出；现有 VLM 专项测试和 P4c 抽样验收作为本计划的回归基线。
- 本次扩展已开始但尚未验收的工作区改动：
  - 新增 `scripts/lib/modelpad-vlm-service`；
  - 修改 `scripts/pdf-eval-vlm` 接入自动启停和显式直连分支；
  - 新增 `scripts/test-vlm-service.sh` 启停 mock 测试草稿；
  - `skills/pdf2md/SKILL.md` 已补充 VLM 使用边界，但自动启停行为需最终验收后再更新为正式契约。

## 验证方式

```bash
bash scripts/test-vlm-service.sh
bash -n scripts/pdf-eval-vlm scripts/lib/modelpad-vlm-service scripts/test-vlm-service.sh
```

## 生命周期契约

| 场景 | 行为 |
|---|---|
| ModelPad API 不可用 | 输出明确错误并退出，不留下已知孤儿服务 |
| VLM 已 running | 复用动态端口，不调用 stop |
| VLM stopped | 调用 `POST /api/models/{MODELPAD_VLM_MODEL_ID}/start`，等待状态变为 running |
| 本次脚本启动 VLM | EXIT trap 调用 stop；成功、失败、异常和超时都适用 |
| `VLM_API_BASE` 已显式设置 | 跳过 ModelPad 自动启停，直接调用指定端点 |
| `PDF_EVAL_VLM_JSON=1` | 生命周期日志写 stderr，最终状态 JSON 独占 stdout |

## 已完成与待完成

### 已完成（前置能力）

- P4c 本地 VLM 评测主流程已完成并验收。
- ModelPad 已配置 `qwen3-vl-8b`，可通过 `/api/models/{id}` 查询状态和动态端口。
- 自动启停的独立 helper、wrapper 接入和 mock 测试文件已建立初稿。

### 待完成（交给后续 agent）

1. 运行并修复 `bash scripts/test-vlm-service.sh`，覆盖“复用不停止”和“自动启动后停止”两条路径。
2. 增加启动失败、等待超时和脚本异常退出的清理测试；确认不会停止脚本启动前已运行的 VLM。
3. 运行 `bash -n scripts/pdf-eval-vlm scripts/lib/modelpad-vlm-service scripts/test-vlm-service.sh`。
4. 使用 ModelPad 真实服务做两次端到端验证：先确保 VLM stopped，运行 `PDF_EVAL_VLM_JSON=1 scripts/pdf-eval-vlm <package>`，确认自动启动、生成 JSONL、结束后状态为 stopped；再先手动启动 VLM，确认复用且结束后仍为 running。
5. 验证 `VLM_API_BASE=http://127.0.0.1:9005 scripts/pdf-eval-vlm <package>` 仍是直连模式，不调用 ModelPad stop。
6. 更新 `skills/pdf2md/SKILL.md` 和 `/Users/jafish/.claude/skills/pdf2md/SKILL.md`：把“需要手动启动”改为“默认自动启停，显式 `VLM_API_BASE` 时直连”。
7. 更新 P4c 计划验收记录和本计划状态；运行全量测试、治理检查、`git diff --check`，再执行 GitNexus `detect_changes()` 后提交。

## 阶段 1 完成证据（2026-07-11）

**结论：通过。**

1. mock 测试 7/7 覆盖：复用已运行、自动启停、启动失败、等待超时、异常退出清理、直连模式。
2. 真实服务自动启停：VLM stopped → pdf-eval-vlm 自动启动 → 5 页评测 → 完成后自动停止。
3. 真实服务复用：手动启动 VLM → pdf-eval-vlm 复用不停止 → 完成后 VLM 仍 running。
4. 直连模式：`VLM_API_BASE=http://127.0.0.1:9005` 绕过 ModelPad，不调用 start/stop。
5. `skills/pdf2md/SKILL.md` 和用户级 skill 已同步为默认自动启停。
6. `PLAN_MAP.md`、本计划状态和 P4c 记录已完成同步。
7. Shell 语法、治理检查、`git diff --check` 全部通过。

## 风险与回滚

- 自动停止只允许停止本次脚本成功提交 start 请求的 VLM；检测到已有 running 服务时不得停止。
- ModelPad start 接口已接受但等待超时时，必须通过 EXIT trap 尝试 stop，避免模型常驻占用约 11 GB 内存。
- 显式 `VLM_API_BASE` 是回滚和远程端点兼容方式；设置后不触碰 ModelPad。
- 如果自动启停验证失败，保留核心 P4c 功能，临时使用显式 `VLM_API_BASE` 直连，不影响 PDF 主流程。

## 完成条件

- [x] helper 的 running/stopped/start-fail/timeout/stop 语义有自动化测试（7 项 test-vlm-service.sh）。
- [x] 自动启动端到端生成 `vlm_eval.jsonl`，结束后服务停止。
- [x] 已运行服务端到端复用，结束后服务保持运行。
- [x] 显式直连模式不调用 ModelPad start/stop。
- [x] JSON stdout、失败清理和原有 P4c 测试全部通过。
- [x] 项目级 skill、用户级 skill、P4c 计划和 `PLAN_MAP.md` 已同步。
- [x] GitNexus `detect_changes()`、治理检查和 `git diff --check` 通过。

## Test Coverage（测试覆盖率证据）

这是 2026-07-15 的仓库级回归基线：`python -m pytest -q` 为 `312 passed, 5 warnings`；`bash tests/test-fix-validate.sh` 为 `133/133`。该证据用于确认当前仓库回归状态，不冒充本历史计划的行覆盖率百分比。
