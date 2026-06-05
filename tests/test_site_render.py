from pathlib import Path
import md2x.config as config
from md2x.site.schemas import Doc, PageEnhancement
from md2x.site import render



def _cfg(archetype="reading"):
    cfg = config.deep_merge(config.DEFAULTS, {})
    cfg["site"]["archetype"] = archetype
    return cfg


def _docs():
    return [
        Doc(path=Path("intro.md"), title="Intro", outline=["A"],
            fragment_html="<p>The quick brown fox.</p>"),
        Doc(path=Path("guide.md"), title="Guide", outline=["B"],
            fragment_html="<p>Second page body.</p>"),
    ]


def test_default_site_plan_one_nav_per_doc():
    plan = render.default_site_plan(_docs(), _cfg())
    assert [n.slug for n in plan.nav] == ["intro", "guide"]
    assert plan.order == ["intro", "guide"]


def test_build_page_is_self_contained_and_keeps_body():
    cfg = _cfg()
    plan = render.default_site_plan(_docs(), cfg)
    html = render.build_page(_docs()[0], plan, PageEnhancement(), cfg,
                             assets_inline=True)
    assert "The quick brown fox." in html          # body verbatim
    assert "<nav" in html and "Guide" in html       # navigation present
    assert "http://" not in html and "https://" not in html  # no external deps
    assert "<style" in html                          # inlined assets


def test_light_enhance_blocks_are_additive():
    cfg = _cfg()
    plan = render.default_site_plan(_docs(), cfg)
    enh = PageEnhancement(tldr="Short summary.",
                          takeaways=["one", "two"], related=["guide"])
    html = render.build_page(_docs()[0], plan, enh, cfg, assets_inline=True)
    assert "The quick brown fox." in html            # original still there
    assert "Short summary." in html
    assert "one" in html and "two" in html


def test_related_drops_unknown_slugs():
    cfg = _cfg()
    plan = render.default_site_plan(_docs(), cfg)  # real slugs: intro, guide
    enh = PageEnhancement(related=["guide", "using-quark-engine"])
    html = render.build_page(_docs()[0], plan, enh, cfg, assets_inline=True)
    assert 'href="guide.html"' in html               # real page linked
    assert "using-quark-engine" not in html          # invented slug dropped


def test_related_all_unknown_emits_no_block():
    cfg = _cfg()
    plan = render.default_site_plan(_docs(), cfg)
    enh = PageEnhancement(related=["ghost-a", "ghost-b"])
    html = render.build_page(_docs()[0], plan, enh, cfg, assets_inline=True)
    assert "Related" not in html                      # empty Related suppressed


def test_write_site_multipage_emits_files(tmp_path):
    cfg = _cfg()  # reading -> sidebar
    docs = _docs()
    plan = render.default_site_plan(docs, cfg)
    enh = {d.slug: PageEnhancement() for d in docs}
    render.write_site(tmp_path, docs, plan, enh, cfg, layout="multi-page")
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "intro.html").exists()
    assert (tmp_path / "guide.html").exists()
    assert (tmp_path / "assets" / "site.css").exists()


def test_write_site_singlepage_emits_one_file(tmp_path):
    cfg = _cfg()
    docs = _docs()
    plan = render.default_site_plan(docs, cfg)
    enh = {d.slug: PageEnhancement() for d in docs}
    render.write_site(tmp_path, docs, plan, enh, cfg, layout="single-page")
    assert (tmp_path / "index.html").exists()
    body = (tmp_path / "index.html").read_text()
    assert "The quick brown fox." in body and "Second page body." in body
    assert not (tmp_path / "assets").exists()  # inlined


def test_deck_shell_has_slides_and_all_bodies():
    cfg = _cfg("presentation")
    docs = _docs()
    plan = render.default_site_plan(docs, cfg)
    enh = {d.slug: PageEnhancement() for d in docs}
    html = render.build_deck(docs, plan, enh, cfg)
    assert 'class="slide"' in html
    assert "The quick brown fox." in html and "Second page body." in html
    assert "http://" not in html and "https://" not in html


def test_landing_shell_has_hero_and_no_sidebar():
    cfg = _cfg("flyer")
    docs = _docs()
    plan = render.default_site_plan(docs, cfg)
    enh = {d.slug: PageEnhancement() for d in docs}
    html = render.build_landing(docs, plan, enh, cfg)
    assert 'class="hero"' in html
    assert "The quick brown fox." in html
    assert "nav class=\"side\"" not in html   # landing has no sidebar


def test_write_site_deck_is_single_index(tmp_path):
    cfg = _cfg("presentation")
    docs = _docs()
    plan = render.default_site_plan(docs, cfg)
    enh = {d.slug: PageEnhancement() for d in docs}
    # layout flag is ignored for deck/landing — always one file
    render.write_site(tmp_path, docs, plan, enh, cfg, layout="multi-page")
    assert (tmp_path / "index.html").exists()
    assert not (tmp_path / "assets").exists()
    assert not (tmp_path / "intro.html").exists()


def test_write_site_copies_diagrams_per_slug(tmp_path):
    # simulate a rendered diagram living under <docdir>/diagrams/<slug>/
    docdir = tmp_path / "src"
    (docdir / "diagrams" / "intro").mkdir(parents=True)
    (docdir / "diagrams" / "intro" / "mermaid_01.png").write_bytes(b"\x89PNG")
    docs = [Doc(path=docdir / "intro.md", title="Intro", outline=[],
                fragment_html='<img src="diagrams/intro/mermaid_01.png">')]
    cfg = _cfg()
    plan = render.default_site_plan(docs, cfg)
    out = tmp_path / "out"
    render.write_site(out, docs, plan, {docs[0].slug: PageEnhancement()},
                      cfg, layout="single-page")
    assert (out / "diagrams" / "intro" / "mermaid_01.png").exists()


def test_unsafe_accent_falls_back_to_default():
    cfg = _cfg()
    cfg["site"]["theme"]["accent"] = "red}</style><script>alert(1)</script>"
    plan = render.default_site_plan(_docs(), cfg)
    h = render.build_page(_docs()[0], plan, PageEnhancement(), cfg,
                          assets_inline=True)
    assert "<script>alert(1)</script>" not in h
    assert "#2563eb" in h  # fell back to default accent
    assert "%ACCENT%" not in h  # placeholder substituted


def test_safe_accent_passes_through():
    cfg = _cfg()
    cfg["site"]["theme"]["accent"] = "#ff0000"
    plan = render.default_site_plan(_docs(), cfg)
    h = render.build_page(_docs()[0], plan, PageEnhancement(), cfg,
                          assets_inline=True)
    assert "#ff0000" in h


def test_related_slug_cannot_break_out_of_href():
    cfg = _cfg()
    plan = render.default_site_plan(_docs(), cfg)
    enh = PageEnhancement(related=['" onmouseover="evil()'])
    h = render.build_page(_docs()[0], plan, enh, cfg, assets_inline=True)
    assert 'onmouseover="evil()"' not in h  # quote was escaped


def test_index_card_slug_cannot_break_out_of_href():
    from md2x.site.schemas import NavItem, SitePlan
    cfg = _cfg()
    plan = SitePlan(nav=[NavItem(title="Evil", slug='" onmouseover="evil()')],
                    order=["x"])
    html = render.build_index(plan, cfg, assets_inline=True)
    assert 'onmouseover="evil()"' not in html  # quote escaped


def test_text_fields_are_escaped():
    cfg = _cfg()
    docs = [Doc(path=Path("intro.md"), title="A & <B>", outline=[],
                fragment_html="<p>body</p>")]
    plan = render.default_site_plan(docs, cfg)
    h = render.build_page(docs[0], plan,
                          PageEnhancement(tldr="x < y & z"), cfg,
                          assets_inline=True)
    assert "A &amp; &lt;B&gt;" in h
    assert "x &lt; y &amp; z" in h
    assert "<p>body</p>" in h  # fragment stays raw


def test_default_site_plan_uses_configured_title():
    cfg = _cfg()
    cfg["site"]["title"] = "My Handbook"
    plan = render.default_site_plan(_docs(), cfg)
    assert plan.index_title == "My Handbook"


def test_default_site_plan_title_none_falls_back():
    cfg = _cfg()
    cfg["site"]["title"] = None
    plan = render.default_site_plan(_docs(), cfg)
    assert plan.index_title == "Documentation"
