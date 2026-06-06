from md2x.site import modes


def test_valid_render_modes_pass_through():
    for m in ("blocks", "hybrid", "full"):
        assert modes.validate_render_mode(m) == m


def test_unknown_render_mode_falls_back_to_default():
    assert modes.validate_render_mode("banana") == modes.DEFAULT_RENDER_MODE
    assert modes.DEFAULT_RENDER_MODE == "blocks"


def test_valid_fidelities_pass_through():
    for f in ("preserve", "light-enhance", "synthesize"):
        assert modes.validate_fidelity(f) == f


def test_unknown_fidelity_falls_back_to_default():
    assert modes.validate_fidelity("nope") == modes.DEFAULT_FIDELITY
