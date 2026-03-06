"""
Sanitize user search query for safe use in Elasticsearch match/match_phrase/match_phrase_prefix.

Food names in our data use: comma (,), hyphen (-), period (.), percent (%), parentheses ().
We allow those so users can search e.g. "milk 2%" or "pan-fried".
We strip or replace characters that could break the request or be interpreted as operators:
  + ; " \\ * ? [ ] { } ^ : / & | and other control/reserved characters.
Hyphen: kept when word-internal (e.g. pan-fried); leading/trailing or standalone " - " replaced with space.
"""

import re


# Pattern: any character that is not allowed. Allowed: letters, digits, space, comma, hyphen, period, %, apostrophe, parentheses.
_NOT_ALLOWED_PATTERN = re.compile(r"[^a-zA-Z0-9\s,\-\.%'()]")

# Space-hyphen-space or leading/trailing hyphen (so hyphen is not word-internal).
_STANDALONE_HYPHEN_PATTERN = re.compile(r"\s-\s|^-|-$")


def sanitize_search_query(query: str) -> str:
    """
    Return a safe query string: only allowed characters kept, others replaced with space,
    standalone hyphens normalized, whitespace collapsed and stripped.
    """
    if not query or not isinstance(query, str):
        return ""

    s = query.strip()
    if not s:
        return ""

    # Replace reserved/special characters with space.
    s = _NOT_ALLOWED_PATTERN.sub(" ", s)

    # Replace " - " (space-hyphen-space) and leading/trailing hyphen with space.
    s = _STANDALONE_HYPHEN_PATTERN.sub(" ", s)

    # Collapse multiple spaces and strip.
    s = " ".join(s.split())
    return s.strip()
