"""
Module 6: Code Extraction Module
- Detect code blocks within mixed text
- Separate code from descriptive text
- Save extracted code snippets
- Prepare code for execution
"""
import re
from typing import List, Dict


def extract_code_blocks(text: str) -> List[Dict[str, str]]:
    """
    Extract code blocks from text. Handles:
    1. Markdown-style fenced code blocks (```language ... ```)
    2. Indentation-based code blocks (4+ spaces or tab indented)
    3. Heuristic-based detection for inline code patterns
    """
    blocks = []

    # 1. Markdown fenced code blocks
    fenced_pattern = r"```(\w*)\n(.*?)```"
    for match in re.finditer(fenced_pattern, text, re.DOTALL):
        lang = match.group(1).strip() or "unknown"
        code = match.group(2).strip()
        if code:
            blocks.append({"language": lang, "code": code, "source": "fenced"})

    # Remove fenced blocks from text for further analysis
    remaining = re.sub(fenced_pattern, "", text, flags=re.DOTALL)

    # 2. Indentation-based code blocks (consecutive lines with 4+ spaces or tab)
    lines = remaining.split("\n")
    current_block = []
    for line in lines:
        if re.match(r"^(\s{4,}|\t)", line) and line.strip():
            current_block.append(line)
        else:
            if len(current_block) >= 2:
                code = "\n".join(current_block)
                blocks.append({"language": "unknown", "code": code.strip(), "source": "indented"})
            current_block = []
    if len(current_block) >= 2:
        code = "\n".join(current_block)
        blocks.append({"language": "unknown", "code": code.strip(), "source": "indented"})

    # 3. Heuristic: detect code-like contiguous blocks
    if not blocks:
        blocks.extend(_heuristic_code_detection(remaining))

    return blocks


def _heuristic_code_detection(text: str) -> List[Dict[str, str]]:
    """Detect code using syntax heuristics when no explicit markers exist."""
    blocks = []
    lines = text.split("\n")
    code_lines = []
    code_indicators = [
        r"^\s*(def |class |import |from |#include|public |private |void |int |float )",
        r"[{};]\s*$",
        r"^\s*(if|else|for|while|return|try|catch|switch)\s*[\({]",
        r"^\s*(print|printf|cout|console\.log|System\.out)\s*\(",
        r"^\s*#\s*(include|define|ifdef)",
        r"=\s*(new|function|=>)",
    ]

    for line in lines:
        is_code = any(re.search(p, line) for p in code_indicators)
        if is_code:
            code_lines.append(line)
        else:
            if len(code_lines) >= 3:
                blocks.append({
                    "language": "unknown",
                    "code": "\n".join(code_lines).strip(),
                    "source": "heuristic",
                })
            code_lines = []

    if len(code_lines) >= 3:
        blocks.append({
            "language": "unknown",
            "code": "\n".join(code_lines).strip(),
            "source": "heuristic",
        })

    return blocks


def separate_code_and_text(text: str) -> Dict[str, any]:
    """
    Split a document into code sections and descriptive text sections.
    Returns structured output ready for different grading pipelines.
    """
    code_blocks = extract_code_blocks(text)

    # Remove code from original text to get pure descriptive text
    descriptive = text
    for block in code_blocks:
        descriptive = descriptive.replace(block["code"], "")

    # Clean up excessive whitespace in descriptive part
    descriptive = re.sub(r"\n{3,}", "\n\n", descriptive).strip()

    return {
        "code_blocks": code_blocks,
        "descriptive_text": descriptive,
        "has_code": len(code_blocks) > 0,
        "code_count": len(code_blocks),
    }
