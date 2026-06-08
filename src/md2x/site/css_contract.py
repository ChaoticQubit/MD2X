"""Hard design-system enforcement for authored sections: scope a section's CSS
to its root and strip declarations that would break the shared visual DNA.

This is the single trust boundary that makes `render_mode: authored` safe to mix
into the main document — model CSS can neither escape its <section> nor introduce
an off-palette colour, a foreign font, or an off-scale size. Sections vary in
components and layout; the contract keeps them one coherent page.
"""
from __future__ import annotations

import re

from ..log import get_logger

log = get_logger(__name__)

_COMMENT = re.compile(r"/\*.*?\*/", re.S)
_ROOTISH = re.compile(r"(?i)^(:root|html|body)$")
# at-rules dropped wholesale (network / font loading / charset / namespace)
_DROP_AT = re.compile(r"(?i)^@(import|font-face|charset|namespace)\b")
# at-rules whose *body* contains nested rules to scope
_NEST_AT = re.compile(r"(?i)^@(media|supports|container)\b")

# Contract value guards (applied to already-scoped CSS).
_PX_OK = {"0", "1px", "2px", "3px", "4px", "8px", "12px", "16px",
          "24px", "32px", "48px", "64px"}
_COLOR_LIT = re.compile(r"(?i)#[0-9a-f]{3,8}\b|\b(rgb|rgba|hsl|hsla)\(")
_PX = re.compile(r"(?i)\b\d+(?:\.\d+)?px\b")

# --- colour-role contract ---------------------------------------------------
# The single rule that kills both bugs the authored sections caused:
#   * "dark mode broke" — sections styled with the --ds-* light-palette tokens
#     stayed light; those neutral tokens now flip in dark mode (theme.py), so any
#     allowed colour here is theme-following by construction.
#   * "font the same colour as the background" — a property that paints TEXT may
#     ONLY use a foreground token, a property that paints a FILL may ONLY use a
#     surface/emphasis token. Text can never resolve to a background token (and
#     vice-versa), so an authored colour can never be invisible.
# Raw hex/rgb/hsl, bare colour keywords (white/black/red…), and raw colour
# functions (oklch/lab/…) are all rejected — only the design tokens get through.
_TEXT_PROPS = {"color", "-webkit-text-fill-color", "caret-color", "stroke"}
_FILL_PROPS = {"background", "background-color", "fill"}
_BORDER_PROPS = {
    "border", "border-top", "border-right", "border-bottom", "border-left",
    "border-color", "border-top-color", "border-right-color",
    "border-bottom-color", "border-left-color", "outline", "outline-color",
}
_TEXT_TOK = {"--ds-fg", "--ds-muted", "--ds-accent", "--fg", "--muted", "--accent"}
_FILL_TOK = {"--ds-bg", "--ds-card", "--ds-accent", "--bg", "--card", "--surface",
             "--accent", "--accent-soft"}
_BORDER_TOK = {"--ds-border", "--ds-accent", "--border", "--accent", "--accent-line"}

# functions allowed inside a colour value (anything else — rgb()/hsl()/oklch()/
# lab()/color() — is a raw colour and rejects the declaration).
_COLOR_FUNCS = {"var", "color-mix", "linear-gradient", "radial-gradient",
                "conic-gradient", "repeating-linear-gradient",
                "repeating-radial-gradient", "repeating-conic-gradient"}
# non-colour words a colour/background/border value may legitimately contain
# (border styles, gradient geometry, repeat/clip/global keywords). Any OTHER bare
# word is a raw colour name and rejects the declaration.
_STRUCT_WORDS = {
    "solid", "dashed", "dotted", "double", "groove", "ridge", "inset", "outset",
    "hidden", "thin", "medium", "thick", "none", "auto",
    "inherit", "initial", "unset", "revert", "currentcolor", "transparent",
    "to", "at", "in", "from", "srgb", "oklab", "oklch", "hsl", "longer",
    "shorter", "hue", "top", "bottom", "left", "right", "center", "circle",
    "ellipse", "closest", "farthest", "side", "corner", "no-repeat", "repeat",
    "repeat-x", "repeat-y", "round", "space", "cover", "contain", "border-box",
    "padding-box", "content-box", "fixed", "scroll", "local", "clip", "text",
}
_VAR_NAME = re.compile(r"(?is)var\(\s*(--[a-z0-9-]+)")
_FUNC_NAME = re.compile(r"(?is)\b([a-z][a-z0-9-]*)\s*\(")
_FUNC_CALL = re.compile(r"(?is)[a-z][a-z0-9-]*\([^()]*\)")
_NUM_UNIT = re.compile(r"(?i)\b\d[\d.]*(?:px|rem|em|%|deg|grad|rad|turn|fr|vh|vw|s|ms)?\b")


def _color_role(prop: str):
    """The allowed token set for a colour-bearing property, or None if `prop` is
    not a colour property (handled by the generic value guard)."""
    if prop in _TEXT_PROPS:
        return _TEXT_TOK
    if prop in _FILL_PROPS:
        return _FILL_TOK
    if prop in _BORDER_PROPS:
        return _BORDER_TOK
    return None


def _color_value_ok(value: str, allowed: set[str]) -> bool:
    """A colour value passes iff every var() it references is allowed for this
    role, it uses no raw colour function, and it carries no raw hex/keyword
    colour. This is what forces theme-following, contrast-safe colours."""
    v = value.strip().lower()
    if not v:
        return False
    for name in _VAR_NAME.findall(v):
        if name not in allowed:
            return False                              # wrong-role / unknown token
    for fn in _FUNC_NAME.findall(v):
        if fn not in _COLOR_FUNCS:
            return False                              # raw colour function
    if _COLOR_LIT.search(v):
        return False                                  # raw hex / rgb / hsl
    rest = _FUNC_CALL.sub(" ", v)                     # drop innermost calls (vars)
    rest = _FUNC_CALL.sub(" ", rest)                  # one more nesting (color-mix)
    rest = _NUM_UNIT.sub(" ", rest).replace(",", " ").replace("/", " ")
    for word in re.findall(r"[a-z][a-z-]+", rest):
        if word not in _STRUCT_WORDS:
            return False                              # bare colour keyword
    return True


def _split_rules(css: str):
    """Yield (head, body, is_block) at brace depth 0. `head` is the selector or
    at-rule head; `body` is the text inside the matching braces. A trailing
    non-block fragment is yielded with is_block=False."""
    depth, start, body_start, head = 0, 0, 0, None
    for i, ch in enumerate(css):
        if ch == "{":
            if depth == 0:
                head = css[start:i].strip()
                body_start = i + 1
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0:
                    yield head, css[body_start:i], True
                    start = i + 1
    tail = css[start:].strip()
    if tail:
        yield tail, "", False


def _scope_selector_list(selectors: str, root: str) -> str:
    out = []
    for sel in selectors.split(","):
        sel = sel.strip()
        if not sel:
            continue
        out.append(root if _ROOTISH.match(sel) else f"{root} {sel}")
    return ",".join(out)


def scope_css(css: str, root: str) -> str:
    """Prefix every selector with `root` so the CSS cannot affect anything outside
    the section. `:root`/`html`/`body` collapse to `root` itself; @media/@supports
    bodies are scoped recursively; @keyframes pass through; @import/@font-face are
    dropped."""
    css = _COMMENT.sub("", css or "")
    parts = []
    for head, body, is_block in _split_rules(css):
        if not is_block:
            continue                       # stray top-level declaration — drop
        if head.startswith("@"):
            if _DROP_AT.match(head):
                log.debug("css_contract: dropped at-rule %r", head[:40])
                continue
            if head.lower().startswith("@keyframes"):
                parts.append(f"{head}{{{body}}}")      # keyframe stops are not page selectors
                continue
            if _NEST_AT.match(head):
                parts.append(f"{head}{{{scope_css(body, root)}}}")
                continue
            log.debug("css_contract: dropped unknown at-rule %r", head[:40])
            continue
        parts.append(f"{_scope_selector_list(head, root)}{{{body.strip()}}}")
    return "".join(parts)


def _decl_ok(prop: str, value: str) -> bool:
    p, v = prop.strip().lower(), value.strip()
    if not p:
        return False
    allowed = _color_role(p)
    if allowed is not None:
        return _color_value_ok(v, allowed)            # colour-role contract
    has_var = "var(" in v
    if _COLOR_LIT.search(v) and not has_var:
        return False                                  # raw colour → force a token
    if p in ("font", "font-family") and not has_var:
        return False                                  # foreign font stack
    for px in _PX.findall(v):
        if px.lower() not in _PX_OK:
            return False                              # off-scale px
    return True


def _filter_decls(body: str) -> str:
    """Keep only the declarations that pass the contract; drop the rest. Shared by
    the <style>-block linter and the inline-`style=` enforcer so both hold model
    CSS to exactly the same rules."""
    kept = []
    for decl in body.split(";"):
        if ":" not in decl:
            continue
        prop, value = decl.split(":", 1)
        if _decl_ok(prop, value):
            kept.append(f"{prop.strip()}:{value.strip()}")
        else:
            log.debug("css_contract: dropped decl %r", decl.strip()[:60])
    return ";".join(kept)


def lint_css(css: str) -> str:
    """Drop declarations that violate the contract; keep the rest. Operates on
    already-scoped CSS (rules of the form `<sel>{<decls>}`)."""
    out = []
    for head, body, is_block in _split_rules(css):
        if not is_block:
            continue
        if head.startswith("@"):
            low = head.lower()
            if low.startswith(("@media", "@supports", "@container")):
                out.append(f"{head}{{{lint_css(body)}}}")
            elif low.startswith("@keyframes"):
                out.append(f"{head}{{{body}}}")
            continue
        kept = _filter_decls(body)
        if kept:
            out.append(f"{head}{{{kept}}}")
    return "".join(out)


_STYLE_ATTR = re.compile(r"""(?is)\sstyle\s*=\s*(?:"([^"]*)"|'([^']*)')""")


def enforce_inline_styles(html: str) -> str:
    """Hold every inline `style="…"` attribute to the same contract as a section's
    <style> block. The model is told to style via the `css` field (scoped+linted),
    but a stray inline colour would otherwise bypass the contract entirely (it is
    not part of the <style> CSS) and break theme/contrast. An attribute left empty
    after filtering is removed."""
    def repl(m: re.Match) -> str:
        body = m.group(1) if m.group(1) is not None else (m.group(2) or "")
        kept = _filter_decls(body)
        return f' style="{kept}"' if kept else ""

    return _STYLE_ATTR.sub(repl, html or "")


def enforce_section_css(css: str, root: str) -> str:
    """Scope then lint — the full contract a section's authored CSS must pass."""
    return lint_css(scope_css(css, root))
