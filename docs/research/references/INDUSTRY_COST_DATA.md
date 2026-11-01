# What poor quality and downtime cost manufacturers

Context for the problem-significance slide: what one idle hour costs, and how much revenue
goes to scrap, rework and other quality failures. Machine-readable copy:
[`industry_cost_benchmarks.csv`](industry_cost_benchmarks.csv).

**Read the confidence column.** Most of these numbers come from industry surveys and vendor
or consultancy blogs, not peer-reviewed studies. Only figures marked **High** were traced to
the primary report; treat the rest as directional and cite the original source, not the blog.

## Cost of one hour of unplanned downtime

| Figure | Scope | Original source | Found via | Confidence |
|---|---|---|---|---|
| **$2.3M per hour** (> $600/second), ~2× the 2019 level | Large automotive plant | Siemens, *True Cost of Downtime 2024* (181 interviews) | [OxMaint](https://oxmaint.com/industries/manufacturing-plant/cost-of-unplanned-downtime-in-manufacturing-2026), [ReliaMag](https://reliamag.com/topics/articles/cost-unplanned-downtime-manufacturing) | **High** — primary PDF located |
| **$1.4T per year, 11% of revenue** (up from $864B, 8%, in 2019–20) | World's 500 largest companies | Siemens, *True Cost of Downtime 2024* | [ReliaMag](https://reliamag.com/topics/articles/cost-unplanned-downtime-manufacturing) | **High** — primary PDF located |
| $36K per hour | Fast-moving consumer goods (low end) | Siemens, *True Cost of Downtime 2024* | search results citing the report | High |
| $1.8–2M+ per hour | Semiconductor fab | Siemens, *True Cost of Downtime 2024* | [OxMaint](https://oxmaint.com/industries/manufacturing-plant/cost-of-unplanned-downtime-in-manufacturing-2026) | Medium — secondary only |
| ≈ $260K per hour | “Average” manufacturer | Aberdeen Research | [SEQENT](https://seqent.com/blog/the-true-cost-of-unplanned-downtime-by-industry/), [ReliaMag](https://reliamag.com/topics/articles/cost-unplanned-downtime-manufacturing) | Low–medium — secondary only; some sources quote it as “up to”, not an average |
| ≈ $125K per hour | Cross-sector median, 3,215 plant decision-makers, 11 sectors | ABB, *Value of Reliability* 2023 | [SEQENT](https://seqent.com/blog/the-true-cost-of-unplanned-downtime-by-industry/) | Medium — secondary only |
| $10K–$50K per hour | Discrete manufacturing (lower end) | not stated | [ReliaMag](https://reliamag.com/topics/articles/cost-unplanned-downtime-manufacturing) | Low–medium |
| ~50% more per hour than in 2019 | Manufacturing overall | Aberdeen | [ReliaMag](https://reliamag.com/topics/articles/cost-unplanned-downtime-manufacturing) | Low–medium |

## Cost of poor quality (COPQ)

| Figure | Scope | Original source | Found via | Confidence |
|---|---|---|---|---|
| **15–20% of sales** | Quality-related costs, many manufacturers | ASQ | [Manufacturing Lead Gen](https://manufacturingleadgeneration.com/manufacturing-quality-statistics/) | Medium — widely attributed to ASQ; original ASQ wording not confirmed |
| 10–30% of revenue; < 5% at world-class plants | Typical manufacturer | Learn Lean Sigma | [Manufacturing Lead Gen](https://manufacturingleadgeneration.com/manufacturing-quality-statistics/) | Low–medium — single consultancy source |
| ~15% of sales (range 5–35%) | Average COPQ by complexity | IISE | [Manufacturing Lead Gen](https://manufacturingleadgeneration.com/manufacturing-quality-statistics/) | Low–medium |
| 1.4–2.2% of revenue (median ~1.4%; top performers < 0.6%) | Visible scrap + rework only | APQC / EASE | [Manufacturing Lead Gen](https://manufacturingleadgeneration.com/manufacturing-quality-statistics/) | Medium–low |
| Fully loaded COPQ 3–5× the visible scrap line | Hidden capacity, labour, freight | iFactory (vendor) | iFactory blog | Low |
| ~40% of raw material and parts scrapped or reworked at one point | Tesla Model 3 ramp, 2018 | internal documents reported by CNBC | [CNBC](https://www.cnbc.com/2018/06/05/tesla-factories-have-struggled-with-scrap-production-rate-reports.html) | Medium — news report |

## Where a defect is caught decides what it costs

The cost-of-quality “1-10-100” rule of thumb: about **$1** to catch a defect at production or
incoming inspection, **$10** during assembly, **$100+** if it reaches the customer
([Manufacturo](https://manufacturo.com/resources/blog/the-cost-of-quality-in-high-complexity-manufacturing)).
A related heuristic: each $1 of prevention avoids $5–15 of failure cost
([User Solutions](https://usersolutions.com/blog/cost-of-quality)). Both are heuristics, not
measurements — useful for explaining why QualityRelay measures at the producing station and
feeds deviations straight back to the machine.

## What the deck uses

Slide 1 uses only the three strongest figures: **$2.3M per hour** and **$1.4T a year (11% of
revenue)** from Siemens 2024, and **15–20% of sales** from ASQ. None of these are QualityRelay
results, and the simulated savings in this repo are not factory savings.

## Provenance

The figures were first gathered by the team with a Tavily web search on 31 Oct 2026, from the
pages linked above. On 1 Nov 2026 those pages could not be re-fetched from the cloud build
environment (network policy); the Siemens figures were cross-checked against search results
pointing to the primary Siemens PDF, and the Aberdeen and COPQ figures were confirmed only as
secondary citations. Re-check any figure against its original source before external
publication.
