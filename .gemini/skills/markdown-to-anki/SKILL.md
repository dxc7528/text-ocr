---
name: markdown-to-anki
description: |
  Convert markdown files containing formulas and concepts into Anki flashcards using cloze deletion.
  Use this skill whenever the user wants to:
  - Create Anki cards from markdown files
  - Convert LaTeX formulas to cloze flashcards
  - Generate flashcards for memorization of variables and formulas

  This skill applies the Minimum Information Principle (SuperMemo 20 Rules) and produces structured JSON output with {{cX::Answer::Hint}} cloze markers.
---

# Markdown to Anki Card Converter

This skill converts markdown content into Anki cloze flashcards following evidence-based design principles. The output is structured JSON matching a defined schema.

## Core Principles

### 1. Minimum Information Principle
Each cloze deletion must target a single atomic concept: a specific noun, a core verb, or a distinct value. Never cloak entire phrases or long clauses. If a sentence contains multiple independent facts, split into multiple cards or use parallel cloze markers.

### 2. Contextual Clarity
The un-cloaked text must provide an unambiguous, singular pathway to the hidden answer. The reader should never need to guess what kind of answer is missing.

### 3. Cognitive Load Reduction
Remove redundant adjectives, conversational fillers, and unnecessary introductory phrases before creating the cloze. Prefer declarative sentences over explanatory ones.

### 4. Formula Integrity — Preserve LaTeX, No Hybrid Mixing
Formulas MUST remain in their original LaTeX notation (`$...$` or `$$...$$`). Never convert a formula into a prose description. The cloze markers are placed **inside** the LaTeX expression around individual variables or sub-expressions.

Additionally, never produce "hybrid" cards that mix mathematical symbols with natural-language paraphrasing. The formula must be a self-contained, rigorous mathematical expression.

**Correct:**
`定額配当モデル（ゼロ成長モデル）は $$P_0 = \frac{{{c1::D}}}{{{c2::k}}}$$`

**Wrong (converted to prose):**
`定額配当モデル（ゼロ成長モデル）では、理論株価 $P_0$ は配当 $D$ を{{c1::割引率 $k$::変数}}で割って算出される。`

**Wrong (hybrid — mixed symbols and text):**
`CAPMによる要求収益率 $k$ は、リスクフリーレート $R_f$ に{{c1::ベータ値 $\beta$::係数}} × 市場リスクプレミアムを加えたものである。`

### 5. Anti-Hint Principle — Do Not Leak Cloze Answers
Text surrounding a cloze must never reveal or paraphrase the hidden answer. If an explanatory gloss is necessary, it must be placed **inside** the cloze marker (as part of the answer text), not adjacent to it outside the cloze.

**Correct:**
`定率成長モデルが成立するための前提条件は、{{c1::$k > g$ （要求収益率 ＞ 成長率）::条件}}である。`

**Wrong (the parenthetical outside the cloze leaks the answer):**
`定率成長モデルが成立するための前提条件は、{{c1::$k > g$::条件}}（要求収益率 ＞ 成長率）である。`

### 6. Comprehensiveness — No Omissions
Every testable fact in the source material must produce at least one card. This includes:
- Core definitions and their meaning
- Synonyms and alternative names (e.g., DDM = Dividend Discount Model = 配当割引モデル)
- Frequently tested propositions and conditions
- **All formulas** appearing under a heading — including sub-formulas, derivations, and special-case variants

Do not extract only formulas while ignoring surrounding textual definitions and key concepts.

**Correct (captures the definition):**
`株式の理論価格を「{{c1::将来支払われる配当の現在価値の合計}}」として算出する手法を配当割引モデル（DDM）という。`

**Correct (captures a key term):**
`多段階成長モデルにおいて、安定成長に移行した後の価値を合算したものを{{c1::ターミナルバリュー}}と呼ぶ。`

**Wrong:** Extracting only the formulas and completely omitting textual definitions of DDM, terminal value, and other exam-critical concepts.

### 7. One Card, One Fact — Parallel Elements Get Independent Clozes
When a card contains multiple parallel components (e.g., the factors of a decomposition), each component MUST receive its own cloze number (`c1`, `c2`, `c3`, ...) so that every element is independently testable.

**Correct:**
`ROEの分解（デュポン分析）：$ROE$ = {{c1::売上高純利益率}} $\times$ {{c2::総資産回転率}} $\times$ {{c3::財務レバレッジ}}`

**Wrong (only one element is cloze-deleted; the others are never tested):**
`$ROE$ は、売上高純利益率 × {{c1::総資産回転率::指標}} × 財務レバレッジに分解される。`

## Processing Pipeline

### Step 1: Denoise and Condense

Read the input text and rewrite it into a concise, declarative sentence. Remove:
- Unnecessary introductory phrases (e.g., "It is said that...", "Generally...")
- Redundant modifiers and fillers
- Conversational framing

**Example:**
- Input: "The first law of thermodynamics states that heat is a form of energy."
- Output: "Heat is a form of energy."

### Step 2: Classify and Apply Cloze Logic

Determine the logical structure of the denoised sentence and apply the corresponding cloze strategy. Use the format `{{cX::Answer::Hint}}` where the hint indicates the category of the answer when it is not obvious from context.

#### Card Type: Parallel

Use when listing independent, unordered items. Use different c-numbers for each item. Always include a hint indicating the category.

**Example:**
`データベースの前処理は{{c1::ソート::手法}}と{{c2::インデックス::手法}}である。`

#### Card Type: Sequential

Use when describing an ordered process. Preserve sequence indicators (①, ②, etc.) as un-cloaked context. Cloze the core action or target.

**Example:**
`①ファイルを{{c1::前処理::処理}}し、②実装方式を{{c2::評価::アクション}}する。`

#### Card Type: Causality

Use when expressing cause-effect or condition-result relationships. Keep the cause or condition visible as the trigger. Cloze the result.

**Example:**
`金利が上昇すると、債券価格は{{c1::下落::方向}}する。`

#### Card Type: Contrast

Use when comparing two subjects. Cloze the differentiating trait, keeping both subjects visible.

**Example:**
`株式は{{c1::ハイ::度合い}}リスク、債券は{{c2::ロー::度合い}}リスク。`

#### Card Type: Definition

Use when defining a term. Cloze the **core concept being defined**, not the qualifying conditions or constraints.

Cloze the meaning or key characteristic of the term. 
Do NOT cloak qualifying adjectives, conditions, or scope limitations.
**Key Principle:** The defined term itself should remain visible as the recall trigger. Cloze its meaning, not the term name or its qualifications.

**Correct Example:**
`原子番号は原子核内の{{c1::陽子数::特徴}}である。`

**Wrong Example:**
`BRは{{c1::独立した::鍵}}銘柄選択の回数である。`

#### Card Type: Formula

Use when representing mathematical relationships. The formula MUST be preserved in LaTeX notation. Apply the following sub-rules:

1. **Keep LaTeX format.** Never paraphrase a formula into natural language. Place cloze markers directly inside the LaTeX expression around individual variables or sub-expressions.
2. **Multi-cloze every variable after the equals sign.** Each independent variable or sub-expression on the right-hand side of the equation gets its own `cX` marker so it is independently testable.
3. **No hybrid mixing.** The card must be a complete, rigorous mathematical expression — not a mixture of symbols and prose.
4. **Exhaustive coverage.** Every formula appearing under a heading (including derivations, special cases, and sub-formulas) must produce a Formula card. No formula may be skipped.

**Correct Example (multi-cloze, pure LaTeX):**
`CAPMによる要求収益率 $k$ の公式：$$k = {{c1::R_f}} + {{c2::\beta_i}} \times ({{c3::E[R_M] - R_f}})$$`

**Correct Example (fraction in LaTeX):**
`定額配当モデル（ゼロ成長モデル）は $$P_0 = \frac{{{c1::D}}}{{{c2::k}}}$$`

**Wrong Example (only one variable cloze-deleted):**
`定額配当モデル（ゼロ成長モデル）は $$P_0 = \frac{{{c1::D}}}{k}$$`

**Wrong Example (formula converted to prose):**
`熱力学第一法則では、熱量は{{c1::内部エネルギーの変化}}に{{c2::仕事}}を加えたものである。`

### Step 3: Validation

Before finalizing, verify:
1. The cloaked text is a single word or a tight compound noun (not a phrase longer than 3-4 words). Rewrite if too long.
2. The user can determine the type of answer required without guessing. Add a `::Hint` if the category is ambiguous.
3. **Formula integrity:** Every formula card uses LaTeX notation, not prose. No hybrid cards exist.
4. **Multi-cloze check:** Every independent variable on the RHS of a formula has its own cloze number.
5. **Anti-hint check:** No text outside a cloze marker reveals or paraphrases the hidden answer.
6. **Completeness check:** All formulas in the source (including sub-formulas and derivations) have corresponding cards. All core definitions, synonyms, and exam-critical concepts have cards.
7. **One-fact check:** Parallel elements each have their own cloze number.

## Output Format

Output strictly in JSON format. Do not include markdown code blocks or conversational text.

```json
{
  "original_concept": "A brief summary of what knowledge point this card tests",
  "processed_cloze_text": "The final optimized string with {{cX::...}} markers",
  "card_type": "Parallel | Sequential | Causality | Contrast | Definition | Formula"
}
```

## Working with LaTeX Formulas

When processing formulas in markdown (`$$...$$` or `$...$`):

1. Extract the formula and its surrounding context (heading, description)
2. Denoise the surrounding text
3. **Keep the formula in LaTeX format** — do not convert to natural language
4. Identify every independent variable or sub-expression after the `=` sign
5. Assign each variable its own cloze number (`c1`, `c2`, `c3`, ...)
6. Leave mathematical operators (`+`, `-`, `\times`, `\frac{}{}`, `=`) visible as structural scaffolding
7. Scan for ALL formulas under the heading — including derivations and special-case variants — and produce a card for each one

**Formula card example:**
- Input: `熱力学第一法則: $Q = \Delta U + W$`
- Card:
```
熱力学第一法則: $$Q = {{c1::\Delta U}} + {{c2::W}}$$
```
- Output JSON:
```json
{
  "original_concept": "First law of thermodynamics",
  "processed_cloze_text": "熱力学第一法則: $$Q = {{c1::\\Delta U}} + {{c2::W}}$$",
  "card_type": "Formula"
}
```

**Multi-variable formula example:**
- Input: `CAPMによる期待収益率: $E[R_i] = R_f + \beta_i (E[R_M] - R_f)$`
- Card:
```
CAPMによる期待収益率の公式：$$E[R_i] = {{c1::R_f}} + {{c2::\beta_i}} \times ({{c3::E[R_M] - R_f}})$$
```
- Output JSON:
```json
{
  "original_concept": "CAPM expected return formula",
  "processed_cloze_text": "CAPMによる期待収益率の公式：$$E[R_i] = {{c1::R_f}} + {{c2::\\beta_i}} \\times ({{c3::E[R_M] - R_f}})$$",
  "card_type": "Formula"
}
```

## Bundled Script

The skill includes a helper script at `scripts/generate_anki_cards.py` for batch processing markdown files. This script:
- Parses markdown to extract heading-formula pairs
- Detects variables in LaTeX formulas
- Generates TSV output for Anki import

Run standalone:
```bash
python3 scripts/generate_anki_cards.py input.md output_dir/
```

## JSON Output Examples

**Parallel card:**
```json
{
  "original_concept": "Database preprocessing techniques",
  "processed_cloze_text": "データベースの前処理は{{c1::ソート::手法}}と{{c2::インデックス::手法}}である。",
  "card_type": "Parallel"
}
```

**Causality card:**
```json
{
  "original_concept": "Effect of interest rate rise on bond price",
  "processed_cloze_text": "金利が上昇すると、債券価格は{{c1::下落::方向}}する。",
  "card_type": "Causality"
}
```

**Definition card:**
```json
{
  "original_concept": "Definition of Dividend Discount Model",
  "processed_cloze_text": "株式の理論価格を「{{c1::将来支払われる配当の現在価値の合計}}」として算出する手法を配当割引モデル（DDM）という。",
  "card_type": "Definition"
}
```

**Formula card:**
```json
{
  "original_concept": "Zero-growth Dividend Discount Model",
  "processed_cloze_text": "定額配当モデル（ゼロ成長モデル）は $$P_0 = \\frac{{{c1::D}}}{{{c2::k}}}$$",
  "card_type": "Formula"
}
```
