from md2x.site.schemas import DesignSystem
from md2x.site import design_css as dc


def test_vars_emit_ds_custom_properties():
    css = dc.design_css_vars(DesignSystem())
    for v in ("--ds-accent", "--ds-bg", "--ds-fg", "--ds-muted", "--ds-card",
              "--ds-border", "--ds-radius", "--ds-font-sans", "--ds-space-1"):
        assert v in css
    assert ":root" in css


def test_custom_accent_flows_in():
    css = dc.design_css_vars(DesignSystem(accent="#ff0000"))
    assert "#ff0000" in css


def test_unsafe_color_falls_back_to_default():
    bad = DesignSystem(accent="red}</style><script>x</script>")
    css = dc.design_css_vars(bad)
    assert "<script>" not in css
    assert "#2563eb" in css  # default accent restored


def test_unsafe_radius_and_font_rejected():
    css = dc.design_css_vars(DesignSystem(radius="8px;}evil", font_sans="a;}b"))
    assert "evil" not in css and "}b" not in css


def test_compact_density_tightens_spacing():
    comfy = dc.design_css_vars(DesignSystem(density="comfortable"))
    compact = dc.design_css_vars(DesignSystem(density="compact"))
    assert comfy != compact


def test_design_system_page_is_self_contained_swatches():
    page = dc.render_design_system_page(DesignSystem(accent="#ff0000"))
    assert "<!doctype html>" in page.lower()
    assert "#ff0000" in page                     # swatch label
    assert "--ds-accent" in page                  # consumes the token layer
    assert "http://" not in page and "https://" not in page
