"""Offline clock-contract tests. No network or production data access."""
import datetime as dt
import hashlib
import json

import pytest
from airtable import DryRunAirtableAdapter
from closing import ClosingEvaluator
from models import JST, RaceStatus
from repositories import MockBaselineRepository, SQLiteStateRepository
from state_machine import RaceStateMachine
from test_state_machine import FakeFetcher, info

START = dt.datetime(2026, 9, 17, 15, 0, tzinfo=JST)
DEADLINE = START + dt.timedelta(minutes=7)
RID = '20260917_GAM_08R'


class Clock:
    def __init__(self, value=START):
        self.value = value
    def __call__(self):
        return self.value


@pytest.fixture
def repo(tmp_path):
    return SQLiteStateRepository(str(tmp_path / 'isolated_clock.db'))


def machine(repo, clock):
    return RaceStateMachine(repo, MockBaselineRepository(), FakeFetcher(),
                            DryRunAirtableAdapter(repo), clock=clock)


@pytest.mark.asyncio
@pytest.mark.parametrize('micros,emitted',[(-1,True),(0,False),(1,False)])
async def test_strict_deadline_after_acquisition(repo, micros, emitted):
    clock=Clock()
    class SlowFetcher(FakeFetcher):
        async def fetch_live_data(self,race_id):
            data=await super().fetch_live_data(race_id)
            clock.value=DEADLINE+dt.timedelta(microseconds=micros)
            return data
    sm=machine(repo,clock);sm.fetcher=SlowFetcher()
    state=await sm.process_race(RID,START,info(RID,DEADLINE))
    assert state.status==(RaceStatus.C_EVENT_DONE if emitted else RaceStatus.SAFE_STOP)
    assert len(await repo.list_shadow_events(RID))==int(emitted)


@pytest.mark.asyncio
async def test_baseline_read_crossing_deadline_is_rejected(repo):
    clock=Clock()
    class SlowBaseline(MockBaselineRepository):
        async def get_latest_baseline_ids(self,race_id):
            clock.value=DEADLINE
            return await super().get_latest_baseline_ids(race_id)
    sm=machine(repo,clock);sm.baseline_repo=SlowBaseline()
    assert (await sm.process_race(RID,START,info(RID,DEADLINE))).status==RaceStatus.SAFE_STOP
    assert await repo.list_shadow_events(RID)==[]


@pytest.mark.asyncio
@pytest.mark.parametrize('value',[None,'2026-09-17T15:00:00+09:00',
                                  START.replace(tzinfo=None),START-dt.timedelta(microseconds=1)])
async def test_bad_clock_fails_closed(repo,value):
    state=await machine(repo,Clock(value)).process_race(RID,START,info(RID,DEADLINE))
    assert state.status==RaceStatus.SAFE_STOP
    assert await repo.list_shadow_events(RID)==[]


@pytest.mark.asyncio
async def test_clock_exception_fails_closed(repo):
    def broken():raise RuntimeError('clock failure')
    state=await machine(repo,broken).process_race(RID,START,info(RID,DEADLINE))
    assert state.status==RaceStatus.SAFE_STOP
    assert await repo.list_shadow_events(RID)==[]


@pytest.mark.asyncio
@pytest.mark.parametrize('after',[DEADLINE,DEADLINE+dt.timedelta(seconds=1),START-dt.timedelta(seconds=1)])
async def test_evaluation_delay_or_clock_regression_cannot_append(repo,monkeypatch,after):
    clock=Clock();original=ClosingEvaluator.evaluate_closing_signals
    def delayed(**kw):
        result=original(**kw);clock.value=after;return result
    monkeypatch.setattr(ClosingEvaluator,'evaluate_closing_signals',staticmethod(delayed))
    state=await machine(repo,clock).process_race(RID,START,info(RID,DEADLINE))
    assert state.status==RaceStatus.SAFE_STOP
    assert await repo.list_shadow_events(RID)==[]


@pytest.mark.asyncio
async def test_utc_clock_and_payload_hash(repo):
    stamp=START+dt.timedelta(seconds=4)
    state=await machine(repo,Clock(stamp.astimezone(dt.timezone.utc))).process_race(RID,START,info(RID,DEADLINE))
    assert state.status==RaceStatus.C_EVENT_DONE
    event=(await repo.list_shadow_events(RID))[0]
    assert dt.datetime.fromisoformat(event['observed_at'])==stamp
    payload=json.loads(event['payload_json'])
    body=json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
    assert hashlib.sha256(body.encode()).hexdigest()==event['payload_hash']


@pytest.mark.asyncio
async def test_default_clock_is_real_not_polled_timestamp(repo):
    # Current wall time and an older supplied poll time remain distinct.
    before=dt.datetime.now(JST);poll=before-dt.timedelta(seconds=2)
    rid=before.strftime('%Y%m%d')+'_GAM_08R'
    sm=RaceStateMachine(repo,MockBaselineRepository(),FakeFetcher(),DryRunAirtableAdapter(repo))
    state=await sm.process_race(rid,poll,info(rid,before+dt.timedelta(minutes=7)))
    after=dt.datetime.now(JST)
    assert state.status==RaceStatus.C_EVENT_DONE
    event=(await repo.list_shadow_events(rid))[0]
    assert before<=dt.datetime.fromisoformat(event['observed_at'])<=after
    assert dt.datetime.fromisoformat(event['observed_at'])!=poll


def test_non_callable_clock_rejected(repo):
    with pytest.raises(TypeError):machine(repo,0)
