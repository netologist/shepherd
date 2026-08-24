"""Safe coercion helpers to prevent Pydantic validation failures from LLM outputs."""

from typing import Any
import re


def safe_float_coerce(v: Any) -> float:
    """Coerce string/None values like 'N/A', '<UNKNOWN>', '23.5%' to safe float."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        cleaned = v.strip().rstrip("%").strip()
        # Extract first valid numeric match if embedded in text
        match = re.search(r"[-+]?\d*\.?\d+", cleaned)
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return 0.0
    return 0.0


def safe_int_coerce(v: Any) -> int:
    """Coerce string/None values to safe int."""
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        cleaned = v.strip()
        match = re.search(r"[-+]?\d+", cleaned)
        if match:
            try:
                return int(match.group(0))
            except ValueError:
                return 0
    return 0


def safe_str_list_coerce(v: Any) -> list[str]:
    """Coerce single string or None into list of strings."""
    if v is None:
        return []
    if isinstance(v, list):
        return [str(item) for item in v if item is not None]
    if isinstance(v, str):
        if not v.strip():
            return []
        if "," in v:
            return [part.strip() for part in v.split(",") if part.strip()]
        return [v.strip()]
    return [str(v)]
