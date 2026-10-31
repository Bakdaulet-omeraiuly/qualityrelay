# QualityRelay: photo capture guide (training + measurement)

There are two kinds of photo with different rules, and one Studio camera panel to save both.

| | **A. Training photos** (NVIDIA anomaly model) | **B. Measurement / reference photos** |
|---|---|---|
| Goal | Train STFPM on *our* printed parts, then check that it flags the defective ones | Measure width in mm from a photo and compare with a GOOD reference |
| Saved to | `data/prints/good/`, `data/prints/defect/` (or `inbox/` to label later) | `data/measure/` |
| Panel setting | Purpose = **training photo** | Purpose = **measurement / reference** |
| Part pose | **Turn good parts a little** between shots | **Same pose against the marker** every time |
| Caliper reading | Not needed | **Enter it**, so we learn the real photo-measurement error |

## 0. Before you start (once)
1. **Print the marker:** `examples/aruco/marker_sheet_20mm.png` at **100% scale**. A copy is in
   `QualityRelay_demo_photos/`.
2. **Check the ruler:** measure the 50 mm line with the caliper. If it is not 50.0 mm, reprint.
3. **Set up the shot:** plain light background (white or grey card), even lighting with no hard
   shadows, phone or Pi camera held straight above.
4. **Open the panel:** start the Studio (`uvicorn qualityrelay17.api:app --port 8000`), open the
   3D Lab, click the iPhone camera of the right lane (slot / tab), then use **Upload photo** or
   **Open device camera**.

## A. Training photos (anomaly model)
- **How many:** minimum **30 good + 10 defect**; this is when the panel says "ready to train".
  Recommended: **50+ good, 20+ defect**, spread over defect types. Without defect photos no score
  can be computed (AUROC needs both classes).
- **Same set-up every photo:** same camera, distance, angle, lighting and background.
- **One part per photo:** centred, filling most of the frame.
- **The marker sits in the same corner in every photo.** The model resizes the whole image to
  256×256 grayscale, so a marker that moves around looks like a change. Keep it small and fixed.
- **Good parts:** use many *different* good parts, and turn each a little between shots.
- **Defect parts:** real defects only. In the panel, choose **Label = defective part** and the
  **Defect type** (warp, stringing, chip, hole, crack, layer_shift, under_extrusion, wrong_size,
  other). The type is written into the file name.
- **Mix part types:** alternate slots and tabs while shooting. The panel names files with a random
  hash prefix, so the train/test split (first 70% of `good/` by name) is not biased by order.
- **Reject bad shots:** no blurry, dark or cropped photos. The panel's image-quality check warns
  you; re-shoot if it says so.

## B. Measurement / reference photos
- **Pose:** place the part **the same way relative to the marker** every time (e.g. long edge
  parallel to the marker's bottom edge, about 1–2 cm to its right).
- **Resolution:** the part plus marker should fill the frame. The panel shows px/mm; aim for
  ≥ 15, ideally ~25.
- **Caliper:** measure the same part and type the reading into **Caliper reading**. The panel then
  shows *photo − caliper*. This is how the synthetic accuracy (0.07 mm at 15 px/mm) gets checked
  on real parts.
- **Reference comparison:** save one GOOD part as the reference (**★ Set as GOOD reference**),
  then photograph the part to inspect in the same pose and click **⇄ Compare**. Results are
  candidates for human review, never a pass or reject.

## Bookkeeping (required for honest results)
- **Specimen ID:** enter one for every photo (e.g. `P07`), the same ID you write on the part.
- **Capture log:** every save is appended to `data/prints/capture_log.csv` with file, purpose,
  label, defect type, specimen ID, caliper reading and photo-measured width.
- **Label check:** a **second person** checks every good/defect label and writes their name in the
  `label_checked_by` column. Results are reported as `PHYSICAL_CAPTURE` only after that.
- **Inbox:** sort anything in `data/prints/inbox/` into `good/` or `defect/` before training.

## Train (Brev, NVIDIA L4, about $0.85/h)
```bash
python scripts/train_anomaly.py --data captured --root data/prints \
  --epochs 100 --size 256 \
  --provider brev --instance-type "g2-standard-4:nvidia-l4:1" --price-per-hour 0.85
```
- **Outputs:** image AUROC, a run manifest and an ONNX export for the Hailo handoff.
- **Reporting:** report as `PHYSICAL_CAPTURE` only, and only after the label check.
