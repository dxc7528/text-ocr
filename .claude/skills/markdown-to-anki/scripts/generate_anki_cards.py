#!/usr/bin/env python3
"""
Markdown to Anki Card Generator

Parses markdown files containing LaTeX formulas and generates
TSV files for Anki import.

Follows the Minimum Information Principle:
- One card per concept/variable
- For complex formulas, generate multiple cloze cards (one per variable)
"""

import re
import csv
import json
import argparse
import os
from pathlib import Path


def parse_markdown(markdown_text):
    """
    Parse markdown to extract concept-formula pairs.

    Returns a list of dicts with keys: concept, formula, context
    """
    items = []

    # Split by headings (## or ###)
    sections = re.split(r'^#{2,3}\s+(.+)$', markdown_text, flags=re.MULTILINE)

    i = 1
    current_concept = None

    while i < len(sections):
        heading = sections[i].strip() if i < len(sections) else ""
        content = sections[i + 1].strip() if i + 1 < len(sections) else ""

        if heading:
            current_concept = heading

        # Extract formulas from content
        formula_pattern = r'\$\$(.+?)\$\$|\$(.+?)\$'
        formulas = re.findall(formula_pattern, content, re.DOTALL)

        for f in formulas:
            formula = f[0] if f[0] else f[1]
            formula = formula.strip()

            if formula and current_concept:
                items.append({
                    "concept": current_concept,
                    "formula": formula,
                    "context": content[:200]
                })

        i += 2

    return items


def extract_variables(formula):
    """
    Extract variable names from a LaTeX formula.

    Returns a list of variable names that are actual mathematical variables.
    Uses subscript patterns like X_y, X_{yz}, D_1, beta_i etc.
    """
    # LaTeX commands to exclude
    exclude_commands = {
        'frac', 'sqrt', 'sum', 'prod', 'int', 'partial',
        'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'theta', 'lambda', 'mu',
        'sigma', 'phi', 'psi', 'omega', 'rho', 'tau', 'eta', 'zeta', 'xi',
        'infty', 'mathbb', 'mathbf', 'mathit', 'mathrm', 'quad',
        'left', 'right', 'begin', 'end', 'array', 'matrix', 'pmatrix',
        'times', 'cdot', 'div', 'leq', 'geq', 'neq', 'approx', 'equiv',
        'sin', 'cos', 'tan', 'log', 'ln', 'exp', 'max', 'min',
        'lim', 'to', 'from', 'over', 'in', 'text', 'label', 'ref',
        '芮', '内部', '留保', '配当', '性向'  # Japanese text in \text{}
    }

    # Common single-letter variables in finance/physics
    common_vars = {
        'P', 'p', 'D', 'd', 'k', 'g', 'r', 'R', 'E', 'M', 'F', 'f',
        'V', 'v', 'C', 'c', 'S', 's', 'I', 'i', 'T', 't', 'L', 'l',
        'Q', 'q', 'W', 'w', 'U', 'u', 'H', 'h', 'A', 'a', 'B', 'b',
        'ROE', 'Beta', 'N', 'n'
    }

    variables = set()

    # Pattern 1: X_{something} or X_{number} - subscripted variables
    # e.g., D_1, P_0, E[R_M], R_f, beta_i
    subscript_pattern = r'([a-zA-Z]+)_\{([^}]+)\}'
    for match in re.finditer(subscript_pattern, formula):
        var_base = match.group(1)
        subscript = match.group(2)
        if var_base.lower() not in exclude_commands:
            variables.add(f"{var_base}_{{{subscript}}}")

    # Pattern 2: X_y (single letter with single char subscript)
    # e.g., D_1, k_g, etc.
    # BUT exclude if the base letter is part of a Greek letter name
    single_subscript = r'([a-zA-Z])_([0-9a-zA-Z])(?![a-zA-Z])'
    greek_names = {'alpha', 'beta', 'gamma', 'delta', 'epsilon', 'theta', 'lambda',
                   'mu', 'sigma', 'phi', 'psi', 'omega', 'rho', 'eta', 'zeta', 'xi'}
    for match in re.finditer(single_subscript, formula):
        var_base = match.group(1)
        subscript = match.group(2)
        # Check if this single letter is part of a Greek letter name
        # by seeing if removing it leaves a valid Greek name
        for greek in greek_names:
            if var_base.lower() in greek and greek.replace(var_base.lower(), '', 1) in greek_names:
                # This single letter is part of a Greek name - skip
                break
        else:
            if var_base.lower() not in exclude_commands:
                variables.add(f"{var_base}_{subscript}")

    # Pattern 3: Greek letters with subscripts like \beta_i
    # Match whole \greekname_sub pattern
    greek_with_subscript = r'\\(alpha|beta|gamma|delta|epsilon|theta|lambda|mu|sigma|phi|psi|omega|rho|eta|zeta|xi)_([a-zA-Z0-9]+)'
    for match in re.finditer(greek_with_subscript, formula):
        greek_name = match.group(1)
        subscript = match.group(2)
        variables.add(f"\\{greek_name}_{subscript}")

    # Pattern 3b: Simple Greek letters (no subscript or already handled)
    greek = r'\\(alpha|beta|gamma|delta|epsilon|theta|lambda|mu|sigma|phi|psi|omega|rho|eta|zeta|xi)'
    for match in re.finditer(greek, formula):
        var_name = match.group(1)
        # Check if this Greek letter has a subscript that we already captured
        # If so, skip the bare Greek letter
        greek_with_any_sub = rf'\\{var_name}_[a-zA-Z0-9]'
        if re.search(greek_with_any_sub, formula):
            continue  # Already handled in pattern 3
        if var_name.lower() not in exclude_commands:
            variables.add(f"\\{var_name}")

    # Pattern 4: Bare common variables (single capital letters or known names)
    # Only match if they appear to be isolated (not part of a subscript)
    # Exclude letters that are followed by _ (part of subscripted var like P_0)
    bare_patterns = [
        r'(?<![\\a-zA-Z])([PDkcgrREFSVCI])(?![a-zA-Z{_])',  # Single capital/special, not before _
        r'(?<![\\])(ROE|Beta)(?![a-zA-Z])',  # Known multi-char
    ]

    for pattern in bare_patterns:
        for match in re.finditer(pattern, formula):
            var_name = match.group(1)
            if var_name not in exclude_commands:
                variables.add(var_name)

    # Post-filter: remove false positives
    filtered = set()
    for v in variables:
        # Skip single-letter_unrestricted-single-letter (e.g., a_i from beta_i)
        # Real subscripts usually have meaningful names or numbers
        if re.match(r'^[a-z]$', v.split('_')[0]) and re.match(r'^[a-z]$', v.split('_')[-1]) and len(v.split('_')) == 2:
            # This is x_y pattern - skip if both parts are single letters
            # Exception: some real variables like x_i might exist, but rare in this context
            continue

        if v.startswith('\\'):
            filtered.add(v)
        elif '_' in v:
            # Subscripted - keep it
            filtered.add(v)
            # Remove the base letter if it exists separately
            base = v.split('_')[0]
            filtered.discard(base)
        elif v in {'ROE', 'Beta'}:
            filtered.add(v)
        elif len(v) == 1 and v in common_vars:
            base_check = rf'{v}_'
            if not re.search(base_check, formula):
                filtered.add(v)

    return sorted(list(filtered), key=len, reverse=True)


def format_basic_card(concept, formula):
    """Create a Basic card (front: precise question, back: formula)"""
    # Generate a precise question from the concept
    front = f"{concept} の計算公式は？"
    back = f"\\[ {formula} \\]"
    return [front, back]


def format_basic_card_custom(concept, question, formula):
    """Create a Basic card with custom question"""
    return [question, f"\\[ {formula} \\]"]


def format_reversed_card(concept, formula):
    """Create a Reversed card (same data, different import type)"""
    return format_basic_card(concept, formula)


def format_cloze_card(concept, formula, hide_target, question_template=None):
    """
    Create a Cloze card with specific target hidden.

    Args:
        concept: The concept/title
        formula: The full LaTeX formula
        hide_target: Specific variable/part to hide (whole variable like D_1, not just D)
        question_template: Optional question about the hidden part
    """
    if hide_target and hide_target in formula:
        # Replace only the first occurrence to avoid issues with repeated variables
        # Use a placeholder approach to avoid nested braces
        cloze_formula = formula.replace(hide_target, f"__CLOZE_{hide_target}__", 1)
        cloze_formula = cloze_formula.replace(f"__CLOZE_{hide_target}__", f"{{{{c1::{hide_target}}}}}")
        if question_template:
            text = f"{question_template}<br>\\[ {cloze_formula} \\]"
        else:
            text = f"{concept}<br>\\[ {cloze_formula} \\]"
    else:
        text = f"{concept}<br>{{{{c1::\\[ {formula} \\]}}}}"

    return [text, ""]


def generate_variable_cloze_cards(concept, formula, variables=None):
    """
    Generate cloze cards for each variable in a formula.

    Args:
        concept: The concept/title
        formula: The full LaTeX formula
        variables: List of variables to hide (auto-detected if None)

    Returns:
        List of cloze cards, one per variable
    """
    if variables is None:
        variables = extract_variables(formula)

    cards = []
    # Sort by length descending to prefer compound variables (D_1) over single (D)
    sorted_vars = sorted(variables, key=len, reverse=True)

    for var in sorted_vars:
        # Skip very short single letters that are likely parts of other words
        if len(var) == 1 and var.lower() in {'a', 'b', 'c', 'd', 'e', 'f', 'i', 'n', 'o', 'r', 's', 't', 'x'}:
            continue
        # Skip LaTeX commands that slipped through
        if var.startswith('\\') and len(var) < 4:
            continue
        card = format_cloze_card(concept, formula, var)
        cards.append(card)

    return cards


def dispatch_card_creation(item, default_strategy="basic", auto_variables=False):
    """
    Create card(s) from a knowledge item.

    Args:
        item: dict with concept, formula, strategy (optional)
        default_strategy: "basic", "reversed", or "cloze"
        auto_variables: If True, generate one cloze per variable for cloze strategy
    """
    concept = item.get("concept", "")
    formula = item.get("formula", "")
    strategy = item.get("strategy", default_strategy)
    hide_target = item.get("hide_target", None)

    if strategy == "basic":
        return [format_basic_card(concept, formula)]
    elif strategy == "reversed":
        return [format_reversed_card(concept, formula)]
    elif strategy == "cloze":
        if auto_variables and not hide_target:
            # Generate one cloze card per variable
            return generate_variable_cloze_cards(concept, formula)
        else:
            return [format_cloze_card(concept, formula, hide_target)]
    else:
        raise ValueError(f"Unknown strategy: {strategy}")


def save_to_tsv(cards, filepath):
    """Save cards as TSV file"""
    if not cards:
        return False

    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)

    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerows(cards)

    print(f"Saved {len(cards)} cards to {filepath}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Convert markdown to Anki cards (Minimum Information Principle)"
    )
    parser.add_argument("input", help="Input markdown file")
    parser.add_argument("output_dir", help="Output directory for TSV files")
    parser.add_argument("--strategy", "-s", default="basic",
                        choices=["basic", "reversed", "cloze"],
                        help="Default card strategy")
    parser.add_argument("--auto-variables", "-a", action="store_true",
                        help="For cloze: generate one card per variable (not one card for whole formula)")
    parser.add_argument("--json", "-j", help="Optional JSON with per-item strategies")
    parser.add_argument("--list-variables", "-l", action="store_true",
                        help="List detected variables for each formula and exit")

    args = parser.parse_args()

    # Read markdown
    with open(args.input, 'r', encoding='utf-8') as f:
        markdown_text = f.read()

    # Parse
    items = parse_markdown(markdown_text)
    print(f"Found {len(items)} concept-formula pairs")

    if not items:
        print("No content found. Make sure markdown has ## headings and $$formula$$ blocks.")
        return

    # List variables mode
    if args.list_variables:
        print("\nDetected variables per formula:")
        for item in items:
            vars_list = extract_variables(item["formula"])
            print(f"  {item['concept']}: {item['formula']}")
            print(f"    → Variables: {vars_list}")
        return

    # Load custom strategies if provided
    custom_strategies = {}
    if args.json and os.path.exists(args.json):
        with open(args.json, 'r', encoding='utf-8') as f:
            custom_strategies = json.load(f)

    # Organize by strategy
    card_baskets = {"basic": [], "reversed": [], "cloze": []}

    for idx, item in enumerate(items):
        # Use custom strategy if provided for this concept
        strategy = custom_strategies.get(item["concept"], {}).get("strategy", args.strategy)

        # Check for hide_target in custom strategy
        hide_target = custom_strategies.get(item["concept"], {}).get("hide_target")

        # Check for custom question
        custom_question = custom_strategies.get(item["concept"], {}).get("question")

        cards = dispatch_card_creation({
            **item,
            "strategy": strategy,
            "hide_target": hide_target
        }, auto_variables=args.auto_variables)

        # If custom question provided for basic, modify the card
        if custom_question and strategy == "basic":
            cards = [format_basic_card_custom(item["concept"], custom_question, item["formula"])]

        card_baskets[strategy].extend(cards)

    # Save each type
    os.makedirs(args.output_dir, exist_ok=True)

    for strategy, cards in card_baskets.items():
        if cards:
            filepath = os.path.join(args.output_dir, f"export_{strategy}.txt")
            save_to_tsv(cards, filepath)

    print("\nDone! Import the TSV files into Anki:")
    print("  - export_basic.txt → Import as 'Basic'")
    print("  - export_reversed.txt → Import as 'Basic (and reversed card)'")
    print("  - export_cloze.txt → Import as 'Cloze'")

    if args.auto_variables:
        print("\n[auto-variables mode] Each variable in a formula got its own cloze card.")


if __name__ == "__main__":
    main()
