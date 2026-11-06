"""Stage11 selection regression tests; all positive withdrawal cases synthetic."""
from dataclasses import FrozenInstanceError
import hashlib
import inspect

from bs4 import BeautifulSoup
import pytest

from test_v11_beforeinfo import fixture
from v11_candidate import beforeinfo as parser
from v11_candidate import observation, withdrawal_observation, table_selection


CASES = ('normal', 'missing_ex', 'missing_st', 'duplicate_ex', 'duplicate_st',
         'unrelated_prefix', 'nested_prefix', 'nested_ex', 'nested_st',
         'reverse_tables', 'ex_header_changed', 'st_header_changed',
         'no_ex_thead', 'no_st_thead', 'notes_only', 'both_labels',
         'ex_withdrawal', 'st_withdrawal', 'late_ex_error', 'late_st_error')


def case_html(case):
    soup = BeautifulSoup(fixture(), 'html.parser')
    ex, st = soup.select_one('#ex'), soup.select_one('#st')
    if case == 'missing_ex': ex.decompose()
    elif case == 'missing_st': st.decompose()
    elif case == 'duplicate_ex': soup.append(BeautifulSoup(str(ex), 'html.parser'))
    elif case == 'duplicate_st': soup.append(BeautifulSoup(str(st), 'html.parser'))
    elif case == 'unrelated_prefix': return '<table><tr><td>欠場 展示タイム ST</td></tr></table>' + str(soup)
    elif case == 'nested_prefix': return '<table><tr><td><table><thead><tr><th>枠</th><th>展示タイム</th></tr></thead></table></td></tr></table>' + str(soup)
    elif case in ('nested_ex', 'nested_st'):
        target = ex if case == 'nested_ex' else st
        target.wrap(soup.new_tag('td')).wrap(soup.new_tag('tr')).wrap(soup.new_tag('table'))
    elif case == 'reverse_tables': st.extract(); soup.insert(0, st)
    elif case == 'ex_header_changed':
        ex.select('th')[2].string = '似た別タイム'
    elif case == 'st_header_changed': st.select('th')[0].string = '前走スタート展示'
    elif case == 'no_ex_thead': ex.thead.unwrap()
    elif case == 'no_st_thead': st.thead.unwrap()
    elif case == 'notes_only': return '<p>枠 展示タイム スタート展示 欠場</p><table><tr><td>6.68</td></tr></table>'
    elif case == 'both_labels':
        extra = soup.new_tag('th'); extra.string = 'スタート展示'; ex.thead.tr.append(extra)
    elif case == 'ex_withdrawal': ex.select('tbody')[1].select('td')[2].string = '欠場'
    elif case == 'st_withdrawal': st.select('.table1_boatImage1Time')[1].string = '欠場'
    elif case == 'late_ex_error':
        ex.select('tbody')[0].select('td')[2].string = '欠場'
        ex.select('tbody')[-1].select('td')[2].string = 'INVALID'
    elif case == 'late_st_error':
        st.select('.table1_boatImage1Time')[0].string = '欠場'
        st.select('.table1_boatImage1Time')[-1].string = 'INVALID'
    return str(soup)


def descriptors(selected):
    return {name: [(x.absolute_index, hashlib.sha256(str(x.table).encode()).hexdigest())
                   for x in tables] for name, tables in selected.items()}


def legacy_reference(soup):
    # Test-only reference for the Stage10 algorithm, not a second runtime selector.
    selected = {'exhibition': [], 'start': []}
    for index, table in enumerate(soup.find_all('table'), 1):
        if table.find_parent('table') is not None: continue
        head = table.find('thead', recursive=False)
        labels = {parser.label(c) for c in head.find_all('th')} if head else set()
        if {'枠', '展示タイム'} <= labels: selected['exhibition'].append((index, table))
        if 'スタート展示' in labels: selected['start'].append((index, table))
    return {name: [(i, hashlib.sha256(str(t).encode()).hexdigest()) for i,t in values]
            for name,values in selected.items()}


@pytest.mark.parametrize('case', CASES)
def test_selection_preserves_legacy_identity_index_and_nonmutation(case):
    soup = BeautifulSoup(case_html(case), 'html.parser')
    before = str(soup)
    result = table_selection.select_beforeinfo_tables(soup)
    assert descriptors(result) == legacy_reference(soup)
    assert str(soup) == before
    all_tables = soup.find_all('table')
    for choices in result.values():
        assert isinstance(choices, tuple)
        for choice in choices:
            assert choice.table is all_tables[choice.absolute_index-1]


@pytest.mark.parametrize('case', CASES)
def test_both_consumers_call_shared_selector_and_same_tables_reach_helpers(monkeypatch, case):
    original = table_selection.select_beforeinfo_tables
    calls, inputs = [], []
    phase = ['observation']
    def select(soup):
        result = original(soup); calls.append(descriptors(result)); return result
    monkeypatch.setattr(table_selection, 'select_beforeinfo_tables', select)
    for name in ('_exhibition', '_starts'):
        helper = getattr(parser, name)
        def record(table, staged, *, name=name, helper=helper):
            inputs.append((phase[0], name, hashlib.sha256(str(table).encode()).hexdigest()))
            return helper(table, staged)
        monkeypatch.setattr(parser, name, record)
    html = case_html(case)
    observation.parse_beforeinfo_observation(html)
    phase[0] = 'scanner'
    withdrawal_observation.scan_withdrawal_text(html.encode())
    assert len(calls) == 2 and calls[0] == calls[1]
    assert [(n,h) for p,n,h in inputs if p=='observation'] == [(n,h) for p,n,h in inputs if p=='scanner']


def test_nested_prefix_preserves_absolute_signal_locator():
    html = '<table><tr><td><table></table></td></tr></table>' + case_html('ex_withdrawal')
    scan = withdrawal_observation.scan_withdrawal_text(html.encode())
    assert len(scan.signals) == 1 and scan.signals[0].boat == 2
    assert scan.signals[0].locator.startswith('table[3]/')
    assert scan.signals[0].body_sha256 == hashlib.sha256(html.encode()).hexdigest()
    assert not scan.official_status_verified


def test_duplicate_matches_are_not_silently_first_selected():
    soup = BeautifulSoup(case_html('duplicate_ex'), 'html.parser')
    assert len(table_selection.select_beforeinfo_tables(soup)['exhibition']) == 2
    obs = observation.parse_beforeinfo_observation(str(soup))
    scan = withdrawal_observation.scan_withdrawal_text(str(soup).encode())
    assert obs.sections['exhibition'].state.value == 'PARSE_FAILED'
    assert scan.sections[0].state == 'PARSE_FAILED' and not scan.signals


def test_consumers_cannot_silently_ignore_shared_selection(monkeypatch):
    monkeypatch.setattr(table_selection, 'select_beforeinfo_tables', lambda soup: {'exhibition': (), 'start': ()})
    obs = observation.parse_beforeinfo_observation(fixture())
    scan = withdrawal_observation.scan_withdrawal_text(fixture().encode())
    assert obs.sections['exhibition'].state.value == obs.sections['start'].state.value == 'MISSING'
    assert all(x.state == 'MISSING' for x in scan.sections)


@pytest.mark.parametrize('invalid', [None, '', {}, 1, BeautifulSoup('<table></table>', 'html.parser').table])
def test_selector_requires_document(invalid):
    with pytest.raises(TypeError): table_selection.select_beforeinfo_tables(invalid)


def test_selection_container_is_frozen_but_not_a_security_boundary():
    match = table_selection.select_beforeinfo_tables(BeautifulSoup(fixture(),'html.parser'))['exhibition'][0]
    with pytest.raises(FrozenInstanceError): match.absolute_index = 99


def test_no_local_table_discovery_loops_in_consumers():
    for fn in (observation.parse_beforeinfo_observation, withdrawal_observation.scan_withdrawal_text):
        source = inspect.getsource(fn)
        assert 'table_selection.select_beforeinfo_tables(soup)' in source
        assert "find_all('table')" not in source
