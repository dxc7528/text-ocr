# 混合架构 Anki 卡片生成器 — 实施方案

## 决策确认

| 决策点 | 用户决定 |
|--------|---------|
| 方案选择 | ✅ 方案 C（混合架构：Program + LLM） |
| Hint | ✅ 全面禁用 `::hint`，所有卡片类型 |
| 输出格式 | ✅ TSV（用户端）；JSON 仅作为 LLM → Python 的内部传输格式 |
| 架构 | ✅ **Python 主导**（Python 解析文件 → Python 处理公式 → Python 调用 LLM 处理文本 → Python 验证 → TSV 输出） |

## 输入文件结构分析

调查了 96 个 markdown 文件，确认全部遵循统一的三段结构：

```
第一段：Point（公式区）
─────────────────────
Point：[标题]
① [子概念]
$$公式$$
② [子概念]
$$公式$$
...
（可能包含 "ただし" 变量说明行）

---

第二段：知識点の解説（概念解说区）
────────────────────────────
### 【知識点の解説】
* **① [子概念]**
    解说文本...
* **② [子概念]**
    解说文本...

第三段：試験の留意点（考试要点区）
────────────────────────────
### 【CMA Level 2 試験の留意点】
1. **[考点标题]**
   考点解说...
2. **[考点标题]**
   考点解说...
```

> [!IMPORTANT]
> 三段结构非常规律，Python 正则完全可以可靠解析。不需要 LLM 做结构识别。

## 架构设计

```
输入 Markdown ──→ Parser (Python)
                      │
           ┌──────────┼──────────┐
           │          │          │
     Point 区     解説区      留意点区
           │          │          │
    Formula        Text        Text
    Processor    Processor   Processor
    (Python)     (LLM API)   (LLM API)
           │          │          │
           └──────────┼──────────┘
                      │
              Validator (Python)
                      │
                 TSV Output
```

### 各模块职责

| 模块 | 方法 | 输入 | 输出 |
|------|------|------|------|
| **Parser** | Python 正则 | 整个 .md 文件 | 三个区块的结构化数据 |
| **Formula Processor** | Python（确定性） | Point 区中的公式 + 上下文 | Formula 类型 cloze 卡片 |
| **Text Processor** | Python 调用 LLM API | 解説区 / 留意点区的文本段落 | Definition / Causality / Contrast 等卡片 |
| **Validator** | Python 正则 | 所有卡片 | 合规卡片（过滤违规项） |

## Proposed Changes

### Stage 1: Parser — 解析 Markdown 三段结构

#### [NEW] [anki_generator.py](file:///c:/Users/dxc75/text-ocr/anki_generator.py)

主入口脚本。功能：

**`parse_markdown(text) → dict`**
- 用 `---` 分隔符切分文件为 3 个区块
- Point 区：提取编号项 `①②③④` 及其公式 `$$...$$` 和 `$...$`
- 解説区：按 `* **` 拆分为独立段落
- 留意点区：按 `1. **` `2. **` 拆分为独立段落

返回结构：
```python
{
    "title": "配当割引モデル（DDM）",
    "point_items": [
        {
            "label": "① 定額配当モデル（ゼロ成長モデル）",
            "formulas": ["P_0 = \\frac{D}{k}"],
            "notes": "ただし...",
        },
        ...
    ],
    "explanation_items": [
        {
            "heading": "① 定額配当モデル（ゼロ成長モデル）",
            "body": "将来の配当金 D が永久に...",
            "inline_formulas": ["D_1 = D_0 \\times (1+g)"],  # 解説中出现的公式也要提取
        },
        ...
    ],
    "exam_tips": [
        {
            "heading": "配当のタイミング（D0 と D1 の違い）",
            "body": "定率成長モデルの計算において...",
            "inline_formulas": ["D_1 = D_0 \\times (1+g)"],
        },
        ...
    ]
}
```

---

### Stage 2A: Formula Processor — 公式 → Cloze 卡片（纯 Python）

在 `anki_generator.py` 中实现。

**`process_formula(label, formula) → list[dict]`**

逻辑：
1. 解析公式，识别等号 `=` 的 LHS 和 RHS
2. 在 RHS 中提取所有独立变量/子表达式（基于现有 `extract_variables()` 的改良版）
3. 对每个变量分配递增的 `cX` 编号
4. 生成 cloze 字符串，**无 hint**
5. 特殊处理 `\frac{}{}` 结构：分子和分母各为独立 cloze

示例输入输出：
```
输入: label="定率成長モデル", formula="P_0 = \\frac{D_1}{k-g}"

输出: {
    "cloze_text": "定率成長モデル（ゴードン・モデル）：$$P_0 = \\frac{{{c1::D_1}}}{{{c2::k}} - {{c3::g}}}$$",
    "card_type": "Formula"
}
```

**关键改进（相对于现有 `extract_variables()`）：**
- 改良对 `\frac{分子}{分母}` 的处理：递归分析分子分母内部的变量
- 处理 `\text{日文}` 内容作为整体变量（如 `\text{配当性向}`）
- 处理复合表达式如 `(1 - \text{配当性向})` 作为一个 cloze 单元
- 处理 `E[R_M]` 这类带括号的变量

---

### Stage 2B: Text Processor — 文本段落 → 语义卡片（LLM）

在 `anki_generator.py` 中通过 API 调用实现。

**`process_text_with_llm(text_items) → list[dict]`**

- 将解説区和留意点区的文本段落批量发给 LLM
- LLM 返回 JSON 格式的卡片（内部传输格式）
- **Prompt 经过精简**：仅包含 Definition / Causality / Contrast / Parallel / Sequential 的规则，不包含 Formula 规则
- **明确指令**：无 hint，Anti-hint 原则，One card one fact
- 解説区和留意点区中出现的**行内公式**也要提取为 Formula 卡片（由 Python 处理，不交给 LLM）

> [!IMPORTANT]
> LLM API 选择问题：你目前 `pyproject.toml` 中没有任何 LLM SDK 依赖。
> 我建议使用 `google-genai` （Google Gemini API）。
> 需要你提供 API key 或确认使用哪个 LLM 服务。

---

### Stage 3: Validator — 规则合规检查（纯 Python）

**`validate_cards(cards) → list[dict]`**

自动检查 + 自动修复：

| # | 检查项 | 检测方法 | 处理 |
|---|--------|---------|------|
| 1 | **Hint 存在** | 正则 `\{\{c\d+::.*?::.*?\}\}` | 自动删除 hint 部分 |
| 2 | **Multi-cloze 不足** | Formula 卡片中 RHS 变量数 > cloze 数 | 输出警告日志 |
| 3 | **Anti-hint** | cloze 外部括号内容与 cloze 内容的文本重叠 | 自动将括号内容移入 cloze |
| 4 | **LaTeX 完整性** | `$` `{` `}` 配对检查 | 输出错误日志 |
| 5 | **公式遗漏** | 输入公式数 vs Formula 卡片数 | 输出警告日志 |

---

### 输出

**`export_tsv(cards, filepath)`**

- Cloze 类型卡片输出为 TSV（一行一卡片，Text 字段 + Extra 字段）
- 文件命名：`output/{原文件名}_cloze.tsv`

---

## 文件清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `anki_generator.py` | [NEW] | 主程序：Parser + Formula Processor + Validator + TSV 导出 |
| `llm_processor.py` | [NEW] | LLM API 调用封装（Text Processor） |
| `prompts.py` | [NEW] | LLM 的 system prompt（精简版规则，仅文本卡片） |
| `.env` (或用户配置) | [NEW] | API key 配置 |
| `pyproject.toml` | [MODIFY] | 添加依赖：`google-genai` |
| `.gemini/skills/markdown-to-anki/SKILL.md` | [DELETE 或 ARCHIVE] | 不再需要，规则已内置到程序中 |

## Open Questions

> [!IMPORTANT]
> ### 1. LLM API 选择
> 你要使用哪个 LLM API？推荐选项：
> - **a) Google Gemini API** (`google-genai` SDK) — 与你现有的 Gemini 工作流一致
> - **b) OpenAI API** (`openai` SDK)
> - **c) 暂时不接 LLM，先只实现 Formula Processor（纯 Python）**，文本卡片后续再加
>
> 如果选 a 或 b，你有现成的 API key 吗？

> [!IMPORTANT]
> ### 2. 是否保留 SKILL.md？
> 混合架构下 SKILL.md 的作用被大幅削弱（公式由 Python 处理，文本卡片由程序内嵌 prompt 处理）。
> - **a) 删除** — 所有规则内嵌到 Python 代码中
> - **b) 保留但标记为 deprecated** — 作为文档参考
> - **c) 简化为仅包含文本卡片规则** — 作为 `prompts.py` 的参考源

> [!NOTE]
> ### 3. 批量处理
> `input/markdown_output/` 有 96 个文件。程序是否要支持批量处理整个目录？
> 我的默认计划是支持：`python anki_generator.py input/markdown_output/ output/`

## Verification Plan

### Automated Tests
1. 使用 `配当割引モデル.md` 作为测试输入
2. 验证 Formula Processor 输出：
   - 4 个 Point 公式全部生成了 Formula 卡片
   - 每个公式的 RHS 变量全部有独立 cloze
   - 没有任何 `::hint`
3. 验证 Validator：
   - 手动注入带 hint 的卡片 → 确认被自动删除
   - 手动注入 anti-hint 违反 → 确认被检测
4. 验证 TSV 输出格式可被 Anki 识别

### Manual Verification
- 将生成的 TSV 导入 Anki，手动复习确认体验
