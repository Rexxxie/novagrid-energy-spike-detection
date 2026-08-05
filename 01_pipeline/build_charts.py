"""
NovaGrid — static chart set
===========================
Renders the presentation-ready PNGs from the pipeline outputs.
Run the pipeline first, then:  python3 01_pipeline/build_charts.py

Design rules applied throughout: one hue per series assigned by entity (never by
rank), a legend whenever two series share a plot, selective direct labels, thin
marks with 4px rounded data-ends, a 2px surface gap between stacked segments,
hairline recessive grid, zero-baselined value axes, and never a second y-axis.

Bar geometry note: rounded corners are built as an explicit path with the corner
radius converted from pixels into each axis's own data units, so a bar's length
is always exactly its value. Matplotlib's FancyBboxPatch rounds in x-data units
only, which silently shortens bars whenever the axes aspect isn't 1:1.
"""

from __future__ import annotations

import json
from pathlib import Path as FsPath

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.path import Path
from matplotlib.patches import PathPatch

ROOT = FsPath(__file__).resolve().parent.parent
DATA = ROOT / "02_data_outputs"
OUT = ROOT / "04_charts"

# --- palette -----------------------------------------------------------------
# Categorical slots 1-2 of the validated default theme (adjacent-pair CVD ΔE 24.7
# protan / 33.6 normal, both PASS on the #fcfcfb surface). Status colours are
# reserved: red only ever means "anomaly / below target", green only "resolved".
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

SERIES_1 = "#2a78d6"   # blue   — appliance / primary series
SERIES_2 = "#eb6834"   # orange — behavioural / secondary series
CRITICAL = "#d03b3b"   # status — spike, below target
RAMP = ["#86b6ef", "#3987e5", "#1c5cab"]  # ordinal ramp, funnel stages

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": INK_2,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "axes.titlesize": 15,
    "axes.labelsize": 10.5,
    "axes.linewidth": 0.8,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "legend.frameon": False,
    "legend.fontsize": 10,
    "figure.dpi": 160,
})

CORNER_PX = 4.0   # rounded data-end radius
GAP_PX = 2.0      # surface gap between adjacent / stacked fills


# --- chrome ------------------------------------------------------------------
def style(ax, xgrid=False, ygrid=True):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.set_axisbelow(True)
    if ygrid:
        ax.yaxis.grid(True, linestyle="-", linewidth=0.8, color=GRID)
    if xgrid:
        ax.xaxis.grid(True, linestyle="-", linewidth=0.8, color=GRID)
    ax.tick_params(length=0)


def title(ax, headline, sub=None, y=1.20):
    """Headline above the plot, deck-caption below it. Both left-aligned to the
    y-axis so the eye starts in the same place on every slide. The caption is
    top-anchored so extra lines grow downward into the gap and can never ride
    up over the headline."""
    ax.text(0, y, headline, transform=ax.transAxes, fontsize=15,
            fontweight="600", color=INK, va="bottom")
    if sub:
        ax.text(0, y - 0.04, sub, transform=ax.transAxes, fontsize=10.5,
                color=INK_2, va="top", linespacing=1.45)


def data_per_px(ax):
    """(x, y) data units per pixel for the *current* limits. Call after limits
    are final — the transform is read at this moment, not at draw time."""
    ax.figure.canvas.draw()
    bb = ax.get_window_extent()
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    return (x1 - x0) / bb.width, (y1 - y0) / bb.height


def rounded_bar(ax, x0, y0, w, h, dx, dy, color, round_end="right",
                radius_px=CORNER_PX, **kw):
    """Rectangle with two rounded corners at the data end. `dx`/`dy` are the
    data-per-pixel scales from data_per_px(). Length is exact."""
    rx, ry = radius_px * dx, radius_px * dy
    rx = min(rx, abs(w) / 2) if w else 0
    ry = min(ry, abs(h) / 2) if h else 0
    r = min(rx / dx if dx else 0, ry / dy if dy else 0)  # keep corners circular
    rx, ry = r * dx, r * dy
    x1, y1 = x0 + w, y0 + h
    k = 0.5523  # circle-to-cubic constant

    if round_end == "right":
        verts = [(x0, y0), (x1 - rx, y0),
                 (x1 - rx + rx * k, y0), (x1, y0 + ry - ry * k), (x1, y0 + ry),
                 (x1, y1 - ry),
                 (x1, y1 - ry + ry * k), (x1 - rx + rx * k, y1), (x1 - rx, y1),
                 (x0, y1), (x0, y0)]
        codes = [Path.MOVETO, Path.LINETO,
                 Path.CURVE4, Path.CURVE4, Path.CURVE4,
                 Path.LINETO,
                 Path.CURVE4, Path.CURVE4, Path.CURVE4,
                 Path.LINETO, Path.CLOSEPOLY]
    else:  # "top"
        verts = [(x0, y0), (x0, y1 - ry),
                 (x0, y1 - ry + ry * k), (x0 + rx - rx * k, y1), (x0 + rx, y1),
                 (x1 - rx, y1),
                 (x1 - rx + rx * k, y1), (x1, y1 - ry + ry * k), (x1, y1 - ry),
                 (x1, y0), (x0, y0)]
        codes = [Path.MOVETO, Path.LINETO,
                 Path.CURVE4, Path.CURVE4, Path.CURVE4,
                 Path.LINETO,
                 Path.CURVE4, Path.CURVE4, Path.CURVE4,
                 Path.LINETO, Path.CLOSEPOLY]

    ax.add_patch(PathPatch(Path(verts, codes), facecolor=color,
                           linewidth=0, **kw))


def save(fig, name):
    fig.savefig(OUT / name, bbox_inches="tight", pad_inches=0.4)
    plt.close(fig)
    print("  ", name)


# ---------------------------------------------------------------------------
def main():
    OUT.mkdir(parents=True, exist_ok=True)
    kpi = json.loads((DATA / "kpi_summary.json").read_text())
    ch = json.loads((DATA / "chart_data.json").read_text())
    ev = pd.read_csv(DATA / "spike_events.csv")
    sc = pd.read_csv(DATA / "household_scorecard.csv")

    print("rendering charts:")

    # -- 1. The blind spot -------------------------------------------------
    # Two classes on one scatter: ordinary readings (recessive grey) and flagged
    # spikes (status red). The rule line and the meter ceiling ARE the finding,
    # so both are drawn and labelled in place.
    fig, ax = plt.subplots(figsize=(9, 5.6))
    normal = np.array(ch["scatter"]["normal"])
    spike = np.array(ch["scatter"]["spike"])
    ceiling = ch["scatter"]["ceiling"]
    cut = ceiling / 1.4

    ax.set_xlim(0.25, 1.30)
    ax.set_ylim(0.05, 1.62)
    ax.axvspan(cut, 1.30, color=CRITICAL, alpha=0.05, linewidth=0)
    ax.scatter(normal[:, 0], normal[:, 1], s=9, c=MUTED, alpha=0.22,
               linewidths=0, label="Normal reading")
    ax.scatter(spike[:, 0], spike[:, 1], s=26, c=CRITICAL, alpha=0.9,
               linewidths=0.8, edgecolors=SURFACE, label="Flagged spike")

    xs = np.linspace(0.28, 1.16, 100)
    ax.plot(xs, 1.4 * xs, color=INK_2, linewidth=1.6, label="1.4 × baseline rule")
    ax.axhline(ceiling, color=AXIS, linewidth=1.2)
    ax.text(0.27, ceiling + 0.02, f"highest reading in the fleet — {ceiling} kWh",
            fontsize=9.5, color=MUTED)
    ax.text(cut + 0.02, 0.13,
            "the rule cannot fire here:\n1.4 × baseline is above what\n"
            f"any meter has ever reported\n\n{kpi['detection']['blind_reading_share_pct']}% of all readings",
            fontsize=9.5, color=CRITICAL, va="bottom", linespacing=1.45)

    ax.set_xlabel("Household baseline for this time slot (kWh)")
    ax.set_ylabel("Actual reading (kWh)")
    style(ax, xgrid=True)
    title(ax, "The 1.4× rule only watches low-consumption households",
          f"All {kpi['detection']['spikes']} flagged spikes sit on a baseline of "
          f"{kpi['detection']['highest_spiking_baseline_kwh']} kWh or below, while the fleet median "
          f"baseline is {kpi['detection']['median_baseline_all_kwh']} kWh.")
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.14), ncol=3)
    save(fig, "01_detection_blind_spot.png")

    # -- 2. Percentage misranks waste --------------------------------------
    fig, ax = plt.subplots(figsize=(8.8, 5.0))
    w = pd.DataFrame(ch["waste_vs_pct"])
    w = w[w.excess_kwh > 0]           # drop the mis-flagged record (logged separately)
    ax.set_xlim(35, 105)
    ax.set_ylim(0.10, 0.40)
    ax.scatter(w.excess_pct, w.excess_kwh, s=34, c=SERIES_1, alpha=0.75,
               linewidths=0.8, edgecolors=SURFACE)

    hi_pct = w.nlargest(1, "excess_pct").iloc[0]
    hi_kwh = w.nlargest(1, "excess_kwh").iloc[0]
    ax.annotate(f"loudest alert in the whole week\n+{hi_pct.excess_pct:.0f}% — but only "
                f"{hi_pct.excess_kwh:.2f} kWh, about {hi_pct.excess_kwh * 0.2862 * 100:.0f}p",
                (hi_pct.excess_pct, hi_pct.excess_kwh),
                xytext=(96, 0.155), fontsize=9.5, color=INK_2, ha="right",
                linespacing=1.4,
                arrowprops=dict(arrowstyle="-", color=AXIS, linewidth=1))
    ax.annotate(f"most energy actually wasted\n{hi_kwh.excess_kwh:.2f} kWh, reported as only "
                f"+{hi_kwh.excess_pct:.0f}%",
                (hi_kwh.excess_pct, hi_kwh.excess_kwh),
                xytext=(58, 0.375), fontsize=9.5, color=INK_2, ha="left",
                linespacing=1.4,
                arrowprops=dict(arrowstyle="-", color=AXIS, linewidth=1))

    ax.set_xlabel("Spike size as reported (% above baseline)")
    ax.set_ylabel("Energy actually wasted (kWh)")
    style(ax)
    title(ax, "The headline percentage is not the size of the problem",
          "Every flagged spike wastes between 0.13 and 0.34 kWh — 4p to 10p of electricity. "
          "The reported percentage mostly records how small\nthe baseline was, not how much "
          "energy went anywhere.")
    save(fig, "02_pct_vs_waste.png")

    # -- 3. Alert funnel ---------------------------------------------------
    fig, ax = plt.subplots(figsize=(8.6, 3.4))
    fn = ch["funnel"]
    ax.set_xlim(0, 160)
    ax.set_ylim(-0.55, len(fn) - 0.45)
    dx, dy = data_per_px(ax)
    for i, (stage, color) in enumerate(zip(fn, RAMP)):
        y = len(fn) - 1 - i
        rounded_bar(ax, 0, y - 0.16, stage["value"], 0.32, dx, dy, color)
        ax.text(stage["value"] + 3, y, f"{stage['value']}", va="center",
                fontsize=13, fontweight="600", color=INK)
        if i:
            ax.text(stage["value"] + 17, y,
                    f"{stage['value'] / fn[0]['value'] * 100:.0f}% of detected   "
                    f"·   {fn[i - 1]['value'] - stage['value']} lost at this step",
                    va="center", fontsize=10, color=INK_2)

    ax.set_yticks(range(len(fn)))
    ax.set_yticklabels([s["stage"] for s in reversed(fn)], fontsize=11, color=INK)
    ax.set_xticks([])
    for side in ("top", "right", "bottom", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    title(ax, "One in three detected spikes never reaches a resolution",
          "Detection and alerting both work. Everything that is lost, is lost after the alert goes out.",
          y=1.22)
    save(fig, "03_alert_funnel.png")

    # -- 4. Household priority --------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 5.4))
    top = sc.nlargest(10, "fault_spikes").sort_values(
        ["fault_spikes", "spikes"]).reset_index(drop=True)
    ax.set_xlim(0, top.spikes.max() + 2.2)
    ax.set_ylim(-0.7, len(top) - 0.3)
    dx, dy = data_per_px(ax)
    gap = GAP_PX * dx

    for i, r in top.iterrows():
        beh = r.spikes - r.fault_spikes
        rounded_bar(ax, 0, i - 0.22, r.fault_spikes, 0.44, dx, dy, SERIES_1)
        if beh > 0:
            rounded_bar(ax, r.fault_spikes + gap, i - 0.22, beh - gap, 0.44,
                        dx, dy, SERIES_2)
        ax.text(r.spikes + 0.28, i, f"{int(r.spikes)}", va="center",
                fontsize=10.5, color=INK_2)

    ax.set_yticks(range(len(top)))
    ax.set_yticklabels([f"{r.customer_id}  ·  {r.region}" for _, r in top.iterrows()],
                       fontsize=10, color=INK)
    ax.set_xlabel("Spikes in the 7-day window")
    style(ax, xgrid=True, ygrid=False)
    title(ax, "Half the caseload sits with a quarter of the households",
          f"The five worst households carry {kpi['concentration']['top5_households_spike_share_pct']}% "
          f"of all {kpi['detection']['spikes']} spikes. The blue segment is the part a single "
          f"field visit can remove permanently.")
    handles = [plt.Line2D([], [], marker="s", linestyle="", markersize=9,
                          color=SERIES_1, label="Appliance fault — recurs until fixed"),
               plt.Line2D([], [], marker="s", linestyle="", markersize=9,
                          color=SERIES_2, label="Behavioural — customer's own choice")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, -0.13), ncol=2)
    save(fig, "04_household_priority.png")

    # -- 5. Reason mix -----------------------------------------------------
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    rs = pd.DataFrame(ch["by_reason"]).sort_values("spikes", ascending=False
                                                   ).reset_index(drop=True)
    ax.set_xlim(-0.6, len(rs) - 0.4)
    ax.set_ylim(0, rs.spikes.max() + 10)
    dx, dy = data_per_px(ax)
    for i, r in rs.iterrows():
        color = SERIES_1 if r.category == "Appliance" else SERIES_2
        rounded_bar(ax, i - 0.17, 0, 0.34, r.spikes, dx, dy, color, round_end="top")
        ax.text(i, r.spikes + 1.3, f"{int(r.spikes)}", ha="center",
                fontsize=12, fontweight="600", color=INK)
        ax.text(i, r.spikes + 4.6, f"{r.resolution_rate:.0f}% resolved",
                ha="center", fontsize=9.5, color=INK_2)

    ax.set_xticks(range(len(rs)))
    ax.set_xticklabels(rs.reason_detected, fontsize=10.5, color=INK)
    ax.set_ylabel("Spikes")
    style(ax)
    title(ax, "Appliance faults are the majority — and the only fixable half",
          f"{kpi['concentration']['fault_spikes']} of {kpi['detection']['spikes']} spikes come from "
          f"equipment rather than behaviour. Behavioural cases are also the ones\nthat close least often.")
    handles = [plt.Line2D([], [], marker="s", linestyle="", markersize=9,
                          color=SERIES_1, label="Appliance"),
               plt.Line2D([], [], marker="s", linestyle="", markersize=9,
                          color=SERIES_2, label="Behavioural")]
    ax.legend(handles=handles, loc="upper right", ncol=2)
    save(fig, "05_reason_mix.png")

    # -- 6. Hourly profile — two measures, two panels, never two axes ------
    fig, axes = plt.subplots(2, 1, figsize=(9, 6.8),
                             gridspec_kw={"hspace": 0.62})
    hr = pd.DataFrame(ch["by_hour"])

    a = axes[0]
    a.set_xlim(-0.7, 23.7)
    a.set_ylim(0, 1.0)
    a.plot(hr.hour, hr.mean_kwh, color=SERIES_1, linewidth=2)
    lo, hi = hr.mean_kwh.idxmin(), hr.mean_kwh.idxmax()
    for idx, va in ((lo, "top"), (hi, "bottom")):
        a.scatter(hr.hour[idx], hr.mean_kwh[idx], s=34, color=SERIES_1, zorder=3,
                  edgecolors=SURFACE, linewidths=1.6)
        a.text(hr.hour[idx], hr.mean_kwh[idx] + (0.05 if va == "bottom" else -0.05),
               f"{hr.mean_kwh[idx]:.2f}", ha="center", va=va, fontsize=10,
               color=INK_2)
    a.set_xticks(range(0, 24, 2))
    a.set_ylabel("Mean kWh per reading")
    style(a)
    title(a, "There is no peak period in this data",
          "Mean consumption moves between 0.69 and 0.78 kWh across the whole 24-hour cycle.\n"
          "A 12% spread is flat, not diurnal — 'waste concentrates in peak hours' cannot be "
          "claimed from this data.", y=1.34)

    b = axes[1]
    b.set_xlim(-0.7, 23.7)
    b.set_ylim(0, hr.spikes.max() + 2)
    dx, dy = data_per_px(b)
    for h, s in zip(hr.hour, hr.spikes):
        if s:
            rounded_bar(b, h - 0.3, 0, 0.6, s, dx, dy, CRITICAL, round_end="top")
    b.set_ylabel("Spikes")
    b.set_xlabel("Hour of day")
    b.set_xticks(range(0, 24, 2))
    style(b)
    title(b, "Spikes are spread evenly around the clock too", y=1.10)
    save(fig, "06_hourly_profile.png")

    # -- 7. Regional resolution -------------------------------------------
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    rg = pd.DataFrame(ch["by_region"]).sort_values("resolution_rate"
                                                   ).reset_index(drop=True)
    fleet = kpi["resolution"]["resolution_rate_pct"]
    ax.set_xlim(-0.6, len(rg) - 0.4)
    ax.set_ylim(0, 118)
    dx, dy = data_per_px(ax)
    for i, r in rg.iterrows():
        below = r.resolution_rate < fleet
        rounded_bar(ax, i - 0.21, 0, 0.42, r.resolution_rate, dx, dy,
                    CRITICAL if below else SERIES_1, round_end="top")
        ax.text(i, r.resolution_rate + 3, f"{r.resolution_rate:.0f}%", ha="center",
                fontsize=12, fontweight="600", color=INK)
        ax.text(i, r.resolution_rate + 9.5, f"{int(r.spikes)} cases", ha="center",
                fontsize=9.5, color=MUTED)
    ax.axhline(fleet, color=INK_2, linewidth=1.4)
    ax.text(-0.55, fleet + 2.5, f"fleet average {fleet}%",
            ha="left", fontsize=9.5, color=INK_2)
    ax.set_xticks(range(len(rg)))
    ax.set_xticklabels(rg.region, fontsize=10.5, color=INK)
    ax.set_ylabel("Cases resolved (%)")
    style(ax)
    title(ax, "Resolution is an operations problem, not a detection one",
          "Manchester closes half its cases; Glasgow closes nine in ten — on the same detector, "
          "the same alert, and the same 14-minute latency.")
    save(fig, "07_region_resolution.png")

    # -- 8. Alert latency --------------------------------------------------
    fig, ax = plt.subplots(figsize=(8.6, 4.6))
    lh = ch["latency_hist"]
    edges = np.array(lh["edges"])
    counts = lh["counts"]
    ax.set_xlim(-13, 43)
    ax.set_ylim(0, max(counts) * 1.18)
    dx, dy = data_per_px(ax)
    for e0, e1, n in zip(edges[:-1], edges[1:], counts):
        if n:
            rounded_bar(ax, e0 + 0.4, 0, (e1 - e0) - 0.8, n, dx, dy,
                        CRITICAL if e0 < 0 else SERIES_1, round_end="top")
    ax.axvline(lh["median"], color=INK_2, linewidth=1.4)
    ax.text(lh["median"] + 1.2, max(counts) * 1.10, f"median {lh['median']} min",
            fontsize=10, color=INK_2)
    ax.text(-12, max(counts) * 0.62,
            f"{kpi['alerting']['negative_latency_count']} alerts are timestamped\nearlier than the reading\nthey refer to",
            fontsize=9.5, color=CRITICAL, va="top", linespacing=1.45)
    ax.set_xlabel("Minutes from meter reading to customer alert")
    ax.set_ylabel("Alerts")
    style(ax)
    title(ax, "Alerting is genuinely near-real-time",
          f"All {kpi['alerting']['alerts_sent']} alerts went out within "
          f"{kpi['alerting']['max_latency_min']:.0f} minutes of the reading — against a "
          f"complaint cycle currently measured in weeks.")
    save(fig, "08_alert_latency.png")

    print(f"\n{len(list(OUT.glob('*.png')))} charts written to {OUT}")


if __name__ == "__main__":
    main()
