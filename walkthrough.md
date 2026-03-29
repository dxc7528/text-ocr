# Anki Card Generator — 完成总结

## 架构概览

```
输入 .md → Parser (Python) → ┬─ Formula Processor (Python) ─→ Validator (Python) → TSV
                              └─ Text Processor (Gemini API) ─┘
```

## 测试结果：配当割引モデル.md

✅ 共生成 **25 张卡片**：7 张 Formula（Python）+ 18 张 Text（LLM）

---

### Formula 卡片（Python 生成）：所有历史问题已修复

| 卡片 | 验证结果 |
|------|---------|
| `$$P_0 = \frac{{{c1::D}}}{{{c2::k}}}$$` | ✅ Multi-cloze (D, k), 无 hint, LaTeX 保持 |
| `$$P_0 = \frac{{{c1::D_1}}}{{{c2::k}}-{{c3::g}}}$$` | ✅ 3 个独立 cloze |
| `$$k = {{c1::\beta_i}}({{c2::E[R_M]}} - {{c3::R_f}}) + {{c3::R_f}}$$` | ✅ 3 个变量, R_f 同编号 c3 |
| `$$g = {{c1::ROE}} \times {{c2::内部留保率}}$$` | ✅ 链式等式拆分-卡1 |
| `$$g = {{c1::ROE}} \times (1 - {{c2::配当性向}})$$` | ✅ 链式等式拆分-卡2 |
| `$$D_1 = {{c1::D_0}} \times (1+{{c2::g}})$$` | ✅ 从留意点区提取 |
| `$$g = {{c1::ROE}} \times \text{{{c2::内部留保率}}}$$` | ✅ \text{} 处理正确 |

### 与之前的 LLM-only 输出对比

| 问题 | 之前 (LLM-only) | 现在 (Hybrid) |
|------|-----------------|--------------|
| **Hint 泄露** | `{{c1::k::割引率}}` ❌ | `{{c1::k}}` ✅ |
| **Multi-cloze 遗漏** | CAPM 只有 β 一个 cloze ❌ | β, E[Rₘ], Rf 三个 ✅ |
| **Anti-hint** | `{{c1::k>g::条件}}（要求収益率＞成長率）` ❌ | `{{c1::$k > g$（要求収益率が成長率を上回る）}}` ✅ |
| **公式转文字** | 有些公式被改为散文 ❌ | 100% LaTeX 保持 ✅ |
| **公式遗漏** | 遗漏了 $D_1 = D_0(1+g)$ ❌ | 从留意点区自动提取 ✅ |

### Text 卡片（LLM 生成）：关键概念覆盖完善

| # | 示例卡片 | 类型 |
|---|---------|------|
| 8 | 定額配当モデルは、将来の配当金 $D$ が永久に{{c1::一定である}}と仮定する | Definition |
| 14 | CAPMの要素: {{c1::リスクフリーレート}}, {{c2::市場リスクプレミアム}}, {{c3::ベータ値}} | Parallel |
| 21 | 定率成長モデルが成立するためには必ず{{c1::$k > g$（要求収益率が成長率を上回る）}} | Definition |
| 23 | ROEの分解: {{c1::売上高純利益率}} × {{c2::総資産回転率}} × {{c3::財務レバレッジ}} | Parallel |
| 24 | CMA第2次試験で頻出の「{{c1::2段階成長モデル}}」 | Definition |
| 25 | 多段階成長モデル: {{c1::各期間の配当の現在価値}} → {{c2::ターミナルバリュー}}合算 | Sequential |

> ✅ LLM 生成的卡片也遵守了无 hint 规则、anti-hint 规则、one-card-one-fact 规则。

---

## 7 条规则验证

| # | 规则 | 状态 |
|---|------|------|
| 1 | 公式保持 LaTeX 格式 | ✅ Python 确保 |
| 2 | 等号后多 cloze | ✅ Python 确保 |
| 3 | 所有公式无遗漏 | ✅ 从 Point + 解説 + 留意点 三区都提取 |
| 4 | 防泄露（无 hint） | ✅ Python 不加 hint + Validator 自动删除 |
| 5 | 網羅性 | ✅ LLM 覆盖定义、同义词、考试要点 |
| 6 | 一卡一事 | ✅ LLM Parallel 卡片用独立 cN |
| 7 | 禁止混合拼接 | ✅ Python 确保纯 LaTeX |

---

## 创建的文件

| 文件 | 说明 |
|------|------|
| [anki_generator.py](file:///c:/Users/dxc75/text-ocr/anki_generator.py) | 主程序（Parser + Validator + TSV 导出） |
| [formula_processor.py](file:///c:/Users/dxc75/text-ocr/formula_processor.py) | 公式 → multi-cloze（纯 Python） |
| [llm_processor.py](file:///c:/Users/dxc75/text-ocr/llm_processor.py) | LLM 文本卡片（Google Gemini API） |

## 使用方法

```bash
# 单文件处理
uv run python anki_generator.py input/markdown_output/配当割引モデル.md output/

# 批量处理全部 96 个文件
uv run python anki_generator.py input/markdown_output/ output/

# 仅生成 Formula 卡片（不调用 LLM）
uv run python anki_generator.py input/markdown_output/ output/ --no-llm
```
