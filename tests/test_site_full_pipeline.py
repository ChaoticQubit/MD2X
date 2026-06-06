import md2x.config as config
from md2x.site import pipeline, schemas


def _doc(p, c):
    return schemas.Doc(path=p, title="A", outline=[],
                       fragment_html="<p>The quick brown fox.</p>")


def test_full_mode_routes_to_write_full_site(tmp_path, monkeypatch):
    import md2x.site.full_render as fr
    seen = {}
    monkeypatch.setattr(pipeline, "build_doc", _doc)

    def fake_write_full(out_dir, docs, plan, cfg, *, use_ai):
        seen["full"] = True
        seen["text"] = docs[0].fragment_html

    monkeypatch.setattr(fr, "write_full_site", fake_write_full)
    # full mode must NOT run the per-page enhancement agents.
    def _boom(*a, **k):
        raise AssertionError("enhancement must not run in full mode")
    monkeypatch.setattr(pipeline, "_enhance_all", _boom)

    md = tmp_path / "a.md"; md.write_text("# A\n\nbody\n")
    cfg = config.deep_merge(config.DEFAULTS, {})
    cfg["site"]["render_mode"] = "full"
    rc = pipeline.generate_site([md], tmp_path / "out", cfg,
                                use_ai=False, layout="multi-page")
    assert rc == 0 and seen.get("full")
    assert "quick brown fox" in seen["text"]
