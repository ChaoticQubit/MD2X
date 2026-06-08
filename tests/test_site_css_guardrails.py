"""Tight CSS guardrails for authored sections — the fix for two live bugs:

1. Dark mode "stopped working": the authored builder is told to colour with the
   --ds-* tokens, but those carried the light palette ONLY, so every authored
   section stayed light (or went dark-on-dark) when the page flipped to dark. The
   neutral --ds-* tokens now flip in dark mode (theme.py), so authored CSS bound
   to them themes with the page.

2. "Font the same colour as the background / unreadable": a property that paints
   TEXT could use a background token (invisible text) and inline `style=` colours
   bypassed the contract entirely. The colour-role contract (css_contract) now
   pins text props to foreground tokens and fill props to surface tokens, rejects
   raw hex/keyword/function colours, and is applied to inline styles too.
"""
from md2x.site.css_contract import (lint_css, enforce_inline_styles,
                                     enforce_section_css)
from md2x.site.theme import SITE_CSS
from md2x.site import blocks_render as br
from md2x.site.blocks import AuthoredSection


# --- dark mode: the neutral --ds-* tokens flip (prong 1) --------------------

def test_dark_mode_flips_neutral_ds_tokens():
    # both dark blocks (OS media query + manual [data-theme=dark]) override the
    # neutral contract tokens, so authored CSS using them follows dark mode.
    assert SITE_CSS.count("--ds-fg:#e8edf4") == 2
    assert SITE_CSS.count("--ds-bg:#0b0f17") == 2
    assert SITE_CSS.count("--ds-card:#141a24") == 2


def test_dark_mode_does_not_flip_accent_or_scales():
    # --ds-accent (brand) and the type/space scales are never re-set in the engine
    # CSS — they stay constant across themes (only referenced via var()).
    assert "--ds-accent:" not in SITE_CSS
    assert "--ds-fs-3:" not in SITE_CSS and "--ds-space-3:" not in SITE_CSS


# --- colour-role contract (prong 2) ----------------------------------------

def test_text_prop_keeps_foreground_tokens():
    for tok in ("--ds-fg", "--ds-muted", "--ds-accent"):
        out = lint_css(f"#s .a{{color:var({tok})}}")
        assert f"color:var({tok})" in out, tok


def test_text_prop_drops_background_token_as_invisible():
    # text resolving to a background token is exactly the "same colour as bg" bug
    out = lint_css("#s .a{color:var(--ds-bg)}")
    assert "color" not in out


def test_fill_prop_drops_foreground_token_as_invisible():
    # a dark fill behind default (dark) text is the inverse invisible case
    out = lint_css("#s .a{background:var(--ds-fg)}")
    assert "background" not in out


def test_fill_prop_keeps_surface_tokens():
    for decl in ("background:var(--ds-card)", "background:var(--ds-bg)",
                 "background:transparent", "background:var(--accent-soft)"):
        out = lint_css(f"#s .a{{{decl}}}")
        assert decl in out, decl


def test_drops_bare_keyword_colours():
    # white/black slip past the hex/rgb guard — the role contract catches them
    assert "white" not in lint_css("#s .a{color:white}")
    assert "black" not in lint_css("#s .a{background:black}")


def test_drops_raw_colour_functions():
    assert "rgb" not in lint_css("#s .a{color:rgb(0,0,0)}")
    assert "oklch" not in lint_css("#s .a{color:oklch(0.7 0.1 200)}")


def test_keeps_color_mix_and_gradient_over_allowed_tokens():
    mix = "background:color-mix(in srgb, var(--ds-accent) 12%, transparent)"
    assert "color-mix" in lint_css(f"#s .a{{{mix}}}")
    grad = "background:linear-gradient(180deg, var(--ds-bg), var(--ds-card))"
    assert "linear-gradient" in lint_css(f"#s .a{{{grad}}}")


def test_border_shorthand_with_token_survives():
    out = lint_css("#s .a{border:1px solid var(--ds-border)}")
    assert "border:1px solid var(--ds-border)" in out


def test_non_colour_props_unaffected():
    out = lint_css("#s .a{gap:8px;display:grid;color:#fff}")
    assert "gap:8px" in out and "display:grid" in out and "#fff" not in out


# --- inline `style=` enforcement (prong 2, the bypass hole) -----------------

def test_inline_style_drops_raw_colour_keeps_layout():
    out = enforce_inline_styles('<div style="color:#fff;padding:8px">x</div>')
    assert "#fff" not in out and "padding:8px" in out


def test_inline_style_removed_when_only_invisible_colour():
    out = enforce_inline_styles('<p style="color:var(--ds-bg)">y</p>')
    assert "style=" not in out and "<p" in out and "y</p>" in out


def test_inline_style_removed_when_all_raw():
    out = enforce_inline_styles('<p style="background:#000;color:#fff">z</p>')
    assert "style=" not in out and "#000" not in out and "#fff" not in out


def test_inline_style_keeps_theme_tokens():
    out = enforce_inline_styles(
        '<p style="color:var(--ds-fg);background:var(--ds-card)">k</p>')
    assert "color:var(--ds-fg)" in out and "background:var(--ds-card)" in out


# --- authored section end-to-end -------------------------------------------

def test_authored_section_strips_inline_raw_colour():
    b = AuthoredSection(
        anchor="x", title="X", css=".k{color:var(--ds-fg)}",
        html='<p class="k" style="color:#fff;background:#000">Hi</p>')
    h = br.render_block(b)
    assert "#fff" not in h and "#000" not in h     # inline raw colour gone
    assert "color:var(--ds-fg)" in h               # theme token survives
    assert "Hi" in h


def test_authored_section_drops_wrong_role_token_in_css():
    # a dark fill behind dark text is dropped end-to-end (would be unreadable)
    b = AuthoredSection(anchor="x", title="X",
                        css=".k{background:var(--ds-fg)}", html='<p>hi</p>')
    h = br.render_block(b)
    assert "background:var(--ds-fg)" not in h


def test_enforce_section_css_still_scopes_and_keeps_tokens():
    out = enforce_section_css(".card{color:var(--ds-fg);background:var(--ds-card)}",
                              "#s1")
    assert "#s1 .card" in out
    assert "color:var(--ds-fg)" in out and "background:var(--ds-card)" in out
