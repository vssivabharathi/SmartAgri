"""Discovery and transparent preparation of the annual coconut source."""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd


def find_coconut_file(data_dir: Path) -> Path:
    """Find a CSV by schema rather than depending on a supplied filename."""
    for path in sorted(data_dir.glob("*.csv")):
        columns = pd.read_csv(path, nrows=0).columns.tolist()
        required = {"Agriculture Year", "Area Hectare", "Production Million Unit"}
        if required.issubset(columns):
            return path
    raise FileNotFoundError("No CSV with Agriculture Year, Area Hectare, and Production Million Unit was found.")


def _calendar_year(label: str, anchor: str) -> int:
    match = re.fullmatch(r"\s*(\d{4})\s*-\s*(\d{2,4})\s*", str(label))
    if not match:
        raise ValueError(f"Unrecognised agriculture-year label: {label!r}")
    start_year = int(match.group(1))
    end_part = match.group(2)
    if len(end_part) == 4:
        end_year = int(end_part)
    else:
        end_year = (start_year // 100) * 100 + int(end_part)
        # Agricultural labels cross a century in forms such as 1999-00.
        if end_year < start_year:
            end_year += 100
    if end_year != start_year + 1:
        raise ValueError(f"Agriculture-year label is not consecutive: {label!r}")
    if anchor == "start":
        return start_year
    if anchor == "end":
        return end_year
    raise ValueError("anchor must be 'start' or 'end'.")


def preprocess_coconut(data_dir: Path, agriculture_year_anchor: str) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    path = find_coconut_file(data_dir)
    raw = pd.read_csv(path)
    required = ["Agriculture Year", "Area Hectare", "Production Million Unit"]
    if raw.columns.tolist() != required:
        # Extra columns are allowed, but named inputs remain explicit.
        missing = set(required) - set(raw.columns)
        if missing:
            raise ValueError(f"Coconut source is missing required columns: {sorted(missing)}")

    processed = raw.loc[:, required].copy()
    processed["Calendar_Year"] = processed["Agriculture Year"].map(
        lambda value: _calendar_year(value, agriculture_year_anchor)
    )
    processed["Agriculture_Year_Anchor"] = agriculture_year_anchor
    processed["Coconut_Area_Hectare"] = pd.to_numeric(processed["Area Hectare"], errors="coerce")
    processed["Coconut_Production_MillionUnit"] = pd.to_numeric(
        processed["Production Million Unit"], errors="coerce"
    )
    # This is deliberately in the source's declared (but semantically unnamed)
    # million-unit scale. It is not silently relabelled as tonnes or coconuts.
    processed["Coconut_Productivity_DeclaredMillionUnit_per_Hectare"] = np.where(
        processed["Coconut_Area_Hectare"] > 0,
        processed["Coconut_Production_MillionUnit"] / processed["Coconut_Area_Hectare"],
        np.nan,
    )
    processed["Coconut_Productivity_Unit"] = "declared million unit per hectare"
    processed["Coconut_Productivity_Formula"] = "Production Million Unit / Area Hectare"
    processed = processed[
        [
            "Calendar_Year", "Agriculture Year", "Agriculture_Year_Anchor",
            "Coconut_Area_Hectare", "Coconut_Production_MillionUnit",
            "Coconut_Productivity_DeclaredMillionUnit_per_Hectare",
            "Coconut_Productivity_Unit", "Coconut_Productivity_Formula",
        ]
    ].sort_values("Calendar_Year", kind="stable").reset_index(drop=True)

    metadata = pd.DataFrame(
        [
            {
                "Feature_Name": "Coconut_Productivity_DeclaredMillionUnit_per_Hectare",
                "Dataset": "yearly_and_dynamic",
                "Source": "Coconut annual CSV",
                "Original_Parameter": "Production Million Unit / Area Hectare",
                "Temporal_Resolution": "agricultural year",
                "Aggregation": "ratio",
                "Period": "full agricultural year",
                "Lag_Years": 0,
                "Unit": "declared million unit per hectare",
                "Description": "Productivity ratio in the unverified production unit stated by the raw header.",
                "Reason_for_Inclusion": "Primary target; unit remains explicitly unresolved.",
                "Availability": "target at end of agricultural year",
            }
        ]
    )
    return processed, metadata, path
