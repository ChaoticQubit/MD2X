"""Mermaid block extraction, caption heuristics, and dot fallback conversion."""
from __future__ import annotations

import re

MERMAID_RE = re.compile(r"```mermaid\s*\n(.*?)\n?```", re.DOTALL)
CAPTION_HINT_RE = re.compile(
    r"^\s*(?:title|%%\s*title)\s+(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def extract_caption(source: str, fallback: str) -> str:
    m = CAPTION_HINT_RE.search(source)
    if m:
        return m.group(1).strip().strip('"').strip("'")
    first = re.search(r"\[(.*?)\]", source)
    if first:
        t = first.group(1).strip()
        if len(t) <= 60:
            return t
    return fallback


MERMAID_EDGE_RE = re.compile(
    r"""
    \s*
    (?P<a>[A-Za-z0-9_\.\-]+)
    (?:\s*\[(?P<la>[^\]]*)\])?
    \s*
    (?P<arrow>-->|---|-\.->|==>|--|\.\.>)
    (?:\s*\|(?P<label>[^|]+)\|)?
    \s*
    (?P<b>[A-Za-z0-9_\.\-]+)
    (?:\s*\[(?P<lb>[^\]]*)\])?
    \s*$
    """,
    re.VERBOSE,
)
MERMAID_NODE_RE = re.compile(
    r"""^\s*(?P<id>[A-Za-z0-9_\.\-]+)\s*\[(?P<label>[^\]]*)\]\s*$""",
    re.VERBOSE,
)


def mermaid_to_dot(source: str) -> str | None:
    if not source.strip():
        return None
    first = source.strip().splitlines()[0].lower()
    if not first.startswith(("flowchart", "graph")):
        return None
    parts = first.split()
    direction = parts[1].upper() if len(parts) > 1 else "TB"
    rd = {"TB": "TB", "TD": "TB", "BT": "BT", "LR": "LR", "RL": "RL"}.get(direction, "TB")

    nodes: dict[str, str] = {}
    edges: list[tuple[str, str, str, str]] = []
    for raw in source.splitlines()[1:]:
        line = raw.strip()
        if not line or line.startswith(("%", "subgraph ", "end ", "classDef",
                                        "click", "style", "linkStyle")):
            continue
        em = MERMAID_EDGE_RE.match(line)
        if em:
            a = em.group("a"); b = em.group("b")
            if em.group("la") and a not in nodes:
                nodes[a] = em.group("la")
            if em.group("lb") and b not in nodes:
                nodes[b] = em.group("lb")
            style = "solid"
            arrow = em.group("arrow")
            if "." in arrow:
                style = "dashed"
            elif "==" in arrow:
                style = "bold"
            edges.append((a, b, style, (em.group("label") or "").strip()))
            continue
        nm = MERMAID_NODE_RE.match(line)
        if nm:
            nodes[nm.group("id")] = nm.group("label")

    out = [
        "digraph G {",
        f"  rankdir={rd};",
        '  bgcolor="white";',
        '  node [shape=box, style="rounded,filled", fillcolor="#D9E2F3",',
        '        fontname="Helvetica", fontsize=11, color="#1F4E79"];',
        '  edge [color="#2E75B6"];',
    ]
    for nid, lbl in nodes.items():
        safe = lbl.replace('"', '\\"')
        out.append(f'  {nid} [label="{safe}"];')
    for a, b, style, label in edges:
        attrs = []
        if style != "solid":
            attrs.append(f"style={style}")
        if label:
            safe = label.replace('"', '\\"')
            attrs.append(f'label="{safe}"')
        suffix = (" [" + ", ".join(attrs) + "]") if attrs else ""
        out.append(f"  {a} -> {b}{suffix};")
    out.append("}")
    return "\n".join(out)
