"""Score the frozen models once on the holdout. See docs/phase_07_evaluation.md.

Run after tune with: uv run python -m src.models.evaluate
"""

import argparse
import json

import numpy as np
import pandas as pd

from src import config
from src.models.baselines import PROBLEMS, Problem, usable_rows
from src.models.run_baselines import summarise, write_report
from src.models.tune import ALERT_PRECISION, DELIVERY_PROBLEM
from src.models.tuned import make_predictor

BOOTSTRAP_SAMPLES = 1000
CONFIDENCE = 0.95
MIN_PRECISION_SHARE = 0.8
TUNED_LABEL = "Tuned model"
PROMISE_LABEL = "Tuned 90th percentile promise"
MARGIN_LABEL = "Tuned promise with margin"
PROMISE_KEY = "4b. Delivery promise"
OLIST_LABEL = "Olist's promised days"

# The best no-ML rule for each problem, chosen on development scores.
SIMPLE_RULES = {
    "1. Late delivery risk": "Rate by same-state route",
    "2. Low review risk": "Rate by overdue",
    "3. Daily order forecast": "Mean of 28 days, 4 weeks ago",
    "4. Delivery time estimate": "Median by customer state",
    "5. Category demand forecast": "Mean of 4 weeks, 4 weeks ago",
    "6. Seller inactivity risk": "Days since last sale",
    "7. Freight cost estimate": "Median by state pair",
}

# Forecast errors on neighbouring days are related, so whole weeks are resampled.
BOOTSTRAP_GROUPS = {
    "3. Daily order forecast": lambda rows: rows["date"].dt.to_period("W-SUN").astype(str),
    "5. Category demand forecast": lambda rows: rows["week_end"].astype(str),
}


def split_holdout(problem: Problem, table: pd.DataFrame):
    """Return development rows for training and holdout rows for scoring."""
    development = usable_rows(problem, table[table["period"] == "development"])
    holdout = table[table["period"] == "holdout"].dropna(subset=list(problem.required_columns))
    if development.empty or holdout.empty:
        raise ValueError(f"{problem.name} needs both development and holdout rows.")
    return development, holdout


def bootstrap_improvement(compute, actual, model, rule, higher_is_better, groups=None):
    """Return the improvement and its interval, resampling rows or whole groups."""
    actual, model, rule = map(np.asarray, (actual, model, rule))
    rng = np.random.default_rng(config.RANDOM_SEED)

    if groups is None:
        members = [np.array([position]) for position in range(len(actual))]
    else:
        members = [np.flatnonzero(np.asarray(groups) == group) for group in pd.unique(groups)]

    def improvement(positions):
        difference = compute(actual[positions], model[positions]) - compute(
            actual[positions], rule[positions]
        )
        return difference if higher_is_better else -difference

    samples = []
    for _ in range(BOOTSTRAP_SAMPLES):
        chosen = rng.integers(0, len(members), len(members))
        samples.append(improvement(np.concatenate([members[index] for index in chosen])))

    tail = (1 - CONFIDENCE) / 2 * 100
    low, high = np.percentile(samples, [tail, 100 - tail])
    return improvement(np.arange(len(actual))), float(low), float(high)


def verdict(interval_low, alert_precision=None, target_precision=None):
    """Apply the verdict rules from the locked plan."""
    if interval_low <= 0:
        return "Use the simple rule"
    if target_precision is None or alert_precision >= MIN_PRECISION_SHARE * target_precision:
        return "Ready"
    return "Ready for ranking only"


def alert_scores(actual, scores, cutoff):
    """Return precision, recall, and the share of rows flagged at a frozen cutoff."""
    actual, scores = np.asarray(actual), np.asarray(scores)
    flagged = scores >= cutoff
    precision = float(actual[flagged].mean()) if flagged.any() else 0.0
    return precision, float(flagged[actual == 1].mean()), float(flagged.mean())


def metric_rows(problem, label, actual, predicted, holdout, development):
    """Return one result row per metric."""
    return [
        {
            "problem": problem.name,
            "baseline": label,
            "fold": "holdout",
            "metric": metric,
            "value": compute(actual, predicted, holdout, development),
            "train_rows": len(development),
            "valid_rows": len(holdout),
        }
        for metric, compute in problem.metrics.items()
    ]


def monthly_rows(problem, predictions, holdout):
    """Return the primary metric by month for the rule and the tuned model."""
    rows = []
    months = holdout[problem.time_column].dt.to_period("M").astype(str).to_numpy()
    actual = holdout[problem.target].to_numpy()
    compute = problem.metrics[problem.primary]
    for month in sorted(set(months)):
        selected = months == month
        for label in (SIMPLE_RULES[problem.name], TUNED_LABEL):
            value = compute(actual[selected], predictions[label][selected], None, None)
            rows.append(
                {
                    "problem": problem.name,
                    "month": month,
                    "model": label,
                    "metric": problem.primary,
                    "value": value,
                    "rows": int(selected.sum()),
                    "actual_mean": float(actual[selected].mean()),
                }
            )
    return rows


def evaluate_problem_on_holdout(problem, table, chosen):
    """Return metric rows, a comparison row, monthly rows, and alert or promise details."""
    development, holdout = split_holdout(problem, table)
    actual = holdout[problem.target]
    tuned = chosen[problem.name]

    predictions = {}
    for label, predict in problem.baselines.items():
        predictions[label] = np.asarray(predict(development, holdout, problem.target))
    predict = make_predictor(tuned["family"], problem.table, tuned["params"])
    predictions[TUNED_LABEL] = np.asarray(predict(development, holdout, problem.target))

    rows = []
    for label, predicted in predictions.items():
        rows += metric_rows(problem, label, actual, predicted, holdout, development)

    def primary(truth, predicted):
        return problem.metrics[problem.primary](truth, predicted, None, None)

    make_groups = BOOTSTRAP_GROUPS.get(problem.name)
    groups = None if make_groups is None else make_groups(holdout).to_numpy()
    improvement, low, high = bootstrap_improvement(
        primary,
        actual,
        predictions[TUNED_LABEL],
        predictions[SIMPLE_RULES[problem.name]],
        problem.higher_is_better,
        groups,
    )

    comparison = {
        "problem": problem.name,
        "metric": problem.primary,
        "simple_rule": SIMPLE_RULES[problem.name],
        "rule_score": primary(actual, predictions[SIMPLE_RULES[problem.name]]),
        "tuned_score": primary(actual, predictions[TUNED_LABEL]),
        "improvement": improvement,
        "interval_low": low,
        "interval_high": high,
        "holdout_rows": len(holdout),
    }

    details = {}
    target = ALERT_PRECISION.get(problem.name)
    if target is not None:
        precision, recall, flagged = alert_scores(
            actual, predictions[TUNED_LABEL], tuned["alert_cutoff"]
        )
        details["alert"] = {
            "problem": problem.name,
            "target_precision": target,
            "precision": precision,
            "recall": recall,
            "flagged_share": flagged,
            "actual_rate": float(actual.mean()),
            "mean_score": float(predictions[TUNED_LABEL].mean()),
        }
        comparison["verdict"] = verdict(low, precision, target)
    else:
        comparison["verdict"] = verdict(low)

    if problem.name == DELIVERY_PROBLEM:
        promise = chosen[PROMISE_KEY]
        predict = make_predictor(promise["family"], problem.table, promise["params"])
        upper = np.asarray(predict(development, holdout, problem.target))
        rows += metric_rows(problem, PROMISE_LABEL, actual, upper, holdout, development)
        with_margin = upper + promise["margin_days"]
        rows += metric_rows(problem, MARGIN_LABEL, actual, with_margin, holdout, development)

    return rows, comparison, monthly_rows(problem, predictions, holdout), details


def holdout_section(comparisons, alerts, results) -> list[str]:
    """Return the report's final results section."""
    lines = [
        "## Final holdout results",
        "",
        "Orders from 2018-06-01 to 2018-08-21. Rules are in `docs/phase_07_evaluation.md`.",
        "",
        "| Problem | Metric | Simple rule | Tuned | Improvement (95% interval) | Verdict |",
        "|---|---|---:|---:|---|---|",
    ]
    for row in comparisons:
        lines.append(
            f"| {row['problem']} | `{row['metric']}` | {row['rule_score']:.4f} "
            f"| {row['tuned_score']:.4f} | {row['improvement']:.4f} "
            f"({row['interval_low']:.4f} to {row['interval_high']:.4f}) | {row['verdict']} |"
        )

    lines += [
        "",
        "| Alert | Target precision | Precision | Recall | Rows flagged | Actual rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in alerts:
        lines.append(
            f"| {row['problem']} | {row['target_precision']:.0%} | {row['precision']:.1%} "
            f"| {row['recall']:.1%} | {row['flagged_share']:.1%} | {row['actual_rate']:.1%} |"
        )

    promises = results[
        results["problem"].eq(DELIVERY_PROBLEM)
        & results["baseline"].isin([OLIST_LABEL, PROMISE_LABEL, MARGIN_LABEL])
    ].pivot(index="baseline", columns="metric", values="value")
    lines += [
        "",
        "| Promise | Mean days promised | Arrived by promise |",
        "|---|---:|---:|",
    ]
    for label in (OLIST_LABEL, PROMISE_LABEL, MARGIN_LABEL):
        row = promises.loc[label]
        lines.append(f"| {label} | {row['mean_predicted']:.1f} | {row['share_by_predicted']:.1%} |")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-rerun",
        action="store_true",
        help="Repeat the holdout run, only to reproduce it or apply a disclosed fix.",
    )
    args = parser.parse_args()

    output = config.REPORTS_DIR / "holdout_results.csv"
    if output.exists() and not args.confirm_rerun:
        raise SystemExit("The holdout has already been used. See docs/phase_07_evaluation.md.")

    chosen = json.loads((config.REPORTS_DIR / "tuned_models.json").read_text())
    rows, comparisons, monthly, alerts = [], [], [], []
    for problem in PROBLEMS:
        table = pd.read_parquet(config.FEATURES_DIR / f"{problem.table}.parquet")
        problem_rows, comparison, months, details = evaluate_problem_on_holdout(
            problem, table, chosen
        )
        rows += problem_rows
        comparisons.append(comparison)
        monthly += months
        if "alert" in details:
            alerts.append(details["alert"])
        print(f"{problem.name}: {comparison['verdict']}", flush=True)

    results = pd.DataFrame(rows)
    results.to_csv(output, index=False)
    pd.DataFrame(comparisons).to_csv(config.REPORTS_DIR / "holdout_comparison.csv", index=False)
    pd.DataFrame(monthly).to_csv(config.REPORTS_DIR / "holdout_monthly.csv", index=False)
    pd.DataFrame(alerts).to_csv(config.REPORTS_DIR / "holdout_alerts.csv", index=False)

    folds = pd.concat(
        [
            pd.read_csv(config.REPORTS_DIR / "baseline_folds.csv"),
            pd.read_csv(config.REPORTS_DIR / "tuned_folds.csv"),
        ],
        ignore_index=True,
    )
    write_report(summarise(folds), holdout_section(comparisons, alerts, results))


if __name__ == "__main__":
    main()
