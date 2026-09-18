"""All HTML below is SYNTHETIC, NOT a captured official HTTP response."""
import datetime as dt
import hashlib
import itertools
import json
import pytest
from v11_candidate.odds import parse_trifecta, OddsParseError
from v11_candidate.contracts import (SourceScopedReader, ContractError, DeadlineSnapshot, StageTelemetry, qualitative_delta, response_metadata, canonical, verify_prediction_times)


def matrix(firsts=(1,2,3,4,5,6), rowspan=True):
    html='<h3>3連単オッズ</h3><table><thead><tr>'
    html+=''.join(f'<th colspan="3">{b}</th>' for b in firsts)+'</tr></thead><tbody>'
    expected={}
    for n in range(20):
        html+='<tr>'
        for first in firsts:
            second=[b for b in range(1,7) if b!=first][n//4]
            third=[b for b in range(1,7) if b not in (first,second)][n%4]
            odds=f'{first*100+second*10+third}.1'
            if not rowspan or n%4==0:
                html+=f'<td rowspan="{4 if rowspan else 1}">{second}</td>'
            html+=f'<td>{third}</td><td>{odds}</td>'
            expected[f'{first}-{second}-{third}']=float(odds)
        html+='</tr>'
    return html+'</tbody></table>',expected


def explicit(count=120):
    combos=list(itertools.permutations(range(1,7),3))[:count]
    return '<h3>3連単</h3><table>'+''.join(f'<tr><td>{a}-{b}-{c}</td><td>12.3</td></tr>' for a,b,c in combos)+'</table>'


@pytest.mark.parametrize('firsts',[(1,2,3,4,5,6),(6,5,4,3,2,1),(2,1,4,3,6,5)])
@pytest.mark.parametrize('rowspan',[True,False])
def test_matrix_exact_all_120(firsts,rowspan):
    html,expected=matrix(firsts,rowspan);result=parse_trifecta(html)
    assert result.odds==expected and result.complete and result.coverage==120


def test_explicit_120():
    assert parse_trifecta(explicit()).coverage==120


def test_partial_is_not_complete():
    with pytest.raises(OddsParseError,match='INCOMPLETE'):parse_trifecta(explicit(2))
    result=parse_trifecta(explicit(2),require_complete=False)
    assert result.coverage==2 and not result.complete


@pytest.mark.parametrize('bad',['nan','inf','0.9','0','-1','10000.0','12.34','12.3abc','1e2','1,234.5','12.3 2'])
def test_invalid_number_rejected(bad):
    with pytest.raises(OddsParseError):parse_trifecta(explicit().replace('12.3',bad,1))


def test_fullwidth_supported():
    assert parse_trifecta(explicit().replace('1-2-3','１－２－３').replace('12.3','１２．３')).complete


def test_wrong_race_numbers_not_guessed():
    with pytest.raises(OddsParseError):parse_trifecta('<h3>3連単</h3><table><tr><td>1 2 3 12.3</td></tr></table>')


def test_ambiguous_tables_rejected():
    with pytest.raises(OddsParseError):parse_trifecta(explicit()+explicit())


def test_duplicate_combo_rejected():
    with pytest.raises(OddsParseError,match='DUPLICATE'):parse_trifecta(explicit().replace('1-2-4','1-2-3'))


def test_missing_matrix_cell_rejected():
    html,_=matrix()
    with pytest.raises(OddsParseError):parse_trifecta(html.replace('<td>123.1</td>','',1))


def test_invalid_matrix_span_rejected():
    html,_=matrix()
    with pytest.raises(OddsParseError):parse_trifecta(html.replace('rowspan="4"','rowspan="5"',1))


def test_nesting_rejected():
    with pytest.raises(OddsParseError):parse_trifecta('<h3>3連単</h3><table><tr><td>'+explicit()+'</td></tr></table>')


def test_second_boat_wrong_rejected():
    html,_=matrix()
    with pytest.raises(OddsParseError):parse_trifecta(html.replace('<td rowspan="4">2</td>','<td rowspan="4">1</td>',1))


def test_foreign_section_not_used():
    with pytest.raises(OddsParseError):parse_trifecta(explicit().replace('3連単','2連単'))


@pytest.mark.parametrize('observed,ingested,deadline',[
 ('2026-09-18T09:45:29+00:00','2026-09-18T09:48:00+00:00','2026-09-18T09:48:00+00:00'),
 ('2026-09-18T09:49:00+00:00','2026-09-18T09:47:39+00:00','2026-09-18T09:48:00+00:00'),
 ('2026-09-18T09:45:29','2026-09-18T09:47:39+00:00','2026-09-18T09:48:00+00:00')])
def test_time_fail_closed(observed,ingested,deadline):
    with pytest.raises(ContractError):verify_prediction_times(observed,ingested,deadline)


def test_real_b8_time_order():
    verify_prediction_times('2026-09-18T09:45:29.009357+00:00','2026-09-18T09:47:39+00:00','2026-09-18T09:48:00+00:00')


def reader():
    return SourceScopedReader('A','fldNpmWHD4xWaC2Za','selZosUzCb9gGHbvK','fldfnYTe2E8CRAVih')


def row(source='A',race_id='20260918_GAMAGORI_5R'):
    return {'source':source,'race_id':race_id,'payload':{'source':source,'race_id':race_id}}


def test_filter_before_query():
    def query(f):
        assert f['operator']=='and'
        assert f['operands'][0]=={'operator':'=','operands':['fldNpmWHD4xWaC2Za','selZosUzCb9gGHbvK']}
        return [row()]
    assert reader().read(query,'20260918_GAMAGORI_5R')==[row()]


def test_mixed_rows_never_released():
    with pytest.raises(ContractError,match='SOURCE_OR_RACE_SCOPE_BREACH') as exc:
        reader().read(lambda f:[row(),{**row('B'),'secret':'B picks here'}],'20260918_GAMAGORI_5R')
    assert 'B picks' not in str(exc.value)


def test_payload_disagrees_with_column():
    bad=row();bad['payload']['source']='B'
    with pytest.raises(ContractError,match='PAYLOAD_SCOPE'):reader().read(lambda f:[bad],'20260918_GAMAGORI_5R')


def test_wrong_date_rejected():
    with pytest.raises(ContractError):reader().read(lambda f:[row(race_id='20260917_GAMAGORI_5R')],'20260918_GAMAGORI_5R')


def deadline(**overrides):
    args=dict(target_date='2026-09-18',scheduled_deadline='2026-09-18T18:48:00+09:00',official_deadline_observed='2026-09-18T18:48:00+09:00',acquired_at='2026-09-18T18:44:00+09:00',source_url='https://www.boatrace.jp/',live_state_consistent=True)
    return DeadlineSnapshot(**(args|overrides))


def test_cutoff_is_strict_and_not_guaranteed():
    assert deadline().allow_revision('2026-09-18T18:45:59+09:00',120)
    assert not deadline().allow_revision('2026-09-18T18:46:00+09:00',120)
    assert not deadline(live_state_consistent=False).allow_revision('2026-09-18T18:45:00+09:00',0)
    assert not deadline(official_deadline_observed=None).allow_revision('2026-09-18T18:45:00+09:00',0)


@pytest.mark.parametrize('bad',[float('nan'),float('inf'),-1])
def test_bad_reserve(bad):
    with pytest.raises(ContractError):deadline().allow_revision('2026-09-18T18:45:00+09:00',bad)


def test_deadline_wrong_target_date():
    with pytest.raises(ContractError):deadline(target_date='2026-09-19').allow_revision('2026-09-18T18:45:00+09:00',0)


def test_future_fetch():
    with pytest.raises(ContractError):deadline().allow_revision('2026-09-18T18:43:00+09:00',0)


def test_monotonic_not_wall_clock_for_durations():
    ticks=iter([100.,103.]);walls=iter([dt.datetime(2026,9,18,16,tzinfo=dt.timezone.utc),dt.datetime(2026,9,18,15,tzinfo=dt.timezone.utc)])
    t=StageTelemetry(lambda:next(ticks),lambda:next(walls));t.mark('FETCH_FINISHED');t.mark('APPEND_STARTED')
    assert t.intervals()[0]['seconds']==3


def test_duplicate_stage():
    t=StageTelemetry();t.mark('FETCH_FINISHED')
    with pytest.raises(ContractError):t.mark('FETCH_FINISHED')


def test_delta_no_fabricated_score():
    d=qualitative_delta('DOWN','EXHIBITION_SLOW',['evidence1']);assert d['score_delta'] is None
    with pytest.raises(ContractError):qualitative_delta('DOWN','EXHIBITION_SLOW',[])


def test_metadata_hash_not_persistence_claim():
    r=response_metadata(b'abc','https://www.boatrace.jp/owpc/pc/race/odds3t?hd=20260918&jcd=07&rno=8','2026-09-18T09:44:00Z',200,'text/html','2026-09-18',8)
    assert r['body_sha256']==hashlib.sha256(b'abc').hexdigest() and r['url_identity_matches']
    assert not r['snapshot_persisted'] and not r['content_validated']


def test_metadata_wrong_date_is_not_validated():
    r=response_metadata(b'abc','https://www.boatrace.jp/owpc/pc/race/odds3t?hd=20260917&jcd=07&rno=8','2026-09-18T09:44:00Z',200,'text/html','2026-09-18',8)
    assert not r['url_identity_matches']


def test_canonical_nonfinite_rejected():
    with pytest.raises(ValueError):canonical({'x':float('nan')})
    assert canonical({'日本':1,'a':2})=='{"a":2,"日本":1}'
