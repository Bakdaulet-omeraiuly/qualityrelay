#!/usr/bin/env python3
"""Summarize a QualityRelay specimen-measurement CSV (standard library only).

Reads the tidy CSV produced by web/measurement_logger.html (one row per caliper/gauge
reading; schema in docs/engineering/templates/specimen_measurements.csv) and prints, per
specimen and feature, the count / min / max / mean / spread, plus the mean deviation from
nominal where a nominal is recorded. Critical features (width, slot_inner_width) whose mean
deviation exceeds the tolerance, or whose spread exceeds the repeatability limit, are
flagged.

This only SUMMARIZES measurements. It does not change any code, tolerance, or nominal; a
person (or a later agent) decides what, if anything, to update. Measured data is evidence,
not an automatic verdict.

Usage:
  python3 scripts/summarize_measurements.py measurements.csv
  python3 scripts/summarize_measurements.py measurements.csv --json out.json
  python3 scripts/summarize_measurements.py measurements.csv --tol 0.15 --spread 0.05
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import OrderedDict

CRITICAL_FEATURES = {"width", "slot_inner_width"}


def load_rows(path: str) -> list[dict]:
    # utf-8-sig so the UTF-8 BOM that Excel-friendly exports add is stripped.
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return []
    required = {"specimen_id", "feature", "value_mm"}
    missing = required - set(rows[0].keys())
    if missing:
        raise SystemExit(f"CSV is missing required columns: {', '.join(sorted(missing))}")
    return rows


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def summarize(rows: list[dict], tol: float, spread_limit: float) -> dict:
    # group by specimen, then feature
    specimens: "OrderedDict[str, dict]" = OrderedDict()
    for r in rows:
        sid = (r.get("specimen_id") or "").strip()
        feat = (r.get("feature") or "").strip()
        val = fnum(r.get("value_mm"))
        if not sid or not feat or val is None:
            continue
        spec = specimens.setdefault(sid, {
            "specimen_id": sid,
            "manual_id": (r.get("manual_id") or "").strip(),
            "part_type": (r.get("part_type") or "").strip(),
            "features": OrderedDict(),
        })
        fe = spec["features"].setdefault(feat, {"values": [], "locations": [], "nominals": []})
        fe["values"].append(val)
        fe["locations"].append((r.get("location") or "").strip())
        nom = fnum(r.get("nominal_mm"))
        if nom is not None:
            fe["nominals"].append(nom)

    out = {"tolerance_mm": tol, "spread_limit_mm": spread_limit, "specimens": [], "flags": []}
    for sid, spec in specimens.items():
        srec = {"specimen_id": sid, "manual_id": spec["manual_id"],
                "part_type": spec["part_type"], "features": []}
        for feat, fe in spec["features"].items():
            vals = fe["values"]
            mean = statistics.fmean(vals)
            spread = max(vals) - min(vals)
            nominal = fe["nominals"][0] if fe["nominals"] else None
            dev = (mean - nominal) if nominal is not None else None
            critical = feat in CRITICAL_FEATURES
            frec = {
                "feature": feat, "n": len(vals),
                "min": round(min(vals), 3), "max": round(max(vals), 3),
                "mean": round(mean, 3), "spread": round(spread, 3),
                "nominal": nominal, "mean_deviation": round(dev, 3) if dev is not None else None,
                "critical": critical,
            }
            srec["features"].append(frec)
            if critical and dev is not None and abs(dev) > tol:
                out["flags"].append(
                    f"{sid}: {feat} mean {mean:.2f} mm deviates {dev:+.2f} mm "
                    f"from nominal {nominal:.2f} (tolerance ±{tol:.2f})")
            if critical and spread > spread_limit:
                out["flags"].append(
                    f"{sid}: {feat} spread {spread:.2f} mm exceeds repeatability limit {spread_limit:.2f}")
        out["specimens"].append(srec)
    return out


def print_report(summary: dict) -> None:
    print(f"{'specimen':14}{'feature':18}{'n':>3}{'mean':>9}{'spread':>9}{'nominal':>9}{'dev':>8}  flag")
    print("-" * 80)
    crit_flagged = {f.split(":")[0] + ":" + f.split(":")[1].split()[0] for f in summary["flags"]}
    for spec in summary["specimens"]:
        head = f"{spec['specimen_id']:14}"
        for i, fr in enumerate(spec["features"]):
            key = f"{spec['specimen_id']}: {fr['feature']}"
            flagged = any(fl.startswith(key) for fl in summary["flags"])
            nom = f"{fr['nominal']:.2f}" if fr["nominal"] is not None else "-"
            dev = f"{fr['mean_deviation']:+.2f}" if fr["mean_deviation"] is not None else "-"
            mark = "  <-- CHECK" if flagged else ("  (critical)" if fr["critical"] else "")
            print(f"{head if i == 0 else '':14}{fr['feature']:18}{fr['n']:>3}"
                  f"{fr['mean']:>9.2f}{fr['spread']:>9.2f}{nom:>9}{dev:>8}{mark}")
    print("-" * 80)
    if summary["flags"]:
        print(f"{len(summary['flags'])} flag(s) for human review:")
        for fl in summary["flags"]:
            print("  - " + fl)
    else:
        print("No critical-feature flags against the current tolerance.")
    print("\nMeasurements are evidence for review; this tool changes no code or thresholds.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("csv", help="path to a specimen-measurement CSV")
    ap.add_argument("--tol", type=float, default=0.15, help="critical-dimension tolerance (mm, default 0.15)")
    ap.add_argument("--spread", type=float, default=0.05, help="repeatability spread limit (mm, default 0.05)")
    ap.add_argument("--json", help="also write the summary as JSON to this path")
    args = ap.parse_args()
    rows = load_rows(args.csv)
    if not rows:
        print("No data rows found.")
        return 0
    summary = summarize(rows, args.tol, args.spread)
    print_report(summary)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"\nWrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
