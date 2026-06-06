from pathlib import Path
from md2x.site.schemas import Doc
from md2x.site import blocks


def test_pagedoc_and_leaves_construct():
    page = blocks.PageDoc(slug="a", title="A")
    assert page.blocks == []
    assert blocks.Kpi(value="1").label == ""
    assert blocks.Callout(text="x").tone == "info"
    assert blocks.Chart(kind="bar").points == []
    assert blocks.Artifact(kind="chart").export is None
    assert blocks.Export().format == "markdown" and blocks.Export().label == "Copy"


def test_build_page_doc_hero_then_prose_verbatim():
    doc = Doc(path=Path("intro.md"), title="Intro", outline=["A"],
              fragment_html="<p>The quick brown fox.</p>")
    page = blocks.build_page_doc(doc)
    assert page.slug == "intro" and page.title == "Intro"
    assert isinstance(page.blocks[0], blocks.Hero)
    assert page.blocks[0].title == "Intro"
    prose = [b for b in page.blocks if isinstance(b, blocks.Prose)]
    assert any("The quick brown fox." in p.html for p in prose)


def test_build_page_doc_splits_sections():
    doc = Doc(path=Path("g.md"), title="G", outline=["S"],
              fragment_html="<p>lead</p><h2>Sec</h2><p>body</p>")
    page = blocks.build_page_doc(doc)
    # intro stays a Prose; each H2 becomes an anchored Section with verbatim body
    prose = [b for b in page.blocks if isinstance(b, blocks.Prose)]
    assert any("lead" in p.html for p in prose)
    secs = [b for b in page.blocks if isinstance(b, blocks.Section)]
    assert len(secs) == 1 and secs[0].title == "Sec" and secs[0].anchor == "sec"
    assert any(isinstance(b, blocks.Prose) and "body" in b.html
               for b in secs[0].blocks)
