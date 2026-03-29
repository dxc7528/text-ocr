"""
Anki Card Generator — Hybrid Architecture (Python + LLM)

Main orchestrator: Parser → Formula Processor → LLM Processor → Validator → TSV Export.

Usage:
    python anki_generator.py input/markdown_output/配当割引モデル.md output/
    python anki_generator.py input/markdown_output/ output/          # batch mode
"""

import re
import csv
import sys
import os
from pathlib import Path
from dataclasses import dataclass, field

from formula_processor import AnkiCard, generate_formula_cards, find_variable_occurrences


# ─── Data Structures ────────────────────────────────────────────────

@dataclass
class PointItem:
    label: str
    formulas: list[str]
    notes: str = ""


@dataclass
class TextItem:
    heading: str
    body: str


@dataclass
class ParsedDocument:
    title: str
    point_items: list[PointItem]
    explanation_items: list[TextItem]
    exam_tips: list[TextItem]


# ─── Stage 1: Parser ────────────────────────────────────────────────

def parse_markdown(text: str) -> ParsedDocument:
    """Parse a 3-section markdown file into structured data."""
    # Normalize line endings
    text = text.replace('\r\n', '\n')

    # Split by horizontal rules (---)
    sections = re.split(r'\n-{3,}\n', text)

    point_section = sections[0] if len(sections) > 0 else ""
    explanation_section = ""
    exam_section = ""

    for s in sections[1:]:
        if '知識点の解説' in s:
            explanation_section = s
        elif '試験の留意点' in s or '留意点' in s:
            exam_section = s

    # Extract title from first line
    first_line = point_section.strip().split('\n')[0]
    title = re.sub(r'^Point[：:]?\s*', '', first_line).strip()

    return ParsedDocument(
        title=title,
        point_items=parse_point_section(point_section),
        explanation_items=parse_text_section(explanation_section),
        exam_tips=parse_text_section(exam_section),
    )


def parse_point_section(text: str) -> list[PointItem]:
    """Extract labeled items with formulas from the Point section."""
    items = []
    lines = text.strip().split('\n')
    if not lines:
        return items

    current_label = ""
    current_formulas: list[str] = []
    current_notes = ""

    def flush():
        nonlocal current_label, current_formulas, current_notes
        if current_label and current_formulas:
            items.append(PointItem(
                label=current_label,
                formulas=list(current_formulas),
                notes=current_notes,
            ))
        current_label = ""
        current_formulas = []
        current_notes = ""

    for line in lines[1:]:  # Skip the Point title line
        line = line.strip()
        if not line:
            continue

        # Numbered item: ①②③...
        if re.match(r'^[①②③④⑤⑥⑦⑧⑨⑩]', line):
            flush()
            current_label = line
            continue

        # Display formula: $$...$$
        display_formulas = re.findall(r'\$\$(.+?)\$\$', line, re.DOTALL)
        if display_formulas:
            current_formulas.extend(f.strip() for f in display_formulas)
            continue

        # Inline formula on its own line: $...$
        inline_match = re.match(r'^\$([^$]+)\$$', line)
        if inline_match:
            current_formulas.append(inline_match.group(1).strip())
            continue

        # Notes line
        if line.startswith('ただし') or line.startswith('※'):
            current_notes = line
            continue

        # Plain text label (not a formula, not a note → new item label)
        if not line.startswith('$') and not line.startswith('（') and current_label:
            # Only start a new item if we have formulas for the current one
            if current_formulas:
                flush()
            current_label = line
            continue

        # First label (when no numbered marker)
        if not current_label:
            current_label = line

    flush()
    return items


def parse_text_section(text: str) -> list[TextItem]:
    """Extract text items from 解説 or 留意点 sections."""
    items = []
    if not text.strip():
        return items

    # Try bullet-point format: * **heading**\n body
    bullet_parts = re.split(r'\n\*\s+\*\*', text)
    if len(bullet_parts) > 1:
        for part in bullet_parts[1:]:
            # Extract heading (up to **)
            heading_match = re.match(r'(.+?)\*\*\s*\n?(.*)', part, re.DOTALL)
            if heading_match:
                heading = heading_match.group(1).strip()
                body = heading_match.group(2).strip()
                items.append(TextItem(heading=heading, body=body))
        return items

    # Try numbered format: 1. **heading**\n body
    numbered_parts = re.split(r'\n\d+\.\s+\*\*', text)
    if len(numbered_parts) > 1:
        for part in numbered_parts[1:]:
            heading_match = re.match(r'(.+?)\*\*\s*\n?(.*)', part, re.DOTALL)
            if heading_match:
                heading = heading_match.group(1).strip()
                body = heading_match.group(2).strip()
                items.append(TextItem(heading=heading, body=body))
        return items

    # Fallback: treat the whole section as one item
    # Remove the section header line
    lines = text.strip().split('\n')
    header_idx = 0
    for i, line in enumerate(lines):
        if '知識点の解説' in line or '試験の留意点' in line or '留意点' in line:
            header_idx = i
            break
    body = '\n'.join(lines[header_idx + 1:]).strip()
    if body:
        items.append(TextItem(heading="", body=body))
    return items


def extract_inline_formulas(text: str) -> list[str]:
    """Extract inline LaTeX formulas ($...$) from text that look like equations."""
    formulas = []
    for m in re.finditer(r'(?<!\$)\$([^$]+?)\$(?!\$)', text):
        formula = m.group(1).strip()
        # Only include if it looks like an equation (contains =)
        if '=' in formula and len(formula) > 3:
            formulas.append(formula)
    return formulas


# ─── Stage 3: Validator ─────────────────────────────────────────────

def validate_cards(cards: list[AnkiCard]) -> list[AnkiCard]:
    """Validate and auto-fix cards for rule compliance."""
    validated = []
    for card in cards:
        text = card.cloze_text

        # Check 1: Remove any hints (::hint pattern)
        hint_pattern = r'\{\{(c\d+)::([^}]*?)::[^}]*?\}\}'
        if re.search(hint_pattern, text):
            text = re.sub(hint_pattern, r'{{\1::\2}}', text)
            print(f"  🔧 Auto-fixed: removed hint from card '{card.original_concept}'")

        # Check 2: Verify at least one cloze exists
        if not re.search(r'\{\{c\d+::', text):
            print(f"  ⚠️ Skipped: no cloze found in card '{card.original_concept}'")
            continue

        # Check 3: Anti-hint — check for parenthetical content right after cloze
        anti_hint = re.search(r'\}\}（([^）]+)）', text)
        if anti_hint:
            # Move the parenthetical content inside the cloze
            leaked = anti_hint.group(1)
            text = re.sub(
                r'(\{\{c\d+::)([^}]+)\}\}（' + re.escape(leaked) + r'）',
                r'\1\2（' + leaked + r'）}}',
                text,
            )
            print(f"  🔧 Auto-fixed: moved leaked hint inside cloze '{card.original_concept}'")

        # Check 4: Format LaTeX and Prevent Fragmented Tags (Apply convert_anki_latex logic)
        try:
            from convert_anki_latex import process_line as format_latex
            text = format_latex(text)
        except ImportError:
            pass

        card.cloze_text = text
        validated.append(card)

    return validated


# ─── Stage 4: TSV Export ─────────────────────────────────────────────

def export_tsv(cards: list[AnkiCard], filepath: str):
    """Export cards as TSV for Anki import (Cloze type: Text + Extra)."""
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        for card in cards:
            # Field 1: cloze text, Field 2: extra info (card type + concept)
            extra = f"[{card.card_type}] {card.original_concept}"
            writer.writerow([card.cloze_text, extra])
    print(f"✅ Exported {len(cards)} cards → {filepath}")


# ─── Main Orchestrator ──────────────────────────────────────────────

def process_file(input_path: str, output_dir: str, use_llm: bool = True) -> list[AnkiCard]:
    """Process a single markdown file → Anki cards."""
    print(f"\n📄 Processing: {os.path.basename(input_path)}")

    with open(input_path, 'r', encoding='utf-8') as f:
        text = f.read()

    doc = parse_markdown(text)
    print(f"  Title: {doc.title}")
    print(f"  Point items: {len(doc.point_items)}")
    print(f"  Explanation items: {len(doc.explanation_items)}")
    print(f"  Exam tips: {len(doc.exam_tips)}")

    all_cards: list[AnkiCard] = []

    # ── Stage 2A: Formula cards (deterministic) ──
    for item in doc.point_items:
        for formula in item.formulas:
            cards = generate_formula_cards(item.label, formula)
            all_cards.extend(cards)
            for c in cards:
                print(f"  📐 Formula: {c.cloze_text[:80]}...")

    # Also extract inline formulas from text sections
    for section in doc.explanation_items + doc.exam_tips:
        inline_formulas = extract_inline_formulas(section.body)
        for formula in inline_formulas:
            cards = generate_formula_cards(section.heading or doc.title, formula)
            all_cards.extend(cards)

    print(f"  Formula cards: {len(all_cards)}")

    # ── Stage 2B: Text cards (LLM) ──
    if use_llm:
        try:
            from llm_processor import create_client, process_text_with_llm

            client = create_client()
            text_sections = []
            for item in doc.explanation_items:
                text_sections.append({"heading": item.heading, "body": item.body})
            for item in doc.exam_tips:
                text_sections.append({"heading": item.heading, "body": item.body})

            if text_sections:
                print(f"  🤖 Sending {len(text_sections)} text sections to LLM...")
                llm_cards = process_text_with_llm(client, text_sections, doc.title)
                all_cards.extend(llm_cards)
                print(f"  Text cards from LLM: {len(llm_cards)}")
        except ImportError:
            print("  ⚠️ LLM processor not available, skipping text cards")
        except ValueError as e:
            print(f"  ⚠️ LLM error: {e}")
            print("  Skipping text cards. Set GEMINI_API_KEY to enable.")

    # ── Stage 3: Validate ──
    all_cards = validate_cards(all_cards)

    return all_cards


def main():
    if len(sys.argv) < 2:
        print("Usage: python anki_generator.py <input_file_or_dir> [output_dir] [--no-llm]")
        print("")
        print("Options:")
        print("  --no-llm    Skip LLM processing (only generate Formula cards)")
        sys.exit(1)

    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith('--') else "output"
    use_llm = "--no-llm" not in sys.argv

    # Load .env if available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    # Collect input files
    input_files = []
    if os.path.isdir(input_path):
        for f in sorted(Path(input_path).glob("*.md")):
            input_files.append(str(f))
    elif os.path.isfile(input_path):
        input_files.append(input_path)
    else:
        print(f"❌ Not found: {input_path}")
        sys.exit(1)

    print(f"Found {len(input_files)} file(s) to process")
    if not use_llm:
        print("⚡ LLM disabled — generating Formula cards only")

    # Process each file
    for filepath in input_files:
        cards = process_file(filepath, output_dir, use_llm=use_llm)
        if cards:
            basename = Path(filepath).stem
            tsv_path = os.path.join(output_dir, f"{basename}_cloze.tsv")
            export_tsv(cards, tsv_path)

    print(f"\n🎉 Done! Import TSV files from '{output_dir}/' into Anki as 'Cloze' type.")


if __name__ == "__main__":
    main()
