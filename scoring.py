"""Confidence scoring + transparency label selection.

Combines the two signals into one calibrated confidence and maps the result to
an attribution and a plain-language label. Thresholds are asymmetric: it takes
stronger evidence to call text AI than to clear it as human, because a false
positive (accusing a human) is worse than a false negative.
"""

LLM_WEIGHT = 0.60
STYLO_WEIGHT = 0.40

AI_THRESHOLD = 0.72      # ai_score >= this -> likely_ai
HUMAN_THRESHOLD = 0.32   # ai_score <= this -> likely_human


def combine(llm_score, stylo_score):
    """Return (ai_score, attribution, confidence).

    ai_score   = weighted P(AI), 0..1
    confidence = certainty of the verdict, 0 (coin-flip) .. 1 (certain)
    """
    ai_score = LLM_WEIGHT * llm_score + STYLO_WEIGHT * stylo_score
    confidence = round(min(1.0, 2 * abs(ai_score - 0.5)), 2)

    if ai_score >= AI_THRESHOLD:
        attribution = "likely_ai"
    elif ai_score <= HUMAN_THRESHOLD:
        attribution = "likely_human"
    else:
        attribution = "uncertain"

    return round(ai_score, 3), attribution, confidence


def label_for(attribution, confidence):
    """Plain-language transparency label. Three variants; text varies with the
    verdict and reported confidence. `pct` is confidence as a percentage.
    """
    pct = round(confidence * 100)
    if attribution == "likely_ai":
        return (
            f"🤖 Likely AI-generated. Our analysis strongly suggests this text was "
            f"produced by an AI system (confidence: {pct}%). This is an automated "
            f"estimate, not a verdict — if you wrote this yourself, you can appeal."
        )
    if attribution == "likely_human":
        return (
            f"✍️ Likely human-written. Our analysis strongly suggests a person wrote "
            f"this text (confidence: {pct}%). This is an automated estimate, not a "
            f"certainty."
        )
    return (
        f"❓ Uncertain origin. We couldn't confidently tell whether a person or an AI "
        f"wrote this (confidence: {pct}%). We've chosen not to guess — treat the "
        f"authorship as unverified."
    )
