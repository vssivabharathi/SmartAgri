# Coconut + NASA POWER Analysis Summary

## Scope and reproducibility

Satellite/JP2 data was deliberately excluded. No ML model, SHAP, or XAI was run. Reproduce this exact run with:

```bash
python src/run_pipeline.py --agriculture-year-anchor start --max-cross-lag 3
```

## Coverage and target

- Coconut source: 1955-56 to 2021-22 (67 agricultural-year records).
- NASA POWER source: 1981 to 2022 (7 parameters; monthly source values retained in `nasa_power_monthly_long.csv`).
- Aligned target period under the configured mapping: 1981–2021 (41 target rows).
- Rows complete across every yearly feature: 38. The limiting issue is `ALLSKY_SFC_SW_DWN`, which is missing in 1981–1983; no values were imputed.
- Target: `Coconut_Productivity_DeclaredMillionUnit_per_Hectare` = `Production Million Unit / Area Hectare`. Its unit is **declared million unit per hectare**, not tonnes/ha or coconuts/ha: the raw production unit remains undocumented.

## Agriculture-year mapping and periods

The source does not state how `YYYY-YY` labels map to calendar years. This run uses the explicit, configurable **start-year anchor**: `1981-82 → 1981`. This is an operational alignment assumption, not a verified source fact.

Calendar periods are configurable and intentionally not asserted as crop seasons: Jan_Feb: months 1,2; Mar_May: months 3,4,5; Jun_Sep: months 6,7,8,9; Oct_Dec: months 10,11,12. NASA total-rate variables (`PRECTOTCORR`, `ALLSKY_SFC_SW_DWN`) are accumulated as monthly daily rate × days; RH, temperature, and wind are day-weighted means. Exact units and rules are in `nasa_power_parameter_metadata.csv` and `feature_metadata.csv`.

## Time-series findings

ACF/PACF examined lags 0–8 using a predeclared small-sample rule `min(8, floor(n/4))` and 95% confidence intervals. Candidate historical target lags (significant in both ACF and PACF): **[1]**.

Cross-correlation uses the explicit convention `feature(t-k) → yield(t)` for lags 0–3. Lag 0 is reported but excluded from the default dynamic dataset because a full current target-year climate period is not assumed available at prediction time. Historical candidates require lag > 0, paired n ≥ 30, and Benjamini-Hochberg FDR-adjusted Pearson p < 0.1; this is a screening rule, not proof of causality. To keep the dynamic review table proportionate to the sample, it selects at most one screened lag per original NASA parameter and at most 7 NASA predictors; every screened candidate remains in `cross_correlation_results.csv`.

### Strongest screened lag relationships

| Feature | Lag_Years | Pearson_Correlation | Pearson_PValue | FDR_PValue | Paired_Sample_Size | Candidate_Lag |
| --- | --- | --- | --- | --- | --- | --- |
| T2M_Jun_Sep_Mean | 1 | 0.6007 | 4.158e-05 | 0.002618 | 40 | True |
| T2M_Jun_Sep_Mean | 2 | 0.6022 | 4.987e-05 | 0.002618 | 39 | True |
| T2M_Jun_Sep_Mean | 3 | 0.5318 | 0.0005895 | 0.01584 | 38 | True |
| T2M_MIN_Jun_Sep_Mean | 1 | 0.5158 | 0.0006581 | 0.01584 | 40 | True |
| ALLSKY_SFC_SW_DWN_Jan_Feb_Total | 3 | 0.5428 | 0.0007542 | 0.01584 | 35 | True |
| ALLSKY_SFC_SW_DWN_Annual_Total | 1 | -0.5134 | 0.001155 | 0.01747 | 37 | True |
| ALLSKY_SFC_SW_DWN_Jan_Feb_Total | 1 | 0.5122 | 0.001191 | 0.01747 | 37 | True |
| WS10M_Mar_May_Mean | 1 | -0.49 | 0.001331 | 0.01747 | 40 | True |
| RH2M_Mar_May_Mean | 3 | 0.4915 | 0.001728 | 0.02016 | 38 | True |
| WS10M_Jun_Sep_Mean | 1 | -0.4689 | 0.002273 | 0.02386 | 40 | True |

Cross-correlation plots were generated for: T2M_Jun_Sep_Mean, WS10M_Mar_May_Mean, RH2M_Mar_May_Mean, WS10M_Annual_Mean, RH2M_Annual_Mean, T2M_MIN_Jun_Sep_Mean, ALLSKY_SFC_SW_DWN_Jan_Feb_Total, ALLSKY_SFC_SW_DWN_Annual_Total, PRECTOTCORR_Mar_May_Total, WS10M_Jun_Sep_Mean, ALLSKY_SFC_SW_DWN_Oct_Dec_Total, ALLSKY_SFC_SW_DWN_Mar_May_Total.

## Dynamic dataset

`dynamic_modeling_dataset.csv` has 41 rows and 12 columns. Its predictor columns are: Coconut_Productivity_DeclaredMillionUnit_per_Hectare_Lag1, T2M_Jun_Sep_Mean_Lag1, T2M_MIN_Jun_Sep_Mean_Lag1, ALLSKY_SFC_SW_DWN_Jan_Feb_Total_Lag3, WS10M_Mar_May_Mean_Lag1, RH2M_Mar_May_Mean_Lag3, PRECTOTCORR_Mar_May_Total_Lag3, T2M_MAX_Jun_Sep_Mean_Lag2. It contains no contemporaneous NASA features by default (`INCLUDE_CONTEMPORANEOUS_FEATURES=False`), preventing an implicit same-year information assumption. Rows with unavailable lagged values remain in the file as missing values; they were not fabricated or silently dropped.

### Target correlation ranking

| Feature | Correlation_With_Target | Absolute_Correlation | Sample_Size |
| --- | --- | --- | --- |
| Coconut_Productivity_DeclaredMillionUnit_per_Hectare_Lag1 | 0.915 | 0.915 | 40 |
| T2M_Jun_Sep_Mean_Lag1 | 0.6007 | 0.6007 | 40 |
| ALLSKY_SFC_SW_DWN_Jan_Feb_Total_Lag3 | 0.5428 | 0.5428 | 35 |
| T2M_MIN_Jun_Sep_Mean_Lag1 | 0.5158 | 0.5158 | 40 |
| RH2M_Mar_May_Mean_Lag3 | 0.4915 | 0.4915 | 38 |
| WS10M_Mar_May_Mean_Lag1 | -0.49 | 0.49 | 40 |
| PRECTOTCORR_Mar_May_Total_Lag3 | 0.446 | 0.446 | 38 |
| T2M_MAX_Jun_Sep_Mean_Lag2 | 0.4176 | 0.4176 | 39 |

### Potential redundancy

Predictor pairs with |Pearson r| ≥ 0.85:

None.

## Quality and statistical limitations

`data_quality_report.csv` reports retained missing values, duplicate/gap checks, simple range checks, and IQR-flagged outlier years; no outliers were removed. There are only 41 aligned annual targets (38 complete across all yearly features), and even fewer paired observations after lags. Multiple seasonal features and lag tests increase false-positive and multicollinearity risk. The outputs identify candidates for later validation, not a final predictor set or an ML-ready claim.
