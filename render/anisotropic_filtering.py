"""Anisotropic texture filtering helpers.

The functions in this module model the pieces of an anisotropic sampler:

* the per-pixel UV footprint (derivatives),
* the major/minor footprint axes and the resulting anisotropy ratio,
* the mip level and LOD bias,
* trilinear blending between neighbouring mips,
* texture-array layer selection,
* BC7 alpha-mode handling,
* and sampler/camera state keys.

The implementation deliberately follows the minor (short) footprint axis for
the mip level and lets the anisotropic sample spread handle the major axis, so
that detail along the stretched direction is preserved instead of being
averaged away by a max-axis mip selection.
"""

import math

# A degraded (low performance tier) sampler must stay anisotropic; 2x is the
# smallest useful spread that avoids snapping back to hard aliased edges.
MIN_DEGRADED_SAMPLES = 2

__all__ = [
    "uv_derivative",
    "aniso_ratio",
    "aniso_samples",
    "mip_level",
    "lod_bias",
    "trilinear_weight",
    "array_layer",
    "bc7_alpha_mode",
    "sampler_key",
    "camera_aniso_key",
    "texture_footprint",
    "clamp_lod",
    "wrap_uv",
    "aniso_axis",
    "degrade_samples",
]


def uv_derivative(dx, dy):
    """Return the length of a per-pixel UV derivative vector.

    ``dx`` and ``dy`` are the two components of the UV change across one
    pixel quad.  Taking the vector length (rather than one axis or the max
    axis) gives a footprint that is continuous across triangle boundaries.
    """
    return math.hypot(float(dx), float(dy))


def aniso_ratio(major, minor):
    """Return the anisotropy ratio (long footprint axis / short axis)."""
    a = abs(float(major))
    b = abs(float(minor))
    hi, lo = max(a, b), min(a, b)
    if lo == 0.0:
        # A zero minor footprint means the ratio is unbounded; the sample
        # count is limited by the sampler capability instead.
        return 1.0 if hi == 0.0 else math.inf
    return hi / lo


def aniso_samples(ratio, max_samples):
    """Return the adaptive anisotropic sample count for ``ratio``.

    The count follows the footprint ratio, rounded up to the next power of
    two, then clamped to ``max_samples``.  A stretched footprint therefore
    gets more samples instead of the previous fixed 4 (which left visible
    bands at high ratios).
    """
    limit = max(1, int(max_samples))
    r = abs(float(ratio))
    if not math.isfinite(r) or r <= 1.0:
        return limit if not math.isfinite(r) else 1
    needed = 1 << max(0, int(math.ceil(math.log2(r))))
    return max(1, min(needed, limit))


def mip_level(width, height, du, dv):
    """Return the mip level for a UV footprint.

    ``du``/``dv`` are UV derivatives and ``width``/``height`` the texture
    dimensions.  The mip is selected from the *minor* footprint axis; the
    stretched (major) axis is resolved by anisotropic sampling.  Selecting
    the max axis here would discard all detail along the stretched direction.
    Magnification is clamped to mip 0.
    """
    footprint_x = abs(float(du)) * abs(float(width))
    footprint_y = abs(float(dv)) * abs(float(height))
    minor = min(footprint_x, footprint_y)
    if minor <= 0.0:
        return 0.0
    return max(0.0, math.log2(minor))


def lod_bias(base_bias, ratio):
    """Return the LOD bias for an anisotropic sample spread.

    A negative user bias would pull nearby texture to a distant mip and erase
    detail prematurely, so it is clamped at zero.  The anisotropic spread then
    applies its own (bounded) negative compensation, ``-log2(ratio)``, which
    recovers the detail the extra samples can resolve.
    """
    user_bias = max(0.0, float(base_bias))
    r = abs(float(ratio))
    if not math.isfinite(r) or r <= 1.0:
        r = 1.0
    return user_bias - math.log2(r)


def trilinear_weight(lod):
    """Return the blend weight towards the next higher mip.

    The weight is the fractional part of a non-negative LOD.  Values that sit
    on (or extremely close to) a mip level are snapped to 0/1 so the sampler
    does not blend across a boundary it does not need to; this keeps road
    markings from ghosting through an over-wide trilinear band.
    """
    lod = float(lod)
    if not math.isfinite(lod) or lod <= 0.0:
        return 0.0
    weight = lod - math.floor(lod)
    if weight < 1e-6:
        return 0.0
    if 1.0 - weight < 1e-6:
        return 1.0
    return weight


def array_layer(layer, base):
    """Return the absolute texture-array layer.

    Anisotropic taps must carry the selected layer with them; resolving the
    layer once here keeps adjacent array slices from bleeding into each other.
    """
    return int(base) + int(layer)


def bc7_alpha_mode(mode):
    """Return whether a BC7 block's alpha mode carries actual alpha.

    ``mode`` is the per-block alpha mode (0 = opaque, non-zero = the block
    stores non-uniform alpha).  Treating such blocks as opaque produces dark
    fringes around alpha-cutout geometry (fences).
    """
    return bool(mode)


def sampler_key(wrap, filter_mode, aniso):
    """Return a canonical sampler-state key.

    Keying on the full sampler state keeps a material switch from leaking the
    previous material's wrap/filter/aniso settings into the new one.
    """
    return f"{wrap}:{filter_mode}:{int(aniso)}"


def camera_aniso_key(camera_id):
    """Return the per-camera anisotropic sampling key.

    Split-screen cameras can see different anisotropy directions, so their
    sampler state must be isolated by camera identity.
    """
    return str(camera_id)


def texture_footprint(uv, width, height):
    """Return the footprint of a UV step in texels along each axis."""
    u, v = uv
    return (
        abs(float(u)) * abs(float(width)),
        abs(float(v)) * abs(float(height)),
    )


def clamp_lod(lod, max_lod):
    """Clamp a LOD to the valid range.

    The lower bound removes negative LODs (which would blur nearby texture)
    and the upper bound keeps sampling inside the mip chain.
    """
    upper = max(0.0, float(max_lod))
    return min(max(float(lod), 0.0), upper)


def wrap_uv(value, mode):
    """Wrap a UV coordinate according to an address mode.

    Supported modes are ``wrap``/``repeat``, ``clamp``/``clamp_to_edge`` and
    ``mirror``/``mirrored_repeat``.  Resolving the mode per sample prevents a
    material's wrap state from contaminating the next material.
    """
    value = float(value)
    normalized = str(mode).strip().lower().replace("-", "_").replace(" ", "_")

    if normalized in ("wrap", "repeat"):
        return value - math.floor(value)
    if normalized in ("clamp", "clamp_to_edge", "clamp_to_border"):
        return min(max(value, 0.0), 1.0)
    if normalized in ("mirror", "mirrored", "mirror_repeat", "mirrored_repeat"):
        mirrored = value - math.floor(value / 2.0) * 2.0
        return mirrored if mirrored <= 1.0 else 2.0 - mirrored

    raise ValueError(f"unsupported wrap mode: {mode!r}")


def aniso_axis(du, dv):
    """Return the axis with the larger UV derivative ("x" or "y")."""
    return "x" if abs(float(du)) >= abs(float(dv)) else "y"


def degrade_samples(quality):
    """Return the sample count for a degraded performance tier.

    Degradation halves the requested anisotropic sample count but never turns
    anisotropy off: at least 2x sampling is retained so oblique views do not
    collapse into hard aliased edges.
    """
    requested = int(quality)
    if requested <= MIN_DEGRADED_SAMPLES:
        return MIN_DEGRADED_SAMPLES
    return max(MIN_DEGRADED_SAMPLES, requested // 2)
