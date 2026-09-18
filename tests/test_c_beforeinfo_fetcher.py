"""Beforeinfo call-path tests. All HTTP is injected; no live recovery claim."""
import inspect
import json
import datetime as dt
import httpx
import pytest
import parsers
from official import OfficialDataFetcher
from closing import ClosingEvaluator
from test_v11_beforeinfo import fixture, STARTS
from test_v11_candidate import matrix

async def fetch(body, odds_status=200):
    def handle(request):
        before = request.url.path.endswith('beforeinfo')
        return httpx.Response(200 if before else odds_status, text=body if before else matrix()[0])
    f=OfficialDataFetcher(max_retries=1)
    await f.client.aclose()
    f.client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
    try:return await f.fetch_live_data('20260918_GAM_12R')
    finally:await f.close()

@pytest.mark.asyncio
@pytest.mark.parametrize('number',range(1,7))
async def test_marked_numeric_survives_fetcher_and_payload(number,monkeypatch):
    def forbidden(*a,**k):raise AssertionError('old beforeinfo called')
    monkeypatch.setattr(parsers,'parse_beforeinfo',forbidden)
    body=fixture().replace('>'+STARTS[number-1]+'<','>F.03<')
    d=await fetch(body)
    assert d.is_complete
    assert len(d.start_exhibition_readings)==6
    assert d.start_exhibition_readings[number].marker=='F'
    assert d.start_exhibition_readings[number].seconds_magnitude==0.03
    assert number not in d.start_exhibition_st
    *_,p=ClosingEvaluator.evaluate_closing_signals('20260918_GAM_12R',1,'test',None,None,d,'test')
    r=json.loads(json.dumps(p))['live_data']['start_exhibition_readings'][str(number)]
    assert r['marker']=='F' and r['raw']=='F.03'

@pytest.mark.asyncio
async def test_all_marked_numeric_complete_even_when_legacy_empty():
    body=fixture()
    for s in STARTS:body=body.replace('>'+s+'<','>F.03<')
    d=await fetch(body)
    assert d.is_complete and d.start_exhibition_st=={}
    assert len(d.start_exhibition_readings)==6

@pytest.mark.asyncio
@pytest.mark.parametrize('value',['F','L','','-'])
async def test_nonnumeric_or_missing_st_is_not_fabricated(value):
    d=await fetch(fixture().replace('>F.01<','>'+value+'<'))
    assert not d.is_complete  # Existing missing-fields policy is NOT relaxed.
    assert 2 not in d.start_exhibition_st
    if value in ('F','L'):
        assert d.start_exhibition_readings[2].marker==value
        assert d.start_exhibition_readings[2].seconds_magnitude is None
    else:assert 2 not in d.start_exhibition_readings

@pytest.mark.asyncio
async def test_good_beforeinfo_survives_failed_odds():
    d=await fetch(fixture(),503)
    assert not d.is_complete and len(d.start_exhibition_readings)==6
    assert d.start_exhibition_readings[2].raw=='F.01'
    assert d.odds_3t=={}

@pytest.mark.asyncio
async def test_bad_exhibition_preserves_other_section_but_blocks_completion():
    d=await fetch(fixture().replace('6.68','NaN',1))
    assert not d.is_complete and d.exhibition_times=={}
    assert len(d.start_exhibition_readings)==6

def test_no_st_count_in_existing_completion_expression():
    source=inspect.getsource(OfficialDataFetcher.fetch_live_data)
    assert 'start_exhibition_st' not in source.split('result.is_complete =',1)[1]
