"""Probe 01 — gsw (TEOS-10) on Apple Silicon.

Why this is a probe and not a library import: gsw ships a C extension. If it needs a
compiler or an arm64 wheel is missing, we want to discover that on day one, not on
Wednesday morning when the ducting code depends on it.

Two things established by this probe:

1. **This gsw wrapper takes degrees C, not Kelvin**, for both CT and in-situ t.
   ``gsw.sound_speed(35, 20, 0) -> 1521.2 m/s`` is the textbook value; passing 293.15
   returns NaN. TEOS-10 defines CT on the ITS-90 scale in kelvin, so the C convention
   is a genuine trap. Do not "fix" inputs to Kelvin.
2. The values are physically sensible, so later failures mean *our* code is wrong
   rather than the library.

Checks use physical *derivatives* (d c/dT, d c/dp) plus a wide plausibility band,
rather than asserting absolute values from memory -- a derivative is a far more robust
thing to test than a recalled number.
"""

from __future__ import annotations

import numpy as np

from ._common import PASS, Probe, Result, run

HARNESS = Probe(
    slug="gsw",
    name="gsw / TEOS-10 thermodynamic toolbox",
    tier=1,
    klass="A",
    provides="sound speed, in-situ & potential density, SA/CT/SP conversions",
    protocol="pip wheel (C extension)",
    order=1,
)

SITE_LON, SITE_LAT = -122.10, 36.70


def check() -> Result:
    import gsw

    detail: dict = {"version": gsw.__version__}
    problems: list[str] = []

    # SA/dcdT/dcdp keep their physics casing deliberately: renaming SA to `sa` loses
    # the link to the TEOS-10 symbol it is, and these appear in the formulas below.
    SA, p0 = 35.0, 0.0  # noqa: N806

    # --- 1. units are degrees C, not Kelvin (documented trap) ---
    c_20c = float(gsw.sound_speed(SA, 20.0, p0))
    c_kelvin_attempt = float(np.asarray(gsw.sound_speed(SA, 293.15, p0)).ravel()[0])
    if not np.isnan(c_kelvin_attempt):
        problems.append("expected NaN for Kelvin input; units may have changed")
    detail["c_at_20C"] = round(c_20c, 1)
    detail["kelvin_input_gives_nan"] = bool(np.isnan(c_kelvin_attempt))

    # textbook check: seawater S=35, 20 C, surface -> ~1521 m/s
    if not 1515.0 < c_20c < 1527.0:
        problems.append(f"c(20C, S=35, p=0)={c_20c:.1f}, expected ~1521 m/s")

    # --- 2. d c / dT  in seawater is ~3-4 m/s per degC ---
    temps = np.array([5.0, 10.0, 15.0, 20.0, 25.0])
    c_t = np.array([float(gsw.sound_speed(SA, t, p0)) for t in temps])
    dcdT = np.diff(c_t) / np.diff(temps)  # noqa: N806
    detail["c_range"] = f"{c_t[0]:.0f}-{c_t[-1]:.0f} m/s"
    detail["dcdT"] = f"{dcdT.mean():.2f} m/s/degC"
    if not 2.5 < dcdT.mean() < 4.5:
        problems.append(f"d c/dT = {dcdT.mean():.2f} m/s/degC, expected 2.5-4.5")
    if not np.all(np.diff(c_t) > 0):
        problems.append("sound speed must increase monotonically with temperature")

    # --- 3. d c / dp: ~17 m/s per 1000 dbar (the textbook "per km of depth" figure) ---
    #    Mean sound speed rises ~1470 -> ~1556 m/s between the surface and 5000 dbar.
    pres = np.array([0.0, 500.0, 1000.0, 2000.0, 3000.0, 4000.0, 5000.0])
    c_p = np.array([float(gsw.sound_speed(SA, 5.0, p)) for p in pres])
    dcdp = np.diff(c_p) / np.diff(pres) * 1000.0  # m/s per 1000 dbar
    detail["c_0_to_5000dbar"] = f"{c_p[0]:.0f}->{c_p[-1]:.0f} m/s"
    detail["dcdp_per_1000dbar"] = f"{dcdp[0]:.1f}->{dcdp[-1]:.1f}"
    if not 15.0 < dcdp.mean() < 19.0:
        problems.append(
            f"mean d c/dp = {dcdp.mean():.1f} m/s/1000dbar, expected ~17"
        )
    # Structural fact: compressibility falls with depth, so the pressure gradient
    # of sound speed increases monotonically -- but only mildly, ~5-10% over
    # 0-5000 dbar. A *monotonic* increase is a far better test than a ratio.
    if not np.all(np.diff(dcdp) > 0):
        problems.append(
            f"d c/dp should increase monotonically with depth, got {np.round(dcdp, 2)}"
        )

    # --- 4. the SP -> SA -> CT -> sigma0 chain, at a plausible Monterey cast ---
    #    paired correctly this time: each row is one (temp, pressure) observation
    t_obs = np.array([14.0, 10.5, 9.0])   # in-situ, degrees C, shallow -> deep
    p_obs = np.array([10.0, 40.0, 60.0])  # dbar
    sp = np.array([33.5, 33.6, 34.1])
    sa = gsw.SA_from_SP(sp, p_obs, SITE_LON, SITE_LAT)
    ct = gsw.CT_from_t(sa, t_obs, p_obs)
    sigma0 = gsw.sigma0(sa, ct)
    detail.update(
        sa_mean=round(float(np.mean(sa)), 3),
        ct_mean=round(float(np.mean(ct)), 3),
        sigma0_mean=round(float(np.mean(sigma0)), 2),
    )
    # potential density anomaly in the open ocean is ~20-28 kg/m^3
    if not 20.0 < float(np.mean(sigma0)) < 28.0:
        problems.append(f"sigma0={float(np.mean(sigma0)):.2f} outside 20-28 kg/m^3")
    # CT tracks t, and because these are shallower than 100 dbar it should not
    # differ by more than a few tenths of a degree from in-situ temperature
    if np.max(np.abs(np.asarray(ct) - t_obs)) > 1.0:
        problems.append("CT and t differ by >1 degC at shallow depths")

    if problems:
        return Result(status="FAIL", note="; ".join(problems), detail=detail)

    return Result(
        status=PASS,
        note=(
            "arm64 wheel, no compiler. units are degrees C (not Kelvin). "
            f"c={c_20c:.0f} m/s at 20C, dcdT={dcdT.mean():.1f} m/s/degC, "
            f"dcdp={dcdp[0]:.1f}->{dcdp[-1]:.1f} m/s/1000dbar, "
            f"sigma0={float(np.mean(sigma0)):.1f}"
        ),
        detail=detail,
    )


if __name__ == "__main__":
    import sys

    from ._common import append_verdict

    res = run(HARNESS, check)
    append_verdict(res)
    sys.exit(0 if res.status == "PASS" else 1)
