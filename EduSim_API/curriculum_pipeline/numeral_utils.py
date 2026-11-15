"""
EduSim Curriculum Pipeline — Unicode Numeral Normalization Utilities
Supports:
  - Standard ASCII digits (0-9)
  - Superscript numerals (⁰ ¹ ² ³ ⁴ ⁵ ⁶ ⁷ ⁸ ⁹)
  - Subscript numerals (₀ ₁ ₂ ₃ ₄ ₅ ₆ ₇ ₈ ₉)
  - Devanagari numerals (० १ २ ३ ४ ५ ६ ७ ८ ९)
  - Telugu numerals (౦ ౧ ౨ ౩ ౪ ౫ ౬ ౭ ౮ ౯)
  - Arabic-Indic numerals (٠ ١ ٢ ٣ ٤ ٥ ٦ ٧ ٨ ٩)
  - Fullwidth numerals (０ １ ２ ３ ４ ５ ６ ７ ８ ９)
  - General Unicode numeric characters via NFKD / unicodedata
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional


# Explicit fast-path character mapping table
UNICODE_NUMERAL_MAP = {
    # Superscripts
    "\u2070": "0", "\u00B9": "1", "\u00B2": "2", "\u00B3": "3", "\u2074": "4",
    "\u2075": "5", "\u2076": "6", "\u2077": "7", "\u2078": "8", "\u2079": "9",
    # Subscripts
    "\u2080": "0", "\u2081": "1", "\u2082": "2", "\u2083": "3", "\u2084": "4",
    "\u2085": "5", "\u2086": "6", "\u2087": "7", "\u2088": "8", "\u2089": "9",
    # Devanagari
    "\u0966": "0", "\u0967": "1", "\u0968": "2", "\u0969": "3", "\u096A": "4",
    "\u096B": "5", "\u096C": "6", "\u096D": "7", "\u096E": "8", "\u096F": "9",
    # Telugu
    "\u0C66": "0", "\u0C67": "1", "\u0C68": "2", "\u0C69": "3", "\u0C6A": "4",
    "\u0C6B": "5", "\u0C6C": "6", "\u0C6D": "7", "\u0C6E": "8", "\u0C6F": "9",
    # Arabic-Indic
    "\u0660": "0", "\u0661": "1", "\u0662": "2", "\u0663": "3", "\u0664": "4",
    "\u0665": "5", "\u0666": "6", "\u0667": "7", "\u0668": "8", "\u0669": "9",
    # Fullwidth
    "\uFF10": "0", "\uFF11": "1", "\uFF12": "2", "\uFF13": "3", "\uFF14": "4",
    "\uFF15": "5", "\uFF16": "6", "\uFF17": "7", "\uFF18": "8", "\uFF19": "9",
}

NUMERAL_TRANS_TABLE = str.maketrans(UNICODE_NUMERAL_MAP)


def normalize_unicode_numerals(s: str) -> str:
    """
    Normalizes any Unicode numeral characters (superscripts, subscripts,
    Devanagari, Telugu, Arabic-Indic, fullwidth) into standard ASCII '0'-'9'.
    Preserves all other characters intact.
    """
    if not s:
        return ""
    # 1. Translate explicit numeral sets
    translated = s.translate(NUMERAL_TRANS_TABLE)
    # 2. Decompose compatibility characters via NFKD
    normalized = unicodedata.normalize("NFKD", translated)
    return normalized


def safe_int(val: Any, default: Optional[int] = None) -> Optional[int]:
    """
    Safely converts a string/number to int after normalizing Unicode numerals.
    Never throws ValueError or TypeError; returns default if conversion is impossible.
    """
    if val is None:
        return default
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        try:
            return int(val)
        except (ValueError, OverflowError):
            return default

    s = str(val).strip()
    if not s:
        return default

    # Normalize Unicode numerals first
    s_norm = normalize_unicode_numerals(s)

    # 1. Direct integer parse
    try:
        return int(s_norm)
    except (ValueError, TypeError):
        pass

    # 2. Extract digits if surrounded by punctuation or labels (e.g. 'Chapter 2', '2.', '1.2')
    m = re.search(r"\b\d+\b", s_norm)
    if m:
        try:
            return int(m.group(0))
        except (ValueError, TypeError):
            pass

    # 3. Check for standalone floating point string (e.g. '3.0')
    try:
        f_val = float(s_norm)
        if f_val.is_integer():
            return int(f_val)
    except (ValueError, TypeError):
        pass

    return default


def is_numeric_numeral(s: str) -> bool:
    """Returns True if the string represents a valid integer after Unicode numeral normalization."""
    return safe_int(s) is not None
