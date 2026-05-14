#!/usr/bin/env python3
"""
WxFlight Planner – Streamlit App (Fixed)
Run: python -m streamlit run wxflight_app.py
"""

import streamlit as st
import pandas as pd
import io
from datetime import date, timedelta, datetime

# Import requests at top level with fallback
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

from wxflight_core import (
    get_hrrr_forecast,
    generate_plots,
    get_site,
    SITES,
    APP_NAME,
    __version__
)

st.set_page_config(
    page_title=APP_NAME,
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title(f"✈️ {APP_NAME}")
st.caption(f"Weather Forecast & Flight Mission Planning | v{__version__}")

st.markdown(
    """
    <style>
    /* Entire tabs wrapper */
    div[data-testid="stTabs"] {
        background-color: #0e1117;
    }

    /* Tab buttons */
    div[data-testid="stTabs"] button[data-baseweb="tab"] {
        background-color: #1a1d24;
        color: #dce3ea;
        padding: 14px 26px;
        border-radius: 10px 10px 0 0;
        margin-right: 6px;
        border: 1px solid #2f3642;
    }

    /* Tab label text */
    div[data-testid="stTabs"] button[data-baseweb="tab"] p {
        font-size: 20px;
        font-weight: 700;
        color: #dce3ea;
    }

    /* Hover effect */
    div[data-testid="stTabs"] button[data-baseweb="tab"]:hover {
        background-color: #252b36;
        color: #ffffff;
    }

    /* Active/selected tab */
    div[data-testid="stTabs"] button[aria-selected="true"] {
        background-color: #12395c;
        border-bottom: 4px solid #3aa0ff;
    }

    div[data-testid="stTabs"] button[aria-selected="true"] p {
        color: #ffffff;
    }

    /* Tab content panel */
    div[data-testid="stTabs"] div[data-baseweb="tab-panel"] {
        min-height: 650px;
        padding: 24px;
        background-color: #151922;
        border: 1px solid #2f3642;
        border-radius: 0 0 14px 14px;
        color: #e6edf3;
    }

    /* Optional: make headings inside tabs brighter */
    div[data-testid="stTabs"] div[data-baseweb="tab-panel"] h1,
    div[data-testid="stTabs"] div[data-baseweb="tab-panel"] h2,
    div[data-testid="stTabs"] div[data-baseweb="tab-panel"] h3 {
        color: #ffffff;
    }
    </style>
    """,
    unsafe_allow_html=True
)

tab_hrrr, tab_avx, tab_tt = st.tabs([
    "🌤️ HRRR Forecast",
    "✈️ Aviation Weather",
    "🌀 Tropical Tidbits"
])

with tab_hrrr:
    st.subheader("HRRR Forecast")
    st.write("Your HRRR forecast content goes here.")

with tab_avx:
    st.subheader("Aviation Weather")
    st.write("Your aviation weather content goes here.")

with tab_tt:
    st.subheader("Tropical Tidbits")
    st.write("Your tropical content goes here.")
# ============================================================
# TAB 1: HRRR FORECAST
# ============================================================
with tab_hrrr:
    st.markdown("### 📍 Select Location")

    loc_choice = st.radio(
        "Site",
        ["🌲 DOE Bankhead NF (Alabama)",
         "🏜️ DustieAim – Phoenix, AZ",
         "📌 Custom Location"],
        horizontal=True)

    if "Bankhead" in loc_choice:
        site = get_site("bankhead")
    elif "DustieAim" in loc_choice:
        site = get_site("dustieaim")
    else:
        cc1, cc2, cc3, cc4 = st.columns(4)
        clat = cc1.number_input("Lat °N", -90.0, 90.0, 40.0, 0.0001)
        clon = cc2.number_input("Lon (neg °W)", -180.0, 180.0, -105.0, 0.0001)
        cname = cc3.text_input("Site Name", "Custom_Site")
        ctz = cc4.selectbox("Timezone", [
            "UTC", "US/Eastern", "US/Central",
            "US/Mountain", "US/Pacific", "America/Phoenix"])
        site = get_site(lat=clat, lon=clon, name=cname, tz=ctz)

    st.info(f"📍 **{site['full_name']}** | "
            f"{site['lat']}°N, {abs(site['lon'])}°W | "
            f"TZ: {site['timezone']}")

    st.markdown("### ⚙️ Parameters")
    col_d, col_h, col_f = st.columns(3)
    with col_d:
        sched_date = st.date_input("📅 Run Date (UTC)",
                                   value=date.today(),
                                   min_value=date(2020, 1, 1),
                                   max_value=date.today())
    with col_h:
        sched_hour = st.selectbox("🕐 Cycle", [0, 6, 12, 18], index=2,
                                  format_func=lambda x: f"{x:02d}Z")
    with col_f:
        sched_fxx = st.number_input("⏱️ Hours", 1, 48, 25)

    st.divider()
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        run_now = st.button("🚀 Run HRRR Forecast", type="primary",
                            use_container_width=True)

    if run_now:
        run_date_str = sched_date.strftime("%Y-%m-%d")
        prog = st.progress(0, text="Connecting to NOAA HRRR...")

        def cb(step, total, msg):
            prog.progress(step / total, text=f"⏳ {msg}")

        df = get_hrrr_forecast(
            run_date=run_date_str,
            run_hour=sched_hour,
            fxx_range=sched_fxx,
            site=site,
            progress_callback=cb,
            verbose=False)
        prog.empty()

        if df.empty:
            st.error("❌ No data. Try earlier date/hour.")
        else:
            st.session_state["df"] = df
            st.session_state["site"] = site
            st.session_state["run_info"] = f"{run_date_str}_{sched_hour:02d}Z"
            st.success(f"✅ {len(df)} hours retrieved")

    if "df" in st.session_state:
        df = st.session_state["df"]
        site_s = st.session_state["site"]
        run_info = st.session_state["run_info"]

        m1, m2, m3, m4, m5, m6 = st.columns(6)
        m1.metric("🌡 Max Temp", f"{df['temp_F'].max():.0f}°F")
        m2.metric("💨 Max Wind", f"{df['wind_speed_mph'].max():.1f} mph")
        m3.metric("🌧 Precip", f"{df['precip_mm'].sum():.1f} mm")
        sm = df['smoke_ugm3'].max() if df['smoke_ugm3'].notna().any() else None
        m4.metric("🔥 Smoke", f"{sm:.1f}" if sm else "N/A")
        du = df['dust_ugm3'].max() if df['dust_ugm3'].notna().any() else None
        m5.metric("🏜️ Dust", f"{du:.1f}" if du else "N/A")
        m6.metric("🌫 AOD", f"{df['aod_proxy'].max():.3f}")

        fig = generate_plots(df, site=site_s, dark_theme=True)
        st.pyplot(fig)

        with st.expander("📋 Data Table"):
            st.dataframe(df, use_container_width=True, height=300)

        st.markdown("### 💾 Download")
        d1, d2, d3 = st.columns(3)
        tag = f"wxflight_{site_s['name']}_{run_info}"
        d1.download_button("📥 CSV", df.to_csv(index=False),
                           f"{tag}.csv", "text/csv",
                           use_container_width=True)
        d2.download_button("📥 JSON",
                           df.to_json(orient="records", indent=2),
                           f"{tag}.json", "application/json",
                           use_container_width=True)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150,
                    bbox_inches="tight", facecolor='#0e1117')
        d3.download_button("📥 PNG", buf.getvalue(),
                           f"{tag}.png", "image/png",
                           use_container_width=True)

# ============================================================
# TAB 2: AVIATION WEATHER
# ============================================================
with tab_avx:
    st.markdown("### ✈️ METAR & TAF")

    if not HAS_REQUESTS:
        st.error("❌ `requests` package not installed. Run:\n\n"
                 "```\npip install requests\n```")
        st.stop()

    st.markdown("Select a station and click the button to fetch "
                "live data from aviationweather.gov")

    avx_c1, avx_c2, avx_c3 = st.columns(3)
    with avx_c1:
        station = st.selectbox("🛫 Station", [
            "KJFX – Jasper/Walker",
            "KBHM – Birmingham",
            "KHSV – Huntsville",
            "KPHX – Phoenix",
            "KDVT – Deer Valley"])
        station_id = station.split(" –")[0].strip()
    with avx_c2:
        custom_id = st.text_input("✏️ Or enter ID", "",
                                  max_chars=4,
                                  placeholder="e.g. KIWA").upper().strip()
    with avx_c3:
        avx_type = st.selectbox("Data type", [
            "METAR + TAF", "METAR only", "TAF only"])

    use_id = custom_id if custom_id else station_id

    st.markdown(f"**Station:** `{use_id}`")

    if st.button("✈️ Get Aviation Weather", type="primary"):
        # METAR
        if "TAF only" not in avx_type:
            st.markdown("#### 📡 METAR – Current Observation")
            try:
                url = (f"https://aviationweather.gov/api/data/metar"
                       f"?ids={use_id}&format=json&hours=2")
                r = requests.get(url, timeout=15)

                if r.status_code == 200:
                    data = r.json()
                    if data and len(data) > 0:
                        m = data[0]
                        # Flight category
                        cat = m.get("fltcat", "VFR")
                        st.markdown(f"**Flight Category:** "
                                    f"`{cat}` | "
                                    f"**Time:** {m.get('reportTime','')}")
                        # Raw
                        st.code(m.get("rawOb", "No raw data"), language=None)
                        # Decoded
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("🌡 Temp",
                                    f"{m.get('temp','?')}°C")
                        col2.metric("💧 Dewpoint",
                                    f"{m.get('dewp','?')}°C")
                        col3.metric("💨 Wind",
                                    f"{m.get('wdir','?')}° @ "
                                    f"{m.get('wspd','?')} kt")
                        col4.metric("👁 Visibility",
                                    f"{m.get('visib','?')} SM")

                        with st.expander("Full JSON response"):
                            st.json(m)
                    else:
                        st.warning(f"No METAR data returned for {use_id}")
                else:
                    st.error(f"API returned status {r.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("❌ Connection failed. Check internet or try:\n\n"
                         f"[Open on website ↗️]"
                         f"(https://aviationweather.gov/data/metar/"
                         f"?id={use_id})")
            except Exception as e:
                st.error(f"Error: {e}")

        # TAF
        if "METAR only" not in avx_type:
            st.markdown("#### 📋 TAF – Terminal Forecast")
            try:
                url = (f"https://aviationweather.gov/api/data/taf"
                       f"?ids={use_id}&format=json")
                r = requests.get(url, timeout=15)

                if r.status_code == 200:
                    data = r.json()
                    if data and len(data) > 0:
                        t = data[0]
                        st.code(t.get("rawTAF", "No raw TAF"),
                                language=None)
                        # Forecast periods
                        fcsts = t.get("fcsts", [])
                        if fcsts:
                            for p in fcsts:
                                change = p.get("fcstChange", "FM")
                                fr = p.get("timeFrom", "")
                                to = p.get("timeTo", "")
                                wd = p.get("wdir", "?")
                                ws = p.get("wspd", "?")
                                wg = p.get("wgst", "")
                                vis = p.get("visib", "?")
                                cld = ", ".join([
                                    f"{c.get('cover','')}{c.get('base','')}"
                                    for c in p.get("clouds", [])
                                ]) or "SKC"
                                gust_str = f" G{wg}kt" if wg else ""
                                st.markdown(
                                    f"**{change} {fr}→{to}** | "
                                    f"Wind: {wd}°@{ws}kt{gust_str} | "
                                    f"Vis: {vis}SM | Clouds: {cld}")
                        with st.expander("Full JSON"):
                            st.json(t)
                    else:
                        st.warning(f"No TAF for {use_id} "
                                   "(not all stations issue TAFs)")
                else:
                    st.error(f"TAF API returned {r.status_code}")
            except Exception as e:
                st.error(f"TAF error: {e}")

    # Always show direct links
    st.markdown("---")
    st.markdown("#### 🔗 Direct Links (open in browser)")
    st.markdown(
        f"- [METAR for {use_id} (website)]"
        f"(https://aviationweather.gov/data/metar/?id={use_id})\n"
        f"- [TAF for {use_id} (website)]"
        f"(https://aviationweather.gov/data/taf/?id={use_id})\n"
        f"- [METAR JSON API]"
        f"(https://aviationweather.gov/api/data/metar"
        f"?ids={use_id}&format=json&hours=2)\n"
        f"- [TAF JSON API]"
        f"(https://aviationweather.gov/api/data/taf"
        f"?ids={use_id}&format=json)")

# ============================================================
# TAB 3: TROPICAL TIDBITS
# ============================================================
with tab_tt:
    st.markdown("### 🌀 HRRR Model Maps – Tropical Tidbits")
    st.markdown("Configure parameters, then click the generated link "
                "to open the map in a new browser tab.")

    # Get current UTC hour safely
    try:
        current_utc_hour = datetime.utcnow().hour
        default_hour_index = max(0, current_utc_hour - 2)
    except Exception:
        default_hour_index = 12

    tt1, tt2, tt3 = st.columns(3)
    with tt1:
        tt_date = st.date_input("📅 Runtime Date",
                                value=date.today(),
                                key="tt_date_input")
    with tt2:
        tt_hour = st.selectbox("🕐 Runtime Hour (Z)",
                               list(range(24)),
                               index=default_hour_index,
                               format_func=lambda x: f"{x:02d}Z")
    with tt3:
        tt_region = st.selectbox("🗺️ Region", [
            "seus – SE US (Bankhead)",
            "swus – SW US (Phoenix)",
            "us – Full CONUS",
            "midsouth – Mid-South",
            "gulf – Gulf Coast",
            "soupl – S. Plains",
            "cpl – C. Plains",
            "ne – Northeast",
            "nw – Northwest",
            "mw – Midwest"])
        tt_region_code = tt_region.split(" –")[0].strip()

    tt4, tt5 = st.columns(2)
    with tt4:
        tt_pkg = st.selectbox("📊 Variable", [
            "ref_frzn – Reflectivity",
            "mslp_pcpn – MSLP & Precip",
            "T2m – 2m Temperature",
            "Td2m – 2m Dewpoint",
            "10mwind – 10m Wind",
            "sfcwind_gust – Surface Gusts",
            "precip_ptotal – Total Precip",
            "cape – CAPE",
            "vis – Visibility",
            "cig – Ceiling",
            "smoke – Smoke",
            "dust – Dust",
            "aod – AOD",
            "z500_mslp – 500mb Heights",
            "T850 – 850mb Temp",
            "pwat – Precip Water"])
        tt_pkg_code = tt_pkg.split(" –")[0].strip()
    with tt5:
        tt_fh = st.slider("⏱️ Forecast Hour", 0, 48, 1)

    # Build URL
    runtime = tt_date.strftime("%Y%m%d") + f"{tt_hour:02d}"
    tt_url = (f"https://www.tropicaltidbits.com/analysis/models/"
              f"?model=hrrr&region={tt_region_code}"
              f"&pkg={tt_pkg_code}&runtime={runtime}&fh={tt_fh}")

    st.markdown(f"**Runtime:** `{runtime}` | "
                f"**Region:** `{tt_region_code}` | "
                f"**Pkg:** `{tt_pkg_code}` | "
                f"**fh:** `{tt_fh}`")

    st.code(tt_url, language=None)

    # Clickable link (Streamlit renders markdown links as clickable)
    st.markdown(f"### [🌀 Open HRRR Map on Tropical Tidbits ↗️]({tt_url})")

    st.markdown("---")

    # Quick links
    st.markdown("#### 🔗 Quick Links")
    pkgs = [("ref_frzn", "Reflectivity"), ("T2m", "Temp"),
            ("10mwind", "Wind"), ("precip_ptotal", "Precip"),
            ("smoke", "Smoke"), ("dust", "Dust"),
            ("aod", "AOD"), ("cape", "CAPE"), ("vis", "Vis")]

    st.markdown("**🌲 Bankhead NF (seus):**")
    links_seus = " | ".join([
        f"[{label}](https://www.tropicaltidbits.com/analysis/models/"
        f"?model=hrrr&region=seus&pkg={code}&runtime={runtime}&fh=1)"
        for code, label in pkgs])
    st.markdown(links_seus)

    st.markdown("**🏜️ DustieAim Phoenix (swus):**")
    links_swus = " | ".join([
        f"[{label}](https://www.tropicaltidbits.com/analysis/models/"
        f"?model=hrrr&region=swus&pkg={code}&runtime={runtime}&fh=1)"
        for code, label in pkgs])
    st.markdown(links_swus)

# Footer
st.divider()
st.caption(f"{APP_NAME} v{__version__} | "
           f"Data: NOAA HRRR, aviationweather.gov, Tropical Tidbits")