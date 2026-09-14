"""Merge validated annual coconut targets with calendar-year POWER summaries."""

from __future__ import annotations

import pandas as pd


def align_coconut_and_power(coconut: pd.DataFrame, power_features: pd.DataFrame) -> pd.DataFrame:
    # A yearly Coconut + POWER table must only contain actual temporal overlap;
    # retaining coconut-only pre-POWER years would create all-null climate rows.
    aligned = coconut.merge(power_features, on="Calendar_Year", how="inner", validate="one_to_one")
    aligned = aligned.rename(columns={"Calendar_Year": "Target_Year"})
    return aligned.sort_values("Target_Year", kind="stable").reset_index(drop=True)
