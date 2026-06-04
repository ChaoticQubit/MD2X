import md2pdf.mermaid as mm


def test_extract_caption_title_hint():
    assert mm.extract_caption("flowchart TD\ntitle My Flow", "fb") == "My Flow"


def test_extract_caption_bracket():
    assert mm.extract_caption("graph LR\nA[Start Node]", "fb") == "Start Node"


def test_extract_caption_fallback():
    assert mm.extract_caption("sequenceDiagram\n  A->>B: hi", "Diagram 3") == "Diagram 3"


def test_mermaid_to_dot_basic_flow():
    dot = mm.mermaid_to_dot("flowchart TD\nA[Start] --> B[End]")
    assert dot is not None
    assert "digraph G {" in dot
    assert "rankdir=TB;" in dot
    assert 'A [label="Start"];' in dot
    assert 'B [label="End"];' in dot
    assert "A -> B;" in dot


def test_mermaid_to_dot_styles_and_label():
    dot = mm.mermaid_to_dot("graph LR\nA -.-> B\nB ==>|go| C")
    assert "rankdir=LR;" in dot
    assert "style=dashed" in dot
    assert "style=bold" in dot
    assert 'label="go"' in dot


def test_mermaid_to_dot_rejects_non_flowchart():
    assert mm.mermaid_to_dot("sequenceDiagram\n A->>B: x") is None
    assert mm.mermaid_to_dot("   ") is None


def test_mermaid_re_matches_block():
    md = "intro\n```mermaid\nflowchart TD\nA-->B\n```\nout"
    blocks = list(mm.MERMAID_RE.finditer(md))
    assert len(blocks) == 1
    assert "flowchart TD" in blocks[0].group(1)
