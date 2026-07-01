import math
import re
import statistics


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"[.!?]+", text)
    return [s.strip() for s in parts if s.strip()]


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def _sentence_length_variance_score(text: str) -> float:
    sentences = _split_sentences(text)
    if len(sentences) < 2:
        return 0.5
    lengths = [len(s.split()) for s in sentences]
    variance = statistics.variance(lengths) if len(lengths) > 1 else 0.0
    # Low variance → AI-like (high score); high variance → human-like (low score)
    return max(0.0, min(1.0, 1.0 - math.tanh(variance / 15.0)))


def _type_token_ratio_score(text: str) -> float:
    tokens = _tokenize(text)
    if len(tokens) < 5:
        return 0.5
    ttr = len(set(tokens)) / len(tokens)
    # Low TTR → AI-like; high TTR → human-like
    return max(0.0, min(1.0, 1.0 - ttr * 1.5))


def _punctuation_density_score(text: str) -> float:
    words = _tokenize(text)
    if not words:
        return 0.5
    punct_count = len(re.findall(r"[,;:—–\-()\"']", text))
    density = punct_count / len(words)
    # AI text tends toward moderate, regular punctuation (~0.05–0.15 per word)
    optimal = 0.10
    deviation = abs(density - optimal)
    return max(0.0, min(1.0, 1.0 - deviation * 5.0))


def get_stylometric_score(text: str) -> float:
    """
    Signal 2: Stylometric heuristics.
    Returns a score in [0.0, 1.0] where higher = more likely AI-generated.
    """
    scores = [
        _sentence_length_variance_score(text),
        _type_token_ratio_score(text),
        _punctuation_density_score(text),
    ]
    return round(sum(scores) / len(scores), 4)
