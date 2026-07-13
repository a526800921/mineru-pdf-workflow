# 计划：TOC target_page 页码坐标系修复

## 计划状态

- 状态：实施中
- 当前阶段：阶段 2 已完成 → 阶段 3：真实样本回填（待实施）
- 最后更新：2026-07-13

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
- 新增 `_check_page_numbering_safety(manifest)` 函数（line 222），检查 `page_numbering.status` 返回安全评估 `{safe, status, warning}`；`verified/proposed` → safe=True，`needs_review/missing` → safe=False + warning
- `main()` 中加载 `toc_tree` 前调用安全评估，stderr 输出警告但保留 TOC section_map（最佳信源）
- `generate_verification()` 新增 `toc_warning` 参数，当页码坐标系未验证时写入 `toc_section_path` warning 检查

**`scripts/pdf-prepare-ingest`**：
- 新增 `_check_page_numbering_gate(pkg, rows)` 函数，在 `compute_ingest_status()` 之后运行，作为最终安全门禁
- 当 `page_numbering.status == "needs_review"` 或缺失时：所有 `ready` 记录降级为 `not_ready`，notes 追加 `unverified_page_numbering` 标记
- `verified/proposed` 时放行；`superseded/suppressed/skipped` 终态不被覆盖

**`scripts/pdf-check-fixes`**：
- 新增 `validate_page_numbering(manifest, pkg_dir)` 函数，校验：块存在性、必含字段、mapping_type/status 合法值、constant_offset 需 offset≥0、toc 文件 hash 一致性
- 旧包缺失 `page_numbering` 时不报 error（安全降级兼容）
- 在 `main()` 中 `validate_manual_fix_candidate_refs` 之后注册

**无需修改文件**（均使用物理页码或不消费 TOC 数据）：`pdf-read-page`、`pdf-table-fix`、`pdf-table-repair`（不存在）、`pdf-export-ingest`、`toc_repair.py`、`review_report.py`

**测试**：

| 测试类 | 测试数 | 覆盖内容 |
|--------|--------|----------|
| `TestCheckPageNumberingSafety` | 6 | verified/proposed/needs_review/missing/非 dict 块 |
| `TestPageNumberingGate` | 7 | verified 放行、proposed 放行、needs_review 阻断、缺失阻断、skipped 不覆盖、无 manifest、损坏 manifest |
| `TestValidatePageNumbering` | 9 | 合法 constant_offset/identity、旧包缺失、非法 mapping_type/status、缺 offset、负数 offset、缺必含字段、toc_tree/toc.md hash 失配 |

验证：

```bash
pytest -q                          # 250 passed（原 227 + 新增 23）
python3 scripts/check_plan_governance.py .  # 通过
python3 scripts/check_plan_governance.py . --drift  # 通过
```

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
