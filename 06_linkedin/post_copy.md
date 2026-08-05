# LinkedIn copy — NovaGrid spike detection

Three versions below. All numbers match `02_data_outputs/kpi_summary.json`.

**One honesty note before you post:** this is a case-study dataset, not a live utility
system. Every version below says so somewhere ("a case study", "the dataset") — keep that
line in. An audit of a real energy company's production detector is a very different claim,
and someone in your comments will ask.

---

## Version 1 — main post (pairs with the carousel or the console poster)

> The spike detector was working perfectly.
>
> That was the problem.
>
> A smart-meter case study: 6,720 half-hourly readings, 20 households, one week in January.
>
> The utility flags an "abnormal spike" when a home uses more than 1.4× its own baseline.
> Simple, explainable, runs on every reading. And it delivered: 114 spikes detected,
> 97% alerted within a median of 14 minutes, zero false alarms.
>
> So I rebuilt the rule from the raw readings to check it. Three things fell out.
>
> 𝗢𝗻𝗲. Readings in this fleet top out at 1.44 kWh.
>
> So wherever a household's baseline is above 1.03 kWh, 1.4 × baseline is higher than
> anything a meter can physically report — and the rule cannot fire at any level of
> consumption.
>
> That's 19% of all readings. Every spike the system has ever raised came from a
> low-consumption home. The heaviest users are the ones it watches least.
>
> 𝗧𝘄𝗼. The percentage it reports isn't the size of the problem.
>
> The loudest alert of the week — "+97%" — was 0.29 kWh. About 8p of electricity.
> Meanwhile 122 readings that were never flagged wasted more than the median flagged spike did.
>
> We were ranking field work by the wrong number.
>
> 𝗧𝗵𝗿𝗲𝗲. Detection loses 3%. The operation loses 30%.
>
> 114 detected → 111 alerted → 77 resolved. And the gap is regional: one region closes 52%
> of its cases, another closes 92% — on the same detector, the same alert, the same
> 14-minute latency. Nothing in the analytics explains that.
>
> 𝗧𝗵𝗲 𝗳𝗶𝘅 𝗶𝘀 𝗼𝗻𝗲 𝗹𝗶𝗻𝗲.
>
> Keep the ratio rule. Add an absolute one beside it:
>
> usage − baseline > 0.30 kWh
>
> In that single week it surfaces five events the rule ignored, each wasting more energy
> than 97% of the spikes it did catch.
>
> 𝗪𝗵𝗮𝘁 𝗜 𝘁𝗼𝗼𝗸 𝗳𝗿𝗼𝗺 𝗶𝘁:
>
> → Audit the rule, not just its output. 113 of 114 flags reproduced exactly — and the one
> that didn't was flagged while sitting 17% *below* baseline.
>
> → A threshold can be well chosen and still be the wrong shape. 1.4 sits right at the tail
> of normal variation. The multiplier was fine. The multiplication wasn't.
>
> → Report the finding that isn't there. No peak-hour concentration, no housing-type effect.
> Saying so out loud is worth more than a chart that implies otherwise.
>
> Built in Python and pandas, delivered as a single self-contained HTML dashboard —
> filters, tooltips, table views, no server and no BI licence.
>
> What's the most expensive "working as designed" you've run into?
>
> #DataAnalytics #Python #DataAnalysis #EnergyData #SmartMeters #Dashboard #DataVisualization

---

## Version 2 — short (single image: the console poster or the dashboard hero)

> "The rule is working." It was. That was the problem.
>
> A smart-meter case study — 6,720 readings, 20 households, one week.
>
> The detector flags a spike at 1.4 × a home's baseline. But readings in this fleet cap out
> at 1.44 kWh, so on any home whose baseline is above 1.03 kWh the rule mathematically
> cannot fire. 19% of all readings sit in that blind band — and every spike ever raised came
> from a low-consumption home.
>
> Two more things it hid:
>
> • The loudest alert of the week, "+97%", was 8p of electricity. 122 unflagged readings
> wasted more than the median flagged spike.
>
> • 114 spikes detected → 111 alerted → 77 resolved. One region closes 52% of cases,
> another 92%, on identical alerts.
>
> The fix was one line: add usage − baseline > 0.30 kWh beside the ratio rule.
>
> Python + pandas, delivered as one self-contained HTML dashboard. Code and write-up in the comments.
>
> #DataAnalytics #Python #DataVisualization #EnergyData

---

## Version 3 — opening comment (post this yourself, right after publishing)

> Full write-up, the data-quality log (13 issues in the source extract, including two
> different date formats in the same file), and the reproducible pipeline — code, data and
> the dashboard file itself:
>
> https://github.com/Rexxxie/novagrid-energy-spike-detection
>
> Happy to talk through the detection logic with anyone working on anomaly rules — the
> ratio-vs-absolute trade-off shows up well beyond energy.

---

## Alt text for the images (accessibility — LinkedIn supports this per image)

**Console poster:** "Dark analytics dashboard titled 'Abnormal energy spike monitor'. Six
KPI tiles read 114 spikes detected, 19.0% detection blind spot, 97.4% alert coverage, 14.4
minute median latency, 68% cases resolved, £17 wasted per meter per year. Nine chart panels
below show the detection blind spot, spike causes, household caseload, regional resolution,
an alert funnel, reported percentage versus energy wasted, alert latency, and consumption by
hour, plus a priority worklist table."

**Blind-spot chart:** "Scatter plot of 6,720 meter readings by household baseline against
actual reading. All 114 flagged spikes, in red, sit at baselines of 0.77 kWh or below. A
shaded band on the right marks the 19% of readings where the 1.4× rule cannot fire because
the threshold exceeds the fleet's maximum possible reading."

**Dashboard hero:** "A browser window showing the NovaGrid abnormal energy spike monitor
dashboard, with filter controls, six KPI tiles and the detection blind-spot scatter chart."

---

## Posting notes

- **Best format:** the carousel (`novagrid_carousel.pdf`) as a LinkedIn *document* post.
  Document posts hold attention longer than a single image. Use Version 1 as the caption.
- **Single image:** use the console poster with Version 2.
- **Don't put the link in the post body** — put it in the first comment (Version 3).
- The first two lines are all that shows before "…see more". Both versions are built so the
  hook lands inside those two lines.
- Swap the closing question for whatever you actually want to talk about; a genuine question
  outperforms a generic one.
