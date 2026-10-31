"""Fit simulator parameters from caliper CSVs exported by web/measurement_logger.html.

    python scripts/calibrate_from_measurements.py data/measurements/*.csv [--scenario F01] [--capture-log data/prints/capture_log.csv]

Prints the per-specimen table, the fitted bias / scatter / caliper repeatability, and the
photo-vs-caliper check. Runs with the fitted values remain SIMULATED (physically calibrated).
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qualityrelay17.sim.physical_data import load_measurements, calibrate, physical_scenario, photo_vs_caliper
from qualityrelay17.sim.scenarios import BY_ID

ap = argparse.ArgumentParser()
ap.add_argument('csv', nargs='+')
ap.add_argument('--scenario', default='F01')
ap.add_argument('--capture-log', default='data/prints/capture_log.csv')
a = ap.parse_args()
rows = load_measurements(a.csv)
cal = calibrate(rows)
print(json.dumps(cal, indent=2))
if cal['status'] == 'FITTED_FROM_PHYSICAL_RECORDS':
    s = physical_scenario(BY_ID[a.scenario], cal).sites[0]
    print(f"\n{a.scenario}-PHYS site: bias {s.printer_bias_mm} mm, width sd {s.width_sd_mm} mm, caliper sd {s.caliper_sd_mm} mm")
pv = photo_vs_caliper(rows, a.capture_log)
print('\nphoto vs caliper:', json.dumps(pv, indent=2) if pv else 'no matching specimen IDs in the capture log')
