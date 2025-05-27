# tests/test_utils.py
from translation.translator import Translator # Adjust import

# ================================
# Test translator.py
# ================================

def test_translate_to_english_from_chinese():
    assert Translator().translate_to_english("车").lower() == "car"

def test_translate_to_english_from_japanese():
    assert Translator().translate_to_english("車").lower() == "car"

def test_translate_from_english_from_chinese():
    assert Translator().translate_from_english("day") == "天"

def test_translate_from_english_from_japanese():
    assert Translator().translate_from_english("day") == "日"