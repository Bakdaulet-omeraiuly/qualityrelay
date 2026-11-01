# Research papers behind QualityRelay

Each entry says what the paper supports in this repo and what it does **not** let us claim.
Links point to the publisher or an open-access copy; PDFs are not committed here, so licensing
stays with the publishers. BibTeX for all entries is in [`references.bib`](references.bib).

## Inspection, statistics and manufacturing quality

### 1. Sequential inspection with Bayesian value of information
Moliner-Heredia, M., Bruscas-Bellido, G. M., Abellán-Nebot, J. V., Peñarrocha-Alós, I. (2021).
*A Sequential Inspection Procedure for Fault Detection in Multistage Manufacturing Processes.*
**Sensors** 21(22), 7524. DOI [10.3390/s21227524](https://doi.org/10.3390/s21227524) ·
open access: [PMC8618403](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8618403/)

- **Supports:** choosing the next inspection by expected information/decision value instead of
  measuring everything — the idea behind `qualityrelay17/vder.py` and the “single agent +
  value-of-information” row on deck slide 3.
- **Limits:** the published model assumes one active fault at a time; our combined slot+tab
  drift cases extend that assumption and must say so. VOI itself is not our invention.

### 2. EWMA control charts (process drift)
NIST/SEMATECH *e-Handbook of Statistical Methods*, §6.3.2.4 “EWMA Control Charts.”
[itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm](https://itl.nist.gov/div898/handbook/pmc/section3/pmc324.htm)

- **Supports:** detecting small sustained shifts (≈1–1.5σ) that a Shewhart chart misses; control
  limits from a frozen in-control reference, not from a handful of live parts.
- **Limits:** control limits are statistical, not engineering tolerance limits.

### 3. Integrating design, manufacturing and inspection data (digital thread)
Hedberg, T. D., Jr., et al. (2021). *Defining requirements for integrating information between
design, manufacturing, and inspection.* **International Journal of Production Research.**
DOI [10.1080/00207543.2021.1920057](https://doi.org/10.1080/00207543.2021.1920057) ·
[NIST record](https://www.nist.gov/publications/defining-requirements-integrating-information-between-design-manufacturing-and)

- **Supports:** the motivation for provenance-tracked evidence across stations — a small-scale
  model-based enterprise test could not fully link design, manufacturing and inspection data.
- **Limits:** motivates the problem; says nothing about our agents' performance.

### 4. Feedback and feedforward quality-control loops in multi-stage systems
Magnanini, M. C., Demir, O., Colledani, M., Tolio, T. (2024). *Performance evaluation of
multi-stage manufacturing systems operating under feedback and feedforward quality control
loops.* **CIRP Annals** 73, 349–352. DOI [10.1016/j.cirp.2024.04.015](https://doi.org/10.1016/j.cirp.2024.04.015) ·
open access (CC BY-NC-ND): [PoliMi repository](https://re.public.polimi.it/handle/11311/1265622)

- **Supports:** evaluating where to place inspection and how measurement feeds back to the
  producing stage — the closest published framing of the “caliper chamber → CSV → CNC agent
  updates G-code” loop on deck slide 2, and of quality-gate placement.
- **Limits:** a performance-evaluation model, not a closed-loop G-code correction method.

### 5. Uncertainty-aware dynamic sampling (virtual metrology)
Han, X., Miller, M., Moyne, J., Vogl, G., Penkova, A., Jia, X. (2025). *A Comparative Study of
Semiconductor Virtual Metrology Methods and Novel Algorithmic Framework for Dynamic Sampling.*
**IEEE Transactions on Semiconductor Manufacturing** 38(2). DOI
[10.1109/TSM.2025.3531920](https://doi.org/10.1109/TSM.2025.3531920) ·
[NIST record](https://www.nist.gov/node/1886686)

- **Supports:** sending only the uncertain parts to physical measurement (camera agent flags
  SUSPECT → caliper chamber) and growing uncertainty when evidence goes stale.
- **Limits:** semiconductor wafers and an OGP model, not 3D-printed or CNC parts.

## Multi-agent reasoning

### 6. Collective reasoning under distributed information
Li, Y., Naito, A., Shirado, H. (2026). *Systematic Failures in Collective Reasoning under
Distributed Information in Multi-Agent LLMs.* **ICML 2026**, PMLR 306.
[proceedings.mlr.press/v306/li26ej.html](https://proceedings.mlr.press/v306/li26ej.html)

- **Supports:** why agents must explicitly request unique evidence (HiddenBench: 30.1% for
  distributed groups vs 80.7% for one agent with full context — their benchmark, not ours).

### 7. Debate versus majority vote
Choi, H. K., Zhu, X., Li, S. (2025). *Debate or Vote: Which Yields Better Decisions in
Multi-Agent Large Language Models?* **NeurIPS 2025.**
[Proceedings](https://papers.nips.cc/paper_files/paper/2025/hash/934252acd87f254d5d4672fbde283bd2-Abstract-Conference.html) ·
[code](https://github.com/deeplearning-wisc/debate-or-vote)

- **Supports:** keeping a majority-vote baseline so communication is not credited for what
  ensembling alone explains — the “Agents, majority vote” row on deck slide 3.

## Industry report

### 8. Siemens, *The True Cost of Downtime 2024*
[Original PDF](https://assets.new.siemens.com/siemens/assets/api/uuid:1b43afb5-2d07-47f7-9eb7-893fe7d0bc59/TCOD-2024_original.pdf)

- **Supports:** the $2.3M/hour (large automotive plant) and $1.4T/year (11% of revenue, world's
  500 largest companies) figures on deck slide 1. Based on 181 interviews at large industrial
  organizations — do not apply the hourly figure to a small supplier.
- Full figures, secondary sources and confidence levels: [`INDUSTRY_COST_DATA.md`](INDUSTRY_COST_DATA.md).

## How these were found

Papers 1–5 were located and checked through web search on 31 Oct–1 Nov 2026 (citations,
DOIs and abstracts confirmed against publisher, PMC, NIST or university-repository records).
alphaXiv's OpenResearch was evaluated but could not run in the cloud build environment, so it
was not used to produce this list. Papers 6–7 were already cited in
[`../PRIOR_ART_AND_RESEARCH_QUESTIONS.md`](../PRIOR_ART_AND_RESEARCH_QUESTIONS.md) and
[`../COLLECTIVE_17_1_BAKDAULET.md`](../COLLECTIVE_17_1_BAKDAULET.md).
