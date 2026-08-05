"""
NovaGrid Energy — abnormal spike detection pipeline
====================================================
Reads the raw smart-meter extract, cleans it, engineers the analysis fields,
re-implements and audits the spike rule, and writes every downstream artefact
(clean data, spike event log, household scorecard, KPI summary, chart data).

Run:    python3 01_pipeline/novagrid_pipeline.py
Inputs: 00_data_raw/smart_meter_dataset.csv
Output: 02_data_outputs/*.csv, 02_data_outputs/*.json

Every cleaning decision is logged to 05_report/data_quality_log.md by hand;
this script is the executable half of that record.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

pd.set_option("future.no_silent_downcasting", True)

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "02_data_outputs"

# The extract is vendored into the repo so a fresh clone runs with no setup.
# The second path is the original drop location, kept as a fallback.
RAW = next(p for p in (
    ROOT / "00_data_raw" / "smart_meter_dataset.csv",
    ROOT.parent / "Smart_Meter_Dataset - Copy - Smart_Meter_Dataset - Copy.csv.csv",
) if p.exists())

# The rule NovaGrid documented in the case study brief.
SPIKE_MULTIPLIER = 1.4

# Ofgem energy price cap, electricity unit rate, Jan-Mar 2024 (Great Britain
# average, direct debit). Used to convert excess kWh into money. Assumption,
# not something the dataset supplies.
UNIT_RATE_GBP_PER_KWH = 0.2862

# NovaGrid had ~1m smart meters deployed by 2021 (company overview in the brief).
FLEET_SIZE = 1_000_000

# The brief asks for anomalies classified as appliance / behavioural /
# infrastructure. The raw `reason_detected` codes map onto that taxonomy.
REASON_TO_CATEGORY = {
    "Overnight appliance": "Appliance",
    "Heater malfunction": "Appliance",
    "Guest visit": "Behavioural",
    "Schedule change": "Behavioural",
}

# Reasons that imply a physical fault someone should go and fix, versus
# reasons that are a customer simply using more energy on purpose.
FAULT_REASONS = {"Heater malfunction", "Overnight appliance"}


# --------------------------------------------------------------------------
# 1. Load and clean
# --------------------------------------------------------------------------
def load_and_clean() -> tuple[pd.DataFrame, dict]:
    raw = pd.read_csv(RAW)
    log = {"rows_raw": len(raw)}

    # A trailing all-null row sits at the end of the export.
    df = raw.dropna(subset=["recordid", "customer_id", "reading_timestamp"]).copy()
    log["rows_dropped_blank"] = log["rows_raw"] - len(df)

    # 43 rows are byte-for-byte repeats of an earlier row (same record id, same
    # meter, same timestamp, same reading) — a re-run of the export, not real
    # readings. Left in, they double-count energy for four households.
    before = len(df)
    df = df.drop_duplicates()
    log["rows_dropped_duplicate"] = before - len(df)

    # The two timestamp columns arrive in different date formats:
    #   reading_timestamp -> DD/MM/YYYY HH:MM:SS  (UK)
    #   alert_time        -> M/D/YYYY HH:MM       (US)
    # Parsing both with one format silently destroys the alert timeline.
    df["reading_ts"] = pd.to_datetime(
        df["reading_timestamp"], format="%d/%m/%Y %H:%M:%S"
    )
    df["alert_ts"] = pd.to_datetime(
        df["alert_time"], format="%m/%d/%Y %H:%M", errors="coerce"
    )
    log["alert_time_unparsed"] = int(
        df["alert_time"].notna().sum() - df["alert_ts"].notna().sum()
    )

    # Booleans arrive as the strings "TRUE"/"FALSE"; `resolved` is blank on
    # every non-spike row, which is meaningful (not missing) — a reading that
    # was never a spike has nothing to resolve.
    for col in ("spike_detected", "alert_sent", "resolved"):
        df[col + "_b"] = (
            df[col].astype(str).str.upper().map({"TRUE": True, "FALSE": False})
        )

    df["region"] = df["region"].fillna("Unknown")
    return df, log


# --------------------------------------------------------------------------
# 2. Engineer the analysis fields
# --------------------------------------------------------------------------
def engineer(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["excess_kwh"] = df["energy_usage_kWh"] - df["baseline_kWh"]
    df["ratio"] = df["energy_usage_kWh"] / df["baseline_kWh"]
    df["excess_pct"] = (df["ratio"] - 1) * 100

    # Re-derive the vendor rule from first principles so the flag can be audited
    # rather than trusted.
    df["rule_spike"] = df["energy_usage_kWh"] > SPIKE_MULTIPLIER * df["baseline_kWh"]

    # Detection coverage: readings are physically capped at the highest value the
    # meter fleet has ever produced. Where 1.4 x baseline sits above that cap, no
    # reading can ever trip the rule — the household is unmonitored by design.
    meter_ceiling = df["energy_usage_kWh"].max()
    df["detectable"] = SPIKE_MULTIPLIER * df["baseline_kWh"] <= meter_ceiling

    df["alert_latency_min"] = (
        df["alert_ts"] - df["reading_ts"]
    ).dt.total_seconds() / 60

    df["category"] = df["reason_detected"].map(REASON_TO_CATEGORY)
    df["is_fault"] = df["reason_detected"].isin(FAULT_REASONS)

    df["excess_cost_gbp"] = df["excess_kwh"].clip(lower=0) * UNIT_RATE_GBP_PER_KWH

    df["hour"] = df["reading_ts"].dt.hour
    df["date"] = df["reading_ts"].dt.date
    df["day_name"] = df["reading_ts"].dt.day_name()

    return df


# --------------------------------------------------------------------------
# 3. Audit the vendor flag against the documented rule
# --------------------------------------------------------------------------
def audit_flag(df: pd.DataFrame) -> dict:
    flagged = df["spike_detected_b"] == True  # noqa: E712
    rule = df["rule_spike"]

    false_positive = df[flagged & ~rule]
    false_negative = df[~flagged & rule]

    spikes = df[flagged]
    return {
        "flagged": int(flagged.sum()),
        "rule_matches": int(rule.sum()),
        "false_positives": false_positive["recordid"].tolist(),
        "false_negatives": false_negative["recordid"].tolist(),
        "spikes_never_alerted": spikes[spikes["alert_sent_b"] != True][  # noqa: E712
            "recordid"
        ].tolist(),
        "alerts_on_non_spikes": int(
            ((df["spike_detected_b"] == False) & (df["alert_sent_b"] == True)).sum()  # noqa: E712
        ),
        "negative_latency": spikes[spikes["alert_latency_min"] < 0][
            "recordid"
        ].tolist(),
    }


# --------------------------------------------------------------------------
# 4. Aggregate
# --------------------------------------------------------------------------
def household_scorecard(df: pd.DataFrame) -> pd.DataFrame:
    spikes = df[df["spike_detected_b"] == True]  # noqa: E712

    sc = df.groupby(["customer_id", "customer_name", "region", "housing_type"]).agg(
        readings=("recordid", "size"),
        total_kwh=("energy_usage_kWh", "sum"),
        mean_baseline_kwh=("baseline_kWh", "mean"),
        detection_coverage=("detectable", "mean"),
    )

    agg = spikes.groupby("customer_id").agg(
        spikes=("recordid", "size"),
        fault_spikes=("is_fault", "sum"),
        excess_kwh=("excess_kwh", "sum"),
        excess_cost_gbp=("excess_cost_gbp", "sum"),
        max_excess_pct=("excess_pct", "max"),
        median_alert_latency_min=("alert_latency_min", "median"),
        resolved=("resolved_b", "sum"),
    )

    sc = sc.join(agg).fillna(
        {
            "spikes": 0,
            "fault_spikes": 0,
            "excess_kwh": 0.0,
            "excess_cost_gbp": 0.0,
            "resolved": 0,
        }
    )
    sc["spike_rate_pct"] = sc["spikes"] / sc["readings"] * 100
    sc["unresolved"] = sc["spikes"] - sc["resolved"]
    sc["resolution_rate_pct"] = np.where(
        sc["spikes"] > 0, sc["resolved"] / sc["spikes"] * 100, np.nan
    )
    sc["detection_coverage"] *= 100

    # Priority score: what an operations team should actually work down. Fault
    # spikes are worth more than behavioural ones (they recur until fixed), and
    # unresolved cases outrank closed ones.
    sc["priority_score"] = (
        sc["fault_spikes"] * 3 + sc["unresolved"] * 2 + sc["spikes"]
    ).round(1)

    return sc.reset_index().sort_values("priority_score", ascending=False)


def spike_events(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "recordid", "customer_id", "customer_name", "region", "housing_type",
        "meter_id", "reading_ts", "energy_usage_kWh", "baseline_kWh",
        "excess_kwh", "excess_pct", "excess_cost_gbp", "reason_detected",
        "category", "is_fault", "alert_sent_b", "alert_ts",
        "alert_latency_min", "resolved_b", "rule_spike",
    ]
    ev = df[df["spike_detected_b"] == True][cols].copy()  # noqa: E712
    ev = ev.rename(
        columns={
            "alert_sent_b": "alert_sent",
            "resolved_b": "resolved",
            "rule_spike": "matches_1_4x_rule",
        }
    )
    # Rank by energy actually wasted, not by headline percentage.
    ev["waste_rank"] = ev["excess_kwh"].rank(ascending=False, method="min").astype(int)
    ev["pct_rank"] = ev["excess_pct"].rank(ascending=False, method="min").astype(int)
    return ev.sort_values("reading_ts")


# --------------------------------------------------------------------------
# 5. KPI summary + chart data
# --------------------------------------------------------------------------
def build_kpis(df: pd.DataFrame, audit: dict, sc: pd.DataFrame) -> dict:
    spikes = df[df["spike_detected_b"] == True]  # noqa: E712
    n_hh = df["customer_id"].nunique()
    n_days = df["date"].nunique()

    excess_total = float(spikes["excess_kwh"].clip(lower=0).sum())
    per_hh_week = excess_total / n_hh / (n_days / 7)
    annual_hh_kwh = per_hh_week * 52

    # A "blind" reading is one where the 1.4x rule cannot physically fire.
    blind_share = float((~df["detectable"]).mean() * 100)
    # No spike has ever been recorded above this baseline — the practical, as
    # opposed to theoretical, edge of the detector.
    highest_spiking_baseline = float(spikes["baseline_kWh"].max())
    above_observed = float(
        (df["baseline_kWh"] > highest_spiking_baseline).mean() * 100
    )

    lat = spikes["alert_latency_min"].dropna()

    return {
        "window": {
            "start": str(df["reading_ts"].min()),
            "end": str(df["reading_ts"].max()),
            "days": int(n_days),
            "households": int(n_hh),
            "meters": int(df["meter_id"].nunique()),
            "regions": int(df["region"].nunique()),
            "readings": int(len(df)),
            # Interval is per meter — a global diff would read 0 because 20
            # meters report on the same timestamps.
            "reading_interval_min": round(
                df.sort_values("reading_ts")
                .groupby("customer_id")["reading_ts"]
                .diff()
                .dt.total_seconds()
                .mode()[0]
                / 60,
                1,
            ),
        },
        "detection": {
            "spikes": int(len(spikes)),
            "spike_rate_pct": round(len(spikes) / len(df) * 100, 2),
            "households_affected": int(spikes["customer_id"].nunique()),
            "false_positives": len(audit["false_positives"]),
            "false_negatives": len(audit["false_negatives"]),
            "blind_reading_share_pct": round(blind_share, 1),
            "readings_above_observed_spike_ceiling_pct": round(above_observed, 1),
            "highest_spiking_baseline_kwh": highest_spiking_baseline,
            "median_baseline_all_kwh": float(df["baseline_kWh"].median()),
            "median_baseline_spikes_kwh": float(spikes["baseline_kWh"].median()),
            "meter_ceiling_kwh": float(df["energy_usage_kWh"].max()),
        },
        "alerting": {
            "alerts_sent": int(spikes["alert_sent_b"].sum()),
            "alert_coverage_pct": round(
                spikes["alert_sent_b"].sum() / len(spikes) * 100, 1
            ),
            "spikes_never_alerted": len(audit["spikes_never_alerted"]),
            "median_latency_min": round(float(lat.median()), 1),
            "p90_latency_min": round(float(lat.quantile(0.9)), 1),
            "max_latency_min": round(float(lat.max()), 1),
            "negative_latency_count": len(audit["negative_latency"]),
        },
        "resolution": {
            "resolved": int(spikes["resolved_b"].sum()),
            "unresolved": int((spikes["resolved_b"] == False).sum()),  # noqa: E712
            "unknown": int(spikes["resolved_b"].isna().sum()),
            "resolution_rate_pct": round(
                spikes["resolved_b"].sum() / len(spikes) * 100, 1
            ),
        },
        "waste": {
            "excess_kwh_window": round(excess_total, 2),
            "excess_cost_window_gbp": round(excess_total * UNIT_RATE_GBP_PER_KWH, 2),
            "share_of_total_consumption_pct": round(
                excess_total / df["energy_usage_kWh"].sum() * 100, 2
            ),
            "annual_kwh_per_household": round(annual_hh_kwh, 1),
            "annual_gbp_per_household": round(
                annual_hh_kwh * UNIT_RATE_GBP_PER_KWH, 2
            ),
            "annual_gbp_fleet": round(
                annual_hh_kwh * UNIT_RATE_GBP_PER_KWH * FLEET_SIZE, 0
            ),
            "unit_rate_gbp_per_kwh": UNIT_RATE_GBP_PER_KWH,
            "fleet_size_assumed": FLEET_SIZE,
        },
        "concentration": {
            "top5_households_spike_share_pct": round(
                sc.nlargest(5, "spikes")["spikes"].sum() / len(spikes) * 100, 1
            ),
            "fault_spikes": int(spikes["is_fault"].sum()),
            "behavioural_spikes": int((~spikes["is_fault"]).sum()),
        },
    }


def build_chart_data(df: pd.DataFrame, sc: pd.DataFrame, ev: pd.DataFrame) -> dict:
    spikes = df[df["spike_detected_b"] == True]  # noqa: E712

    by_region = (
        df.groupby("region")
        .agg(readings=("recordid", "size"), households=("customer_id", "nunique"))
        .join(
            spikes.groupby("region").agg(
                spikes=("recordid", "size"),
                resolved=("resolved_b", "sum"),
                excess_kwh=("excess_kwh", "sum"),
                median_latency=("alert_latency_min", "median"),
            )
        )
        .fillna(0)
        .reset_index()
    )
    by_region["spikes_per_household"] = by_region["spikes"] / by_region["households"]
    by_region["resolution_rate"] = np.where(
        by_region["spikes"] > 0, by_region["resolved"] / by_region["spikes"] * 100, 0
    )

    by_reason = (
        spikes.groupby("reason_detected")
        .agg(
            spikes=("recordid", "size"),
            resolved=("resolved_b", "sum"),
            excess_kwh=("excess_kwh", "sum"),
            mean_excess_pct=("excess_pct", "mean"),
        )
        .reset_index()
    )
    by_reason["category"] = by_reason["reason_detected"].map(REASON_TO_CATEGORY)
    by_reason["resolution_rate"] = by_reason["resolved"] / by_reason["spikes"] * 100

    by_hour = (
        df.groupby("hour")
        .agg(mean_kwh=("energy_usage_kWh", "mean"))
        .join(spikes.groupby("hour").size().rename("spikes"))
        .fillna({"spikes": 0})
        .reset_index()
    )

    by_day = (
        df.groupby("date")
        .agg(total_kwh=("energy_usage_kWh", "sum"))
        .join(spikes.groupby("date").size().rename("spikes"))
        .fillna({"spikes": 0})
        .reset_index()
    )
    by_day["date"] = by_day["date"].astype(str)

    # Scatter for the coverage chart: every reading as (baseline, usage). Down-
    # sampled for the non-spike cloud so the page stays light; all spikes kept.
    cloud = df[df["spike_detected_b"] != True].sample(  # noqa: E712
        n=min(1800, (df["spike_detected_b"] != True).sum()), random_state=7
    )
    scatter = {
        "normal": cloud[["baseline_kWh", "energy_usage_kWh"]].round(3).values.tolist(),
        "spike": spikes[["baseline_kWh", "energy_usage_kWh"]]
        .round(3)
        .values.tolist(),
        "ceiling": float(df["energy_usage_kWh"].max()),
        "multiplier": SPIKE_MULTIPLIER,
    }

    latency = spikes["alert_latency_min"].dropna()
    hist, edges = np.histogram(latency, bins=np.arange(-10, 45, 5))

    return {
        "by_region": by_region.round(2).to_dict("records"),
        "by_reason": by_reason.round(2).to_dict("records"),
        "by_hour": by_hour.round(3).to_dict("records"),
        "by_day": by_day.round(2).to_dict("records"),
        "households": sc.round(2).to_dict("records"),
        "scatter": scatter,
        "latency_hist": {
            "counts": hist.tolist(),
            "edges": edges.tolist(),
            "median": round(float(latency.median()), 1),
        },
        "waste_vs_pct": ev[["excess_pct", "excess_kwh", "customer_id", "reason_detected"]]
        .round(3)
        .to_dict("records"),
        "funnel": [
            {"stage": "Spikes detected", "value": int(len(spikes))},
            {"stage": "Alerts sent", "value": int(spikes["alert_sent_b"].sum())},
            {"stage": "Cases resolved", "value": int(spikes["resolved_b"].sum())},
        ],
    }


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    df, clean_log = load_and_clean()
    df = engineer(df)
    audit = audit_flag(df)
    sc = household_scorecard(df)
    ev = spike_events(df)
    kpis = build_kpis(df, audit, sc)
    kpis["cleaning"] = clean_log
    kpis["audit"] = audit
    charts = build_chart_data(df, sc, ev)

    df.to_csv(OUT / "novagrid_clean.csv", index=False)
    ev.to_csv(OUT / "spike_events.csv", index=False)
    sc.to_csv(OUT / "household_scorecard.csv", index=False)
    (OUT / "kpi_summary.json").write_text(json.dumps(kpis, indent=2, default=str))
    (OUT / "chart_data.json").write_text(json.dumps(charts, indent=2, default=str))

    print(f"clean rows            {len(df)}")
    print(f"  dropped blank       {clean_log['rows_dropped_blank']}")
    print(f"  dropped duplicate   {clean_log['rows_dropped_duplicate']}")
    print(f"spikes                {kpis['detection']['spikes']}")
    print(f"  false positives     {audit['false_positives']}")
    print(f"  never alerted       {audit['spikes_never_alerted']}")
    print(f"  negative latency    {len(audit['negative_latency'])}")
    print(f"blind readings        {kpis['detection']['blind_reading_share_pct']}%")
    print(f"resolution rate       {kpis['resolution']['resolution_rate_pct']}%")
    print(f"annual waste / meter  £{kpis['waste']['annual_gbp_per_household']}")
    print(f"\nwrote 5 files to {OUT}")


if __name__ == "__main__":
    main()
