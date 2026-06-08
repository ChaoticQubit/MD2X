"""The hard design-system enforcement engine for authored sections."""
from md2x.site.css_contract import scope_css, lint_css, enforce_section_css
from md2x.site.design_css import design_css_vars
from md2x.site.schemas import DesignSystem


# --- scope_css --------------------------------------------------------------

def test_scope_prefixes_each_selector():
    out = scope_css(".a,.b{color:var(--ds-fg)}", "#s1")
    assert "#s1 .a" in out and "#s1 .b" in out


def test_scope_collapses_root_html_body():
    out = scope_css("body{padding:var(--ds-space-3)} :root{--x:1}", "#s1")
    assert "#s1 body" not in out and "#s1{padding" in out
    assert "#s1{--x:1}" in out


def test_scope_strips_import_and_fontface():
    out = scope_css('@import url(http://x);@font-face{font-family:x}.a{color:red}',
                    "#s1")
    assert "@import" not in out and "@font-face" not in out and "#s1 .a" in out


def test_scope_handles_media_and_keyframes():
    css = "@media (max-width:600px){.a{color:var(--ds-fg)}}@keyframes k{from{opacity:0}}"
    out = scope_css(css, "#s1")
    assert "@media" in out and "#s1 .a" in out
    assert "@keyframes k" in out and "#s1 from" not in out


def test_scope_is_idempotent_safe_on_empty():
    assert scope_css("", "#s1") == ""
    assert scope_css(None, "#s1") == ""


# --- lint_css ---------------------------------------------------------------

def test_lint_drops_raw_color_keeps_token():
    out = lint_css("#s .a{color:#ff0000;background:var(--ds-card)}")
    assert "color:#ff0000" not in out and "background:var(--ds-card)" in out


def test_lint_drops_foreign_font_keeps_token_font():
    out = lint_css("#s .a{font-family:Comic Sans} #s .b{font-family:var(--ds-font-sans)}")
    assert "Comic Sans" not in out and "var(--ds-font-sans)" in out


def test_lint_drops_offscale_px_keeps_scale_and_borders():
    out = lint_css("#s .a{margin:17px;padding:16px;border-width:1px}")
    assert "17px" not in out and "padding:16px" in out and "border-width:1px" in out


def test_lint_keeps_rgb_via_var_token():
    # value referencing a token is fine even if it mentions colour-ish text
    out = lint_css("#s .a{color:var(--ds-accent)}")
    assert "color:var(--ds-accent)" in out


# --- enforce_section_css ----------------------------------------------------

def test_enforce_section_css_scopes_then_lints():
    out = enforce_section_css(".a{color:#fff;gap:8px}", "#s1")
    assert "#s1 .a" in out and "#fff" not in out and "gap:8px" in out


# --- contract tokens (design_css) -------------------------------------------

def test_design_tokens_include_type_and_extended_space_scale():
    css = design_css_vars(DesignSystem())
    for t in ("--ds-fs-1", "--ds-fs-3", "--ds-fs-6", "--ds-space-5", "--ds-space-6"):
        assert t in css
