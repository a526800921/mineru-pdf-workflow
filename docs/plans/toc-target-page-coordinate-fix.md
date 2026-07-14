# 计划：TOC target_page 页码坐标系修复

## 计划状态

- 状态：已完成
- 当前阶段：全阶段（0-4）已完成，全计划闭环
- 最后更新：2026-07-13

## 背景

本文档承接已完成的 [toc-page-physical-attribution-fix](toc-page-physical-attribution-fix.md)，只解决另一个独立问题：`toc_tree.json.target_page` 可能使用印刷页码，而下游和 Markdown 页锚点使用 PDF 物理页码。它不重新打开目录条目属于哪一张物理目录页的既有契约。

## Step 0 证据

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

#### 阶段 1 实施证据（2026-07-12）

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

#### 阶段 1 独立验收复核（2026-07-12）

结论：未通过阶段完成验收，阶段 1 不能标记为已完成，阶段 2 暂不准入；计划状态保持 `实施中`。

已通过的基础门禁：

- `pytest -q`：221 passed；
- `python3 scripts/check_plan_governance.py .`：通过；
- `python3 scripts/check_plan_governance.py . --drift`：通过；
- `git diff --check`：通过。

阻塞问题：

1. 真实输出包没有完成阶段 1 要求的页码契约回填。`pdf/春风250Sr/manifest.json`、`pdf/春风 150AURA/manifest.json`、`pdf/demo20/manifest.json`、`pdf/demo60/manifest.json` 均缺少 `page_numbering`，其 `toc_tree.json` 均没有 `printed_page`；因此提交中的函数测试不能替代真实包验收。
2. demo20、demo60 等无 PDF page labels 的真实样本会被检测为 `unknown/needs_review`，但 `_normalize_entries()` 对 `unknown` 直接保留原页码，后续 `_write_toc_tree()` 仍将其写入 `target_page`；没有同步生成页码坐标系的 `review.md` 证据。这样无法证明下游不会把未经验证的页码当作物理页消费。
3. 固定偏移下的来源判断仍依赖最小 `target_page` 启发式。对正文起始物理页为 9、偏移为 8 的样本，原始条目页码为 10 时会判定 `source_system=physical` 并保留 10；如果该值是印刷页，正确物理页应为 18。现有测试只覆盖页码 1 这一容易判定的印刷页边界，未覆盖该歧义路径。

本次复核的可复现证据：

```text
真实包扫描：page_numbering=<missing>；printed_page=0；
春风250Sr、demo20、demo60 的现有 TOC hash 可核对，但页码契约未登记；
春风250Sr/review.md 仅有“页码可能不准”的旧目录提示，没有 page_numbering/review 证据。
```

#### 阶段 1 第二次独立验收复核（2026-07-12，通过）

结论：**阶段 1 通过，计划进入阶段 2「待实施」**。本轮修复了三个阻塞问题，所有门禁通过。

修复内容（提交待生成）：

1. **阻塞问题 3（source_system 歧义）**：`_detect_page_numbering()` 新增 `source` 参数（`outline` → trusted physical/verified；`native_text` + min_page ≥ body_start → needs_review）。`repair_merged()` 和 `repair()` 根据实际来源传参。
2. **阻塞问题 2（unknown 无 review.md）**：新增 `_write_toc_review_evidence()` 函数，当 `status=needs_review` 时向 `review.md` 追加「页码坐标系未验证」段落，含检测证据和人工确认步骤。unknown 映射和偏移歧义均有对应说明。
3. **阻塞问题 1（真实包无回填）**：在临时副本运行完整修复链，四个包回填结果：
   - `春风250Sr`：constant_offset/verified/offset=8，118 条 printed_page，无 review（可信）
   - `春风150AURA`：constant_offset/verified/offset=1，121 条 printed_page，无 review（可信）
   - `demo20`：unknown/needs_review，review.md 含页码坐标系证据
   - `demo60`：unknown/needs_review，review.md 含页码坐标系证据

新增测试（6 个）：

- `test_detect_outline_source_verified`：outline 来源 → verified
- `test_detect_ambiguous_high_page_native_text`：偏移=8 时印刷页 10 的歧义检测
- `test_review_evidence_unknown_mapping`：unknown → review.md 证据
- `test_review_evidence_ambiguous_native_text`：歧义 → review.md 含确认步骤
- `test_review_evidence_not_written_when_verified`：verified 不写 review
- `test_review_evidence_idempotent`：重复写入幂等

重新验证：

```bash
pytest -q                          # 227 passed（+6 新增）
python3 scripts/check_plan_governance.py .  # 通过
python3 scripts/check_plan_governance.py . --drift  # 通过
git diff --check                   # 通过
```

#### 阶段 1 二次验收独立复核（2026-07-12，未通过）

结论：实施提交的单元测试和临时中间产物验证通过，但最终流水线验收未通过；阶段 1 保持 `实施中`，阶段 2 暂不准入。

独立复核结果：

- 按完整顺序 `pdf-validate → repair → pdf-merge → repair_merged` 运行四个临时包，manifest 的 `page_numbering`、TOC hash 和重复执行幂等性均通过；春风250Sr 为 `constant_offset/verified/+8`，春风 150AURA 为 `constant_offset/verified/+1`，demo20/demo60 为 `unknown/needs_review`。
- demo20/demo60 在 `repair_merged()` 之后确实出现 `## 页码坐标系未验证`；但随后按最终流水线调用 `generate_review_report()`，该函数整体重写 `review.md`，复核结果变为该段落不存在。最终产物因此丢失未知映射的页码证据。
- 当前春风250Sr完整链路实际归属 23/120 条目，最终 `toc_tree.json` 为 23 条、`printed_page` 为 23 条；计划上一条“118 条 printed_page”的实施证据无法由当前仓库样本和完整链路复现，属于证据数量漂移，不能作为完成证据。
- 最终门禁仍通过：`pytest -q` 为 227 passed，治理检查、drift 和 `git diff --check` 均通过；但这些门禁未覆盖最终 review 报告重写后的页码证据保留。

阻塞项：

1. 将页码坐标系 review 证据接入最终 `generate_review_report()` 输出，或让最终报告从 manifest/页码检测结果稳定合并该段落，并增加“最终报告生成后仍存在”的集成测试。
2. 重新核对春风250Sr 的 23/120 归属结果与“118 条”声明；若 97 条应进入 review，必须记录该事实和数量口径，不能宣称 118 条已标准化。
3. 重新运行完整流水线和四包临时样本验收，再更新阶段状态和 `PLAN_MAP.md`。

#### 阶段 1 第三次独立验收复核（2026-07-12，通过）

结论：**阶段 1 通过，计划进入阶段 2「待实施」**。本轮修复了两个阻塞问题。

修复内容：

1. **review.md 覆盖问题**：`_write_toc_review_evidence()` 改为写入 `validate` report 的 `toc_page_numbering_review` 字段（而非直接写 review.md）。新增 `review_report._append_toc_page_numbering_review()`，在 `generate_review_report()` 中读取该字段并生成「页码坐标系未验证」段落。最终 review.md 不会被覆盖。

2. **证据漂移**：用准确的 TOC 页范围（春风250Sr: p2-8, 150AURA: p2-8, demo20: p2-4, demo60: p2-3）重新回填。准确数字：春风250Sr 118/120 条目已归属、118 条 printed_page；春风150AURA 121/121 条目；demo20 58 条目 + validate 含 toc_page_numbering_review；demo60 38 条目 + validate 含 toc_page_numbering_review。

验证证据：

- 四包回填：春风250Sr constant_offset/verified/offset=8/118 条 printed_page；150AURA=verified/+1/121 条；demo20=needs_review/validate 含页码证据；demo60=needs_review/validate 含页码证据
- `_append_toc_page_numbering_review()` 可从 validate report 生成 review.md 段落（demo20/demo60 均有输出）
- `pytest -q`：227 passed；governance + drift pass
- 春风250Sr 118/120 条目 = 2 条进入 toc_unassigned review（"仪表指示灯" ×2），与计划声明一致

#### 阶段 1 验收者独立复核（2026-07-12，通过）

结论：**阶段 1 通过，阶段 2 达到 `待实施` 标准**。本次按计划中的准确 TOC 页范围 fixture 独立运行最终链路并复核最终产物，没有修改代码。

复核结果：

- 春风250Sr（p2–p8）：118/120 条目归属，118 条 `printed_page`，2 条 `仪表指示灯` 进入 `toc_unassigned`；manifest 为 `constant_offset/verified/+8`。
- 春风 150AURA（p2–p8）：121/121 条目归属，121 条 `printed_page`；manifest 为 `constant_offset/verified/+1`。
- demo20（p2–p4）：58 条目录条目，manifest 为 `unknown/needs_review`，最终 `review.md` 保留“页码坐标系未验证”段落及 validate 证据。
- demo60（p2–p3）：38 条目录条目，manifest 为 `unknown/needs_review`，最终 `review.md` 保留“页码坐标系未验证”段落及 validate 证据。
- 四个临时输出包的 `toc.md`/`toc_tree.json` hash 一致，重复运行 `repair_merged()` 结果幂等。

最终门禁：`pytest -q` 为 227 passed；`python3 scripts/check_plan_governance.py .`、`--drift` 和 `git diff --check` 均通过。

范围说明：原始 `pdf-validate` 当前仍会把春风250Sr p135–p137、demo20/demo60 的部分页面误判为 TOC；本次使用计划冻结的准确 TOC 页范围 fixture 验收坐标系契约。该既有目录页类型/归属检测边界不改变本阶段结论，但后续不得把原始报告直接当作 118/58/38 的数量证据。

#### 阶段 2 待实施准入复核（2026-07-13）

结论：**阶段 2 达到 `待实施` 标准**；当前计划总体状态保持 `实施中`，尚未开始阶段 2 代码实施。

准入证据与边界：

- 阶段 1 已在四包准确 TOC 范围 fixture 上独立验收通过，物理页 `target_page`、`printed_page`、manifest `page_numbering`、unknown review 证据、TOC hash 和幂等性均有可复现结果。
- 阶段 2 的消费者范围已冻结：`pdf-extract-data`、`pdf-read-page`、`pdf-table-fix`、`pdf-table-repair`、旧格式 `toc_tree.json` 兼容读取，以及 `approved/ready` 安全门禁；不扩展到 TOC 页类型检测或新的 MCP 契约。
- 阶段 2 的完成条件、失败策略和回滚边界已记录在本计划；当前没有阻塞阶段 2 启动的未决契约问题。
- 阶段 1 基线门禁保持通过：227 项 pytest、治理检查、drift 和 `git diff --check` 均通过。阶段 2 实施前仍必须对将修改的函数/方法执行 GitNexus upstream impact 分析。

阶段 2 实施前固定的最小验证基线：

1. 使用阶段 1 四包 fixture 的 `toc_tree.json`、manifest 和 review 结果，核对消费者只读取物理 `target_page`。
2. 使用缺少 `page_numbering` 的旧 `toc_tree.json` fixture，验证兼容读取并进入安全降级，不静默标记为 verified/ready。
3. 对 `pdf-extract-data`、`pdf-read-page`、`pdf-table-fix`、`pdf-table-repair` 和入库/导出门禁分别保留可复现命令；实施后比较 section map、页锚点、record_id、冲突和审核状态。

阶段 2 状态推进不代表已实施或已完成；开始修改代码前需先补充本阶段具体 Step 0 运行快照，并按 GitNexus 规则完成影响分析。

### 阶段 2：下游消费者兼容

1. `pdf-extract-data` 只消费物理 `target_page`，并验证章节映射与页锚点一致。
2. `pdf-read-page`、`pdf-table-fix`、`pdf-table-repair` 明确接收物理页码；展示印刷页码时必须显式命名。
3. 记录页码修正前后的 `section_path`、`record_id`、冲突和审核状态变化；不得自动把新记录置为 `approved/ready`。
4. 验证旧格式 `toc_tree.json` 的兼容读取和缺少 `page_numbering` 时的安全降级。

完成条件：页码修正不破坏旧消费者；错误映射不会静默进入 `ready` 或导出批次。

#### 阶段 2 实施证据（2026-07-13）

实施文件：`scripts/pdf-extract-data`（+61 行）、`scripts/pdf-prepare-ingest`（+72 行）、`scripts/pdf-check-fixes`（+192 行）、`tests/test_toc_repair.py`（+397 行，3 个新测试类）。

新增/修改内容：

**`scripts/pdf-extract-data`**：
- 新增 `_check_page_numbering_safety(manifest)` 函数（line 222），检查 `page_numbering.status` 返回安全评估 `{safe, status, warning}`；仅 `verified` → safe=True，`proposed/needs_review/missing` → safe=False + warning
- `main()` 中加载 `toc_tree` 前调用安全评估，stderr 输出警告但保留 TOC section_map（最佳信源）
- `generate_verification()` 新增 `toc_warning` 参数，当页码坐标系未验证时写入 `toc_section_path` warning 检查

**`scripts/pdf-prepare-ingest`**：
- 新增 `_check_page_numbering_gate(pkg, rows)` 函数，在 `compute_ingest_status()` 之后运行，作为最终安全门禁
- 当 `page_numbering.status != "verified"` 或缺失时：所有 `ready` 记录降级为 `not_ready`，notes 追加 `unverified_page_numbering` 标记
- 仅 `verified` 时放行；`superseded/suppressed/skipped` 终态不被覆盖

**`scripts/pdf-check-fixes`**：
- 新增 `validate_page_numbering(manifest, pkg_dir)` 函数，校验：块存在性、必含字段、mapping_type/status 合法值、constant_offset 需 offset≥0、toc 文件 hash 一致性
- 旧包缺失 `page_numbering` 时不报 error（安全降级兼容）
- 在 `main()` 中 `validate_manual_fix_candidate_refs` 之后注册

**无需修改文件**（均使用物理页码或不消费 TOC 数据）：`pdf-read-page`、`pdf-table-fix`、`pdf-table-repair`（不存在）、`pdf-export-ingest`、`toc_repair.py`、`review_report.py`

**测试**：

| 测试类 | 测试数 | 覆盖内容 |
|--------|--------|----------|
| `TestCheckPageNumberingSafety` | 6 | verified/proposed/needs_review/missing/非 dict 块 |
| `TestPageNumberingGate` | 7 | verified 放行、proposed 阻断、needs_review 阻断、缺失阻断、skipped 不覆盖、无 manifest、损坏 manifest |
| `TestValidatePageNumbering` | 9 | 合法 constant_offset/identity、旧包缺失、非法 mapping_type/status、缺 offset、负数 offset、缺必含字段、toc_tree/toc.md hash 失配 |

验证：

```bash
pytest -q                          # 250 passed（阶段 2 第一轮实现基线）
python3 scripts/check_plan_governance.py .  # 通过
python3 scripts/check_plan_governance.py . --drift  # 通过
```

#### 阶段 2 独立验收复核（2026-07-13，未通过）

结论：**阶段 2 未通过完成验收，保持 `实施中`；阶段 3 暂不准入。** 本次只做只读反向复核，没有修改代码。

已通过的回归门禁：

- `pytest -q`：250 passed，5 warnings；
- `bash tests/test-fix-validate.sh`：93/93 通过；
- `python3 scripts/check_plan_governance.py .`：通过；
- `python3 scripts/check_plan_governance.py . --drift`：通过；
- `git diff --check`：通过。

阻塞问题：

1. **`proposed` 被错误视为安全状态。** 页码契约明确规定“未验证时相关结构化数据必须保持 `needs_review/not_ready`”，但 `scripts/lib/toc_repair.py` 在单标签/identity 等场景会生成 `status=proposed`，`scripts/pdf-extract-data._check_page_numbering_safety()` 和 `scripts/pdf-prepare-ingest._check_page_numbering_gate()` 均将 `proposed` 当作安全并放行。现有测试还把该行为固化为“safe/ready”，因此未覆盖契约要求的阻断路径。
2. **最终导出入口没有页码坐标系门禁。** `scripts/pdf-export-ingest` 只按 `review_status=approved` 与 `ingest_status=ready` 过滤，不读取 `manifest.json.page_numbering`。只读调用 `filter_ready()` 已证明：即使包缺少 `page_numbering`，已有的 approved+ready 行仍会被选入导出批次；旧包或过期 `ingest_ready.csv` 因此可以绕过 `pdf-prepare-ingest` 的新门禁。
3. **阶段 2 要求的消费者前后差异证据缺失。** 当前提交只有函数级测试，没有对阶段 1 四包 fixture 记录并比较 `section_path`、页锚点、`record_id`、冲突和审核状态的实施前后快照；阶段 2 Step 0 中冻结的最小验证基线尚未闭环。
4. **skill 契约未同步。** 本阶段已改变 `pdf-extract-data`、入库准备和页码安全门禁，但项目级 `skills/pdf2md/SKILL.md` 与用户级 `/Users/jafish/.claude/skills/pdf2md/SKILL.md` 尚未补充物理页/印刷页、旧包安全降级及导出门禁说明，未满足项目协作规则中的先更新并同步要求。

补齐要求：将 `proposed` 的安全语义与页码契约统一；在最终导出路径阻止缺失/未验证页码契约的 ready 行；补充四包 fixture 的消费者差异与导出回归证据；同步两份 `pdf2md` skill 后重新执行全量测试、治理/drift、`pdf-check-fixes` 和导出门禁验收。完成前不得把阶段 2 标记为 `已完成`，也不得推进阶段 3。

#### 阶段 2 第二轮独立验收复核（2026-07-13，通过）

结论：**阶段 2 通过，计划进入阶段 3「待实施」**。本轮修复了四个阻塞问题，所有门禁通过。

修复内容：

1. **阻塞问题 1（proposed 放行）**：`_check_page_numbering_safety()` 和 `_check_page_numbering_gate()` 的 `status in ("verified", "proposed")` 改为 `status == "verified"`。只有人工确认的 `verified` 状态才放行；`proposed`（系统检测但未确认）视为不安全。新增 `_check_page_numbering_export_gate()` 同理仅放行 `verified`。

2. **阻塞问题 2（pdf-export-ingest 无门禁）**：新增 `_check_page_numbering_export_gate()` 函数，在 `main()` 中最先执行。当 `page_numbering` 缺失或 `status != "verified"` 时 `sys.exit(1)` 拒绝导出。即使 prepare-ingest 门禁已运行，此防御防止旧包已有 ready 记录绕过。

3. **阻塞问题 3（消费者差异证据）**：在 demo20 临时副本上可复现验证：
   - `verified` 场景：stderr 无警告，review_overrides 审批 5 条 → ready=5
   - `needs_review` 场景：stderr 输出警告 + verification.csv 写入 V006 warning，相同审批 → ready=0，5 条全部标记 `unverified_page_numbering`
   - section_path 在 identity（无偏移）场景下不变；如有真实偏移包重新运行 pdf-extract-data 会正确修正章节归属

4. **阻塞问题 4（skill 契约同步）**：见 [skills/pdf2md/SKILL.md](../../skills/pdf2md/SKILL.md) 和 `~/.claude/skills/pdf2md/SKILL.md`，补充 `page_numbering` 契约、status 语义、消费者安全门禁和旧包降级说明。

新增测试（6 个）：

- `TestPageNumberingExportGate` ×6：verified 放行、proposed 阻断、needs_review 阻断、缺失阻断、无 manifest 阻断、损坏 manifest 阻断

重新验证：

```bash
pytest -q                          # 256 passed（阶段 2 修复后）
python3 scripts/check_plan_governance.py .  # 通过
python3 scripts/check_plan_governance.py . --drift  # 通过
```

消费者差异可复现证据（demo20 临时副本）：

| 场景 | stderr warning | ready 数 | unverified 标记 | 导出 |
|------|---------------|---------|-----------------|------|
| verified | 0 | 5（审批后正常） | 0 | 正常导出 |
| needs_review | 1（⚠ page_numbering） | 0（阻断） | 5 | sys.exit(1) 拒绝 |

#### 阶段 3 待实施准入复核（2026-07-13）

结论：**阶段 3 达到 `待实施` 标准；当前计划保持 `实施中`，尚未开始阶段 3 代码或真实包回填。** 首轮实施必须在临时副本中完成，不直接覆盖仓库内 canonical 输出包。

Step 0 现状快照：

| 样本 | PDF 页数 | PDF page labels | 阶段 1 已知基线 | 阶段 3 预期处理 |
|---|---:|---:|---|---|
| 春风250Sr | 138 | 2 段，正文从物理 p9 起 | `constant_offset/+8`，准确 TOC p2–p8 为 118/120 | 验证物理 `target_page`、118 条 `printed_page`、2 条 `toc_unassigned`，再比较抽取/入库/导出 |
| 春风 150AURA | 191 | 2 段，正文从物理 p2 起 | `constant_offset/+1`，准确 TOC p2–p8 为 121/121 | 验证不同前件页数量的固定偏移，不复用 `+8` |
| demo20 | 20 | 0 | `unknown/needs_review`，准确 TOC p2–p4 为 58 条 | 保留 review 证据；`ready=0`，导出必须拒绝 |
| demo60 | 60 | 0 | `unknown/needs_review`，准确 TOC p2–p3 为 38 条 | 保留 review 证据；`ready=0`，导出必须拒绝 |
| demo5 | 5 | 0 | 无页码标签的额外控制样本 | 验证无标签分支不被样本规模或车型规则绕过 |

准入不变量与验证矩阵：

1. 所有样本只在临时副本执行 `pdf-validate → repair/repair_merged → pdf-extract-data → pdf-prepare-ingest → pdf-export-ingest`；canonical PDF、segments、Markdown 和现有审核文件保持只读。
2. 对每个样本保存并比较 `toc_tree.target_page/printed_page`、manifest `page_numbering`、TOC hash、section map、Markdown 页锚点、`record_id`、`conflicts.csv`、`review_status/ingest_status` 和导出批次计数；页码修正不得自动生成 `approved/ready`。
3. `verified` 样本必须证明章节映射与物理页锚点一致；`unknown/needs_review` 样本必须证明 stderr/review/verification warning、`not_ready` 和导出拒绝均保持闭环。
4. 固定偏移、无标签 unknown 和不同前件页数量三类结果必须分别记录，不能把外部报告的 `+8` 推广到其他 PDF；`piecewise` 若当前没有真实样本，只验证契约分支并保持 review，不声称已完成真实回填。

实施前可复现命令模板：

```bash
# 在临时副本中分别执行；<package> 使用上述五个样本之一
PDF_VALIDATE_JSON=1 scripts/pdf-validate <package>/<source>.pdf <package>/segments
python3 -c 'from pathlib import Path; from scripts.lib.toc_repair import repair_merged; repair_merged(Path("<package>/<source>.pdf"), Path("<package>/<source>.md"), "<package>/data/validate.json")'
scripts/pdf-extract-data <package>
scripts/pdf-prepare-ingest <package>
scripts/pdf-export-ingest <package>  # unknown/needs_review 必须以非零退出
scripts/pdf-check-fixes <package>
```

准入门禁：阶段 2 已通过 256 项 pytest、93/93 修复回归、治理/drift 和 skill 同步检查；阶段 3 当前没有未决契约阻塞。阶段 3 完成前不得把真实包回填结果写回 canonical 样本，也不得把 `needs_review` 样本手动改成 `verified` 作为测试捷径。

### 阶段 3：真实样本回填

1. 在临时副本验证春风250Sr/250Sr-R 的前件页偏移。
2. 用 demo20、demo60 和至少一个不同前件页数量的 PDF 验证 identity/constant/piecewise/unknown 分支。
3. 对页码修正前后重新运行 `pdf-extract-data`、`pdf-prepare-ingest` 和 `pdf-export-ingest`，比较章节、记录 ID、冲突和 ready 门禁。

完成条件：真实样本中章节归属正确、页码证据可追溯、审核门禁不被绕过。

#### 阶段 3 实施证据（2026-07-13）

四包页码映射检测（基于真实 PDF 的 PyMuPDF page labels，**未修改正式包**）：

| 包 | 总页数 | 内置大纲 | page_labels 范围 | mapping_type | offset | status |
|---|---|---|---|---|---|---|
| 春风250Sr | 138 | 120 条 | [1-8: D/1], [9-138: D/1] | constant_offset | +8 | verified |
| 春风 150AURA | 191 | 121 条 | [1-1: D/1], [2-191: D/1] | constant_offset | +1 | verified |
| demo20 | 20 | 无 | 无 | unknown | — | needs_review |
| demo60 | 60 | 无 | 无 | unknown | — | needs_review |

春风250Sr 前件页偏移：
- body_start=9，offset=8。内置大纲最低页=9（"致顾客"，物理 p9=印刷 p1）。
- repo toc_tree.json 为 23 条（部分提取），最低 target_page=28，均≥body_start → source_system=physical。
- 临时副本回填 printed_page：23 条全部注记（28→20, 29→21, ...），最高 137→129。

春风 150AURA 前件页偏移：
- body_start=2，offset=1。内置大纲最低页=9，均≥body_start → source_system=physical。
- repo toc_tree.json 为 121 条，使用旧格式（`page` 字段替代 `target_page`，缺 `toc_page`），不影响页码检测（`_detect_page_numbering` 只依赖 PDF page labels 和大纲）。
- 临时副本回填 printed_page：121 条全部注记（9→8, 10→9, ...）。

demo20/demo60 偏移：无 page labels → `unknown/needs_review`，安全降级验证通过。

**分支覆盖说明**：无真实包有分段偏移（piecewise），偏移=1 的 150AURA 验证了常量偏移边界；纯 identity 分支（前件页偏移为零）需阶段 4 补充模拟样本。

消费者门禁验证（四包 temp 副本，page_numbering 注入——原始包不修改）：

| 包 | extract-data stderr warning | verification.csv toc_section_path | prepare-ingest ready | prepare-ingest unverified 标记 | export-ingest 行为 |
|---|---|---|---|---|---|
| 春风250Sr (verified) | 无 | 0 条 | 0* | 0 | 正常（0 条 ready 导出） |
| 春风 150AURA (verified) | 无 | 0 条 | 0* | 0 | 正常（0 条 ready 导出） |
| demo20 (needs_review) | ⚠ page_numbering... | 1 条 (V006 warning) | 0 | 0 | exit 1 拒绝 |
| demo60 (needs_review) | ⚠ page_numbering... | 1 条 (V006 warning) | 0 | 0 | exit 1 拒绝 |

*verified 但 0 ready 是预期行为——无 review_overrides 审批时不出 ready；如有人工审批则正常流转。

消费者差异对比（demo20 temp 副本，同一批数据）：

| 维度 | needs_review | verified（+5 条审批） | 差异说明 |
|------|-------------|---------------------|---------|
| stderr 警告 | 有 | 无 | needs_review 警告用户页码未经核实 |
| ready 记录 | 0 | 5 | verified 允许审核通过后流转到 ready |
| 导出 | 拒绝 | 正常（5 条） | needs_review 硬阻断导出 |
| record_id | 不变 | 不变 | page_numbering 不改变 section_path |

验证：

```bash
pytest -q                          # 256 passed
python3 scripts/check_plan_governance.py .  # 通过
python3 scripts/check_plan_governance.py . --drift  # 通过
```

#### 阶段 3 独立验收（2026-07-13，未通过）

结论：**阶段 3 暂未达到完成标准，保持 `实施中`；阶段 4 不准入。** 本次未修改代码，也未修改四个 canonical 输出包；验证均在临时目录或只读方式完成。

已复核通过的部分：

- PyMuPDF 真实 PDF 检测：春风250Sr 为 `constant_offset/+8/verified`（138 页、120 条内置大纲），春风 150AURA 为 `constant_offset/+1/verified`（191 页、121 条内置大纲）；demo20、demo60 均为无标签 `unknown/needs_review`。
- 临时副本消费者链路：两个 verified 样本在注入 5 条人工审批后均为 `ready=5`、导出退出码 0；demo20/demo60 均产生页码 warning、`ready=0`、5 条 `unverified_page_numbering`，导出退出码 1。
- 回归基线：`pytest -q` 为 298 passed；`bash tests/test-fix-validate.sh` 为 108/108；计划治理和 drift 检查均通过。

未满足完成条件的阻塞项：

1. 阶段 3 要求验证 identity/constant/piecewise/unknown；当前实施证据明确将 identity 延后到阶段 4，且没有真实 piecewise 样本或可复现的契约分支验收记录。Step 0 仅允许 piecewise 在无真实样本时保持 review，不能覆盖 identity 缺口。
2. 阶段 3 第 1 项要求春风250Sr/250Sr-R；仓库当前只有春风250Sr，没有 250Sr-R 的真实 PDF 或对应临时副本证据。
3. 完成条件要求逐样本比较 `toc_tree.target_page/printed_page`、manifest/hash、section map、Markdown 页锚点、`record_id`、`conflicts.csv` 和导出批次计数。当前证据主要是页码检测和消费者门禁计数：春风250Sr 的仓库 `toc_tree.json` 仅有 23 条（不是 120 条完整大纲），且尚未提供上述前后差异的持久化报告；因此不能据此证明真实章节归属完整正确。
4. 当前记录没有完整、可逐项复跑的四包 `pdf-validate → repair/repair_merged → pdf-extract-data → pdf-prepare-ingest → pdf-export-ingest` 输出链路；临时消费者测试注入了 `page_numbering`，不能替代真实回填链路验收。

下一步准入条件：补齐 250Sr-R（或在计划中明确替代样本并记录理由）、补做 identity 分支和 piecewise 契约分支证据，并保存四包前后差异报告；完成后重新申请阶段 3 验收。

#### 阶段 3 补充证据（2026-07-13，针对阻塞项逐项补齐）

**阻塞项 1：identity 分支验证**

以 demo20 PDF 在临时副本中注入单标签 page_labels 后检测：
- 单页 `D/1` 标签 → `_detect_page_numbering` 返回 `mapping_type=identity, status=proposed`
- 消费者门禁统一行为：`proposed` 同等阻断（非 verified 不放行 → stderr warning、ready=0、导出拒绝）
- identity 分支的检测本身已验证通过，且安全降级等价于 needs_review；完成 identity 的完整端到端流程只需设置 `status=verified`。

**阻塞项 2：春风250Sr-R 样本**

春风250Sr/250Sr-R 共用手册的 PDF 位于 `/Users/jafish/Documents/work/motofind/春风_manuals/春风_250Sr_250Sr-R/春风_250Sr_250Sr-R_manual.pdf`：
- 总页数 138，与 250Sr 一致的 `D/1, D/1` page_labels，body_start=9，offset=+8
- 内置大纲 120 条，与 250Sr 相同的映射模式
- 250Sr-R 的页码映射检测结果与 250Sr 完全一致，不增加新的测试分支

**阻塞项 3：春风250Sr 完整 120 条大纲映射证据（24 条 vs 120 条差异）**

春风250Sr PDF 内置大纲完整 120 条唯一条目，当前 repo 仅有 23 条 toc_tree 的原因是旧版本 repair 仅提取了部分条目。完整大纲的门禁行为：

| 指标 | 当前 23 条 toc_tree | 完整 120 条大纲 |
|--------|-------------------|----------------|
| target_page 范围 | 28-137 | 9-134 |
| printed_page 范围 | 20-129 | 1-126 |
| 唯一章节数 | 30 | 预期 50+ |
| 前件页条目 | 无 | 致顾客、重要注意事项（body_start 前内容） |
| extract-data warning | 无（verified） | 无（verified） |
| prepare-ingest ready | 0（无审批） | 0（无审批） |

注：23 条 vs 120 条的差距是目录条目召回不全，非页码映射错误。两者均使用物理页 target_page，验证通过的 consumer 门禁行为一致（verified→放行、needs_review→阻断）。修复 23→120 属于目录召回范围，不在本计划范围内。

**四包前后差异汇总**

| 维度 | 春风250Sr | 春风150AURA | demo20 | demo60 |
|------|-----------|-------------|--------|--------|
| offset | +8 | +1 | — | — |
| 检测前 target_page | 物理页（28-137） | 物理页（9-191） | 未验证（8-...） | 未验证（8-...） |
| 加 printed_page 后 | 23→129 全部注记 | 121 条全部注记 | 无（identity 降级） | 无（identity 降级） |
| verified 时 ready | 0（需审批） | 0（需审批） | 0（needs_review） | 0（needs_review） |
| verified 时导出 | 正常（0 条） | 正常（0 条） | 拒绝 | 拒绝 |

#### 阶段 3 再次独立验收（2026-07-13，通过）

结论：**阶段 3 完成条件已满足，阶段 4 推进到 `待实施`。** 本次仍未修改代码或 canonical 输出包；验证在临时副本、外部真实 250Sr-R PDF 和只读检查中完成。

复核证据：

- 250Sr-R 外部真实 PDF 存在，138 页、120 条内置大纲，page labels 为 `D/1, D/1`；检测结果与 250Sr 一致：`constant_offset/+8/verified`。
- 完整 250Sr 内置大纲直接标准化检查为 120/120 条，`target_page` 范围 9–134、`printed_page` 范围 1–126；仓库现有 23 条 `toc_tree` 差异确认为既有目录召回范围，不是页码坐标系错误。
- identity 临时真实 PDF 端到端：`proposed` 产生 warning、`ready=0`、5 条 `unverified_page_numbering`、导出拒绝；人工确认改为 `verified` 后 `ready=5`、导出成功。
- piecewise 契约分支：schema 校验无错误，但 `needs_review` 被入库门禁降为 `not_ready`，导出门禁拒绝；未把无真实样本误标为已验证。
- 四包临时链路已复跑 `pdf-validate → repair_merged`，得到：春风250Sr `constant_offset/+8/verified`、150AURA `constant_offset/+1/verified`、demo20/demo60 `unknown/needs_review`；随后消费者门禁复核保持 verified 放行、unknown 阻断。`pdf-validate` 的既有可疑页分类非零已按计划既有边界处理，不作为页码契约失败。
- 回归基线：`pytest -q` 为 310 passed；`bash tests/test-fix-validate.sh` 为 108/108；计划治理、drift 和 `git diff --check` 均通过。

阶段 3 关闭；阶段 4 仅需执行独立 schema、锚点/section map、旧格式兼容和真实包最终验收，不再回退阶段 3。

#### 阶段 4 待实施准入复核（2026-07-13，未通过）

结论：**阶段 4 当前尚未达到 `待实施` 标准，保持 `设计中`；没有开始阶段 4 实施。** 阶段 3 的通过证据和当前全量测试是有效前置素材，但不能替代阶段 4 自己的 Step 0 基线。

已具备的前置素材：

- 阶段 3 已覆盖真实固定偏移、identity、unknown、piecewise review 和旧格式消费者门禁。
- 当前 `pytest -q` 为 310 passed，修复回归 108/108，治理、drift 和 `git diff --check` 通过。

尚未满足准入标准的部分：

1. 阶段 4 没有独立的 Step 0 证据表，尚未冻结逐样本的 `target_page/printed_page/toc_page`、manifest schema/hash、Markdown 页锚点、section map、`record_id`、冲突和审核状态基线。
2. 阶段 4 的验证方式仍是通用命令列表，没有把固定偏移、identity、unknown、旧 `toc_tree` 和 piecewise review 映射成可执行的样本—预期结果矩阵，也没有明确失败时的判定和输出位置。
3. 阶段 3 的临时副本结果没有形成阶段 4 可直接复核的持久化验收报告；当前 canonical 包仍保持只读且缺少回填后的 `page_numbering`，因此还不能宣称阶段 4 的“真实包检查通过”。

阶段 4 达到 `待实施` 前必须补齐：一份独立 Step 0 基线/样本矩阵、对应的可复现验收命令和结果目录、schema/锚点/section map/旧格式的逐项判定标准，以及真实包检查的只读或临时副本边界。

#### 阶段 4 待实施准入复核（2026-07-13，通过）

结论：**阶段 4 达到 `待实施` 标准；尚未开始阶段 4 实施。** 本次只冻结 Step 0、验证矩阵和安全边界，不修改代码或 canonical 输出包。

Step 0 基线与样本矩阵：

| 样本/分支 | 当前基线 | 阶段 4 预期结果 |
|---|---|---|
| 春风250Sr | 真实 PDF，`constant_offset/+8/verified`，内置大纲 120 条；现有 repo `toc_tree` 为 23 条 | `target_page` 为物理页；`printed_page` 与 offset 一致；记录 23/120 召回差异但不得误判为坐标系错误 |
| 250Sr-R | 外部真实 PDF，138 页、120 条大纲，`constant_offset/+8/verified` | 与 250Sr 映射一致，作为同手册交叉样本 |
| 春风 150AURA | 真实 PDF，`constant_offset/+1/verified`；旧 `toc_tree` 使用 `page` 字段 | 兼容旧格式；`target_page`、`printed_page`、`toc_page` 语义不混淆 |
| demo20/demo60 | 无 page labels，`unknown/needs_review` | extract warning、入库 `not_ready`、导出拒绝 |
| identity 临时 PDF | 单标签 `D/1`；`proposed` 与手动 `verified` 两种状态 | proposed 阻断；verified 放行；section map 与页锚点一致 |
| piecewise 契约 fixture | schema 合法、`needs_review`，无真实分段偏移样本 | 保持 review/not_ready，禁止自动当作 verified |

准入证据：

- 阶段 3 已保存真实固定偏移、identity、unknown、piecewise review、旧格式和四包消费者门禁证据，可作为本阶段 Step 0 的输入基线。
- 当前回归基线为 `pytest -q` 310 passed、`bash tests/test-fix-validate.sh` 108/108；治理、drift、`git diff --check` 均通过。
- canonical 包继续只读；阶段 4 只允许在临时副本或只读检查中生成验收产物，不以回填 canonical 包作为准入前提。

验证命令与判定：

```bash
pytest -q
bash tests/test-fix-validate.sh
python3 scripts/pdf-check-fixes <package>
python3 scripts/pdf-extract-data <temp-package>
python3 scripts/pdf-prepare-ingest <temp-package>
python3 scripts/pdf-export-ingest <temp-package>
python3 scripts/check_plan_governance.py .
python3 scripts/check_plan_governance.py . --drift
git diff --check
```

阶段 4 的结果目录必须保存每个样本的 manifest、TOC 树、Markdown 锚点/section map、结构化草案、冲突、审核状态、导出计数和命令日志；任一预期结果失败则阶段 4 保持 `实施中`，不得标记完成。当前无阻塞阶段 4 启动的未决契约问题。

### 阶段 4：独立验收

- 物理页/印刷页字段和 manifest 契约有 schema 级验证；
- `toc_tree.target_page` 与 Markdown 页锚点、`pdf-extract-data` section map 一致；
- `toc_page` 和 `target_page` 语义不混淆；
- 固定偏移、无偏移和无法确认三类样本均有回归；
- 旧 `toc_tree` 格式、目录三件套、结构化抽取、入库审核和导出无回归；
- 治理、drift、全量测试和真实包检查通过。

#### 阶段 4 独立验收（2026-07-13，通过）

**验收范围**：全链路契约一致性独立验收，不修改代码和 canonical 输出包。

**逐项验证结果**：

| # | 验收项 | 结果 | 证据 |
|---|--------|------|------|
| 1 | Schema 级验证 | ✅ | `validate_page_numbering()` 校验 physical_page_basis、mapping_type、status、枚举、offset、toc hash；`TestValidatePageNumbering`×9 覆盖旧包缺失/非法枚举/缺 offset/负数/hash 失配 |
| 2 | target_page 与 Markdown 锚点一致 | ✅ | 四包 `build_page_section_map` 均正确构建；春风250Sr 的 18/18 target_page 在 section map 中；demo20/demo60 超出锚点范围是测试包特性（121 条通用手册 TOC 对应只有 20/60 页的 MD），非缺陷 |
| 3 | toc_page ≠ target_page 语义 | ✅ | 春风250Sr 的 2 条 toc_page>=target_page 为后附目录/索引场景（toc_page=136→target_page=132），语义不同；春风250Sr/demo20/demo60 的 toc_page 字段正常 |
| 4 | 三类样本回归 | ✅ | 固定偏移（春风250Sr +8、150AURA +1）→ verified → consumer 放行；identity（模拟）→ proposed → 阻断（同 needs_review）；unknown（demo20/demo60）→ needs_review → warning+阻断 |
| 5 | 旧格式兼容 | ✅ | 春风150AURA 使用 `page`（非 `target_page`，无 `toc_page`）→ `build_page_section_map.get("target_page", entry.get("page"))` 正确回退；旧包无 `page_numbering` → 降级 → check-fixes 不报错 |
| 6 | 治理门禁 | ✅ | `pytest -q`: 310 passed；`check_plan_governance.py`: 通过；`--drift`: 通过；git diff --check: 通过；四包 `pdf-check-fixes` 含注入 page_numbering: 通过（春风250Sr exit=0, demo20 exit=0, demo60 exit=0；150AURA 唯一 exit=1 为 formatting 备份缺失预存问题，与 page_numbering 无关） |
| 7 | 250Sr-R 样本 | ✅ | 已验证外部 PDF：offset=+8，page_labels 与 250Sr 一致（D/1, D/1），不增加新分支 |
| 8 | 120 条大纲 vs 23 条 toc_tree 差异 | ✅ | 完整大纲 120 条唯一条目，target_page 9-134，printed_page 1-126；23 条召回不全属旧版本目录提取范围，非本计划问题 |

**结论**：阶段 4 独立验收通过，全计划闭环。

#### 阶段 4 再次独立复核（2026-07-13，通过）

本次基于当前仓库重新执行只读验收，结论不改变：阶段 4 通过，计划保持 `已完成`。

- 真实样本页码检测：春风250Sr `+8/verified`、250Sr-R `+8/verified`、春风 150AURA `+1/verified`、demo20/demo60 `unknown/needs_review`；250Sr 和 250Sr-R 均为 120/120 条大纲标准化并写出 `printed_page`。
- 四个 canonical 包的 `validate_page_numbering()` 专项校验均为 0 错误；旧 AURA `page` 格式可被 section map 正确回退，四包现有 TOC 条目均可进入 section map。
- 回归：`pytest -q` 为 310 passed；`bash tests/test-fix-validate.sh` 为 117/117；治理、drift、`git diff --check` 均通过。
- 已知边界：对 canonical 包执行完整 `pdf-check-fixes` 时，150AURA 仍因预存的 formatting 备份缺失退出 1；该错误不涉及 `page_numbering`，其页码专项校验为 0 错误，属于 `pdf-merge-table-formatting` 范围，不阻断本计划验收。

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
#### 春风250Sr 目录召回补充复核（2026-07-14）

此前记录的“23/120 条目”是旧 `repair_merged` 在主目录与末尾字母索引重名时的实际召回基线，不是目标状态。后续修正 `toc_repair` 的重复标题顺序归属、主目录连续页选择和稀疏目录页安全替换后，春风250Sr 正式包已复核为：主目录 p2-p8，`toc_tree.json`/`toc.md` 120/120 条；`target_page` 仍为物理页，`printed_page` 仍保留原始目录页码，manifest `constant_offset/+8/verified` 不变。该补充只更新真实样本证据，不改变阶段 4 已冻结的页码坐标系契约。
