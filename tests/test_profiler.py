import pytest
from ego_metrology import EgoProfiler, ModelSectorConfig

@pytest.fixture
def profiler():
    return EgoProfiler("deepseek-14b")

# ── Entrées invalides ─────────────────────────────────────────────────────────

def test_negative_tokens(profiler):
    with pytest.raises(ValueError):
        profiler.profile(-1)

def test_zero_tokens(profiler):
    with pytest.raises(ValueError):
        profiler.profile(0)

def test_string_tokens(profiler):
    with pytest.raises(TypeError):
        profiler.profile("1000")

def test_float_tokens(profiler):
    with pytest.raises(TypeError):
        profiler.profile(1000.5)

def test_over_context(profiler):
    with pytest.raises(ValueError):
        profiler.profile(99999)

def test_unknown_model():
    with pytest.raises(ValueError):
        EgoProfiler("gpt-99")

# ── Bornes de eta ─────────────────────────────────────────────────────────────

def test_eta_min(profiler):
    assert profiler._eta(0) == 0.0

def test_eta_max(profiler):
    assert profiler._eta(999_999) == 1.0

def test_eta_mid(profiler):
    eta = profiler._eta(8_192)
    assert abs(eta - 0.5) < 1e-6

# ── Monotonie de alpha_s ──────────────────────────────────────────────────────

def test_alpha_s_monotonic(profiler):
    a1 = profiler.get_spectatorization_ratio(1_000)
    a2 = profiler.get_spectatorization_ratio(8_000)
    a3 = profiler.get_spectatorization_ratio(15_000)
    assert a1 < a2 < a3

def test_alpha_s_range(profiler):
    for tokens in [100, 1_000, 8_000, 16_000]:
        a = profiler.get_spectatorization_ratio(tokens)
        assert 0.0 <= a <= 1.0

# ── Bornes de r_eta ───────────────────────────────────────────────────────────

def test_r_eta_bounds(profiler):
    import math
    r_1d   = (1 + math.sqrt(2)) / 2
    r_holo = math.pi / 2
    for tokens in [100, 5_000, 10_000, 16_000]:
        r = profiler.get_geometric_saturation(tokens)["r_eta"]
        assert r_1d <= r <= r_holo + 1e-9

def test_r_eta_status_safe(profiler):
    result = profiler.get_geometric_saturation(500)
    assert result["status"] == "Safe"

def test_r_eta_status_critical(profiler):
    result = profiler.get_geometric_saturation(16_000)
    assert result["status"] in ("Warning", "Critical")

# ── Profile complet ───────────────────────────────────────────────────────────

def test_profile_returns_result(profiler):
    from ego_metrology import ProfileResult
    result = profiler.profile(5_000)
    assert isinstance(result, ProfileResult)

def test_profile_calibration_status(profiler):
    result = profiler.profile(5_000)
    assert result.calibration_status == "heuristic"

def test_profile_saturation_pct(profiler):
    result = profiler.profile(8_192)
    assert abs(result.saturation_pct - 50.0) < 0.1

def test_custom_config():
    cfg = ModelSectorConfig("TestModel", 10_000, 1.0, 0.001)
    p   = EgoProfiler(cfg)
    result = p.profile(5_000)
    assert result.model == "TestModel"
