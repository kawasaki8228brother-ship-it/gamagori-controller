"""Official racelist DOM candidate: verify listed identities, not live starters.

The known layout exposes roster listings, not an explicit ACTIVE-at-decision
status or a roster-effective timestamp. Do not equate a listing with ACTIVE.
The Stage8 adapter deliberately emits UNKNOWN slot states pending the reviewed
source-status contract. No runtime import, transport or betting side effect.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
import hashlib
import re
import unicodedata
from urllib.parse import urlsplit, parse_qs

from bs4 import BeautifulSoup, Tag
from .beforeinfo import grid, cells, span
from .participant_evidence import RaceIdentity, RosterExtraction, SemanticValidator
from .readiness import CheckState


class RosterSemanticError(ValueError):
    pass


def _text(node: Tag) -> str:
    return unicodedata.normalize('NFKC', node.get_text(' ', strip=True)).strip()


def _compact(node: Tag) -> str:
    return re.sub(r'\s+', '', _text(node))


def _one(items: list, code: str):
    if len(items) != 1:
        raise RosterSemanticError(code)
    return items[0]


def _query(url: str, path: str, keys: set[str]) -> dict[str, str]:
    if type(url) is not str or any(c.isspace() for c in url):
        raise RosterSemanticError('BODY_LINK_FORMAT')
    try:
        p = urlsplit(url)
        if p.scheme not in ('', 'https') or p.username is not None or p.password is not None or p.fragment:
            raise RosterSemanticError('BODY_LINK_ORIGIN')
        if p.netloc and (p.hostname not in {'boatrace.jp', 'www.boatrace.jp'} or p.port not in (None, 443)):
            raise RosterSemanticError('BODY_LINK_ORIGIN')
        if not p.scheme and p.netloc:
            raise RosterSemanticError('PROTOCOL_RELATIVE_LINK')
        q = parse_qs(p.query, keep_blank_values=True)
        if p.path != path or set(q) != keys or any(len(v) != 1 for v in q.values()):
            raise RosterSemanticError('BODY_LINK_CONTEXT')
        return {k: v[0] for k, v in q.items()}
    except ValueError as exc:
        if isinstance(exc, RosterSemanticError):
            raise
        raise RosterSemanticError('BODY_LINK_FORMAT') from exc


def _race_link(url: str, role: str) -> RaceIdentity:
    q = _query(url, '/owpc/pc/race/' + role, {'hd', 'jcd', 'rno'})
    if not re.fullmatch(r'\d{8}', q['hd']) or not re.fullmatch(r'[1-9]|1[0-2]', q['rno']):
        raise RosterSemanticError('BODY_RACE_FORMAT')
    d = q['hd']
    return RaceIdentity(d[:4]+'-'+d[4:6]+'-'+d[6:], q['jcd'], int(q['rno']))


def _body_identity(soup: BeautifulSoup) -> RaceIdentity:
    title = _one(soup.find_all('title'), 'TITLE_MISSING_OR_DUPLICATE')
    if _compact(title) != '出走表|BOATRACEオフィシャルウェブサイト':
        raise RosterSemanticError('WRONG_PAGE_ROLE')
    area = _one(soup.select('.heading2_area img'), 'VENUE_AMBIGUOUS')
    if area.get('alt') != '蒲郡' or area.get('src') != '/static_extra/pc/images/text_place2_07.png':
        raise RosterSemanticError('BODY_VENUE_MISMATCH')
    menu = _one(soup.select('.tab3_tabs'), 'PAGE_MENU_AMBIGUOUS')
    active = _one(menu.select(':scope > li.is-active'), 'PAGE_ROLE_AMBIGUOUS')
    if _compact(active) != '出走表':
        raise RosterSemanticError('WRONG_PAGE_ROLE')
    roles = {'odds3t', 'beforeinfo', 'pcexpect', 'myexpect', 'raceresult'}
    links = menu.select(':scope > li > a[href]')
    if len(links) != len(roles):
        raise RosterSemanticError('INCOMPLETE_PAGE_MENU')
    identities, seen = [], set()
    for a in links:
        role = urlsplit(a['href']).path.rsplit('/', 1)[-1]
        if role not in roles or role in seen:
            raise RosterSemanticError('AMBIGUOUS_PAGE_MENU')
        seen.add(role); identities.append(_race_link(a['href'], role))
    identity = identities[0]
    if any(i != identity for i in identities):
        raise RosterSemanticError('BODY_LINK_IDENTITY_CONFLICT')
    date_node = _one(soup.select('.tab2_tabs > li.is-active2 > .tab2_inner'), 'SELECTED_DATE_AMBIGUOUS')
    match = re.match(r'^(\d{1,2})月(\d{1,2})日', _compact(date_node))
    date = dt.date.fromisoformat(identity.target_date)
    if not match or (int(match[1]), int(match[2])) != (date.month, date.day):
        raise RosterSemanticError('BODY_DATE_DISPLAY_CONFLICT')
    navs = [t for t in soup.find_all('table') if t.find('thead', recursive=False)
            and any(_compact(th)=='レース' for th in t.find('thead', recursive=False).find_all('th'))]
    nav = _one(navs, 'RACE_NAV_AMBIGUOUS')
    numbers, selected = [], []
    for th in nav.find('thead', recursive=False).find_all('th'):
        m = re.fullmatch(r'([1-9]|1[0-2])R', _compact(th))
        if not m:
            continue
        b = int(m[1]); numbers.append(b)
        a = _one(th.find_all('a', href=True), 'RACE_NAV_LINK_AMBIGUOUS')
        if _race_link(a['href'], 'racelist') != RaceIdentity(identity.target_date, '07', b):
            raise RosterSemanticError('RACE_NAV_IDENTITY_CONFLICT')
        if 'is-thColor2' not in th.get('class', []):
            selected.append(b)
    if numbers != list(range(1, 13)) or selected != [identity.race_no]:
        raise RosterSemanticError('SELECTED_RACE_CONFLICT')
    return identity


@dataclass(frozen=True)
class ListedSlot:
    boat: int
    registration_no: str
    name_raw: str
    name_normalized: str
    listing_state: str
    locator: str


@dataclass(frozen=True)
class ListedRoster:
    body_identity: RaceIdentity
    slots: tuple[ListedSlot, ...]
    six_slots_present: bool
    body_sha256: str
    source_effective_at: None = None
    active_status_verified: bool = False


def parse_listed_roster(body: bytes) -> ListedRoster:
    if type(body) is not bytes or not 0 < len(body) <= 2_000_000:
        raise RosterSemanticError('BODY_TYPE_OR_SIZE')
    try:
        html = body.decode('utf-8', errors='strict')
    except UnicodeError as exc:
        raise RosterSemanticError('BODY_ENCODING') from exc
    soup = BeautifulSoup(html, 'html.parser')
    identity = _body_identity(soup)
    candidates = []
    for table in soup.find_all('table'):
        head = table.find('thead', recursive=False)
        if head and {'枠', 'ボートレーサー'} <= {_compact(c) for c in head.find_all('th')}:
            candidates.append(table)
    table = _one(candidates, 'ROSTER_TABLE_AMBIGUOUS')
    if table.find('table') is not None:
        raise RosterSemanticError('NESTED_ROSTER_TABLE')
    headrows = table.find('thead', recursive=False).find_all('tr', recursive=False)
    width = sum(span(c, 'colspan') for c in cells(headrows[0]))
    header = grid(headrows, width)
    positions = {}
    for key, expected in [('boat', '枠'), ('racer', '登録番号/級別氏名支部/出身地年齢/体重')]:
        hits = [col for col in range(width) if any(_compact(row[col]) == expected for row in header)]
        positions[key] = _one(hits, 'ROSTER_COLUMN_AMBIGUOUS:' + key)
    slots = []
    for index, tbody in enumerate(table.find_all('tbody', recursive=False), 1):
        rows = tbody.find_all('tr', recursive=False)
        if len(rows) != 4:
            raise RosterSemanticError('UNREVIEWED_ROSTER_ROW_LAYOUT')
        expanded = grid(rows, width)
        bcell, racer = expanded[0][positions['boat']], expanded[0][positions['racer']]
        if any(row[positions['boat']] is not bcell or row[positions['racer']] is not racer for row in expanded):
            raise RosterSemanticError('ROSTER_ROW_ASSOCIATION_CONFLICT')
        btext = _compact(bcell)
        if not re.fullmatch(r'[1-6]', btext):
            raise RosterSemanticError('INVALID_ROSTER_BOAT')
        b = int(btext)
        codes = [c for c in bcell.get('class',[]) if re.fullmatch(r'is-boatColor[1-6]',c)]
        if codes != [f'is-boatColor{b}']:
            raise RosterSemanticError('ROSTER_BOAT_CLASS_CONFLICT')
        a = _one(racer.select('div.is-fs18 > a[href]'), 'RACER_NAME_LINK_AMBIGUOUS')
        q = _query(a['href'], '/owpc/pc/data/racersearch/profile', {'toban'})
        reg = q['toban']
        if not re.fullmatch(r'\d{4}',reg):
            raise RosterSemanticError('INVALID_REGISTRATION_NO')
        labels = racer.select('div.is-fs11')
        if not labels or not re.fullmatch(re.escape(reg)+r'/(?:A1|A2|B1|B2)', _compact(labels[0])):
            raise RosterSemanticError('REGISTRATION_TEXT_LINK_CONFLICT')
        raw = a.get_text('', strip=True)
        normal = re.sub(r'\s+', '', unicodedata.normalize('NFKC',raw))
        if not normal:
            raise RosterSemanticError('RACER_NAME_MISSING')
        slots.append(ListedSlot(b, reg, raw, normal, 'LISTED_STATUS_UNVERIFIED',
                                f'roster_table/tbody[{index}]/racer'))
    if len({s.boat for s in slots}) != len(slots) or len({s.registration_no for s in slots}) != len(slots):
        raise RosterSemanticError('DUPLICATE_ROSTER_SLOT_OR_RACER')
    slots.sort(key=lambda s:s.boat)
    return ListedRoster(identity, tuple(slots), {s.boat for s in slots}==set(range(1,7)), hashlib.sha256(body).hexdigest())


def extract_listed_roster_semantics(body: bytes) -> RosterExtraction:
    parsed = parse_listed_roster(body)
    # Deliberate hold: the normal listing has not yet been reviewed as an
    # authoritative ACTIVE-at-decision marker. Do not upgrade listed to ACTIVE.
    return RosterExtraction(parsed.body_identity, tuple((s.boat,'UNKNOWN') for s in parsed.slots),
                            'racelist:body-navigation+listed-roster;active-status-unverified')


LISTED_ROSTER_VALIDATOR = SemanticValidator('RACELIST_LISTING_DOM_V1_CANDIDATE', extract_listed_roster_semantics, test_only=False)


@dataclass(frozen=True)
class RosterTimeReport:
    state: CheckState
    usable_at_decision: bool
    reasons: tuple[str,...]
    acquired_at: str
    decision_at: str
    target_date: str
    source_effective_at: None = None


def assess_roster_time_context(target: RaceIdentity, acquired_at: str, *, decision_at: dt.datetime) -> RosterTimeReport:
    """Facts-only temporal guard; no TTL or freshness PASS is invented.

    A post-decision recapture cannot establish what was available at decision.
    HTTP Date and read time are not publication time. Even same-day capture is
    UNVERIFIED until the source-specific effective-state policy is reviewed.
    """
    if type(target) is not RaceIdentity or type(decision_at) is not dt.datetime or decision_at.tzinfo is None:
        raise RosterSemanticError('INVALID_TIME_CONTEXT')
    try:
        if type(acquired_at) is not str:
            raise ValueError()
        acquired = dt.datetime.fromisoformat(acquired_at.replace('Z','+00:00'))
        if acquired.tzinfo is None:
            raise ValueError()
    except (ValueError, TypeError) as exc:
        raise RosterSemanticError('INVALID_ACQUIRED_AT') from exc
    reasons = []
    if acquired > decision_at:
        reasons.append('CAPTURE_AFTER_REQUESTED_DECISION')
    jst = dt.timezone(dt.timedelta(hours=9))
    if acquired.astimezone(jst).date().isoformat()!=target.target_date:
        reasons.append('CAPTURE_NOT_ON_TARGET_DAY')
    reasons.append('ROSTER_EFFECTIVE_TIME_UNVERIFIED')
    state = CheckState.FAIL if acquired > decision_at else CheckState.UNVERIFIED
    return RosterTimeReport(state,False,tuple(reasons),acquired_at,decision_at.isoformat(),target.target_date)
