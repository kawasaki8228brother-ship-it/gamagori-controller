"""Authored roster fixtures: not captured bytes or ACTIVE source-contract evidence."""
import datetime as dt
from dataclasses import asdict
import hashlib
from bs4 import BeautifulSoup
import pytest
from v11_candidate.roster_semantics import (
    parse_listed_roster, RosterSemanticError, extract_listed_roster_semantics,
    LISTED_ROSTER_VALIDATOR, assess_roster_time_context)
from v11_candidate.participant_evidence import RaceIdentity, RosterSnapshot, inspect_participant_evidence
from v11_candidate.readiness import CheckState


def fixture(race=12):
    s='<html><head><title>出走表｜BOAT RACE オフィシャルウェブサイト</title></head><body>'
    s+='<div class="heading2_area"><img alt="蒲郡" src="/static_extra/pc/images/text_place2_07.png"></div>'
    s+='<ul class="tab2_tabs"><li class="is-active2"><span class="tab2_inner">9月18日<span>最終日</span></span></li></ul>'
    s+='<ul class="tab3_tabs"><li class="is-active"><span>出走表</span></li>'
    for role in ('odds3t','beforeinfo','pcexpect','myexpect','raceresult'):
        s+=f'<li><a href="/owpc/pc/race/{role}?hd=20260918&amp;jcd=07&amp;rno={race}">{role}</a></li>'
    s+='</ul><table id="nav"><thead><tr><th>レース</th>'
    for r in range(1,13):
        c='' if r==race else 'is-thColor2'
        s+=f'<th class="{c}"><a href="/owpc/pc/race/racelist?hd=20260918&amp;jcd=07&amp;rno={r}">{r}R</a></th>'
    s+='</tr></thead></table><table id="roster"><thead><tr><th rowspan="2">枠</th><th>ボートレーサー</th><th rowspan="2">成績</th></tr><tr><th>登録番号/級別<br>氏名<br>支部/出身地<br>年齢/体重</th></tr></thead>'
    for b in range(1,7):
        s+=f'<tbody><tr><td rowspan="4" class="is-boatColor{b}">{b}</td><td rowspan="4"><div class="is-fs11">{5000+b}/A1</div><div class="is-fs18"><a href="/owpc/pc/data/racersearch/profile?toban={5000+b}">試験　{b}</a></div></td><td>F</td></tr><tr><td>欠場</td></tr><tr><td>.02</td></tr><tr><td>1</td></tr></tbody>'
    return (s+'</table></body></html>').encode()


def mutate(body, selector, action):
    soup=BeautifulSoup(body,'html.parser');action(soup.select_one(selector));return str(soup).encode()


@pytest.mark.parametrize('r',[3,12])
def test_real_layout_shape_identifies_listing_but_never_active(r):
    b=fixture(r);p=parse_listed_roster(b)
    assert p.body_identity==RaceIdentity('2026-09-18','07',r)
    assert [x.registration_no for x in p.slots]==[str(5000+i) for i in range(1,7)]
    assert p.six_slots_present and not p.active_status_verified and p.source_effective_at is None
    assert p.body_sha256==hashlib.sha256(b).hexdigest()
    assert all(x.listing_state=='LISTED_STATUS_UNVERIFIED' for x in p.slots)


def test_stage8_adapter_never_upgrades_listing_to_active():
    x=extract_listed_roster_semantics(fixture());assert all(state=='UNKNOWN' for _,state in x.slot_states)
    snap=RosterSnapshot('synthetic','https://www.boatrace.jp/owpc/pc/race/racelist?hd=20260918&jcd=07&rno=12','https://www.boatrace.jp/owpc/pc/race/racelist?hd=20260918&jcd=07&rno=12','2026-09-18T09:00:00Z',200,'text/html',fixture(),hashlib.sha256(fixture()).hexdigest())
    p=inspect_participant_evidence(snap,RaceIdentity('2026-09-18','07',12),now=dt.datetime(2026,9,18,9,1,tzinfo=dt.timezone.utc),validator=LISTED_ROSTER_VALIDATOR)
    assert p.state==CheckState.UNVERIFIED and p.expected_boats is None and p.verify_binding()
    assert p.reasons==('ROSTER_SLOT_STATUS_UNKNOWN',)


@pytest.mark.parametrize('body',[b'',b'\xff',b'X'*2_000_001,None,'<html/>'])
def test_invalid_body_rejected(body):
    with pytest.raises(RosterSemanticError):parse_listed_roster(body)


@pytest.mark.parametrize('old,new',[
 ('出走表｜BOAT RACE','結果｜BOAT RACE'),
 ('alt="蒲郡"','alt="浜名湖"'),
 ('text_place2_07.png','text_place2_06.png'),
 ('9月18日','9月17日'),
 ('class="is-active"><span>出走表','class="is-active"><span>直前情報'),
 ('<title>','<title>bad'),
])
def test_visible_body_identity_conflicts_rejected(old,new):
    with pytest.raises((ValueError,)):parse_listed_roster(fixture().replace(old.encode(),new.encode(),1))


@pytest.mark.parametrize('href',[
 'https://www.boatrace.jp.evil.example/owpc/pc/race/odds3t?hd=20260918&jcd=07&rno=12',
 'https://name@www.boatrace.jp/owpc/pc/race/odds3t?hd=20260918&jcd=07&rno=12',
 '//www.boatrace.jp/owpc/pc/race/odds3t?hd=20260918&jcd=07&rno=12',
 'http://www.boatrace.jp/owpc/pc/race/odds3t?hd=20260918&jcd=07&rno=12',
 '/owpc/pc/race/odds3t?hd=20260918&jcd=07&rno=12&rno=12',
 '/owpc/pc/race/odds3t?hd=20260917&jcd=07&rno=12',
 '/owpc/pc/race/odds3t?hd=20260918&jcd=06&rno=12',
 '/owpc/pc/race/odds3t?hd=20260918&jcd=07&rno=3',
 '/owpc/pc/race/odds3t?hd=20260918&jcd=07&rno=12#x',
 '/owpc/pc/race/odds3t?hd=20260918&jcd=07&rno=12&x=1',
 '/owpc/pc/race/odds3t?hd=20260230&jcd=07&rno=12',
])
def test_body_menu_links_must_all_agree(href):
    b=mutate(fixture(),'.tab3_tabs li a',lambda a:a.__setitem__('href',href))
    with pytest.raises(ValueError):parse_listed_roster(b)


@pytest.mark.parametrize('selector',['title','.heading2_area img','.tab2_tabs li','.tab3_tabs','#nav','#roster'])
def test_required_body_sections_missing(selector):
    with pytest.raises(ValueError):parse_listed_roster(mutate(fixture(),selector,lambda n:n.decompose()))


@pytest.mark.parametrize('selector',['title','.heading2_area','.tab2_tabs','.tab3_tabs','#nav','#roster'])
def test_duplicate_identity_or_roster_sections(selector):
    s=BeautifulSoup(fixture(),'html.parser');s.body.append(BeautifulSoup(str(s.select_one(selector)),'html.parser'))
    with pytest.raises(ValueError):parse_listed_roster(str(s).encode())


@pytest.mark.parametrize('n',[1,3,6])
def test_missing_slot_does_not_shrink_active_set(n):
    b=mutate(fixture(),f'#roster tbody:nth-of-type({n})',lambda x:x.decompose())
    p=parse_listed_roster(b);assert not p.six_slots_present and len(p.slots)==5
    assert all(s=='UNKNOWN' for _,s in extract_listed_roster_semantics(b).slot_states)


def test_history_fl_withdrawal_does_not_classify_current_slot():
    p=parse_listed_roster(fixture());assert len(p.slots)==6 and not p.active_status_verified


@pytest.mark.parametrize('selector,attribute,value',[
 ('#roster tbody td','class',['is-boatColor6']),
 ('#roster tbody .is-fs18 a','href','/owpc/pc/data/racersearch/profile?toban=9999'),
 ('#nav th:last-child','class',['is-thColor2']),
 ('#nav th:nth-child(4)','class',[]),
])
def test_row_identity_and_active_race_conflicts(selector,attribute,value):
    with pytest.raises(ValueError):parse_listed_roster(mutate(fixture(),selector,lambda x:x.__setitem__(attribute,value)))


def test_duplicate_boat_or_racer_rejected():
    s=BeautifulSoup(fixture(),'html.parser');s.select_one('#roster').append(BeautifulSoup(str(s.select_one('#roster tbody')),'html.parser'))
    with pytest.raises(ValueError):parse_listed_roster(str(s).encode())


def test_name_missing_rejected():
    with pytest.raises(ValueError):parse_listed_roster(mutate(fixture(),'#roster .is-fs18 a',lambda x:x.clear()))


def test_nested_table_rejected():
    s=BeautifulSoup(fixture(),'html.parser');s.select_one('#roster td').append(s.new_tag('table'))
    with pytest.raises(ValueError):parse_listed_roster(str(s).encode())


@pytest.mark.parametrize('row',[0,1,3])
def test_removed_row_not_reinterpreted(row):
    s=BeautifulSoup(fixture(),'html.parser');s.select('#roster tbody')[0].select('tr')[row].decompose()
    with pytest.raises(ValueError):parse_listed_roster(str(s).encode())


def test_original_bytes_not_modified():
    b=fixture();h=hashlib.sha256(b).hexdigest();parse_listed_roster(b);assert hashlib.sha256(b).hexdigest()==h


@pytest.mark.parametrize('acquired', ['2026-09-18T09:00:00Z','2026-09-17T09:00:00Z'])
def test_recent_or_old_read_does_not_prove_source_effective_time(acquired):
    r=assess_roster_time_context(RaceIdentity('2026-09-18','07',12),acquired,decision_at=dt.datetime(2026,9,18,9,1,tzinfo=dt.timezone.utc))
    assert r.state==CheckState.UNVERIFIED and not r.usable_at_decision and r.source_effective_at is None


def test_postdecision_recapture_cannot_validate_historical_decision():
    r=assess_roster_time_context(RaceIdentity('2026-09-18','07',12),'2026-09-18T17:44:54Z',decision_at=dt.datetime.fromisoformat('2026-09-18T20:44:00+09:00'))
    assert r.state==CheckState.FAIL and 'CAPTURE_AFTER_REQUESTED_DECISION' in r.reasons


@pytest.mark.parametrize('acquired',['2026-09-18T10:00:00','bad',None,123])
def test_invalid_acquisition_time_rejected(acquired):
    with pytest.raises(ValueError):assess_roster_time_context(RaceIdentity('2026-09-18','07',12),acquired,decision_at=dt.datetime.now(dt.timezone.utc))


def test_utc_date_does_not_hide_jst_day_change():
    r=assess_roster_time_context(RaceIdentity('2026-09-18','07',12),'2026-09-18T17:44:54Z',decision_at=dt.datetime.fromisoformat('2026-09-18T18:00:00Z'))
    assert 'CAPTURE_NOT_ON_TARGET_DAY' in r.reasons and r.state==CheckState.UNVERIFIED
