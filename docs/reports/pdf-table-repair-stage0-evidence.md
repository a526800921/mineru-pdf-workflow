# pdf-table-repair 阶段 0 准入证据

日期：2026-07-13

## 结论

阶段 0 准入通过，`pdf-table-repair` 可推进到“待实施”。下一阶段只实现页级 draft 生成和安全应用，不提前修改真实包或 canonical Markdown。

## 最小样本复核

`pdf-table-audit` 的真实候选已覆盖阶段 0 约定的修复类型：

| 样本 | 当前证据 |
|---|---|
| 春风250Sr p34 | `春风250Sr_p0034`，原生文字缺失候选 |
| demo60 p47/p48 | `demo60_p0047`、`demo60_p0048`，8192 空列/结构异常候选 |
| 春风250Sr p73 | `春风250Sr_p0073`，原生文字缺失候选 |
| 春风250Sr p77 | `春风250Sr_p0077`，原生文字缺失候选 |
| 春风250Sr p87/p90 | `春风250Sr_p0087`、`春风250Sr_p0090`，8192 空列候选 |

## 最小 draft 复现

从真实包 `pdf/春风250Sr/data/table_candidates.jsonl` 的 `春风250Sr_p0094` 候选生成临时 draft `/tmp/pdf-table-repair-stage0-draft.json`。该 draft 未写入项目目录，关键结果如下：

```json
{
  "fix_id": "draft-春风250Sr-p0094",
  "status": "proposed",
  "needs_human": true,
  "pages": [94],
  "page_anchor": "<!-- pages 94-94 -->",
  "table_id": "春风250Sr_p0094",
  "source_segment": "p0094-0094",
  "before_html_bytes": 147120,
  "draft_html_bytes": 1096,
  "pdf_text_bytes": 724,
  "source_pdf_sha256": "b7fa3994722df752a212892300fc9e3329071c6f7063d5426aedfa4ac273c991",
  "source_markdown_sha256": "8670a37522b2fc29707a7055012080e57dad37850127a191c2492e86897c1e73"
}
```

复核结果：canonical Markdown 的 hash 仍为 `8670a37522b2fc29707a7055012080e57dad37850127a191c2492e86897c1e73`，manifest 未被临时 draft 生成过程修改。

## 阶段 0 冻结决策

- `pdf-table-fix` 继续负责异常发现和证据候选；repair 不重复实现扫描逻辑。
- `pdf-table-repair` 的 draft 初始状态固定为 `status=proposed`、`needs_human=true`；未人工确认不得写回 Markdown。
- draft 必须携带 `fix_id`、`table_id`、`pages`、`page_anchor`、来源 PDF/Markdown hash、segment、`before_html`、`draft_html`、`pdf_text` 和 alignment 候选。
- VLM 固定为 `qwen3-vl-8b`（ModelPad 9999、VLM 9005），只提供文字/数字/警告等视觉证据，不决定列数、表头、`rowspan`、`colspan` 或跨页归属。
- 确认后的应用复用 `pdf-apply-fixes` 页锚点边界；Markdown、`manual_fixes.jsonl` 和 manifest 必须作为一个可回滚单元更新。
- p47/p48 只生成共享 `table_id` 候选，不在 repair 阶段物理合并 Markdown。

## 待实施边界

阶段 1 需要补齐：指定页参数、draft 生成器、alignment 候选字段、预期命中次数校验和 draft 失败回滚测试。阶段 0 不修改代码、真实 PDF、segments 或 canonical Markdown。
