# Detecting Abnormal Energy Spikes — NovaGrid Energy

**Analysis of 6,720 smart-meter readings, 1–7 January 2024**
Prepared against the NovaGrid case-study brief · all figures recomputed from the raw extract

---

## Executive summary

NovaGrid's spike detector works exactly as documented, and that is the problem.

Over one week the `1.4 × baseline` rule flagged 114 readings, alerted on 111 of them within a
median of 14 minutes, and closed 77 cases. Detection and alerting are not the weak link. Two
things are:

1. **The rule is structurally blind to 19% of all readings.** Every spike it has ever raised sits
   on a baseline of 0.77 kWh or below, while the fleet median baseline is 0.74 kWh. On any
   reading where `1.4 × baseline` exceeds the largest value a NovaGrid meter has ever reported
   (1.44 kWh), the rule cannot fire at any level of consumption. The households that consume the
   most are the ones the detector watches least.
2. **A third of detected cases are never closed.** 37 of 114 spikes are still open, and the
   spread between regions — Manchester 52%, Glasgow 92% — has nothing to do with detection,
   alerting, or latency, all of which are identical everywhere.

There is a third, quieter finding that changes how the alerts should be used at all: **the
percentage NovaGrid reports is not a measure of how much energy was wasted.** Every flagged
spike in the week wasted between 0.13 and 0.34 kWh — 4p to 10p of electricity. A "+97% spike"
turns out to be 0.29 kWh on a household with a very small baseline. Meanwhile 122 unflagged
readings wasted *more* energy than the median flagged spike did.

**The headline recommendation is one line of logic:** add an absolute-excess trigger
(`energy_usage_kWh − baseline_kWh > 0.30`) alongside the existing ratio rule. In this week alone
that would have surfaced five events the current rule ignored, each of which wasted more energy
than 97% of the spikes it did flag.

| | |
|---|---|
| Readings analysed | 6,720 (from 6,764 raw; 43 duplicates and 1 blank row removed) |
| Households / meters / regions | 20 / 20 / 5 |
| Reading interval | 28.8 minutes — **not** the 30 minutes the brief specifies |
| Spikes detected | 114 (1.70% of readings; all 20 households affected) |
| Readings the rule cannot fire on | 19.0% |
| Alerts sent | 111 of 114 (97.4%), median latency 14.4 min, max 36 min |
| Cases resolved | 77 of 114 (67.5%) |
| Energy wasted by flagged spikes | 23.15 kWh over the week — £6.63 at 28.62 p/kWh |

---

## 1. Objective 1 — detect abnormal spikes

### 1.1 The supplied flag is trustworthy; the rule behind it is not

The `spike_detected` column was re-derived from scratch rather than trusted. Applying
`energy_usage_kWh > 1.4 × baseline_kWh` to the 6,720 clean readings reproduces 113 of the 114
flags exactly, with **no false negatives**.

One record fails: `REC000015` (CUST001, 1 January, 06:57) is flagged `TRUE` on a reading of
0.30 kWh against a baseline of 0.36 kWh. That is 17% *below* baseline. It carries no reason code,
no alert, and no resolution — an orphan record that will inflate every spike count downstream
until it is corrected. The engineering point is small; the process point is not. A flag column
that disagrees with its own documented definition means nothing downstream can be taken on trust.

### 1.2 The blind band — the most important finding in this analysis

A multiplicative threshold assumes consumption can always rise by 40%. Meter readings cannot:
the highest value anywhere in this extract is 1.44 kWh per half-hour. So for any reading whose
baseline exceeds **1.44 ÷ 1.4 = 1.03 kWh**, the rule is arithmetically incapable of firing.

- **19.0%** of all readings sit in that band.
- The highest baseline that has *ever* produced a spike is **0.77 kWh**. **46.2%** of readings sit
  above it.
- Median baseline across all readings: **0.74 kWh**. Median baseline of flagged spikes: **0.38 kWh**.

The detector is not sampling the fleet. It is sampling the bottom half of it. A faulty immersion
heater in a large detached house — precisely the "aging or faulty appliances running unnoticed"
the brief names as the core problem — is invisible to it.

*See `04_charts/01_detection_blind_spot.png`, and the first panel of the dashboard.*

### 1.3 What the rule misses in practice

Ranking every reading by energy actually wasted rather than by percentage:

| Record | Household | Region | Reading | Baseline | Wasted | Flagged? |
|---|---|---|---|---|---|---|
| REC006437 | CUST020 | Glasgow | 1.43 kWh | 1.12 kWh | 0.31 kWh | **No** |
| REC006323 | CUST019 | London | 1.41 kWh | 1.10 kWh | 0.31 kWh | **No** |
| REC004388 | CUST014 | Leeds | 1.11 kWh | 0.81 kWh | 0.30 kWh | **No** |
| REC002787 | CUST009 | Manchester | 1.16 kWh | 0.86 kWh | 0.30 kWh | **No** |
| REC000569 | CUST002 | Bristol | 1.19 kWh | 0.89 kWh | 0.30 kWh | **No** |
| REC005793 | CUST018 | Manchester | 0.59 kWh | 0.30 kWh | 0.29 kWh | Yes — "+97%" |

The top five rows waste more energy than the event NovaGrid raised as its largest spike of the
week. None of them generated an alert. All five sit in, or just below, the blind band.

More broadly: **122 unflagged readings waste more energy than the median flagged spike (0.20 kWh).**

### 1.4 Is 1.4 the right multiplier?

Yes, as a ratio threshold — and that is worth stating plainly, because the fix is not to move it.
Among readings the rule never flags, the ratio `usage ÷ baseline` reaches 1.18 at the 90th
percentile, 1.34 at the 99th and 1.39 at the 99.9th. A 1.4 cut therefore sits just past the tail of
normal variation: lowering it to 1.3 would roughly double the caseload with events statistically
indistinguishable from noise.

The threshold is well chosen. The *form* of the rule is what fails. Ratio and absolute excess
should run together — ratio to catch proportionally large events on small baselines, absolute
excess to catch materially large events on any baseline.

---

## 2. Objective 2 — classify anomalies

The brief asks for spikes classified as appliance-related, behavioural or infrastructure-driven.
The four reason codes in the data map onto the first two:

| Reason | Class | Spikes | Resolved |
|---|---|---|---|
| Overnight appliance | Appliance | 32 | 72% |
| Heater malfunction | Appliance | 31 | 74% |
| Schedule change | Behavioural | 30 | 70% |
| Guest visit | Behavioural | 20 | 50% |
| *(none recorded)* | — | 1 | — |

**63 appliance vs 50 behavioural.** The split matters operationally because the two classes have
opposite economics: a behavioural spike is a customer choosing to use energy and needs, at most,
an informational nudge. An appliance spike is a fault that will keep costing money until someone
fixes it.

**No spike anywhere in the week is classified as infrastructure.** Either NovaGrid has no
infrastructure faults, or — far more likely — the reason taxonomy has no code for one, so
infrastructure faults are being absorbed into "Heater malfunction". This is a gap in the data
model, not a finding about the grid, and it should be closed before the next cycle.

### 2.1 Recurrence is the signal the reason codes are hiding

Classification is currently applied per event. Applied per household it identifies faults outright:

- **CUST006 (Leeds)** — 11 spikes, of which **7 are "Overnight appliance"**. That is not seven
  incidents; that is one appliance, malfunctioning nightly, generating seven alerts.
- **CUST008 (London)** — 7 spikes, of which **5 are "Heater malfunction"**.
- **19 of 20 households** have at least one appliance-fault spike.
- The five worst households carry **44 of 114 spikes (38.6%)**.

Seven alerts to a customer whose appliance is broken is not proactive service. It is the same
alert seven times.

---

## 3. Objective 3 — proactive alerts

Alerting is the part of the system that is genuinely working, and the report should say so.

- **111 of 114 spikes alerted (97.4%)**; median latency **14.4 minutes**, 90th percentile 28
  minutes, maximum 36 minutes. Every alert went out inside the same hour as the reading, against
  a complaint cycle the brief describes as monthly.
- **No alert was sent on a non-spike** — zero false alarms.

Three defects:

1. **Three spikes never alerted** — `REC000015` (the mis-flagged record), `REC001414` (CUST005,
   +55%) and `REC004675` (CUST014, +55%). Two are real spikes that silently failed to notify.
2. **Six alerts carry a timestamp earlier than the reading that triggered them**, by up to 5.2
   minutes. An alert cannot precede its cause; this is a clock-skew or timezone defect in the
   alerting service and it makes latency reporting unreliable until fixed.
3. **`alert_time` is written in US date format (M/D/YYYY)** while `reading_timestamp` uses UK
   format (DD/MM/YYYY), in the same file. Any tool that parses both columns with one format
   silently destroys the alert timeline — the failure is invisible, which is what makes it
   dangerous.

---

## 4. Objective 4 — enhance monitoring

### 4.1 Where the value leaks

```
114 spikes detected
    ↓  3 lost
111 alerts sent          97% of detected
    ↓  34 lost
 77 cases resolved       68% of detected
```

The detector loses 3%. The operation loses 30%.

### 4.2 Resolution is regional, and it is not explained by workload

| Region | Cases | Resolved | Rate | Median alert latency |
|---|---|---|---|---|
| Manchester | 21 | 11 | **52%** | 9.4 min |
| London | 31 | 19 | 61% | 15.6 min |
| Bristol | 7 | 5 | 71% | 14.8 min |
| Leeds | 42 | 30 | 71% | 11.8 min |
| Glasgow | 13 | 12 | **92%** | 21.0 min |

Manchester has the *fastest* alerts and the *worst* closure rate. Glasgow has the slowest alerts
and the best. Whatever drives resolution, it is not the analytics — it is what happens after the
alert lands. That is a process question for the support organisation, and this dashboard can
measure it but cannot fix it.

Behavioural cases close least often (Guest visit, 50%), which is unsurprising: there is nothing to
fix, so nothing to close. That argues for a separate disposition — "no action required" — rather
than leaving them open and depressing the metric.

### 4.3 What the data does *not* support

Two claims are commonly attached to projects like this. Neither survives contact with this extract:

- **"Waste concentrates in peak hours."** Mean consumption ranges from 0.69 to 0.78 kWh across the
  entire 24-hour cycle — a 12% spread with no diurnal shape. Spikes are distributed evenly around
  the clock (1 to 10 per hour, no pattern). There is no peak period in this dataset to concentrate
  in.
- **"Anomalies cluster by housing type."** Spike rates are 1.9% for flats, 1.6% for detached and
  1.5% for semi-detached — a difference of a handful of events across 6,720 readings. Not
  actionable.

Reporting these as findings would be reporting noise. They are recorded here so the next analyst
does not have to re-derive them.

---

## 5. What the waste is actually worth

At the Ofgem price cap for January–March 2024 (28.62 p/kWh):

| | |
|---|---|
| Excess energy from flagged spikes, one week, 20 households | 23.15 kWh — **£6.63** |
| Share of total consumption in the window | 0.46% |
| Annualised per meter | 60.2 kWh — **£17.23** |
| Extrapolated across a 1m-meter fleet | **≈ £17.2m per year** |

**The £17.2m figure is an illustration of scale, not a forecast.** It extrapolates one January week
from 20 households to a million, assumes the sample is representative when it is demonstrably a
low-baseline slice, and takes no account of seasonality. Treat it as an order of magnitude for
prioritisation and nothing more.

The honest framing is this: the *energy* recovered per spike is small — pennies. The value is in
what the spike reveals. A heater malfunctioning nightly costs a few pence per event and hundreds
of pounds over a winter, and it is a fault, a safety question, and a complaint waiting to be
filed. The business case for spike detection is fault-finding and trust, not kilowatt-hours.

---

## 6. Recommendations

**1. Add an absolute-excess trigger to the detection rule.** Flag when
`energy_usage_kWh − baseline_kWh > 0.30` regardless of ratio. This closes the 19% blind band. In
this week it surfaces five events the current rule ignored, each wasting more energy than 97% of
the spikes it did flag — only three flagged spikes in the whole week wasted as much. Cost: one
line of logic. *(Owner: analytics — this week.)*

**2. Rank the worklist by kWh wasted, not by percentage.** The two orderings disagree badly: the
event that wasted the most energy all week (`REC004602`, 0.34 kWh) ranks **85th of 114** by
reported percentage, while the loudest alert (+97%) ranks only 5th by energy wasted. Field
resources are currently pointed at the loudest events rather than the most expensive ones. Implemented in
`02_data_outputs/spike_events.csv` (`waste_rank` vs `pct_rank`) and in the dashboard worklist.

**3. Escalate on recurrence, not on events.** When the same reason code appears three or more
times for one household within seven days, stop sending alerts and raise an engineer visit.
CUST006 alone would convert seven alerts into one job. *(Owner: operations.)*

**4. Fix three alerting defects.** The clock skew producing six negative latencies; the three
spikes that never alerted; and the mixed date formats between `reading_timestamp` and
`alert_time`. All three are small and all three corrupt the metrics built on top of them.

**5. Add an infrastructure reason code, and a "no action required" disposition.** The first closes
a gap in the brief's own taxonomy. The second stops behavioural cases from being counted as
operational failures.

**6. Investigate Manchester's closure rate as a process problem.** 52% against a 92% ceiling
demonstrated by Glasgow, with faster alerts and a smaller caseload. This is the largest single
recoverable loss in the funnel and it needs no new analytics at all.

---

## 7. Method, and what would make this better

**Method.** One Python pipeline (`01_pipeline/novagrid_pipeline.py`) performs cleaning, feature
engineering, rule audit and aggregation, and emits every downstream artefact. Charts and dashboard
read those artefacts; nothing is hand-entered anywhere, so the whole report regenerates from the
raw CSV with two commands. Cleaning decisions are logged in `data_quality_log.md`.

**Limits of this dataset.** Seven days, 20 households, one January week. That is enough to audit a
detection rule and size an operational gap. It is not enough to establish seasonality, to model
consumption, or to forecast anything. Any statement in this report about trends over time is
deliberately absent for that reason.

**What would make the next iteration materially better:**

- **A longer window** — twelve months would let the baseline be validated (the supplied
  `baseline_kWh` changes daily, so it is not the "4-week average for the same time slot" the brief
  describes) and would make seasonal comparison possible.
- **Appliance-level or half-hourly circuit data**, which is what would turn "Heater malfunction"
  from a label someone typed into a classification the system can make.
- **Case outcome data** — what the engineer found, whether the spike recurred afterwards. Without
  it, "resolved" is an unverified status, and the effectiveness of the whole programme cannot be
  measured.
- **The complaint log.** The brief frames this project around customer complaints during off-peak
  seasons. Nothing in this extract can be joined to a complaint, so the central business claim —
  that spike detection reduces complaints — remains untested here.
