"""Authored result layouts. No synthetic fixture proves real withdrawal semantics."""
from dataclasses import replace, asdict
import datetime as dt
import hashlib
import json
from bs4 import BeautifulSoup
import pytest
from test_v11_roster_semantics import fixture as roster_fixture
from v11_candidate.participant_evidence import RaceIdentity
from v11_candidate.postrace_completion import (ResultSnapshot, CompletionError,
    inspect_result, assess_postrace_day, parse_result_publication)

NOW=dt.datetime(2026,9,19,10,tzinfo=dt.timezone.utc)


def fixture(race=12):
    s=BeautifulSoup(roster_fixture(race).decode(),'html.parser')
    s.title.string='結果｜BOAT RACE オフィシャルウェブサイト'
    s.select_one('.tab3_tabs > li.is-active').string='結果'
    a=s.select_one('.tab3_tabs a[href*="raceresult"]'); a['href']=a['href'].replace('raceresult','racelist')
    for a in s.select('#nav a'): a['href']=a['href'].replace('racelist','raceresult')
    s.select_one('#roster').decompose()
    h='<table id="finish"><thead><tr><th>着</th><th>枠</th><th>ボートレーサー</th><th>レースタイム</th></tr></thead>'
    for rank,b in enumerate((1,5,2,6,4,3),1):
        h+=f'<tbody><tr><td>{rank}</td><td class="is-boatColor{b}">{b}</td><td><span class="is-fs12">{5000+b}</span>試験</td><td></td></tr></tbody>'
    h+='</table><table id="payout"><thead><tr><th>勝式</th><th>組番</th><th>払戻金</th><th>人気</th></tr></thead>'
    h+='<tbody><tr><td rowspan="2">3連単</td><td>1-5-2</td><td>¥1,910</td><td>6</td></tr><tr><td></td><td></td><td></td></tr></tbody></table>'
    s.body.append(BeautifulSoup(h,'html.parser'))
    return str(s).encode()


def snap(race=12,body=None,**kw):
    b=fixture(race) if body is None else body
    u=f'https://www.boatrace.jp/owpc/pc/race/raceresult?hd=20260918&jcd=07&rno={race}'
    return replace(ResultSnapshot(race,u,u,'2026-09-19T00:00:00+00:00',200,'text/html;charset=UTF-8','identity',True,b,hashlib.sha256(b).hexdigest()),**kw)


def inspect(x):return inspect_result(x,RaceIdentity('2026-09-18','07',x.race_no),now=NOW)


@pytest.mark.parametrize('race',range(1,13))
def test_recognized_single_result_is_observation_not_withdrawal(race):
    r=inspect(snap(race))
    assert r.state=='PASS' and r.trifecta=='1-5-2' and r.payout_yen==1910
    assert r.withdrawal_classification=='NOT_PERFORMED' and r.source_effective_at is None


def test_all_twelve_can_plan_archive_without_authorizing_any_other_operation():
    r=assess_postrace_day('2026-09-18',tuple(snap(i) for i in range(1,13)),now=NOW)
    assert r['archive_input_eligible'] and r['verified_count']==12
    assert not r['scheduler_started'] and not r['predeadline_state_proven'] and not r['permanent_settlement_certified']
    digest=r.pop('binding_sha256')
    assert digest==hashlib.sha256(json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


@pytest.mark.parametrize('races',[(),(12,),tuple(range(1,12))])
def test_date_elapsed_or_last_race_alone_does_not_establish_day_completion(races):
    r=assess_postrace_day('2026-09-18',tuple(snap(i) for i in races),now=NOW)
    assert r['state']=='UNVERIFIED' and not r['archive_input_eligible']


def test_reusing_last_result_body_for_every_race_is_detected():
    r=assess_postrace_day('2026-09-18',tuple(snap(i,fixture(12)) for i in range(1,13)),now=NOW)
    assert r['state']=='FAIL' and r['verified_count']==1


@pytest.mark.parametrize('old,new',[
 ('結果｜BOAT','出走表｜BOAT'),('alt="蒲郡"','alt="津"'),
 ('text_place2_07.png','text_place2_06.png'),('9月18日','9月17日'),
 ('hd=20260918','hd=20260917'),('jcd=07','jcd=06'),
 ('rno=12','rno=3'),('class="is-active">結果','class="is-active">出走表')])
def test_result_body_identity_conflicts_never_pass(old,new):
    assert inspect(snap(body=fixture().replace(old.encode(),new.encode(),1))).state!='PASS'


@pytest.mark.parametrize('field',['requested_url','response_url'])
@pytest.mark.parametrize('url',[
 'https://www.boatrace.jp.evil/owpc/pc/race/raceresult?hd=20260918&jcd=07&rno=12',
 'https://user@www.boatrace.jp/owpc/pc/race/raceresult?hd=20260918&jcd=07&rno=12',
 'https://www.boatrace.jp:444/owpc/pc/race/raceresult?hd=20260918&jcd=07&rno=12',
 'https://www.boatrace.jp/owpc/pc/race/raceresult?hd=20260918&jcd=07&rno=12&rno=12',
 'https://www.boatrace.jp/owpc/pc/race/raceresult?hd=20260918&jcd=07&rno=12#x',
 'https://www.boatrace.jp/owpc/pc/race/beforeinfo?hd=20260918&jcd=07&rno=12'])
def test_request_and_response_scope_both_checked(field,url):
    assert inspect(snap(**{field:url})).state=='FAIL'


@pytest.mark.parametrize('kwargs',[
 {'http_status':503},{'body_complete':False},{'content_type':'application/json'},
 {'content_encoding':'gzip'}])
def test_transport_unavailable_stays_unverified(kwargs):
    assert inspect(snap(**kwargs)).state=='UNVERIFIED'


@pytest.mark.parametrize('kwargs',[
 {'body_sha256':'0'*64},{'http_status':True},{'body_complete':'true'},
 {'acquired_at':'2026-09-20T00:00:00Z'},{'acquired_at':'2026-09-17T00:00:00Z'},
 {'acquired_at':'2026-09-19T00:00:00'},{'acquired_at':'bad'}])
def test_tamper_mistyped_metadata_or_time_conflict_is_fail(kwargs):
    assert inspect(snap(**kwargs)).state=='FAIL'


@pytest.mark.parametrize('selector',['#finish','#payout','#nav','.tab3_tabs'])
def test_duplicate_sections_rejected(selector):
    soup=BeautifulSoup(fixture(),'html.parser'); duplicate=str(soup.select_one(selector))
    assert inspect(snap(body=(str(soup)+duplicate).encode())).state=='FAIL'


@pytest.mark.parametrize('selector',['#finish','#payout'])
def test_missing_results_never_mean_no_race_or_cancelled(selector):
    soup=BeautifulSoup(fixture(),'html.parser');soup.select_one(selector).decompose()
    r=inspect(snap(body=str(soup).encode()))
    assert r.state=='UNVERIFIED' and r.withdrawal_classification=='NOT_PERFORMED'


@pytest.mark.parametrize('marker',['F','L','欠場','不明'])
def test_nonstandard_finish_token_kept_raw_without_withdrawal_classification(marker):
    soup=BeautifulSoup(fixture(),'html.parser');soup.select('#finish tbody')[5].tr.td.string=marker
    r=inspect(snap(body=str(soup).encode()))
    assert r.state=='PASS' and (3,marker) in r.finish_labels
    assert r.withdrawal_classification=='NOT_PERFORMED'


@pytest.mark.parametrize('value',['','2','F'])
def test_top_three_missing_or_tied_never_passes(value):
    soup=BeautifulSoup(fixture(),'html.parser');soup.select('#finish tbody')[0].tr.td.string=value
    assert inspect(snap(body=str(soup).encode())).state=='UNVERIFIED'


@pytest.mark.parametrize('value',['','返還','¥0','¥1,91','¥1,910abc'])
def test_unreviewed_payout_not_used(value):
    soup=BeautifulSoup(fixture(),'html.parser');soup.select('#payout tbody tr')[0].find_all('td')[2].string=value
    assert inspect(snap(body=str(soup).encode())).state=='UNVERIFIED'


def test_finish_and_payout_disagreement_rejected():
    assert inspect(snap(body=fixture().replace(b'1-5-2',b'1-2-5'))).state=='FAIL'


def test_second_winning_trifecta_is_not_silently_ignored():
    soup=BeautifulSoup(fixture(),'html.parser');row=soup.select('#payout tbody tr')[1]
    for cell,val in zip(row.find_all('td'),('1-2-5','¥2,000','7')):cell.string=val
    assert inspect(snap(body=str(soup).encode())).state=='UNVERIFIED'


@pytest.mark.parametrize('mutation',['boat','registration','row','nested'])
def test_invalid_finish_table_fails_closed(mutation):
    soup=BeautifulSoup(fixture(),'html.parser')
    row=soup.select('#finish tbody')[0].tr
    if mutation=='boat':row.find_all('td')[1]['class']=['is-boatColor2']
    elif mutation=='registration':row.select_one('.is-fs12').string='not-a-number'
    elif mutation=='row':row.td.decompose()
    else:row.append(BeautifulSoup('<table><tr><td>x</td></tr></table>','html.parser'))
    assert inspect(snap(body=str(soup).encode())).state=='FAIL'


def test_duplicate_snapshots_not_last_write_wins():
    with pytest.raises(CompletionError):assess_postrace_day('2026-09-18',(snap(),snap()),now=NOW)


@pytest.mark.parametrize('bad',[None,[],(None,),('PASS',)])
def test_freeform_pass_or_wrong_set_type_rejected(bad):
    with pytest.raises(CompletionError):assess_postrace_day('2026-09-18',bad,now=NOW)


def test_aggregation_retains_failures_and_unverified_missing_races():
    r=assess_postrace_day('2026-09-18',(snap(body_sha256='0'*64),),now=NOW)
    assert r['state']=='FAIL'
    assert sum(x['state']=='UNVERIFIED' for x in r['result_publications'])==11
