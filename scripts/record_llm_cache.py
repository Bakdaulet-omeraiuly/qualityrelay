"""Fill the LLM planner cache once (PAID), so the website and experiments replay it for $0.

    python scripts/record_llm_cache.py --confirm-spend [--pairs 30] [--scenario F01] [--max-usd 0.50]

Uses adilnurgg's OpenAI planner from the environment / git-ignored .env (OPENAI_API_KEY, OPENAI_MODEL,
optional OPENAI_PRICE_*, OPENAI_REASONING_EFFORT). Stops at the SpendGuard caps. Appends to
examples/llm_cache/planner_cache.jsonl (situations + the planner's answer; no key, no part data
beyond verdict kinds). Then replays the same run from the cache and prints the hit rate.
"""
import argparse, json, sys
from dataclasses import replace
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from qualityrelay17.api import read_dotenv
from qualityrelay17.collective.llm_planner import openai_planner_from_env
from qualityrelay17.sim.engine import Factory, calibrate_part_model
from qualityrelay17.sim.llm_cache import CachingPlanner
from qualityrelay17.sim.scenarios import BY_ID
import os

ap = argparse.ArgumentParser()
ap.add_argument('--confirm-spend', action='store_true'); ap.add_argument('--pairs', type=int, default=30)
ap.add_argument('--scenario', default='F01'); ap.add_argument('--seed', type=int, default=0); ap.add_argument('--max-usd', default='0.50')
a = ap.parse_args()
if not a.confirm_spend:
    sys.exit('This makes paid OpenAI calls. Re-run with --confirm-spend.')
env = {**read_dotenv(), **{k: v for k, v in os.environ.items() if v}, 'LLM_MAX_USD_PER_RUN': a.max_usd, 'LLM_MAX_CALLS_PER_RUN': '400'}
inner, status = openai_planner_from_env(env)
if inner is None:
    sys.exit(f'OpenAI planner not configured: {status}')
m = calibrate_part_model()
sc = replace(BY_ID[a.scenario], n_pairs=a.pairs, cameras=('phone',))  # website configuration: one phone camera per lane
rec = CachingPlanner(inner, mode='record')
f = Factory(sc, a.seed, 'bayes', 'optimized', model=m, reprint=True, lane_by_kind=True, agents=True, planner=rec); f.run()
print('record:', json.dumps(rec.describe()))
rep = CachingPlanner(mode='replay', model=rec.model)
g = Factory(sc, a.seed, 'bayes', 'optimized', model=m, reprint=True, lane_by_kind=True, agents=True, planner=rep); g.run()
print('replay:', json.dumps(rep.describe()))
print('cache file:', rec.path)
