import pytest
from md2x.cli import _normalize_argv, build_parser


def test_normalize_bare_file_routes_to_convert():
    assert _normalize_argv(["doc.md"]) == ["convert", "doc.md"]
    assert _normalize_argv(["doc.md", "--to", "docx"]) == \
        ["convert", "doc.md", "--to", "docx"]


def test_normalize_check_flag_routes_to_convert():
    assert _normalize_argv(["--check"]) == ["convert", "--check"]


def test_normalize_site_is_left_alone():
    assert _normalize_argv(["site", "docs/"]) == ["site", "docs/"]


def test_normalize_help_is_left_alone():
    assert _normalize_argv(["-h"]) == ["-h"]
    assert _normalize_argv([]) == []


def test_parser_has_site_subcommand():
    parser = build_parser()
    args = parser.parse_args(["site", "docs/", "--archetype", "flyer",
                              "--no-ai"])
    assert args.cmd == "site"
    assert args.archetype == "flyer"
    assert args.no_ai is True


import argparse
import md2x.config as config
from md2x.site.cli import _apply_site_overrides


def _site_args(**kw):
    base = dict(archetype=None, layout=None, style=None, fidelity=None, model=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_apply_site_overrides_sets_values():
    cfg = config.deep_merge(config.DEFAULTS, {})
    _apply_site_overrides(cfg, _site_args(archetype="flyer", layout="single-page",
                                          style="bold", fidelity="preserve",
                                          model="openai:gpt-4o"))
    assert cfg["site"]["archetype"] == "flyer"
    assert cfg["site"]["layout"] == "single-page"
    assert cfg["site"]["style_prompt"] == "bold"
    assert cfg["site"]["fidelity"] == "preserve"
    assert cfg["ai"]["model"] == "openai:gpt-4o"


def test_apply_site_overrides_noops_when_none():
    cfg = config.deep_merge(config.DEFAULTS, {})
    _apply_site_overrides(cfg, _site_args())
    assert cfg["site"]["archetype"] == "reading"      # default preserved
    assert cfg["ai"]["model"] == "anthropic:claude-sonnet-4-5"
