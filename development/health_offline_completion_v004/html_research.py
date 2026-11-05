"""Research normalization only: never an official parser or terminal authority."""
from __future__ import annotations

import datetime as dt
import hashlib
from html import escape
from html.parser import HTMLParser
import json
import re

from bs4 import BeautifulSoup
from parsers import ParserError, parse_race_index

_RACE_HEADERS = {"レース", "レース番号", "R", "レースNo."}
_CLOSING = re.compile(r"(?:投票|発売)?締切(?:予定)?(?:時刻|時間)?(?:[/／・]?投票)?\Z")
_STATE_HEADERS = {"状態", "発売状況"}


class ResearchHold(ValueError):
    """Fixed code only; never retains HTML or URLs."""


class _OptionalEnds(HTMLParser):
    """Resolve a narrow optional td/th/tr-end grammar, without inventing EOF."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.frames = []
        self.output = []
        self.repairs = {"cell_end": 0, "row_end": 0}
        self.nesting = False

    @staticmethod
    def _tag(tag, attrs, ending=False):
        if ending:
            return "</" + tag + ">"
        encoded = "".join(" " + escape(str(k), quote=True) +
                          ("" if v is None else '="' + escape(str(v), quote=True) + '"')
                          for k, v in attrs)
        return "<" + tag + encoded + ">"

    def _close_cell(self):
        frame = self.frames[-1]
        if frame["cell"]:
            self.output.append("</" + frame["cell"] + ">")
            frame["cell"] = None
            self.repairs["cell_end"] += 1

    def _close_row(self):
        frame = self.frames[-1]
        if frame["row"]:
            self._close_cell()
            self.output.append("</tr>")
            frame["row"] = False
            self.repairs["row_end"] += 1

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.nesting |= bool(self.frames)
            self.frames.append({"row": False, "cell": None})
        elif tag == "tr" and self.frames:
            self._close_row()
            self.frames[-1]["row"] = True
        elif tag in ("td", "th") and self.frames:
            if not self.frames[-1]["row"]:
                raise ResearchHold("CELL_WITHOUT_ROW")
            self._close_cell()
            self.frames[-1]["cell"] = tag
        elif tag in ("tbody", "thead", "tfoot") and self.frames:
            self._close_row()
        self.output.append(self._tag(tag, attrs))

    def handle_endtag(self, tag):
        if tag == "table":
            if not self.frames:
                raise ResearchHold("UNMATCHED_TABLE_END")
            self._close_row()
            self.frames.pop()
        elif tag == "tr" and self.frames:
            if not self.frames[-1]["row"]:
                raise ResearchHold("UNMATCHED_ROW_END")
            self._close_cell()
            self.frames[-1]["row"] = False
        elif tag in ("td", "th") and self.frames:
            if self.frames[-1]["cell"] != tag:
                raise ResearchHold("UNMATCHED_CELL_END")
            self.frames[-1]["cell"] = None
        elif tag in ("tbody", "thead", "tfoot") and self.frames:
            self._close_row()
        self.output.append(self._tag(tag, (), True))

    def handle_startendtag(self, tag, attrs):
        if tag in ("table", "tr", "td", "th"):
            raise ResearchHold("SELF_CLOSING_TABLE_STRUCTURE")
        self.output.append(self._tag(tag, attrs)[:-1] + "/>")

    def handle_data(self, data):
        self.output.append(escape(data))

    def handle_comment(self, data):
        # Comments cannot introduce additional candidate tables.
        self.output.append("<!-- -->")

    def finish(self, html):
        self.feed(html)
        self.close()
        if self.frames:
            raise ResearchHold("UNCLOSED_TABLE_NO_EOF_REPAIR")
        return "".join(self.output)


def _text(cell):
    return " ".join(cell.stripped_strings)


def _own_cell_text(cell):
    # Exclude nested-table descendants, without discarding the parent's own
    # race/time cells alongside a nested layout table.
    values = []
    for node in cell.find_all(string=True):
        ancestor = node.parent
        nested = False
        while ancestor is not None and ancestor is not cell:
            if getattr(ancestor, "name", None) == "table":
                nested = True
                break
            ancestor = ancestor.parent
        if not nested:
            value = str(node).strip()
            if value:
                values.append(value)
    return " ".join(values)


def _own_row_has_race_clock(row):
    values = [_own_cell_text(cell) for cell in row.find_all(["th", "td"], recursive=False)]
    has_race = any(re.fullmatch(r"[0-9０-９]+\s*[RＲ]", value, re.IGNORECASE) for value in values)
    has_clock = re.search(r"[0-9０-９]{1,2}[:：][0-9０-９]{2}", " ".join(values))
    return bool(has_race and has_clock)


def _heading(cell):
    return re.sub(r"\s+", "", _text(cell))


def _columns(cells):
    result = []
    expanded = False
    for cell in cells:
        if cell.get("rowspan", "1") != "1":
            raise ResearchHold("ROWSPAN_UNREVIEWED")
        raw = str(cell.get("colspan", "1"))
        if not re.fullmatch(r"[1-9][0-9]?", raw) or int(raw) > 12:
            raise ResearchHold("COLSPAN_UNREVIEWED")
        count = int(raw)
        text = _heading(cell)
        if count != 1 and (text in _RACE_HEADERS or _CLOSING.fullmatch(text) or text in _STATE_HEADERS):
            raise ResearchHold("SEMANTIC_COLUMN_SPAN_AMBIGUOUS")
        result.extend([text] * count)
        expanded |= count != 1
    return result, expanded


def _anchor(headings):
    race = [i for i, text in enumerate(headings) if text in _RACE_HEADERS]
    closing = [i for i, text in enumerate(headings) if _CLOSING.fullmatch(text)]
    if not race or not closing:
        return None
    if len(race) != 1 or len(closing) != 1 or race[0] == closing[0]:
        raise ResearchHold("SEMANTIC_HEADER_AMBIGUOUS")
    return race[0], closing[0]


def _canonical_records(races):
    return [race.model_dump(mode="json") for race in races]


def _digest(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    return hashlib.sha256(data).hexdigest()


def inspect_research_html(html, date_str, acquired_at="UNVERIFIED_CAPTURE_TIME"):
    result = {"status": "HOLD", "reason": "INPUT_UNVERIFIED", "go": False,
              "runtime_execution_allowed": False, "official_compatibility": "UNVERIFIED",
              "policy_status": "POLICY_PENDING_REAL_HTML", "records": None,
              "normalization": {}, "candidate_table_count": 0}
    try:
        if not isinstance(html, str) or not isinstance(date_str, str) or not re.fullmatch(r"[0-9]{8}", date_str):
            raise ResearchHold("INPUT_UNVERIFIED")
        dt.datetime.strptime(date_str, "%Y%m%d")
        normalizer = _OptionalEnds()
        normalized = normalizer.finish(html)
        soup = BeautifulSoup(normalized, "html.parser")
        for hidden in soup.find_all(["script", "style"]):
            hidden.decompose()
        candidates = []
        orphan_race_rows = any(
            row.find_parent("table") is None and _own_row_has_race_clock(row)
            for row in soup.find_all("tr"))
        forms = set()
        if normalizer.nesting:
            forms.add("LAYOUT_NESTING")
        if any(normalizer.repairs.values()):
            forms.add("OPTIONAL_CELL_ROW_ENDS")
        for table in soup.find_all("table"):
            rows = [row for row in table.find_all("tr") if row.find_parent("table") is table]
            anchors = []
            for index, row in enumerate(rows):
                cells = row.find_all(["th", "td"], recursive=False)
                if not cells or any(cell.find("table") for cell in cells):
                    continue
                headings, expanded = _columns(cells)
                # A numbered data cell is never a header.
                if any(re.fullmatch(r"[0-9]+\s*R", h, re.IGNORECASE) for h in headings):
                    continue
                anchor = _anchor(headings)
                if anchor:
                    anchors.append((index, headings, anchor, expanded))
            if not anchors:
                for row in rows:
                    if _own_row_has_race_clock(row):
                        orphan_race_rows = True
                continue
            first_index, headings, (race_col, closing_col), expanded = anchors[0]
            if any(other[1] != headings or other[2] != (race_col, closing_col) for other in anchors[1:]):
                raise ResearchHold("CONFLICTING_REPEATED_HEADERS")
            if len(anchors) > 1:
                forms.add("IDENTICAL_REPEATED_HEADERS")
            if expanded:
                forms.add("NONSEMANTIC_HEADER_COLSPAN")
            if headings[race_col] == "レースNo.":
                forms.add("RACE_NO_ALIAS")
            output_headers = list(headings)
            output_headers[race_col] = "レース"
            serialized = ["<table><tr>" + "".join("<th>" + escape(h) + "</th>" for h in output_headers) + "</tr>"]
            profile_rows = []
            for index, row in enumerate(rows):
                if index in {item[0] for item in anchors}:
                    continue
                cells = row.find_all(["th", "td"], recursive=False)
                if not cells:
                    continue
                if any(cell.find("table") for cell in cells):
                    raise ResearchHold("NESTED_DATA_CELL_UNREVIEWED")
                if any(cell.get("rowspan", "1") != "1" or cell.get("colspan", "1") != "1" for cell in cells):
                    raise ResearchHold("DATA_CELL_SPAN_UNREVIEWED")
                values = [_text(cell) for cell in cells]
                if index < first_index:
                    if any(re.search(r"[0-9]+\s*R", value, re.IGNORECASE) for value in values):
                        raise ResearchHold("DATA_BEFORE_HEADER")
                    continue
                if len(values) != len(headings):
                    raise ResearchHold("DATA_WIDTH_MISMATCH")
                profile_rows.append(values)
                serialized.append("<tr>" + "".join("<td>" + escape(v) + "</td>" for v in values) + "</tr>")
            serialized.append("</table>")
            sanitized = "".join(serialized)
            races = parse_race_index(sanitized, date_str, "LOCAL_RESEARCH_INPUT", acquired_at,
                                     expected_race_numbers=range(1, 13))
            records = _canonical_records(races)
            candidates.append({"records": records, "profile": [headings, profile_rows],
                               "sanitized_sha256": hashlib.sha256(sanitized.encode()).hexdigest()})
        if orphan_race_rows:
            raise ResearchHold("UNANCHORED_RACE_ROWS")
        result["candidate_table_count"] = len(candidates)
        if not candidates:
            raise ResearchHold("SEMANTIC_TABLE_UNVERIFIED")
        reference = candidates[0]
        if any(candidate["records"] != reference["records"] or candidate["profile"] != reference["profile"]
               for candidate in candidates[1:]):
            raise ResearchHold("DUPLICATE_TABLE_CONFLICT")
        if len(candidates) > 1:
            forms.add("EQUIVALENT_MULTIPLE_TABLES")
        result.update(status="RESEARCH_PARSED", reason="SYNTHETIC_CANDIDATE_ONLY",
                      records=reference["records"], semantic_sha256=_digest(reference["records"]),
                      normalization={"repairs": normalizer.repairs, "forms": sorted(forms),
                                     "normalized_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
                                     "sanitized_table_sha256": reference["sanitized_sha256"]})
    except ResearchHold as exc:
        result["reason"] = exc.args[0] if len(exc.args) == 1 else "RESEARCH_HOLD"
    except ParserError:
        result["reason"] = "STRICT_PARSER_REJECTED"
    except (ValueError, TypeError, AttributeError, OverflowError):
        result["reason"] = "INPUT_OR_STRUCTURE_UNVERIFIED"
    return result
