import jieba
import pypinyin
from fugashi import Tagger
import jaconv


class NLPService:
    def __init__(self):
        # Initialize Japanese Tagger (MeCab wrapper)
        self.jp_tagger = Tagger("-Owakati")

    def process_japanese(self, text: str):
        # Fugashi gives us nodes with access to reading/lemma
        tagger = Tagger()
        tokens = []
        for word in tagger(text):
            # feature indices: 0=pos, 6=base form, 7=reading (katakana)
            # If reading is missing (punctuation), use the surface form
            reading_katakana = word.feature.kana if word.feature.kana else ""

            # Convert Katakana reading to Hiragana for standard Furigana
            reading_hiragana = jaconv.kata2hira(reading_katakana)

            tokens.append(
                {
                    "surface": word.surface,  # The word as seen in text
                    "base": word.feature.lemma,  # Dictionary form (for SRS matching)
                    "reading": reading_hiragana,  # For the ruby tag
                    "pos": word.feature.pos1,  # Part of speech (to filter particles if needed)
                }
            )
        return tokens

    def process_chinese(self, text: str):
        # Jieba for segmentation
        seg_list = list(jieba.cut(text))
        tokens = []

        for word in seg_list:
            # pypinyin to generate tones
            # style=pypinyin.NORMAL returns 'ni' (no tone)
            # style=pypinyin.TONE returns 'nǐ' (with tone marks)
            pinyin_list = pypinyin.pinyin(word, style=pypinyin.Style.TONE)
            # flatten list of lists
            flat_pinyin = [item for sublist in pinyin_list for item in sublist]
            reading = "".join(flat_pinyin)

            tokens.append(
                {
                    "surface": word,
                    "base": word,  # Chinese doesn't have conjugation, so base == surface
                    "reading": reading,
                    "pos": "unknown",  # Jieba has pos tagging but requires 'jieba.posseg'
                }
            )
        return tokens


# Usage Example
nlp = NLPService()
# result = nlp.process_japanese("猫が水を飲みます")
# Result: [{'surface': '猫', 'base': '猫', 'reading': 'ねこ'...}, {'surface': 'が', ...}]
