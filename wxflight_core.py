#!/usr/bin/env python3
"""
WxFlight Planner – Core HRRR Module (FIXED for 2D Lambert grid)
"""

import argparse
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import pytz

__version__ = "2.0.1"
APP_NAME = "WxFlight Planner"

SITES = {
    "bankhead": {
        "name": "Bankhead_NF",
        "full_name": "DOE Bankhead National Forest",
        "lat": 34.3425,
        "lon": -87.3382,
        "alt_m": 293,
        "timezone": "America/Chicago",
        "description": "Alabama forested site",
        "region": "seus"
    },
    "dustieaim": {
        "name": "DustieAim_PHX",
        "full_name": "DustieAim Field Campaign – Phoenix, AZ",
        "lat": 33.6070,
        "lon": -112.1669,
        "alt_m": 331,
        "timezone": "America/Phoenix",
        "description": "Arizona dust/aerosol campaign site",
        "region": "swus"
    }
}


def get_site(site_key=None, lat=None, lon=None, name=None, tz=None):
    if site_key and site_key in SITES:
        return SITES[site_key]
    elif lat is not None and lon is not None:
        return {
            "name": name or "Custom_Site",
            "full_name": name or f"Custom ({lat:.4f}°N, {abs(lon):.4f}°W)",
            "lat": lat, "lon": lon, "alt_m": 0,
            "timezone": tz or "UTC",
            "description": "User-defined", "region": "us"
        }
    return SITES["bankhead"]


def wind_dir_label(deg):
    dirs = ['N','NNE','NE','ENE','E','ESE','SE','SSE',
            'S','SSW','SW','WSW','W','WNW','NW','NNW']
    return dirs[int((deg + 11.25) / 22.5) % 16]


def extract_point(ds, lat, lon):
    """
    Extract nearest grid point from HRRR 2D Lambert Conformal grid.
    
    HRRR uses:
      - 2D latitude/longitude arrays with dims (y, x)
      - Longitude in 0-360° convention
    
    So .sel(latitude=x, longitude=y) does NOT work.
    We must find the nearest point manually.
    """
    var_name = list(ds.data_vars)[0]
    data = ds[var_name]

    # Get 2D coordinate arrays
    lat2d = ds.latitude.values
    lon2d = ds.longitude.values

    # Convert target longitude to 0-360 if grid uses that convention
    target_lon = lon + 360 if lon < 0 and lon2d.min() > 0 else lon

    # Find nearest grid point using Euclidean distance
    dist = np.sqrt((lat2d - lat)**2 + (lon2d - target_lon)**2)
    iy, ix = np.unravel_index(dist.argmin(), dist.shape)

    # Extract value at that grid point
    val = float(data.values[iy, ix])
    return val


def extract_point_multi(ds, lat, lon, var_names=None):
    """Extract multiple variables from same grid (e.g., u10 and v10)."""
    lat2d = ds.latitude.values
    lon2d = ds.longitude.values
    target_lon = lon + 360 if lon < 0 and lon2d.min() > 0 else lon
    dist = np.sqrt((lat2d - lat)**2 + (lon2d - target_lon)**2)
    iy, ix = np.unravel_index(dist.argmin(), dist.shape)

    if var_names is None:
        var_names = list(ds.data_vars)

    results = {}
    for vn in var_names:
        if vn in ds.data_vars:
            results[vn] = float(ds[vn].values[iy, ix])
    return results


def get_hrrr_forecast(run_date=None, run_hour=12, fxx_range=25,
                      site=None, progress_callback=None, verbose=True):
    """
    Pull HRRR 24-hour forecast for a given site.
    Fixed for HRRR's 2D Lambert Conformal grid with 0-360° longitude.
    """
    from herbie import Herbie

    if site is None:
        site = SITES["bankhead"]

    LAT = site["lat"]
    LON = site["lon"]
    LOCAL_TZ = pytz.timezone(site["timezone"])
    UTC_TZ = pytz.utc

    if run_date is None:
        # Use current UTC time minus 3 hours to ensure data is available
        # (HRRR data typically appears on AWS ~2 hours after run time)
        safe_time = datetime.utcnow() - timedelta(hours=3)
        run_date = safe_time.strftime("%Y-%m-%d")
        # Also adjust run_hour to the latest safe hour if not specified
        if run_hour > safe_time.hour:
            run_hour = (safe_time.hour // 6) * 6  # Round down to 0,6,12,18

    run_time = f"{run_date} {run_hour:02d}:00"
    run_dt_utc = UTC_TZ.localize(
        datetime.strptime(run_time, "%Y-%m-%d %H:%M"))

    if verbose:
        print(f"{'='*60}")
        print(f"  {APP_NAME} – HRRR Forecast (v{__version__})")
        print(f"  Site: {site['full_name']}")
        print(f"  Coords: {LAT}°N, {abs(LON)}°W")
        print(f"  Grid lon: {LON + 360:.4f}° (0-360 convention)")
        print(f"  Run: {run_time}Z | Hours: f00–f{fxx_range-1}")
        print(f"{'='*60}\n")

    results = []

    for fxx in range(fxx_range):
        if progress_callback:
            progress_callback(fxx + 1, fxx_range,
                              f"Fetching f{fxx:02d}/{fxx_range-1}")
        if verbose:
            print(f"  [f{fxx:02d}] ", end="", flush=True)

        try:
            H = Herbie(run_time, model="hrrr", product="sfc", fxx=fxx)
            row = {"forecast_hour": fxx}

            # Timestamps
            valid_utc = run_dt_utc + timedelta(hours=fxx)
            valid_local = valid_utc.astimezone(LOCAL_TZ)
            row["valid_time_utc"] = valid_utc.strftime("%Y-%m-%d %H:%M UTC")
            row["valid_time_local"] = valid_local.strftime("%Y-%m-%d %H:%M %Z")
            row["hour_utc"] = valid_utc.hour
            row["hour_local"] = valid_local.hour

            # --- Temperature 2m ---
            ds = H.xarray(":TMP:2 m above ground")
            t_k = extract_point(ds, LAT, LON)
            row["temp_C"] = round(t_k - 273.15, 1)
            row["temp_F"] = round((t_k - 273.15) * 9/5 + 32, 1)

            # --- Relative Humidity 2m ---
            ds = H.xarray(":RH:2 m above ground")
            row["RH_pct"] = round(extract_point(ds, LAT, LON), 1)

            # --- Wind 10m (U and V components) ---
            ds = H.xarray(":(?:UGRD|VGRD):10 m above ground")
            wind_vals = extract_point_multi(ds, LAT, LON)
            u = wind_vals.get("u10", 0)
            v = wind_vals.get("v10", 0)
            row["wind_speed_ms"] = round(np.sqrt(u**2 + v**2), 2)
            row["wind_speed_mph"] = round(row["wind_speed_ms"] * 2.237, 1)
            row["wind_dir_deg"] = round(
                (270 - np.degrees(np.arctan2(v, u))) % 360, 1)
            row["wind_dir_compass"] = wind_dir_label(row["wind_dir_deg"])

            # --- Wind Gust ---
            try:
                ds = H.xarray(":GUST:surface")
                gust = extract_point(ds, LAT, LON)
                row["wind_gust_mph"] = round(gust * 2.237, 1)
            except Exception:
                row["wind_gust_mph"] = None

            # --- Precipitation ---
            try:
                ds = H.xarray(":APCP:surface")
                row["precip_mm"] = round(extract_point(ds, LAT, LON), 2)
            except Exception:
                row["precip_mm"] = 0.0

            # --- Cloud Ceiling ---
            try:
                ds = H.xarray(":HGT:cloud ceiling")
                ceil = extract_point(ds, LAT, LON)
                row["cloud_ceiling_ft"] = round(ceil * 3.281, 0)
            except Exception:
                row["cloud_ceiling_ft"] = None

            # --- Visibility ---
            try:
                ds = H.xarray(":VIS:surface")
                vis = extract_point(ds, LAT, LON)
                row["visibility_mi"] = round(vis / 1609.34, 1)
            except Exception:
                row["visibility_mi"] = None

            # --- Smoke (near-surface) ---
            try:
                ds = H.xarray(":MASSDEN:8 m above ground")
                smoke_val = extract_point(ds, LAT, LON)
                row["smoke_ugm3"] = round(smoke_val * 1e9, 3)
            except Exception:
                row["smoke_ugm3"] = None

            # --- Dust (near-surface) ---
            # Note: HRRR-Smoke may not have separate dust in all runs
            try:
                ds = H.xarray(":MASSDEN:8 m above ground:.*dust")
                row["dust_ugm3"] = round(extract_point(ds, LAT, LON) * 1e9, 3)
            except Exception:
                row["dust_ugm3"] = None

            # --- Column smoke ---
            try:
                ds = H.xarray(":COLMD:entire atmosphere")
                row["smoke_col_mgm2"] = round(
                    extract_point(ds, LAT, LON) * 1e6, 3)
            except Exception:
                row["smoke_col_mgm2"] = None

            # --- Column dust ---
            try:
                ds = H.xarray(":COLMD:entire atmosphere:.*dust")
                row["dust_col_mgm2"] = round(
                    extract_point(ds, LAT, LON) * 1e6, 3)
            except Exception:
                row["dust_col_mgm2"] = None

            # --- AOD proxy ---
            sc = row.get("smoke_col_mgm2") or 0
            dc = row.get("dust_col_mgm2") or 0
            row["aod_proxy"] = round(sc * 0.003 + dc * 0.005, 4)

            results.append(row)

            if verbose:
                print(f"✓ {row['temp_F']}°F | RH {row['RH_pct']}% | "
                      f"Wind {row['wind_speed_mph']}mph "
                      f"@ {row['wind_dir_deg']}°"
                      f"({row['wind_dir_compass']})")

        except Exception as e:
            if verbose:
                print(f"✗ {type(e).__name__}: {e}")
            continue

    df = pd.DataFrame(results)
    if verbose:
        print(f"\n✓ Retrieved {len(df)} of {fxx_range} forecast hours")
    return df


def generate_plots(df, site=None, output_path=None,
                   dark_theme=True, show=False):
    """Create 8-panel forecast plot matching WxFlight Planner v20."""
    import matplotlib.pyplot as plt

    if site is None:
        site = SITES["bankhead"]

    bg = '#0e1117' if dark_theme else 'white'
    fg = '#fafafa' if dark_theme else '#1a1a1a'
    grid_c = '#3d4560' if dark_theme else '#e0e0e0'
    ax_bg = '#1a1f2e' if dark_theme else '#f8f9fa'

    fig, axes = plt.subplots(4, 2, figsize=(15, 14))
    fig.patch.set_facecolor(bg)

    x = range(len(df))
    local_labels = [f"{h:02d}" for h in df["hour_local"]]
    utc_labels = [f"{h:02d}Z" for h in df["hour_utc"]]

    def style_ax(ax, title):
        ax.set_facecolor(ax_bg)
        ax.set_title(title, color=fg, fontsize=10, pad=10)
        ax.tick_params(colors='#a3a8b8', labelsize=7)
        ax.grid(True, alpha=0.2, color=grid_c)
        for spine in ax.spines.values():
            spine.set_color(grid_c)
        step = max(1, len(x) // 12)
        ax.set_xticks(list(x)[::step])
        ax.set_xticklabels([local_labels[i] for i in list(x)[::step]])
        ax.set_xlabel("Local Time", fontsize=8, color='#a3a8b8')
        ax2 = ax.twiny()
        ax2.set_xlim(ax.get_xlim())
        ax2.set_xticks(list(x)[::step])
        ax2.set_xticklabels([utc_labels[i] for i in list(x)[::step]],
                            fontsize=7, color='#4fc3f7')
        ax2.set_xlabel("UTC", fontsize=8, color='#4fc3f7')
        ax2.tick_params(colors='#4fc3f7', labelsize=7)

    # 1: Temperature & RH
    ax = axes[0, 0]
    ax.plot(x, df["temp_F"], '-o', color='#ff4b4b', markersize=3, lw=1.5)
    ax.set_ylabel("Temperature (°F)", color='#ff4b4b', fontsize=9)
    ax_r = ax.twinx()
    ax_r.plot(x, df["RH_pct"], '--s', color='#4fc3f7', markersize=2, lw=1)
    ax_r.set_ylabel("Relative Humidity (%)", color='#4fc3f7', fontsize=9)
    ax_r.set_ylim(0, 100)
    ax_r.tick_params(colors='#4fc3f7', labelsize=7)
    style_ax(ax, "🌡️ Temperature & Relative Humidity")

    # 2: Wind Speed & Gusts
    ax = axes[0, 1]
    ax.bar(x, df["wind_speed_mph"], color='#4fc3f7', alpha=0.6)
    if df["wind_gust_mph"].notna().any():
        ax.scatter(x, df["wind_gust_mph"].fillna(0), color='#ff4b4b',
                   s=15, marker='^', zorder=5, label="Gust")
        ax.legend(fontsize=7)
    ax.set_ylabel("Wind Speed (mph)", fontsize=9, color='#a3a8b8')
    style_ax(ax, "💨 Wind Speed & Gusts (10m)")

    # 3: Wind Direction
    ax = axes[1, 0]
    ax.scatter(x, df["wind_dir_deg"], c=df["wind_speed_mph"],
               cmap='cool', s=30, edgecolors='white', linewidths=0.3)
    ax.set_ylim(0, 360)
    ax.set_yticks([0, 90, 180, 270, 360])
    ax.set_yticklabels(['N', 'E', 'S', 'W', 'N'])
    ax.set_ylabel("Wind Direction", fontsize=9, color='#a3a8b8')
    style_ax(ax, "🧭 Wind Direction (10m)")

    # 4: Precipitation
    ax = axes[1, 1]
    ax.bar(x, df["precip_mm"], color='#81c784', alpha=0.8)
    ax.set_ylabel("Precipitation (mm)", fontsize=9, color='#a3a8b8')
    style_ax(ax, "🌧️ Hourly Accumulated Precipitation")

    # 5: Cloud Ceiling & Visibility
    ax = axes[2, 0]
    if df["cloud_ceiling_ft"].notna().any():
        ax.plot(x, df["cloud_ceiling_ft"].ffill(), '-o',
                color='#ce93d8', markersize=3, lw=1.5)
        ax.axhline(1000, color='red', ls='--', alpha=0.5, lw=1)
        ax.set_ylabel("Cloud Ceiling (ft AGL)", color='#ce93d8', fontsize=9)
    if df["visibility_mi"].notna().any():
        ax_v = ax.twinx()
        ax_v.plot(x, df["visibility_mi"].fillna(10), 's-',
                  color='#ffee58', markersize=2, lw=1)
        ax_v.set_ylabel("Visibility (statute miles)",
                        color='#ffee58', fontsize=9)
        ax_v.tick_params(colors='#ffee58', labelsize=7)
    style_ax(ax, "☁️ Cloud Ceiling & Visibility")

    # 6: Smoke
    ax = axes[2, 1]
    if df["smoke_ugm3"].notna().any():
        ax.fill_between(x, df["smoke_ugm3"].fillna(0),
                        color='#ff8a65', alpha=0.3)
        ax.plot(x, df["smoke_ugm3"].fillna(0), '-o',
                color='#e64a19', markersize=3, lw=1.5)
    ax.set_ylabel("Smoke (µg/m³)", fontsize=9, color='#a3a8b8')
    style_ax(ax, "🔥 Near-Surface Smoke Concentration")

    # 7: Dust
    ax = axes[3, 0]
    if df["dust_ugm3"].notna().any():
        ax.fill_between(x, df["dust_ugm3"].fillna(0),
                        color='#d4a373', alpha=0.3)
        ax.plot(x, df["dust_ugm3"].fillna(0), '-o',
                color='#8d6e63', markersize=3, lw=1.5)
    ax.set_ylabel("Dust (µg/m³)", fontsize=9, color='#a3a8b8')
    is_arid = "Phoenix" in site.get("full_name", "")
    style_ax(ax, f"🏜️ Near-Surface Dust Concentration"
             f"{' (Arid Site)' if is_arid else ''}")

    # 8: AOD
    ax = axes[3, 1]
    if df["aod_proxy"].notna().any():
        ax.plot(x, df["aod_proxy"], '-o', color='#ce93d8',
                markersize=3, lw=2)
    ax.set_ylabel("AOD", fontsize=9, color='#a3a8b8')
    style_ax(ax, "🌫️ Aerosol Optical Depth (Smoke + Dust)")

    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.suptitle(
        f"{APP_NAME} | {site['full_name']} "
        f"({site['lat']}°N, {abs(site['lon'])}°W)\n"
        f"{df['valid_time_utc'].iloc[0]} → {df['valid_time_utc'].iloc[-1]}",
        color=fg, fontsize=11, y=0.99)

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches='tight', facecolor=bg)
        print(f"✓ Plot saved: {output_path}")
    if show:
        plt.show()
    return fig


def export_csv(df, path):
    df.to_csv(path, index=False)
    return path


def export_json(df, path):
    df.to_json(path, orient="records", indent=2)
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} – HRRR Forecast (v{__version__})")
    parser.add_argument("--site", choices=list(SITES.keys()), default=None)
    parser.add_argument("--lat", type=float, default=None)
    parser.add_argument("--lon", type=float, default=None)
    parser.add_argument("--name", type=str, default=None)
    parser.add_argument("--tz", type=str, default="UTC")
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--hour", type=int, default=12)
    parser.add_argument("--hours", type=int, default=25)
    parser.add_argument("--output", type=str, default=None)
    parser.add_argument("--no-plot", action="store_true")
    args = parser.parse_args()

    if args.lat is not None and args.lon is not None:
        site = get_site(lat=args.lat, lon=args.lon,
                        name=args.name, tz=args.tz)
    else:
        site = get_site(args.site or "bankhead")

    df = get_hrrr_forecast(run_date=args.date, run_hour=args.hour,
                           fxx_range=args.hours, site=site)

    if df.empty:
        print("❌ No data retrieved.")
        raise SystemExit(1)

    prefix = args.output or f"wxflight_{site['name']}_{args.date or 'today'}"
    export_csv(df, f"{prefix}.csv")
    export_json(df, f"{prefix}.json")
    print(f"\n✓ {len(df)} records → {prefix}.csv / .json")

    if not args.no_plot:
        generate_plots(df, site=site, output_path=f"{prefix}_plots.png",
                       dark_theme=False, show=True)