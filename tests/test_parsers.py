import pytest

from parsers import ParserError, parse_beforeinfo, parse_odds3t, parse_race_index


RACEINDEX_HTML = """
<html><body><table>
<tr><th>レース</th><th>締切予定時刻/投票</th></tr>
<tr><td>1R</td><td>15:21 投票</td></tr>
<tr><td>2R</td><td>15:48 発売終了</td></tr>
<tr><td>3R</td><td>16:14 中止</td></tr>
</table></body></html>
"""

BEFORE_HTML = """
<html><body>
<h3>展示タイム</h3><table>
<tr><th>艇</th><th>展示タイム</th></tr>
<tr><td>1号艇</td><td>6.71</td></tr><tr><td>2号艇</td><td>6.68</td></tr>
<tr><td>3号艇</td><td>6.73</td></tr><tr><td>4号艇</td><td>6.75</td></tr>
<tr><td>5号艇</td><td>6.70</td></tr><tr><td>6号艇</td><td>6.77</td></tr>
</table>
<h3>スタート展示</h3><table>
<tr><td>1号艇 進入 1 ST 0.12</td></tr><tr><td>2号艇 進入 2 ST 0.08</td></tr>
<tr><td>3号艇 進入 3 ST 0.15</td></tr><tr><td>4号艇 進入 4 ST 0.11</td></tr>
<tr><td>5号艇 進入 5 ST 0.09</td></tr><tr><td>6号艇 進入 6 ST 0.14</td></tr>
</table>
<div>風向 北西 風速 2m 波高 1cm</div>
</body></html>
"""

ODDS_HTML = """
<html><body><h3>3連単オッズ</h3><table>
<tr><td>1-2-3</td><td>4.5</td></tr>
<tr><td>1-2-4</td><td>8.2</td></tr>
</table></body></html>
"""


def test_parse_race_index():
    races = parse_race_index(RACEINDEX_HTML, "20260917", "u", "2026-09-17T14:00:00+09:00")
    assert len(races) == 3
    assert races[0].race_id == "20260917_GAM_01R"
    assert races[0].official_deadline.hour == 15 and races[0].official_deadline.minute == 21
    assert races[1].is_closed is True
    assert races[2].is_cancelled is True


def test_parse_beforeinfo_semantically_anchored():
    data = parse_beforeinfo(BEFORE_HTML, "before", "2026-09-17T15:10:00+09:00")
    assert len(data.exhibition_times) == 6
    assert data.exhibition_times[2] == 6.68
    assert data.entry_courses == {1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}
    assert data.weather_info["wind_speed_m"] == 2.0


def test_beforeinfo_wrong_structure_fails_closed():
    data = parse_beforeinfo("<html><body>6.71 6.68 6.73 6.75 6.70 6.77</body></html>", "u", "t")
    assert data.exhibition_times == {}
    assert "exhibition_section" in data.missing_fields


def test_parse_odds3t_explicit_combos_only():
    odds, _ = parse_odds3t(ODDS_HTML, "odds", "t")
    assert odds["1-2-3"] == 4.5


def test_odds_wrong_structure_raises():
    with pytest.raises(ParserError):
        parse_odds3t("<html><body><h3>3連単</h3>4.5 8.2</body></html>", "u", "t")


def test_raceindex_partial_structure_fails_closed():
    html = '''<html><body><table>
    <tr><td>1R</td><td>15:21 投票</td></tr>
    <tr><td>2R</td><td>時刻取得失敗 投票</td></tr>
    </table></body></html>'''
    with pytest.raises(ParserError, match="partial parse"):
        parse_race_index(html, "20260917", "u", "t")
