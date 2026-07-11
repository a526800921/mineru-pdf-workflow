# 缺陷单：原生表格检测器漏报——整表头行丢失 / 顶部列头缺失

- 状态：待处理（仅记录，未修复）
- 发现日期：2026-07-11
- 样本：demo20.pdf 第 14 页（参数规格表，顶部为车型列头）
- 归属范围：`table-text-omission-detection` 检测器**覆盖缺口**（`native_table_text_missing` 假阴性）
- 相关：[table-text-omission-detection 计划](../plans/table-text-omission-detection.md)、[toc-page-full-duplication](toc-page-full-duplication.md)

## 现象

PDF 第 14 页参数表顶部有车型列头 `150 AURA`、`CF150T-32`、`CF150T-32A`，但 MinerU 单页输出把整行丢失，段 md 表格**第一行为空单元格**：

```html
<table><tr><td></td><td></td></tr><tr><td colspan="2">性能</td></tr>...
```

`native_table_text_missing` 检测器对该页返回 `[]`（无信号），demo20 run 中 p14 判为 `pass`——**漏报**。这与 p16「百公里综合油耗」同属「PDF 表格区域有、HTML 丢了」的类别，但检测器只抓到了 p16、漏掉了 p14。

## 核实证据

| 事实 | 证据 |
|---|---|
| PDF 第 14 页原生文本含型号 | `150 AURA`、`CF150T-32`、`CF150T-32A` |
| p14 段 md 丢失型号 | 三者各出现 0 次；表格首行 `<tr><td></td><td></td></tr>` |
| 检测器结果 | `signals=[]`，`native_table_missing=0` |
| 型号在 `html_all`（HTML 单元格文本集） | 均 False（已被丢弃） |
| 型号视觉行是否有词命中 `html_all` | False（整行无锚） |

型号坐标（页宽 556）——位于**页顶、右侧**，是列头非左列行标：

| 文字 | x0 | x0/页宽 | y0 |
|---|---|---|---|
| CF150T-32 | 265 | 48% | 72 |
| 150 AURA | 360 | 65% | 59 |
| CF150T-32A | 410 | 74% | 72 |

## 根因

检测器（`detect_native_table_text_omission`）的设计假设：一个表格行**至少有一个单元格在 HTML 中幸存**，作为"锚"确认该视觉行是表格行，再检查其**左列**标签是否缺失。

p14 两点都不满足：

1. **整表头行被丢**：型号词无一进入 `html_all` → 该视觉行 `has_html_match=False` → 检测器在 `if not has_html_match: continue` 处**跳过整行**。
2. **型号是顶部列头，非左列行标**：型号 x0 在 48%–74%（右侧），检测器只收集 `x0 < split_x` 的左列候选。

对比 p16 为何命中：`百公里综合油耗` 的**值 `≤2.7L` 在 HTML 中幸存** → 该行有锚 → 才进入左列标签缺失检查。

## 可复现基线

```bash
python3 - <<'PY'
import sys; sys.path.insert(0, "scripts")
from lib.page_quality import detect_native_table_text_omission
import fitz

doc = fitz.open("pdf/demo20/demo20.pdf")
words = doc[13].get_text("words")               # 第14页
w, h = doc[13].rect.width, doc[13].rect.height
native = doc[13].get_text()
doc.close()
md = open("pdf/demo20/segments/p0014-0014/demo20/hybrid_auto/demo20.md").read()

# 红基线：PDF 有型号，md 丢失，检测器却无信号
assert "150 AURA" in native and "CF150T-32A" in native
assert "150 AURA" not in md and "CF150T-32A" not in md
sig, met = detect_native_table_text_omission(md, words, w, h)
assert sig == [] and met["native_table_missing"] == 0, "复现：检测器漏报整表头行"
print("red baseline: 整表头行丢失，检测器假阴性已复现")
PY
```

## 影响

- 检测器只覆盖「左列行标 + 值幸存」一种子模式，漏掉「整表头行丢失」和「顶部列头/右侧文字缺失」。
- 直接影响 `table-text-omission-detection` 计划的完整性：同一份 demo20 上即存在检测器抓不到的同类丢失，计划不应视为对该目标完全闭环。
- 下游：p14 参数表缺车型归属，若用于结构化抽取会丢失「参数属于哪个车型」的关键上下文。

## 关键文件

| 来源 | 路径 |
|---|---|
| 丢失型号的段 md（首行空） | `pdf/demo20/segments/p0014-0014/demo20/hybrid_auto/demo20.md` |
| 检测器实现 | `scripts/lib/page_quality.py`（`detect_native_table_text_omission`） |
| 源 PDF | `pdf/demo20/demo20.pdf`（第 14 页） |

## 待决策（候选方案，未实施）

1. **空表头行探针**：当 HTML 表格首行全为空单元格（`<tr><td></td>...`），而表格区域顶部原生文本非空时，直接产生遗漏信号，绕过"需锚单元格"的前提。
2. **顶部列头比对**：除左列行标外，增加对表格区域**顶部行**原生文字与 HTML 首行单元格的比对，支持右侧/居中列头。
3. **无锚行兜底**：对表格 bbox 内、但整行无 HTML 匹配的视觉行，按"疑似整行丢失"标记 review，而非静默跳过。
4. **维持现状**：接受该类假阴性，仅靠人工复核发现（当前行为）。

选定方案前应先固定本缺陷单为 Step 0 红基线；若采纳，宜作为 `table-text-omission-detection` 的后续阶段闭环，并补 p14 回归 fixture。
