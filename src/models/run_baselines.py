"""Score every baseline and write the comparison report.

Run after make_features with: uv run python -m src.models.run_baselines
"""

import pandas as pd

from src import config
from src.models.baselines import PROBLEMS, evaluate_problem


def load_development(table_name: str) -> pd.DataFrame:
    """Read a feature table's development rows, with a clear error if it's missing."""
    path = config.FEATURES_DIR / f"{table_name}.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Run src.features.make_features first.")
    table = pd.read_parquet(path)
    return table[table["period"] == "development"]


def summarise(results: pd.DataFrame) -> pd.DataFrame:
    """Return the mean, spread, and worst fold for each baseline and metric."""
    return (
        results.groupby(["problem", "baseline", "metric"], sort=False)["value"]
        .agg(mean="mean", std="std", lowest="min", highest="max")
        .round(4)
        .reset_index()
    )


def write_report(summary: pd.DataFrame) -> None:
    """Write reports/model_comparison.md."""
    lines = [
        "# Model comparison",
        "",
        "Baseline scores from time-based validation on development rows.",
        "The holdout hasn't been used. See `docs/phase_05_baselines.md`.",
    ]
    for problem in PROBLEMS:
        lines += ["", f"## {problem.name}", ""]
        lines += [
            f"Primary metric: `{problem.primary}`. "
            f"{'Higher' if problem.higher_is_better else 'Lower'} is better.",
            "",
            "| Baseline | Metric | Mean | Std | Lowest fold | Highest fold |",
            "|---|---|---:|---:|---:|---:|",
        ]
        rows = summary[summary["problem"] == problem.name]
        for row in rows.itertuples():
            lines.append(
                f"| {row.baseline} | `{row.metric}` | {row.mean:.4f} | {row.std:.4f} "
                f"| {row.lowest:.4f} | {row.highest:.4f} |"
            )
    (config.REPORTS_DIR / "model_comparison.md").write_text("\n".join(lines) + "\n")


def main() -> None:
    results = pd.concat(
        [evaluate_problem(problem, load_development(problem.table)) for problem in PROBLEMS],
        ignore_index=True,
    )
    results.to_csv(config.REPORTS_DIR / "baseline_folds.csv", index=False)

    summary = summarise(results)
    write_report(summary)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
