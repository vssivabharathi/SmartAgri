"""Annual target ACF/PACF and feature(t-k) -> yield(t) analysis."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/coconut_nasa_matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr
from statsmodels.stats.multitest import multipletests
from statsmodels.tsa.stattools import acf, pacf

from config import ALPHA, FDR_ALPHA, MIN_PAIRED_OBSERVATIONS


def _max_acf_lag(n: int) -> int:
    """Conservative predeclared rule: no more than a quarter of observations, capped at eight."""
    return max(1, min(8, n // 4))


def analyze_yield_series(data: pd.DataFrame, target: str, output_dir: Path) -> tuple[pd.DataFrame, list[int], int]:
    series = data[["Target_Year", target]].dropna().sort_values("Target_Year")
    n = len(series)
    max_lag = _max_acf_lag(n)
    acf_values, acf_ci = acf(series[target], nlags=max_lag, alpha=ALPHA, fft=False)
    pacf_values, pacf_ci = pacf(series[target], nlags=max_lag, alpha=ALPHA, method="ywm")
    analysis = pd.DataFrame(
        {
            "Lag_Years": range(max_lag + 1),
            "ACF": acf_values,
            "ACF_CI_Lower": acf_ci[:, 0],
            "ACF_CI_Upper": acf_ci[:, 1],
            "PACF": pacf_values,
            "PACF_CI_Lower": pacf_ci[:, 0],
            "PACF_CI_Upper": pacf_ci[:, 1],
        }
    )
    analysis["ACF_Significant"] = (analysis["ACF_CI_Lower"] > 0) | (analysis["ACF_CI_Upper"] < 0)
    analysis["PACF_Significant"] = (analysis["PACF_CI_Lower"] > 0) | (analysis["PACF_CI_Upper"] < 0)
    analysis.loc[0, ["ACF_Significant", "PACF_Significant"]] = False
    analysis["Candidate_Yield_Lag"] = analysis["ACF_Significant"] & analysis["PACF_Significant"]
    candidates = analysis.loc[analysis["Candidate_Yield_Lag"], "Lag_Years"].astype(int).tolist()

    plt.figure(figsize=(9, 4.5))
    plt.plot(series["Target_Year"], series[target], marker="o", linewidth=1.5)
    plt.title("Coconut productivity time series")
    plt.xlabel("Target year")
    plt.ylabel("Declared million unit per hectare")
    plt.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(output_dir / "coconut_productivity_timeseries.png", dpi=160); plt.close()
    for values, confidence, name, label in [
        (acf_values, acf_ci, "acf_plot.png", "ACF"),
        (pacf_values, pacf_ci, "pacf_plot.png", "PACF"),
    ]:
        lags = np.arange(len(values))
        plt.figure(figsize=(8, 4.5))
        plt.vlines(lags, 0, values, color="#1f77b4")
        plt.scatter(lags, values, color="#1f77b4", s=24)
        plt.axhline(0, color="black", linewidth=0.8)
        plt.fill_between(lags, confidence[:, 0], confidence[:, 1], color="#9ecae1", alpha=0.35, label="95% CI")
        plt.title(f"Coconut productivity {label}")
        plt.xlabel("Annual lag"); plt.ylabel(label); plt.legend(); plt.tight_layout()
        plt.savefig(output_dir / name, dpi=160); plt.close()
    return analysis, candidates, max_lag


def cross_correlations(data: pd.DataFrame, target: str, features: list[str], max_lag: int) -> pd.DataFrame:
    records = []
    for feature in features:
        for lag in range(max_lag + 1):
            paired = pd.DataFrame({"feature": data[feature].shift(lag), "target": data[target]}).dropna()
            n = len(paired)
            record = {
                "Feature": feature, "Lag_Years": lag, "Convention": f"{feature}(t-{lag}) -> {target}(t)",
                "Paired_Sample_Size": n,
                "Temporal_Availability": "contemporaneous; excluded from default dynamic dataset" if lag == 0 else "previous-year information",
                "Pearson_Correlation": np.nan, "Pearson_PValue": np.nan,
                "Spearman_Correlation": np.nan, "Spearman_PValue": np.nan,
            }
            if n >= 3 and paired["feature"].nunique() > 1 and paired["target"].nunique() > 1:
                record["Pearson_Correlation"], record["Pearson_PValue"] = pearsonr(paired["feature"], paired["target"])
                record["Spearman_Correlation"], record["Spearman_PValue"] = spearmanr(paired["feature"], paired["target"])
            records.append(record)
    result = pd.DataFrame(records)
    result["FDR_PValue"] = np.nan
    eligible = result["Pearson_PValue"].notna() & result["Lag_Years"].gt(0)
    if eligible.any():
        result.loc[eligible, "FDR_PValue"] = multipletests(result.loc[eligible, "Pearson_PValue"], method="fdr_bh")[1]
    result["Candidate_Lag"] = (
        result["Lag_Years"].gt(0)
        & result["Paired_Sample_Size"].ge(MIN_PAIRED_OBSERVATIONS)
        & result["FDR_PValue"].lt(FDR_ALPHA)
    )
    result["Selection_Rule"] = (
        f"Lag > 0, paired n >= {MIN_PAIRED_OBSERVATIONS}, and Benjamini-Hochberg FDR-adjusted Pearson p < {FDR_ALPHA}; requires review for temporal/agricultural plausibility."
    )
    return result.sort_values(["Candidate_Lag", "FDR_PValue", "Pearson_PValue"], ascending=[False, True, True], na_position="last").reset_index(drop=True)


def plot_cross_correlations(result: pd.DataFrame, output_dir: Path, max_features: int = 12) -> list[str]:
    plot_dir = output_dir / "cross_correlation_plots"; plot_dir.mkdir(exist_ok=True)
    ranked = result.assign(rank_p=result["Pearson_PValue"].fillna(1.0)).groupby("Feature", as_index=False)["rank_p"].min().nsmallest(max_features, "rank_p")
    names = []
    for feature in ranked["Feature"]:
        subset = result.loc[result["Feature"].eq(feature)].sort_values("Lag_Years")
        plt.figure(figsize=(6.5, 4))
        colors = ["#d62728" if candidate else "#1f77b4" for candidate in subset["Candidate_Lag"]]
        plt.bar(subset["Lag_Years"], subset["Pearson_Correlation"], color=colors)
        plt.axhline(0, color="black", linewidth=0.8); plt.ylim(-1, 1)
        plt.title(f"Lagged Pearson correlation: {feature}")
        plt.xlabel("Feature lag in years: feature(t-k) → yield(t)"); plt.ylabel("Pearson r")
        plt.tight_layout()
        filename = f"{feature.replace('/', '_')}.png"; plt.savefig(plot_dir / filename, dpi=160); plt.close()
        names.append(feature)
    return names
