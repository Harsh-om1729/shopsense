"""Tune every model on development folds and update the comparison report.

Run after run_baselines with: uv run python -m src.models.tune
"""

import json

import numpy as np
import pandas as pd

from src import config
from src.models import metrics
from src.models.baselines import (
    INACTIVE_PRECISION,
    LATE_PRECISION,
    LOW_REVIEW_PRECISION,
    PROBLEMS,
    score_predictor,
    usable_rows,
)
from src.models.run_baselines import load_development, summarise, write_report
from src.models.tuned import PROMISE_QUANTILE, TUNING, make_predictor, sample_settings

ALERT_PRECISION = {
    "1. Late delivery risk": LATE_PRECISION,
    "2. Low review risk": LOW_REVIEW_PRECISION,
    "6. Seller inactivity risk": INACTIVE_PRECISION,
}
DELIVERY_PROBLEM = "4. Delivery time estimate"
PROMISE_LABEL = "Tuned 90th percentile promise"
MARGIN_LABEL = "Tuned promise with margin"


def forward_alert_results(problem_name, predictions, target_precision):
    """Set each alert cutoff on earlier folds, then score it on the next fold."""
    folds = list(dict.fromkeys(predictions["fold"]))
    rows = []
    for position in range(1, len(folds)):
        earlier = predictions[predictions["fold"].isin(folds[:position])]
        current = predictions[predictions["fold"] == folds[position]]
        cutoff = metrics.threshold_at_precision(
            earlier["actual"], earlier["score"], target_precision
        )
        flagged = (
            current["score"] >= cutoff
            if cutoff is not None
            else pd.Series(False, index=current.index)
        )
        positives = current["actual"] == 1
        precision = float(positives[flagged].mean()) if flagged.any() else np.nan
        recall = float(flagged[positives].mean())
        for metric, value in [("forward_precision", precision), ("forward_recall", recall)]:
            rows.append(
                {
                    "problem": problem_name,
                    "baseline": "Tuned model",
                    "fold": folds[position],
                    "metric": metric,
                    "value": value,
                    "train_rows": len(earlier),
                    "valid_rows": len(current),
                }
            )
    return rows


def forward_promise_results(problem_name, predictions):
    """Set a safety margin on earlier folds, then score the adjusted promise on the next fold."""
    folds = list(dict.fromkeys(predictions["fold"]))
    rows = []
    for position in range(1, len(folds)):
        earlier = predictions[predictions["fold"].isin(folds[:position])]
        current = predictions[predictions["fold"] == folds[position]]
        margin = (earlier["actual"] - earlier["score"]).quantile(PROMISE_QUANTILE)
        promise = current["score"] + margin
        scores = {
            "share_by_predicted": metrics.share_by_predicted(current["actual"], promise),
            "mean_predicted": float(promise.mean()),
        }
        for metric, value in scores.items():
            rows.append(
                {
                    "problem": problem_name,
                    "baseline": MARGIN_LABEL,
                    "fold": folds[position],
                    "metric": metric,
                    "value": value,
                    "train_rows": len(earlier),
                    "valid_rows": len(current),
                }
            )
    return rows


def tune_problem(problem, usable):
    """Return all trials, plus the best candidate's rows and predictions."""
    trials = []
    best = None
    for family, space in TUNING[problem.name].items():
        for params in sample_settings(space):
            predict = make_predictor(family, problem.table, params)
            rows, predictions = score_predictor(problem, usable, "Tuned model", predict)
            scores = [row["value"] for row in rows if row["metric"] == problem.primary]
            mean = float(np.mean(scores))
            trials.append(
                {
                    "problem": problem.name,
                    "family": family,
                    "params": json.dumps(params, sort_keys=True),
                    "metric": problem.primary,
                    "mean": round(mean, 4),
                    "std": round(float(np.std(scores, ddof=1)), 4),
                }
            )
            better = best is None or (
                mean > best["mean"] if problem.higher_is_better else mean < best["mean"]
            )
            if better:
                best = {
                    "mean": mean,
                    "family": family,
                    "params": params,
                    "rows": rows,
                    "predictions": predictions,
                }
            print(f"{problem.name} {family} {mean:.4f}", flush=True)
    return trials, best


def main() -> None:
    trials, tuned_rows, chosen = [], [], {}
    for problem in PROBLEMS:
        usable = usable_rows(problem, load_development(problem.table))
        problem_trials, best = tune_problem(problem, usable)
        trials += problem_trials
        tuned_rows += best["rows"]
        chosen[problem.name] = {"family": best["family"], "params": best["params"]}

        if problem.name in ALERT_PRECISION:
            target = ALERT_PRECISION[problem.name]
            predictions = best["predictions"]
            tuned_rows += forward_alert_results(problem.name, predictions, target)
            cutoff = metrics.threshold_at_precision(
                predictions["actual"], predictions["score"], target
            )
            chosen[problem.name]["target_precision"] = target
            chosen[problem.name]["alert_cutoff"] = None if cutoff is None else float(cutoff)

        if problem.name == DELIVERY_PROBLEM:
            predict = make_predictor("boosted_quantile", problem.table, best["params"])
            promise_rows, promises = score_predictor(problem, usable, PROMISE_LABEL, predict)
            tuned_rows += promise_rows + forward_promise_results(problem.name, promises)
            margin = (promises["actual"] - promises["score"]).quantile(PROMISE_QUANTILE)
            chosen["4b. Delivery promise"] = {
                "family": "boosted_quantile",
                "params": best["params"],
                "margin_days": float(margin),
            }

    pd.DataFrame(trials).to_csv(config.REPORTS_DIR / "tuning_results.csv", index=False)
    tuned = pd.DataFrame(tuned_rows)
    tuned.to_csv(config.REPORTS_DIR / "tuned_folds.csv", index=False)
    (config.REPORTS_DIR / "tuned_models.json").write_text(json.dumps(chosen, indent=2) + "\n")

    baselines = pd.read_csv(config.REPORTS_DIR / "baseline_folds.csv")
    summary = summarise(pd.concat([baselines, tuned], ignore_index=True))
    write_report(summary)
    print(summarise(tuned).to_string(index=False))


if __name__ == "__main__":
    main()
