"""Text utilities for handling LLM-generated content with special formats.

LLM outputs often wrap structured data (JSON, code) in markdown code fences
like ```` ```json\n{...}\n``` ````. These utilities strip such wrappers so
the underlying content can be parsed and used directly.

Supported fence patterns:
  - ```json ... ```        (JSON code blocks)
  - ```python ... ```      (Python code blocks)
  - ``` ... ```            (generic code blocks)
  - ```\n ... \n```        (bare fences with no language tag)
  - `` `...` ``            (inline code — single backtick pair)

Also handles:
  - Leading/trailing whitespace
  - BOM characters
  - Leading prose before the fence (e.g. "Here is the JSON:\n```json\n...")
  - Trailing prose after the fence
"""

from __future__ import annotations

import re
from typing import Any

__all__ = [
    "strip_code_fences",
    "extract_json_from_text",
    "clean_llm_output",
    "try_parse_json_lenient",
]


# Regex for fenced code blocks: ```lang\n...\n``` or ```\n...\n```
# Captures optional language tag and the inner content.
# Uses non-greedy matching and allows the fence to appear anywhere in the text.
_FENCED_CODE_RE = re.compile(
    r"```[a-zA-Z0-9_+-]*\s*\n?(.*?)```",
    re.DOTALL,
)

# Regex for inline code: `...` (single backtick, not triple)
# Only matches when not preceded/followed by additional backticks.
_INLINE_CODE_RE = re.compile(
    r"(?<!`)`([^`\n]+)`(?!`)",
)


def strip_code_fences(text: str) -> str:
    """Remove markdown code fences from *text*, returning the inner content.

    If the text contains a fenced code block, the **first** fence's content
    is returned (stripped of surrounding whitespace). If no fence is found,
    the original text is returned unchanged (after stripping whitespace).

    Examples:
        >>> strip_code_fences('```json\\n{"key": "value"}\\n```')
        '{"key": "value"}'
        >>> strip_code_fences('```\\nprint("hello")\\n```')
        'print("hello")'
        >>> strip_code_fences('plain text')
        'plain text'
        >>> strip_code_fences('Here is the result:\\n```json\\n[1, 2, 3]\\n```\\nDone.')
        '[1, 2, 3]'
    """
    if not isinstance(text, str):
        return text

    # Try fenced code block first (```...```)
    match = _FENCED_CODE_RE.search(text)
    if match:
        inner = match.group(1).strip()
        if inner:
            return inner

    # Try inline code (`...`) — only if the entire text is just the inline code
    inline_match = _INLINE_CODE_RE.match(text.strip())
    if inline_match:
        return inline_match.group(1).strip()

    return text.strip()


def extract_json_from_text(text: str) -> str | None:
    """Extract a JSON string from *text* that may be wrapped in code fences
    or embedded in prose.

    Returns the extracted JSON string (without fences), or ``None`` if no
    JSON-like content is found.

    Tries these strategies in order:
    1. Strip code fences and check if result starts with ``[`` or ``{``
    2. Search for the first ``{...}`` or ``[...]`` block in the text
    3. Return ``None`` if nothing found
    """
    if not isinstance(text, str) or not text.strip():
        return None

    # Strategy 1: strip fences and check
    stripped = strip_code_fences(text)
    if stripped and stripped[0] in ('[', '{'):
        return stripped

    # Strategy 2: find first JSON-like block using brace/bracket matching
    for opener, closer in (('{', '}'), ('[', ']')):
        start = text.find(opener)
        if start == -1:
            continue
        # Simple depth-counting bracket matcher
        depth = 0
        in_string = False
        escape_next = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape_next:
                escape_next = False
                continue
            if ch == '\\':
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1].strip()
                    return candidate

    return None


def clean_llm_output(text: str) -> str:
    """Clean up common LLM output artifacts.

    Removes:
    - BOM characters (\\ufeff)
    - Leading/trailing whitespace
    - Markdown code fences (when the entire content is a single fenced block)
    - Leading "Here is..." / "Sure..." / "Below is..." prose before a fence

    Does NOT modify text that has no fences — preserves mixed content.
    """
    if not isinstance(text, str):
        return text

    # Remove BOM
    cleaned = text.lstrip('\ufeff')

    # If the text is primarily a code fence (possibly with leading/trailing
    # prose), extract just the fenced content.
    fence_match = _FENCED_CODE_RE.search(cleaned)
    if fence_match:
        inner = fence_match.group(1).strip()
        if inner:
            # Check if the fenced content looks like structured data
            # (starts with { or [ or is multi-line code)
            if inner[0] in ('{', '[') or '\n' in inner:
                return inner

    return cleaned.strip()


def try_parse_json_lenient(value: Any) -> Any:
    """Parse *value* as JSON, tolerating code fences and surrounding prose.

    This is a drop-in replacement for the existing ``_try_parse_json``
    functions in ``executor.py`` and ``codegen.py``. It:

    1. Passes through non-string values unchanged.
    2. Strips markdown code fences if present.
    3. Attempts ``json.loads()`` on the cleaned string.
    4. Falls back to extracting JSON from prose if direct parse fails.
    5. Returns the original value if all attempts fail.

    Examples:
        >>> try_parse_json_lenient('```json\\n{"a": 1}\\n```')
        {'a': 1}
        >>> try_parse_json_lenient('Here is the data:\\n```\\n[1, 2, 3]\\n```')
        [1, 2, 3]
        >>> try_parse_json_lenient('{"a": 1}')
        {'a': 1}
        >>> try_parse_json_lenient('not json')
        'not json'
    """
    if not isinstance(value, str):
        return value

    import json

    stripped = value.strip()
    if not stripped:
        return value

    # Step 1: Strip code fences
    unfenced = strip_code_fences(stripped)

    # Step 2: Try direct JSON parse on unfenced content
    if unfenced and unfenced[0] in ('[', '{'):
        try:
            return json.loads(unfenced)
        except (json.JSONDecodeError, ValueError):
            pass

    # Step 3: Try extracting JSON from prose (handles "Here is...: {json}")
    extracted = extract_json_from_text(stripped)
    if extracted and extracted != unfenced:
        try:
            return json.loads(extracted)
        except (json.JSONDecodeError, ValueError):
            pass

    # Step 4: If original starts with [ or { (no fence), try that too
    if stripped[0] in ('[', '{'):
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            pass

    return value
