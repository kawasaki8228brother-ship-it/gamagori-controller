"""Shared table discovery for observation and withdrawal scanning candidates.

Discovery only: duplicates remain visible and each caller keeps its existing
section validation. Nodes are owned by this parse, not persistent evidence.
Across independent parses, object id() is not comparable; bind any persisted
locator to the exact input body digest. This function does not mutate the DOM.
"""
from __future__ import annotations

from dataclasses import dataclass
from bs4 import BeautifulSoup, Tag
from . import beforeinfo as parser


@dataclass(frozen=True, eq=False)
class SelectedTable:
    absolute_index: int
    table: Tag


def select_beforeinfo_tables(soup: BeautifulSoup) -> dict[str, tuple[SelectedTable, ...]]:
    """Preserve the Stage10 selection rules and absolute table numbering.

    The index counts ALL tables in document order, including nested tables
    that are subsequently excluded. Never choose the first of duplicates or
    infer a section from numeric cells/notes. Not a page-identity validator.
    """
    if not isinstance(soup, BeautifulSoup):
        raise TypeError('BEAUTIFULSOUP_DOCUMENT_REQUIRED')
    selected: dict[str, list[SelectedTable]] = {'exhibition': [], 'start': []}
    for index, table in enumerate(soup.find_all('table'), 1):
        if table.find_parent('table') is not None:
            continue
        head = table.find('thead', recursive=False)
        labels = {parser.label(c) for c in head.find_all('th')} if head else set()
        match = SelectedTable(index, table)
        if {'枠', '展示タイム'} <= labels:
            selected['exhibition'].append(match)
        if 'スタート展示' in labels:
            selected['start'].append(match)
    return {name: tuple(matches) for name, matches in selected.items()}
