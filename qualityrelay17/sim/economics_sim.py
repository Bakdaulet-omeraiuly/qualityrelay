"""SIM-04: factory economics, ROI and payback with disclosed assumptions and uncertainty.

Every input is a separately named ILLUSTRATIVE ASSUMPTION with a (low, mode, high) range; the
Monte Carlo draws them jointly (triangular) and pairs them with engine seeds, so an interval
reflects BOTH assumption uncertainty and simulated-lot variability. Output is labelled
SCENARIO_OUTCOME -- it is never a measured or proven factory saving.

Baseline = 'rules' + FIFO pairing, no QualityRelay platform costs. QualityRelay = 'bayes' +
optimised pairing + platform opex (cloud/LLM per decision, maintenance) + capex (edge kit,
integration labour) amortised over its life.
"""
from __future__ import annotations
from random import Random
from statistics import mean

# name: (low, mode, high, unit, note)
ASSUMPTIONS = {
    'margin_per_good_assembly': (3.0, 6.0, 10.0, 'cu/unit', 'sale price minus material of a good Slot/Tab assembly'),
    'material_per_part': (0.25, 0.40, 0.60, 'cu/part', 'PLA + energy per printed part'),
    'labour_per_operator_hour': (20.0, 30.0, 45.0, 'cu/h', 'metrology/review/rework operator'),
    'printer_cost_per_busy_hour': (0.3, 0.5, 1.0, 'cu/h', 'energy + wear per printer while printing'),
    'hold_carrying_per_part_hour': (0.02, 0.05, 0.15, 'cu/part-h', 'quarantine floor space, handling, WIP capital'),
    'scrap_disposal_per_part': (0.05, 0.10, 0.20, 'cu/part', ''),
    'escape_cost': (80.0, 150.0, 400.0, 'cu/escape', 'warranty / customer return; = economics.Costs.escaped_defect mode'),
    'downtime_cost_per_hour': (10.0, 20.0, 40.0, 'cu/h', 'lost-production overhead while a station is under repair'),
    'transport_per_part': (0.01, 0.02, 0.05, 'cu/part', 'intra-site; inter-site handled per scenario'),
    'cloud_llm_per_decision': (0.0, 0.002, 0.02, 'cu/decision', 'QR platform; 0 for the deterministic mock'),
    'platform_maintenance_per_hour': (0.5, 1.5, 4.0, 'cu/h', 'QR monitoring, model upkeep'),
    'platform_capex': (1500.0, 3000.0, 8000.0, 'cu', 'Pi + Hailo + cameras + fixtures'),
    'integration_labour': (2000.0, 6000.0, 15000.0, 'cu', 'one-time site integration (12 doc: count it in ROI)'),
    'equipment_life_years': (1.5, 2.5, 4.0, 'years', 'amortisation horizon for capex'),
    'operating_hours_per_year': (2000.0, 4000.0, 6000.0, 'h/year', '1-3 shifts'),
}


def modes():
    return {k: v[1] for k, v in ASSUMPTIONS.items()}


def draw(rng: Random):
    return {k: rng.triangular(lo, hi, md) for k, (lo, md, hi, _u, _n) in ASSUMPTIONS.items()}


def run_cost(summary: dict, a: dict, *, platform: bool, printers: int = 4, inter_site_per_part: float = 0.0) -> dict:
    """Itemised cost and profit of ONE engine run under assumption set `a`."""
    h = summary['makespan_s'] / 3600.0
    parts = summary['parts']
    items = dict(
        material=parts * a['material_per_part'],
        operator_labour=summary['operator_seconds'] / 3600.0 * a['labour_per_operator_hour'],
        printer_time=summary['utilization'].get('site-A:printer', 0.0) * printers * h * a['printer_cost_per_busy_hour']
        if 'site-A:printer' in summary['utilization'] else
        sum(u for k, u in summary['utilization'].items() if k.endswith(':printer')) * 2 * h * a['printer_cost_per_busy_hour'],
        hold_inventory=summary['hold_inventory_part_hours'] * a['hold_carrying_per_part_hour'],
        scrap_disposal=summary['scrapped_parts'] * a['scrap_disposal_per_part'],
        escapes=summary['escape_cost_units'] * a['escape_cost'],
        downtime=summary['downtime_s'] / 3600.0 * a['downtime_cost_per_hour'],
        transport=parts * (a['transport_per_part'] + inter_site_per_part),
    )
    if platform:
        items['cloud_llm'] = summary['pair_decisions'] * a['cloud_llm_per_decision']
        items['platform_maintenance'] = h * a['platform_maintenance_per_hour']
        items['platform_capex_amortised'] = h * (a['platform_capex'] + a['integration_labour']) / (
            a['equipment_life_years'] * a['operating_hours_per_year'])
    total = sum(items.values())
    revenue = summary['shipped_good'] * a['margin_per_good_assembly']
    return dict(items={k: round(v, 4) for k, v in items.items()}, total_cost=total, margin=revenue,
                profit=revenue - total, hours=h, profit_per_hour=(revenue - total) / h,
                cost_per_good_unit=total / summary['shipped_good'] if summary['shipped_good'] else None)


def roi_monte_carlo(baseline_runs: list[dict], qr_runs: list[dict], *, draws=2000, seed=4242, printers=4):
    """Paired by seed. Returns percentile intervals of Δprofit/h, annual Δprofit, ROI, payback."""
    if [r['seed'] for r in baseline_runs] != [r['seed'] for r in qr_runs]:
        raise ValueError('runs must be paired by seed')
    rng = Random(seed)
    dph, annual, roi, payback = [], [], [], []
    for _ in range(draws):
        a = draw(rng)
        i = rng.randrange(len(baseline_runs))
        b = run_cost(baseline_runs[i], a, platform=False, printers=printers)
        q = run_cost(qr_runs[i], a, platform=True, printers=printers)
        d = q['profit_per_hour'] - b['profit_per_hour']   # platform capex already amortised inside q
        dph.append(d)
        yearly = d * a['operating_hours_per_year']
        annual.append(yearly)
        invest = a['platform_capex'] + a['integration_labour']
        # ROI over the equipment life on the gross (pre-amortisation) gain
        gross = (d + (a['platform_capex'] + a['integration_labour']) / (a['equipment_life_years'] * a['operating_hours_per_year'])) \
            * a['operating_hours_per_year']
        roi.append((gross * a['equipment_life_years'] - invest) / invest)
        payback.append(12 * invest / gross if gross > 0 else float('inf'))

    def pct(xs):
        ys = sorted(xs)
        f = lambda q: ys[min(len(ys) - 1, int(q * len(ys)))]  # noqa: E731
        return dict(p05=f(0.05), p50=f(0.50), p95=f(0.95), mean=mean([y for y in ys if y != float('inf')] or [0]))

    point_b = [run_cost(r, modes(), platform=False, printers=printers) for r in baseline_runs]
    point_q = [run_cost(r, modes(), platform=True, printers=printers) for r in qr_runs]
    return dict(
        status='SCENARIO_OUTCOME_NOT_MEASURED_SAVINGS', draws=draws, seeds=[r['seed'] for r in baseline_runs],
        delta_profit_per_hour=pct(dph), annual_delta_profit=pct(annual), roi_over_life=pct(roi),
        payback_months=pct(payback), p_payback_within_12_months=sum(p <= 12 for p in payback) / draws,
        p_qr_worse=sum(d < 0 for d in dph) / draws,
        point_estimate_at_modes=dict(
            baseline=dict(profit_per_hour=mean(x['profit_per_hour'] for x in point_b),
                          cost_per_good_unit=mean(x['cost_per_good_unit'] for x in point_b),
                          items=_mean_items(point_b)),
            qualityrelay=dict(profit_per_hour=mean(x['profit_per_hour'] for x in point_q),
                              cost_per_good_unit=mean(x['cost_per_good_unit'] for x in point_q),
                              items=_mean_items(point_q))),
        assumptions={k: dict(low=v[0], mode=v[1], high=v[2], unit=v[3], note=v[4], status='ILLUSTRATIVE_ASSUMPTION')
                     for k, v in ASSUMPTIONS.items()})


def _mean_items(runs):
    keys = runs[0]['items'].keys()
    return {k: round(mean(r['items'][k] for r in runs), 3) for k in keys}


def derived_hold_cost(a=None) -> dict:
    """What one HOLD actually costs in this factory under assumption set `a`: review labour +
    quarantine carrying for the review duration. Lost throughput when Review saturates is NOT
    in this number -- it shows up in the engine's makespan (see the hold_all runs)."""
    from .scenarios import STATION_S
    a = a or modes()
    labour = STATION_S['review'] / 3600 * a['labour_per_operator_hour']
    carrying = STATION_S['review'] / 3600 * a['hold_carrying_per_part_hour']
    return dict(review_labour=round(labour, 4), carrying=round(carrying, 4), total=round(labour + carrying, 4),
                note='per held part, excluding queueing delay and lost throughput')
