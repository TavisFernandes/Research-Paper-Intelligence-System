def rouge(predictions: list[str], references: list[str]) -> dict[str, float]:
    try:
        from rouge_score import rouge_scorer
        scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=True)
        scores = [scorer.score(reference, prediction) for prediction, reference in zip(predictions, references)]
        return {key: round(sum(score[key].fmeasure for score in scores) / max(len(scores), 1), 5) for key in ("rouge1", "rouge2", "rougeL")}
    except ImportError as error:
        raise RuntimeError("Install rouge-score to calculate ROUGE.") from error
