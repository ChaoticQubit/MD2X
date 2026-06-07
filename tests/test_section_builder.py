"""The section-designer (per page) and section-builder (per section) agents,
fully stubbed so no network/model is touched."""
import md2x.config as config
from md2x.site import section_designer as sd
from md2x.site import section_builder as sb
from md2x.site.blocks import AuthoredSection, Artifact
from md2x.site.design_tree import DesignTree, SectionSpec
from md2x.site.schemas import Doc


def _cfg():
    cfg = config.deep_merge(config.DEFAULTS, {})
    cfg["site"]["render_mode"] = "authored"
    return cfg


def _make_doc(tmp_path):
    frag = ("<h1>Charter</h1>"
            "<h2>Roles</h2><p>Who does what.</p>"
            "<h2>Triage</h2><p>How work flows.</p>")
    return Doc(path=tmp_path / "charter.md", title="Charter",
               outline=["Roles", "Triage"], fragment_html=frag)


class _Resp:
    def __init__(self, content):
        self.content = content


def _no_agent(monkeypatch, mod):
    # never construct a real agno Agent in a unit test
    monkeypatch.setattr(mod, "_build_agent", lambda *a, **k: None)


# --- designer ---------------------------------------------------------------

def test_run_designer_maps_model_to_tree(monkeypatch, tmp_path):
    _no_agent(monkeypatch, sd)
    fake = sd._TreeM(sections=[
        sd._SpecM(anchor="roles", title="Roles", realization="inline",
                  layout="grid", components=["table:sortable"],
                  source_anchors=["roles"]),
        sd._SpecM(anchor="", title="Triage Board", realization="artifact",
                  layout="feature", source_anchors=["triage"])])
    monkeypatch.setattr(sd, "invoke_agent", lambda *a, **k: _Resp(fake))
    tree = sd.run_designer(_make_doc(tmp_path), _cfg())
    assert isinstance(tree, DesignTree) and len(tree.sections) == 2
    assert tree.sections[0].anchor == "roles" and tree.sections[0].layout == "grid"
    # blank anchor is derived from the title
    assert tree.sections[1].anchor == "triage-board"
    assert tree.sections[1].realization == "artifact"


def test_run_designer_falls_back_to_source_titles(monkeypatch, tmp_path):
    _no_agent(monkeypatch, sd)
    monkeypatch.setattr(sd, "invoke_agent",
                        lambda *a, **k: _Resp(sd._TreeM(sections=[])))
    tree = sd.run_designer(_make_doc(tmp_path), _cfg())
    assert [s.anchor for s in tree.sections] == ["roles", "triage"]


# --- builder ----------------------------------------------------------------

def test_builder_inline_returns_authored_section(monkeypatch):
    _no_agent(monkeypatch, sb)
    fake = sb._BuiltM(realization="inline", html="<div class='c'>x</div>",
                      css=".c{color:var(--ds-fg)}")
    monkeypatch.setattr(sb, "invoke_agent", lambda *a, **k: _Resp(fake))
    blk = sb.run_builder(SectionSpec(anchor="a", title="A"), "<p>src</p>", _cfg())
    assert isinstance(blk, AuthoredSection) and blk.anchor == "a"
    assert ".c{color:var(--ds-fg)}" in blk.css


def test_builder_artifact_returns_artifact(monkeypatch):
    _no_agent(monkeypatch, sb)
    fake = sb._BuiltM(realization="artifact", kind="board",
                      html="<div></div>", css="", js="console.log(1)")
    monkeypatch.setattr(sb, "invoke_agent", lambda *a, **k: _Resp(fake))
    blk = sb.run_builder(SectionSpec(anchor="t", title="T", realization="artifact"),
                         "<p>src</p>", _cfg())
    assert isinstance(blk, Artifact) and blk.kind == "board"
    assert blk.js == "console.log(1)"


def test_builder_defaults_realization_from_spec(monkeypatch):
    _no_agent(monkeypatch, sb)
    # model leaves realization blank -> fall back to the spec's
    fake = sb._BuiltM(realization="", kind="board", html="<div></div>",
                      js="x()")
    monkeypatch.setattr(sb, "invoke_agent", lambda *a, **k: _Resp(fake))
    blk = sb.run_builder(SectionSpec(anchor="t", title="T", realization="artifact"),
                         "<p>s</p>", _cfg())
    assert isinstance(blk, Artifact)
