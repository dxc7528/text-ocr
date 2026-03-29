"""
Formula Processor — Deterministic LaTeX formula → Anki multi-cloze card generation.

Rules enforced:
- ALL RHS variables get independent cloze numbers (c1, c2, c3, ...)
- NO hints (never ::hint)
- LaTeX format preserved (never converted to prose)
- Same variable appearing multiple times → same cloze number
- Chain equalities (a = b = c) → split into separate cards
"""

import re
from dataclasses import dataclass, field


@dataclass
class AnkiCard:
    original_concept: str
    cloze_text: str
    card_type: str  # Formula, Definition, Causality, Contrast, Parallel, Sequential


# LaTeX commands that should NOT be treated as variables
LATEX_COMMANDS = {
    'frac', 'sqrt', 'times', 'cdot', 'quad', 'qquad',
    'left', 'right', 'begin', 'end', 'big', 'Big',
    'text', 'mathrm', 'mathbf', 'mathit', 'operatorname',
    'log', 'ln', 'sin', 'cos', 'tan', 'exp',
    'max', 'min', 'lim', 'sup', 'inf',
    'sum', 'prod', 'int', 'partial',
    'leq', 'geq', 'neq', 'approx', 'equiv',
    'circ', 'prime', 'to', 'infty', 'pm', 'mp',
    'over', 'displaystyle', 'scriptstyle',
}


def find_variable_occurrences(formula: str) -> list[tuple[int, int, str]]:
    """
    Find all variable occurrences in a formula string.

    Returns list of (start_pos, end_pos, variable_text) tuples.
    Uses priority-ordered pattern matching to avoid overlaps.
    """
    occurrences = []
    occupied = set()

    # Patterns in priority order (most specific / longest first)
    patterns = [
        # 1. \text{...} blocks (e.g. \text{配当性向})
        r'\\text\{[^}]+\}',
        # 2. Greek letters with optional subscripts (e.g. \beta_i, \sigma, \Delta)
        r'\\(?:alpha|beta|gamma|delta|epsilon|sigma|mu|phi|psi|omega|rho|tau|theta|lambda|eta|zeta|xi|Delta)(?:_\{[^}]+\}|_[a-zA-Z0-9])?',
        # 3. E[R_M] style — variable with bracket notation
        r'[A-Z]\[[^\]]+\]',
        # 4. Multi-letter var + braced subscript: FCFF_{1}
        r'[A-Z][a-zA-Z]+_\{[^}]+\}',
        # 5. Multi-letter var + single subscript: FCFF_1, EV_0
        r'[A-Z][a-zA-Z]+_[a-zA-Z0-9]',
        # 6. Single letter + braced subscript: k_{D}, D_{1}
        r'[a-zA-Z]_\{[^}]+\}',
        # 7. Single letter + single subscript: D_1, R_f, k_D, V_P
        r'[a-zA-Z]_[a-zA-Z0-9]',
        # 8. Multi-letter uppercase variables: ROE, WACC, FCFF, NOPAT, VaR
        r'[A-Z][a-zA-Z]{1,}',
        # 9. Japanese text tokens (consecutive CJK characters)
        r'[\u3000-\u303f\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff\uff00-\uffef]+',
        # 10. Single letter (fallback) — not part of LaTeX command or another var
        r'(?<![\\a-zA-Z_])[a-zA-Z](?![a-zA-Z\[\{_])',
    ]

    for pattern in patterns:
        for m in re.finditer(pattern, formula):
            match_positions = set(range(m.start(), m.end()))
            if match_positions & occupied:
                continue  # Overlaps with already-claimed match

            var_text = m.group(0)

            # Filter out LaTeX commands (e.g. \frac matched via Greek pattern fallback)
            if var_text.startswith('\\'):
                cmd_name = var_text[1:].split('_')[0].split('{')[0]
                if cmd_name.lower() in LATEX_COMMANDS:
                    continue

            occurrences.append((m.start(), m.end(), var_text))
            occupied |= match_positions

    return occurrences


def split_chain_equality(formula: str) -> list[tuple[str, str]]:
    """
    Split a chain equality into (LHS, RHS) pairs.

    'g = A \\times B = A \\times (1-C)' → [('g', 'A \\times B'), ('g', 'A \\times (1-C)')]
    'P_0 = \\frac{D}{k}' → [('P_0', '\\frac{D}{k}')]
    """
    # Find all top-level '=' signs (not inside braces/brackets/parens)
    parts = []
    depth = 0
    current = []
    for char in formula:
        if char in '{([':
            depth += 1
            current.append(char)
        elif char in '})]':
            depth -= 1
            current.append(char)
        elif char == '=' and depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    parts.append(''.join(current).strip())

    if len(parts) < 2:
        return []
    if len(parts) == 2:
        return [(parts[0], parts[1])]

    # Chain equality: first part is LHS, rest are individual RHS expressions
    lhs = parts[0]
    return [(lhs, rhs) for rhs in parts[1:] if rhs]


def apply_cloze_to_rhs(rhs: str, occurrences: list[tuple[int, int, str]]) -> str:
    """
    Replace variable occurrences in RHS with {{cN::variable}} markers.

    Same variable → same cloze number. No hints.
    Replaces right-to-left to preserve positions.
    """
    if not occurrences:
        return rhs

    # Assign cloze numbers to unique variables (in order of appearance)
    var_to_cloze: dict[str, int] = {}
    counter = 0
    for _, _, var_text in sorted(occurrences, key=lambda x: x[0]):
        if var_text not in var_to_cloze:
            counter += 1
            var_to_cloze[var_text] = counter

    # Replace right-to-left
    rhs_chars = list(rhs)
    for start, end, var_text in sorted(occurrences, key=lambda x: x[0], reverse=True):
        cloze_num = var_to_cloze[var_text]
        replacement = f"{{{{c{cloze_num}::{var_text}}}}}"
        rhs_chars[start:end] = list(replacement)

    return ''.join(rhs_chars)


def generate_formula_cards(label: str, formula: str) -> list[AnkiCard]:
    """
    Generate multi-cloze Anki cards from a single formula string.

    - Splits chain equalities into separate cards
    - Each RHS variable gets its own cloze number
    - No hints added
    - LaTeX preserved
    """
    cards = []
    pairs = split_chain_equality(formula)

    for lhs, rhs in pairs:
        occurrences = find_variable_occurrences(rhs)
        if not occurrences:
            continue

        cloze_rhs = apply_cloze_to_rhs(rhs, occurrences)
        cloze_formula = f"$${lhs} = {cloze_rhs}$$"
        cloze_text = f"{label}：{cloze_formula}"

        cards.append(AnkiCard(
            original_concept=label,
            cloze_text=cloze_text,
            card_type="Formula"
        ))

    return cards
