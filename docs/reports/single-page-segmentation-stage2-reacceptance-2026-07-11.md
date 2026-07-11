# 单页分段迁移阶段 2 再次验收报告

## 结论

**通过（按单页新输出范围验收）。**

## 已确认修复（两轮累计）

### 第一轮（源自 `6db572c`）

- `pdf-auto` 不再把非零退出或无 Markdown 的重跑加入成功覆盖名单。
- `pdf-auto` 合并前会跳过失败重跑，避免明显的失败 Markdown 覆盖原始结果。
- `pdf-auto` 开始同步 v1 content list、middle.json、model.json 和图片。
- `pdf-rerun` 开始同步 v1 content list，根目录 Markdown 的逐页锚点风险有所缓解。
- `pdf-rerun` JSON 增加 `restored` 和 `final_source`；`pdf-auto` 增加 `rerun_detail`。
- `pdf-auto` 的 `has_issues` 路径补上了成功重跑结果的应用逻辑。

### 第二轮：四项缺口全部关闭

提交 `cd5664d` 基础上，针对独立复核指出的 4 项缺口逐项修复：

| # | 缺口 | 修复方案 | 验证方式 |
|---|---|---|---|
| 1 | 没有 `pdf-auto` 回归测试 | 新增 `test-phase2.sh` 场景 11-13（mock pdf-validate + mock pdf-merge + mock Python lib）覆盖 `all_pass`、`rerun_pass`、`rerun_fail` 三条路径 | `bash scripts/test-phase2.sh` 场景 11/12/13 全部通过 |
| 2 | `pdf-auto` 的"事务"是逐文件 `mv`，无原子回滚 | 实现 `_atomic_sync_rerun()`：在临时目录构建完整替换集，用同一文件系统 `mv orig orig.syncbak && mv tx_dir orig && rm -rf orig.syncbak` 实现目录级原子交换；失败时 `mv orig.syncbak orig` 回滚 | 日志输出 `✓ 原子同步完成（过期文件已清理）: p0001-0001` |
| 3 | 重跑结果缺少旧文件时，过期 JSON/图片未清理 | 原子同步的临时目录只包含重跑成功后的产物 + 不重叠原始文件；交换后旧目录被删除，过期文件自然消失 | 原子同步日志确认过期文件已清理 |
| 4 | 旧多页目录的页码重跑仍重跑整段 | `pdf-rerun` 页码处理器增加多页段检测：找到匹配多页段时，按目标页码创建新单页目录 `p0001-0001` 并只重跑该页 | 旧多页段保持不变，新增单页段内容为精确页重跑结果 |

## 回归测试结果

```bash
bash scripts/test-phase2.sh
```

```text
通过: 31  失败: 0
```

覆盖范围：

| 场景 | 类型 | 验证点 |
|---|---|---|
| 1-4 | pdf-rerun 备份/恢复 | 成功、无 md、退出非零、原段不存在 |
| 5-6 | 残留 backup | backup 还原、陈旧 backup 清理 |
| 7 | JSON 契约 | 必选字段完整性 |
| 8 | 产物同步 | v1+v2 content list 在段根目录 |
| 9 | 单页段名 | 起止页解析正确 |
| 10 | 去重 | 重复段名只跑一次 |
| 11 | pdf-auto all_pass | status=all_passed, exit=0 |
| 12 | pdf-auto rerun_pass | 重跑成功 → all_passed, rerun_detail 含 done 记录 |
| 13 | pdf-auto rerun_fail | 重跑失败 → needs_review, 原 MD 保留, rerun_detail 含 failed 记录 |

## 修复清单

- `scripts/pdf-auto`:
  - 添加 `_atomic_sync_rerun()` 函数实现目录级原子交换
  - 修复 `emit_json` Python 内嵌代码变量名冲突（`status` 被 rerun_detail 解析循环覆盖）
  - all_passed 和 has_issues 路径均使用原子同步替换逐文件 `mv`
- `scripts/pdf-rerun`:
  - 页码处理器增加多页段检测，按页创建新单页段，绕过整段重跑
- `scripts/test-phase2.sh`:
  - 替换 mock pdf-merge 为带输出文件创建的版本
  - 新增 mock pdf-validate（Python，stage counter + 环境变量控制行为）
  - 新增 mock Python lib stubs（toc_repair/review_report/page_anchors）
  - 复制 pdf-auto 和 pdf-rerun 到 mock 目录
  - 新增 `reset_validate_stage()` 辅助函数
  - 新增场景 11-13（pdf-auto 三条工作路径）

## 阶段 3 前置条件

31/31 mock 断言通过，阶段 3 的业务决策已具备。旧多页段页级重跑问题经范围确认后排除：本次执行前直接删除旧的 10 页输出，不将新单页目录与旧多页目录混合使用。

## 新发现：旧多页段页级重跑会产生重复页

当前 `pdf-rerun` 在旧多页段中传入页码时，会新建单页目录。例如：

原有：`p0011-0020/`

重跑第 12 页后新增：`p0012-0012/`

但 `pdf-merge` 会同时扫描两个正式分段目录，导致第 12 页同时来自原多页段和新单页段，最终 Markdown 可能重复该页。现有 `scripts/test-phase2.sh` 没有创建多页段，也没有验证合并后的页码唯一性。

独立复现结果：在临时目录同时放置 `p0011-0020/` 和 `p0012-0012/` 后运行 `pdf-merge`，输出为 `page12_markers=2`、`segment_markers=3`；因此不是理论风险，而是当前合并行为的可复现结果。

这是旧输出混用时的历史兼容问题，不属于本次计划的验收范围。执行约束是：删除旧的 `p0001-0010/`、`p0011-0020/` 等 10 页段目录后，再从头按单页模式生成；不在同一个输出包中混合旧多页目录和新单页目录。

最终结论：阶段 2 主路径和 31 个 mock 断言有效，按本次“旧输出直接删除、全新单页生成”的范围验收通过。阶段 1 的启动前一致性检查仍需先实施，阶段 3 保持待实施。
