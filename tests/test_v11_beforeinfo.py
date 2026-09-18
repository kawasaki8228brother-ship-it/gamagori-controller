"""Authored DOM fixtures, not originals from the 9/18 incident."""
from bs4 import BeautifulSoup
import pytest
from v11_candidate.beforeinfo import parse_beforeinfo_snapshot, parse_start, BeforeInfoParseError

TIMES = [6.68,6.72,6.69,6.77,6.71,6.80]
STARTS = ['.02','F.01','F.02','.11','.01','.14']


def fixture(order=(1,2,3,4,5,6)):
    h='<table id="ex"><thead><tr><th rowspan="2">枠</th><th>体重</th><th rowspan="2">展示<br>タイム</th><th colspan="2" rowspan="2">前走成績</th></tr><tr><th>調整重量</th></tr></thead>'
    for boat,value in enumerate(TIMES,1):
        h+=f'<tbody><tr><td rowspan="4">{boat}</td><td rowspan="2">52.0kg</td><td rowspan="4">{value:.2f}</td><td>R</td><td>9</td></tr><tr><td>進入</td><td>6</td></tr><tr><td rowspan="2">0.5</td><td>ST</td><td>.99</td></tr><tr><td>着順</td><td>5</td></tr></tbody>'
    h+='</table><table id="st"><thead><tr><th colspan="3">スタート展示</th></tr><tr><th>コース</th><th>並び</th><th>ST</th></tr></thead><tbody>'
    for boat in order:
        h+=f'<tr><td colspan="3"><div class="table1_boatImage1"><span class="table1_boatImage1Number is-type{boat}">{boat}</span><span class="table1_boatImage1Time">{STARTS[boat-1]}</span></div></td></tr>'
    h+='</tbody></table><div class="weather1"><p class="weather1_title">水面気象情報 11R時点</p>'
    for name,value in [('気温','24.0℃'),('水温','24.0℃'),('風速','1m'),('波高','0cm')]:
        h+=f'<div class="weather1_bodyUnitLabel"><span class="weather1_bodyUnitLabelTitle">{name}</span><span class="weather1_bodyUnitLabelData">{value}</span></div>'
    return h+'<div class="is-windDirection"><p class="weather1_bodyUnitImage is-wind15"></p></div></div>'


def test_semantic_columns_not_weight_or_previous_race():
    d=parse_beforeinfo_snapshot(fixture())
    assert d.exhibition_times==dict(enumerate(TIMES,1))
    assert d.entry_courses=={i:i for i in range(1,7)}
    assert [d.starts[i].raw for i in range(1,7)]==STARTS
    assert d.starts[2].marker=='F' and d.starts[2].seconds_magnitude==0.01
    assert d.exhibition_six and d.entry_six and d.numeric_st_six
    assert d.weather['reference_race_no']==11 and d.weather['wave_height_cm']==0
    assert d.weather['wind_direction_code']=='is-wind15'
    assert d.missing_fields==[]
    assert not hasattr(d,'is_complete')


def test_non_frame_entry_order_is_not_overwritten():
    d=parse_beforeinfo_snapshot(fixture((1,2,4,3,5,6)))
    assert d.entry_courses[4]==3 and d.entry_courses[3]==4
    assert d.starts[3].raw=='F.02' and d.starts[4].raw=='.11'


@pytest.mark.parametrize('missing',['6.68','6.72','6.69','6.77','6.71','6.80'])
def test_blank_exhibition_stays_missing(missing):
    d=parse_beforeinfo_snapshot(fixture().replace(missing,'',1))
    assert len(d.exhibition_times)==5 and not d.exhibition_six
    assert 'exhibition_times_6boats' in d.missing_fields


@pytest.mark.parametrize('value',['NaN','inf','6.681','0.00','-6.68','6.68abc'])
def test_invalid_exhibition_is_not_guessed(value):
    with pytest.raises(BeforeInfoParseError):parse_beforeinfo_snapshot(fixture().replace('6.68',value,1))


@pytest.mark.parametrize('raw,marker,magnitude',[('.00',None,0.0),('F.00','F',0.0),('F.01','F',0.01),('L.99','L',0.99),('0.12',None,0.12),('Ｆ．０２','F',0.02),('F','F',None),('L','L',None)])
def test_start_markers_preserved(raw,marker,magnitude):
    s=parse_start(raw)
    assert (s.raw,s.marker,s.seconds_magnitude)==(raw,marker,magnitude)


@pytest.mark.parametrize('raw',['','-','--','欠場'])
def test_missing_start_not_zero(raw):
    assert parse_start(raw) is None


@pytest.mark.parametrize('raw',['nan','inf','.001','.02foo','F-.01','F .01','-0.01'])
def test_bad_start_format_rejected(raw):
    with pytest.raises(BeforeInfoParseError):parse_start(raw)


def test_missing_st_keeps_entry_but_not_numeric_coverage():
    d=parse_beforeinfo_snapshot(fixture().replace('F.01','',1))
    assert d.entry_six and not d.numeric_st_six and 2 not in d.starts


def test_removed_start_row_cannot_shift_courses():
    s=BeautifulSoup(fixture(),'html.parser');s.select('#st tbody tr')[2].decompose()
    d=parse_beforeinfo_snapshot(str(s));assert d.entry_courses=={} and d.starts=={}
    assert 'start_rows_six' in d.missing_fields


def test_blank_start_row_does_not_shift_later_course():
    s=BeautifulSoup(fixture(),'html.parser');row=s.select('#st tbody tr')[2];row.td.clear()
    d=parse_beforeinfo_snapshot(str(s))
    assert 3 not in d.entry_courses and d.entry_courses[4]==4 and not d.entry_six


@pytest.mark.parametrize('section',['#ex','#st','.weather1'])
def test_duplicate_sections_fail_closed(section):
    s=BeautifulSoup(fixture(),'html.parser');html=str(s)+str(s.select_one(section))
    with pytest.raises(BeforeInfoParseError):parse_beforeinfo_snapshot(html)


def test_duplicate_boat_rejected():
    with pytest.raises(BeforeInfoParseError):parse_beforeinfo_snapshot(fixture((1,2,3,4,5,5)))


def test_color_identity_conflict_rejected():
    with pytest.raises(BeforeInfoParseError):parse_beforeinfo_snapshot(fixture().replace('is-type2','is-type3',1))


@pytest.mark.parametrize('bad',['0','-1','x','99'])
def test_invalid_rowspan_rejected(bad):
    with pytest.raises(BeforeInfoParseError):parse_beforeinfo_snapshot(fixture().replace('rowspan="4"',f'rowspan="{bad}"',1))


def test_missing_time_cell_rejected():
    with pytest.raises(BeforeInfoParseError):parse_beforeinfo_snapshot(fixture().replace('<td rowspan="4">6.68</td>','',1))


def test_no_tables_is_missing_not_not_published_claim():
    d=parse_beforeinfo_snapshot('<html><body>6.68 .02 1 2 3</body></html>')
    assert not d.exhibition_six and not d.entry_six and not d.numeric_st_six
    assert 'exhibition_section' in d.missing_fields


def test_blank_wind_is_distinct_from_zero_wave():
    d=parse_beforeinfo_snapshot(fixture().replace('>1m<','><'))
    assert 'wind_speed_m' not in d.weather and d.weather['wave_height_cm']==0
    assert 'weather_wind_speed_m' in d.missing_fields


def test_weather_unit_is_not_guessed():
    with pytest.raises(BeforeInfoParseError):parse_beforeinfo_snapshot(fixture().replace('>1m<','>1km<'))


def test_previous_race_st_not_used_when_start_table_absent():
    s=BeautifulSoup(fixture(),'html.parser');s.select_one('#st').decompose()
    d=parse_beforeinfo_snapshot(str(s));assert d.starts=={} and d.entry_courses=={}
