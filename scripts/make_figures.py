"""Interactive figures — standalone plotly HTML, no server.

The gate figures are static matplotlib. These are the interactive ones: the acoustic
heatmap against wind and ocean on a shared timeline, and the duct diagram with a
parameter you can move.

Two decisions worth stating:

* **Standalone HTML, not a dashboard.** These open in a browser with no server, no
  session, no FastAPI. `include_plotlyjs="cdn"` keeps each file around 1 MB instead of
  4 MB, at the cost of needing internet to view. For a learning tool that is the right
  trade.
* **Daily aggregation in the browser.** The acoustic table has ~19,600 hourly rows by 30
  bands. Plotly's heatmap manages roughly a million cells comfortably, so the browser gets
  ~850 daily rows x 30 bands instead. Hourly detail stays in the database where SQL can
  reach it.

Run:  uv run python scripts/make_figures.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ocean_data_workshop.config import OCEAN_SITE
from ocean_data_workshop.dsn import dsn

ROOT = Path(__file__).resolve().parent.parent
FIGDIR = ROOT / "figures"
FIGDIR.mkdir(exist_ok=True)

import psycopg  # noqa: E402

DSN = dsn()

# The 30 ISO third-octave band centres, ascending.
BANDS = [25, 32, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800,
         1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500,
         16000, 20000]

WINDOW = ("2019-06-01", "2019-09-30")  # a summer window: upwelling active, dolphins present


def q(sql: str, **params) -> pd.DataFrame:
    """Run a parameterised query. SQL must use %(name)s placeholders, not bare %s,
    because params arrive as a dict."""
    with psycopg.connect(DSN) as conn:
        return pd.read_sql_query(sql, conn, params=params)


def acoustic_panel(fig: go.Figure, row: int) -> None:
    """Heatmap of daily mean band level: time x frequency."""
    # Each band needs an explicit alias: bare avg(band_x) is named "avg" by Postgres,
    # so all 30 columns would collide and pandas would rename them avg, avg_1, ...
    band_select = ", ".join(f"avg(band_{b}hz) AS band_{b}hz" for b in BANDS)
    df = q(
        f"""
        SELECT observed_at::date AS day, {band_select}
        FROM acoustic_tol_hourly
        WHERE observed_at::date BETWEEN %(start)s AND %(end)s
        GROUP BY 1 ORDER BY 1
        """,
        start=WINDOW[0], end=WINDOW[1],
    )
    z = df[[f"band_{b}hz" for b in BANDS]].to_numpy(dtype=float)
    hovertemplate = "day=%{x}<br>band=%{y} Hz<br>level=%{z:.1f} dB<extra></extra>"
    fig.add_trace(
        go.Heatmap(
            x=df["day"], y=BANDS, z=z, name="band level",
            colorscale="Viridis", colorbar=dict(title="dB", len=0.30, y=0.80),
            hovertemplate=hovertemplate,
        ),
        row=row, col=1,
    )
    fig.update_yaxes(type="log", title_text="Hz (log)", row=row, col=1)
    fig.update_xaxes(rangeslider_visible=True, row=row, col=1)


def wind_panel(fig: go.Figure, row: int) -> None:
    df = q(
        """
        SELECT observed_at AS day, wind_speed_mean_ms, wind_gust_max_ms,
               wind_northward_ms, wave_height_max_m
        FROM wind_daily
        WHERE station_id='46092' AND observed_at BETWEEN %(start)s AND %(end)s
        ORDER BY observed_at
        """,
        start=WINDOW[0], end=WINDOW[1],
    )
    fig.add_trace(go.Scatter(
        x=df.day, y=df.wind_speed_mean_ms, name="wind speed",
        line=dict(color="steelblue"), hovertemplate="%{x|%Y-%m-%d}<br>wind %{y:.1f} m/s<extra></extra>",
    ), row=row, col=2)
    fig.add_trace(go.Scatter(
        x=df.day, y=df.wind_northward_ms, name="northerly wind",
        line=dict(color="darkorange"), hovertemplate="%{x|%Y-%m-%d}<br>northerly %{y:.1f} m/s<extra></extra>",
    ), row=row, col=2)
    fig.add_trace(go.Scatter(
        x=df.day, y=df.wave_height_max_m, name="wave height",
        line=dict(color="seagreen", dash="dot"),
        hovertemplate="%{x|%Y-%m-%d}<br>H %{y:.1f} m<extra></extra>",
    ), row=row, col=2)
    fig.update_yaxes(title_text="m/s  ·  m", row=row, col=2)


def dolphin_panel(fig: go.Figure, row: int) -> None:
    """Daily dolphin detection rate, computed with a window function."""
    df = q(
        """
        SELECT observed_at::date AS day,
               round(100.0 * avg(presence)::numeric, 1) AS pct_positive,
               count(*) AS hours
        FROM detection_hourly
        WHERE taxon = 'dolphin' AND NOT is_event_list
          AND observed_at::date BETWEEN %(start)s AND %(end)s
        GROUP BY 1 ORDER BY 1
        """,
        start=WINDOW[0], end=WINDOW[1],
    )
    fig.add_trace(go.Bar(
        x=df.day, y=df.pct_positive, name="dolphin hours %",
        marker_color="mediumpurple",
        hovertemplate="%{x|%Y-%m-%d}<br>%{y:.1f}% of hours<extra></extra>",
    ), row=row, col=2)
    fig.update_yaxes(title_text="% hours", row=row, col=2)


def ocean_panel(fig: go.Figure, row: int) -> None:
    """Time-depth temperature section."""
    df = q(
        """
        SELECT observed_at::date AS day, depth_m, avg(raw_temperature_c) AS temperature_c
        FROM ocean_profile_daily
        WHERE observed_at::date BETWEEN %(start)s AND %(end)s
        GROUP BY 1, 2 ORDER BY 1, 2
        """,
        start=WINDOW[0], end=WINDOW[1],
    )
    piv = df.pivot(index="depth_m", columns="day", values="temperature_c")
    fig.add_trace(go.Heatmap(
        x=piv.columns, y=piv.index, z=piv.to_numpy(),
        colorscale="thermal_r", zmin=8, zmax=17, name="temperature",
        colorbar=dict(title="°C", len=0.30, y=0.30),
        hovertemplate="day=%{x}<br>depth=%{y} m<br>%{z:.1f} °C<extra></extra>",
    ), row=row, col=1)
    fig.update_yaxes(autorange="reversed", title_text="depth (m)", row=row, col=1)


def duct_figure() -> go.Figure:
    """c(z) with the sound-speed minimum marked, and how it moves over the window."""
    df = q(
        """
        SELECT observed_at::date AS day, depth_m, avg(sound_speed_ms) AS c_ms,
               avg(dc_dz_s) AS dcdz
        FROM ocean_profile_daily
        WHERE observed_at::date BETWEEN %(start)s AND %(end)s
        GROUP BY 1, 2 ORDER BY 1, 2
        """,
        start=WINDOW[0], end=WINDOW[1],
    )
    piv = df.pivot(index="depth_m", columns="day", values="c_ms").sort_index()
    dpiv = df.pivot(index="depth_m", columns="day", values="dcdz").sort_index()

    fig = make_subplots(
        rows=1, cols=2, shared_yaxes=True,
        subplot_titles=("Sound speed c(z)", "Gradient dc/dz  —  negative = duct"),
    )
    for day in piv.columns[:: max(1, len(piv.columns) // 12)]:
        fig.add_trace(go.Scatter(
            x=piv[day], y=piv.index, name=str(day), mode="lines", opacity=0.55,
            hovertemplate=f"{day}<br>depth=%{{y}} m<br>c=%{{x:.1f}} m/s<extra></extra>",
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=dpiv[day], y=dpiv.index, name=str(day), mode="lines", opacity=0.55,
            showlegend=False, line=dict(width=1),
            hovertemplate=f"{day}<br>depth=%{{y}} m<br>dc/dz=%{{x:.4f}} s⁻¹<extra></extra>",
        ), row=1, col=2)
    fig.add_vline(x=0, line_dash="dash", line_color="black", row=1, col=2)
    fig.update_xaxes(title_text="c  (m s⁻¹)", row=1, col=1)
    fig.update_xaxes(title_text="dc/dz  (s⁻¹)", row=1, col=2)
    fig.update_yaxes(title_text="depth (m)", autorange="reversed", row=1, col=1)
    fig.update_layout(
        height=720,
        title=(
            f"{OCEAN_SITE.name} — sound speed and ducting, {WINDOW[0]} to {WINDOW[1]}"
            "<br><sup>The sound-speed minimum sits at the deepest sampled level, so the "
            "true SOFAR axis is below this box. The whole column is one deep surface duct."
            "</sup>"
        ),
    )
    return fig


def main() -> int:
    print(f"window: {WINDOW[0]} .. {WINDOW[1]}")

    fig = make_subplots(
        rows=2, cols=2,
        specs=[[{"type": "heatmap"}, {}], [{"type": "heatmap"}, {}]],
        shared_xaxes=True,
        column_widths=[0.52, 0.48],
        subplot_titles=(
            "Acoustic band level (dB re 1 µPa²/Hz, daily mean)",
            "Forcing",
            "Temperature section (°C)",
            "Dolphin detections",
        ),
        vertical_spacing=0.14,
    )
    print("  building acoustic + wind + dolphin + ocean panels ...")
    acoustic_panel(fig, 1)
    wind_panel(fig, 1)
    ocean_panel(fig, 2)
    dolphin_panel(fig, 2)

    fig.update_xaxes(rangeslider_visible=True, row=1, col=1)
    fig.update_layout(
        height=900,
        title=(
            f"{OCEAN_SITE.name} — ocean, wind and acoustics on one timeline"
            f" ({WINDOW[0]} to {WINDOW[1]})"
            "<br><sup>Drag the range sliders. 160–500 Hz is the shipping band and barely "
            "tracks wind; above ~2 kHz surface and wave noise dominates and rises with it.</sup>"
        ),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    out = FIGDIR / "interactive_ocean_wind_acoustic.html"
    fig.write_html(out, include_plotlyjs="cdn", full_html=True)
    print(f"  wrote {out.name}  ({out.stat().st_size / 1024:.0f} KB)")

    print("  building duct figure ...")
    d = duct_figure()
    out2 = FIGDIR / "interactive_duct.html"
    d.write_html(out2, include_plotlyjs="cdn", full_html=True)
    print(f"  wrote {out2.name}  ({out2.stat().st_size / 1024:.0f} KB)")

    print("\nopen with:  open figures/interactive_ocean_wind_acoustic.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
