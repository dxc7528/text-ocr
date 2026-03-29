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

Use when defining a term. Cloze the term itself or its key distinguishing characteristic.

**Example:**
`原子番号は原子核内の{{c1::陽子数::特徴}}である。`

#### Card Type: Formula

Use when representing mathematical relationships. Cloze the core variables, leaving mathematical operators visible.

**Example:**
`$Q = \Delta U + {{c1::W::熱力学量}}$`

### Step 3: Validation

Before finalizing, verify:
1. The cloaked text is a single word or a tight compound noun (not a phrase longer than 3-4 words). Rewrite if too long.
2. The user can determine the type of answer required without guessing. Add a `::Hint` if the category is ambiguous.

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

When processing formulas in markdown ($$...$$ or $...$):

1. Extract the formula and its surrounding context (heading, description)
2. Denoise the surrounding text
3. Identify key variables that should be tested independently
4. Apply the appropriate cloze type based on the variable's role

**Formula card example:**
- Input: "熱力学第一法則: $Q = \Delta U + W$"
- Denoised: "Heat equals change in internal energy plus work."
- Card: `{{c1::Heat}} equals {{c2::change in internal energy}} plus {{c3::work}}.`
- Output JSON:
```json
{
  "original_concept": "First law of thermodynamics",
  "processed_cloze_text": "{{c1::Heat}} equals {{c2::change in internal energy}} plus {{c3::work}}.",
  "card_type": "Definition"
}
```

## Handling Multiple Variables in One Formula

For formulas with multiple key variables, generate one card per variable. Each card should test a single atomic piece of knowledge.

**Example for $P_0 = \frac{D_1}{k - g}$:**
- Card 1: `"original_concept": "Gordon growth model - dividend", "processed_cloze_text": "In $P_0 = \frac{{{c1::D_1}}}{k - g}$, D_1 represents {{c2::next year dividend::meaning}}", "card_type": "Formula"`
- Card 2: `"original_concept": "Gordon growth model - required return", "processed_cloze_text": "In $P_0 = \frac{D_1}{{{c1::k}} - g}$, k represents {{c2::required return on equity::meaning}}", "card_type": "Formula"`

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

**Formula card:**
```json
{
  "original_concept": "First law of thermodynamics",
  "processed_cloze_text": "$Q = \Delta U + {{c1::W::熱力学量}}$",
  "card_type": "Formula"
}
```
