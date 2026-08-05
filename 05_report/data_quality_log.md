# Data quality log — NovaGrid smart-meter extract

Source file: `Smart_Meter_Dataset - Copy - Smart_Meter_Dataset - Copy.csv.csv`
Raw rows: 6,764 · Rows used in analysis: 6,720

Every issue below was found by inspection, not assumed. Each row states what was done about it
and where in the pipeline that happens. Issues marked **carried forward** were *not* silently
repaired — they are real defects in the source system and repairing them here would hide them.

---

## Resolved during cleaning

| # | Issue | Evidence | Treatment | Where |
|---|---|---|---|---|
| 1 | **43 exact duplicate rows** | Same `recordid`, meter, timestamp and reading repeated up to 4× (e.g. `REC000010` appears 4 times, `REC006710` 4 times). Affects 4 households. | Dropped via `drop_duplicates()`. Left in, they double-count energy and inflate spike counts for those households. | `load_and_clean()` |
| 2 | **1 completely blank row** | Trailing row with every field null except `recordid`. | Dropped. | `load_and_clean()` |
| 3 | **Two different date formats in one file** | `reading_timestamp` = `DD/MM/YYYY HH:MM:SS` (UK). `alert_time` = `M/D/YYYY HH:MM` (US). | Parsed with separate explicit formats. **This is the most dangerous issue in the file:** parsing both with one format produces no error, just a silently wrong alert timeline. | `load_and_clean()` |
| 4 | **Booleans stored as strings** | `"TRUE"` / `"FALSE"` as text in `spike_detected`, `alert_sent`, `resolved`. | Mapped to real booleans; blanks preserved as null rather than coerced to `False`. | `load_and_clean()` |
| 5 | **1 missing `region`** | One row with a null region. | Filled as `"Unknown"` rather than dropped — the reading itself is valid. | `load_and_clean()` |
| 6 | **`resolved` blank on 6,606 rows** | Blank on every non-spike row. | Left null and read as *not applicable*, not as *missing*. A reading that was never a spike has nothing to resolve; imputing `False` would have understated the resolution rate. | `load_and_clean()` |

## Carried forward — reported, not repaired

| # | Issue | Evidence | Why it is left in |
|---|---|---|---|
| 7 | **`REC000015` is flagged as a spike but is not one** | Reading 0.30 kWh against a baseline of 0.36 kWh — 17% *below* baseline, `spike_percentage` = 0, no reason code, no alert, no resolution. It is the only record where `spike_detected` disagrees with `usage > 1.4 × baseline`. | It is a defect in the source system's flag logic. Removing it would hide a live bug. It is excluded from the waste-vs-percentage chart (where a negative excess is meaningless) and reported explicitly everywhere else. |
| 8 | **6 alerts timestamped before the reading that triggered them** | `alert_time − reading_timestamp` is negative on 6 spikes, by up to 5.2 minutes. | Physically impossible; a clock-skew or timezone defect in the alerting service. Latency statistics are reported with these included and the count flagged, so the metric is not quietly flattered. |
| 9 | **3 spikes with no alert** | `REC000015` (the mis-flag), `REC001414`, `REC004675`. The latter two are genuine spikes at +55%. | A real 2.6% notification leak. Counted in the alert-coverage KPI. |
| 10 | **1 spike with no reason code** | `REC000015` again. | Shown as "not recorded" rather than bucketed into a category. |

## Documentation mismatches

The brief and the data disagree in three places. The data was taken as the source of truth and the
mismatch recorded:

| # | Brief says | Data shows |
|---|---|---|
| 11 | Readings every 30 minutes | Every **28.8 minutes** (50 readings per meter per day, exactly 336 per meter over 7 days) |
| 12 | `baseline_kWh` = "4-week average for the same time slot" | The baseline changes **every day** for the same customer and time slot — 7 distinct values per customer per slot over 7 days. It is not a 4-week average of anything; the extract is only 7 days long. |
| 13 | Column named `record_id` | Column is actually named `recordid` (no underscore) |

## Structural characteristics worth knowing before using this data

- **Balanced by design.** Every one of the 20 meters has exactly 336 readings, on the same 336
  timestamps. There are no gaps, no missing intervals and no meter outages — unusual enough in real
  smart-meter data that it should be treated as a property of this extract rather than of the fleet.
- **Regions are unevenly weighted.** London 6 households, Leeds 6, Manchester 4, Glasgow 2,
  Bristol 2. Any regional percentage on Glasgow or Bristol rests on 13 and 7 spikes respectively —
  reported, but not a basis for decisions on its own.
- **Readings are bounded** at 0.10–1.44 kWh, and baselines at 0.30–1.20 kWh. The upper bound is
  what makes the `1.4 ×` rule structurally unable to fire on high-baseline readings; see
  `findings_report.md` §1.2.
- **Personal data.** The file contains customer names and email addresses. They are not required
  for any analysis in this project and are carried through only so cases can be identified
  operationally. If this work is shared outside the operations team, drop `customer_name` and
  `email` and key on `customer_id`.

---

*Regenerate this evidence with `python3 01_pipeline/novagrid_pipeline.py` — the cleaning counts and
the audit lists are written to `02_data_outputs/kpi_summary.json` under `cleaning` and `audit`.*
