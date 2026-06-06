import md2x.config as config
from md2x.site import pipeline, schemas


def _doc(p, c):
    return schemas.Doc(path=p, title="A", outline=[],
                       fragment_html="<p>The quick brown fox.</p>")


def test_blocks_mode_routes_to_write_blocks_site(tmp_path, monkeypatch):
    import md2x.site.blocks_render as br
    seen = {}
    monkeypatch.setattr(pipeline, "build_doc", _doc)

    def fake_write_blocks(out_dir, docs, plan, enh, cfg, **_):
        seen["blocks"] = True
        seen["text"] = docs[0].fragment_html

    monkeypatch.setattr(br, "write_blocks_site", fake_write_blocks)
    md = tmp_path / "a.md"; md.write_text("# A\n\nbody\n")
    cfg = config.deep_merge(config.DEFAULTS, {})        # render_mode=blocks default
    rc = pipeline.generate_site([md], tmp_path / "out", cfg,
                                use_ai=False, layout="multi-page")
    assert rc == 0 and seen.get("blocks")
    assert "quick brown fox" in seen["text"]


def test_hybrid_mode_routes_to_write_blocks_site(tmp_path, monkeypatch):
    import md2x.site.blocks_render as br
    seen = {}
    monkeypatch.setattr(pipeline, "build_doc", _doc)
    monkeypatch.setattr(br, "write_blocks_site",
                        lambda *a, **k: seen.setdefault("hybrid", True))
    md = tmp_path / "a.md"; md.write_text("# A\n\nbody\n")
    cfg = config.deep_merge(config.DEFAULTS, {})
    cfg["site"]["render_mode"] = "hybrid"
    rc = pipeline.generate_site([md], tmp_path / "out", cfg,
                                use_ai=False, layout="multi-page")
    assert rc == 0 and seen.get("hybrid")


def test_report_archetype_still_routes_to_report(tmp_path, monkeypatch):
    import md2x.site.report as report
    called = {}
    monkeypatch.setattr(pipeline, "build_doc", _doc)

    def fake_report(docs, out, cfg, *, use_ai):
        called["r"] = True
        return 0

    monkeypatch.setattr(report, "generate_report_site", fake_report)
    md = tmp_path / "a.md"; md.write_text("# A\n\nbody\n")
    cfg = config.deep_merge(config.DEFAULTS, {})
    cfg["site"]["archetype"] = "report"
    rc = pipeline.generate_site([md], tmp_path / "out", cfg,
                                use_ai=False, layout="multi-page")
    assert rc == 0 and called.get("r")
