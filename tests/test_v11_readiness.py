"""Stage7 pure-policy/section tests. Fixtures are authored, not live evidence."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from bs4 import BeautifulSoup
import pytest
from test_v11_beforeinfo import fixture, STARTS, TIMES
from v11_candidate.beforeinfo import BeforeInfoParseError, StartReading, parse_beforeinfo_snapshot
from v11_candidate.observation import (parse_beforeinfo_observation, coverage, ParseState,
                                       SectionReport, BeforeObservation, ObservationContractError)
from v11_candidate.readiness import (CheckState, EvidenceCheck, ReadinessContext,
                                     REQUIRED_CHECKS, assess_exhibition_readiness)


def context(**overrides):
    values = dict(expected_boats=(1,2,3,4,5,6), checks={key: EvidenceCheck(CheckState.PASS, ('synthetic:' + key,)) for key in REQUIRED_CHECKS})
    values.update(overrides)
    return ReadinessContext(**values)


def change_start(html, index, value):
    soup = BeautifulSoup(html, 'html.parser')
    soup.select('#st .table1_boatImage1Time')[index].string = value
    return str(soup)


def test_good_snapshot_preserves_existing_strict_output():
    html = fixture()
    result = parse_beforeinfo_observation(html)
    assert asdict(result.data) == asdict(parse_beforeinfo_snapshot(html))
    assert result.start_data_six
    assert all(report.state == ParseState.PARSED for report in result.sections.values())
    decision = assess_exhibition_readiness(result, context())
    assert decision.state == CheckState.PASS and decision.input_eligible
    assert decision.marked_numeric_boats == (2,3) and decision.marker_only_boats == ()
    assert decision.unused_inputs == ('weather', 'odds')
    assert not hasattr(decision, 'can_append') and not hasattr(decision, 'bet')


@pytest.mark.parametrize('index',range(6))
@pytest.mark.parametrize('marker',['F','L'])
def test_bare_marker_counts_as_observed_not_numeric(index, marker):
    obs = parse_beforeinfo_observation(change_start(fixture(), index, marker))
    caps = coverage(obs.data)
    assert caps['start_data_six'] and not caps['numeric_st_six']
    assert obs.data.starts[index+1] == StartReading(marker, marker, None)
    decision = assess_exhibition_readiness(obs, context())
    assert decision.input_eligible and decision.marker_only_boats == (index+1,)
    assert 'MARKER_ONLY_ST_QUALITATIVE_ONLY' in decision.warnings
    assert 'start_st_numeric_6boats' in obs.data.missing_fields
    # There is no score, direction, or automatic negative delta.
    assert not hasattr(decision, 'direction') and not hasattr(decision, 'score_delta')


@pytest.mark.parametrize('raw',['.00','F.00','F.01','L.99','Ｆ．０２'])
def test_numeric_marker_and_raw_are_not_lost(raw):
    obs = parse_beforeinfo_observation(change_start(fixture(), 0, raw))
    assert obs.data.starts[1].raw == raw
    assert obs.start_data_six and coverage(obs.data)['numeric_st_six']
    assert assess_exhibition_readiness(obs, context()).input_eligible


@pytest.mark.parametrize('raw',['','-','--','欠場'])
def test_blank_is_not_marker_only(raw):
    obs = parse_beforeinfo_observation(change_start(fixture(),0,raw))
    assert obs.data.entry_six and 1 not in obs.data.starts
    assert not obs.start_data_six
    assert not assess_exhibition_readiness(obs,context()).input_eligible


@pytest.mark.parametrize('index',range(6))
def test_invalid_exhibition_discards_whole_failed_section(index):
    html = fixture().replace(f'{TIMES[index]:.2f}', 'NaN', 1)
    obs = parse_beforeinfo_observation(html)
    assert obs.data.exhibition_times == {}
    assert obs.sections['exhibition'].state == ParseState.PARSE_FAILED
    assert obs.sections['exhibition'].source_status.value == 'SOURCE_PARSE_FAILED'
    assert obs.data.starts and obs.data.weather
    assert not assess_exhibition_readiness(obs, context()).input_eligible


@pytest.mark.parametrize('index',range(6))
def test_invalid_start_discards_prefix_not_exhibition(index):
    obs = parse_beforeinfo_observation(change_start(fixture(),index,'F-.01'))
    assert obs.data.starts == {} and obs.data.entry_courses == {}
    assert obs.sections['start'].state == ParseState.PARSE_FAILED
    assert obs.data.exhibition_times == dict(enumerate(TIMES,1))
    assert not assess_exhibition_readiness(obs,context()).input_eligible


@pytest.mark.parametrize('bad',['1km','nan','-1m','1m junk'])
def test_bad_optional_weather_does_not_erase_required_sections(bad):
    html=fixture().replace('>1m<','>'+bad+'<')
    with pytest.raises(BeforeInfoParseError):parse_beforeinfo_snapshot(html)
    obs = parse_beforeinfo_observation(html)
    assert obs.data.weather == {}  # even its previously staged reference is discarded
    assert obs.sections['weather'].state == ParseState.PARSE_FAILED
    decision = assess_exhibition_readiness(obs, context())
    assert decision.input_eligible and 'UNUSED_WEATHER_UNAVAILABLE' in decision.warnings
    assert obs.data.exhibition_times == dict(enumerate(TIMES,1))
    assert [obs.data.starts[i].raw for i in range(1,7)] == STARTS


def test_missing_weather_is_not_source_not_published():
    soup=BeautifulSoup(fixture(),'html.parser');soup.select_one('.weather1').decompose()
    obs = parse_beforeinfo_observation(str(soup))
    assert obs.sections['weather'].state == ParseState.MISSING
    assert obs.sections['weather'].source_status is None
    assert assess_exhibition_readiness(obs,context()).input_eligible


@pytest.mark.parametrize('section',['#ex','#st','.weather1'])
def test_duplicate_section_isolated(section):
    soup=BeautifulSoup(fixture(),'html.parser')
    obs=parse_beforeinfo_observation(str(soup)+str(soup.select_one(section)))
    failed={'#ex':'exhibition','#st':'start','.weather1':'weather'}[section]
    assert obs.sections[failed].state == ParseState.PARSE_FAILED
    assert all(r.state==ParseState.PARSED for name,r in obs.sections.items() if name!=failed)
    assert assess_exhibition_readiness(obs,context()).input_eligible == (failed=='weather')


@pytest.mark.parametrize('name',['_exhibition','_starts','_weather'])
def test_unexpected_section_exception_is_reported_and_isolated(monkeypatch,name):
    import v11_candidate.beforeinfo as parser
    def fail(*args):raise RuntimeError('private data not for error message')
    monkeypatch.setattr(parser,name,fail)
    obs=parse_beforeinfo_observation(fixture())
    key={'_exhibition':'exhibition','_starts':'start','_weather':'weather'}[name]
    assert obs.sections[key].error_code=='UNEXPECTED_SECTION_ERROR:RuntimeError'
    assert 'private data' not in json.dumps(asdict(obs),ensure_ascii=False)
    assert assess_exhibition_readiness(obs,context()).input_eligible == (key=='weather')


def test_course_gap_never_shifts_remaining_rows():
    soup=BeautifulSoup(fixture(),'html.parser');soup.select('#st tbody tr')[2].decompose()
    obs=parse_beforeinfo_observation(str(soup))
    assert obs.data.entry_courses=={} and obs.data.starts=={}
    assert not assess_exhibition_readiness(obs,context()).input_eligible


def test_non_frame_order_and_st_raw_retained():
    obs=parse_beforeinfo_observation(fixture((1,2,4,3,5,6)))
    assert obs.data.entry_courses[4]==3 and obs.data.entry_courses[3]==4
    assert assess_exhibition_readiness(obs,context()).input_eligible


def test_empty_page_preserves_missing_not_eligible():
    obs=parse_beforeinfo_observation('<html>6.68 .01 1 2 3</html>')
    assert all(r.state == ParseState.MISSING for r in obs.sections.values())
    assert assess_exhibition_readiness(obs,context()).state == CheckState.FAIL


@pytest.mark.parametrize('body',[None,b'abc',42,'x'*2_000_001])
def test_invalid_entire_body_rejected(body):
    with pytest.raises(BeforeInfoParseError):parse_beforeinfo_observation(body)


def test_inputs_without_verified_identity_freshness_are_not_eligible():
    obs=parse_beforeinfo_observation(fixture())
    decision=assess_exhibition_readiness(obs)
    assert decision.state == CheckState.UNVERIFIED and not decision.input_eligible
    assert decision.capabilities['start_data_six']


@pytest.mark.parametrize('key',REQUIRED_CHECKS)
@pytest.mark.parametrize('state',[CheckState.FAIL,CheckState.UNVERIFIED])
def test_each_required_evidence_gate_blocks(key,state):
    ctx=context();checks=dict(ctx.checks);checks[key]=EvidenceCheck(state)
    decision=assess_exhibition_readiness(parse_beforeinfo_observation(fixture()),replace(ctx,checks=checks))
    assert decision.state==state and not decision.input_eligible


@pytest.mark.parametrize('expected',[None,(),(1,2,3,4,5)])
def test_unknown_or_reduced_participant_set_never_inferred(expected):
    decision=assess_exhibition_readiness(parse_beforeinfo_observation(fixture()),context(expected_boats=expected))
    assert decision.state==CheckState.UNVERIFIED and not decision.input_eligible


@pytest.mark.parametrize('expected',[(True,2,3,4,5,6),(1,2,3,4,5,5),(1,2,3,4,5,7),[1,2,3,4,5,6]])
def test_invalid_authority_set_rejected(expected):
    decision=assess_exhibition_readiness(parse_beforeinfo_observation(fixture()),context(expected_boats=expected))
    assert decision.state==CheckState.FAIL and not decision.input_eligible


@pytest.mark.parametrize('state',['PASS',True,None,1])
def test_mistyped_gate_state_rejected(state):
    with pytest.raises(ValueError):EvidenceCheck(state,('e',))


def test_empty_reference_cannot_claim_pass():
    with pytest.raises(ValueError):EvidenceCheck(CheckState.PASS)
    with pytest.raises(ValueError):EvidenceCheck(CheckState.PASS,('',))


def test_parser_capabilities_cannot_be_forged_by_cached_flags():
    obs=parse_beforeinfo_observation(change_start(fixture(),0,''))
    obs.data.numeric_st_six=True;obs.data.entry_six=True;obs.data.exhibition_six=True
    assert not assess_exhibition_readiness(obs,context()).input_eligible


@pytest.mark.parametrize('reading',[StartReading('F','F',0.0),StartReading('F.01',None,0.01),StartReading('.01','F',0.01),StartReading('F.01','F',None)])
def test_raw_marker_magnitude_conflicts_are_not_eligible(reading):
    obs=parse_beforeinfo_observation(fixture());obs.data.starts[1]=reading
    with pytest.raises(ObservationContractError):coverage(obs.data)
    assert not assess_exhibition_readiness(obs,context()).input_eligible


@pytest.mark.parametrize('bad',[float('nan'),True,-1,12.0])
def test_invalid_exhibition_value_cannot_pass_coverage(bad):
    obs=parse_beforeinfo_observation(fixture());obs.data.exhibition_times[1]=bad
    assert not assess_exhibition_readiness(obs,context()).input_eligible


def test_optional_section_reference_is_not_start_freshness():
    obs=parse_beforeinfo_observation(fixture().replace('11R時点','1R時点'))
    checks=context().checks.copy();checks['START_FRESHNESS']=EvidenceCheck()
    decision=assess_exhibition_readiness(obs,context(checks=checks))
    assert obs.data.weather['reference_race_no']==1
    assert decision.state==CheckState.UNVERIFIED
    assert coverage(obs.data)['start_data_six']


def test_no_mutation_and_no_market_input():
    obs=parse_beforeinfo_observation(fixture());before=deepcopy(asdict(obs))
    ctx=context();first=assess_exhibition_readiness(obs,ctx);second=assess_exhibition_readiness(obs,ctx)
    assert first==second and asdict(obs)==before
    # No market arg or hidden fall-through to an odds-dependent policy.
    with pytest.raises(TypeError):assess_exhibition_readiness(obs,ctx,odds={})


def test_invalid_context_or_section_provenance_fails_closed():
    obs=parse_beforeinfo_observation(fixture())
    assert not assess_exhibition_readiness(obs,True).input_eligible
    obs.sections['start']=None
    assert not assess_exhibition_readiness(obs,context()).input_eligible


@pytest.mark.parametrize('state',['PARSED',True,None,1])
def test_section_state_type_is_not_coerced(state):
    with pytest.raises(ValueError):SectionReport(state)


def test_section_cannot_hide_known_error_as_success():
    with pytest.raises(ValueError):SectionReport(ParseState.PARSED,error_code='oops')
    with pytest.raises(ValueError):SectionReport(ParseState.PARSE_FAILED)


def test_success_does_not_claim_prediction_change_or_no_change():
    obs=parse_beforeinfo_observation(fixture())
    assert all(report.source_status is None for report in obs.sections.values())


def test_required_error_takes_precedence_but_does_not_hide_unverified():
    obs=parse_beforeinfo_observation(change_start(fixture(),0,''))
    decision=assess_exhibition_readiness(obs)
    assert decision.state==CheckState.FAIL
    assert any('UNVERIFIED' in reason for reason in decision.reasons)
