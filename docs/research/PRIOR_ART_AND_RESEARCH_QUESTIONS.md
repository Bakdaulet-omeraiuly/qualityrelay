# Scientific prior art, precise gap and proposed tests

**Do not claim:** we read 10,000 studies, invented Bayesian VOI, invented provenance/signatures, invented multi-agent manufacturing, proved industrial cost savings or attained L5 maturity. Earlier QualityRelay 9.0 includes **a retrieval script**, not a completed 10,000-item screened corpus. The citation list below was individually checked through public research pages; it is not a systematic review.

## Key externally verifiable work
1. Hedberg et al. (2021), [Defining requirements for integrating information between design, manufacturing, and inspection](https://www.nist.gov/publications/defining-requirements-integrating-information-between-design-manufacturing-and) — real integration experiment did not fully link all digital-thread information. Relevance: strong factory provenance and CAD revision crosswalking.
2. Frechette, Shao, Pease (2026), [NIST Digital Twins Workshops Summary Report](https://www.nist.gov/publications/digital-twins-workshops-summary-report) — interoperability, VVUQ, cybersecurity, workforce readiness gaps. Relevance: test assumptions, not visual demo alone.
3. Anindya (2026), [From digital shadows to assured intervention](https://link.springer.com/article/10.1186/s44147-026-01295-x) — systematic review of 235 selected manufacturing quality digital twins; no reviewed study integrated a full assured intervention chain. This is a claim about that review's corpus, **not a proof that no systems exist anywhere**.
4. Li, Naito, Shirado (ICML 2026), [Systematic Failures in Collective Reasoning under Distributed Information in Multi-Agent LLMs](https://proceedings.mlr.press/v306/li26ej.html) — HiddenBench: 30.1% distributed vs 80.7% full-context single agent in reported evaluation, showing structured communication failure. These values are NOT QualityRelay performance.
5. [MVTec Anomaly Detection dataset](https://www.mvtec.com/research-teaching/datasets/mvtec-ad) — industrial baseline, >5,000 images, noncommercial/share-alike dataset terms. Relevance: pretrain/testing methodology, not factory-specific acceptance.
6. [ReinAD, NeurIPS 2025](https://proceedings.neurips.cc/paper_files/paper/2025/file/1bdcb065d40203a00bd39831153338bb-Paper-Datasets_and_Benchmarks_Track.pdf) — benchmark real-world distribution shift limitations; check full protocol before borrowing numerical comparisons.
7. [NVIDIA Isaac Sim](https://developer.nvidia.com/isaac/sim/) — simulation/Replicator is existing scientific infrastructure, not a new research invention.
8. [NVIDIA PhysicsNeMo](https://github.com/NVIDIA/physicsnemo) — physics-ML framework; a pretrained surrogate is not validated for our PLA specimens.

## Research gap that we can actually test
Proposed hypothesis: For independently authorized multi-factory camera+CAD+metrology evidence, **provenance-constrained active acquisition plus separately governed physical intervention** improves one or more operational dimensions relative to matched conservative and centralized baselines **without increasing unsafe PASS**. Do not assume improvement just because more agents are added.

## Five falsifiable hypotheses
- H1 **Lineage:** Reused frame or derived CAD/photo result cannot count twice as independent modality. Measure confidence calibration/error vs naive Bayes/voting.
- H2 **Decision action:** V-DER/CAIR reduces excess inspection time at matched unsafe-pass tolerance vs fixed rule / entropy selection.
- H3 **Decentralized governance:** Under random link loss, local station can process bounded safe operations and reconcile correctly after reconnect.
- H4 **Sim-to-real:** Models trained on Replicator/physical photographs maintain performance under held-out new camera angle, printer, filament, and light; quantify failure (not just success).
- H5 **Assured physical action:** Operator-approved state machine + independent bin sensor reduces duplicated/lost sort events vs unverified servo command.

## Comparator matrix
| Variant | Same evidence budget? | Same model and core? | Main question |
|---|---|---|---|
| P0 Conservative rules | Yes | N/A | Can simpler logic achieve same safety? |
| P1 Single full-context model | Yes | Same entitled model | Are specialists needed? |
| P2 Multi-agent naive voting | Yes | Same weights | Does collaboration add value? |
| P3 Centralized all-access baseline | No (oracle), clearly label | Same deterministic math | Upper-bound reference only |
| P4 Centralized matched access | Yes | Same math | Does topology matter? |
| P5 SAFE-MESH no V-DER | Yes | Same math | Does lineage/dissent help? |
| P6 SAFE-MESH + V-DER/CAIR | Yes | Same math | Value of active inspection? |
| P7 + governed physical feedback | Yes | Same math | Does action assurance reduce event mismatch? |

## Primary endpoints
Unsafe PASS probability with Wilson/cluster bootstrap CI; acceptable-unit throughput; inspection $/part; physical route audit mismatch; calibrated Brier score; communication bytes, latency and queue occupancy. Comparisons must be **paired** (same underlying latent defect and camera/noise draws), with pre-registered seeds and thresholds, and a no-benefit/null result reported transparently.

## Formal definitions
- `unsafe_PASS` means physically bad specimen (blind independent ground truth) is authorized as PASS.
- `HOLD` is an uncertainty management decision, not scrap.
- `CONFIRMED_REJECT` needs independent nonconformance or qualified engineer approval.
- `risk` requires assumptions and calibrated posteriors. Softmax scores are not validated probabilities.
- `discovered` requires literature novelty verification, independent results and appropriate publication/review; a named acronym is not discovery.
