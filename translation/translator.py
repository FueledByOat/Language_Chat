"""
translator.py

This module provides functions to translate between the target language and English  using the googletrans library.
"""

from googletrans import Translator

# Constants
TRANSLATOR = Translator()

# Variables

def translate_target_to_english(input_text, tl = "zh-cn"):
    """
    Uses the the google translate library to translate text from a target input language to English

    Parameters:
    input_text (string): the text in the target language to be translated to English.
    tl (string): Target language langauge code 

    Output:
    string:  the translated text in English 
    """
    translated = TRANSLATOR.translate(input_text, src = tl, dest = 'en')
    print(f"Input: {translated.text}")
    return translated.text


def translate_english_to_target(output_text, tl = "zh-cn"):
    """
    Uses the the google translate library to translate text from English to a target input language 

    Parameters:
    output_text (string): the text in English to be translated to the target language.
    tl (string): Target language langauge code 

    Output:
    string:  the translated text in the target language 
    """
    translated = TRANSLATOR.translate(output_text, src='en', dest=tl)
    print(translated.text)  
    return translated.text