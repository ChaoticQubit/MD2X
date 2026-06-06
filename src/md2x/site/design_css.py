"""DesignSystem -> sanitized CSS custom properties (--ds-*), plus the living
design-system page (Thariq's tokens -> copyable swatches).

Sanitization here is the single trust boundary for design DNA: an unsafe colour,
length, or font-stack from config or the model can never break out of <style>.
"""
from __future__ import annotations

import html
import re

from ..log import get_logger
from .schemas import DesignSystem

log = get_logger(__name__)

# Canonical colour guard, owned here (design concern). render.py re-exports these
# for the report path; keeping them here keeps design_css free of a render import.
# Allows #hex (3-8 digits), a bare CSS keyword, or rgb()/rgba()/hsl()/hsla() —
# anything else is rejected so a config- or model-supplied colour can never break
# out of the <style> block.
_SAFE_COLOR = re.compile(
    r"^#[0-9a-fA-F]{3,8}$"
    r"|^[a-zA-Z]{2,32}$"
    r"|^(rgb|rgba|hsl|hsla)\([0-9.,%\s/]+\)$"
)
_DEFAULT_ACCENT = "#2563eb"

_SAFE_LEN = re.compile(r"^[0-9]+(?:\.[0-9]+)?(?:px|rem|em|%)$")
# Font stacks: letters/digits/space/comma plus quotes and hyphen only.
_SAFE_FONT = re.compile(r'^[\w ,"\'\-]+$')
_DEFAULTS = DesignSystem()

# Density -> 4-step spacing scale (rem).
_SPACE = {
    "comfortable": ("0.5rem", "1rem", "1.5rem", "2.5rem"),
    "compact":     ("0.35rem", "0.7rem", "1.1rem", "1.8rem"),
}


def _color(value: str, fallback: str) -> str:
    value = (value or "").strip()
    if _SAFE_COLOR.match(value):
        return value
    log.warning("design: unsafe colour %r; using %s", value, fallback)
    return fallback


def _len(value: str, fallback: str) -> str:
    value = (value or "").strip()
    if _SAFE_LEN.match(value):
        return value
    log.warning("design: unsafe length %r; using %s", value, fallback)
    return fallback


def _font(value: str, fallback: str) -> str:
    value = (value or "").strip()
    if _SAFE_FONT.match(value):
        return value
    log.warning("design: unsafe font %r; using default", value)
    return fallback


def _tokens(ds: DesignSystem) -> dict[str, str]:
    density = ds.density if ds.density in _SPACE else "comfortable"
    s1, s2, s3, s4 = _SPACE[density]
    return {
        "--ds-accent": _color(ds.accent, _DEFAULT_ACCENT),
        "--ds-bg": _color(ds.bg, _DEFAULTS.bg),
        "--ds-fg": _color(ds.fg, _DEFAULTS.fg),
        "--ds-muted": _color(ds.muted, _DEFAULTS.muted),
        "--ds-card": _color(ds.card, _DEFAULTS.card),
        "--ds-border": _color(ds.border, _DEFAULTS.border),
        "--ds-radius": _len(ds.radius, _DEFAULTS.radius),
        "--ds-font-sans": _font(ds.font_sans, _DEFAULTS.font_sans),
        "--ds-font-mono": _font(ds.font_mono, _DEFAULTS.font_mono),
        "--ds-density": density,
        "--ds-space-1": s1, "--ds-space-2": s2,
        "--ds-space-3": s3, "--ds-space-4": s4,
    }


def design_css_vars(ds: DesignSystem) -> str:
    """`:root{--ds-*: ...}` — sanitized, ready to drop in a <style>."""
    body = ";".join(f"{k}:{v}" for k, v in _tokens(ds).items())
    return f":root{{{body}}}"


def render_design_system_page(ds: DesignSystem, *, title: str = "Design System") -> str:
    """Standalone tokens -> copyable swatches page. Self-contained, no network."""
    toks = _tokens(ds)
    swatches = "".join(
        f'<button class="sw" data-c="{html.escape(v, quote=True)}" '
        f'style="--c:{v}"><span class="chip"></span>'
        f'<code>{html.escape(k)}</code><code class="val">{html.escape(v)}</code>'
        f"</button>"
        for k, v in toks.items() if k.endswith(("accent", "bg", "fg", "muted",
                                                "card", "border"))
    )
    spaces = "".join(
        f'<div class="sp"><span style="width:{toks[k]}"></span>'
        f'<code>{html.escape(k)}</code>'
        f'<code class="val">{html.escape(toks[k])}</code></div>'
        for k in ("--ds-space-1", "--ds-space-2", "--ds-space-3", "--ds-space-4")
    )
    css = (
        f"{design_css_vars(ds)}"
        "*{box-sizing:border-box}body{margin:0;background:var(--ds-bg);"
        "color:var(--ds-fg);font-family:var(--ds-font-sans);padding:var(--ds-space-4)}"
        "h1{font-size:1.8rem}h2{margin-top:var(--ds-space-4);font-size:1.1rem;"
        "text-transform:uppercase;letter-spacing:.08em;color:var(--ds-muted)}"
        ".grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));"
        "gap:var(--ds-space-2)}"
        ".sw{display:flex;flex-direction:column;gap:6px;align-items:flex-start;"
        "padding:var(--ds-space-2);border:1px solid var(--ds-border);"
        "border-radius:var(--ds-radius);background:var(--ds-card);cursor:pointer;"
        "font-family:var(--ds-font-mono);font-size:.78rem;color:var(--ds-fg)}"
        ".chip{width:100%;height:46px;border-radius:calc(var(--ds-radius) - 2px);"
        "background:var(--c);border:1px solid var(--ds-border)}"
        ".val{color:var(--ds-muted)}"
        ".sp{display:flex;align-items:center;gap:10px;margin:8px 0;"
        "font-family:var(--ds-font-mono);font-size:.78rem}"
        ".sp span{height:14px;background:var(--ds-accent);border-radius:3px;"
        "display:inline-block}"
        ".copied{outline:2px solid var(--ds-accent)}"
    )
    js = ("document.querySelectorAll('.sw').forEach(function(b){"
          "b.addEventListener('click',function(){var c=b.getAttribute('data-c');"
          "if(navigator.clipboard)navigator.clipboard.writeText(c);"
          "b.classList.add('copied');setTimeout(function(){"
          "b.classList.remove('copied')},700);});});")
    return (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
        "style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:\">\n"
        f"<title>{html.escape(title)}</title>\n<style>{css}</style>\n</head>\n<body>\n"
        f"<h1>{html.escape(title)}</h1>\n"
        f'<h2>Colour tokens</h2>\n<div class="grid">{swatches}</div>\n'
        f"<h2>Spacing</h2>\n{spaces}\n"
        f"<script>{js}</script>\n</body>\n</html>\n"
    )
