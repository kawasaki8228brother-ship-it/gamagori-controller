"""Authored and deliberately mutated fixtures; no real withdrawal proven."""
from dataclasses import asdict, FrozenInstanceError
from hashlib import sha256
import inspect
import json
from bs4 import BeautifulSoup
import pytest
from test_v11_beforeinfo import fixture
from v11_candidate.beforeinfo import BeforeInfoParseError, blank, parse_start
from v11_candidate.observation import parse_beforeinfo_observation, coverage
from v11_candidate.readiness import assess_exhibition_readiness, CheckState
from v11_candidate.withdrawal_observation import scan_withdrawal_text


def changed(section, b=2, value='欠場'):
    soup=BeautifulSoup(fixture(),'html.parser')
    if section=='exhibition':
        cell=soup.select('#ex > tbody')[b-1].select('tr')[0].find_all('td',recursive=False)[2]
    else:
        cell=soup.select('#st .table1_boatImage1Time')[b-1]
    cell.string=value
    return soup


def scan(html):
    return scan_withdrawal_text(str(html).encode('utf-8'))


def section_state(result, name):
    return next(s.state for s in result.sections if s.section==name)


@pytest.mark.parametrize('section',['exhibition','start'])
@pytest.mark.parametrize('boat',range(1,7))
def test_exact_marker_keeps_boat_section_raw_and_digest(section,boat):
    html=str(changed(section,boat)); result=scan(html)
    assert len(result.signals)==1
    marker=result.signals[0]
    assert (marker.boat,marker.section,marker.raw_text,marker.normalized_text)==(boat,section,'欠場','欠場')
    assert marker.body_sha256==result.body_sha256==sha256(html.encode()).hexdigest()
    assert marker.locator.startswith('table[')
    assert marker.kind=='WITHDRAWAL_TEXT_OBSERVED'
    assert not result.official_status_verified and not result.page_identity_verified
    assert result.source_effective_at is None


@pytest.mark.parametrize('value',['','-','--','―','—','ー'])
@pytest.mark.parametrize('section',['exhibition','start'])
def test_blanks_are_not_withdrawals(section,value):
    assert scan(changed(section,value=value)).signals==()


@pytest.mark.parametrize('value',['F','L','F.01','L.99','.00','.02','Ｆ．０２'])
def test_start_markers_not_withdrawal(value):
    assert scan(changed('start',value=value)).signals==()


@pytest.mark.parametrize('value',['欠場なし','欠場予定','前走欠場','欠場取消','欠場?','欠 場','出走取消','中止'])
@pytest.mark.parametrize('section',['exhibition','start'])
def test_substrings_and_unreviewed_synonyms_are_not_promoted(section,value):
    result=scan(changed(section,value=value))
    assert result.signals==()
    assert section_state(result,section)=='PARSE_FAILED'


@pytest.mark.parametrize('value',[' 欠場 ','\n欠場\t','\u3000欠場\u3000'])
@pytest.mark.parametrize('section',['exhibition','start'])
def test_outer_space_normalized_but_original_text_kept(section,value):
    result=scan(changed(section,value=value))
    assert result.signals[0].raw_text==value
    assert result.signals[0].normalized_text=='欠場'


@pytest.mark.parametrize('location',['previous_result','weather','page_note','other_table'])
def test_other_locations_never_become_current_race_withdrawal(location):
    soup=BeautifulSoup(fixture(),'html.parser')
    if location=='previous_result':
        soup.select('#ex > tbody')[0].select('tr')[-1].find_all('td')[-1].string='欠場'
    elif location=='weather':
        soup.select_one('.weather1_bodyUnitLabelData').string='欠場'
    elif location=='page_note':
        soup.append(BeautifulSoup('<p>2号艇 欠場</p>','html.parser'))
    else:
        soup.append(BeautifulSoup('<table><tr><td>2号艇</td><td>欠場</td></tr></table>','html.parser'))
    assert scan(soup).signals==()


def test_same_boat_marked_in_both_sections_kept_as_two_observations():
    soup=changed('exhibition',2)
    soup.select('#st .table1_boatImage1Time')[1].string='欠場'
    result=scan(soup)
    assert {(m.boat,m.section) for m in result.signals}=={(2,'exhibition'),(2,'start')}
    assert result.coexisting_observations==()
    assert not result.official_status_verified


def test_exhibition_rowspan_marker_only_recorded_once():
    result=scan(changed('exhibition',2))
    assert len(result.signals)==1
    assert result.coexisting_observations==('BOAT_2:WITHDRAWAL_TEXT_AND_START_READING',)


def test_numeric_exhibition_and_start_marker_both_retained_without_resolution():
    result=scan(changed('start',2))
    assert result.coexisting_observations==('BOAT_2:WITHDRAWAL_TEXT_AND_NUMERIC_EXHIBITION',)


@pytest.mark.parametrize('section',['exhibition','start'])
def test_duplicate_table_discards_only_ambiguous_section(section):
    soup=changed(section)
    selector='#ex' if section=='exhibition' else '#st'
    result=scan(str(soup)+str(soup.select_one(selector)))
    assert result.signals==()
    assert section_state(result,section)=='PARSE_FAILED'
    other='start' if section=='exhibition' else 'exhibition'
    assert section_state(result,other)=='SCANNED'


def test_late_malformed_exhibition_discards_earlier_marker():
    soup=changed('exhibition',1)
    soup.select('#ex > tbody')[-1].select('tr')[0].find_all('td',recursive=False)[2].string='NaN'
    result=scan(soup)
    assert result.signals==() and section_state(result,'exhibition')=='PARSE_FAILED'


def test_late_malformed_start_discards_earlier_marker():
    soup=changed('start',1)
    soup.select('#st .table1_boatImage1Time')[-1].string='NaN'
    result=scan(soup)
    assert result.signals==() and section_state(result,'start')=='PARSE_FAILED'


def test_invalid_exhibition_does_not_erase_independent_start_signal():
    soup=changed('start',2)
    soup.select('#ex > tbody')[0].select('tr')[0].find_all('td',recursive=False)[2].string='NaN'
    result=scan(soup)
    assert len(result.signals)==1 and result.signals[0].section=='start'
    assert section_state(result,'exhibition')=='PARSE_FAILED'


def test_invalid_optional_weather_does_not_erase_any_marker():
    soup=changed('start',2)
    soup.select_one('.weather1_bodyUnitLabelData').string='nonsense'
    assert len(scan(soup).signals)==1


def test_removed_start_row_never_assigns_shifted_course_or_boat():
    soup=changed('start',4)
    soup.select('#st tbody tr')[0].decompose()
    result=scan(soup)
    assert result.signals==() and section_state(result,'start')=='PARTIAL'


def test_missing_boat_with_marker_cannot_be_assigned():
    soup=changed('start',2)
    soup.select('#st .table1_boatImage1Number')[1].string=''
    result=scan(soup)
    assert result.signals==() and section_state(result,'start')=='PARSE_FAILED'


def test_no_tables_is_missing_not_evidence_of_no_withdrawals():
    result=scan('<p>欠場</p>')
    assert result.signals==()
    assert all(s.state=='MISSING' for s in result.sections)
    assert not result.official_status_verified


def test_normal_page_has_no_signal_but_no_active_status():
    result=scan(fixture())
    assert not result.signals and all(s.state=='SCANNED' for s in result.sections)
    assert not result.official_status_verified
    assert not hasattr(result,'expected_boats') and not hasattr(result,'input_eligible')


@pytest.mark.parametrize('body',[None,'欠場',bytearray(b'abc'),b'x'*2_000_001,b'\xff'])
def test_bad_body_type_size_or_encoding_rejected(body):
    with pytest.raises(BeforeInfoParseError):scan_withdrawal_text(body)


def test_result_roundtrips_json_and_signal_is_immutable():
    result=scan(changed('start'))
    assert json.loads(json.dumps(asdict(result),ensure_ascii=False))['signals'][0]['raw_text']=='欠場'
    with pytest.raises(FrozenInstanceError):result.signals[0].boat=3


def test_scan_leaves_legacy_parser_and_readiness_unchanged():
    html=str(changed('start'))
    before=parse_beforeinfo_observation(html)
    stored=asdict(before)
    scan(html)
    assert asdict(parse_beforeinfo_observation(html))==stored
    assert not coverage(before.data)['start_data_six']
    assert assess_exhibition_readiness(before).state==CheckState.FAIL
    assert blank('欠場') and parse_start('欠場') is None


def test_no_authority_or_acceptance_override_parameters():
    assert set(inspect.signature(scan_withdrawal_text).parameters)=={'body'}
