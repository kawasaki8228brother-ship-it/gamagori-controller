"""Runtime-call-path integration, using explicitly mocked HTTP only."""
import asyncio
import datetime as dt
import itertools
import logging
import hashlib

import httpx
import pytest

import odds_bridge
import parsers
from official import OfficialDataFetcher
from parsers import ParserError
from models import JST, OfficialRaceInfo, RaceStatus
from state_machine import RaceStateMachine
from repositories import MockBaselineRepository, SQLiteStateRepository
from airtable import DryRunAirtableAdapter
from test_v11_beforeinfo import fixture as beforeinfo_fixture

# The connected parser uses the semantic official-layout fixture; assertions unchanged.
BEFORE_HTML = beforeinfo_fixture()
from test_v11_candidate import matrix, explicit

ACQUIRED='2026-09-18T18:40:00+09:00'
URL='https://www.boatrace.jp/owpc/pc/race/odds3t?hd=20260918&jcd=07&rno=8'


@pytest.mark.parametrize('layout',['matrix','explicit','reverse'])
def test_bridge_preserves_complete_odds_without_market_normalization(layout,caplog):
    html=explicit() if layout=='explicit' else matrix(firsts=(6,5,4,3,2,1) if layout=='reverse' else (1,2,3,4,5,6))[0]
    with caplog.at_level(logging.INFO):
        values,evidence=odds_bridge.parse_c_odds(html,URL,ACQUIRED)
    assert set(values)=={'-'.join(map(str,p)) for p in itertools.permutations(range(1,7),3)}
    assert values['1-2-3']==(12.3 if layout=='explicit' else 123.1)
    assert evidence.url==URL and evidence.acquired_at==ACQUIRED
    assert evidence.status=='OK' and evidence.parser_status.startswith('C_ODDS_STRICT120_V1:')
    assert hashlib.sha256(html.encode()).hexdigest() in caplog.text
    assert 'decoded_text_sha256' in caplog.text


@pytest.mark.parametrize('count',[0,1,2,60,119])
def test_no_legacy_fallback_for_partial_tables(count,monkeypatch):
    def forbidden(*a,**k):raise AssertionError('legacy fallback must never run')
    monkeypatch.setattr(parsers,'parse_odds3t',forbidden)
    with pytest.raises(ParserError):odds_bridge.parse_c_odds(explicit(count),URL,ACQUIRED)


@pytest.mark.parametrize('bad',['NaN','inf','0','0.9','12.34','-1','1e2','10000.0','12.3abc'])
def test_bad_odds_rejected_through_bridge(bad):
    with pytest.raises(ParserError):odds_bridge.parse_c_odds(explicit().replace('12.3',bad,1),URL,ACQUIRED)


async def make_fetcher(odds_html=None, before_html=BEFORE_HTML, *, fail_endpoint=None):
    requests=[]
    def handle(request):
        requests.append(str(request.url))
        if request.url.path.endswith(fail_endpoint or '/never'):
            return httpx.Response(503,text='test error',request=request)
        body=before_html if request.url.path.endswith('beforeinfo') else odds_html
        return httpx.Response(200,text=body,headers={'content-type':'text/html; charset=utf-8'},request=request)
    fetcher=OfficialDataFetcher(max_retries=1)
    await fetcher.client.aclose()
    fetcher.client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
    return fetcher,requests


@pytest.mark.asyncio
async def test_actual_fetcher_path_selects_new_parser(monkeypatch):
    def forbidden(*a,**k):raise AssertionError('legacy parser called')
    monkeypatch.setattr(parsers,'parse_odds3t',forbidden)
    expected=matrix()[1]
    fetcher,requests=await make_fetcher(matrix()[0])
    try:r=await fetcher.fetch_live_data('20260918_GAM_08R')
    finally:await fetcher.close()
    assert len(requests)==2 and all('rno=8' in u for u in requests)
    assert r.odds_3t==expected and r.is_complete
    assert r.source_evidence['odds3t'].parser_status=='C_ODDS_STRICT120_V1:BOAT_MATRIX:120'
    assert len(r.exhibition_times)==6


@pytest.mark.asyncio
@pytest.mark.parametrize('bad_html',[explicit(2),explicit()+explicit(),'<h3>3連単</h3>4.5 8.2'])
async def test_odds_parse_failure_remains_incomplete(bad_html):
    fetcher,requests=await make_fetcher(bad_html)
    try:r=await fetcher.fetch_live_data('20260918_GAM_08R')
    finally:await fetcher.close()
    assert len(requests)==2 and r.odds_3t=={} and not r.is_complete
    assert 'odds_3t' in r.missing_fields and len(r.exhibition_times)==6
    assert r.source_evidence['odds3t'].status=='ERROR'


@pytest.mark.asyncio
async def test_good_odds_do_not_override_missing_beforeinfo():
    fetcher,requests=await make_fetcher(matrix()[0],before_html='<html>No exhibition</html>')
    try:r=await fetcher.fetch_live_data('20260918_GAM_08R')
    finally:await fetcher.close()
    assert len(r.odds_3t)==120 and not r.is_complete
    assert 'odds_3t' not in r.missing_fields and r.exhibition_times=={}


@pytest.mark.asyncio
@pytest.mark.parametrize('failed',['odds3t','beforeinfo'])
async def test_fetch_failure_does_not_erase_other_source(failed):
    fetcher,requests=await make_fetcher(matrix()[0],fail_endpoint=failed)
    try:r=await fetcher.fetch_live_data('20260918_GAM_08R')
    finally:await fetcher.close()
    assert len(requests)==2 and not r.is_complete
    if failed=='odds3t':assert len(r.exhibition_times)==6 and r.odds_3t=={}
    else:assert len(r.odds_3t)==120 and not r.exhibition_times


@pytest.mark.asyncio
async def test_shadow_state_path_with_mock_complete_inputs_and_local_store(tmp_path):
    # Positive remains synthetic after fixture migration.
    # Mock baselines/adapter never write production.
    now=dt.datetime(2026,9,18,18,40,tzinfo=JST)
    repo=SQLiteStateRepository(str(tmp_path/'shadow.sqlite'))
    fetcher,_=await make_fetcher(matrix()[0])
    sm=RaceStateMachine(repo,MockBaselineRepository(),fetcher,DryRunAirtableAdapter(repo),clock=lambda:now)
    info=OfficialRaceInfo(race_id='20260918_GAM_08R',official_deadline=now+dt.timedelta(minutes=7),
                          source_url='synthetic-fixture',acquired_at=now.isoformat())
    try:state=await sm.process_race(info.race_id,now,info)
    finally:await fetcher.close()
    assert state.status==RaceStatus.C_EVENT_DONE
    assert len(await repo.list_shadow_events(info.race_id))==1
