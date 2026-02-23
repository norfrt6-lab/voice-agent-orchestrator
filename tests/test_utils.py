"""Tests for shared utility functions."""

from src.utils import normalize_phone


class TestNormalizePhone:
    def test_strips_spaces(self):
        assert normalize_phone("0412 345 678") == "0412345678"

    def test_strips_dashes(self):
        assert normalize_phone("0412-345-678") == "0412345678"

    def test_strips_parentheses(self):
        assert normalize_phone("(04) 1234 5678") == "0412345678"

    def test_preserves_leading_plus(self):
        assert normalize_phone("+61 412 345 678") == "+61412345678"

    def test_clean_number_unchanged(self):
        assert normalize_phone("0412345678") == "0412345678"

    def test_strips_whitespace(self):
        assert normalize_phone("  0412345678  ") == "0412345678"

    def test_mixed_separators(self):
        assert normalize_phone("+61 (412) 345-678") == "+61412345678"
