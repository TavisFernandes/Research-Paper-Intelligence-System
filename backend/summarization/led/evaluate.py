<<<<<<< HEAD
"""ROUGE-1/2/L evaluation against reference summaries."""
from __future__ import annotations

from typing import Dict, Sequence

from errors import InvalidInputError


def rouge(predictions: Sequence[str], references: Sequence[str]) -> Dict[str, float]:
    """Mean ROUGE F-measures (0-1). Requires equal-length, non-empty prediction/reference lists."""
    if len(predictions) != len(references):
        raise InvalidInputError("predictions and references must have the same length.")
    if not predictions:
        raise InvalidInputError("At least one prediction/reference pair is required.")
    if any(not str(r).strip() for r in references):
        raise InvalidInputError("Reference summaries must not be empty; ROUGE needs valid references.")
    try:
        from rouge_score import rouge_scorer
    except ImportError as error:
        raise RuntimeError("Install rouge-score to calculate ROUGE.") from error
    scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
    scores = [scorer.score(str(reference), str(prediction)) for prediction, reference in zip(predictions, references)]
    result = {key: round(sum(s[key].fmeasure for s in scores) / len(scores), 5) for key in ("rouge1", "rouge2", "rougeL")}
    result["n_examples"] = len(scores)  # type: ignore[assignment]
    return result
=======
def rouge(predictions: list[str], references: list[str]) -> dict[str, float]:
    try:
        from rouge_score import rouge_scorer
        scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
        scores = [scorer.score(reference, prediction) for prediction, reference in zip(predictions, references)]
        return {key: round(sum(score[key].fmeasure for score in scores) / max(len(scores), 1), 5) for key in ("rouge1", "rouge2", "rougeL")}
    except ImportError as error:
        raise RuntimeError("Install rouge-score to calculate ROUGE.") from error
>>>>>>> origin/main
