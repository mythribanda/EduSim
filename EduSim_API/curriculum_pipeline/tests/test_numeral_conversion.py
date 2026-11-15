"""
EduSim Curriculum Pipeline — Regression Tests for Unicode Numeral Conversion
Tests exact failing characters from:
  - dhve.pdf: '²' (superscript 2)
  - jemh.pdf: '¹' (superscript 1)
  - Devanagari, Telugu, subscripts, fullwidth, and graceful fallback.
"""

import unittest
from curriculum_pipeline.numeral_utils import (
    is_numeric_numeral,
    normalize_unicode_numerals,
    safe_int,
)


class TestUnicodeNumeralConversion(unittest.TestCase):
    def test_exact_failing_characters_dhve_and_jemh(self):
        """Test exact characters that caused dhve.pdf ('²') and jemh.pdf ('¹') to crash."""
        # dhve.pdf exact failing character: '²' (U+00B2)
        self.assertEqual(normalize_unicode_numerals("²"), "2")
        self.assertEqual(safe_int("²"), 2)
        self.assertTrue(is_numeric_numeral("²"))

        # jemh.pdf exact failing character: '¹' (U+00B9)
        self.assertEqual(normalize_unicode_numerals("¹"), "1")
        self.assertEqual(safe_int("¹"), 1)
        self.assertTrue(is_numeric_numeral("¹"))

    def test_all_superscript_numerals(self):
        superscripts = "⁰¹²³⁴⁵⁶⁷⁸⁹"
        for idx, char in enumerate(superscripts):
            self.assertEqual(normalize_unicode_numerals(char), str(idx))
            self.assertEqual(safe_int(char), idx)
            self.assertTrue(is_numeric_numeral(char))

    def test_all_subscript_numerals(self):
        subscripts = "₀₁₂₃₄₅₆₇₈₉"
        for idx, char in enumerate(subscripts):
            self.assertEqual(normalize_unicode_numerals(char), str(idx))
            self.assertEqual(safe_int(char), idx)

    def test_devanagari_numerals(self):
        deva = ["०", "१", "२", "३", "४", "५", "६", "७", "८", "९"]
        for idx, char in enumerate(deva):
            self.assertEqual(normalize_unicode_numerals(char), str(idx))
            self.assertEqual(safe_int(char), idx)
        self.assertEqual(safe_int("१२"), 12)
        self.assertEqual(safe_int("२५"), 25)

    def test_telangana_telugu_numerals(self):
        telugu = ["౦", "౧", "౨", "౩", "౪", "౫", "౬", "౭", "౮", "౯"]
        for idx, char in enumerate(telugu):
            self.assertEqual(normalize_unicode_numerals(char), str(idx))
            self.assertEqual(safe_int(char), idx)
        self.assertEqual(safe_int("౧౦"), 10)

    def test_heading_strings_with_unicode_numerals(self):
        self.assertEqual(normalize_unicode_numerals("Chapter ²"), "Chapter 2")
        self.assertEqual(safe_int("Chapter ²"), 2)
        self.assertEqual(normalize_unicode_numerals("अध्याय ३"), "अध्याय 3")
        self.assertEqual(safe_int("अध्याय ३"), 3)
        self.assertEqual(normalize_unicode_numerals("1.² Introduction"), "1.2 Introduction")

    def test_graceful_handling_invalid_values(self):
        """Ensures safe_int never raises ValueError or TypeError on invalid or empty input."""
        self.assertIsNone(safe_int(None))
        self.assertIsNone(safe_int(""))
        self.assertIsNone(safe_int("   "))
        self.assertIsNone(safe_int("non-numeric text"))
        self.assertEqual(safe_int("abc", default=99), 99)
        self.assertEqual(safe_int(None, default=0), 0)


if __name__ == "__main__":
    unittest.main()
