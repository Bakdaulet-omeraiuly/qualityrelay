#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pytest -q
python -m qualityrelay17.demo > examples/results/DEMO_SYNTHETIC.json
python - <<'PY'
import json
from qualityrelay17.benchmark import run_benchmark
from qualityrelay17.digital_line import run_line
open('examples/results/BENCHMARK_30x1000_SYNTHETIC.json','w').write(json.dumps(run_benchmark(range(30),1000),indent=2))
open('examples/results/FACTORY_LINE_SYNTHETIC.json','w').write(json.dumps(run_line(120,42,lines=2),indent=2))
PY
echo 'All outputs SIMULATED/TEST_FIXTURE; physical validation NOT performed.'
