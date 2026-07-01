from services.scoring import AI_THRESHOLD, HUMAN_THRESHOLD


def generate_label(confidence: float) -> str:
    pct = int(round(confidence * 100))

    if confidence >= AI_THRESHOLD:
        return (
            f"Likely AI-Generated — This content was assessed as likely AI-generated "
            f"(confidence: {pct}%). Our analysis detected patterns consistent with "
            f"AI-assisted writing, including uniform sentence structure and "
            f"characteristic phrasing. If you believe this assessment is incorrect, "
            f"you may submit an appeal."
        )

    if confidence <= HUMAN_THRESHOLD:
        return (
            f"Likely Human-Written — This content was assessed as likely human-written "
            f"(confidence: {pct}%). Writing patterns — including natural variation in "
            f"sentence length and vocabulary — suggest authentic human authorship."
        )

    return (
        f"Attribution Uncertain — We could not confidently determine authorship "
        f"(confidence: {pct}%). The text shows mixed signals from our analysis. "
        f"Manual review is recommended if provenance is important. You may submit "
        f"an appeal with additional context."
    )
