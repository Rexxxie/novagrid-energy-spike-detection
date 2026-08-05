"""
NovaGrid — all-charts dashboard poster
======================================
One image that reads as a working analytics console rather than a wall of
charts: app chrome, a filter bar, a KPI strip, titled panels and a live
worklist table — with every chart in the project inside it.

    06_linkedin/all_charts_poster.png

Charts are rendered bare (no baked-in headline) at exactly the pixel size of
the panel that holds them, so panel headers carry the titles and every row
lines up. Nothing is scaled after the fact.

Run after novagrid_pipeline.py:  python3 01_pipeline/build_linkedin_poster.py
Requires Google Chrome and Pillow.
"""

from __future__ import annotations

import base64
import http.server
import json
import shutil
import socketserver
import subprocess
import threading
from contextlib import closing
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from PIL import Image

from build_charts import rounded_bar, data_per_px

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "02_data_outputs"
OUT = ROOT / "06_linkedin"
TMP = OUT / ".poster"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

BYLINE = "Rexley Adio"          # change this line to re-brand the console
HANDLE = "Data Analyst"

# --- tokens ------------------------------------------------------------------
PLANE = "#0a0a0a"      # app background
PANEL = "#141413"      # panel surface
RAIL = "#101010"       # sidebar
EDGE = "#262624"
EDGE_2 = "#1d1d1c"
INK = "#ffffff"
INK_2 = "#c3c2b7"
MUTED = "#7f7d77"
DIM = "#5a5955"
S1 = "#3987e5"
S2 = "#d95926"
CRIT = "#e05555"
GOOD = "#2eb85c"
RAMP = ["#86b6ef", "#3987e5", "#1c5cab"]

# --- geometry (CSS px; the page renders at 1.5x) ------------------------------
CANVAS_W = 2560
RAIL_W = 258
PAD = 30
GAP = 18
COLS = 3
CONTENT_W = CANVAS_W - RAIL_W - PAD * 2
COL_W = (CONTENT_W - GAP * (COLS - 1)) / COLS          # 738.0
PANEL_PAD = 15
HEAD_H = 47
BODY_PAD = 14

WIDE_W = COL_W * 2 + GAP
H_HERO, H_STD, H_TALL = 452, 404, 428


def body_px(panel_w, panel_h):
    return (round(panel_w - PANEL_PAD * 2), round(panel_h - HEAD_H - BODY_PAD - PANEL_PAD))


plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "figure.facecolor": PANEL, "axes.facecolor": PANEL, "savefig.facecolor": PANEL,
    "axes.edgecolor": "#3a3a37", "axes.labelcolor": MUTED, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "font.size": 10, "xtick.labelsize": 9.5, "ytick.labelsize": 9.5,
    "axes.labelsize": 9.5, "axes.linewidth": 0.9,
    "grid.color": "#242422", "grid.linewidth": 0.9,
    "legend.frameon": False, "legend.fontsize": 9.5,
})


def panel_fig(w_css, h_css, left=54, right=14, top=12, bottom=42):
    """A figure whose saved pixel size is exactly 2x the panel body, with
    margins given in CSS px so every panel's plot area lines up."""
    fig = plt.figure(figsize=(w_css / 100, h_css / 100), dpi=200)
    ax = fig.add_axes([left / w_css, bottom / h_css,
                       1 - (left + right) / w_css, 1 - (top + bottom) / h_css])
    return fig, ax


def style(ax, xgrid=False, ygrid=True):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#33332f")
    ax.set_axisbelow(True)
    if ygrid:
        ax.yaxis.grid(True, linestyle="-", linewidth=0.9, color="#242422")
    if xgrid:
        ax.xaxis.grid(True, linestyle="-", linewidth=0.9, color="#242422")
    ax.tick_params(length=0)


def save(fig, name):
    p = TMP / name
    fig.savefig(p, facecolor=PANEL)
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


def ticks(max_v, n=4):
    step = 10 ** np.floor(np.log10(max(max_v / n, 1e-9)))
    err = max_v / n / step
    mult = 10 if err >= 7.5 else 5 if err >= 3 else 2 if err >= 1.5 else 1
    s = step * mult
    return [round(v, 6) for v in np.arange(0, max_v + 1e-9, s)]


# ============================================================================
# panels
# ============================================================================
def p_blindspot(ch, kpi, w, h):
    fig, ax = panel_fig(w, h, left=58, right=16, top=14, bottom=68)
    normal = np.array(ch["scatter"]["normal"])
    spike = np.array(ch["scatter"]["spike"])
    ceiling, cut = ch["scatter"]["ceiling"], ch["scatter"]["ceiling"] / 1.4
    ax.set_xlim(0.26, 1.29)
    ax.set_ylim(0.08, 1.62)
    ax.axvspan(cut, 1.29, color=CRIT, alpha=0.10, linewidth=0)
    ax.scatter(normal[:, 0], normal[:, 1], s=6, c=MUTED, alpha=0.28, linewidths=0)
    ax.scatter(spike[:, 0], spike[:, 1], s=22, c=CRIT, alpha=0.95,
               linewidths=0.7, edgecolors=PANEL)
    xs = np.linspace(0.28, 1.15, 80)
    ax.plot(xs, 1.4 * xs, color=INK_2, linewidth=1.5)
    ax.axhline(ceiling, color="#43433f", linewidth=1.2)
    ax.text(cut - 0.02, ceiling + 0.04, f"fleet maximum reading — {ceiling} kWh",
            fontsize=9, color=MUTED, ha="right")
    ax.text(cut + 0.02, 0.30, "the 1.4× rule can never fire in this band",
            fontsize=10, color=CRIT, fontweight="600")
    ax.text(cut + 0.02, 0.20, f"{kpi['detection']['blind_reading_share_pct']}% of all readings",
            fontsize=9.5, color=CRIT)
    ax.set_xlabel("Household baseline for this half hour (kWh)")
    ax.set_ylabel("Actual reading (kWh)")
    style(ax, xgrid=True)
    for lbl, col, mk in (("Normal reading", MUTED, "o"), ("Flagged spike", CRIT, "o"),
                         ("1.4 × baseline rule", INK_2, "_")):
        ax.scatter([], [], c=col, s=26, marker=mk, label=lbl)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.155), ncol=3,
              handletextpad=.4, columnspacing=2.4, labelcolor=INK_2)
    return save(fig, "blind.png")


def p_reasons(ch, w, h):
    fig, ax = panel_fig(w, h, left=42, right=12, top=22, bottom=46)
    rs = pd.DataFrame(ch["by_reason"]).sort_values("spikes", ascending=False).reset_index(drop=True)
    t = ticks(rs.spikes.max())
    top = max(t[-1], rs.spikes.max() * 1.22)
    ax.set_xlim(-0.6, len(rs) - 0.4)
    ax.set_ylim(0, top)
    dx, dy = data_per_px(ax)
    for i, r in rs.iterrows():
        rounded_bar(ax, i - 0.19, 0, 0.38, r.spikes, dx, dy,
                    S1 if r.category == "Appliance" else S2, round_end="top")
        ax.text(i, r.spikes + top * .04, str(int(r.spikes)), ha="center",
                fontsize=12, fontweight="600", color=INK)
        ax.text(i, r.spikes + top * .115, f"{r.resolution_rate:.0f}% resolved",
                ha="center", fontsize=8.5, color=MUTED)
    ax.set_yticks(t)
    ax.set_xticks(range(len(rs)))
    ax.set_xticklabels([n.replace(" ", "\n") for n in rs.reason_detected],
                       fontsize=9, color=INK_2)
    style(ax)
    return save(fig, "reasons.png")


def p_households(sc, w, h):
    fig, ax = panel_fig(w, h, left=134, right=30, top=10, bottom=52)
    top = sc.nlargest(8, "fault_spikes").sort_values(["fault_spikes", "spikes"]).reset_index(drop=True)
    ax.set_xlim(0, top.spikes.max() + 1.6)
    ax.set_ylim(-0.7, len(top) - 0.3)
    dx, dy = data_per_px(ax)
    gap = 2.5 * dx
    for i, r in top.iterrows():
        beh = r.spikes - r.fault_spikes
        rounded_bar(ax, 0, i - 0.22, r.fault_spikes, 0.44, dx, dy, S1)
        if beh > 0:
            rounded_bar(ax, r.fault_spikes + gap, i - 0.22, beh - gap, 0.44, dx, dy, S2)
        ax.text(r.spikes + 0.22, i, str(int(r.spikes)), va="center",
                fontsize=9.5, color=INK_2)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels([f"{r.customer_id} · {r.region}" for _, r in top.iterrows()],
                       fontsize=9, color=INK_2)
    ax.set_xlabel("Spikes in the window")
    style(ax, xgrid=True, ygrid=False)
    return save(fig, "hh.png")


def p_region(ch, kpi, w, h):
    fig, ax = panel_fig(w, h, left=44, right=12, top=24, bottom=56)
    rg = pd.DataFrame(ch["by_region"]).sort_values("resolution_rate").reset_index(drop=True)
    fleet = kpi["resolution"]["resolution_rate_pct"]
    ax.set_xlim(-0.6, len(rg) - 0.4)
    ax.set_ylim(0, 124)
    dx, dy = data_per_px(ax)
    for i, r in rg.iterrows():
        rounded_bar(ax, i - 0.18, 0, 0.36, r.resolution_rate, dx, dy,
                    CRIT if r.resolution_rate < fleet else S1, round_end="top")
        ax.text(i, r.resolution_rate + 4, f"{r.resolution_rate:.0f}%", ha="center",
                fontsize=11.5, fontweight="600", color=INK)
        # the case count rides under the axis label: above the bar the
        # fleet-average line cuts through it, inside the bar it out-runs the width
    ax.axhline(fleet, color=INK_2, linewidth=1.2)
    ax.text(len(rg) - 0.55, fleet + 3.5, f"fleet average {fleet:.0f}%",
            fontsize=8.5, color=INK_2, ha="right")
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    ax.set_xticks(range(len(rg)))
    ax.set_xticklabels([f"{r.region}\n{int(r.spikes)} cases" for _, r in rg.iterrows()],
                       fontsize=9.5, color=INK_2, linespacing=1.6)
    style(ax)
    return save(fig, "region.png")


def p_funnel(ch, w, h):
    fig, ax = panel_fig(w, h, left=118, right=16, top=26, bottom=26)
    fn = ch["funnel"]
    ax.set_xlim(0, 150)
    ax.set_ylim(-0.62, len(fn) - 0.38)
    dx, dy = data_per_px(ax)
    for i, (st, col) in enumerate(zip(fn, RAMP)):
        y = len(fn) - 1 - i
        rounded_bar(ax, 0, y - 0.15, st["value"], 0.30, dx, dy, col)
        ax.text(st["value"] + 3.5, y + .05, str(st["value"]), va="center",
                fontsize=15, fontweight="600", color=INK)
        if i:
            ax.text(st["value"] + 3.5, y - 0.30,
                    f"{fn[i - 1]['value'] - st['value']} lost here",
                    va="center", fontsize=9, color=CRIT)
    ax.set_yticks(range(len(fn)))
    ax.set_yticklabels([s["stage"] for s in reversed(fn)], fontsize=10, color=INK_2)
    ax.set_xticks([])
    for s in ("top", "right", "bottom", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    return save(fig, "funnel.png")


def p_waste(ch, w, h):
    fig, ax = panel_fig(w, h, left=52, right=14, top=14, bottom=44)
    wd = pd.DataFrame(ch["waste_vs_pct"])
    wd = wd[wd.excess_kwh > 0]
    ax.set_xlim(35, 104)
    ax.set_ylim(0.10, 0.40)
    ax.scatter(wd.excess_pct, wd.excess_kwh, s=24, c=S1, alpha=0.8,
               linewidths=0.7, edgecolors=PANEL)
    hp = wd.nlargest(1, "excess_pct").iloc[0]
    hk = wd.nlargest(1, "excess_kwh").iloc[0]
    ax.annotate("loudest alert: +97%, 8p wasted", (hp.excess_pct, hp.excess_kwh),
                xytext=(93, 0.135), ha="right", fontsize=9, color=INK_2,
                arrowprops=dict(arrowstyle="-", color="#43433f", linewidth=.9))
    ax.annotate("most energy wasted — reported as +44%", (hk.excess_pct, hk.excess_kwh),
                xytext=(50, 0.385), ha="left", fontsize=9, color=INK_2,
                arrowprops=dict(arrowstyle="-", color="#43433f", linewidth=.9))
    ax.set_xlabel("Reported spike size (% above baseline)")
    ax.set_ylabel("Energy wasted (kWh)")
    style(ax)
    return save(fig, "waste.png")


def p_latency(ch, kpi, w, h):
    fig, ax = panel_fig(w, h, left=44, right=12, top=16, bottom=44)
    lh = ch["latency_hist"]
    edges, counts = np.array(lh["edges"]), lh["counts"]
    t = ticks(max(counts))
    top = max(t[-1], max(counts) * 1.12)
    ax.set_xlim(-13, 43)
    ax.set_ylim(0, top)
    dx, dy = data_per_px(ax)
    for e0, e1, n in zip(edges[:-1], edges[1:], counts):
        if n:
            rounded_bar(ax, e0 + .5, 0, (e1 - e0) - 1, n, dx, dy,
                        CRIT if e0 < 0 else S1, round_end="top")
    ax.axvline(lh["median"], color=INK_2, linewidth=1.2)
    ax.text(lh["median"] + 1.4, top * .92, f"median {lh['median']} min",
            fontsize=9, color=INK_2)
    ax.text(-12, top * .55, f"{kpi['alerting']['negative_latency_count']} alerts stamped\n"
            "before their reading", fontsize=8.5, color=CRIT, va="top", linespacing=1.5)
    ax.set_yticks(t)
    ax.set_xticks([-10, 0, 10, 20, 30, 40])
    ax.set_xlabel("Minutes from reading to customer alert")
    style(ax)
    return save(fig, "lat.png")


def p_hourly(ch, w, h):
    fig, ax = panel_fig(w, h, left=48, right=14, top=18, bottom=44)
    hr = pd.DataFrame(ch["by_hour"])
    ax.set_xlim(-0.6, 23.6)
    ax.set_ylim(0, 1.0)
    ax.plot(hr.hour, hr.mean_kwh, color=S1, linewidth=1.8)
    for idx, va, dy in ((hr.mean_kwh.idxmin(), "top", -0.05),
                        (hr.mean_kwh.idxmax(), "bottom", 0.05)):
        ax.scatter(hr.hour[idx], hr.mean_kwh[idx], s=26, color=S1, zorder=3,
                   edgecolors=PANEL, linewidths=1.4)
        ax.text(hr.hour[idx], hr.mean_kwh[idx] + dy, f"{hr.mean_kwh[idx]:.2f}",
                ha="center", va=va, fontsize=9, color=INK_2)
    ax.set_xticks(range(0, 24, 3))
    ax.set_ylabel("Mean kWh per reading")
    ax.set_xlabel("Hour of day")
    style(ax)
    return save(fig, "hour.png")


def p_spike_hour(ch, w, h):
    fig, ax = panel_fig(w, h, left=42, right=12, top=16, bottom=44)
    hr = pd.DataFrame(ch["by_hour"])
    t = ticks(hr.spikes.max())
    top = max(t[-1], hr.spikes.max() * 1.1)
    ax.set_xlim(-0.7, 23.7)
    ax.set_ylim(0, top)
    dx, dy = data_per_px(ax)
    for h_, s in zip(hr.hour, hr.spikes):
        if s:
            rounded_bar(ax, h_ - 0.32, 0, 0.64, s, dx, dy, CRIT, round_end="top")
    ax.set_yticks(t)
    ax.set_xticks(range(0, 24, 3))
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Spikes")
    style(ax)
    return save(fig, "spikehour.png")


# ============================================================================
# markup
# ============================================================================
CSS = """
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ width: {CANVAS_W}px; background: {PLANE}; -webkit-print-color-adjust: exact;
  font-family: system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
  color: {INK}; display: flex; }}

/* ---- sidebar ---- */
.rail {{ width: {RAIL_W}px; flex: none; background: {RAIL};
  border-right: 1px solid {EDGE_2}; padding: 26px 20px; display: flex;
  flex-direction: column; }}
.brand {{ display: flex; align-items: center; gap: 12px; margin-bottom: 34px; }}
.mark {{ width: 40px; height: 40px; border-radius: 11px; flex: none;
  background: linear-gradient(140deg, {S1}, #1c5cab); display: flex;
  align-items: center; justify-content: center; font-size: 16px; font-weight: 700;
  letter-spacing: -.02em; }}
.brand .n {{ font-size: 16.5px; font-weight: 600; letter-spacing: -.01em; }}
.brand .s {{ font-size: 12px; color: {DIM}; margin-top: 2px; }}
.navlbl {{ font-size: 10.5px; letter-spacing: .14em; text-transform: uppercase;
  color: {DIM}; margin: 0 0 12px 8px; }}
.nav a {{ display: flex; align-items: center; gap: 11px; padding: 10px 12px;
  border-radius: 9px; font-size: 13.5px; color: {MUTED}; margin-bottom: 3px; }}
.nav a.on {{ background: #1a1a19; color: {INK}; font-weight: 500; }}
.nav a .ic {{ width: 15px; height: 15px; border-radius: 4px; border: 1.6px solid currentColor;
  flex: none; opacity: .85; }}
.nav a.on .ic {{ background: {S1}; border-color: {S1}; }}
.facts {{ margin-top: 34px; }}
.facts .f {{ display: flex; justify-content: space-between; align-items: baseline;
  font-size: 12.5px; color: {DIM}; padding: 7px 8px; }}
.facts .f b {{ color: {INK_2}; font-weight: 500; }}
.rule-box {{ margin-top: 20px; background: #17171680; border: 1px solid {EDGE_2};
  border-radius: 10px; padding: 13px 14px; }}
.rule-box code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px; color: {S1}; }}
.rail .foot {{ margin-top: auto; border-top: 1px solid {EDGE_2}; padding-top: 18px;
  display: flex; align-items: center; gap: 11px; }}
.av {{ width: 34px; height: 34px; border-radius: 50%; flex: none; background: #232322;
  border: 1px solid {EDGE}; display: flex; align-items: center; justify-content: center;
  font-size: 12.5px; font-weight: 600; color: {INK_2}; }}
.rail .foot .n {{ font-size: 13px; font-weight: 600; }}
.rail .foot .s {{ font-size: 11.5px; color: {DIM}; }}

/* ---- main ---- */
.main {{ flex: 1; min-width: 0; padding: 0 {PAD}px {PAD}px; }}
.topbar {{ display: flex; align-items: center; justify-content: space-between;
  padding: 24px 0 20px; border-bottom: 1px solid {EDGE_2}; }}
.crumb {{ font-size: 11.5px; color: {DIM}; margin-bottom: 6px; letter-spacing: .04em; }}
.topbar h1 {{ font-size: 27px; font-weight: 600; letter-spacing: -.022em; }}
.controls {{ display: flex; align-items: center; gap: 9px; }}
.chip {{ display: flex; align-items: center; gap: 8px; background: {PANEL};
  border: 1px solid {EDGE}; border-radius: 9px; padding: 9px 13px;
  font-size: 12.5px; color: {INK_2}; }}
.chip .k {{ color: {DIM}; }}
.chip .car {{ width: 0; height: 0; border-left: 4px solid transparent;
  border-right: 4px solid transparent; border-top: 5px solid {DIM}; margin-left: 2px; }}
.chip.live {{ color: {MUTED}; }}
.dot {{ width: 7px; height: 7px; border-radius: 50%; background: {GOOD}; flex: none;
  box-shadow: 0 0 0 3px rgba(46,184,92,.16); }}

/* ---- kpi strip ---- */
.kpis {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: {GAP}px;
  margin: {GAP}px 0; }}
.kpi {{ background: {PANEL}; border: 1px solid {EDGE}; border-radius: 13px;
  padding: 16px 17px 14px; }}
.kpi .k {{ font-size: 10.5px; letter-spacing: .1em; text-transform: uppercase;
  color: {DIM}; }}
.kpi .v {{ font-size: 33px; font-weight: 600; letter-spacing: -.03em; margin-top: 11px;
  line-height: 1; }}
.kpi .v small {{ font-size: 16px; color: {MUTED}; font-weight: 500; margin-left: 1px; }}
.kpi .v.bad {{ color: {CRIT}; }}
.kpi .m {{ font-size: 11.5px; color: {MUTED}; margin-top: 11px;
  display: flex; align-items: center; gap: 6px; }}
.pill {{ font-size: 10.5px; padding: 2px 7px; border-radius: 99px; font-weight: 500; }}
.pill.bad {{ background: rgba(224,85,85,.15); color: {CRIT}; }}
.pill.ok {{ background: rgba(46,184,92,.15); color: {GOOD}; }}

/* ---- panels ---- */
.grid {{ display: grid; grid-template-columns: repeat({COLS}, 1fr); gap: {GAP}px; }}
.p {{ background: {PANEL}; border: 1px solid {EDGE}; border-radius: 13px;
  padding: {PANEL_PAD}px; display: flex; flex-direction: column; }}
.p.w2 {{ grid-column: span 2; }}
.ph {{ height: {HEAD_H}px; display: flex; align-items: flex-start;
  justify-content: space-between; gap: 12px; }}
.ph .t {{ font-size: 14.5px; font-weight: 600; letter-spacing: -.008em; }}
.ph .s {{ font-size: 11.5px; color: {MUTED}; margin-top: 4px; }}
.badge {{ flex: none; font-size: 10.5px; padding: 3px 9px; border-radius: 99px;
  border: 1px solid {EDGE}; color: {MUTED}; }}
.badge.bad {{ border-color: rgba(224,85,85,.4); color: {CRIT}; }}
.keys {{ display: flex; gap: 14px; flex: none; padding-top: 3px; }}
.keys span {{ display: inline-flex; align-items: center; gap: 6px;
  font-size: 11.5px; color: {MUTED}; white-space: nowrap; }}
.keys i {{ width: 9px; height: 9px; border-radius: 3px; flex: none; }}
.p img {{ width: 100%; display: block; border-radius: 6px; }}

/* ---- table ---- */
table {{ width: 100%; border-collapse: collapse; font-size: 12px;
  font-variant-numeric: tabular-nums; }}
th {{ text-align: right; padding: 8px 10px; color: {DIM}; font-weight: 500;
  font-size: 10px; letter-spacing: .09em; text-transform: uppercase;
  border-bottom: 1px solid {EDGE}; }}
td {{ text-align: right; padding: 9px 10px; border-bottom: 1px solid {EDGE_2};
  color: {INK_2}; white-space: nowrap; }}
th:first-child, td:first-child {{ text-align: left; }}
td.id {{ color: {MUTED}; font-size: 11.5px; }}
td.v {{ color: {INK}; font-weight: 600; }}
.st {{ display: inline-block; padding: 2px 9px; border-radius: 99px; font-size: 10.5px;
  font-weight: 500; }}
.st.open {{ background: rgba(224,85,85,.15); color: {CRIT}; }}
.st.done {{ background: rgba(46,184,92,.15); color: {GOOD}; }}
"""

PAGE = """<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>
<div class="rail">
  <div class="brand">
    <div class="mark">NG</div>
    <div><div class="n">NovaGrid Ops</div><div class="s">Energy analytics</div></div>
  </div>
  <div class="navlbl">Monitoring</div>
  <div class="nav">
    <a class="on"><span class="ic"></span>Spike overview</a>
    <a><span class="ic"></span>Detection rule</a>
    <a><span class="ic"></span>Alert delivery</a>
    <a><span class="ic"></span>Case resolution</a>
    <a><span class="ic"></span>Households</a>
  </div>
  <div class="navlbl" style="margin-top:26px">Data</div>
  <div class="nav">
    <a><span class="ic"></span>Meter readings</a>
    <a><span class="ic"></span>Quality log</a>
  </div>
  <div class="facts">
    <div class="navlbl">Scope</div>
    <div class="f"><span>Window</span><b>1–7 Jan 2024</b></div>
    <div class="f"><span>Readings</span><b>6,720</b></div>
    <div class="f"><span>Meters</span><b>20</b></div>
    <div class="f"><span>Regions</span><b>5</b></div>
    <div class="f"><span>Interval</span><b>28.8 min</b></div>
    <div class="rule-box">
      <div class="navlbl" style="margin:0 0 9px">Detection rule</div>
      <code>usage &gt; 1.4 × baseline</code>
    </div>
  </div>
  <div class="foot">
    <div class="av">RA</div>
    <div><div class="n">{BYLINE}</div><div class="s">{HANDLE}</div></div>
  </div>
</div>

<div class="main">
  <div class="topbar">
    <div>
      <div class="crumb">Monitoring / Spike overview</div>
      <h1>Abnormal energy spike monitor</h1>
    </div>
    <div class="controls">
      <div class="chip"><span class="k">Region</span> All 5<span class="car"></span></div>
      <div class="chip"><span class="k">Housing</span> All types<span class="car"></span></div>
      <div class="chip"><span class="k">Status</span> All cases<span class="car"></span></div>
      <div class="chip">1–7 Jan 2024<span class="car"></span></div>
      <div class="chip live"><span class="dot"></span>6,720 readings</div>
    </div>
  </div>

  <div class="kpis">{kpis}</div>

  <div class="grid">
    <div class="p w2">{h_blind}<img src="{c_blind}"></div>
    <div class="p">{h_reasons}<img src="{c_reasons}"></div>

    <div class="p">{h_hh}<img src="{c_hh}"></div>
    <div class="p">{h_region}<img src="{c_region}"></div>
    <div class="p">{h_funnel}<img src="{c_funnel}"></div>

    <div class="p">{h_waste}<img src="{c_waste}"></div>
    <div class="p">{h_lat}<img src="{c_lat}"></div>
    <div class="p">{h_hour}<img src="{c_hour}"></div>

    <div class="p">{h_spikehour}<img src="{c_spikehour}"></div>
    <div class="p w2">{h_table}{table}</div>
  </div>
</div>
</body></html>"""


def head(title, sub, badge=None, bad=False, keys=None):
    """Panel header. `keys` renders the series legend as header chips, which is
    where a BI panel puts it — and it keeps the plot area clean."""
    right = ""
    if keys:
        right = '<div class="keys">' + "".join(
            f'<span><i style="background:{c}"></i>{n}</span>' for n, c in keys) + "</div>"
    elif badge:
        right = f'<span class="badge{" bad" if bad else ""}">{badge}</span>'
    return (f'<div class="ph"><div><div class="t">{title}</div>'
            f'<div class="s">{sub}</div></div>{right}</div>')


def kpi_html(kpi):
    d, a, r, w = (kpi["detection"], kpi["alerting"], kpi["resolution"], kpi["waste"])
    cells = [
        ("Spikes detected", f"{d['spikes']}", "", f"{d['spike_rate_pct']}% of readings", None),
        ("Detection blind spot", f"{d['blind_reading_share_pct']}", "%",
         "rule cannot fire", ("bad", "structural")),
        ("Alert coverage", f"{a['alert_coverage_pct']}", "%",
         f"{a['spikes_never_alerted']} never alerted", ("bad", "leak")),
        ("Median latency", f"{a['median_latency_min']}", " min", "reading → alert",
         ("ok", "on target")),
        ("Cases resolved", f"{r['resolution_rate_pct']:.0f}", "%",
         f"{r['unresolved'] + r['unknown']} still open", ("bad", "below target")),
        ("Waste / meter / yr", f"£{w['annual_gbp_per_household']:.0f}", "",
         f"≈ £{w['annual_gbp_fleet'] / 1e6:.1f}m fleet-wide", None),
    ]
    out = []
    for k, v, u, m, pill in cells:
        bad = " bad" if pill and pill[0] == "bad" else ""
        pl = f'<span class="pill {pill[0]}">{pill[1]}</span>' if pill else ""
        out.append(f'<div class="kpi"><div class="k">{k}</div>'
                   f'<div class="v{bad}">{v}<small>{u}</small></div>'
                   f'<div class="m">{pl}{m}</div></div>')
    return "".join(out)


def table_html(ev, unit):
    rows = ev.assign(open=lambda d: d.resolved != True)  # noqa: E712
    rows = rows.sort_values(["open", "is_fault", "excess_kwh"],
                            ascending=[False, False, False]).head(8)
    body = "".join(
        f"<tr><td class='id'>{r.recordid}</td>"
        f"<td style='text-align:left'>{r.customer_id} · {r.customer_name}</td>"
        f"<td style='text-align:left'>{r.region}</td>"
        f"<td style='text-align:left'>{r.reason_detected}</td>"
        f"<td class='v'>{r.excess_kwh:.2f}</td>"
        f"<td>£{r.excess_kwh * unit:.2f}</td>"
        f"<td>+{r.excess_pct:.0f}%</td>"
        f"<td>{r.alert_latency_min:.0f} min</td>"
        f"<td><span class='st {'open' if r.resolved != True else 'done'}'>"  # noqa: E712
        f"{'open' if r.resolved != True else 'resolved'}</span></td></tr>"  # noqa: E712
        for r in rows.itertuples())
    return ("<table><thead><tr><th>Case</th><th>Household</th><th>Region</th><th>Reason</th>"
            "<th>kWh wasted</th><th>Cost</th><th>Reported</th><th>Alert lag</th>"
            f"<th>Status</th></tr></thead><tbody>{body}</tbody></table>")


def free_port():
    import socket
    with closing(socket.socket()) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def trim_bottom(path, plane=(10, 10, 10)):
    im = Image.open(path).convert("RGB")
    px, (w, h) = im.load(), im.size
    last = h - 1
    for y in range(h - 1, -1, -1):
        if not all(all(abs(px[x, y][i] - plane[i]) < 6 for i in range(3))
                   for x in range(0, w, 17)):
            last = y
            break
    im.crop((0, 0, w, min(h, last + int(PAD * 1.5)))).save(path)


def main():
    OUT.mkdir(exist_ok=True)
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)

    kpi = json.loads((DATA / "kpi_summary.json").read_text())
    ch = json.loads((DATA / "chart_data.json").read_text())
    sc = pd.read_csv(DATA / "household_scorecard.csv")
    ev = pd.read_csv(DATA / "spike_events.csv")
    unit = kpi["waste"]["unit_rate_gbp_per_kwh"]

    print("rendering panels:")
    hero_w, hero_h = body_px(WIDE_W, H_HERO)
    std_w, std_h = body_px(COL_W, H_STD)
    tall_w, tall_h = body_px(COL_W, H_TALL)
    panels = {
        "c_blind": p_blindspot(ch, kpi, hero_w, hero_h),
        "c_reasons": p_reasons(ch, std_w, hero_h - (H_STD - H_STD) - (H_HERO - H_HERO)),
        "c_hh": p_households(sc, std_w, std_h),
        "c_region": p_region(ch, kpi, std_w, std_h),
        "c_funnel": p_funnel(ch, std_w, std_h),
        "c_waste": p_waste(ch, std_w, std_h),
        "c_lat": p_latency(ch, kpi, std_w, std_h),
        "c_hour": p_hourly(ch, std_w, std_h),
        "c_spikehour": p_spike_hour(ch, tall_w, tall_h),
    }
    for k in panels:
        print("  ", k[2:])

    heads = {
        "h_blind": head("Where the 1.4× rule can and cannot see",
                        "Every reading by its own baseline · red band is undetectable by design",
                        f"{kpi['detection']['blind_reading_share_pct']}% blind", True),
        "h_reasons": head("Spike causes", "Grouped appliance vs behavioural",
                          keys=[("Appliance", S1), ("Behavioural", S2)]),
        "h_hh": head("Households carrying the caseload", "Top 8 by appliance-fault load",
                     keys=[("Appliance fault", S1), ("Behavioural", S2)]),
        "h_region": head("Case resolution by region", "Same detector, same alert latency",
                         "52–92%", True),
        "h_funnel": head("Detection → alert → resolution", "Where the caseload leaks"),
        "h_waste": head("Reported % vs energy wasted", "The two rankings disagree"),
        "h_lat": head("Alert latency", "Reading to customer notification", "healthy"),
        "h_hour": head("Consumption by hour", "Mean kWh across the 24-hour cycle"),
        "h_spikehour": head("Spikes by hour", "No diurnal concentration"),
        "h_table": head("Priority worklist",
                        "Open cases first, appliance faults next, then by energy wasted",
                        f"{kpi['resolution']['unresolved'] + kpi['resolution']['unknown']} open", True),
    }

    css = CSS.format(CANVAS_W=CANVAS_W, RAIL_W=RAIL_W, PAD=PAD, GAP=GAP, COLS=COLS,
                     PANEL_PAD=PANEL_PAD, HEAD_H=HEAD_H, PLANE=PLANE, PANEL=PANEL,
                     RAIL=RAIL, EDGE=EDGE, EDGE_2=EDGE_2, INK=INK, INK_2=INK_2,
                     MUTED=MUTED, DIM=DIM, S1=S1, CRIT=CRIT, GOOD=GOOD)
    html = PAGE.format(css=css, BYLINE=BYLINE, HANDLE=HANDLE, kpis=kpi_html(kpi),
                       table=table_html(ev, unit), **panels, **heads)
    page = TMP / "console.html"
    page.write_text(html)

    port = free_port()
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(  # noqa: E731
        *a, directory=str(TMP), **k)
    out = OUT / "all_charts_poster.png"
    with socketserver.TCPServer(("127.0.0.1", port), handler) as srv:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        subprocess.run(
            [CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
             "--hide-scrollbars", "--force-device-scale-factor=1.5",
             f"--window-size={CANVAS_W},3400", "--virtual-time-budget=9000",
             f"--screenshot={out}", f"http://127.0.0.1:{port}/console.html"],
            check=True, capture_output=True, timeout=240)
        srv.shutdown()

    trim_bottom(out)
    im = Image.open(out)
    print(f"\nposter  {out.name}  ({out.stat().st_size / 1024 / 1024:.1f} MB, "
          f"{im.width} × {im.height} px)")
    shutil.rmtree(TMP)


if __name__ == "__main__":
    main()
