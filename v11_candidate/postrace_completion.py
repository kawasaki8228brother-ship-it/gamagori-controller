"""Evidence-backed postrace archive eligibility, not a scheduler or bet gate.

All twelve target-race result pages must expose consistent top-three finishers
and a single numeric trifecta payout. Unsupported/cancelled/unpublished layouts
stay UNVERIFIED. Finish labels are preserved; no withdrawal is inferred.
Transport metadata comes from a trusted future acquisition boundary; hashes
prove association, not publisher authenticity, freshness or disk durability.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import datetime as dt
import hashlib
import re
from urllib.parse import urlsplit, parse_qs
from bs4 import BeautifulSoup
from .beforeinfo import cells, grid
from .participant_evidence import RaceIdentity
from .roster_semantics import _compact, _one, _race_link


class CompletionError(ValueError):
    pass


class ResultUnavailable(CompletionError):
    pass


@dataclass(frozen=True)
class ResultSnapshot:
    race_no: int
    requested_url: str
    response_url: str
    acquired_at: str
    http_status: int
    content_type: str
    content_encoding: str
    body_complete: bool
    body: bytes
    body_sha256: str


@dataclass(frozen=True)
class ResultProof:
    target: RaceIdentity
    state: str
    reason: str | None
    acquired_at: str | None
    body_sha256: str | None
    finish_labels: tuple[tuple[int, str], ...] = ()
    trifecta: str | None = None
    payout_yen: int | None = None
    withdrawal_classification: str = 'NOT_PERFORMED'
    source_effective_at: None = None


def _url_ok(value: str, target: RaceIdentity) -> bool:
    try:
        if type(value) is not str or any(c.isspace() for c in value):
            return False
        p = urlsplit(value)
        q = parse_qs(p.query, keep_blank_values=True)
        return (p.scheme == 'https' and p.hostname in {'boatrace.jp','www.boatrace.jp'}
                and p.port in (None,443) and p.username is None and p.password is None
                and not p.fragment and p.path == '/owpc/pc/race/raceresult'
                and q == {'hd':[target.target_date.replace('-','')], 'jcd':['07'], 'rno':[str(target.race_no)]})
    except ValueError:
        return False


def _identity(soup: BeautifulSoup) -> RaceIdentity:
    if _compact(_one(soup.find_all('title'),'TITLE_AMBIGUOUS')) != '結果|BOATRACEオフィシャルウェブサイト':
        raise CompletionError('WRONG_PAGE_ROLE')
    area = _one(soup.select('.heading2_area img'),'VENUE_AMBIGUOUS')
    if area.get('alt') != '蒲郡' or area.get('src') != '/static_extra/pc/images/text_place2_07.png':
        raise CompletionError('BODY_VENUE_MISMATCH')
    menu = _one(soup.select('.tab3_tabs'),'MENU_AMBIGUOUS')
    if _compact(_one(menu.select(':scope > li.is-active'),'ROLE_AMBIGUOUS')) != '結果':
        raise CompletionError('WRONG_ACTIVE_ROLE')
    roles = {'racelist','odds3t','beforeinfo','pcexpect','myexpect'}
    identities, seen = [], set()
    for a in menu.select(':scope > li > a[href]'):
        role = urlsplit(a['href']).path.rsplit('/',1)[-1]
        if role not in roles or role in seen:
            raise CompletionError('MENU_ROLE_CONFLICT')
        identities.append(_race_link(a['href'],role)); seen.add(role)
    if seen != roles or any(i != identities[0] for i in identities):
        raise CompletionError('MENU_IDENTITY_CONFLICT')
    identity = identities[0]
    date_node = _one(soup.select('.tab2_tabs > li.is-active2 > .tab2_inner'),'DATE_AMBIGUOUS')
    match = re.match(r'^(\d{1,2})月(\d{1,2})日',_compact(date_node))
    day = dt.date.fromisoformat(identity.target_date)
    if match is None or (int(match[1]),int(match[2])) != (day.month,day.day):
        raise CompletionError('DATE_DISPLAY_CONFLICT')
    nav = _one([t for t in soup.find_all('table') if t.find('thead',recursive=False)
                and any(_compact(th)=='レース' for th in t.thead.find_all('th'))],'NAV_AMBIGUOUS')
    numbers, selected = [], []
    for th in nav.thead.find_all('th'):
        m = re.fullmatch(r'([1-9]|1[0-2])R',_compact(th))
        if m is None:
            continue
        number = int(m[1]); numbers.append(number)
        link = _one(th.find_all('a',href=True),'NAV_LINK_AMBIGUOUS')
        if _race_link(link['href'],'raceresult') != RaceIdentity(identity.target_date,'07',number):
            raise CompletionError('NAV_LINK_CONFLICT')
        if 'is-thColor2' not in th.get('class',[]):
            selected.append(number)
    if numbers != list(range(1,13)) or selected != [identity.race_no]:
        raise CompletionError('SELECTED_RACE_CONFLICT')
    return identity


def _table(soup, labels):
    found = [t for t in soup.find_all('table') if t.find('thead',recursive=False)
             and [_compact(th) for th in t.thead.find_all('th')] == labels]
    if not found:
        raise ResultUnavailable('RESULT_SECTION_NOT_RECOGNIZED')
    table = _one(found,'AMBIGUOUS_RESULT_SECTION')
    if table.find('table') is not None or table.find_parent('table') is not None:
        raise CompletionError('NESTED_RESULT_SECTION')
    return table


def parse_result_publication(body: bytes):
    """Return observed result content, not a refund/withdrawal classification."""
    if type(body) is not bytes or not 0 < len(body) <= 2_000_000:
        raise CompletionError('BODY_TYPE_OR_SIZE')
    soup = BeautifulSoup(body.decode('utf-8',errors='strict'),'html.parser')
    identity = _identity(soup)
    table = _table(soup,['着','枠','ボートレーサー','レースタイム'])
    rows = [r for b in table.find_all('tbody',recursive=False) for r in b.find_all('tr',recursive=False)]
    if len(rows) != 6:
        raise ResultUnavailable('RESULT_ROWS_INCOMPLETE_OR_UNREVIEWED')
    labels, numeric, registrations = [], {}, set()
    for row in rows:
        c = cells(row)
        if len(c)!=4 or any(x.get('colspan','1')!='1' or x.get('rowspan','1')!='1' for x in c):
            raise CompletionError('RESULT_ROW_LAYOUT')
        mark, boat = _compact(c[0]), _compact(c[1])
        if not re.fullmatch('[1-6]',boat):
            raise CompletionError('INVALID_BOAT')
        boat = int(boat)
        codes = [v for v in c[1].get('class',[]) if re.fullmatch('is-boatColor[1-6]',v)]
        if codes != [f'is-boatColor{boat}'] or boat in {b for b,_ in labels}:
            raise CompletionError('BOAT_IDENTITY_CONFLICT')
        reg = _compact(_one(c[2].select('span.is-fs12'),'REGISTRATION_AMBIGUOUS'))
        if not re.fullmatch(r'\d{4}',reg) or reg in registrations:
            raise CompletionError('REGISTRATION_CONFLICT')
        registrations.add(reg)
        if not mark:
            raise ResultUnavailable('BLANK_FINISH_LABEL')
        labels.append((boat,mark))
        if re.fullmatch('[1-6]',mark):
            if int(mark) in numeric:
                raise ResultUnavailable('TIED_FINISH_LAYOUT_NOT_REVIEWED')
            numeric[int(mark)]=boat
    if not {1,2,3} <= set(numeric):
        raise ResultUnavailable('TOP_THREE_NOT_PUBLISHED')
    expected = '-'.join(str(numeric[i]) for i in (1,2,3))
    payout_table = _table(soup,['勝式','組番','払戻金','人気'])
    blocks = [b for b in payout_table.find_all('tbody',recursive=False)
              if b.find('tr',recursive=False) and cells(b.find('tr',recursive=False))
              and _compact(cells(b.find('tr',recursive=False))[0])=='3連単']
    if not blocks:
        raise ResultUnavailable('TRIFECTA_PAYOUT_NOT_PUBLISHED')
    block = _one(blocks,'TRIFECTA_BLOCK_AMBIGUOUS')
    expanded = grid(block.find_all('tr',recursive=False),4)
    payouts=[]
    for c in expanded:
        if _compact(c[0])!='3連単':
            raise CompletionError('BET_TYPE_CONFLICT')
        combo,pay=_compact(c[1]),_compact(c[2])
        if not combo and not pay and not _compact(c[3]):
            continue
        if not re.fullmatch(r'[1-6]-[1-6]-[1-6]',combo):
            raise ResultUnavailable('TRIFECTA_LAYOUT_NOT_REVIEWED')
        if not re.fullmatch(r'¥(?:[1-9]\d*|[1-9]\d{0,2}(?:,\d{3})+)',pay):
            raise ResultUnavailable('NUMERIC_PAYOUT_NOT_PUBLISHED')
        payouts.append((combo,int(pay[1:].replace(',',''))))
    if len(payouts)!=1:
        raise ResultUnavailable('SINGLE_TRIFECTA_NOT_PUBLISHED')
    if payouts[0][0]!=expected:
        raise CompletionError('FINISH_PAYOUT_CONFLICT')
    return identity, tuple(labels), expected, payouts[0][1]


def inspect_result(snapshot: ResultSnapshot, target: RaceIdentity, *, now: dt.datetime) -> ResultProof:
    if type(target) is not RaceIdentity or type(now) is not dt.datetime or now.utcoffset() is None:
        raise CompletionError('INVALID_CONTEXT')
    def proof(state,reason,**extra):
        return ResultProof(target,state,reason,getattr(snapshot,'acquired_at',None),getattr(snapshot,'body_sha256',None),**extra)
    if type(snapshot) is not ResultSnapshot:
        return proof('FAIL','SNAPSHOT_TYPE')
    if (type(snapshot.race_no) is not int or snapshot.race_no!=target.race_no
            or type(snapshot.http_status) is not int or type(snapshot.body_complete) is not bool
            or any(type(v) is not str for v in (snapshot.content_type,snapshot.content_encoding,snapshot.acquired_at))):
        return proof('FAIL','SNAPSHOT_METADATA')
    if not all(_url_ok(v,target) for v in (snapshot.requested_url,snapshot.response_url)):
        return proof('FAIL','URL_CONTEXT_MISMATCH')
    if type(snapshot.body) is not bytes or type(snapshot.body_sha256) is not str or hashlib.sha256(snapshot.body).hexdigest()!=snapshot.body_sha256:
        return proof('FAIL','BODY_HASH_MISMATCH')
    try:
        acquired=dt.datetime.fromisoformat(snapshot.acquired_at.replace('Z','+00:00'))
        if acquired.utcoffset() is None or acquired>now or acquired.astimezone(dt.timezone(dt.timedelta(hours=9))).date()<dt.date.fromisoformat(target.target_date):
            raise ValueError()
    except (ValueError,TypeError):
        return proof('FAIL','ACQUISITION_TIME_CONFLICT')
    if (snapshot.http_status!=200 or not snapshot.body_complete
            or snapshot.content_type.split(';')[0].strip().lower()!='text/html'
            or snapshot.content_encoding.strip().lower() not in ('','identity')):
        return proof('UNVERIFIED','RESPONSE_NOT_PARSEABLE')
    try:
        identity,labels,combo,payout=parse_result_publication(snapshot.body)
        if identity!=target:
            return proof('FAIL','BODY_IDENTITY_MISMATCH')
    except ResultUnavailable as exc:
        return proof('UNVERIFIED',str(exc))
    except Exception as exc:
        return proof('FAIL','RESULT_PARSE_ERROR:'+type(exc).__name__+':'+str(exc)[:120])
    return proof('PASS',None,finish_labels=labels,trifecta=combo,payout_yen=payout)


def assess_postrace_day(target_date: str, snapshots: tuple[ResultSnapshot,...], *, now: dt.datetime) -> dict:
    """Fixed 12-race normal-result path. No clock-only or database-flag shortcut.

    PASS permits planning the postrace archive, not a recurring job, prediction,
    irreversible result finality, no-withdrawal claim or predeadline evidence.
    Job deduplication, budgets and worker/retention configuration are separate.
    """
    RaceIdentity(target_date,'07',1)
    if type(now) is not dt.datetime or now.utcoffset() is None:
        raise CompletionError('INVALID_DECISION_TIME')
    if type(snapshots) is not tuple or any(type(s) is not ResultSnapshot or type(s.race_no) is not int or not 1<=s.race_no<=12 for s in snapshots):
        raise CompletionError('INVALID_SNAPSHOT_SET')
    if len({s.race_no for s in snapshots})!=len(snapshots):
        raise CompletionError('DUPLICATE_RACE_SNAPSHOT')
    supplied={s.race_no:s for s in snapshots}
    results=[]
    for race in range(1,13):
        target=RaceIdentity(target_date,'07',race)
        result=inspect_result(supplied[race],target,now=now) if race in supplied else ResultProof(target,'UNVERIFIED','RESULT_SNAPSHOT_MISSING',None,None)
        results.append(asdict(result))
    state='FAIL' if any(r['state']=='FAIL' for r in results) else 'UNVERIFIED' if any(r['state']!='PASS' for r in results) else 'PASS'
    result={'policy_id':'ALL12_RESULT_PUBLICATIONS_V1_CANDIDATE','target_date':target_date,
            'decision_at':now.isoformat(),'state':state,'archive_input_eligible':state=='PASS',
            'result_publications':results,'verified_count':sum(r['state']=='PASS' for r in results),
            'withdrawal_classification':'NOT_PERFORMED','scheduler_started':False,
            'permanent_settlement_certified':False,'predeadline_state_proven':False}
    import json
    result['binding_sha256']=hashlib.sha256(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    return result
