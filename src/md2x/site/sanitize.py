"""The HTML sanitization boundary — one home for every sanitizer the site uses.

The runtime guards are the iframe sandbox + the CSP `default-src 'none'` on
hybrid artifacts and full pages; these deterministic, unit-tested sanitizers are
the defense-in-depth layer that strips external/network references before output
ever ships. Context decides the script policy:

- `sanitize_inline`  — block escape-hatch (raw_html) / prose: strip ALL scripts.
- `sanitize_svg`     — inline SVG: keep drawing markup, drop scripts/handlers.
- `sanitize_artifact_html` / `sanitize_full` — interactive widgets/pages: KEEP
  inline scripts (that is the point), strip only external/network references.

`is_self_contained` verifies the result pulls no remote resource (used by evals).
"""
from __future__ import annotations

import re

_SCRIPT = re.compile(r"(?is)<script\b.*?</script\s*>")
_DANGER_TAGS = re.compile(r"(?is)</?(?:iframe|object|embed|link|meta|base|form)\b[^>]*>")
# Capture the attribute boundary (whitespace, quote, or slash) so handlers are
# caught even with no leading space — e.g. `<div id="x"onclick=...>` — and the
# boundary char is restored on replacement.
_ON_ATTR = re.compile(
    r"(?is)([\s\"'/])(on\w+\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+))")
_JS_URL = re.compile(r"(?i)(href|src|xlink:href)\s*=\s*([\"'])\s*javascript:[^\"']*\2")
_EXT_URL = re.compile(r"(?i)(href|src|xlink:href)\s*=\s*([\"'])\s*https?:[^\"']*\2")
_FOREIGN = re.compile(r"(?is)<foreignObject\b.*?</foreignObject\s*>")

_EXT_SCRIPT = re.compile(
    r'(?is)<script\b[^>]*\bsrc\s*=\s*["\']?\s*(?:https?:|//)[^>]*>(?:\s*</script\s*>)?')
_EXT_LINK = re.compile(
    r'(?is)<link\b[^>]*\bhref\s*=\s*["\']?\s*(?:https?:|//)[^>]*>')
_EXT_IFRAME_SRC = re.compile(
    r'(?i)(<iframe\b[^>]*\bsrc\s*=\s*["\'])\s*(?:https?:|//)[^"\']*(["\'])')
_EXT_IMG_SRC = re.compile(
    r'(?i)(<img\b[^>]*\bsrc\s*=\s*["\'])\s*(?:https?:|//)[^"\']*(["\'])')
_IMPORT_URL = re.compile(r'(?i)@import\s+(?:url\()?["\']?\s*(?:https?:|//)[^;]*;?')

# A remote resource LOAD: an `src`/`xlink:href`, a `<link href>` stylesheet, or a
# CSS `url()` pointing at http(s). Deliberately excludes `<a href>` (navigation,
# not a load) and `xmlns="http://..."` namespace URIs / JS string literals.
_REMOTE_REF = re.compile(
    r'(?i)(?:\b(?:src|xlink:href)\s*=\s*["\']?\s*https?:'
    r'|<link\b[^>]*\bhref\s*=\s*["\']?\s*https?:'
    r'|url\(\s*["\']?\s*https?:)')


def sanitize_inline(markup: str) -> str:
    """Block escape-hatch / prose: strip scripts, handlers, dangerous tags, URLs."""
    s = _SCRIPT.sub("", markup or "")
    s = _DANGER_TAGS.sub("", s)
    s = _ON_ATTR.sub(r"\1", s)
    s = _JS_URL.sub(r"\1=\2#\2", s)
    s = _EXT_URL.sub(r"\1=\2#\2", s)
    return s


def sanitize_svg(svg: str) -> str:
    """Inline SVG: keep drawing markup; drop scripts, foreignObject, handlers, refs."""
    s = _SCRIPT.sub("", svg or "")
    s = _FOREIGN.sub("", s)
    s = _ON_ATTR.sub(r"\1", s)
    s = _JS_URL.sub(r"\1=\2#\2", s)
    s = _EXT_URL.sub(r"\1=\2#\2", s)
    return s


def sanitize_artifact_html(markup: str) -> str:
    """Artifact widget HTML: keep inline scripts, strip external `<script src>`."""
    return _EXT_SCRIPT.sub("", markup or "")


def sanitize_full(doc: str) -> str:
    """Full standalone page: keep inline scripts/styles, strip external/network."""
    s = _EXT_SCRIPT.sub("", doc or "")
    s = _EXT_LINK.sub("", s)
    s = _IMPORT_URL.sub("", s)
    s = _EXT_IFRAME_SRC.sub(r"\1#\2", s)
    s = _EXT_IMG_SRC.sub(r"\1#\2", s)
    return s


def is_self_contained(html: str) -> bool:
    """True iff the markup loads no remote resource. Ignores xmlns namespace URIs
    and JS string literals (only attribute src/href and CSS url() count)."""
    return not _REMOTE_REF.search(html or "")
