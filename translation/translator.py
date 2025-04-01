"""
translator.py

This module provides functions to translate between the target language and English  using the googletrans library.
"""

from deep_translator import GoogleTranslator

def translate_target_to_english(input_text, language = "chinese"):
    """
    Uses the the google translate library to translate text from a target input language to English

    Parameters:
    input_text (string): the text in the target language to be translated to English.
    langauge (string): Language to converse in, defaulting to Chinese

    Output:
    string:  the translated text in English 
    """
    #  tl (string): Target language langauge code 
    tl = "zh-CN" if language == "chinese" else "ja"
    # translated = await TRANSLATOR.translate(input_text, dest = 'en', src = tl)
    translated = GoogleTranslator(source = tl, target = "en").translate(input_text)
    print(f"Input: {translated}")
    return translated


def translate_english_to_target(output_text, language = "chinese"):
    """
    Uses the the google translate library to translate text from English to a target input language 

    Parameters:
    output_text (string): the text in English to be translated to the target language.
    langauge (string): Language to converse in, defaulting to Chinese

    Output:
    string:  the translated text in the target language 
    """
    #   tl (string): Target language langauge code 
    tl = "zh-CN" if language == "chinese" else "ja"
    # translated = await TRANSLATOR.translate(output_text, dest=tl, src='en')
    translated = GoogleTranslator(source = "en", target = tl).translate(output_text)
    print(translated)  
    return translated