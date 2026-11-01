import sys
import unittest

from curriculum_pipeline.page_extractor import (
    normalize_devanagari,
    compute_page_quality_metrics,
    detect_script,
)
from curriculum_pipeline.chunker import CurriculumChunker


class TestTextQualityGate(unittest.TestCase):
    def test_devanagari_normalization_broken_sample(self):
        """Test normalization on known broken conjunct string with stray ZWJ and repeated halant."""
        broken_sample = "पंक््\u200dतति"
        normalized = normalize_devanagari(broken_sample)
        self.assertEqual(normalized, "पंक्ति")

    def test_devanagari_normalization_shakti(self):
        """Test normalization on another ligature pattern: शक््\u200dतति -> शक्ति."""
        broken = "शक््\u200dतति"
        self.assertEqual(normalize_devanagari(broken), "शक्ति")

    def test_devanagari_normalization_clean_text_preserved(self):
        """Clean Hindi text remains unaltered."""
        clean = "यह एक स्वच्छ और सुंदर हिंदी वाक्य है।"
        self.assertEqual(normalize_devanagari(clean), clean)

    def test_quality_gate_control_chars_trigger_garbled(self):
        """Control chars exceeding 2% trigger garbled classification."""
        # 10 control chars in a 100 char string = 10% > 2%
        text = "Hello world " + "\x07\x1f\x03\x0e\x14\x01\x02\x04\x05\x06" + " " * 80
        metrics = compute_page_quality_metrics(text, expected_lang="eng")
        self.assertTrue(metrics["is_garbled"])
        self.assertGreater(metrics["control_char_ratio"], 0.02)

    def test_quality_gate_replacement_chars_trigger_garbled(self):
        """PUA or replacement chars exceeding 5% trigger garbled classification."""
        text = "Valid text " + "\ufffd" * 10 + " " * 80
        metrics = compute_page_quality_metrics(text, expected_lang="eng")
        self.assertTrue(metrics["is_garbled"])
        self.assertGreater(metrics["replacement_char_ratio"], 0.05)

    def test_quality_gate_outside_script_telugu_trigger_garbled(self):
        """Telugu book with legacy font glyphs (ASCII/Latin) triggers garbled classification."""
        garbled_legacy = "u\x0e e!\x93+Ý\x03¡ This is actually legacy font Telugu glyphs that decode as Latin."
        metrics = compute_page_quality_metrics(garbled_legacy, expected_lang="tel")
        self.assertTrue(metrics["is_garbled"])
        self.assertGreater(metrics["outside_script_ratio"], 0.50)

    def test_quality_gate_clean_pages_pass(self):
        """Clean Telugu, Hindi, and English text passes with is_garbled=False."""
        clean_tel = "ఇది ఒక మంచి తెలుగు వాక్యము. విద్యార్థులు చదువుకుంటున్నారు."
        metrics_tel = compute_page_quality_metrics(clean_tel, expected_lang="tel")
        self.assertFalse(metrics_tel["is_garbled"])

        clean_hin = "यह एक स्वच्छ हिंदी वाक्य है जिसमें सभी वर्ण सही हैं।"
        metrics_hin = compute_page_quality_metrics(clean_hin, expected_lang="hin")
        self.assertFalse(metrics_hin["is_garbled"])

        clean_eng = "Newton's second law of motion states that force equals mass times acceleration."
        metrics_eng = compute_page_quality_metrics(clean_eng, expected_lang="eng")
        self.assertFalse(metrics_eng["is_garbled"])

    def test_chunker_skips_garbled_page(self):
        """CurriculumChunker.classify_page_skip skips pages with status='garbled'."""
        chunker = CurriculumChunker.__new__(CurriculumChunker)
        garbled_prec = {
            "page_no": 9,
            "text": "garbled text...",
            "status": "garbled",
            "ocr_needed": True,
        }
        skip, reason = chunker.classify_page_skip(
            text=garbled_prec["text"],
            page_no=9,
            is_whole_book=True,
            first_ch_start=1,
            ch_title="Chapter 1",
            page_record=garbled_prec,
        )
        self.assertTrue(skip)
        self.assertEqual(reason, "garbled_text_quality_gate")


if __name__ == "__main__":
    unittest.main()
