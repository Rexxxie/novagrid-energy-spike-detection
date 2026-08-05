"""
NovaGrid — LinkedIn carousel
============================
Builds a 10-slide, 1080x1080 document carousel from the pipeline outputs:

    06_linkedin/novagrid_carousel.pdf     upload as a LinkedIn document post
    06_linkedin/slides/slide_01..10.png   the same slides as square images

Charts are re-rendered "bare" — no baked-in headline — on the dark slide surface,
so the slide's own typography carries the message and the chart carries the data.

Run the pipeline first, then:  python3 01_pipeline/build_linkedin_carousel.py
Requires Google Chrome (used headlessly to rasterise and to print the PDF).
"""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from build_charts import rounded_bar, data_per_px   # exact-length bar geometry

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "02_data_outputs"
OUT = ROOT / "06_linkedin"
TMP = OUT / ".build"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

BYLINE = "Rexley Adio"          # change this line to re-brand the deck
HANDLE = "Data Analyst"

# --- dark slide palette (the validated dark steps, on the dark surface) ------
PLANE = "#0d0d0d"
SURFACE = "#141413"
INK = "#ffffff"
INK_2 = "#c3c2b7"
MUTED = "#898781"
GRID = "#2c2c2a"
AXIS = "#383835"
S1 = "#3987e5"     # blue   — appliance / primary
S2 = "#d95926"     # orange — behavioural / secondary
CRIT = "#e05555"   # status — anomaly, below target (lifted for the dark plane)
RAMP = ["#86b6ef", "#3987e5", "#1c5cab"]

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK_2, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "xtick.labelsize": 15, "ytick.labelsize": 15, "axes.labelsize": 16,
    "axes.linewidth": 1.0, "grid.color": GRID, "grid.linewidth": 1.0,
    "legend.frameon": False, "legend.fontsize": 15, "figure.dpi": 150,
})


def style(ax, xgrid=False, ygrid=True):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(AXIS)
    ax.set_axisbelow(True)
    if ygrid:
        ax.yaxis.grid(True, linestyle="-", linewidth=1.0, color=GRID)
    if xgrid:
        ax.xaxis.grid(True, linestyle="-", linewidth=1.0, color=GRID)
    ax.tick_params(length=0)


def save(fig, name):
    p = TMP / name
    fig.savefig(p, bbox_inches="tight", pad_inches=0.28, facecolor=SURFACE)
    plt.close(fig)
    return p


def b64(p: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


# ===========================================================================
# bare charts
# ===========================================================================
def chart_blindspot(ch, kpi):
    fig, ax = plt.subplots(figsize=(11, 6.1))
    normal = np.array(ch["scatter"]["normal"])
    spike = np.array(ch["scatter"]["spike"])
    ceiling = ch["scatter"]["ceiling"]
    cut = ceiling / 1.4

    ax.set_xlim(0.26, 1.29)
    ax.set_ylim(0.08, 1.60)
    ax.axvspan(cut, 1.29, color=CRIT, alpha=0.10, linewidth=0)
    ax.scatter(normal[:, 0], normal[:, 1], s=13, c=MUTED, alpha=0.30, linewidths=0,
               label="Normal reading")
    ax.scatter(spike[:, 0], spike[:, 1], s=40, c=CRIT, alpha=0.95, linewidths=1.0,
               edgecolors=SURFACE, label="Flagged spike")
    xs = np.linspace(0.28, 1.14, 80)
    ax.plot(xs, 1.4 * xs, color=INK_2, linewidth=2.2, label="The 1.4× rule")
    ax.axhline(ceiling, color=AXIS, linewidth=1.6)
    ax.text(0.28, ceiling + 0.03, f"highest reading in the fleet — {ceiling} kWh",
            fontsize=14, color=MUTED)
    ax.text(cut + 0.025, 0.15,
            "the rule can never\nfire in here",
            fontsize=16, color=CRIT, va="bottom", linespacing=1.5, fontweight="600")
    ax.set_xlabel("Household baseline for this half hour (kWh)")
    ax.set_ylabel("Actual reading (kWh)")
    style(ax, xgrid=True)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.15), ncol=3)
    return save(fig, "c_blind.png")


def chart_waste(ch):
    fig, ax = plt.subplots(figsize=(11, 5.8))
    w = pd.DataFrame(ch["waste_vs_pct"])
    w = w[w.excess_kwh > 0]
    ax.set_xlim(35, 104)
    ax.set_ylim(0.10, 0.40)
    ax.scatter(w.excess_pct, w.excess_kwh, s=64, c=S1, alpha=0.8, linewidths=1.2,
               edgecolors=SURFACE)
    hp = w.nlargest(1, "excess_pct").iloc[0]
    hk = w.nlargest(1, "excess_kwh").iloc[0]
    ax.annotate("the loudest alert of the week\n+97% — and 8p of electricity",
                (hp.excess_pct, hp.excess_kwh), xytext=(95, 0.147), ha="right",
                fontsize=15, color=INK_2, linespacing=1.5,
                arrowprops=dict(arrowstyle="-", color=AXIS, linewidth=1.3))
    ax.annotate("the most energy actually wasted\nreported as only +44%",
                (hk.excess_pct, hk.excess_kwh), xytext=(56, 0.377), ha="left",
                fontsize=15, color=INK_2, linespacing=1.5,
                arrowprops=dict(arrowstyle="-", color=AXIS, linewidth=1.3))
    ax.set_xlabel("Spike size as reported (% above baseline)")
    ax.set_ylabel("Energy actually wasted (kWh)")
    style(ax)
    return save(fig, "c_waste.png")


def chart_funnel(ch):
    fig, ax = plt.subplots(figsize=(11, 4.3))
    fn = ch["funnel"]
    ax.set_xlim(0, 168)
    ax.set_ylim(-0.6, len(fn) - 0.4)
    dx, dy = data_per_px(ax)
    for i, (st, col) in enumerate(zip(fn, RAMP)):
        y = len(fn) - 1 - i
        rounded_bar(ax, 0, y - 0.17, st["value"], 0.34, dx, dy, col)
        ax.text(st["value"] + 4, y, str(st["value"]), va="center", fontsize=25,
                fontweight="600", color=INK)
        if i:
            ax.text(st["value"] + 26, y,
                    f"{fn[i - 1]['value'] - st['value']} lost here",
                    va="center", fontsize=16, color=CRIT)
    ax.set_yticks(range(len(fn)))
    ax.set_yticklabels([s["stage"] for s in reversed(fn)], fontsize=17, color=INK)
    ax.set_xticks([])
    for s in ("top", "right", "bottom", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    return save(fig, "c_funnel.png")


def chart_regions(ch, kpi):
    fig, ax = plt.subplots(figsize=(11, 5.4))
    rg = pd.DataFrame(ch["by_region"]).sort_values("resolution_rate").reset_index(drop=True)
    fleet = kpi["resolution"]["resolution_rate_pct"]
    ax.set_xlim(-0.6, len(rg) - 0.4)
    ax.set_ylim(0, 120)
    dx, dy = data_per_px(ax)
    for i, r in rg.iterrows():
        below = r.resolution_rate < fleet
        rounded_bar(ax, i - 0.19, 0, 0.38, r.resolution_rate, dx, dy,
                    CRIT if below else S1, round_end="top")
        ax.text(i, r.resolution_rate + 4, f"{r.resolution_rate:.0f}%", ha="center",
                fontsize=21, fontweight="600", color=INK)
        ax.text(i, r.resolution_rate + 12, f"{int(r.spikes)} cases", ha="center",
                fontsize=14, color=MUTED)
    ax.axhline(fleet, color=INK_2, linewidth=1.6)
    ax.text(-0.55, fleet + 3, f"fleet average {fleet}%", fontsize=14, color=INK_2)
    ax.set_xticks(range(len(rg)))
    ax.set_xticklabels(rg.region, fontsize=17, color=INK)
    ax.set_ylabel("Cases resolved (%)")
    style(ax)
    return save(fig, "c_region.png")


def chart_households(sc):
    fig, ax = plt.subplots(figsize=(11, 5.6))
    top = sc.nlargest(8, "fault_spikes").sort_values(["fault_spikes", "spikes"]).reset_index(drop=True)
    ax.set_xlim(0, top.spikes.max() + 2)
    ax.set_ylim(-0.7, len(top) - 0.3)
    dx, dy = data_per_px(ax)
    gap = 3 * dx
    for i, r in top.iterrows():
        beh = r.spikes - r.fault_spikes
        rounded_bar(ax, 0, i - 0.23, r.fault_spikes, 0.46, dx, dy, S1)
        if beh > 0:
            rounded_bar(ax, r.fault_spikes + gap, i - 0.23, beh - gap, 0.46, dx, dy, S2)
        ax.text(r.spikes + 0.3, i, str(int(r.spikes)), va="center", fontsize=16, color=INK_2)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels([f"{r.customer_id}  ·  {r.region}" for _, r in top.iterrows()],
                       fontsize=15, color=INK)
    ax.set_xlabel("Spikes in one week")
    style(ax, xgrid=True, ygrid=False)
    handles = [plt.Line2D([], [], marker="s", linestyle="", markersize=13, color=S1,
                          label="Appliance fault — recurs until fixed"),
               plt.Line2D([], [], marker="s", linestyle="", markersize=13, color=S2,
                          label="Behavioural — customer's own choice")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, -0.16), ncol=1)
    return save(fig, "c_hh.png")


# ===========================================================================
# slide markup
# ===========================================================================
CSS = f"""
@page {{ size: 11.25in 11.25in; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ background: {PLANE}; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.slide {{
  width: 1080px; height: 1080px; position: relative; overflow: hidden;
  background: {PLANE}; color: {INK};
  font-family: system-ui, -apple-system, "Helvetica Neue", Arial, sans-serif;
  padding: 74px 76px 118px; display: flex; flex-direction: column;
  page-break-after: always; break-after: page;
}}
.slide:last-child {{ page-break-after: auto; break-after: auto; }}
.eyebrow {{
  font-size: 19px; letter-spacing: .16em; text-transform: uppercase;
  color: {MUTED}; font-weight: 500; margin-bottom: 26px;
}}
.eyebrow b {{ color: {S1}; font-weight: 600; }}
h1 {{ font-size: 76px; line-height: 1.06; letter-spacing: -.028em; font-weight: 600; }}
h2 {{ font-size: 54px; line-height: 1.12; letter-spacing: -.022em; font-weight: 600; }}
h2 .hl {{ color: {CRIT}; }}
h2 .hl-b {{ color: {S1}; }}
.lede {{ font-size: 27px; line-height: 1.5; color: {INK_2}; margin-top: 26px; max-width: 27ch; }}
.note {{ font-size: 22px; line-height: 1.55; color: {INK_2}; margin-top: 24px; max-width: 46ch; }}
.note b {{ color: {INK}; font-weight: 600; }}
/* everything under the eyebrow is centred in the remaining space, so a
   text-only slide balances and a chart slide never runs into the footer */
.body {{ flex: 1; min-height: 0; display: flex; flex-direction: column; justify-content: center; }}
.chart {{ margin-top: 36px; min-height: 0; flex: 0 1 auto;
         display: flex; align-items: center; justify-content: center; }}
.chart img {{ max-width: 100%; max-height: 100%; width: auto; height: auto;
             display: block; border-radius: 12px; }}
.rule {{ width: 76px; height: 5px; background: {S1}; border-radius: 3px; margin: 34px 0 6px; }}
.foot {{
  position: absolute; left: 76px; right: 76px; bottom: 46px;
  display: flex; justify-content: space-between; align-items: center;
  font-size: 19px; color: {MUTED}; border-top: 1px solid {GRID}; padding-top: 18px;
}}
.foot b {{ color: {INK_2}; font-weight: 500; }}
.stats {{ display: flex; gap: 22px; margin-top: 46px; flex-wrap: wrap; }}
.stat {{
  background: {SURFACE}; border: 1px solid {GRID}; border-radius: 16px;
  padding: 26px 28px; flex: 1 1 0; min-width: 0;
}}
.stat .v {{ font-size: 52px; font-weight: 600; letter-spacing: -.03em; line-height: 1; }}
.stat .v small {{ font-size: 26px; color: {INK_2}; font-weight: 500; }}
.stat .k {{ font-size: 18px; color: {MUTED}; margin-top: 14px; line-height: 1.4; }}
.big {{ font-size: 152px; font-weight: 600; letter-spacing: -.045em; line-height: .95; color: {CRIT}; }}
.big.blue {{ color: {S1}; }}
ol.pts {{ list-style: none; margin-top: 48px; }}
ol.pts li {{ display: flex; gap: 26px; margin-bottom: 38px; align-items: flex-start; }}
ol.pts .n {{
  flex: none; width: 52px; height: 52px; border-radius: 14px; background: {SURFACE};
  border: 1px solid {GRID}; color: {S1}; font-size: 25px; font-weight: 600;
  display: flex; align-items: center; justify-content: center;
}}
ol.pts .t {{ font-size: 30px; line-height: 1.4; }}
ol.pts .t span {{ display: block; font-size: 22px; color: {INK_2}; margin-top: 8px; line-height: 1.5; }}
.code {{
  background: {SURFACE}; border: 1px solid {GRID}; border-radius: 16px;
  padding: 34px 36px; margin-top: 40px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 27px; line-height: 1.75;
}}
.code .dim {{ color: {MUTED}; }}
.code .add {{ color: {S1}; font-weight: 600; }}
.cover-mark {{
  position: absolute; right: -180px; top: -180px; width: 720px; height: 720px;
  border-radius: 50%; background: radial-gradient(circle, {S1}26 0%, transparent 68%);
}}
"""


def slide(n, total, body, eyebrow=None, foot_right=None):
    eb = f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else ""
    fr = foot_right if foot_right else f"{n} / {total}"
    return f"""<section class="slide">{eb}<div class="body">{body}</div>
  <div class="foot"><span><b>{BYLINE}</b> · {HANDLE}</span><span>{fr}</span></div>
</section>"""


def build_slides(kpi, ch, sc, imgs):
    d, a, r, w, c = (kpi["detection"], kpi["alerting"], kpi["resolution"],
                     kpi["waste"], kpi["concentration"])
    T = 10
    S = []

    # 1 — cover
    S.append(slide(1, T, f"""
  <div class="cover-mark"></div>
  <h1>The spike detector<br>worked exactly<br>as documented.<br><span style="color:{CRIT}">That was the problem.</span></h1>
  <div class="rule"></div>
  <div class="lede">What 6,720 smart-meter readings said about a rule nobody had audited.</div>
  <div class="stats">
    <div class="stat"><div class="v">6,720</div><div class="k">readings analysed</div></div>
    <div class="stat"><div class="v">20</div><div class="k">households, 5 regions</div></div>
    <div class="stat"><div class="v">7<small> days</small></div><div class="k">January 2024</div></div>
  </div>""", eyebrow="Case study · Energy analytics", foot_right="Swipe →"))

    # 2 — the setup
    S.append(slide(2, T, f"""
  <h2>The utility flags a spike when a home uses <span class="hl-b">more than 1.4× its own baseline</span>.</h2>
  <div class="note">Simple, explainable, and it runs on every half-hourly reading in the fleet.
  In one week it raised <b>{d['spikes']} spikes</b>, alerted on <b>{a['alerts_sent']}</b> of them
  in a median of <b>{a['median_latency_min']} minutes</b>, and closed <b>{r['resolved']}</b> cases.
  <br><br>So I rebuilt the rule from the raw readings to check it. Three things fell out.</div>
  <div class="stats">
    <div class="stat"><div class="v">{a['alert_coverage_pct']}<small>%</small></div><div class="k">of spikes alerted</div></div>
    <div class="stat"><div class="v">{a['median_latency_min']}<small> min</small></div><div class="k">median alert latency</div></div>
    <div class="stat"><div class="v">0</div><div class="k">false alarms</div></div>
  </div>""", eyebrow="The system"))

    # 3 — finding 1 headline
    S.append(slide(3, T, f"""
  <h2>Every spike it has <span class="hl">ever</span> raised came from a low-consumption home.</h2>
  <div class="note">Readings top out at <b>{d['meter_ceiling_kwh']} kWh</b>. So wherever a household's
  baseline is above <b>1.03 kWh</b>, <b>1.4 × baseline</b> is higher than anything a meter can
  physically report — and the rule cannot fire at all.</div>
  <div class="chart"><img src="{imgs['blind']}"></div>""",
        eyebrow="Finding <b>01</b> · Detection"))

    # 4 — the blind-spot number
    S.append(slide(4, T, f"""
  <div class="big">{d['blind_reading_share_pct']}%</div>
  <h2 style="margin-top:34px">of all readings sit in a band where the rule is <span class="hl">arithmetically unable</span> to fire.</h2>
  <div class="note">The highest baseline that has ever produced a spike is
  <b>{d['highest_spiking_baseline_kwh']} kWh</b>. The fleet median is
  <b>{d['median_baseline_all_kwh']} kWh</b>.
  <br><br>The detector isn't sampling the fleet. It's sampling the bottom half of it — and a faulty
  heater in a large house is invisible to it.</div>""",
        eyebrow="Finding <b>01</b> · Detection"))

    # 5 — finding 2
    S.append(slide(5, T, f"""
  <h2>A “+97% spike” turned out to be <span class="hl">eight pence</span> of electricity.</h2>
  <div class="note">Every flagged spike wasted between <b>0.13 and 0.34 kWh</b>. The headline
  percentage mostly records how small the baseline was — not how much energy went anywhere.
  Meanwhile <b>122 readings that were never flagged</b> wasted more than the median spike did.</div>
  <div class="chart"><img src="{imgs['waste']}"></div>""",
        eyebrow="Finding <b>02</b> · Prioritisation"))

    # 6 — finding 3
    S.append(slide(6, T, f"""
  <h2>Detection loses 3%.<br>The <span class="hl">operation</span> loses 30%.</h2>
  <div class="note">{d['spikes']} spikes detected, {a['alerts_sent']} alerted,
  <b>{r['resolved']} resolved</b>. Everything that goes missing, goes missing after the alert
  lands — which makes it a process problem, not an analytics one.</div>
  <div class="chart"><img src="{imgs['funnel']}"></div>""",
        eyebrow="Finding <b>03</b> · Follow-through"))

    # 7 — regional
    S.append(slide(7, T, f"""
  <h2>Same detector. Same alert. <span class="hl-b">Same 14-minute latency.</span></h2>
  <div class="note">Manchester closes half its cases; Glasgow closes nine in ten — and Manchester
  has the <b>fastest</b> alerts of any region, on a smaller caseload than Leeds. Nothing in the
  analytics explains the gap.</div>
  <div class="chart"><img src="{imgs['region']}"></div>""",
        eyebrow="Finding <b>03</b> · Follow-through"))

    # 8 — recurrence
    S.append(slide(8, T, f"""
  <h2>One broken appliance.<br><span class="hl">Seven separate alerts.</span></h2>
  <div class="note">The worst household logged 11 spikes — <b>7 of them the same reason code</b>,
  on seven different nights. That isn't seven incidents, and seven notifications isn't proactive
  service. Alert on the event; escalate on the <b>pattern</b>.</div>
  <div class="chart"><img src="{imgs['hh']}"></div>""",
        eyebrow="Finding <b>02</b> · Prioritisation"))

    # 9 — the fix
    S.append(slide(9, T, f"""
  <h2>The fix is <span class="hl-b">one line</span>.</h2>
  <div class="code">
    <span class="dim"># today</span><br>
    usage &gt; 1.4 * baseline<br><br>
    <span class="dim"># add</span><br>
    <span class="add">or (usage - baseline) &gt; 0.30</span>
  </div>
  <div class="note">Ratio catches proportionally large events on small baselines. Absolute excess
  catches materially large events on <b>any</b> baseline. Run both.
  <br><br>In this week alone it surfaces <b>five events the rule ignored</b> — each wasting more
  energy than 97% of the spikes it did flag.</div>""",
        eyebrow="The recommendation"))

    # 10 — close
    S.append(slide(10, T, f"""
  <h2>What I actually took<br>from this one.</h2>
  <ol class="pts">
    <li><span class="n">1</span><span class="t">Audit the rule, not just the output.
      <span>113 of 114 flags reproduced exactly — and the one that didn't was flagged while sitting 17% <i>below</i> baseline.</span></span></li>
    <li><span class="n">2</span><span class="t">A threshold can be well chosen and still be the wrong shape.
      <span>1.4 sits right at the tail of normal variation. The multiplier was fine. The multiplication wasn't.</span></span></li>
    <li><span class="n">3</span><span class="t">Report the finding that isn't there.
      <span>No peak-hour concentration, no housing-type effect. Saying so is worth more than a chart that implies otherwise.</span></span></li>
  </ol>
  <div class="note" style="margin-top:34px">Built with Python, pandas and a self-contained HTML
  dashboard — no Tableau licence needed. Happy to share the write-up.</div>""",
        eyebrow="Takeaways", foot_right="Thanks for reading"))

    return S


# ===========================================================================
def chrome(*args):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-sandbox",
                    "--hide-scrollbars", *args],
                   check=True, capture_output=True, timeout=180)


def main():
    OUT.mkdir(exist_ok=True)
    TMP.mkdir(exist_ok=True)
    (OUT / "slides").mkdir(exist_ok=True)

    kpi = json.loads((DATA / "kpi_summary.json").read_text())
    ch = json.loads((DATA / "chart_data.json").read_text())
    sc = pd.read_csv(DATA / "household_scorecard.csv")

    print("rendering charts for the carousel:")
    imgs = {
        "blind": b64(chart_blindspot(ch, kpi)),
        "waste": b64(chart_waste(ch)),
        "funnel": b64(chart_funnel(ch)),
        "region": b64(chart_regions(ch, kpi)),
        "hh": b64(chart_households(sc)),
    }
    for k in imgs:
        print("  ", k)

    slides = build_slides(kpi, ch, sc, imgs)
    head = f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"

    # one document for the PDF
    doc = TMP / "carousel.html"
    doc.write_text(head + "\n".join(slides) + "</body></html>")
    pdf = OUT / "novagrid_carousel.pdf"
    chrome("--print-to-pdf=" + str(pdf), "--no-pdf-header-footer", doc.as_uri())
    print(f"\npdf   {pdf.name}  ({pdf.stat().st_size / 1024:.0f} KB, {len(slides)} pages)")

    # one file per slide for the PNGs
    for i, s in enumerate(slides, 1):
        one = TMP / f"s{i:02d}.html"
        one.write_text(head + s + "</body></html>")
        png = OUT / "slides" / f"slide_{i:02d}.png"
        chrome("--screenshot=" + str(png), "--window-size=1080,1080", one.as_uri())
    print(f"png   slides/slide_01..{len(slides):02d}.png  (1080 × 1080)")

    for f in TMP.iterdir():
        f.unlink()
    TMP.rmdir()


if __name__ == "__main__":
    main()
