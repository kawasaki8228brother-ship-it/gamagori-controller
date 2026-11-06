"""Synthetic review counterexamples; not historical runtime evidence."""
import pytest
from v11_candidate.odds import parse_trifecta, OddsParseError
from v11_candidate.contracts import ContractError
from test_v11_candidate import matrix, explicit, deadline, reader, row


@pytest.mark.parametrize('header',[(1,2,3,4,5,6),(6,5,4,3,2,1)])
def test_matrix_multiple_first_boat_headers_fail_closed(header):
    html,_=matrix()
    extra='<tr>'+''.join(f'<th colspan="3">{b}</th>' for b in header)+'</tr>'
    with pytest.raises(OddsParseError):
        parse_trifecta(html.replace('</thead>',extra+'</thead>'))


@pytest.mark.parametrize('extra',[
    '<tr><td>1-2-7</td><td>12.3</td></tr>',
    '<tr><td>1-2-3</td><td>12.3</td><td>99</td></tr>',
    '<tr><td>1-2</td><td>12.3</td></tr>',
])
def test_malformed_extra_data_rows_do_not_hide_behind_120_valid_entries(extra):
    with pytest.raises(OddsParseError):
        parse_trifecta(explicit().replace('</table>',extra+'</table>'))


@pytest.mark.parametrize('value',[1,'false','true',[],{},None])
def test_deadline_requires_literal_boolean_live_state(value):
    with pytest.raises(ContractError):
        deadline(live_state_consistent=value).allow_revision('2026-09-18T18:45:00+09:00',0)


@pytest.mark.parametrize('value',[True,False,'120',None])
def test_deadline_rejects_non_numeric_or_boolean_reserve(value):
    with pytest.raises(ContractError):
        deadline().allow_revision('2026-09-18T18:45:00+09:00',value)


@pytest.mark.parametrize('race',['20260230_GAMAGORI_5R','20261301_GAMAGORI_5R'])
def test_invalid_calendar_date_is_rejected_before_query(race):
    calls=[]
    def query(f):
        calls.append(f)
        return []
    with pytest.raises(ContractError):reader().read(query,race)
    assert calls==[]


@pytest.mark.parametrize('bad',[None,{},iter([]),[None]])
def test_reader_requires_eager_list_of_plain_records(bad):
    with pytest.raises(ContractError):reader().read(lambda f:bad,'20260918_GAMAGORI_5R')


def test_reader_output_is_detached_from_adapter_mutation():
    rows=[row()]
    out=reader().read(lambda f:rows,'20260918_GAMAGORI_5R')
    rows[0]['payload']['source']='B'
    assert out[0]['payload']['source']=='A'
