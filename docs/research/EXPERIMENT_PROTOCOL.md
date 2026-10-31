# Pre-registerable scientific protocol

## Endpoints and unit of analysis
Unit = unique 3D printed specimen + unique lot. Do not split frames of the SAME specimen between train and test. Primary: unsafe-pass rate under matched good-unit release throughput and inspection budget. Secondary: false HOLD, inspection seconds, cost per good unit, Brier, ECE, claim traceability, physical route mismatch. Include CIs and raw counts.

## Data collection
Print nominal, close-tolerance, tight-risk, visually chipped, stringing, warping samples with unique QR/ID (not identifying human subject). Use CAD revision and physical caliper record; repeated stable gauge checks (at least 10) for within-operator repeatability, plus another operator/instrument if available. Collect phone and Pi images independently with logged lighting, distance and angle, not screenshots of each other. Two ground-truth human assessors adjudicate crack/assembly fit; document disagreement.

## Physically independent ground truth
Blind measurement and actual fit test separate from model predictions. For barely perceptible 0.1mm shift, report measurement uncertainty instead of confidently assigning a label by camera. Distinguish nominal design geometry, printed geometry and observed fitness.

## Synthetic data
Use predetermined controlled hidden variables. Register 30 seeds × 1000 parts quick baseline and, if available, more runs with uncertainty analysis; identical seeds for every model. Vary printer drift, part tolerance distribution, sensor noise, camera correlation, cross-station evidence missingness and physical sorter verification errors. Cost parameters are assumptions until independently measured.

## Safeguards against misleading claims
- A model that holds everything has zero unsafe PASS: therefore also constrain good part release/throughput.
- Negative result must be published. Older 9.0 toy V-DER vs Information Gain differences were near zero; new reference also shows cost disadvantage, not significant improvement.
- HMAC signature does not make sensor evidence true; it only protects envelope integrity under a secret.
- Simulated cost savings are not factory savings. Include GPU cloud cost, human setup and downtime.
- A low-quality photo is `UNUSABLE`, not a 'good' or 'bad' vote.

## Test matrix and experiments
| ID | Stimulus | Expected safe outcome |
|---|---|---|
| E01 | phone clear; Pi suspect; caliper within tolerance | HOLD, explanation includes Pi evidence |
| E02 | Pi offline; old Pi image available | HOLD stale, local station retains operations |
| E03 | same photo duplicated as 2 sensor inputs | do not claim two independent observations |
| E04 | CAD rev incorrect | HOLD and request correct reference |
| E05 | visually normal, oversize tab | HOLD dimensional failure |
| E06 | crack visible, dimension okay | HOLD, expert verification |
| E07 | image blurred | recapture, no defect certainty |
| E08 | classifier OOD lighting and printer | detect distribution shift / abstain |
| E09 | LLM invents event ID | rejected explanation, no actuation |
| E10 | Chief Engineer unavailable | peer-local bounded service continues |
| E11 | servo request without operator | denied, zero hardware command |
| E12 | correct software route, wrong physical bin | discrepancy alert, no false count |
| E13 | two identical sensor ACK IDs | one verified count |
| E14 | false assumption that image is calibrated | hold pending calibration |
| E15 | simulation images mislabeled as real | ingestion rejects or flags mixed provenance |

## Reporting
Create per-run JSON manifest (code commit, model, seed, timestamp, origin, scenario, hyperparameters, cloud/hardware, exact policies, costs) and raw CSV rows, export plots as PNG if needed. Do not overwrite after seeing results; mark preregistered vs exploratory analysis. Run robustness on unseen lot/printer and compare family-wise uncertainties across tests.
