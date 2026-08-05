"""
NovaGrid — dashboard builder
============================
Injects a compact columnar payload into the dashboard template and writes the
self-contained HTML. Nothing is fetched at runtime, so the file opens straight
from disk (or from a shared drive) with no server.

Run the pipeline first, then:  python3 01_pipeline/build_dashboard.py
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "02_data_outputs"
DASH = ROOT / "03_dashboard"


def compact(df: pd.DataFrame) -> dict:
    """Columnar payload: dimension values are interned to keep the file small
    enough to email, while every one of the 6,720 readings stays present so the
    dashboard can re-aggregate under any filter combination."""
    regions = sorted(df.region.unique())
    housing = sorted(df.housing_type.unique())
    custs = sorted(df.customer_id.unique())
    reasons = sorted(df.reason_detected.dropna().unique())

    names = df.drop_duplicates("customer_id").set_index("customer_id")["customer_name"]

    def code(series, vocab):
        idx = {v: i for i, v in enumerate(vocab)}
        return [int(idx[v]) if v in idx else -1 for v in series]

    spike = (df.spike_detected_b == True)  # noqa: E712

    return {
        "vocab": {
            "region": regions,
            "housing": housing,
            "customer": custs,
            "customer_name": [str(names[c]) for c in custs],
            "reason": reasons,
        },
        "n": int(len(df)),
        "region": code(df.region, regions),
        "housing": code(df.housing_type, housing),
        "customer": code(df.customer_id, custs),
        "usage": [round(float(v), 3) for v in df.energy_usage_kWh],
        "base": [round(float(v), 3) for v in df.baseline_kWh],
        "hour": [int(v) for v in df.hour],
        "day": [str(v) for v in df.date],
        "spike": [int(v) for v in spike],
        "reason": code(df.reason_detected.fillna("~"), reasons),
        "alert": [int(v == True) for v in df.alert_sent_b],  # noqa: E712
        "resolved": [
            (1 if v is True else (0 if v is False else -1)) for v in df.resolved_b
        ],
        "latency": [
            (None if pd.isna(v) else round(float(v), 1)) for v in df.alert_latency_min
        ],
        "record": list(df.recordid),
        "ts": [str(v) for v in df.reading_ts],
    }


def main() -> None:
    df = pd.read_csv(DATA / "novagrid_clean.csv")
    kpi = json.loads((DATA / "kpi_summary.json").read_text())

    payload = {
        "readings": compact(df),
        "constants": {
            "multiplier": 1.4,
            "ceiling": kpi["detection"]["meter_ceiling_kwh"],
            "unit_rate": kpi["waste"]["unit_rate_gbp_per_kwh"],
            "fleet": kpi["waste"]["fleet_size_assumed"],
            "window": kpi["window"],
            "cleaning": kpi["cleaning"],
            "audit_false_positives": kpi["audit"]["false_positives"],
            "audit_never_alerted": kpi["audit"]["spikes_never_alerted"],
            "audit_negative_latency": kpi["audit"]["negative_latency"],
        },
        "fault_reasons": ["Heater malfunction", "Overnight appliance"],
    }

    tpl = (DASH / "dashboard.template.html").read_text()
    out = tpl.replace(
        "/*__DATA__*/null",
        json.dumps(payload, separators=(",", ":"), default=str),
    )
    target = DASH / "novagrid_dashboard.html"
    target.write_text(out)
    print(f"wrote {target}  ({len(out) / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
