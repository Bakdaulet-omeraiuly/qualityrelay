"""Belief state and next-inspection proposal behind ONE small interface.

This is the Bakdaulet boundary: the collaboration engine only ever calls `update()` and
`propose()`. The reference implementation below uses vder.posterior / vder.action_scores with
either calibration.Likelihoods (from_likelihoods) or clearly-labelled illustrative numbers.
Replacing it with a calibrated, two-axis, properly cost-accounted model (task board SCI-06)
does not touch the protocol, the ACL, the trace, or the API.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Protocol
from ..vder import posterior, action_scores, Inspection

POSITIVE_VERDICTS = {'suspect', 'fail', 'nonconforming'}
NEGATIVE_VERDICTS = {'clear', 'verified', 'pass'}


class BeliefModel(Protocol):
    def update(self, belief: float, summary: dict) -> tuple[float, str]: ...
    def propose(self, belief: float, *, budget: float) -> dict: ...


@dataclass
class ReferenceBelief:
    """P(defect) on one axis. likelihoods: evidence kind -> (sensitivity, specificity)."""
    likelihoods: dict[str, tuple[float, float]]
    prior: float
    source: str = 'illustrative'
    candidates: list[Inspection] = field(default_factory=lambda: [
        Inspection('CALIPER_RETAKE', 0.98, 0.98, 0.5), Inspection('PI_RECAPTURE', 0.85, 0.85, 0.1),
        Inspection('PHONE_RECAPTURE', 0.80, 0.80, 0.1)])
    false_pass_cost: float = 100.0
    false_hold_cost: float = 3.0

    def update(self, belief: float, summary: dict) -> tuple[float, str]:
        """Returns (new_belief, note). Only VERIFIED, new-source, calibrated, decisive summaries move it."""
        if summary.get('verification_status') != 'VERIFIED' or not summary.get('new_source'):
            return belief, 'ignored: not a verified new source'
        if summary['kind'] not in self.likelihoods:
            return belief, f'ignored: no likelihood model for {summary["kind"]}'
        if summary['kind'] in ('PHONE_IMAGE', 'PI_IMAGE', 'CAD_IMAGE') and not summary.get('calibration_id'):
            return belief, 'ignored: uncalibrated visual evidence cannot update belief'
        v = summary.get('verdict')
        if v in POSITIVE_VERDICTS: positive = True
        elif v in NEGATIVE_VERDICTS: positive = False
        else: return belief, f'ignored: verdict {v!r} is not an observation (recapture needed)'
        sens, spec = self.likelihoods[summary['kind']]
        return posterior(belief, sens, spec, positive), f'{summary["kind"]} {v} (sens={sens}, spec={spec}, {self.source})'

    def propose(self, belief: float, *, budget: float) -> dict:
        rows = action_scores(belief, self.candidates, false_pass_cost=self.false_pass_cost, false_hold_cost=self.false_hold_cost)
        affordable = [r for r in rows if r['inspection_cost'] <= budget]
        chosen = min(affordable, key=lambda r: r['expected_loss']) if affordable else {'name': 'NO_ACTION'}
        baseline = next(r for r in rows if r['name'] == 'NO_ACTION')['expected_loss']
        return {'chosen': chosen['name'], 'net_voi': round(baseline - chosen.get('expected_loss', baseline), 6),
                'candidates': [{**r, 'net_voi': round(baseline - r['expected_loss'], 6)} for r in rows],
                'budget': budget, 'likelihood_source': self.source}


DEFAULT_LIKELIHOODS = {'PHONE_IMAGE': (0.80, 0.80), 'PI_IMAGE': (0.85, 0.85), 'CALIPER': (0.98, 0.98), 'CAD_IMAGE': (0.70, 0.90)}


def illustrative(prior: float = 0.08) -> ReferenceBelief:
    """Numbers for explaining the interface only (plan section 7.4 footnote). Never on a slide."""
    return ReferenceBelief(dict(DEFAULT_LIKELIHOODS), prior, source='ILLUSTRATIVE_NOT_CALIBRATED')


def from_likelihoods(lk) -> ReferenceBelief:
    """Adapter for calibration.Likelihoods (Bakdaulet's estimates). Surface axis only here."""
    return ReferenceBelief({'PHONE_IMAGE': (lk.phone_sens, lk.phone_spec), 'PI_IMAGE': (lk.pi_sens, lk.pi_spec),
                            'CALIPER': (lk.caliper_sens, lk.caliper_spec)}, lk.surface_prior,
                           source=f'calibration:{lk.calibration_id}')
