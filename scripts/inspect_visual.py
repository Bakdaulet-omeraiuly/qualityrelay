#!/usr/bin/env python3
"""Offline, read-only visual inspection candidates: photo-to-photo, anomaly map, Roboflow JSON.

No image is sent to any cloud service. No trained model is bundled or run by this CLI.
Examples are in docs/engineering/VISUAL_INSPECTION_INTEGRATIONS.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
from qualityrelay17.inspection_visuals import (
    draw_candidate_boxes, model_anomaly_map, overlay_heatmap,
    reference_difference, roboflow_predictions,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--mode', choices=('reference', 'anomaly-map', 'roboflow-json'), required=True)
    parser.add_argument('--live', required=True, help='Local captured image path (.png/.jpg)')
    parser.add_argument('--out', required=True, help='Output directory (creates report.json, heatmap.png, boxes.png)')
    parser.add_argument('--specimen-id', required=True)
    parser.add_argument('--event-id', required=True, help='Unique live-image event ID')
    parser.add_argument('--source-root', required=True, help='Source root of the original live image')
    parser.add_argument('--station-id', required=True, help='Phone, Pi or authorized capture station')
    parser.add_argument('--source-tier', choices=('SIMULATED', 'PHYSICAL_CAPTURE', 'EXTERNAL_DATASET'), required=True)
    parser.add_argument('--calibration-id', help='Metadata only: the ID is not validated by this CLI')
    parser.add_argument('--reference', help='Reference image path for reference mode')
    parser.add_argument('--reference-event-id', help='Reference source event ID')
    parser.add_argument('--reference-root', help='Reference source root')
    parser.add_argument('--aligned', action='store_true', help='Assert alignment already established externally')
    parser.add_argument('--diff-threshold', type=int, default=40, help='Uncalibrated difference threshold [0,255]')
    parser.add_argument('--anomaly-map', help='Raw HxW score map .npy from STFPM/Anomalib')
    parser.add_argument('--raw-threshold', type=float, help='User supplied raw score threshold (not a probability)')
    parser.add_argument('--predictions-json', help='Local Roboflow-style prediction JSON')
    parser.add_argument('--model-id', help='Identifier of model that already produced map/predictions')
    parser.add_argument('--renderer', choices=('opencv', 'supervision'), default='opencv')
    return parser


def execute(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    live_path = Path(args.live)
    live = cv2.imread(str(live_path), cv2.IMREAD_COLOR)
    if live is None:
        parser.error('live image path does not exist or is unreadable')
    common = dict(specimen_id=args.specimen_id, image_event_id=args.event_id,
                  source_root=args.source_root, station_id=args.station_id,
                  source_tier=args.source_tier, calibration_id=args.calibration_id)
    if args.mode == 'reference':
        if not (args.reference and args.reference_event_id and args.reference_root and args.aligned):
            parser.error('reference mode needs --reference, --reference-event-id, --reference-root, --aligned')
        ref = cv2.imread(args.reference, cv2.IMREAD_COLOR)
        if ref is None:
            parser.error('reference image path does not exist or is unreadable')
        report, raw, mask = reference_difference(ref, live, **common,
                                                 reference_event_id=args.reference_event_id,
                                                 reference_root=args.reference_root,
                                                 aligned=args.aligned, threshold=args.diff_threshold)
    elif args.mode == 'anomaly-map':
        if args.anomaly_map is None or args.model_id is None or args.raw_threshold is None:
            parser.error('anomaly-map mode needs --anomaly-map, --model-id and --raw-threshold')
        raw_map = np.load(args.anomaly_map, allow_pickle=False)
        report, raw, mask = model_anomaly_map(live, raw_map, **common,
                                              model_id=args.model_id,
                                              raw_threshold=args.raw_threshold)
    else:
        if args.predictions_json is None or args.model_id is None:
            parser.error('roboflow-json mode needs --predictions-json and --model-id')
        with Path(args.predictions_json).open(encoding='utf-8') as stream:
            payload = json.load(stream)
        report, raw, mask = roboflow_predictions(live, payload, **common, model_id=args.model_id)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'report.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    overlay = overlay_heatmap(live, raw, mask=mask)
    annotated = draw_candidate_boxes(overlay, report, renderer=args.renderer)
    if not cv2.imwrite(str(out / 'heatmap.png'), overlay) or not cv2.imwrite(str(out / 'boxes.png'), annotated):
        raise OSError('cannot write visual artifact images')
    print(json.dumps({'decision': report['decision'], 'region_count': len(report['regions']),
                      'method': report['method'], 'output': str(out), 'warning': 'REVIEW ONLY — NOT PASS'}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(execute())
