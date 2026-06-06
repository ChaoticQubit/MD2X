"""The report block model + deterministic builder.

ReportPage is a small, typed block vocabulary (dek, summary, stat-strip,
callouts, sections). The deterministic builder below derives one from a Doc's
HTML fragment with no LLM — it powers `--no-ai` and is the fallback when the AI
agent fails. Section bodies are the author's verbatim HTML; only the dek and
summary are derived text (and only the AI path in agent.py truly synthesizes).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ...log import get_logger

log = get_logger(__name__)


@dataclass
class Stat:
    """One KPI card in the stat strip."""
    value: str          # e.g. "+20%", "$1.4M", "99.9%"
    label: str          # e.g. "revenue", "active users"


@dataclass
class Callout:
    """A highlighted key finding."""
    text: str
    label: str = "Key finding"


@dataclass
class Section:
    """One H2 section. `html` is the author's verbatim fragment HTML."""
    title: str
    html: str


@dataclass
class ReportPage:
    """The editorial-dashboard block tree for a single report document."""
    slug: str
    title: str
    dek: str = ""                                  # hero one-liner
    summary: str = ""                              # executive summary
    stats: list[Stat] = field(default_factory=list)
    findings: list[Callout] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)


# --- HTML/text helpers ------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_H1_RE = re.compile(r"(?is)<h1\b[^>]*>.*?</h1>")
_H2_RE = re.compile(r"(?is)<h2\b[^>]*>(.*?)</h2>")
_P_RE = re.compile(r"(?is)<p\b[^>]*>(.*?)</p>")
_WS_RE = re.compile(r"\s+")
# A "stat-like" token: optional sign/currency, digits (with separators), and a
# trailing unit that signals a metric (%, K/M/B, x). We only keep tokens with a
# %, $, or magnitude unit — bare integers ("3 risks") are too noisy on their own.
_STAT_RE = re.compile(
    r"[+\-]?\$?\d[\d,]*(?:\.\d+)?\s?(?:%|[KMB]\b|x\b)?", re.IGNORECASE
)
# Words skipped/stopped on when guessing a KPI label from surrounding prose.
_FILLER = {
    "to", "of", "at", "the", "a", "an", "by", "was", "were", "is", "are", "be",
    "grew", "rose", "reached", "held", "hit", "up", "down", "and", "our", "this",
    "yoy", "year", "over", "with", "from", "in", "on", "for", "we", "saw", "than",
}


def _strip_tags(html: str) -> str:
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", html)).strip()


def _first_paragraph(html: str) -> str:
    """Plain text of the first <p> — used for dek/summary so headings (the H1
    title in particular) never leak into the framing text."""
    m = _P_RE.search(html)
    return _strip_tags(m.group(1)) if m else ""


def _first_sentences(text: str, n: int) -> str:
    if not text:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", text)
    return " ".join(p for p in parts[:n]).strip()


def split_sections(fragment_html: str) -> tuple[str, list[Section]]:
    """Split a fragment into (intro_html_before_first_H2, [Section,...]).

    Section.html is the verbatim slice between one H2 and the next — the
    author's prose is never altered.
    """
    matches = list(_H2_RE.finditer(fragment_html))
    if not matches:
        return fragment_html, []
    intro = fragment_html[: matches[0].start()]
    sections: list[Section] = []
    for i, m in enumerate(matches):
        title = _strip_tags(m.group(1))
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(fragment_html)
        sections.append(Section(title=title, html=fragment_html[start:end].strip()))
    return intro, sections


def _label_before(text: str, start: int) -> str:
    """Guess a KPI label from the 1-2 content words preceding the number."""
    words = re.findall(r"[A-Za-z][A-Za-z&/-]+", text[:start])
    picked: list[str] = []
    for w in reversed(words):
        if w.lower() in _FILLER:
            if picked:
                break          # hit filler after collecting a word -> stop
            continue           # skip leading filler ("to", "grew", ...)
        picked.append(w)
        if len(picked) >= 2:
            break
    return " ".join(reversed(picked)) or "metric"


def extract_stats(text: str, limit: int = 4) -> list[Stat]:
    """Best-effort KPI extraction: keep %/$/magnitude tokens and label each with
    the nearest preceding subject (deterministic, intentionally conservative).
    This only powers --no-ai; the AI path produces clean labels."""
    stats: list[Stat] = []
    seen: set[str] = set()
    for m in _STAT_RE.finditer(text):
        value = m.group(0).strip()
        # Require a unit/currency so bare numbers don't flood in. Case-insensitive
        # to match _STAT_RE (which is re.IGNORECASE), so "40k"/"1.2m" are kept.
        if not re.search(r"[%$KMBx]", value, re.I):
            continue
        if value in seen:
            continue
        seen.add(value)
        stats.append(Stat(value=value, label=_label_before(text, m.start())))
        if len(stats) >= limit:
            break
    return stats


def build_report_page(doc) -> ReportPage:
    """Deterministic ReportPage from a Doc — no LLM. Sections stay verbatim."""
    intro_html, sections = split_sections(doc.fragment_html)
    # Frame from the first body paragraph, not the H1 title (which the hero
    # already shows). Fall back to the first paragraph anywhere in the doc.
    intro_html = _H1_RE.sub(" ", intro_html)
    lead = _first_paragraph(intro_html) or _first_paragraph(doc.fragment_html)
    page = ReportPage(
        slug=doc.slug,
        title=doc.title,
        dek=_first_sentences(lead, 1),
        summary=_first_sentences(lead, 3),
        stats=extract_stats(_strip_tags(_H1_RE.sub(" ", doc.fragment_html))),
        sections=sections,
    )
    log.debug("report %s: deterministic page (%d sections, %d stats)",
              doc.slug, len(page.sections), len(page.stats))
    return page
