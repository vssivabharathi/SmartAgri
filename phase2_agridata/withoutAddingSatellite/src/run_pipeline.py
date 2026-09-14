"""Run the reproducible Coconut + NASA POWER time-series preparation pipeline.

Example:
    python src/run_pipeline.py --agriculture-year-anchor start --max-cross-lag 3
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from config import (
    CALENDAR_PERIODS,
    DEFAULT_AGRICULTURE_YEAR_ANCHOR,
    DEFAULT_CROSS_CORRELATION_MAX_LAG,
    FDR_ALPHA,
    INCLUDE_CONTEMPORANEOUS_FEATURES,
    MAX_DYNAMIC_NASA_FEATURES,
    MIN_PAIRED_OBSERVATIONS,
    REDUNDANCY_THRESHOLD,
)
from coconut_preprocessing import preprocess_coconut
from correlation_analysis import analyze_dynamic_correlations
from nasa_power_preprocessing import aggregate_power, parse_power
from temporal_alignment import align_coconut_and_power
from time_series_analysis import analyze_yield_series, cross_correlations, plot_cross_correlations

TARGET = "Coconut_Productivity_DeclaredMillionUnit_per_Hectare"


def _quality_report(aligned: pd.DataFrame, power_raw: pd.DataFrame) -> pd.DataFrame:
    """Report, never delete, missingness, continuity, range concerns and IQR outliers."""
    rows: list[dict] = []
    year = aligned["Target_Year"]
    duplicate_years = int(year.duplicated().sum())
    expected = set(range(int(year.min()), int(year.max()) + 1))
    gaps = sorted(expected - set(year.dropna().astype(int)))
    rows.extend(
        [
            {"Report_Type": "dataset", "Variable": "Target_Year", "Issue": "duplicate_target_years", "Count": duplicate_years, "Details": "none" if not duplicate_years else "duplicate target years found"},
            {"Report_Type": "dataset", "Variable": "Target_Year", "Issue": "unexpected_year_gaps", "Count": len(gaps), "Details": ",".join(map(str, gaps)) or "none"},
            {"Report_Type": "NASA_raw", "Variable": "PARAMETER,YEAR", "Issue": "duplicate_parameter_year_records", "Count": int(power_raw.duplicated(["PARAMETER", "YEAR"]).sum()), "Details": "checked before aggregation"},
        ]
    )
    for column in aligned.columns:
        if column in {"Agriculture Year", "Agriculture_Year_Anchor", "Coconut_Productivity_Unit", "Coconut_Productivity_Formula"}:
            continue
        values = pd.to_numeric(aligned[column], errors="coerce")
        nonmissing = values.dropna()
        missing = int(values.isna().sum())
        constant = bool(len(nonmissing) > 0 and nonmissing.nunique() == 1)
        details = ""
        if len(nonmissing) >= 4:
            q1, q3 = nonmissing.quantile([0.25, 0.75]); iqr = q3 - q1
            outlier_mask = (values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)
            outliers = aligned.loc[outlier_mask, "Target_Year"].astype(int).tolist()
            outlier_details = ",".join(map(str, outliers)) or "none"
        else:
            outliers, outlier_details = [], "not assessed (<4 values)"
        impossible = 0
        if column in {"Coconut_Area_Hectare", "Coconut_Production_MillionUnit", TARGET}:
            impossible = int((values <= 0).sum())
            details = "non-positive value"
        elif column.startswith("RH2M_"):
            impossible = int(((values < 0) | (values > 100)).sum())
            details = "outside 0-100 percent"
        elif column.startswith("PRECTOTCORR_"):
            impossible = int((values < 0).sum())
            details = "negative accumulated precipitation"
        rows.extend(
            [
                {"Report_Type": "variable", "Variable": column, "Issue": "missing_values", "Count": missing, "Details": "raw missingness is retained as NA"},
                {"Report_Type": "variable", "Variable": column, "Issue": "constant_variable", "Count": int(constant), "Details": "true means no temporal variation"},
                {"Report_Type": "variable", "Variable": column, "Issue": "IQR_outlier_years", "Count": len(outliers), "Details": outlier_details},
                {"Report_Type": "variable", "Variable": column, "Issue": "impossible_values", "Count": impossible, "Details": details or "not rule-checked"},
            ]
        )
    return pd.DataFrame(rows)


def _dynamic_dataset(
    aligned: pd.DataFrame,
    cross_results: pd.DataFrame,
    yield_lags: list[int],
    base_metadata: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    selected = cross_results.loc[cross_results["Dynamic_Selected"], ["Feature", "Lag_Years"]].drop_duplicates()
    dynamic = aligned[["Target_Year", "Agriculture Year", "Agriculture_Year_Anchor", TARGET]].copy()
    target_metadata = base_metadata.loc[base_metadata["Feature_Name"].eq(TARGET)].iloc[0].to_dict()
    dynamic_metadata: list[dict] = []
    selected_names: list[str] = []
    for lag in yield_lags:
        name = f"{TARGET}_Lag{lag}"
        dynamic[name] = aligned[TARGET].shift(lag)
        row = target_metadata.copy()
        row.update({"Feature_Name": name, "Dataset": "dynamic", "Lag_Years": int(lag), "Description": f"Historical coconut productivity at t-{lag}.", "Reason_for_Inclusion": "ACF and PACF 95% confidence intervals both exclude zero.", "Availability": "previous agricultural year"})
        dynamic_metadata.append(row); selected_names.append(name)
    for _, selection in selected.iterrows():
        original, lag = selection["Feature"], int(selection["Lag_Years"])
        name = f"{original}_Lag{lag}"
        dynamic[name] = aligned[original].shift(lag)
        row = base_metadata.loc[base_metadata["Feature_Name"].eq(original)].iloc[0].to_dict()
        row.update({"Feature_Name": name, "Dataset": "dynamic", "Lag_Years": lag, "Description": f"{row['Description']} shifted by {lag} target year(s).", "Reason_for_Inclusion": f"Historical lag passed the n/FDR screen and was the predeclared representative selected for its original parameter; still requires review.", "Availability": "previous-year information"})
        dynamic_metadata.append(row); selected_names.append(name)
    # Raw values are retained in the yearly table. The modelling table has only
    # lagged predictors by default, so it does not imply same-year availability.
    dynamic = dynamic.dropna(subset=[TARGET]).sort_values("Target_Year").reset_index(drop=True)
    return dynamic, pd.DataFrame(dynamic_metadata), selected_names


def _write_summary(
    output_dir: Path,
    anchor: str,
    coconut: pd.DataFrame,
    power_raw: pd.DataFrame,
    aligned: pd.DataFrame,
    dynamic: pd.DataFrame,
    yield_analysis: pd.DataFrame,
    yield_lags: list[int],
    cross_results: pd.DataFrame,
    selected_dynamic: list[str],
    ranking: pd.DataFrame,
    redundancy: pd.DataFrame,
    plotted_features: list[str],
) -> None:
    n_complete = int(aligned.dropna().shape[0])
    candidates = cross_results.loc[cross_results["Candidate_Lag"]]
    top_cross = cross_results.loc[cross_results["Lag_Years"].gt(0)].nsmallest(10, "Pearson_PValue")
    def md_table(frame: pd.DataFrame, columns: list[str], limit: int = 10) -> str:
        if frame.empty:
            return "None."
        view = frame.loc[:, columns].head(limit).copy()
        def value_text(value: object) -> str:
            if pd.isna(value):
                return ""
            if isinstance(value, (float, np.floating)):
                return f"{value:.4g}"
            return str(value).replace("|", "\\|")
        header = "| " + " | ".join(columns) + " |"
        separator = "| " + " | ".join("---" for _ in columns) + " |"
        body = ["| " + " | ".join(value_text(value) for value in row) + " |" for row in view.itertuples(index=False, name=None)]
        return "\n".join([header, separator, *body])
    periods = "; ".join(f"{name}: months {','.join(map(str, months))}" for name, months in CALENDAR_PERIODS.items())
    text = f"""# Coconut + NASA POWER Analysis Summary

## Scope and reproducibility

Satellite/JP2 data was deliberately excluded. No ML model, SHAP, or XAI was run. Reproduce this exact run with:

```bash
python src/run_pipeline.py --agriculture-year-anchor {anchor} --max-cross-lag {cross_results['Lag_Years'].max()}
```

## Coverage and target

- Coconut source: {coconut['Agriculture Year'].min()} to {coconut['Agriculture Year'].max()} ({len(coconut)} agricultural-year records).
- NASA POWER source: {power_raw['YEAR'].min()} to {power_raw['YEAR'].max()} ({power_raw['PARAMETER'].nunique()} parameters; monthly source values retained in `nasa_power_monthly_long.csv`).
- Aligned target period under the configured mapping: {aligned['Target_Year'].min()}–{aligned['Target_Year'].max()} ({len(aligned)} target rows).
- Rows complete across every yearly feature: {n_complete}. The limiting issue is `ALLSKY_SFC_SW_DWN`, which is missing in 1981–1983; no values were imputed.
- Target: `{TARGET}` = `Production Million Unit / Area Hectare`. Its unit is **declared million unit per hectare**, not tonnes/ha or coconuts/ha: the raw production unit remains undocumented.

## Agriculture-year mapping and periods

The source does not state how `YYYY-YY` labels map to calendar years. This run uses the explicit, configurable **{anchor}-year anchor**: `1981-82 → {1981 if anchor == 'start' else 1982}`. This is an operational alignment assumption, not a verified source fact.

Calendar periods are configurable and intentionally not asserted as crop seasons: {periods}. NASA total-rate variables (`PRECTOTCORR`, `ALLSKY_SFC_SW_DWN`) are accumulated as monthly daily rate × days; RH, temperature, and wind are day-weighted means. Exact units and rules are in `nasa_power_parameter_metadata.csv` and `feature_metadata.csv`.

## Time-series findings

ACF/PACF examined lags 0–{int(yield_analysis['Lag_Years'].max())} using a predeclared small-sample rule `min(8, floor(n/4))` and 95% confidence intervals. Candidate historical target lags (significant in both ACF and PACF): **{yield_lags or 'none'}**.

Cross-correlation uses the explicit convention `feature(t-k) → yield(t)` for lags 0–{int(cross_results['Lag_Years'].max())}. Lag 0 is reported but excluded from the default dynamic dataset because a full current target-year climate period is not assumed available at prediction time. Historical candidates require lag > 0, paired n ≥ {MIN_PAIRED_OBSERVATIONS}, and Benjamini-Hochberg FDR-adjusted Pearson p < {FDR_ALPHA}; this is a screening rule, not proof of causality. To keep the dynamic review table proportionate to the sample, it selects at most one screened lag per original NASA parameter and at most {MAX_DYNAMIC_NASA_FEATURES} NASA predictors; every screened candidate remains in `cross_correlation_results.csv`.

### Strongest screened lag relationships

{md_table(top_cross, ['Feature', 'Lag_Years', 'Pearson_Correlation', 'Pearson_PValue', 'FDR_PValue', 'Paired_Sample_Size', 'Candidate_Lag'])}

Cross-correlation plots were generated for: {', '.join(plotted_features) or 'none'}.

## Dynamic dataset

`dynamic_modeling_dataset.csv` has {len(dynamic)} rows and {len(dynamic.columns)} columns. Its predictor columns are: {', '.join(selected_dynamic) if selected_dynamic else 'none selected by the configured historical-lag screen'}. It contains no contemporaneous NASA features by default (`INCLUDE_CONTEMPORANEOUS_FEATURES={INCLUDE_CONTEMPORANEOUS_FEATURES}`), preventing an implicit same-year information assumption. Rows with unavailable lagged values remain in the file as missing values; they were not fabricated or silently dropped.

### Target correlation ranking

{md_table(ranking, ['Feature', 'Correlation_With_Target', 'Absolute_Correlation', 'Sample_Size'])}

### Potential redundancy

Predictor pairs with |Pearson r| ≥ {REDUNDANCY_THRESHOLD}:

{md_table(redundancy, ['Feature_A', 'Feature_B', 'Correlation', 'Potential_Redundancy'])}

## Quality and statistical limitations

`data_quality_report.csv` reports retained missing values, duplicate/gap checks, simple range checks, and IQR-flagged outlier years; no outliers were removed. There are only {len(aligned)} aligned annual targets ({n_complete} complete across all yearly features), and even fewer paired observations after lags. Multiple seasonal features and lag tests increase false-positive and multicollinearity risk. The outputs identify candidates for later validation, not a final predictor set or an ML-ready claim.
"""
    (output_dir / "analysis_summary.md").write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Coconut + NASA POWER dynamic time-series outputs; satellite is excluded.")
    parser.add_argument("--agriculture-year-anchor", choices=["start", "end"], default=DEFAULT_AGRICULTURE_YEAR_ANCHOR)
    parser.add_argument("--max-cross-lag", type=int, default=DEFAULT_CROSS_CORRELATION_MAX_LAG)
    args = parser.parse_args()
    if args.max_cross_lag < 0:
        parser.error("--max-cross-lag must be non-negative")
    root = Path(__file__).resolve().parents[1]
    data_dir, output_dir = root / "dataset", root / "outputs"
    output_dir.mkdir(exist_ok=True)

    coconut, coconut_metadata, coconut_path = preprocess_coconut(data_dir, args.agriculture_year_anchor)
    power_raw, parameter_metadata, power_path, power_header = parse_power(data_dir)
    power_features, power_feature_metadata, power_monthly = aggregate_power(power_raw)
    aligned = align_coconut_and_power(coconut, power_features)
    coconut.to_csv(output_dir / "coconut_processed.csv", index=False)
    aligned.to_csv(output_dir / "coconut_nasa_yearly_dataset.csv", index=False)
    power_monthly.to_csv(output_dir / "nasa_power_monthly_long.csv", index=False)
    parameter_metadata.to_csv(output_dir / "nasa_power_parameter_metadata.csv", index=False)

    quality = _quality_report(aligned, power_raw); quality.to_csv(output_dir / "data_quality_report.csv", index=False)
    yield_analysis, yield_lags, _ = analyze_yield_series(aligned, TARGET, output_dir)
    yield_analysis.to_csv(output_dir / "yield_lag_analysis.csv", index=False)
    nasa_features = power_features.columns.drop("Calendar_Year").tolist()
    cross = cross_correlations(aligned, TARGET, nasa_features, args.max_cross_lag)
    original_parameter = power_feature_metadata.set_index("Feature_Name")["Original_Parameter"].to_dict()
    cross["Original_Parameter"] = cross["Feature"].map(original_parameter)
    cross["Dynamic_Selected"] = False
    # Predeclared down-selection: ranked screen result, one lag per physical
    # parameter, then cap at seven environmental predictors for 38 complete rows.
    screened = cross.loc[cross["Candidate_Lag"]].sort_values(
        ["FDR_PValue", "Pearson_PValue", "Lag_Years"], ascending=[True, True, True]
    )
    representative = screened.drop_duplicates("Original_Parameter", keep="first").head(MAX_DYNAMIC_NASA_FEATURES)
    cross.loc[representative.index, "Dynamic_Selected"] = True
    cross["Dynamic_Selection_Rule"] = (
        f"Among screened candidates: lowest FDR/p-value lag per original NASA parameter, capped at {MAX_DYNAMIC_NASA_FEATURES}; not a final predictor decision."
    )
    cross.to_csv(output_dir / "cross_correlation_results.csv", index=False)
    plotted = plot_cross_correlations(cross, output_dir)

    feature_metadata = pd.concat([coconut_metadata, power_feature_metadata], ignore_index=True)
    dynamic, dynamic_metadata, selected_dynamic = _dynamic_dataset(aligned, cross, yield_lags, feature_metadata)
    dynamic.to_csv(output_dir / "dynamic_modeling_dataset.csv", index=False)
    feature_metadata = pd.concat([feature_metadata, dynamic_metadata], ignore_index=True)
    feature_metadata.to_csv(output_dir / "feature_metadata.csv", index=False)
    _, ranking, redundancy = analyze_dynamic_correlations(dynamic, TARGET, output_dir)
    _write_summary(output_dir, args.agriculture_year_anchor, coconut, power_raw, aligned, dynamic, yield_analysis, yield_lags, cross, selected_dynamic, ranking, redundancy, plotted)
    print(f"Processed coconut source: {coconut_path.name}")
    print(f"Processed NASA POWER source: {power_path.name}")
    print(f"Wrote outputs to: {output_dir}")
    print(f"NASA location header: {power_header['location']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
