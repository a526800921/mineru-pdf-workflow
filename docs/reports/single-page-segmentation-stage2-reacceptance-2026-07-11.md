# 单页分段迁移阶段 2 再次验收报告

## 结论

**未通过。**

提交 `6db572c` 已修复上一轮发现的 6 项主要问题，但独立复核仍发现数据同源、备份安全、事务回滚和回归测试方面的缺口。

## 已确认修复

- `pdf-auto` 不再把非零退出或无 Markdown 的重跑加入成功覆盖名单。
- `pdf-auto` 合并前会跳过失败重跑，避免明显的失败 Markdown 覆盖原始结果。
- `pdf-auto` 开始同步 v1 content list、middle.json、model.json 和图片。
- `pdf-rerun` 开始同步 v1 content list，根目录 Markdown 的逐页锚点风险有所缓解。
- `pdf-rerun` JSON 增加 `restored` 和 `final_source`；`pdf-auto` 增加 `rerun_detail`。
- `pdf-auto` 的 `has_issues` 路径补上了成功重跑结果的应用逻辑。

## 仍未通过的项目

| 项目 | 证据 | 风险 |
|---|---|---|
| v2 content list 未同步 | 覆盖逻辑只查找非 v2 的 `*_content_list.json` | 页面类型验证和新 Markdown 可能不同源 |
| `pdf-rerun` 直接入口产物不完整 | 只复制 v1 content list，没有 middle/model/v2/images | 直接重跑与自动重跑结果契约不一致 |
| 残留 backup 处理不安全 | 发现 `.backup` 后直接 `rm -rf` | 原目录缺失时可能丢失唯一原始结果 |
| 覆盖过程非事务 | Markdown、JSON、图片逐项 `cp` | 中途失败可能留下半更新分段 |
| 缺少回归测试 | `6db572c` 只修改脚本和文档，没有测试文件 | 无法独立证明失败恢复和兼容路径 |

## 必须补齐的验收证据

1. 增加可运行回归测试，覆盖成功、无 Markdown、非零退出、残留 backup、部分复制失败、单页目录和旧多页目录。
2. 明确并验证 v1/v2 content list、middle、model、images 的整套同源替换。
3. 将残留 backup 改为恢复或中止策略，并验证原始目录缺失时不丢数据。
4. 以临时输出包执行自动流程，验证失败时原始分段和最终合并结果均保持不变。

阶段 3 仍不得开始代码实施。
