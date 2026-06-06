import md2x.config as config


def test_defaults_have_site_block():
    cfg = config.deep_merge(config.DEFAULTS, {})
    assert cfg["site"]["archetype"] == "reading"
    assert cfg["site"]["layout"] == "auto"
    assert cfg["site"]["fidelity"] == "synthesize"


def test_defaults_have_render_mode():
    cfg = config.deep_merge(config.DEFAULTS, {})
    assert cfg["site"]["render_mode"] == "hybrid"


def test_defaults_have_ai_block():
    cfg = config.deep_merge(config.DEFAULTS, {})
    assert cfg["ai"]["model"] == "anthropic:claude-sonnet-4-6"
    assert cfg["ai"]["concurrency"] == 4


def test_defaults_have_deploy_block():
    cfg = config.deep_merge(config.DEFAULTS, {})
    assert cfg["deploy"]["provider"] == "vercel"
    assert cfg["deploy"]["token_env"] == "VERCEL_TOKEN"
