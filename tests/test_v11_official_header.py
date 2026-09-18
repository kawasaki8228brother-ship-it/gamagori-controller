"""Synthetic regression for the header layout found in captured official HTML."""
import pytest
from v11_candidate.odds import parse_trifecta, OddsParseError
from test_v11_candidate import matrix


def split_header(html):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'html.parser')
    header=soup.find('thead').find('tr')
    header.clear()
    for boat in range(1,7):
        number=soup.new_tag('th',attrs={'class':f'is-boatColor{boat}'})
        number.string=str(boat)
        name=soup.new_tag('th',attrs={'class':f'is-boatColor{boat}','colspan':'2'})
        name.string=f'Test Racer {boat}'
        header.extend([number,name])
    return str(soup)


def test_split_number_name_header_layout():
    html,expected=matrix()
    assert parse_trifecta(split_header(html)).odds==expected


def test_split_header_color_conflict_rejected():
    html,_=matrix()
    html=split_header(html).replace('class="is-boatColor1" colspan="2"','class="is-boatColor2" colspan="2"',1)
    with pytest.raises(OddsParseError):parse_trifecta(html)
