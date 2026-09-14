# Coconut Yield Prediction — Data Discovery Report

**Scope:** first-pass, read-only inspection of the raw project as found on 17 August 2026. No raw data was changed, no raster was converted, no annual/dynamic dataset was created, and no machine-learning, correlation, ACF, PACF, or cross-correlation analysis was run.

## 1. Complete inventory

The `dataset/` directory contains 98 files (731,022,381 bytes) when the archive and its already-unpacked duplicate are both counted.

| Location | Type / contents | Count | Size |
| --- | --- | ---: | ---: |
| `dataset/trend-of-coconut-production-in-kerala(in).csv` | Coconut annual table | 1 | 1,462 B |
| `dataset/POWER_Point_Monthly_19810101_20221231_010d85N_076d27E_LST(in).csv` | NASA POWER monthly/annual table with a 15-line metadata header | 1 | 26,867 B |
| `dataset/satellite/S2A_MSIL2A_20170210T045931_N0500_R119_T44PKT_20230916T013342.SAFE.zip` | ZIP of the Sentinel-2 SAFE product | 1 | 365,514,519 B |
| `dataset/satellite/S2A_MSIL2A_20170210T045931_N0500_R119_T44PKT_20230916T013342.SAFE/` | Unpacked copy of the same product | 95 files | 365,479,533 B |

The archive passes `unzip -t` integrity testing. Its 95 members match the unpacked product's file-type composition: 68 JP2, 14 XML, 3 XSD, 3 PNG, 2 JPG, 1 each of HTML/XSL/SAFE manifest, and 2 extensionless auxiliary files. It should be treated as a duplicate backup, not a second observation.

The unpacked SAFE contains the following complete data groups (all dates in the filenames are `20170210T045931`):

| Subtree | Exact contents |
| --- | --- |
| `IMG_DATA/R10m` | `B02`, `B03`, `B04`, `B08`, `TCI`, `AOT`, `WVP` (7 JP2) |
| `IMG_DATA/R20m` | `B01`, `B02`, `B03`, `B04`, `B05`, `B06`, `B07`, `B8A`, `B11`, `B12`, `TCI`, `AOT`, `WVP`, `SCL` (14 JP2) |
| `IMG_DATA/R60m` | `B01`, `B02`, `B03`, `B04`, `B05`, `B06`, `B07`, `B8A`, `B09`, `B11`, `B12`, `TCI`, `AOT`, `WVP`, `SCL` (15 JP2) |
| `QI_DATA` | `MSK_CLASSI_B00`; cloud- and snow-probability masks at 20 m and 60 m; 13 `MSK_DETFOO_*`; 13 `MSK_QUALIT_*`; and `PVI` (32 JP2) |
| Product/tile metadata | `MTD_MSIL2A.xml`, tile `MTD_TL.xml`, datastrip `MTD_DS.xml`, `INSPIRE.xml`, `manifest.safe`, three metadata XSDs, 11 quality XML files, and two auxiliary files |
| Product visual/support files | one quicklook JPG, one HTML index, one XSL, three banner PNGs, and one background JPG |

There are no notebooks, source modules, processed-data directories, outputs, or project README at present.

## 2. Coconut production table

**File:** `dataset/trend-of-coconut-production-in-kerala(in).csv`  
**Rows:** 67; **duplicates:** no duplicate agriculture-year labels; **missing cells:** none.  
**Columns:**

| Column | Observed values / structure | Unit status |
| --- | --- | --- |
| `Agriculture Year` | `1955-56` through `2021-22`, one record per labelled agricultural year | Two-year label. The file does not state whether the record should align to the starting, ending, or a different reporting year. |
| `Area Hectare` | 447,952–925,783 | Header explicitly says hectares. |
| `Production Million Unit` | 2,602–6,326 | The header says “Million Unit” but does **not** identify the commodity unit (for example, nuts, tonnes, or another unit). |

The filename identifies the series as Kerala, but the CSV itself has no district, point, polygon, coordinate, source citation, or harvest-calendar metadata. It is therefore a Kerala-wide aggregate target, not a point observation.

### Yield/productivity status

No yield/productivity variable exists in the raw table. A numeric productivity ratio can only be expressed provisionally as:

`production_per_hectare = Production Million Unit / Area Hectare`

If—and only if—the unnamed production unit is confirmed to be *million coconuts*, converting that ratio to coconuts/ha would multiply it by 1,000,000. The present files do not support that assumption, so no target yield was calculated in this discovery pass. The original data source or a data dictionary is required before fixing the target unit and formula.

## 3. NASA POWER table

**File:** `dataset/POWER_Point_Monthly_19810101_20221231_010d85N_076d27E_LST(in).csv`  
**Format:** CSV with 15 metadata lines followed by a `PARAMETER,YEAR,JAN,...,DEC,ANN` header.  
**Temporal resolution:** monthly values plus `ANN`; local solar time (LST).  
**Location:** latitude 10.8505, longitude 76.2673; MERRA-2 grid-cell mean elevation 370.89 m (0.5 × 0.625 degree region).  
**Coverage:** 1981–2022 inclusive, 294 parameter-year records (7 parameters × 42 years), exactly one record per parameter/year.

| Parameter | NASA header meaning and unit | Missingness | Appropriate later aggregation |
| --- | --- | --- | --- |
| `ALLSKY_SFC_SW_DWN` | All-sky surface shortwave downward irradiance, MJ/m²/day | All 13 monthly/annual cells are `-999` in 1981–1983; otherwise complete | Day-weighted mean daily irradiance; if seasonal energy exposure is wanted, sum each monthly daily rate × days in month (MJ/m²). |
| `PRECTOTCORR` | Corrected precipitation, mm/day | Complete | Sum monthly daily rates × days in month to obtain seasonal/annual precipitation (mm). |
| `RH2M` | Relative humidity at 2 m, % | Complete | Day-weighted seasonal/annual mean (%); retain monthly values where seasonal detail is retained. |
| `T2M` | Temperature at 2 m, °C | Complete | Day-weighted seasonal/annual mean (°C). |
| `T2M_MAX` | Temperature at 2 m maximum, °C | Complete | Retain as the day-weighted mean of the monthly maximum-temperature statistic; do not relabel it an annual absolute maximum. |
| `T2M_MIN` | Temperature at 2 m minimum, °C | Complete | Retain as the day-weighted mean of the monthly minimum-temperature statistic; do not relabel it an annual absolute minimum. |
| `WS10M` | Wind speed at 10 m, m/s | Complete | Day-weighted seasonal/annual mean (m/s). |

`-999` is explicitly declared by the NASA header as the missing-data code. No other parameter/year duplication or missingness was found. The NASA data is an environmental point/grid-cell proxy; it is not documented as a Kerala-wide spatial aggregation.

## 4. Satellite / JP2 inspection

The satellite data is one **Sentinel-2A MSI Level-2A** product (`S2MSI2A`), processing baseline 05.00—not an annual or seasonal satellite time series. Its sensing date is **2017-02-10 04:59:31 UTC** (tile sensing time 05:15:43 UTC); the 2023 timestamps in the product name/metadata are generation and archiving times, not acquisition dates. The product itself does not assign a season.

### Geospatial metadata

| Property | Value documented in product/tile metadata |
| --- | --- |
| Tile | `T44PKT` |
| CRS | `EPSG:32644`, WGS 84 / UTM zone 44N |
| Main-image grids | 10 m: 10,980 × 10,980; 20 m: 5,490 × 5,490; 60 m: 1,830 × 1,830 |
| Upper-left origin | E 199,980 m, N 1,300,020 m |
| Pixel size | 10/20/60 m, with negative northing step in the affine grid |
| WGS84 product footprint | approximately 10.7590–11.5496°N and 78.8289–79.2604°E |
| Product cloud assessment | 4.300489%; cloud shadow 3.399076%; metadata NODATA percentage 72.659332% |
| Georeferencing | Yes: CRS, grid origin, pixel dimensions, and footprint are present. |

This footprint is roughly 2.56° east of the NASA longitude (76.2673°E) and is not spatially compatible with that point. It is also not a Kerala-wide observation. The coconut table has no geometry with which to prove a specific spatial intersection. This is a hard validity issue, not a preprocessing detail.

### Bands, scaling, and special values

The product metadata explicitly identifies Sentinel-2 physical bands and their native resolutions: B1 (60 m), B2/B3/B4/B8 (10 m), B5/B6/B7/B8A/B11/B12 (20 m), and B9/B10 (60 m). The listed JP2 file paths corroborate the image-file identifiers; no band names have been inferred from image appearance.

Metadata records BOA quantification 10,000, BOA per-band additive offsets of −1,000, AOT quantification 1,000, and WVP quantification 1,000 cm. Product-level special values are NODATA = 0 and saturated = 65,535. Any later calculation must apply the product's declared scale/offset and mask invalid, cloud, cloud-shadow, snow, and saturation pixels; it must verify file-specific nodata/dtype directly with GDAL/rasterio rather than assume the product-level values apply identically to every quality layer.

The present environment lacks `rasterio`, GDAL (`gdalinfo`), `pyproj`, and JP2 inspection utilities. The SAFE XML provides the main image grid metadata above, but individual JP2 band count, datatype, and file-specific tags have not been independently opened. This is explicitly unresolved and should be rechecked in a geospatial-enabled environment before extraction.

The product contains no documented NDVI/EVI/NDWI raster. `TCI` is a true-colour image product and the `PVI` item is in `QI_DATA`; neither should be treated as a vegetation index without product-specific verification. A future NDVI is technically possible only after the spatial problem is solved, using documented B08 and B04 reflectance on a common grid and a valid agricultural AOI.

## 5. Temporal and geographic overlap

| Dataset | Actual temporal coverage | Spatial coverage | Consequence |
| --- | --- | --- | --- |
| Coconut | Agricultural years 1955-56–2021-22 | Kerala aggregate stated only by filename; no geometry in file | Target labels need a calendar-year mapping decision. |
| NASA POWER | Calendar years 1981–2022, monthly + annual | One 10.8505°N, 76.2673°E grid-cell proxy | Complete for six parameters; radiation usable from 1984. |
| Satellite | One acquisition, 10 Feb 2017 | Sentinel tile T44PKT, approximately 78.83–79.26°E | Neither multi-year nor co-located with the NASA point / Kerala target. |

For coconut + NASA alone, assuming the agricultural label is keyed to its **starting** calendar year, the label overlap is 1981-82–2021-22 (41 records), or 1984-85–2021-22 (38 records) when all seven NASA variables including radiation are required. That assumption is not validated by the raw data. If labels are instead keyed to their ending year, the paired labels differ by one year.

For all three sources there is **no usable common period**: satellite has one date only and fails the geographic compatibility check. Ignoring the geographic failure would yield only one ambiguous agriculture-year association for February 2017, which is not an annual time series and must not be fabricated into missing satellite years.

## 6. Proposed, validation-first harmonization

1. Obtain/confirm the coconut source's production unit and its agriculture-year calendar convention. Define a target-year mapping once, document it, and retain the original label.
2. Retain every NASA monthly value. After the target calendar is known, assign months to the corresponding agricultural year and calculate named seasonal summaries using day-weighted means or day-weighted totals as specified above. Do not use an unweighted average for precipitation or irradiance accumulation.
3. Define season month sets only from an approved Kerala crop/calendar rationale; the raw files do not specify seasons. The resulting feature names should contain the exact month range (for example `PRECTOTCORR_Jun_Sep_mm`) so they remain auditable.
4. Do **not** extract satellite predictors from the current product for this Kerala/NASA analysis. Acquire a temporally repeated Sentinel collection covering the same validated AOI and target years (or replace/re-locate the NASA and target geography). Preserve each acquisition date and derive per-acquisition features before any annual/seasonal aggregation.
5. Once spatially compatible imagery is available, use SCL and probability masks, crop/mask to a documented coconut/target AOI, harmonize grid/resampling intentionally, and calculate robust AOI summaries (valid-pixel count, median, mean, quantiles, and cloud fraction). Only then compute documented indices such as NDVI from B08/B04 reflectance. Keep the JP2s unchanged.

## 7. Proposed analysis after the blockers are resolved

The future base table should stay chronological and have one row per explicitly mapped target agriculture year, retaining original annual target fields and named seasonal NASA/satellite summaries. It should not be built now.

Before choosing lags, analyze the validated, contiguous target series with ACF and PACF. Set the tested maximum lag from available sample size and pre-declare it (not from a favourable result); inspect confidence intervals and domain plausibility. For each environmental feature, calculate lagged Pearson (and optionally Spearman) correlations using an explicit convention such as `feature(t-k)` versus `yield(t)`, report the paired sample size at every lag, and retain only candidates supported by timing, uncertainty, and agronomic reasoning. Candidate `yield(t-1)` must be generated only after calendar alignment and must not leak future data.

Only after that review should a dynamic dataset, feature-metadata table, correlation matrix/heatmap, target-feature ranking, and a redundancy report be produced. With the currently valid all-feature coconut+NASA overlap, there would be at most 38 observations before lagging; this will make high-dimensional seasonal/lags exploration statistically fragile even after the satellite issue is fixed.

## 8. Decisions / inputs required before implementation

1. Authoritative source or documentation for `Production Million Unit`, and the intended productivity unit.
2. The agriculture-year-to-calendar-month mapping and the intended forecasting cutoff (what information is allowed when predicting a target year).
3. A geographically compatible coconut AOI (state/district/polygon or approved sampling design) and satellite observations spanning enough years to support the intended analysis.
4. A geospatial-capable runtime (GDAL/rasterio/pyproj) for direct JP2 validation and later read-only extraction.

**Stop point:** this discovery report is the requested first-execution deliverable. No implementation beyond inspection has been performed.
