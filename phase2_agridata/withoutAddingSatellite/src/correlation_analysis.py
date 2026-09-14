"""Correlation and non-destructive redundancy reporting for the dynamic table."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/coconut_nasa_matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from config import REDUNDANCY_THRESHOLD


def analyze_dynamic_correlations(data: pd.DataFrame, target: str, output_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    numeric = data.select_dtypes(include="number").drop(columns=["Target_Year"], errors="ignore")
    matrix = numeric.corr(method="pearson", min_periods=3)
    matrix.to_csv(output_dir / "correlation_matrix.csv")
    correlations = []
    for feature in numeric.columns:
        if feature == target:
            continue
        paired = numeric[[target, feature]].dropna()
        correlations.append(
            {
                "Feature": feature,
                "Correlation_With_Target": matrix.loc[target, feature] if feature in matrix else np.nan,
                "Absolute_Correlation": abs(matrix.loc[target, feature]) if feature in matrix else np.nan,
                "Sample_Size": len(paired),
                "Temporal_Status": "lagged / historical candidate",
            }
        )
    ranking = pd.DataFrame(correlations).sort_values("Absolute_Correlation", ascending=False, na_position="last") if correlations else pd.DataFrame(columns=["Feature", "Correlation_With_Target", "Absolute_Correlation", "Sample_Size", "Temporal_Status"])
    ranking.to_csv(output_dir / "target_feature_correlations.csv", index=False)

    redundancy = []
    predictor_cols = [col for col in numeric.columns if col != target]
    for i, left in enumerate(predictor_cols):
        for right in predictor_cols[i + 1:]:
            value = matrix.loc[left, right]
            if pd.notna(value) and abs(value) >= REDUNDANCY_THRESHOLD:
                redundancy.append({"Feature_A": left, "Feature_B": right, "Correlation": value, "Potential_Redundancy": True})
    redundancy_df = pd.DataFrame(redundancy, columns=["Feature_A", "Feature_B", "Correlation", "Potential_Redundancy"])
    redundancy_df.to_csv(output_dir / "feature_redundancy_report.csv", index=False)

    if matrix.empty:
        return matrix, ranking, redundancy_df
    size = max(6, min(18, len(matrix.columns) * 0.65))
    fig, ax = plt.subplots(figsize=(size, size))
    image = ax.imshow(matrix, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(matrix.columns)), matrix.columns, rotation=90, fontsize=7)
    ax.set_yticks(range(len(matrix.index)), matrix.index, fontsize=7)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04, label="Pearson r")
    ax.set_title("Dynamic dataset Pearson correlation matrix")
    fig.tight_layout(); fig.savefig(output_dir / "correlation_heatmap.png", dpi=180); plt.close(fig)
    return matrix, ranking, redundancy_df
