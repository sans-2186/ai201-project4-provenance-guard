LLM_WEIGHT = 0.60
STYLOMETRIC_WEIGHT = 0.40

AI_THRESHOLD = 0.65
HUMAN_THRESHOLD = 0.35


def combine_scores(llm_score: float, stylometric_score: float) -> float:
    """Weighted combination of both detection signals."""
    confidence = LLM_WEIGHT * llm_score + STYLOMETRIC_WEIGHT * stylometric_score
    return round(max(0.0, min(1.0, confidence)), 4)


def classify_attribution(confidence: float) -> str:
    if confidence >= AI_THRESHOLD:
        return "likely_ai"
    if confidence <= HUMAN_THRESHOLD:
        return "likely_human"
    return "uncertain"
