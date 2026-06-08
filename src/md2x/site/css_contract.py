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
    has_var = "var(" in v
    if _COLOR_LIT.search(v) and not has_var:
        return False                                  # raw colour → force a token
    if p in ("font", "font-family") and not has_var:
        return False                                  # foreign font stack
    for px in _PX.findall(v):
        if px.lower() not in _PX_OK:
            return False                              # off-scale px
    return True


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
        kept = []
        for decl in body.split(";"):
            if ":" not in decl:
                continue
            prop, value = decl.split(":", 1)
            if _decl_ok(prop, value):
                kept.append(f"{prop.strip()}:{value.strip()}")
            else:
                log.debug("css_contract: dropped decl %r", decl.strip()[:60])
        if kept:
            out.append(f"{head}{{{';'.join(kept)}}}")
    return "".join(out)


def enforce_section_css(css: str, root: str) -> str:
    """Scope then lint — the full contract a section's authored CSS must pass."""
    return lint_css(scope_css(css, root))
