# src/keyword_extractor/keyword_extractor.py
from keybert import KeyBERT


class SentenceBert:
    def __init__(self, model: str | None = None):
        self.kw_model = KeyBERT(model=model)

    def extract_keywords(self, sentence: str, top_n: int = 5) -> list[str]:
        if not sentence or not sentence.strip():
            return []

        keywords = self.kw_model.extract_keywords(
            sentence,
            keyphrase_ngram_range=(1, 1),
            stop_words="english",
            top_n=top_n,
            use_mmr=True,
            diversity=0.7,
        )

        return [word for word, _ in keywords]
