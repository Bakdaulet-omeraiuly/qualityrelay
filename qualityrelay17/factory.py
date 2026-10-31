"""Reproducible process-level factory simulation. Illustrative synthetic parameters ONLY."""
from __future__ import annotations
import random, math

def seeded_scenario(n=1000, seed=2026, *, process_shift_mm=0.10, camera_noise=0.04, network_outage=0.05, shared_camera_noise=0.0, use_reinspection=True):
    if n<1:raise ValueError('n >= 1')
    if any(not 0<=x<=1 for x in (camera_noise,network_outage,shared_camera_noise)):raise ValueError('invalid probability')
    rng=random.Random(seed)
    # Draw common latent variables once. Competing policies MUST use exact same records.
    rows=[]
    for i in range(n):
        slot=rng.gauss(21.0-0.5*process_shift_mm,0.12)
        tab=rng.gauss(20.0+process_shift_mm,0.12)
        surface_defect=rng.random()<0.06
        safe=(slot-tab>=0.5 and not surface_defect)
        common_flip=rng.random()<shared_camera_noise
        phone=(bool(surface_defect ^ (rng.random()<camera_noise) ^ common_flip))
        pi=(bool(surface_defect ^ (rng.random()<camera_noise) ^ common_flip))
        measured_clearance=(slot-tab)+rng.gauss(0,0.05)  # synthetic caliper noise, *not* oracle ground truth
        network_down=rng.random()<network_outage
        rows.append(dict(specimen_id=f'V-{i:05d}', slot=slot,tab=tab,surface_defect=surface_defect,
                         safe=safe, phone_suspect=phone,pi_suspect=pi,network_down=network_down,
                         measured_clearance=measured_clearance, true_clearance=slot-tab, shared_camera_flip=common_flip,
                         origin='SIMULATED'))
    return rows

def _voi_driven_rows(rows):
    """Wire vder.action_scores into the comparator so H2 (PRIOR_ART_AND_RESEARCH_QUESTIONS.md:
    'V-DER/CAIR reduces excess inspection time at matched unsafe-pass tolerance vs fixed rule')
    is actually testable instead of only documented.

    Sensitivity/specificity/cost below are illustrative placeholders -- same caveat as
    vder.py itself ('reference implementation, NOT a newly proven algorithm'). The prior
    nudge from phone/pi suspect votes is a crude heuristic, not a calibrated likelihood;
    replace both before trusting this for anything beyond A/B comparison in simulation.
    """
    from .vder import Inspection, action_scores
    actions = (
        Inspection('phone_recapture', sensitivity=0.75, specificity=0.85, cost=1.0),
        Inspection('pi_recapture', sensitivity=0.80, specificity=0.88, cost=1.5),
        Inspection('caliper_retake', sensitivity=0.95, specificity=0.97, cost=3.0),
    )
    results = []
    for r in rows:
        suspect_votes = int(r['phone_suspect']) + int(r['pi_suspect'])
        prior = min(0.95, 0.03 * (4 ** suspect_votes))
        ranked = action_scores(prior, actions)
        best = ranked[0]
        checks = 1 + (1 if best['name'] != 'NO_ACTION' else 0)
        # Clearance is already-available/free evidence in this synthetic world (the other
        # three policies use it unconditionally) -- VOI only decides whether to ALSO spend
        # on extra camera evidence, it never gets to withhold evidence the baselines get
        # for free, or this stops being an apples-to-apples comparison.
        hold = r['measured_clearance'] < 0.5
        if best['name'] == 'phone_recapture':
            hold = hold or bool(r['phone_suspect'])
        elif best['name'] == 'pi_recapture':
            hold = hold or bool(r['pi_suspect'])
        elif best['name'] == 'NO_ACTION':
            hold = hold or suspect_votes > 0  # fall back to the free camera votes already on hand
        # 'caliper_retake' adds no new signal here: the synthetic world has no separate
        # retake draw, so it is scored by vder but changes nothing beyond the free reading.
        outcome = 'hold' if hold else ('pass' if r['safe'] else 'escaped_defect')
        results.append(dict(specimen_id=r['specimen_id'], outcome=outcome, inspections=checks,
                             unsafe_pass=int(not hold and not r['safe']), chosen_action=best['name']))
    return results


def _collective_fusion_rows(rows, *, phone_sens=0.75, phone_spec=0.85, pi_sens=0.80, pi_spec=0.88,
                             caliper_sens=0.95, caliper_spec=0.97, prior_defect_rate=0.06,
                             false_pass_cost=100., false_hold_cost=3.):
    """Collective-capability reference: fuse THREE independently-sourced votes (phone,
    pi, caliper) into one posterior via sequential Bayes updates (vder.posterior), instead
    of (a) trusting one source alone like phone_only/metrology_only, or (b) the naive
    OR-of-flags rule conservative_rules/safe_mesh_reference use. Same three evidence
    sources are read in every policy here -- this changes only how their votes are
    combined, so it is a fair same-budget comparison, not an extra-inspection trick.

    The hold threshold is the Bayes-optimal break-even point for the SAME false_pass_cost/
    false_hold_cost ratio vder.risk() already uses elsewhere, not an arbitrary cutoff.

    Important correctness note (found by running this, not assumed): phone and pi are both
    noisy observations of the SAME latent variable (`surface_defect` in seeded_scenario) --
    fusing them is genuine collective reasoning about one question. The caliper measures a
    DIFFERENT, independent fault axis (dimensional clearance) and carries zero information
    about surface defects. An earlier draft fused all three into one posterior, which let a
    clean caliper reading wrongly explain away real camera suspicion about an unrelated
    surface defect -- mathematically incoherent, not just a tuning issue. Fixed: two
    separate posteriors (surface, from phone+pi; dimensional, from caliper), hold if either
    crosses threshold.

    Modeling assumption to stress-test, not hide: phone/pi fusion assumes their errors are
    conditionally independent given the true state. factory.py's own `shared_camera_noise`
    parameter exists specifically to inject correlated camera errors -- re-run this policy
    with shared_camera_noise > 0 before trusting the fused result; correlated cameras break
    the independence assumption sequential Bayes updating relies on.
    """
    from .vder import posterior
    threshold = false_hold_cost / (false_pass_cost + false_hold_cost)
    results = []
    for r in rows:
        surface_p = posterior(prior_defect_rate, phone_sens, phone_spec, bool(r['phone_suspect']))
        surface_p = posterior(surface_p, pi_sens, pi_spec, bool(r['pi_suspect']))
        dimensional_p = posterior(prior_defect_rate, caliper_sens, caliper_spec, r['measured_clearance'] < 0.5)
        hold = surface_p >= threshold or dimensional_p >= threshold
        outcome = 'hold' if hold else ('pass' if r['safe'] else 'escaped_defect')
        results.append(dict(specimen_id=r['specimen_id'], outcome=outcome, inspections=3,
                             unsafe_pass=int(not hold and not r['safe']),
                             surface_posterior=round(surface_p, 6), dimensional_posterior=round(dimensional_p, 6)))
    return results


def _structured_request_rows(rows, *, phone_sens=0.75, phone_spec=0.85, pi_sens=0.80, pi_spec=0.88,
                              caliper_sens=0.95, caliper_spec=0.97, prior_defect_rate=0.06,
                              false_pass_cost=100., false_hold_cost=3., request_cost=0.3,
                              indecisive_margin=0.03):
    """Smallest honest slice of Bakdaulet's 17.1 evidence-request protocol
    (docs/research/COLLECTIVE_17_1_BAKDAULET.md) -- Gate A, one function, not the full
    qualityrelay17/collective/ package, until this minimal version is validated.

    Unlike every other policy in this file, Pi evidence is NOT read for free. The Quality
    role starts with phone + caliper only (real information asymmetry -- criterion 1 of
    Bakdaulet's 'real collaboration, not theater' test). It issues exactly one
    REQUEST_EVIDENCE for Pi, paying request_cost, ONLY when the phone-only surface
    posterior falls in an indecisive band around the Bayes-optimal threshold (criterion 2:
    a TARGETED request, not 'ask everyone everything'). Requesting Pi evidence is always a
    genuinely new, independently-sourced observation already in this data model (criterion
    3). decision_flip flags whether the new evidence actually changed the surface
    disposition (criterion 4). Compare this policy's cost/safety against collective_fusion
    (has Pi for free, no request, no request_cost) to see what asking is actually worth
    versus simply always having the answer (criterion 5 -- this IS that control).
    """
    from .vder import posterior
    # Honesty note found by running this, not assumed beforehand: phone_suspect is a
    # single boolean sensor, so phone_only_p only ever takes two values (flagged /
    # not-flagged) -- the indecisive band either catches the whole not-flagged cluster or
    # none of it, there is no graded "slightly uncertain" middle with a one-bit sensor.
    # A continuous confidence score would make 'selective request' a real spectrum instead
    # of this all-or-nothing cluster split; that is a concrete upgrade for whoever builds
    # the full qualityrelay17/collective/ package, not hidden here.
    threshold = false_hold_cost / (false_pass_cost + false_hold_cost)
    results = []
    for r in rows:
        dimensional_p = posterior(prior_defect_rate, caliper_sens, caliper_spec, r['measured_clearance'] < 0.5)
        phone_only_p = posterior(prior_defect_rate, phone_sens, phone_spec, bool(r['phone_suspect']))

        requested = abs(phone_only_p - threshold) <= indecisive_margin
        checks = 2  # phone + caliper are always read
        if requested:
            checks += 1
            fused_surface_p = posterior(phone_only_p, pi_sens, pi_spec, bool(r['pi_suspect']))
        else:
            fused_surface_p = phone_only_p

        hold = fused_surface_p >= threshold or dimensional_p >= threshold
        decided_without_request = phone_only_p >= threshold or dimensional_p >= threshold
        outcome = 'hold' if hold else ('pass' if r['safe'] else 'escaped_defect')
        results.append(dict(
            specimen_id=r['specimen_id'], outcome=outcome, inspections=checks,
            unsafe_pass=int(not hold and not r['safe']),
            requested_pi_evidence=requested,
            decision_flip_from_request=bool(requested and hold != decided_without_request),
            request_cost_paid=round(request_cost, 4) if requested else 0.0,
        ))
    return results


def apply_policy(rows,policy:str, costs=None):
    """Independent, comparable preset dispositions; not learned/calibrated agents,
    except 'voi_driven' which calls vder.action_scores per specimen, and
    'collective_fusion' which calls vder.posterior three times per specimen -- both are
    reference wirings, not calibrated production policies."""
    if policy == 'voi_driven':
        return _voi_driven_rows(rows)
    if policy == 'collective_fusion':
        return _collective_fusion_rows(rows)
    if policy == 'structured_request_lite':
        return _structured_request_rows(rows)
    results=[]
    for r in rows:
        if policy=='phone_only':
            hold=r['phone_suspect']; checks=1
        elif policy=='metrology_only':
            hold=r['measured_clearance']<0.5;checks=1
        elif policy=='conservative_rules':
            hold=r['phone_suspect'] or r['pi_suspect'] or r['measured_clearance']<0.5 or r['network_down'];checks=3
        elif policy=='safe_mesh_reference':
            # Include extra inspection cost on disagreements; no model superiority implied.
            hold=r['phone_suspect'] or r['pi_suspect'] or r['measured_clearance']<0.5 or r['network_down'];
            checks=3+int(r['phone_suspect']!=r['pi_suspect'])
        else:raise ValueError('unknown policy')
        outcome='hold' if hold else ('pass' if r['safe'] else 'escaped_defect')
        results.append(dict(specimen_id=r['specimen_id'],outcome=outcome,inspections=checks,unsafe_pass=int(not hold and not r['safe'])))
    return results

def compare_policies(n=1000,seed=2026,**kwargs):
    from .economics import Costs, calculate
    rows=seeded_scenario(n=n,seed=seed,**kwargs)
    out={'origin':'SIMULATED','generator':'seeded_scenario_v1','seed':seed,'n':n,'policies':{}}
    for p in ('phone_only','metrology_only','conservative_rules','safe_mesh_reference','voi_driven','collective_fusion'):
        classified=apply_policy(rows,p)
        out['policies'][p]={'unsafe_pass':sum(x['unsafe_pass'] for x in classified),
                            'hold':sum(x['outcome']=='hold' for x in classified),
                            **calculate(classified,Costs())}
    return out
