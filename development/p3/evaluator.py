"""SYS-25 evaluation of supplied predictions only. No training or prediction."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from itertools import permutations
import math
import random
import re


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("FINITE_NUMBER_REQUIRED")
    try:result=float(value)
    except (OverflowError,ValueError):raise ValueError('FINITE_NUMBER_REQUIRED') from None
    if not math.isfinite(result):raise ValueError('FINITE_NUMBER_REQUIRED')
    return result


def _money(value):
    if isinstance(value, bool) or value is None:
        raise ValueError("MONEY_UNKNOWN_OR_INVALID")
    try:
        v = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("MONEY_UNKNOWN_OR_INVALID") from None
    if not v.is_finite() or v < 0:
        raise ValueError("MONEY_UNKNOWN_OR_INVALID")
    return v


def _domain(boats):
    if not isinstance(boats, list) or not 3 <= len(boats) <= 6 or len(set(boats)) != len(boats):
        raise ValueError("ACTIVE_BOATS_INVALID")
    if any(type(x) is not int or x not in range(1, 7) for x in boats):
        raise ValueError("ACTIVE_BOATS_INVALID")
    return {"-".join(map(str, p)) for p in permutations(boats, 3)}


def _tickets(prediction, domain):
    tickets = prediction.get("tickets")
    if not isinstance(tickets, list) or len(tickets) != 5 or any(not isinstance(t, str) for t in tickets):
        raise ValueError("FIVE_TICKETS_REQUIRED")
    if len(set(tickets)) != 5 or not set(tickets) <= domain:
        raise ValueError("TICKETS_INVALID")
    return tickets


def _probabilities(vector, domain):
    if not isinstance(vector, dict) or set(vector) != domain:
        raise ValueError("FULL_PROBABILITY_DOMAIN_REQUIRED")
    values = {k: _number(v) for k, v in vector.items()}
    if any(v <= 0 or v > 1 for v in values.values()):
        raise ValueError("PROBABILITY_RANGE")
    if not math.isclose(math.fsum(values.values()), 1.0, rel_tol=0, abs_tol=1e-9):
        raise ValueError("PROBABILITIES_NOT_NORMALIZED")
    return values


def _market(odds, domain):
    if not isinstance(odds, dict) or set(odds) != domain:
        raise ValueError("FULL_ODDS_DOMAIN_REQUIRED")
    values = {k: _number(v) for k, v in odds.items()}
    if any(v <= 0 for v in values.values()):
        raise ValueError("ODDS_RANGE")
    inverse = {k: 1.0 / v for k, v in values.items()}
    total = math.fsum(inverse.values())
    if not math.isfinite(total) or total <= 0:
        raise ValueError("ODDS_NORMALIZATION_UNAVAILABLE")
    return {k: v / total for k, v in inverse.items()}


def _scores(vector, result):
    # No clipping, smoothing or conversion of zero probability into a finite loss.
    return (-math.log(vector[result]), math.fsum((v - int(k == result)) ** 2 for k, v in vector.items()))


def _ece(samples, edges):
    if edges is None:
        return {"status": "UNVERIFIED_BINS_NOT_PREREGISTERED", "value": None}
    if not isinstance(edges, list) or len(edges) < 2:
        raise ValueError("CALIBRATION_EDGES_INVALID")
    clean = [_number(x) for x in edges]
    if clean[0] != 0 or clean[-1] != 1 or any(a >= b for a, b in zip(clean, clean[1:])):
        raise ValueError("CALIBRATION_EDGES_INVALID")
    if not samples:
        return {"status": "UNVERIFIED_NO_COMPLETE_PROBABILITIES", "value": None}
    bins = []
    total = 0.0
    for i, (lo, hi) in enumerate(zip(clean, clean[1:])):
        selected = [(p, y) for p, y in samples if lo <= p and (p < hi or i == len(clean)-2 and p <= hi)]
        if selected:
            confidence = math.fsum(p for p, _ in selected) / len(selected)
            accuracy = math.fsum(y for _, y in selected) / len(selected)
            total += len(selected) / len(samples) * abs(confidence - accuracy)
            bins.append({"low": lo, "high": hi, "n": len(selected), "confidence": confidence, "accuracy": accuracy})
        else:
            bins.append({"low": lo, "high": hi, "n": 0, "confidence": None, "accuracy": None})
    return {"status": "EXPLORATORY_ON_SUPPLIED_BINS", "value": total, "bins": bins, "definition": "TOP_LABEL_ECE"}


def _percentile(values, q):
    ordered = sorted(values)
    location = (len(ordered)-1) * q
    a, b = math.floor(location), math.ceil(location)
    return ordered[a] + (ordered[b]-ordered[a]) * (location-a)


def cluster_interval(day_deltas, config):
    if not isinstance(day_deltas,dict) or any(not isinstance(v,list) or not v or any(type(x) is not int or x not in (-1,0,1) for x in v) for v in day_deltas.values()):
        raise ValueError('DAY_CLUSTER_VALUES_INVALID')
    if config is None:
        return {"status": "UNVERIFIED_PREREG_CONFIG_MISSING", "interval": None}
    required = {"replicates", "seed", "confidence", "min_cluster_days", "preregistration_sha256", "exchangeable_days_assumption"}
    if not isinstance(config, dict) or not required <= config.keys():
        return {"status": "UNVERIFIED_PREREG_CONFIG_INCOMPLETE", "interval": None}
    b, seed, minimum = config["replicates"], config["seed"], config["min_cluster_days"]
    confidence = _number(config["confidence"])
    digest = config["preregistration_sha256"]
    if type(b) is not int or not 10 <= b <= 100000 or type(seed) is not int or type(minimum) is not int or minimum < 2 or not 0 < confidence < 1:
        raise ValueError("BOOTSTRAP_CONFIG_INVALID")
    if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest) or config["exchangeable_days_assumption"] is not True:
        return {"status": "UNVERIFIED_PREREG_OR_ASSUMPTION", "interval": None}
    if len(day_deltas) < minimum:
        return {"status": "UNVERIFIED_SMALL_CLUSTER_COUNT", "interval": None, "days": len(day_deltas), "required_by_supplied_plan": minimum}
    clusters = [day_deltas[k] for k in sorted(day_deltas)]
    generator = random.Random(seed)
    draws = []
    for _ in range(b):
        selected = [generator.choice(clusters) for _ in clusters]
        # Whole days are resampled; unequal race counts remain race-weighted.
        draws.append(math.fsum(math.fsum(x) for x in selected) / sum(len(x) for x in selected))
    tail = (1-confidence)/2
    return {"status": "EXPLORATORY_CONDITIONAL_ON_EXCHANGEABLE_DAYS", "interval": [_percentile(draws, tail), _percentile(draws, 1-tail)], "days": len(clusters), "replicates": b, "confidence": confidence, "method": "RACE_WEIGHTED_DAY_BLOCK_PERCENTILE_BOOTSTRAP", "preregistration_reference_authenticity": "NOT_VERIFIED", "formal_superiority": "NOT_EVALUATED"}


def evaluate_pairs(rows, *, comparator_source, candidate_id, calibration_edges=None, ci_config=None):
    if comparator_source not in ('A', 'B') or not isinstance(rows, list) or not isinstance(candidate_id,str) or not candidate_id:
        raise ValueError("SOURCE_OR_ROWS_INVALID")
    if any(not isinstance(r, dict) for r in rows):
        raise ValueError('ROWS_OBJECTS_REQUIRED')
    counts = Counter((r.get('comparator_source'), r.get('race_id')) for r in rows if r.get('comparator_source') in ('A','B') and isinstance(r.get('race_id'),str))
    issues, hits, scores, market_scores, money, matched_market = [], [], [], [], [], []
    day_deltas = defaultdict(list)
    calibration = {'old': [], 'candidate': [], 'market': []}
    for index, row in enumerate(rows):
        try:
            if row.get('comparator_source') != comparator_source:
                raise ValueError("SOURCE_MISMATCH")
            if not isinstance(row.get('race_id'), str) or not row['race_id']:
                raise ValueError("RACE_ID_MISSING")
            if counts[(comparator_source, row.get('race_id'))] != 1:
                raise ValueError("DUPLICATE_RACE_PAIR_ALL_EXCLUDED")
            try:day = date.fromisoformat(row['day']).isoformat()
            except (ValueError,TypeError):raise ValueError('DAY_INVALID') from None
            if row.get('race_id_profile')!='DATE_PREFIXED_GAMAGORI_V1' or not re.fullmatch(r'[0-9]{8}_GAMAGORI_(?:[1-9]|1[0-2])R',row['race_id']):
                raise ValueError('UNSUPPORTED_OR_MISSING_RACE_ID_PROFILE')
            if row['race_id'][:8]!=day.replace('-',''):
                raise ValueError('RACE_DAY_MISMATCH')
            old, candidate = row['old'], row['candidate']
            if not isinstance(old,dict) or not isinstance(candidate,dict):raise ValueError('PREDICTION_OBJECT_REQUIRED')
            if old.get('race_id') != row['race_id'] or candidate.get('race_id') != row['race_id'] or candidate.get('lane') != 'THIRD_RESEARCH':
                raise ValueError("PAIR_ID_OR_LANE_MISMATCH")
            if old.get('source')!=comparator_source or candidate.get('comparator_source')!=comparator_source:
                raise ValueError('BOUND_PREDICTION_SOURCE_MISMATCH')
            if old.get('target_date')!=day or candidate.get('target_date')!=day:
                raise ValueError('PREDICTION_DAY_MISMATCH')
            if candidate.get('candidate_id')!=candidate_id:
                raise ValueError('CANDIDATE_ID_MISMATCH')
            if old.get('existing_predeadline_verdict') != 'VERIFIED' or candidate.get('existing_predeadline_verdict') != 'VERIFIED':
                raise ValueError("UPSTREAM_ELIGIBILITY_UNVERIFIED")
            domain = _domain(row['active_boats'])
            if row.get('result') not in domain:
                raise ValueError("RESULT_UNAVAILABLE_OR_INVALID")
            tickets_old, tickets_new = _tickets(old, domain), _tickets(candidate, domain)
        except (ValueError, KeyError, TypeError) as exc:
            reason = str(exc) if isinstance(exc, ValueError) else 'REQUIRED_INPUT_INVALID'
            issues.append({'row_index': index, 'scope': 'PAIR', 'reason': reason})
            continue
        outcome = row['result']
        y0, y1 = int(outcome in tickets_old), int(outcome in tickets_new)
        hits.append((y0, y1))
        day_deltas[day].append(y1-y0)
        row_score = None
        try:
            p0, p1 = _probabilities(old.get('probabilities'), domain), _probabilities(candidate.get('probabilities'), domain)
            row_score = (_scores(p0, outcome), _scores(p1, outcome))
            scores.append(row_score)
            for name, vector in [('old', p0), ('candidate', p1)]:
                top = min(vector, key=lambda k: (-vector[k], k))
                calibration[name].append((vector[top], int(top == outcome)))
        except ValueError as exc:
            issues.append({'row_index': index, 'scope': 'PROPER_SCORES', 'reason': str(exc)})
        try:
            if row.get('market_snapshot_verdict') != 'VERIFIED':
                raise ValueError("MARKET_SNAPSHOT_UNVERIFIED")
            pm = _market(row.get('market_odds'), domain)
            market_scores.append(_scores(pm, outcome))
            if row_score is not None:matched_market.append((row_score,market_scores[-1]))
            top = min(pm, key=lambda k: (-pm[k], k))
            calibration['market'].append((pm[top], int(top == outcome)))
        except ValueError as exc:
            issues.append({'row_index': index, 'scope': 'MARKET', 'reason': str(exc)})
        try:
            pair_money = []
            for prediction in (old, candidate):
                record = prediction.get('money', {})
                if not isinstance(record,dict):raise ValueError('MONEY_OBJECT_REQUIRED')
                stake, payout, refund = (_money(record.get(k)) for k in ('stake_yen', 'payout_yen', 'refund_yen'))
                if stake <= 0:
                    raise ValueError("POSITIVE_STAKE_REQUIRED")
                pair_money.append((stake, payout, refund))
            money.append(pair_money)
        except ValueError as exc:
            issues.append({'row_index': index, 'scope': 'MONEY', 'reason': str(exc)})
    n = len(hits)
    result = {'status': 'COMPUTED_ON_SUPPLIED_ELIGIBILITY_NOT_LOCK_VALIDATION', 'comparator_source': comparator_source, 'candidate_id':candidate_id, 'input_rows': len(rows), 'complete_pair_N': n, 'excluded_pair_count': len(rows)-n, 'old_hit_rate': sum(a for a, _ in hits)/n if n else None, 'candidate_hit_rate': sum(b for _, b in hits)/n if n else None, 'paired_improvement': sum(b-a for a, b in hits)/n if n else None, 'gain_count': sum(a == 0 and b == 1 for a, b in hits), 'loss_count': sum(a == 1 and b == 0 for a, b in hits), 'proper_score_pair_N': len(scores), 'market_N': len(market_scores), 'money_complete_pair_N': len(money), 'issues': issues, 'production_GO': False, 'model_or_weight_change': False, 'eligibility_and_timestamp_authenticity': 'NOT_VERIFIED'}
    result['proper_scores'] = {name: {'log_loss': sum(x[i][0] for x in scores)/len(scores) if scores else None, 'brier_multiclass_sum': sum(x[i][1] for x in scores)/len(scores) if scores else None} for i, name in enumerate(('old','candidate'))}
    result['market_scores'] = {'log_loss': sum(x[0] for x in market_scores)/len(market_scores) if market_scores else None, 'brier_multiclass_sum': sum(x[1] for x in market_scores)/len(market_scores) if market_scores else None, 'interpretation': 'NORMALIZED_INVERSE_ODDS_PROXY_NOT_TRUE_PROBABILITIES'}
    result['paired_market_comparison']={'N':len(matched_market),'old_log_loss_minus_market':sum(a[0][0]-b[0] for a,b in matched_market)/len(matched_market) if matched_market else None,'candidate_log_loss_minus_market':sum(a[1][0]-b[0] for a,b in matched_market)/len(matched_market) if matched_market else None,'negative_difference_means':'LOWER_LOSS_THAN_MARKET_PROXY_ON_IDENTICAL_ROWS'}
    result['money'] = {}
    for i, name in enumerate(('old','candidate')):
        if not money:
            result['money'][name] = {'stake_yen': None, 'payout_yen': None, 'refund_yen': None, 'gross_return_rate': None, 'net_ROI': None}
        else:
            stake, payout, refund = (sum((row[i][k] for row in money), Decimal(0)) for k in range(3))
            result['money'][name] = {'stake_yen': str(stake), 'payout_yen': str(payout), 'refund_yen': str(refund), 'gross_return_rate': str((payout+refund)/stake), 'net_ROI': str((payout+refund-stake)/stake)}
    result['calibration'] = {k: _ece(v, calibration_edges) for k, v in calibration.items()}
    result['cluster_CI'] = cluster_interval(day_deltas, ci_config)
    return result
