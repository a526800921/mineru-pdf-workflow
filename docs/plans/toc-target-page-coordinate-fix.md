# 计划：TOC target_page 页码坐标系修复

## 计划状态

- 状态：实施中
- 当前阶段：阶段 1 已完成 → 阶段 2：下游消费者兼容
- 最后更新：2026-07-12

本文档承接已完成的 [toc-page-physical-attribution-fix](toc-page-physical-attribution-fix.md)，只解决另一个独立问题：`toc_tree.json.target_page` 可能使用印刷页码，而下游和 Markdown 页锚点使用 PDF 物理页码。它不重新打开目录条目属于哪一张物理目录页的既有契约。

## 背景与 Step 0 证据

外部报告 `/Users/jafish/Documents/work/motofind/docs/reports/toc-target-page-offset-fix.md` 记录了春风250Sr/250Sr-R 的典型偏移：正文印刷页从 1 开始，而 PDF 物理页包含封面、版权页和目录等前件页，报告样本中物理页 = 印刷页 + 8。该偏移导致 `pdf-extract-data` 将“最大净功率”等数据映射到错误章节。

现有已完成计划解决的是：

- `toc_page`：目录条目所在的物理目录页；
- 目录页条目的物理归属、重复目录裁剪、`toc.md`/`toc_tree.json` 同源和页锚点保真。

本计划新增核对的是：

- `target_page`：目录条目指向的正文页到底是印刷页还是 PDF 物理页；
- `pdf-extract-data.build_page_section_map()` 消费的页码是否与 `<!-- pages N-N -->` 使用同一坐标系；
- 页码偏移是否已登记在输出包，而不是由某个车型脚本临时写死。

Step 0 必须在当前项目的真实包上用已知锚点复现或排除该问题，不能直接把外部报告的 `+8` 复制到所有 PDF。

## 目标

- 固定 PDF 物理页码和印刷页码的命名、存储与消费契约。
- 在能确定映射时，把 `toc_tree.json.target_page` 标准化为 PDF 物理页码，供结构化抽取和页面跳转使用。
- 保留 `printed_page` 或等价来源字段，避免丢失目录原始页码证据。
- 在 manifest 中记录本包页码基准、偏移/分段映射、证据和验证状态。
- 当页码映射不确定时进入 review，不静默猜测、不生成错误章节归属。
- 让 `pdf-extract-data`、目录展示、页跳转、人工修复和 VLM 证据使用一致的物理页码。

## 非目标

- 不把 `toc_page`（目录所在物理页）和 `target_page`（正文指向页）混成一个字段。
- 不对所有 PDF 固定使用 `+8` 或其他全局常量。
- 不修改原始 PDF、原始 `segments/**/content_list*.json` 或人工修复事实。
- 不因页码修复自动批准结构化数据、解除冲突或生成 `ready`。
- 不重新设计 `toc.md` 的展示文本；只保证其页码来源可追溯。

## 影响模块或文件

- `scripts/lib/toc_repair.py`：读取/验证页码映射，并在写入 `toc_tree.json` 时输出标准化字段。
- `scripts/pdf-extract-data`：消费物理 `target_page`，拒绝未验证的页码坐标系。
- `scripts/pdf-read-page`、`scripts/pdf-table-fix`、`scripts/pdf-table-repair`：验证页码参数和候选证据是否使用物理页码。
- `scripts/pdf-check-fixes`：校验 manifest 页码契约、`toc_tree.json` hash 和消费者一致性。
- `skills/pdf2md/SKILL.md`、`skills/pdf2md-fix/SKILL.md`：说明物理页/印刷页边界；公共契约变化时同步用户级 skill。
- `docs/plans/toc-page-physical-attribution-fix.md`：只通过依赖链接引用既有 `toc_page` 契约，不修改其历史完成证据。

## 页码坐标系契约（设计中）

输出包统一使用：

```json
{
  "page_numbering": {
    "physical_page_basis": "pdf_1_based",
    "printed_page_basis": "content_start_at_1",
    "mapping_type": "constant_offset",
    "printed_to_physical_offset": 8,
    "status": "verified",
    "evidence": [
      {"printed_page": 1, "physical_page": 9, "source": "PDF page label"},
      {"printed_page": 5, "physical_page": 13, "source": "TOC anchor"}
    ]
  }
}
```

约束：

- `physical_page` 是 PDF 文件 1-based 页码，等同于 Markdown `<!-- pages N-N -->` 的页码。
- `printed_page` 是页面印刷或目录显示页码，只作展示和证据，不直接用于下游页段读取。
- `toc_page` 始终表示目录条目所在的物理目录页。
- `toc_tree.target_page` 在验证通过后统一表示物理正文页；可选保留 `printed_page` 作为来源字段。
- `mapping_type` 支持 `constant_offset`、`piecewise`、`identity`、`unknown`；不允许把未知映射当作 `identity`。
- `status` 使用 `proposed`、`verified`、`needs_review`；未验证时相关结构化数据必须保持 `needs_review/not_ready`。

## 分阶段计划

### 阶段 0：页码坐标系基线与转换契约冻结

状态：设计中。

1. 在当前项目的春风250Sr、demo20、demo60 临时副本中读取 `toc_tree.json`、Markdown 页锚点、PDF 页面标签和已知章节/数据行。
2. 选择至少三个锚点（正文起始页、参数页、操作页）验证印刷页与物理页映射。
3. 判断每个包是 `identity`、固定偏移、分段偏移还是无法确认。
4. 冻结 manifest `page_numbering`、`toc_tree` 字段和 review 失败策略。
5. 验证现有 `toc_page` 物理归属逻辑不被改变。

准入条件：当前项目至少一个真实包有可复现的页码映射验证命令，且能区分“目录所在物理页”和“正文指向物理页”。

#### 阶段 0 准入复核（2026-07-12）

结论：达到阶段 1 `待实施` 标准；本次只推进计划，不实施代码。

Step 0 证据：

- 外部春风250Sr报告提供了印刷页与 PDF 物理页的已知锚点：印刷 p25 对应物理 p33，印刷 p5 对应物理 p13，样本中偏移为 `+8`。
- 当前项目 `pdf/春风250Sr/` 的物理页可复核：物理 p13 包含参数表，物理 p33 包含左手把表，物理 p42 包含仪表显示区内容。
- 当前 `toc_tree.json` 的 `仪表显示区` 为 `target_page=42`、`toc_page=3`，与物理 p42 内容和目录物理页语义一致；说明 `toc_page` 与 `target_page` 可以被独立核对，不能合并解释。
- 当前 `pdf-extract-data` 明确使用 `target_page` 构建物理页章节映射；页码契约对下游有可观察影响。

阶段 1 实施前已冻结：`target_page` 标准化为物理页、保留 `printed_page` 证据、manifest 登记 `page_numbering`、未知映射进入 review；不得把 `+8` 写成通用常量。

### 阶段 1：TOC 标准化与 manifest 登记

1. 在 `toc_repair` 的共享输出点执行页码转换，不在车型或单次 fix 脚本中写死偏移。
2. 写入 `target_page`（物理页）及可选 `printed_page`，同步 `page_numbering` 和 `hash.toc_tree_json_sha256`。
3. 映射无法确认时输出 `review.md` 证据，不生成未经验证的物理页映射。
4. 保持 `toc.md`、`toc_tree.json`、主 Markdown 页锚点和 manifest 的原子一致性。

完成条件：同一输出包中目录三件套、页锚点和页码契约一致；重复执行幂等。

#### 阶段 1 完成证据（2026-07-12）

实施文件：`scripts/lib/toc_repair.py`（新增 3 函数 + 修改 3 函数）+ `tests/test_toc_repair.py`（新增 12 测试）。

新增函数：

- `_detect_page_numbering(doc, entries)`：使用 PyMuPDF `get_page_labels()` 检测印刷页/物理页映射；支持 `identity`、`constant_offset`、`unknown` 三种映射类型；无 page labels 时安全降级为 `needs_review`。
- `_normalize_entries(entries, numbering)`：按映射标准化 `target_page` 为物理页；`source_system=printed` 时转换，`source_system=physical` 时保留并记录 `printed_page`；前件页区域条目不加 `printed_page`。
- `_sync_manifest_page_numbering(pkg_root, numbering)`：将 `page_numbering` 块和 `hash.toc_md_sha256`、`hash.toc_tree_json_sha256` 写入 manifest；保留现有字段；manifest 不存在时安全返回。

修改函数：

- `_write_toc_tree()`：条目含 `printed_page` 时输出该字段到 `toc_tree.json`。
- `repair_merged()`：在写入 `toc_tree.json` 前调用检测→标准化，写入后同步 manifest。
- `repair()`：同上。

验证：

```bash
pytest -q                          # 221 passed（含新增 12 个页码检测测试）
python3 scripts/check_plan_governance.py .  # 计划治理检查通过
```

春风250Sr 实测：offset=8 正确检测，`source_system=physical`（条目已使用物理页），标准化后 `printed_page` 正确记录（"致顾客" page=9 printed=1，"参数" page=13 printed=5）。春风150AURA 实测：offset=1 正确检测。demo20/demo60：无 page labels → `unknown/needs_review` 安全降级。

### 阶段 2：下游消费者兼容

1. `pdf-extract-data` 只消费物理 `target_page`，并验证章节映射与页锚点一致。
2. `pdf-read-page`、`pdf-table-fix`、`pdf-table-repair` 明确接收物理页码；展示印刷页码时必须显式命名。
3. 记录页码修正前后的 `section_path`、`record_id`、冲突和审核状态变化；不得自动把新记录置为 `approved/ready`。
4. 验证旧格式 `toc_tree.json` 的兼容读取和缺少 `page_numbering` 时的安全降级。

完成条件：页码修正不破坏旧消费者；错误映射不会静默进入 `ready` 或导出批次。

### 阶段 3：真实样本回填

1. 在临时副本验证春风250Sr/250Sr-R 的前件页偏移。
2. 用 demo20、demo60 和至少一个不同前件页数量的 PDF 验证 identity/constant/piecewise/unknown 分支。
3. 对页码修正前后重新运行 `pdf-extract-data`、`pdf-prepare-ingest` 和 `pdf-export-ingest`，比较章节、记录 ID、冲突和 ready 门禁。

完成条件：真实样本中章节归属正确、页码证据可追溯、审核门禁不被绕过。

### 阶段 4：独立验收

- 物理页/印刷页字段和 manifest 契约有 schema 级验证；
- `toc_tree.target_page` 与 Markdown 页锚点、`pdf-extract-data` section map 一致；
- `toc_page` 和 `target_page` 语义不混淆；
- 固定偏移、无偏移和无法确认三类样本均有回归；
- 旧 `toc_tree` 格式、目录三件套、结构化抽取、入库审核和导出无回归；
- 治理、drift、全量测试和真实包检查通过。

## 风险与回滚

| 风险 | 控制措施 | 回滚 |
|---|---|---|
| 把印刷页误当物理页 | 记录两套页码和锚点证据，未知映射进入 review | 恢复原 toc_tree/manifest，结构化结果保持 not_ready |
| 不同章节存在分段偏移 | 支持 piecewise/unknown，不强制常量偏移 | 对不确定区间停止自动映射 |
| target_page 修正导致 record_id 变化 | 保存前后映射和来源 hash，重新生成审核候选 | 保留旧候选，不静默覆盖 review override |
| 目录修复与表格/抽取并行漂移 | 目录产物、page_numbering 和 hash 原子登记 | 整组回滚派生产物 |
| 报告声称 ready 但未完成审核 | 保持 `approved + evidence + no conflict` 三重门禁 | 清除批量 override，重新生成 not_ready |

## 验证方式

```bash
python3 scripts/pdf-extract-data <package>
python3 scripts/pdf-prepare-ingest <package>
python3 scripts/pdf-export-ingest <package>
python3 scripts/pdf-check-fixes <package>
pytest -q
python3 scripts/check_plan_governance.py .
python3 scripts/check_plan_governance.py . --drift
git diff --check
```
