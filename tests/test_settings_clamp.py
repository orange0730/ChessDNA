from chessdna.app import _clamp_analyze_settings


def test_clamp_analyze_settings_defaults_and_ranges():
    t, m, w = _clamp_analyze_settings(0.0, 999999)
    assert t == 0.01
    assert m == 800
    assert "time_per_move" in w
    assert "max_plies" in w

    t2, m2, w2 = _clamp_analyze_settings(0.05, 200)
    assert t2 == 0.05
    assert m2 == 200
    assert w2 == ""


def test_clamp_analyze_settings_bad_types():
    t, m, w = _clamp_analyze_settings("nope", "wat")  # type: ignore[arg-type]
    assert t == 0.05
    assert m == 200
    assert "回復預設" in w
