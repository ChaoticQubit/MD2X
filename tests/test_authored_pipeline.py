"""The authored-mode orchestrator + its wiring into modes/pipeline/page-builder.
All model calls are stubbed — no network."""
import md2x.config as config
from md2x.site import authored_agent as aa
from md2x.site import blocks_agent as ba
from md2x.site.blocks import AuthoredSection, Hero, PageDoc, Section
from md2x.site.design_tree import DesignTree, SectionSpec
from md2x.site.modes import validate_render_mode
from md2x.site.schemas import Doc, SitePlan, NavItem, PageEnhancement


def _cfg():
    cfg = config.deep_merge(config.DEFAULTS, {})
    cfg["site"]["render_mode"] = "authored"
    cfg["site"]["fidelity"] = "synthesize"
    return cfg


def _make_doc(tmp_path):
    frag = ("<h1>Charter</h1>"
            "<h2>Roles</h2><p>Who does what.</p>"
            "<h2>Triage</h2><p>How work flows.</p>")
    return Doc(path=tmp_path / "charter.md", title="Charter",
               outline=["Roles", "Triage"], fragment_html=frag)


def _plan():
    return SitePlan(nav=[NavItem(title="Charter", slug="charter")],
                    order=["charter"])


# --- orchestrator -----------------------------------------------------------

def test_authored_page_assembles_sections(monkeypatch, tmp_path):
    doc = _make_doc(tmp_path)
    monkeypatch.setattr(aa, "run_designer", lambda d, c: DesignTree(slug=doc.slug,
        sections=[SectionSpec(anchor="roles", title="Roles", source_anchors=["roles"]),
                  SectionSpec(anchor="triage", title="Triage", source_anchors=["triage"])]))
    monkeypatch.setattr(aa, "run_builder",
        lambda spec, html, cfg: AuthoredSection(anchor=spec.anchor, title=spec.title,
                                                html="<p>x</p>", css=""))
    page = aa.run_authored_page(doc, _cfg(), _plan())
    assert isinstance(page, PageDoc) and isinstance(page.blocks[0], Hero)
    anchors = [b.anchor for b in page.blocks if isinstance(b, AuthoredSection)]
    assert anchors == ["roles", "triage"]


def test_authored_page_falls_back_when_builder_raises(monkeypatch, tmp_path):
    doc = _make_doc(tmp_path)
    monkeypatch.setattr(aa, "run_designer", lambda d, c: DesignTree(slug=doc.slug,
        sections=[SectionSpec(anchor="roles", title="Roles", source_anchors=["roles"])]))

    def boom(*a, **k):
        raise RuntimeError("model down")

    monkeypatch.setattr(aa, "run_builder", boom)
    # the typed fallback would also call a model — force it to the condensed path
    monkeypatch.setattr(ba, "run_section_blocks", boom)
    page = aa.run_authored_page(doc, _cfg(), _plan())
    # never amputated: the section still appears (condensed verbatim Section)
    assert any(isinstance(b, (Section, AuthoredSection)) for b in page.blocks)


def test_authored_page_designer_failure_mirrors_sections(monkeypatch, tmp_path):
    doc = _make_doc(tmp_path)

    def boom(*a, **k):
        raise RuntimeError("designer down")

    monkeypatch.setattr(aa, "run_designer", boom)
    monkeypatch.setattr(aa, "run_builder",
        lambda spec, html, cfg: AuthoredSection(anchor=spec.anchor, title=spec.title,
                                                html="<p>x</p>", css=""))
    page = aa.run_authored_page(doc, _cfg(), _plan())
    anchors = [b.anchor for b in page.blocks if isinstance(b, AuthoredSection)]
    assert anchors == ["roles", "triage"]          # mirrored 1:1 from source H2s


# --- wiring -----------------------------------------------------------------

def test_authored_is_a_valid_mode():
    assert validate_render_mode("authored") == "authored"


def test_page_doc_for_authored_uses_authored_agent(monkeypatch, tmp_path):
    from md2x.site import blocks_render as br
    import md2x.site.authored_agent as aa_mod
    cfg = _cfg()
    called = {}

    def fake_authored(doc, c, plan):
        called["hit"] = True
        return PageDoc(slug=doc.slug, title=doc.title, blocks=[Hero(title=doc.title)])

    monkeypatch.setattr(aa_mod, "run_authored_page", fake_authored)
    page = br._page_doc_for(_make_doc(tmp_path), cfg, _plan(), use_ai=True)
    assert called.get("hit") and isinstance(page, PageDoc)


def test_authored_no_ai_writes_seamless_site(tmp_path):
    from md2x.site.blocks_render import write_blocks_site
    cfg = _cfg()
    doc = Doc(path=tmp_path / "c.md", title="Charter", outline=["Roles"],
              fragment_html="<h1>Charter</h1><h2>Roles</h2><p>Body text here.</p>")
    plan = SitePlan(nav=[NavItem(title="Charter", slug="c")], order=["c"])
    out = tmp_path / "site"
    write_blocks_site(out, [doc], plan, {"c": PageEnhancement()}, cfg, use_ai=False)
    page = (out / "c.html").read_text()
    assert '<section id="roles"' in page
    assert (out / "assets" / "site.js").exists()
    assert "http://" not in page and "https://" not in page
