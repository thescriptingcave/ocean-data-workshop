"""The gate, steps 1-2: load a month of ocean data and look at it.

Deliberately NOT Postgres. The point is to see whether the *data* is interesting before
any schema is designed, so a loader bug can never be mistaken for a dead end.

Run:  uv run python scripts/gate_look.py
Writes figures to figures/ and prints a structure summary.

Step 3 of the gate is not here and cannot be: write down three questions you actually
want to answer. No test can tell you whether you are curious about something.
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: no window to draw into on a build agent
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import cmocean

from ocean_sim.config import (
    ACOUSTIC_ANCHOR,
    OCEAN_BOX,
    OCEAN_SITE,
    SEPT_2019,
)
from ocean_sim.data import glorys

FIGDIR = Path(__file__).resolve().parent.parent / "figures"
FIGDIR.mkdir(exist_ok=True)

VARS = {
    "temperature": ("Potential temperature", "°C", cmocean.cm.thermal, 9, 18),
    "salinity": ("Practical salinity", "PSU", cmocean.cm.haline, 32.5, 34.0),
    "u_eastward": ("Eastward current", "m s⁻¹", cmocean.cm.balance, -0.15, 0.15),
    "v_northward": ("Northward current", "m s⁻¹", cmocean.cm.balance, -0.15, 0.20),
}


def main() -> int:
    print(f"site  : {OCEAN_SITE.name}  {OCEAN_SITE.lat}N {OCEAN_SITE.lon}E")
    print(f"window: {SEPT_2019.label}   source: GLORYS12V1 daily, 1/12 deg")
    print(f"anchor: {ACOUSTIC_ANCHOR.name} @ {ACOUSTIC_ANCHOR.depth_m} m "
          f"({ACOUSTIC_ANCHOR.note.split(';')[0]})")

    paths = glorys.fetch(
        list(VARS), OCEAN_BOX, SEPT_2019.start, SEPT_2019.end, "data/glorys"
    )
    ds = glorys.load(paths, label=SEPT_2019.label)
    print(f"\nloaded: {dict(ds.sizes)}")

    # ---------------------------------------------------------------- figure 1
    # time x depth for every variable -- the single most informative picture here
    fig, axes = plt.subplots(2, 2, figsize=(15, 10), constrained_layout=True)
    for ax, (name, (label, unit, cmap, vmin, vmax)) in zip(
        axes.ravel(), VARS.items(), strict=True
    ):
        field = ds[name].mean(dim=["latitude", "longitude"])  # (time, depth)
        m = field.plot.pcolormesh(
            ax=ax,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            shading="auto",
            add_colorbar=True,
        )
        ax.invert_yaxis()  # depth increases downward, as in every oceanographic plot
        ax.set_title(f"{label}  (bay mean)")
        fig.colorbar(m, ax=ax, label=unit, shrink=0.85)
    fig.suptitle(
        f"Monterey Bay — {SEPT_2019.label} — time × depth", fontsize=14, weight="bold"
    )
    fig.savefig(FIGDIR / "gate_01_time_depth.png", dpi=130)
    plt.close(fig)
    print(f"wrote {FIGDIR/'gate_01_time_depth.png'}")

    # ---------------------------------------------------------------- figure 2
    # mean profiles, plus the sound-speed profile derived with gsw
    import gsw

    fig, axes = plt.subplots(1, 3, figsize=(15, 5.5), constrained_layout=True)

    t_prof = ds.temperature.mean(dim=["time", "latitude", "longitude"])
    s_prof = ds.salinity.mean(dim=["time", "latitude", "longitude"])
    axes[0].plot(t_prof, t_prof.depth, color="crimson", label="temperature")
    axes[0].plot(s_prof - 32.0 + 12.0, s_prof.depth, color="teal",
                 label="salinity − 20 (scaled)")
    axes[0].set_xlabel("°C  /  PSU (offset)")
    axes[0].invert_yaxis()
    axes[0].legend()
    axes[0].set_title("Month-mean profiles")

    # gsw takes degrees C, not Kelvin -- verified in probe 01
    sa = gsw.SA_from_SP(s_prof.values, t_prof.depth.values * 1.0198, OCEAN_SITE.lon,
                        OCEAN_SITE.lat)
    ct = gsw.CT_from_t(sa, t_prof.values, t_prof.depth.values * 1.0198)
    c = gsw.sound_speed(sa, ct, t_prof.depth.values * 1.0198)

    axes[1].plot(c, t_prof.depth, color="black")
    axes[1].set_xlabel("m s⁻¹")
    axes[1].invert_yaxis()
    axes[1].set_title("Sound speed c(z)  [TEOS-10]")

    dcdz = np.gradient(c, t_prof.depth.values)
    axes[2].plot(dcdz, t_prof.depth, color="purple")
    axes[2].axvline(0, color="k", lw=0.8)
    axes[2].set_xlabel("dc/dz  (s⁻¹)")
    axes[2].invert_yaxis()
    axes[2].set_title("dc/dz  —  negative = duct")
    # mark the minimum of c, the SOFAR axis
    axes[1].axhline(float(t_prof.depth.values[int(np.argmin(c))]),
                    color="crimson", ls="--", lw=1)
    fig.suptitle("What the derived physics looks like", fontsize=14, weight="bold")
    fig.savefig(FIGDIR / "gate_02_profiles.png", dpi=130)
    plt.close(fig)
    print(f"wrote {FIGDIR/'gate_02_profiles.png'}")

    # ---------------------------------------------------------------- figure 3
    # surface temperature and current direction as plain time series
    fig, axes = plt.subplots(3, 1, figsize=(13, 9), constrained_layout=True, sharex=True)
    t0 = ds.time.values
    axes[0].plot(t0, ds.temperature.isel(depth=0).mean(dim=["latitude", "longitude"]),
                 color="crimson", label="surface")
    axes[0].plot(t0, ds.temperature.isel(depth=-1).mean(dim=["latitude", "longitude"]),
                 color="navy", label="bottom (56 m)")
    axes[0].legend(loc="best")
    axes[0].set_ylabel("°C")
    axes[0].set_title("Surface vs bottom temperature — the thermocline shows up as the gap")

    u = ds.u_eastward.mean(dim=["depth", "latitude", "longitude"])
    v = ds.v_northward.mean(dim=["depth", "latitude", "longitude"])
    axes[1].plot(t0, u, color="crimson", label="u eastward")
    axes[1].plot(t0, v, color="navy", label="v northward")
    axes[1].axhline(0, color="k", lw=0.6)
    axes[1].legend(loc="best")
    axes[1].set_ylabel("m s⁻¹")
    axes[1].set_title("Current components")

    speed = np.hypot(u, v)
    axes[2].plot(t0, speed, color="purple", label="speed")
    ang = np.degrees(np.arctan2(v, u))
    axes[2].plot(t0, ang, color="darkgreen", label="direction (deg, 0=N 90=E)")
    axes[2].legend(loc="best")
    axes[2].set_ylabel("m s⁻¹  /  deg")
    axes[2].set_title("Current speed and bearing — the 'direction' metric")
    fig.suptitle("Time series", fontsize=14, weight="bold")
    fig.savefig(FIGDIR / "gate_03_timeseries.png", dpi=130)
    plt.close(fig)
    print(f"wrote {FIGDIR/'gate_03_timeseries.png'}")

    # ---------------------------------------------------------------- structure
    print("\n" + "=" * 66)
    print("STRUCTURE SUMMARY  (a proxy for 'is there anything here' — not the gate)")
    print("=" * 66)
    for name, (_, unit, _, _, _) in VARS.items():
        f = ds[name].mean(dim=["latitude", "longitude"])
        print(f"  {name:14} std over time at surface: "
              f"{float(f.isel(depth=0).std()):.5f} {unit}")

    # thermocline depth, day by day -- the thing every later question keys off
    depth = ds.depth.values
    daily_tc = []
    for k in range(ds.sizes["time"]):
        p = ds.temperature.isel(time=k).mean(dim=["latitude", "longitude"]).values
        if np.all(np.isfinite(p)):
            daily_tc.append(float(depth[int(np.argmin(np.gradient(p, depth)))]))
    tc = np.array(daily_tc)
    print(f"\n  thermocline depth: median {np.median(tc):.1f} m, "
          f"range {tc.min():.1f}-{tc.max():.1f} m")
    print(f"  day-to-day movement: max jump {np.abs(np.diff(tc)).max():.1f} m")

    spd = np.hypot(u, v)
    print(f"  current speed: mean {spd.mean():.4f} m/s, max {spd.max():.4f} m/s")
    print(f"  current bearing: {np.degrees(np.arctan2(v, u)).min():.0f} to "
          f"{np.degrees(np.arctan2(v, u)).max():.0f} deg")
    if float(spd.mean()) < 0.005:
        print("    WARNING: currents are near zero -- the 'direction' metric may be empty")

    print("\n" + "=" * 66)
    print("STEP 3 IS NOT CODE. Write down three questions you want to answer.")
    print("=" * 66)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
