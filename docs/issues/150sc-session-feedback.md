# 150Sc 交付会话问题复盘与 pdf2md 流程改进建议

> 来源：`春风_150Sc` 最终下游交付（阶段 0～9）会话实录。
> 日期：2026-08-11
> 范围：本文记录本次会话实际踩到的问题、根因，以及 pdf2md 流程/SKILL 中可改进的设计点。供流程迭代参考。

---

## 一、本次实际遇到的问题（按类型）

### 1. 表号体系双轨，排查时反复误判

**现象**：覆盖审计的 `source_block_id` 用 canonical **源码表号**，而 draft/ingest_ready 的 `table_id` 用抽取器**候选表号**（跳过单行 HTML 表后重新计数）。两者常常差一。

**实例**：处理 p158 扭矩表时，先把 `html_table:84`（实际是 p156 故障表）误当成扭矩表排查，最后才发现扭矩表在抽取器里是 `html_table:85`、在覆盖审计里是 `html_table:85`，但 draft 候选 `table_id` 又不同。两套编号全靠心算映射，极易踩坑。

**根因**：`source_to_candidate_table_ids` 的映射存在，但对使用者不透明——读 CSV 时看到的编号与读 canonical/覆盖审计时看到的编号不是同一套，且没有任何显式标注说明"这是候选表号"。

### 2. `header_rows=1` 吞掉第一行业务数据

**现象**：电器装置表 `html_table:9` 在 `extraction_overrides.json` 配置了 `header_rows=1`，但该表第一行「蓄电池 | 12V / 7Ah」其实是**业务数据**，被当成表头跳过。覆盖审计随后把该行标为 `non_business`（"明确不生成业务候选"）。

**暴露**：直到用户逐行检查 CSV 才发现"38 行这里少了一行蓄电池"。抽取配置错误在自动化审计中无法自查——审计只是顺着配置把缺行标成 non_business，等于把配置错误固化了。

### 3. pair_groups 拆分引发全链连锁重建

**现象**：整车通用扭矩表 5 行拆成 10 条（`row_index` 从 `1` 变 `1.1`/`1.2`），导致：
- `candidate_id` 全变（location 含 `row_index`）
- 旧审核决定全部失效（candidate_id 不匹配）
- `parent_context_overrides.csv` 旧条目全部失效
- 必须删旧决定 → 重算新 cid → 逐条写新决定

**另一个问题**：pair_groups 生成的候选默认 `status=needs_review`，而**状态门禁不允许 LLM 直接 approved needs_review 候选**（LLM 只能 evidence_exact 从 draft 批，或 user_confirmed）。结果 10 条机械拆分项全部被迫走 user_confirmed——用户逐条确认没有业务意义。

### 4. parent_key 是重灾区

本次会话最痛的部分，具体四个子问题：

**4a. 用户在最终产物上的修改会被重跑覆盖**
用户在 `ingest_ready.csv` 上手动把 parent_key 改成正确值（智能钥匙 7 条、左手把开关 8 条），但 `pdf-prepare-ingest` 每次从 draft 全量重建，用户改动全部丢失。没有"保留用户已改字段"的机制。

**4b. enrich 只补空、拒绝覆盖已有非空值**
想把左手把开关的数字 parent_key（2/3/4/5）改成「左手把开关」，`pdf-enrich-parent-context` 直接报错"覆盖文件试图覆盖已有 parent_key"。必须先手工清空 ingest_ready 中对应行，再跑 enrich。两步操作极易遗漏，且清空动作本身没有保护。

**4c. 改 draft 的 parent_key 会改变 candidate_id，连锁破坏一切**
`compute_candidate_id` 的 location 包含 `parent_key`。draft 里把 parent_key 从数字改成「左手把开关」后，candidate_id 变化 → 所有审核决定、overrides 失效。一个字段的微调演变成全链重建。

**4d. enrich 对段落候选（paragraph）不生效**
火花塞 3 条是冒号行段落（`colon_line`），不是表格候选。`section_path_fallback` 只处理表格，parent_key 补不上，最后只能手工加 override 指定「火花塞」。

### 5. 同页同名 section 的 TOC 覆盖缺陷

**现象**：p129 同时有「火花塞」（`## 火花塞`，2615 行起）和「怠速」（`## 怠速`，2627 行起）两个同级子节。toc_tree 中两者都指向 `target_page=129`。`build_page_section_map` 按 target_page 范围覆盖，**后写的「怠速」把整页 p129 吞掉**，火花塞 3 条（2615-2625 行）全部错误归属「发动机总成 / 怠速」。

**暴露**：直到用户追问"292-294 这个怠速是怎么来的"才发现归属错误。

**根因**：section 归属是纯页级映射（page → path），不支持行级边界。同页多子节时必然出错。

### 6. 局部修正被迫走临时副本全量重抽

**现象**：为拆分一张扭矩表，需复制整包到临时目录 → `--force-rebuild` 重抽 → 取回 diff → 再迁移候选。重跑保护是"全有或全无"：
- 检测到任一产物（review_decisions/ingest_ready/...）就整体拒绝
- 要么 `--force-rebuild` 全量重建

没有"单表重抽"或"单候选修正"的细粒度入口。

---

## 二、pdf2md 流程设计不合理处（按优先级）

### P0 · 身份哈希耦合了易变业务字段（最根本问题）

`compute_candidate_id` 的 location 包含 `section_path`、`parent_key`、`key_role` 等**业务字段**。业务字段不该参与身份：
- 改一个 parent_key → candidate_id 变 → 审核决定、overrides 全部失效
- 任何业务层面的修正（parent_key、拆分、归属）都触发全链身份重建

**建议**：身份只锁来源位置（source_pdf/table/row_index/page），内容变化由 `candidate_hash` 阻断过期决定即可。这能大幅降低业务修正成本。

### P0 · 审核绑定 hash，缺少"修订/超驰"低成本通道

review_decisions 绑定 `candidate_hash`，内容一改全部失效。防篡改有价值，但没有"用户明确修订"的低成本通道。蓄电池补充、火花塞归属修正是低风险修订，却都要删旧决定 → 重算 → 写新决定。

**建议**：支持 `review_status=superseded` 或"修订版本"语义，让用户确认的修正不必摧毁既有审计链。

### P1 · 状态门禁不对称（LLM 不能批 needs_review）

pair_groups 拆分默认 `needs_review`，而 LLM 只能从 draft 用 evidence_exact 批准，不能推进 needs_review。规则明确的机械拆分（扭矩表每行两组）应允许 LLM 批量确认。

**建议**：为"规则明确、证据充分"的机械拆分提供 LLM 批量批准通道，仅在真正有歧义时升级用户。

### P1 · draft 是唯一事实源，用户对最终产物的修改没有回流通道

prepare-ingest 每次从 draft 全量重建 ingest_ready，覆盖用户对最终文件的任何手动修正。**最终产物上的值应是权威的**，draft 只是候选。

**建议**：对 parent_key 等业务字段，最终 ingest_ready 上的值应作为权威保留；重跑时若 draft 与新值冲突，应提示而非静默覆盖。

### P1 · enrich 的"只补空"与"改已有值"需求冲突

想改已有 parent_key 必须手工清空两处（draft + ingest_ready），是设计缺口。

**建议**：支持"用户显式确认的覆盖"——overrides 带 `force` 或 `user_confirmed` 标记时可覆盖已有非空值，而不是一律报错。

### P2 · 重跑保护粒度太粗

要么整体拒绝，要么全量重建。缺少"单表重抽""单候选修正"的细粒度操作。

**建议**：增加按 table_id / candidate_id 的局部重抽与修正入口。

### P2 · 同页 section 归属缺行级边界

纯页级映射（page → path）在同页多子节时必然出错。

**建议**：支持按 canonical 标题行号的行级 section 边界；当同页多个 depth 相同的子节指向同一 target_page 时，应报警或回退到行号归属。

### P3 · 表号双轨对使用者不透明

`source_to_candidate_table_ids` 的映射存在但对使用者不可见。

**建议**：draft/ingest_ready 中标注"候选表号"，或在报告中输出源码表号 ↔ 候选表号对照表，避免排查时心算映射。

---

## 三、一句话总结

核心不合理在于**身份与业务值耦合**：把"来源位置"和"业务语义"绑在同一个 hash 上，导致任何业务层面的修正（parent_key、拆分、归属）都触发全链身份重建。方向应该是：**身份只锁来源位置，业务值允许低成本修订并保留审计痕迹**。
