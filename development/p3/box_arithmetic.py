"""SYS-26 local arithmetic. PRE/LIVE/FINAL never share a cumulative total."""
from collections import defaultdict
from decimal import Decimal, InvalidOperation


def amount(value):
    if value is None or isinstance(value, bool):
        raise ValueError('AMOUNT_UNKNOWN')
    try:
        result=Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError('AMOUNT_INVALID') from None
    if not result.is_finite() or result < 0:
        raise ValueError('AMOUNT_INVALID')
    return result


def check_box(entries, *, coverage=None):
    groups=defaultdict(list)
    if not isinstance(entries,list): raise ValueError('ENTRIES_LIST_REQUIRED')
    for i,row in enumerate(entries):
        if not isinstance(row,dict) or row.get('phase') not in ('PRE','LIVE','FINAL') or not isinstance(row.get('period'),str) or not row['period']:
            raise ValueError('PHASE_OR_PERIOD_INVALID')
        groups[(row['phase'],row['period'])].append((i,row))
    reports=[]
    for (phase,period),rows in sorted(groups.items()):
        complete=True;issues=[];flows=[];snapshots=[];ids=set()
        proof=coverage.get(phase+'|'+period) if isinstance(coverage,dict) else None
        if not isinstance(proof,dict) or proof.get('complete') is not True or not isinstance(proof.get('evidence_reference'),str) or not proof['evidence_reference']:
            complete=False;issues.append({'reason':'PERIOD_COVERAGE_UNVERIFIED'})
        for i,row in rows:
            if not isinstance(row.get('entry_id'),str) or not row['entry_id'] or row['entry_id'] in ids:
                complete=False;issues.append({'row_index':i,'reason':'MISSING_OR_DUPLICATE_ID'});continue
            ids.add(row['entry_id'])
            if row.get('kind') not in ('FLOW','CUMULATIVE_SNAPSHOT'):
                complete=False;issues.append({'row_index':i,'reason':'UNKNOWN_ENTRY_KIND'});continue
            if phase=='FINAL' and row.get('confirmed') is not True:
                complete=False;issues.append({'row_index':i,'reason':'FINAL_NOT_CONFIRMED'});continue
            try:values=tuple(amount(row.get(k)) for k in ('stake_yen','payout_yen','refund_yen'))
            except ValueError as exc:
                complete=False;issues.append({'row_index':i,'reason':str(exc)});continue
            if row['kind']=='FLOW':flows.append(values)
            else:snapshots.append((values,row.get('scope_complete') is True))
        totals=tuple(sum((r[k] for r in flows),Decimal(0)) for k in range(3))
        # No rows of flows is not proof of a zero period.
        if not flows:
            complete=False;issues.append({'reason':'NO_COMPLETE_FLOWS'})
        if len(snapshots)>1:
            complete=False;issues.append({'reason':'MULTIPLE_CUMULATIVE_SNAPSHOTS'})
        snapshot_match=None
        if len(snapshots)==1:
            values,scope_complete=snapshots[0]
            if scope_complete and complete:snapshot_match=values==totals
            else:issues.append({'reason':'SNAPSHOT_SCOPE_OR_FLOW_COVERAGE_UNVERIFIED'})
        stake,payout,refund=totals
        reports.append({'phase':phase,'period':period,'status':'COMPUTED_FLOW_ARITHMETIC_ONLY' if complete else 'UNVERIFIED',
            'complete_flow_count':len(flows),'known_flow_subtotal':dict(zip(('stake_yen','payout_yen','refund_yen'),map(str,totals))),
            'complete_totals':dict(zip(('stake_yen','payout_yen','refund_yen'),map(str,totals))) if complete else None,
            'gross_return_rate':str((payout+refund)/stake) if complete and stake>0 else None,
            'net_ROI':str((payout+refund-stake)/stake) if complete and stake>0 else None,
            'claimed_cumulative_matches_flows':snapshot_match,'issues':issues})
    return {'groups':reports,'PRE_LIVE_FINAL_combined_total':'NOT_COMPUTED_DIFFERENT_SCOPES','coverage_evidence_authenticity':'NOT_VERIFIED_BY_ARITHMETIC_CODE','existing_cumulative_rewritten':False,'production_GO':False}
