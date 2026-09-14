"""Schema-aware parsing and physically appropriate NASA POWER aggregation."""

from __future__ import annotations

import calendar
from pathlib import Path

import numpy as np
import pandas as pd

from config import CALENDAR_PERIODS

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
MONTH_NUMBERS = {name: index + 1 for index, name in enumerate(MONTHS)}
PARAMETER_INFO = {
    "ALLSKY_SFC_SW_DWN": ("All-sky surface shortwave downward irradiance", "MJ/m^2/day", "total_daily_rate"),
    "PRECTOTCORR": ("Corrected precipitation", "mm/day", "total_daily_rate"),
    "RH2M": ("Relative humidity at 2 m", "%", "day_weighted_mean"),
    "T2M": ("Temperature at 2 m", "C", "day_weighted_mean"),
    "T2M_MAX": ("Temperature at 2 m maximum", "C", "day_weighted_mean"),
    "T2M_MIN": ("Temperature at 2 m minimum", "C", "day_weighted_mean"),
    "WS10M": ("Wind speed at 10 m", "m/s", "day_weighted_mean"),
}


def find_power_file(data_dir: Path) -> Path:
    for path in sorted(data_dir.glob("*.csv")):
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        if any(line.startswith("PARAMETER,YEAR,JAN") for line in lines):
            return path
    raise FileNotFoundError("No NASA POWER CSV with a PARAMETER,YEAR,JAN header was found.")


def parse_power(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, Path, dict[str, str]]:
    path = find_power_file(data_dir)
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    header_index = next(i for i, line in enumerate(lines) if line.startswith("PARAMETER,YEAR,JAN"))
    raw = pd.read_csv(path, skiprows=header_index)
    expected = {"PARAMETER", "YEAR", *MONTHS, "ANN"}
    if not expected.issubset(raw.columns):
        raise ValueError("NASA POWER table lacks required monthly columns.")
    raw["YEAR"] = pd.to_numeric(raw["YEAR"], errors="raise").astype(int)
    raw[MONTHS + ["ANN"]] = raw[MONTHS + ["ANN"]].apply(pd.to_numeric, errors="coerce").replace(-999, np.nan)

    header_text = "\n".join(lines[:header_index])
    metadata = []
    for parameter in sorted(raw["PARAMETER"].unique()):
        meaning, unit, aggregation = PARAMETER_INFO.get(parameter, ("Not documented by parser", "unknown", "review_required"))
        records = raw.loc[raw["PARAMETER"].eq(parameter)]
        metadata.append(
            {
                "Parameter": parameter,
                "Physical_Meaning": meaning,
                "Unit": unit,
                "Temporal_Resolution": "monthly daily-rate/statistic plus supplied ANN",
                "Years": f"{records['YEAR'].min()}-{records['YEAR'].max()}",
                "Duplicate_Year_Records": int(records["YEAR"].duplicated().sum()),
                "Missing_Monthly_Values": int(records[MONTHS].isna().sum().sum()),
                "Missing_Annual_Values": int(records["ANN"].isna().sum()),
                "Aggregation_Rule": aggregation,
            }
        )
    parsed_header = {
        "source_header": header_text,
        "location": next((line for line in lines[:header_index] if line.startswith("Location:")), "not found"),
        "dates": next((line for line in lines[:header_index] if line.startswith("Dates")), "not found"),
    }
    return raw, pd.DataFrame(metadata), path, parsed_header


def monthly_long(power_wide: pd.DataFrame) -> pd.DataFrame:
    long = power_wide.melt(
        id_vars=["PARAMETER", "YEAR"], value_vars=MONTHS,
        var_name="Month_Name", value_name="Value",
    )
    long["Month"] = long["Month_Name"].map(MONTH_NUMBERS).astype(int)
    long["Days_In_Month"] = [calendar.monthrange(int(y), int(m))[1] for y, m in zip(long["YEAR"], long["Month"])]
    long["Unit"] = long["PARAMETER"].map(lambda p: PARAMETER_INFO.get(p, ("", "unknown", ""))[1])
    long["Physical_Meaning"] = long["PARAMETER"].map(lambda p: PARAMETER_INFO.get(p, ("Not documented", "", ""))[0])
    return long.sort_values(["YEAR", "Month", "PARAMETER"]).reset_index(drop=True)


def _aggregate_period(records: pd.DataFrame, parameter: str) -> float:
    valid = records.dropna(subset=["Value"])
    if len(valid) != len(records):
        return np.nan  # Never create a partial-period statistic as if it were complete.
    rule = PARAMETER_INFO.get(parameter, ("", "", "review_required"))[2]
    if rule == "total_daily_rate":
        return float((valid["Value"] * valid["Days_In_Month"]).sum())
    if rule == "day_weighted_mean":
        return float(np.average(valid["Value"], weights=valid["Days_In_Month"]))
    return np.nan


def _feature_name(parameter: str, period: str) -> str:
    rule = PARAMETER_INFO[parameter][2]
    suffix = "Total" if rule == "total_daily_rate" else "Mean"
    return f"{parameter}_{period}_{suffix}"


def aggregate_power(power_wide: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    long = monthly_long(power_wide)
    rows: list[dict] = []
    feature_metadata: list[dict] = []
    periods = {"Annual": tuple(range(1, 13)), **CALENDAR_PERIODS}
    for year in sorted(long["YEAR"].unique()):
        row: dict = {"Calendar_Year": int(year)}
        year_data = long.loc[long["YEAR"].eq(year)]
        for parameter in sorted(power_wide["PARAMETER"].unique()):
            for period, months in periods.items():
                records = year_data.loc[
                    year_data["PARAMETER"].eq(parameter) & year_data["Month"].isin(months)
                ]
                name = _feature_name(parameter, period)
                row[name] = _aggregate_period(records, parameter)
                if year == min(long["YEAR"]):
                    meaning, unit, rule = PARAMETER_INFO[parameter]
                    # A daily rate summed over days loses only the /day term:
                    # MJ/m^2/day -> MJ/m^2 and mm/day -> mm.
                    output_unit = unit.removesuffix("/day") if rule == "total_daily_rate" else unit
                    feature_metadata.append(
                        {
                            "Feature_Name": name,
                            "Dataset": "yearly",
                            "Source": "NASA POWER",
                            "Original_Parameter": parameter,
                            "Temporal_Resolution": "monthly -> annual/defined calendar period",
                            "Aggregation": "sum(value × days in month)" if rule == "total_daily_rate" else "day-weighted mean",
                            "Period": "Jan-Dec" if period == "Annual" else ",".join(calendar.month_abbr[m] for m in months),
                            "Lag_Years": 0,
                            "Unit": output_unit,
                            "Description": meaning,
                            "Reason_for_Inclusion": "Observed NASA POWER climate covariate; contemporaneous values are flagged, not default predictors.",
                            "Availability": "contemporaneous full-period information",
                        }
                    )
        rows.append(row)
    return pd.DataFrame(rows).sort_values("Calendar_Year"), pd.DataFrame(feature_metadata), long
