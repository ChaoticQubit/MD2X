from md2x.site import sanitize as S


def test_sanitize_inline_strips_all_scripts_and_handlers():
    s = S.sanitize_inline("<script>x</script><p onclick='e()'>hi</p>")
    assert "<script" not in s and "onclick" not in s and "hi" in s


def test_sanitize_svg_keeps_shapes_drops_script():
    s = S.sanitize_svg("<svg><script>b</script><rect x='1'/></svg>")
    assert "<rect" in s and "<script" not in s


def test_sanitize_inline_strips_handler_without_leading_space():
    # handler glued to the previous attribute's closing quote (no space)
    s = S.sanitize_inline('<div id="x"onclick="evil()">hi</div>')
    assert "onclick" not in s and "hi" in s
    assert 'id="x"' in s                         # boundary quote preserved


def test_sanitize_svg_strips_handler_after_slash():
    s = S.sanitize_svg('<svg/onload="evil()"><rect/></svg>')
    assert "onload" not in s and "<rect" in s


def test_sanitize_artifact_html_keeps_inline_drops_external():
    s = S.sanitize_artifact_html(
        '<script src="https://e/x.js"></script><script>let a=1</script>')
    assert "https://e" not in s and "let a=1" in s


def test_sanitize_full_strips_external_keeps_inline():
    s = S.sanitize_full(
        '<link href="https://e/x.css" rel="stylesheet">'
        '<img src="https://e/i.png"><script>q=1</script>')
    assert "https://e" not in s and "q=1" in s


def test_is_self_contained():
    assert S.is_self_contained(
        '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>') is True   # namespace
    assert S.is_self_contained('<a href="https://example.com">link</a>') is True  # nav, not a load
    assert S.is_self_contained("<p>all local</p>") is True
    assert S.is_self_contained('<img src="https://e/x.png">') is False
    assert S.is_self_contained('<link href="https://e/x.css">') is False
    assert S.is_self_contained("body{background:url('https://cdn/x.png')}") is False
