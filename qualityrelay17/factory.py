"""Reproducible process-level factory simulation. Illustrative synthetic parameters ONLY.

31 Oct (Bakdaulet, scientific-engine owner): posterior-based policies now take their
likelihoods from `calibration.estimate_likelihoods` (held-out seeds) and their loss scale
from the same `economics.Costs` the benchmark grades with; `voi_driven` buys genuinely fresh
observations drawn from a second RNG stream (primary 17.0 columns are byte-identical --
see tests/test_scientific_engine.py). Rationale and registered protocol:
docs/research/PROTOCOL_REGISTRATION_31OCT.md.
"""
from __future__ import annotations
import random
from functools import lru_cache
from .calibration import Likelihoods, estimate_likelihoods
from .economics import Costs

TOLERANCE_MM = 0.5
_FRESH_STREAM_SALT = 0x5F3759DF  # second stream so recapture/retake draws never disturb the 17.0 columns

# The invented 17.0 constants, kept ONLY as the mis-specification ablation (S11 in the
# registration). Never the default.
LIKELIHOODS_PLACEHOLDER_17_0 = Likelihoods(
    phone_sens=0.75, phone_spec=0.85, pi_sens=0.80, pi_spec=0.88, caliper_sens=0.95, caliper_spec=0.97,
    phone_recapture_sens=0.75, phone_recapture_spec=0.85, pi_recapture_sens=0.80, pi_recapture_spec=0.88,
    caliper_retake_sens=0.95, caliper_retake_spec=0.97,
    surface_prior=0.06, dimensional_prior=0.06,
    source='PLACEHOLDER_17_0', calibration_id='placeholder-17.0')

POLICIES = ('phone_only', 'metrology_only', 'conservative_rules', 'safe_mesh_reference',
            'collective_fusion', 'structured_request_lite', 'voi_driven', 'entropy_driven')


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
    # Fresh observations a policy may PAY for. Separate stream -> the columns above are
    # byte-identical to 17.0. A recapture is a new frame of the same part under the same
    # lighting, so it shares the common-mode flip (correlated-camera scenarios therefore also
    # stress the recapture-independence assumption, as 17.1 section 4.3 asks). A caliper
    # retake is an independent reading with the same instrument noise.
    fresh=random.Random(_FRESH_STREAM_SALT ^ (int(seed)*0x9E3779B1))
    for r in rows:
        r['phone_recapture_suspect']=bool(r['surface_defect'] ^ (fresh.random()<camera_noise) ^ r['shared_camera_flip'])
        r['pi_recapture_suspect']=bool(r['surface_defect'] ^ (fresh.random()<camera_noise) ^ r['shared_camera_flip'])
        r['retake_clearance']=r['true_clearance']+fresh.gauss(0,0.05)
    return rows


@lru_cache(maxsize=1)
def default_likelihoods() -> Likelihoods:
    """Calibrated on held-out seeds 1000-1009 at the baseline scenario. run_benchmark passes
    an explicit calibration for the scenario it runs; this default is for ad-hoc calls."""
    return estimate_likelihoods()


def _hold_threshold(costs: Costs) -> float:
    # Bayes break-even on the SAME costs the benchmark grades with: hold iff
    # p_unsafe * escaped_defect >= (1 - p_unsafe) * hold.
    return costs.hold / (costs.hold + costs.escaped_defect)


def _free_posteriors(r, lk: Likelihoods):
    from .vder import posterior
    surface_p = posterior(lk.surface_prior, lk.phone_sens, lk.phone_spec, bool(r['phone_suspect']))
    surface_p = posterior(surface_p, lk.pi_sens, lk.pi_spec, bool(r['pi_suspect']))
    dimensional_p = posterior(lk.dimensional_prior, lk.caliper_sens, lk.caliper_spec, r['measured_clearance'] < TOLERANCE_MM)
    return surface_p, dimensional_p


def _collective_fusion_rows(rows, *, lk: Likelihoods, costs: Costs):
    """B3 / 'voi_driven minus the adaptive step': fuse the three FREE votes (phone, Pi,
    caliper) into two axis posteriors via sequential Bayes updates and hold at the Bayes
    break-even on the combined unsafe probability. Same evidence budget as
    conservative_rules (3 inspections); only the combination rule differs.

    Correctness note kept from the first version: phone and Pi observe the SAME latent
    (surface_defect); the caliper observes a DIFFERENT one (clearance). Fusing all three into
    one posterior let a clean caliper reading explain away camera suspicion -- incoherent.
    Two posteriors, combined only at the decision, is the fix.

    Assumes phone/Pi errors are conditionally independent given the true state;
    shared_camera_noise > 0 violates that on purpose -- see the registered grid."""
    from .vder import combined_defect_probability
    threshold = _hold_threshold(costs)
    results = []
    for r in rows:
        surface_p, dimensional_p = _free_posteriors(r, lk)
        p_unsafe = combined_defect_probability(surface_p, dimensional_p)
        hold = p_unsafe >= threshold
        outcome = 'hold' if hold else ('pass' if r['safe'] else 'escaped_defect')
        results.append(dict(specimen_id=r['specimen_id'], outcome=outcome, inspections=3,
                             observations=['phone', 'pi', 'caliper'],
                             unsafe_pass=int(not hold and not r['safe']), p_unsafe=round(p_unsafe, 6),
                             surface_posterior=round(surface_p, 6), dimensional_posterior=round(dimensional_p, 6)))
    return results


def _structured_request_rows(rows, *, lk: Likelihoods, costs: Costs, indecisive_margin=0.03):
    """Smallest honest slice of the 17.1 evidence-request protocol
    (docs/research/COLLECTIVE_17_1_BAKDAULET.md) -- Gate A, one function.

    Unlike every other policy here, Pi evidence is NOT read for free. The Quality role starts
    with phone + caliper only (real information asymmetry -- criterion 1 of section 3.4). It
    issues exactly one REQUEST_EVIDENCE for Pi, paying request_cost, ONLY when the phone-only
    surface posterior falls in an indecisive band around the hold threshold (criterion 2: a
    TARGETED request). The Pi reading is a genuinely independent observation already in the
    data model (criterion 3). decision_flip flags whether it changed the disposition
    (criterion 4). collective_fusion (Pi always free, no request cost) is the no-request
    control (criterion 5).

    Honesty note from running it: phone_suspect is one bit, so phone_only_p takes exactly two
    values -- the band catches the whole not-flagged cluster or none of it. A continuous
    camera confidence would make 'selective request' a real spectrum. Logic unchanged on
    31 Oct except that the threshold and priors now come from Costs / calibration."""
    from .vder import posterior, combined_defect_probability
    threshold = _hold_threshold(costs)
    results = []
    for r in rows:
        dimensional_p = posterior(lk.dimensional_prior, lk.caliper_sens, lk.caliper_spec, r['measured_clearance'] < TOLERANCE_MM)
        phone_only_p = posterior(lk.surface_prior, lk.phone_sens, lk.phone_spec, bool(r['phone_suspect']))
        requested = abs(phone_only_p - threshold) <= indecisive_margin
        observations = ['phone', 'caliper']  # always read
        fused_surface_p = phone_only_p
        if requested:
            observations.append('pi')
            fused_surface_p = posterior(phone_only_p, lk.pi_sens, lk.pi_spec, bool(r['pi_suspect']))
        p_unsafe = combined_defect_probability(fused_surface_p, dimensional_p)
        hold = p_unsafe >= threshold
        decided_without_request = combined_defect_probability(phone_only_p, dimensional_p) >= threshold
        outcome = 'hold' if hold else ('pass' if r['safe'] else 'escaped_defect')
        results.append(dict(
            specimen_id=r['specimen_id'], outcome=outcome, inspections=len(observations),
            observations=observations, unsafe_pass=int(not hold and not r['safe']), p_unsafe=round(p_unsafe, 6),
            requested_pi_evidence=requested, peer_requests=int(requested),
            decision_flip_from_request=bool(requested and hold != decided_without_request),
            # 18.1 SCI-02: this used to be reported but never charged. economics.calculate now
            # bills peer_requests * Costs.peer_request on its own line, separate from the Pi
            # observation itself (which is in `inspections`).
            request_cost_paid=round(costs.peer_request, 4) if requested else 0.0,
        ))
    return results


def _adaptive_rows(rows, *, lk: Likelihoods, costs: Costs, selector: str):
    """B6 (`voi_driven`, selector='expected_loss') and its cost-blind ablation
    (`entropy_driven`, selector='entropy'). Both: read the three free sources exactly like
    collective_fusion, then consider buying AT MOST ONE fresh observation
    (phone_recapture, pi_recapture, caliper_retake) at Costs.inspection each.

    voi_driven acts only if some action's one-step NetVOI is positive, i.e. it is expected to
    lower cost + decision risk on the benchmark's own loss scale (17.1 section 4). The
    entropy variant always buys the action with the largest expected entropy reduction when
    one exists -- the classic information-gain rule, deliberately blind to cost, so the
    difference between the two isolates 'cost awareness' (ablation B7 - cost_awareness).

    Myopic by construction: one look-ahead step, one purchase. Reference wiring, not a
    production planner."""
    from .vder import Inspection, posterior, combined_defect_probability, two_axis_action_scores
    threshold = _hold_threshold(costs)
    surface_actions = (Inspection('phone_recapture', lk.phone_recapture_sens, lk.phone_recapture_spec, costs.inspection),
                       Inspection('pi_recapture', lk.pi_recapture_sens, lk.pi_recapture_spec, costs.inspection))
    dimensional_actions = (Inspection('caliper_retake', lk.caliper_retake_sens, lk.caliper_retake_spec, costs.inspection),)
    results = []
    for r in rows:
        surface_p, dimensional_p = _free_posteriors(r, lk)
        p_before = combined_defect_probability(surface_p, dimensional_p)
        hold_before = p_before >= threshold
        scored = two_axis_action_scores(surface_p, dimensional_p, surface_actions, dimensional_actions,
                                        false_pass_cost=costs.escaped_defect, false_hold_cost=costs.hold)
        if selector == 'expected_loss':
            best = scored[0]  # lowest expected loss; act only if strictly better than NO_ACTION
            if best['net_voi'] <= 0:
                best = next(x for x in scored if x['name'] == 'NO_ACTION')
        elif selector == 'entropy':
            candidates = [x for x in scored if x['name'] != 'NO_ACTION' and x['expected_entropy_reduction'] > 0]
            best = max(candidates, key=lambda x: (x['expected_entropy_reduction'], x['name'])) if candidates \
                else next(x for x in scored if x['name'] == 'NO_ACTION')
        else:
            raise ValueError('unknown selector')
        name = best['name']
        if name == 'phone_recapture':
            surface_p = posterior(surface_p, lk.phone_recapture_sens, lk.phone_recapture_spec, bool(r['phone_recapture_suspect']))
        elif name == 'pi_recapture':
            surface_p = posterior(surface_p, lk.pi_recapture_sens, lk.pi_recapture_spec, bool(r['pi_recapture_suspect']))
        elif name == 'caliper_retake':
            dimensional_p = posterior(dimensional_p, lk.caliper_retake_sens, lk.caliper_retake_spec, r['retake_clearance'] < TOLERANCE_MM)
        p_unsafe = combined_defect_probability(surface_p, dimensional_p)
        hold = p_unsafe >= threshold
        outcome = 'hold' if hold else ('pass' if r['safe'] else 'escaped_defect')
        results.append(dict(specimen_id=r['specimen_id'], outcome=outcome, inspections=3 + int(name != 'NO_ACTION'),
                             observations=['phone', 'pi', 'caliper'] + ([name] if name != 'NO_ACTION' else []),
                             unsafe_pass=int(not hold and not r['safe']), chosen_action=name,
                             p_unsafe=round(p_unsafe, 6), net_voi_of_choice=round(best['net_voi'], 6),
                             decision_flip_from_fresh_evidence=bool(name != 'NO_ACTION' and hold != hold_before)))
    return results


def apply_policy(rows, policy: str, costs: Costs | None = None, likelihoods: Likelihoods | None = None):
    """Independent, comparable preset dispositions on identical rows. Rule policies are
    fixed logic; posterior-based policies (collective_fusion, structured_request_lite,
    voi_driven, entropy_driven) use `likelihoods` (default: held-out calibration at the
    baseline scenario) and derive their hold threshold / loss scale from `costs`
    (default: economics.Costs()). Reference wirings, not calibrated production policies."""
    costs = costs or Costs()
    if policy in ('collective_fusion', 'structured_request_lite', 'voi_driven', 'entropy_driven'):
        lk = likelihoods or default_likelihoods()
        if policy == 'collective_fusion':
            return _collective_fusion_rows(rows, lk=lk, costs=costs)
        if policy == 'structured_request_lite':
            return _structured_request_rows(rows, lk=lk, costs=costs)
        return _adaptive_rows(rows, lk=lk, costs=costs, selector='expected_loss' if policy == 'voi_driven' else 'entropy')
    results=[]
    for r in rows:
        if policy=='phone_only':
            hold=r['phone_suspect']; obs=['phone']
        elif policy=='metrology_only':
            hold=r['measured_clearance']<TOLERANCE_MM; obs=['caliper']
        elif policy=='conservative_rules':
            hold=r['phone_suspect'] or r['pi_suspect'] or r['measured_clearance']<TOLERANCE_MM or r['network_down']; obs=['phone','pi','caliper']
        elif policy=='safe_mesh_reference':
            # Include extra inspection cost on disagreements; no model superiority implied.
            hold=r['phone_suspect'] or r['pi_suspect'] or r['measured_clearance']<TOLERANCE_MM or r['network_down'];
            obs=['phone','pi','caliper']+(['disagreement_review'] if r['phone_suspect']!=r['pi_suspect'] else [])
        else:raise ValueError('unknown policy')
        outcome='hold' if hold else ('pass' if r['safe'] else 'escaped_defect')
        results.append(dict(specimen_id=r['specimen_id'],outcome=outcome,inspections=len(obs),observations=obs,unsafe_pass=int(not hold and not r['safe'])))
    return results


def compare_policies(n=1000,seed=2026,**kwargs):
    from .economics import calculate
    rows=seeded_scenario(n=n,seed=seed,**kwargs)
    lk=default_likelihoods(); costs=Costs()
    out={'origin':'SIMULATED','generator':'seeded_scenario_v2_fresh_stream','seed':seed,'n':n,
         'calibration_id':lk.calibration_id,'policies':{}}
    for p in POLICIES:
        classified=apply_policy(rows,p,costs=costs,likelihoods=lk)
        out['policies'][p]={'unsafe_pass':sum(x['unsafe_pass'] for x in classified),
                            'hold':sum(x['outcome']=='hold' for x in classified),
                            **calculate(classified,costs)}
    return out
