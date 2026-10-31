#!/usr/bin/env python
"""Gate B: run the LLM policies (B7_llm, B7_llm-specialist_roles) in Bakdaulet's Gate-A
environment, paired against the deterministic baselines on the SAME simulated cases.

  python scripts/run_llm_gate_b.py --provider dry-run                       # no key, no cost: plumbing check
  python scripts/run_llm_gate_b.py --provider nebius --scenarios S13 --n 50 --confirm-spend --max-usd 1.0

Keys and models come from the environment or the git-ignored .env (NEBIUS_API_KEY / NEBIUS_MODEL,
OPENAI_API_KEY / OPENAI_MODEL). A live run refuses to start without --confirm-spend and runs under a
hard SpendGuard (calls, tokens, USD). If the guard or the provider stops the planner, the parts that
follow are decided on held evidence, the run is marked INCOMPLETE_PLANNER_STOPPED and the exit code is 2.

Writes examples/results/llm_gate_b/<provider>-<model>-<UTC>/: <SID>.json, summary.csv, manifest.json.
Everything is origin=SIMULATED. A few dozen parts per scenario is a smoke-scale comparison,
not the registered 30x1000 grid; report it with its n.
"""
from __future__ import annotations
import argparse, csv, json, os, platform, re, subprocess, sys, time
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qualityrelay17.collective.llm_planner import PROVIDERS, OpenAICompatiblePlanner, SpendGuard  # noqa: E402
from qualityrelay17.experiments.belief import calibrate_belief_model  # noqa: E402
from qualityrelay17.experiments.collective_baselines import POLICIES  # noqa: E402
from qualityrelay17.experiments.collective_eval import run_scenario  # noqa: E402
from qualityrelay17.experiments.llm_policies import (make_llm_policy, LLM_CONTRASTS, POLICY_NAMES, PROMPT_SHA256,  # noqa: E402
                                                    MAX_INVALID)
from qualityrelay17.experiments.scenarios import BY_ID  # noqa: E402

BASELINES = ('B0_rules', 'B1_single_agent_fixed', 'B5_structured_fixed', 'B6_single_agent_voi', 'B7_safe_mesh_voi')


class DryRunClient:
    """Scripted stand-in for a chat-completions client, so the whole pipeline runs with no key:
    caliper first, then whatever the safety gate says is missing, then finish. Not a model;
    its numbers mean nothing beyond 'the plumbing works'."""
    def __init__(self):
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, *, messages, **_):
        s = json.loads(messages[-1]['content'])
        avail = {a['kind']: a['owner'] for a in s['available']}
        held = {e['kind'] for e in s['evidence'] if e['counted']}
        want = next((k for k in ('caliper', 'phone', 'pi') if k in avail and k not in held), None)
        if want and (want == 'caliper' or s['belief']['safety_gate_reasons']):
            name, args = 'request_evidence', {'kind': want, 'recipient_role': avail[want], 'reason_code': 'DRY_RUN'}
        else:
            name, args = 'finish', {'reason': 'dry run'}
        call = NS(id='dry', function=NS(name=name, arguments=json.dumps(args)))
        return NS(choices=[NS(message=NS(content=None, tool_calls=[call]))], usage=NS(prompt_tokens=0, completion_tokens=0))


def _env() -> dict:
    from qualityrelay17.api import read_dotenv
    return {**read_dotenv(), **{k: v for k, v in os.environ.items() if v}}


def _git(*args):
    try:
        return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return 'UNKNOWN'


def _llm_summary(recs: list[dict]) -> dict:
    n = len(recs)
    usd = [r['llm_usd'] for r in recs]
    return dict(parts=n,
                llm_calls_per_part=sum(r['compute_calls'] for r in recs) / n,
                prompt_tokens_per_part=sum(r['llm_prompt_tokens'] for r in recs) / n,
                completion_tokens_per_part=sum(r['llm_completion_tokens'] for r in recs) / n,
                usd_total=None if any(u is None for u in usd) else round(sum(usd), 6),
                mean_llm_latency_ms_per_part=sum(r['llm_latency_ms'] for r in recs) / n,
                invalid_proposals_per_part=sum(r['invalid_proposals'] for r in recs) / n,
                parts_with_planner_stopped=sum(r['planner_stopped'] for r in recs),
                peer_requests_per_part=sum(r['peer_requests'] for r in recs) / n)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--provider', choices=sorted(PROVIDERS) + ['dry-run'], required=True)
    ap.add_argument('--scenarios', default='S01,S13', help='comma-separated Gate-A ids (S01..S14, X01..X03)')
    ap.add_argument('--seeds', type=int, default=1, help='lots per scenario (seeds 0..k-1)')
    ap.add_argument('--n', type=int, default=30, help='parts per lot')
    ap.add_argument('--variants', default='role,generic', help='role (B7_llm) and/or generic (B7_llm-specialist_roles)')
    ap.add_argument('--max-calls', type=int, default=None, help='hard cap on LLM calls for the whole run (default: worst case)')
    ap.add_argument('--max-tokens', type=int, default=2_000_000)
    ap.add_argument('--max-usd', type=float, default=1.0, help='hard USD cap; only enforced when prices are configured')
    ap.add_argument('--confirm-spend', action='store_true', help='required for a live provider')
    ap.add_argument('--keep-traces', type=int, default=6)
    ap.add_argument('--out', default=None)
    a = ap.parse_args()

    scenarios = [BY_ID[s.strip()] for s in a.scenarios.split(',') if s.strip()]
    variants = [v.strip() for v in a.variants.split(',') if v.strip()]
    bad = [v for v in variants if v not in POLICY_NAMES]
    if bad: ap.error(f'unknown variant(s) {bad}; use role and/or generic')
    parts = a.seeds * a.n * len(scenarios) * len(variants)
    worst = sum(a.seeds * a.n * len(variants) * (sc.budget + MAX_INVALID + 3) for sc in scenarios)
    print(f'{len(scenarios)} scenario(s) x {a.seeds} lot(s) x {a.n} parts x {len(variants)} LLM variant(s) = {parts} LLM-decided parts; '
          f'worst case {worst} LLM calls (typically 2-4 per part)')

    if a.provider == 'dry-run':
        planner = OpenAICompatiblePlanner(client=DryRunClient(), model='scripted', provider='dry-run', tool_choice='auto')
    else:
        planner, status = PROVIDERS[a.provider](_env())
        if planner is None:
            sys.exit(f'{a.provider} NOT_CONFIGURED: missing {status["missing"]} (set them in .env or the environment)')
        if not a.confirm_spend:
            sys.exit(f'live run on {planner.name} makes up to {worst} paid calls; re-run with --confirm-spend')
        if planner.price_in is None:
            print('WARNING: no per-token prices configured -- tokens are logged, USD is not, and --max-usd cannot be enforced')
    planner.guard = SpendGuard(max_calls=a.max_calls or worst, max_total_tokens=a.max_tokens, max_usd=a.max_usd)

    policies = {k: POLICIES[k] for k in BASELINES}
    collected = {POLICY_NAMES[v]: [] for v in variants}
    for v in variants:
        inner = make_llm_policy(planner, v)
        def policy(env, sc, model, _inner=inner, _sink=collected[POLICY_NAMES[v]]):
            rec = _inner(env, sc, model); _sink.append(rec); return rec
        policies[POLICY_NAMES[v]] = policy
    contrasts = tuple(c for c in LLM_CONTRASTS if c[0] in policies and c[1] in policies)

    slug = re.sub(r'[^A-Za-z0-9._-]+', '_', f'{planner.provider}-{planner.model}')
    stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
    out = Path(a.out or ROOT / 'examples' / 'results' / 'llm_gate_b' / f'{slug}-{stamp}')
    out.mkdir(parents=True, exist_ok=True)
    commit, dirty = _git('rev-parse', 'HEAD'), bool(_git('status', '--porcelain'))
    model = calibrate_belief_model()
    started = time.time()
    rows, llm_blocks = [], {}
    for sc in scenarios:
        for sink in collected.values(): sink.clear()
        res, traces = run_scenario(sc, model, seeds=range(a.seeds), n=a.n, keep_traces=a.keep_traces,
                                   policies=policies, contrasts=contrasts)
        res['llm'] = llm_blocks[sc.sid] = {name: _llm_summary(recs) for name, recs in collected.items()}
        res['traces'] = traces
        (out / f'{sc.sid}.json').write_text(json.dumps(res, indent=1, sort_keys=True, default=str))
        for pol, s in res['summary'].items():
            rows.append(dict(scenario=sc.sid, policy=pol, unsafe_pass_rate=s['unsafe_pass_rate'],
                             released_good_rate=s['released_good_rate'], hold_rate=s['hold_rate'],
                             mean_inspections=s['mean_inspections'], mean_peer_requests=s['mean_peer_requests'],
                             cost_per_unit=s['cost_per_unit'],
                             **{k: v for k, v in res['llm'].get(pol, {}).items() if k != 'parts'}))
        print(f"{sc.sid}: " + ', '.join(f"{p} unsafe={s['unsafe_pass_rate']:.4f} good={s['released_good_rate']:.3f} "
                                        f"req/part={s['mean_peer_requests']:.2f}" for p, s in res['summary'].items()))

    fields = sorted({k for r in rows for k in r}, key=lambda k: (k not in ('scenario', 'policy'), k))
    with open(out / 'summary.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    stopped = sum(b['parts_with_planner_stopped'] for blk in llm_blocks.values() for b in blk.values())
    manifest = dict(origin='SIMULATED', gate='B (LLM backbone), smoke scale', dry_run=a.provider == 'dry-run',
                    provider=planner.provider, model=planner.model, tool_choice=planner.tool_choice, create_kwargs=planner.extra,
                    temperature=planner.temperature, prompt_sha256={POLICY_NAMES[v]: PROMPT_SHA256[v] for v in variants},
                    git_commit=commit, dirty_before_run=dirty, python=platform.python_version(),
                    started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started)), runtime_s=round(time.time() - started, 1),
                    scenarios=[sc.sid for sc in scenarios], seeds=list(range(a.seeds)), n_per_seed=a.n,
                    baselines=list(BASELINES), llm_policies=list(collected), spend=planner.guard.summary(),
                    completeness='INCOMPLETE_PLANNER_STOPPED' if stopped else 'COMPLETE', parts_with_planner_stopped=stopped)
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=1, sort_keys=True))
    print(f"{manifest['completeness']}; spend {planner.guard.summary()}; wrote {out}")
    sys.exit(2 if stopped else 0)


if __name__ == '__main__':
    main()
