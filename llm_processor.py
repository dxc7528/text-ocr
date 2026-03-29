"""
LLM Processor — Google Gemini API wrapper for semantic text card generation.

Handles Definition, Causality, Contrast, Parallel, Sequential cards
from the 解説 and 留意点 sections of the markdown files.
"""

import json
import os
from google import genai
from google.genai import types
from pydantic import BaseModel
from formula_processor import AnkiCard


# ── Pydantic schema for structured LLM output ──────────────────────

class LLMAnkiCard(BaseModel):
    original_concept: str
    cloze_text: str
    card_type: str  # Definition, Causality, Contrast, Parallel, Sequential


class LLMCardResponse(BaseModel):
    cards: list[LLMAnkiCard]


# ── System prompt ───────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an Anki cloze card generator for CMA (日本証券アナリスト) exam preparation.
Convert the given Japanese text into Anki cloze deletion cards.

## STRICT RULES

1. Output JSON matching the provided schema. Nothing else.
2. Card types allowed: Definition, Causality, Contrast, Parallel, Sequential
3. **NEVER add hints.** Use ONLY {{cN::answer}} format. NEVER write {{cN::answer::hint}}.
4. **Anti-hint rule:** Text outside a cloze must NEVER reveal or paraphrase the hidden answer.
   If an explanatory gloss is needed, place it INSIDE the cloze as part of the answer text.
   WRONG: {{c1::$k > g$}}（要求収益率 ＞ 成長率）
   RIGHT: {{c1::$k > g$（要求収益率 ＞ 成長率）}}
5. **One card, one fact:** Each parallel element gets its own cloze number (c1, c2, c3...).
6. Keep the text in Japanese. Do not translate.
7. Do NOT create Formula cards — those are handled by a separate program.
8. If LaTeX formulas appear in the text, keep them in LaTeX format (do not convert to prose).
   You may reference formulas as context but do not cloze-delete formula variables.
9. Focus on extracting:
   - Core definitions and their meaning
   - Synonyms and alternative names
   - Cause-effect relationships
   - Exam-critical conditions and caveats
   - Frequently tested concepts and distinctions

## CARD TYPE GUIDELINES

- **Definition:** The defined term stays visible as the recall trigger. Cloze the meaning/characteristic.
- **Causality:** The cause or condition stays visible. Cloze the effect or result.
- **Contrast:** Both subjects stay visible. Cloze the differentiating trait for each.
- **Parallel:** Multiple independent items → each gets its own cN number.
- **Sequential:** Sequence indicators (①②) stay visible. Cloze the core action.

## EXAMPLES

Definition:
{"original_concept": "DDMの定義", "cloze_text": "株式の理論価格を「{{c1::将来支払われる配当の現在価値の合計}}」として算出する手法を配当割引モデル（DDM）という。", "card_type": "Definition"}

Causality:
{"original_concept": "成長率と株価の関係", "cloze_text": "定率成長モデルでは、成長率 $g$ が高いほど株価は{{c1::高く}}評価される。", "card_type": "Causality"}

Parallel:
{"original_concept": "WACCの構成要素", "cloze_text": "WACCは{{c1::負債コスト}}と{{c2::株主資本コスト}}を時価比率で加重平均したものである。", "card_type": "Parallel"}
"""


def create_client() -> genai.Client:
    """Create a Google Gemini API client."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "API key not found. Set GEMINI_API_KEY or GOOGLE_API_KEY environment variable."
        )
    return genai.Client(api_key=api_key)


def process_text_with_llm(
    client: genai.Client,
    text_sections: list[dict[str, str]],
    document_title: str,
    model: str = "gemini-2.5-flash",
) -> list[AnkiCard]:
    """
    Send text sections to the LLM and get back semantic cloze cards.

    Args:
        client: Google Gemini API client
        text_sections: List of dicts with 'heading' and 'body' keys
        document_title: Title of the source document for context
        model: Gemini model to use

    Returns:
        List of AnkiCard objects
    """
    if not text_sections:
        return []

    # Build the user prompt
    sections_text = ""
    for section in text_sections:
        heading = section.get("heading", "")
        body = section.get("body", "")
        sections_text += f"\n### {heading}\n{body}\n"

    user_prompt = f"""Source document: {document_title}

Please create Anki cloze cards from the following text sections:
{sections_text}

Remember: NO hints (never use ::hint), NO Formula cards, follow anti-hint rules strictly.
"""

    try:
        response = client.models.generate_content(
            model=model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_json_schema=LLMCardResponse.model_json_schema(),
                temperature=0.2,
            ),
        )
    except Exception as e:
        err_str = str(e)
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            print(f"  ⚠️ API クォータ超過 (429): テキストカードをスキップします。")
            print(f"     gemini-2.5-pro は無料枠の制限が厳しいため、")
            print(f"     gemini-2.5-flash の使用を推奨します。")
            print(f"     Formulaカードのみで出力を続けます。")
        else:
            print(f"  ⚠️ LLM API エラー: {e}")
        return []

    # Parse response
    try:
        parsed = LLMCardResponse.model_validate_json(response.text)
        return [
            AnkiCard(
                original_concept=card.original_concept,
                cloze_text=card.cloze_text,
                card_type=card.card_type,
            )
            for card in parsed.cards
        ]
    except Exception as e:
        print(f"  ⚠️ LLM レスポンスのパースに失敗しました: {e}")
        print(f"  Raw response: {response.text[:500]}")
        return []
