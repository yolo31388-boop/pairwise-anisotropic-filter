import pytest
from render import anisotropic_filtering as mod

CASES = [
    ("deriv", 'm.uv_derivative(3, 4) == approx(5.0)'),
    ("ratio", 'm.aniso_ratio(16, 1) == approx(16.0)'),
    ("samples", 'm.aniso_samples(8, 4) == 4'),
    ("mip", 'm.mip_level(256, 256, 1 / 256, 1 / 256) == approx(0.0)'),
    ("bias", 'm.lod_bias(0, 8) == -3'),
    ("tri", 'm.trilinear_weight(2.25) == approx(0.25)'),
    ("layer", 'm.array_layer(3, 2) == 5'),
    ("bc7", 'm.bc7_alpha_mode(1) is True'),
    ("sampler", 'm.sampler_key("wrap", "linear", 4) == "wrap:linear:4"'),
    ("camkey", 'm.camera_aniso_key("L") == "L"'),
    ("footprint", 'm.texture_footprint((0.5, 0.25), 800, 400) == approx((400.0, 100.0))'),
    ("clamp", 'm.clamp_lod(9, 5) == 5'),
    ("wrap", 'm.wrap_uv(1.25, "wrap") == approx(0.25)'),
    ("axis", 'm.aniso_axis(3, 1) == "x"'),
    ("degrade", 'm.degrade_samples(8) == 4')
]

@pytest.mark.parametrize("name,expr", CASES, ids=[c[0] for c in CASES])
def test_contract(name, expr):
    assert eval(expr, {"m": mod, "approx": pytest.approx})
