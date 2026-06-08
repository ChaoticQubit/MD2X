"""Section-coverage guardrail for the authored designer.

The designer (section_designer) is the one synthesis path that may MERGE, split,
or reorder a document's sections — and so the one path that can silently DROP a
section the reader expects (the live bug: "Certifications" and "Trainings"
vanished from a charter site). blocks/full modes iterate the source H2s 1:1, so
they can't drop a section; only the designer needs this guard.

The guard: after the designer returns its tree, every source heading must be
covered by some spec — by its `source_anchors` or by a spec whose own anchor is
that heading's slug. Any heading nothing covers is appended as a 1:1 section, so
the website is guaranteed to carry all of the document's sections (the wording
and design may differ; the section is present).
"""
from pathlib import Path

from md2x.site.section_designer import _to_tree, _TreeM, _SpecM, run_designer
from md2x.site.schemas import Doc


# --- _to_tree coverage (pure) ----------------------------------------------

def test_appends_omitted_source_sections():
    # designer kept only Alpha, dropping Certifications + Trainings
    m = _TreeM(sections=[_SpecM(anchor="alpha", title="Alpha",
                                source_anchors=["alpha"])])
    tree = _to_tree("doc", m, ["Alpha", "Certifications", "Trainings"])
    titles = [s.title for s in tree.sections]
    assert "Certifications" in titles and "Trainings" in titles
    cert = next(s for s in tree.sections if s.title == "Certifications")
    assert cert.anchor == "certifications"
    assert cert.source_anchors == ["certifications"]   # maps back to source html


def test_merged_section_covers_multiple_sources():
    # designer merged Alpha + Beta into one website section: neither re-appended
    m = _TreeM(sections=[_SpecM(anchor="overview", title="Overview",
                                source_anchors=["alpha", "beta"])])
    tree = _to_tree("doc", m, ["Alpha", "Beta"])
    assert [s.title for s in tree.sections] == ["Overview"]


def test_anchor_matches_source_when_no_source_anchors():
    # a spec whose own anchor equals the heading slug counts as covering it
    m = _TreeM(sections=[_SpecM(anchor="alpha", title="Alpha (reworded)",
                                source_anchors=[])])
    tree = _to_tree("doc", m, ["Alpha"])
    assert len(tree.sections) == 1            # not re-appended


def test_empty_model_mirrors_all_sources():
    tree = _to_tree("doc", _TreeM(sections=[]), ["Alpha", "Beta"])
    assert [s.title for s in tree.sections] == ["Alpha", "Beta"]


def test_appended_sections_keep_source_order():
    m = _TreeM(sections=[_SpecM(anchor="beta", title="Beta",
                                source_anchors=["beta"])])
    tree = _to_tree("doc", m, ["Alpha", "Beta", "Gamma"])
    appended = [s.title for s in tree.sections if s.title != "Beta"]
    assert appended == ["Alpha", "Gamma"]     # source order preserved


# --- run_designer integration (fake agent, no network) ---------------------

def test_run_designer_covers_every_source_section(monkeypatch):
    import md2x.site.section_designer as sd

    doc = Doc(path=Path("d.md"), title="D", outline=[],
              fragment_html=("<h1>D</h1>"
                             "<h2>Alpha</h2><p>a</p>"
                             "<h2>Certifications</h2><p>c</p>"
                             "<h2>Trainings</h2><p>t</p>"))

    class _Resp:                              # designer drops two sections
        content = sd._TreeM(sections=[
            sd._SpecM(anchor="alpha", title="Alpha", source_anchors=["alpha"])])

    monkeypatch.setattr(sd, "_build_agent", lambda cfg: object())
    monkeypatch.setattr(sd, "invoke_agent", lambda *a, **k: _Resp())

    cfg = {"ai": {"timeout": None},
           "site": {"archetype": "reading", "render_mode": "authored",
                    "fidelity": "synthesize"}}
    tree = run_designer(doc, cfg)
    titles = [s.title for s in tree.sections]
    assert "Certifications" in titles and "Trainings" in titles
