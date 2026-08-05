# Presentation script — NovaGrid spike detection

**Audience:** NovaGrid operations and customer-support leads, plus the analytics owner.
**Running time:** 12 minutes, 11 slides. **Ask at the end:** approve one rule change and one
process review.

Each slide below gives the headline to put on the slide, the image to place, and what to say.
Speaker notes are written to be read aloud at pace — roughly 45–70 seconds per slide.

---

## Slide 1 — Title

> ### The detector is working. It is watching the wrong half of the fleet.
> Abnormal energy spike detection · 6,720 smart-meter readings · 1–7 January 2024

**Say:** "Seven days, twenty households, five regions, every reading re-analysed from the raw
extract rather than taken from the flags. Three things came out of it. One is good news, two need
a decision from this room."

---

## Slide 2 — What we found, in one slide

> ### Three findings
> 1. Alerting works — 97% coverage, 14-minute median latency
> 2. The detection rule is blind to 19% of all readings
> 3. A third of detected cases are never closed

**Say:** "I want to be clear that the analytics layer is not the problem. Alerts go out within a
quarter of an hour of the meter reading, on 97% of spikes, with zero false alarms. The problems are
on either side of it — the rule feeding it, and the process consuming it."

---

## Slide 3 — The blind band

**Image:** `04_charts/01_detection_blind_spot.png`

> ### The 1.4× rule only watches low-consumption households

**Say:** "Every dot is one meter reading, positioned by that household's own baseline. Red dots are
the spikes we caught. Look where they are — all of them below 0.77 kWh of baseline, when the fleet
median is 0.74. The diagonal is our rule. The horizontal line is the highest reading any meter has
ever produced, 1.44 kWh. Where the diagonal crosses above that line, the rule is arithmetically
incapable of firing — no reading, at any consumption level, can trip it. That's the shaded band,
and it is 19% of everything we measure. A faulty heater in a large detached house is invisible to
us today."

---

## Slide 4 — What that costs us

**Image:** `04_charts/02_pct_vs_waste.png`

> ### The percentage we report is not the size of the problem

**Say:** "Every spike we flagged this week wasted between 0.13 and 0.34 kilowatt-hours — four to
ten pence of electricity. Our loudest alert of the week, a plus-97% spike, wasted 29 pence-worth,
0.29 kWh, because the baseline underneath it was tiny. Meanwhile 122 readings we never flagged
wasted more than our median spike did. Five of them wasted more than 97% of everything we did
flag. And the single biggest waste event of the week ranks 85th out of 114 by the percentage we
report. We are ranking our field work by the wrong number."

---

## Slide 5 — The fix

> ### One line of logic closes the gap
> Today: `usage > 1.4 × baseline`
> Add: `OR usage − baseline > 0.30 kWh`
>
> In this week alone that surfaces **5 events we ignored**, each wasting more energy than 97% of
> the spikes we did catch.

**Say:** "I'm not proposing we move the threshold. As a ratio, 1.4 is well placed — normal
variation reaches 1.39 at the 99.9th percentile, so lowering it would double our caseload with
noise. The problem is the *form* of the rule, not its number. Ratio catches proportionally large
events on small baselines. Absolute excess catches materially large events on any baseline. We
should run both."

---

## Slide 6 — What the spikes actually are

**Image:** `04_charts/05_reason_mix.png`

> ### 63 appliance faults, 50 behavioural, and no infrastructure code at all

**Say:** "Roughly half of what we detect is equipment and half is people. That distinction should
drive completely different responses — a guest visit needs an FYI at most, a malfunctioning heater
needs an engineer. Worth noting: not a single spike this week is classified as infrastructure. I
don't believe our grid is flawless; I believe we have no reason code for it, so infrastructure
faults are being filed as heater malfunctions."

---

## Slide 7 — Recurrence is the signal we're not using

**Image:** `04_charts/04_household_priority.png`

> ### One appliance, seven alerts

**Say:** "The five worst households carry 39% of the entire caseload. CUST006 in Leeds generated
eleven spikes — seven of them the same reason code, 'overnight appliance', on seven different
nights. That is not seven incidents. That is one broken appliance and seven alerts to a customer
who already knows something is wrong. CUST008 in London: five heater malfunctions. When the same
reason repeats three times in a week for one household, we should stop alerting and raise a job."

---

## Slide 8 — Alerting, the part that works

**Image:** `04_charts/08_alert_latency.png`

> ### Alerts land in 14 minutes — against a complaint cycle measured in weeks

**Say:** "Credit where it's due: every alert this week went out within 36 minutes of the reading,
median 14. That is genuinely near-real-time and it is the foundation everything else is built on.
Two defects to fix, both small: three spikes never alerted at all, and six alerts carry a timestamp
*earlier* than the reading that caused them — a clock problem in the alerting service that makes
our latency reporting unreliable until it's corrected."

---

## Slide 9 — Where the value leaks

**Image:** `04_charts/03_alert_funnel.png`

> ### The detector loses 3%. The operation loses 30%.

**Say:** "114 detected, 111 alerted, 77 resolved. Thirty-seven cases still open at the end of the
week. This is the single largest recoverable loss in the whole pipeline, and it needs no new
analytics whatsoever."

---

## Slide 10 — And it is regional

**Image:** `04_charts/07_region_resolution.png`

> ### Manchester closes half its cases. Glasgow closes nine in ten.

**Say:** "Same detector, same alert, same latency — Manchester actually has the *fastest* alerts of
any region and the worst closure rate, on a smaller caseload than Leeds. So this isn't workload and
it isn't analytics. It's what happens after the alert lands, and it's a process question for the
support organisation. Glasgow proves 92% is achievable."

---

## Slide 11 — What I'm asking for

> ### Two decisions and four fixes
> **Decide today**
> 1. Approve the absolute-excess trigger — analytics, this week
> 2. Commission a review of Manchester case handling — operations
>
> **Fix in the backlog**
> 3. Escalate on recurrence (3 same-reason events in 7 days → engineer visit)
> 4. Rank the worklist by kWh wasted, not by percentage
> 5. Repair the alert clock skew and the 3 missed notifications
> 6. Add an infrastructure reason code and a "no action required" disposition

**Say:** "Two decisions from this room, four items for the backlog. The dashboard is live and
filterable by region, housing type and case status, so you can each check your own patch. Happy to
take questions."

---

## Appendix slides (hold in reserve)

| If asked | Show |
|---|---|
| "Does waste concentrate at peak times?" | `04_charts/06_hourly_profile.png` — no. 12% spread across 24 hours, spikes evenly distributed. The claim isn't supported by this data. |
| "What's this worth in money?" | 23.15 kWh wasted across 20 households in a week = £6.63. Annualised per meter: £17.23. At a million meters, roughly £17m a year — an order of magnitude for prioritising, not a forecast. |
| "Can we trust the flags?" | 113 of 114 reproduce exactly from the documented rule. One record, `REC000015`, is flagged despite being 17% *below* baseline. Details in `data_quality_log.md`. |
| "How solid is the sample?" | Seven days, 20 households, one January week. Enough to audit a rule and size an operational gap. Not enough for seasonality or forecasting — which is why there's no trend claim anywhere in this deck. |

---

## Build notes

- All images are in `04_charts/`, rendered at 160 dpi on a light surface; they drop straight into
  16:9 slides at full width with the chart's own headline hidden if the slide carries it.
- The interactive version is `03_dashboard/novagrid_dashboard.html` — a single self-contained file,
  no server or Tableau licence needed. Open it directly, or screen-share it during Q&A to answer
  region-specific questions live.
- Every number in this script traces to `02_data_outputs/kpi_summary.json`.
