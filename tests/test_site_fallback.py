"""Glance-able degradation when a section can't be synthesised: a lead paragraph
plus a collapsible, instead of dumping the whole verbatim body inline."""
import pytest

pytest.importorskip("agno")

from md2x.site.blocks_agent import _condensed_fallback
from md2x.site.blocks import Prose, Collapsible


def test_empty_section_yields_nothing():
    assert _condensed_fallback("") == []
    assert _condensed_fallback("   ") == []


def test_short_section_shown_as_is():
    out = _condensed_fallback("<p>A short section.</p>")
    assert len(out) == 1 and isinstance(out[0], Prose)
    assert "short section" in out[0].html


def test_long_section_is_lead_plus_collapsible():
    body = "<p>The lead sentence carries the gist.</p><p>" + ("x" * 1200) + "</p>"
    out = _condensed_fallback(body)
    assert isinstance(out[0], Prose) and "lead sentence" in out[0].html
    assert any(isinstance(b, Collapsible) for b in out)        # rest tucked away
    assert "x" * 1200 not in out[0].html                       # not dumped inline
    coll = next(b for b in out if isinstance(b, Collapsible))
    assert "x" * 1200 in coll.html                             # available on expand
