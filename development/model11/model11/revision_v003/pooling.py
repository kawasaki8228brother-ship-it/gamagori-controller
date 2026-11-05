"""Explicit market-weight log-linear pooling; endpoints preserve exact values."""
from __future__ import annotations

from itertools import permutations
import math
import re

DEFAULT_MARKET_WEIGHTS = [0, 0.25, 0.5, 0.75, 0.9, 1.0]
_TICKET = re.compile(r"[1-6]-[1-6]-[1-6]\Z")


def _checked(dist):
    if not isinstance(dist, dict) or not dist:
        raise ValueError("HOLD:NONEMPTY_TICKET_DISTRIBUTION_REQUIRED")
    boats = set()
    for ticket, probability in dist.items():
        if (not isinstance(ticket, str) or not _TICKET.fullmatch(ticket)
                or len(set(ticket.split("-"))) != 3):
            raise ValueError("HOLD:POOL_TICKET_DOMAIN_INVALID")
        boats.update(map(int, ticket.split("-")))
        try:
            valid = (type(probability) in (float, int) and math.isfinite(probability)
                     and 0 <= probability <= 1)
        except OverflowError:
            valid = False
        if not valid:
            raise ValueError("HOLD:POOL_PROBABILITY_INVALID")
    expected = {"-".join(map(str, triple)) for triple in permutations(sorted(boats), 3)}
    if not 3 <= len(boats) <= 6 or set(dist) != expected:
        raise ValueError("HOLD:POOL_FULL_ACTIVE_DOMAIN_REQUIRED")
    if not math.isclose(math.fsum(dist.values()), 1.0, rel_tol=0, abs_tol=1e-10):
        raise ValueError("HOLD:POOL_MASS_NOT_ONE")
    return dict(dist)


def pool_market(model_dist, market_dist, weight):
    """Pooled(t) proportional to model(t)^(1-w) * market(t)^w.

    w is MARKET weight; (1-w) is MODEL weight. Both distributions are checked
    even at endpoints. w=1 returns a detached exact market copy and w=0 an
    exact model copy. There is no endpoint softmax/re-normalization or epsilon.
    At intermediate weights, zero input support has zero product support.
    """
    try:
        valid_weight = type(weight) in (int, float) and math.isfinite(weight) and 0 <= weight <= 1
    except OverflowError:
        valid_weight = False
    if not valid_weight:
        raise ValueError("HOLD:POOL_MARKET_WEIGHT_INVALID")
    model, market = _checked(model_dist), _checked(market_dist)
    if set(model) != set(market):
        raise ValueError("HOLD:POOL_DISTRIBUTION_DOMAIN_MISMATCH")
    if weight == 1:
        return market
    if weight == 0:
        return model
    logits = {ticket: (1-weight)*math.log(model[ticket]) + weight*math.log(market[ticket])
              for ticket in model if model[ticket] > 0 and market[ticket] > 0}
    if not logits:
        raise ValueError("HOLD:POOL_NO_COMMON_POSITIVE_SUPPORT")
    maximum = max(logits.values())
    masses = {ticket: math.exp(logit-maximum) for ticket, logit in logits.items()}
    total = math.fsum(masses.values())
    return {ticket: masses.get(ticket, 0.0)/total for ticket in model}
