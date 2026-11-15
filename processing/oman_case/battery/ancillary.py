"""Ancillary (non-SAR) data for the Oman battery: wind, rain, SST, chlorophyll, currents.

Used by M4/M5 (wind for the GMF / damping ratio), M15 (drift: wind + currents) and
M20 (look-alike context: upwelling = cold SST, blooms = high chlorophyll, rain cells).

Network access happens only when a cache file is missing; with a filled cache
(oman_case/data_cache/ancillary/*.npz) every function works offline.

Sources (all open, no extra accounts):
  ERA5 wind/precip  Open-Meteo archive API, models=era5, 0.25 deg, hourly
  SST               MUR SST v4.1 L4 (JPL), ERDDAP coastwatch.pfeg.noaa.gov jplMURSST41, 0.01 deg, daily
                    fallback: NOAA OISST v2.1 ERDDAP ncdcOisst21Agg_LonPM180, 0.25 deg
  Chlorophyll       NOAA CoastWatch DINEOF gap-filled VIIRS(SNPP+NOAA-20)+OLCI(S3A) daily, ~2 km
                    (ERDDAP noaacwNPPN20S3ASCIDINEOF2kmDaily) + raw daily VIIRS NOAA-20 / SNPP
                    (nesdisVHNnoaa20chlaDaily / nesdisVHNchlaDaily, 0.0375 deg) to report real cloud gaps
  Currents          Open-Meteo marine API (MeteoFrance SMOC: Eulerian + waves + tides, native 0.08 deg),
                    sampled on a 1/6 deg grid; direction = flow direction ("towards")
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

from . import config

CACHE = config.ANCILLARY
ERDDAP = "https://coastwatch.pfeg.noaa.gov/erddap/griddap"
MARGIN_DEG = 0.25


# ----------------------------------------------------------------------------- helpers
def _scene(scene_id):
    return config.scene(scene_id)


def _bbox(scene_id, margin=MARGIN_DEG):
    lon0, lat0, lon1, lat1, _ = config.AOI[_scene(scene_id)["aoi"]]
    return lon0 - margin, lat0 - margin, lon1 + margin, lat1 + margin


def _scene_dt(scene_id):
    return datetime.strptime(_scene(scene_id)["time"], "%Y-%m-%dT%H:%M")


def _grid(lo, hi, step):
    a = np.floor(lo / step) * step
    b = np.ceil(hi / step) * step
    return np.round(np.arange(a, b + step / 2, step), 6)


def _get(url, timeout=180, tries=3):
    last = None
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nisar-oman-battery/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # network hiccups / rate limits: back off and retry
            last = e
            time.sleep(3 * (k + 1))
    raise RuntimeError(f"request failed after {tries} tries: {last}")


def _save(path, **arrays):
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **{k: (np.asarray(v) if not isinstance(v, str) else np.array(v)) for k, v in arrays.items()})


def _load(path):
    d = np.load(path, allow_pickle=False)
    out = {}
    for k in d.files:
        v = d[k]
        out[k] = v.item() if v.ndim == 0 else v
    return out


def _openmeteo_points(base, lats, lons, params, chunk=100):
    """Multi-location Open-Meteo request, chunked; returns list of per-point JSON objects."""
    out = []
    for i in range(0, len(lats), chunk):
        q = dict(params)
        q["latitude"] = ",".join(f"{v:.4f}" for v in lats[i:i + chunk])
        q["longitude"] = ",".join(f"{v:.4f}" for v in lons[i:i + chunk])
        js = json.loads(_get(base + "?" + urllib.parse.urlencode(q)))
        out.extend(js if isinstance(js, list) else [js])
        time.sleep(0.5)
    return out


def _time_weights(times_iso, t):
    """Indices and linear weights of the two hourly samples bracketing t."""
    ts = [datetime.strptime(s, "%Y-%m-%dT%H:%M") for s in times_iso]
    for i in range(len(ts) - 1):
        if ts[i] <= t <= ts[i + 1]:
            w = (t - ts[i]).total_seconds() / (ts[i + 1] - ts[i]).total_seconds()
            return i, i + 1, w
    j = int(np.argmin([abs((x - t).total_seconds()) for x in ts]))
    return j, j, 0.0


def _erddap_nc(dataset, var, time_iso, lat0, lat1, lon0, lon1, altitude=False):
    """Download an ERDDAP griddap subset (.nc) and return (lat, lon, 2D values) with lat ascending."""
    import xarray as xr
    tsel = f"[({time_iso})]"
    asel = "[(0.0)]" if altitude else ""
    q = f"{var}{tsel}{asel}[({lat0}):1:({lat1})][({lon0}):1:({lon1})]"
    url = f"{ERDDAP}/{dataset}.nc?" + urllib.parse.quote(q, safe="():,")
    raw = _get(url)
    tmp = CACHE / f"_tmp_{dataset}.nc"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(raw)
    with xr.open_dataset(tmp) as ds:
        a = ds[var].values.squeeze().astype(np.float32)
        lat = ds["latitude"].values.astype(np.float64)
        lon = ds["longitude"].values.astype(np.float64)
        t_actual = str(ds["time"].values.ravel()[0])[:19]
    tmp.unlink(missing_ok=True)
    if lat[0] > lat[-1]:
        lat, a = lat[::-1], a[::-1]
    return lat, lon, a, t_actual


# ----------------------------------------------------------------------------- ERA5
def era5(scene_id):
    """ERA5 10 m wind + precipitation at the scene time (linear in time between hours).

    Returns dict(lon[nx], lat[ny], u10, v10, wspd [m/s], wdir_from_deg (meteorological, coming from),
    precip_mm (hour containing the acquisition), precip_3h_mm, time_utc, source)."""
    path = CACHE / f"era5_{scene_id}.npz"
    if path.exists():
        return _load(path)
    lon0, lat0, lon1, lat1 = _bbox(scene_id)
    lons, lats = _grid(lon0, lon1, 0.25), _grid(lat0, lat1, 0.25)
    LON, LAT = np.meshgrid(lons, lats)
    t = _scene_dt(scene_id)
    day0 = (t - timedelta(hours=3)).strftime("%Y-%m-%d")
    day1 = (t + timedelta(hours=1)).strftime("%Y-%m-%d")
    pts = _openmeteo_points(
        "https://archive-api.open-meteo.com/v1/archive", LAT.ravel(), LON.ravel(),
        dict(start_date=day0, end_date=day1, hourly="wind_speed_10m,wind_direction_10m,precipitation",
             wind_speed_unit="ms", timezone="GMT", models="era5"))
    u = np.full(LAT.size, np.nan)
    v = np.full(LAT.size, np.nan)
    p1 = np.full(LAT.size, np.nan)
    p3 = np.full(LAT.size, np.nan)
    for k, pt in enumerate(pts):
        h = pt["hourly"]
        i, j, w = _time_weights(h["time"], t)
        ws, wd = np.array(h["wind_speed_10m"], float), np.deg2rad(np.array(h["wind_direction_10m"], float))
        uu, vv = -ws * np.sin(wd), -ws * np.cos(wd)
        u[k] = (1 - w) * uu[i] + w * uu[j]
        v[k] = (1 - w) * vv[i] + w * vv[j]
        pr = np.array(h["precipitation"], float)
        p1[k] = pr[j]                               # hour ending after the acquisition
        p3[k] = np.nansum(pr[max(0, j - 2):j + 1])
    u, v = u.reshape(LAT.shape), v.reshape(LAT.shape)
    res = dict(lon=lons, lat=lats, u10=u, v10=v, wspd=np.hypot(u, v),
               wdir_from_deg=(np.rad2deg(np.arctan2(-u, -v)) + 360) % 360,
               precip_mm=p1.reshape(LAT.shape), precip_3h_mm=p3.reshape(LAT.shape),
               time_utc=t.strftime("%Y-%m-%dT%H:%M"), source="Open-Meteo archive ERA5 0.25deg")
    _save(path, **res)
    return res


# ----------------------------------------------------------------------------- SST
def sst(scene_id):
    """Daily L4 SST for the scene UTC date: dict(lon, lat, sst_c, source, time_actual)."""
    path = CACHE / f"sst_{scene_id}.npz"
    if path.exists():
        return _load(path)
    lon0, lat0, lon1, lat1 = _bbox(scene_id)
    day = _scene_dt(scene_id).strftime("%Y-%m-%d")
    try:
        lat, lon, a, ta = _erddap_nc("jplMURSST41", "analysed_sst", f"{day}T09:00:00Z", lat0, lat1, lon0, lon1)
        src = "MUR SST v4.1 (jplMURSST41) 0.01deg"
    except Exception as e:
        lat, lon, a, ta = _erddap_nc("ncdcOisst21Agg_LonPM180", "sst", f"{day}T12:00:00Z", lat0, lat1, lon0, lon1,
                                     altitude=True)
        src = f"NOAA OISST v2.1 0.25deg (MUR failed: {e})"
    res = dict(lon=lon, lat=lat, sst_c=a, source=src, time_actual=ta)
    _save(path, **res)
    return res


# ----------------------------------------------------------------------------- chlorophyll
_CHL_GAPFILLED = "noaacwNPPN20S3ASCIDINEOF2kmDaily"
_CHL_RAW = ["nesdisVHNnoaa20chlaDaily", "nesdisVHNchlaDaily"]


def chl(scene_id, max_days=3):
    """Chlorophyll-a [mg m^-3] for the scene date.

    chl_mg_m3 is the DINEOF gap-filled multi-sensor product (no cloud gaps) for the scene date
    (nearest day within +-max_days if missing). raw_chl is the best-covered *observed* daily VIIRS
    field within +-max_days (cloud gaps = NaN); raw_coverage is its valid fraction over ocean.
    Returns dict(lon, lat, chl_mg_m3, source, days_from_scene,
                 raw_lon, raw_lat, raw_chl, raw_source, raw_days_from_scene, raw_coverage, raw_coverage_same_day)."""
    path = CACHE / f"chl_{scene_id}.npz"
    if path.exists():
        return _load(path)
    lon0, lat0, lon1, lat1 = _bbox(scene_id)
    d0 = _scene_dt(scene_id).date()
    offsets = [0] + [s * k for k in range(1, max_days + 1) for s in (1, -1)]
    gap = None
    for off in offsets:
        day = (d0 + timedelta(days=off)).isoformat()
        try:
            lat, lon, a, ta = _erddap_nc(_CHL_GAPFILLED, "chlor_a", f"{day}T12:00:00Z", lat0, lat1, lon0, lon1,
                                         altitude=True)
            if np.isfinite(a).any():
                gap = (lat, lon, a, off)
                break
        except Exception:
            continue
    ocean_frac = float(np.isfinite(gap[2]).mean()) if gap else np.nan   # gap-filled is NaN only on land
    best = None
    same_day_cov = 0.0
    for off in offsets:
        day = (d0 + timedelta(days=off)).isoformat()
        for ds in _CHL_RAW:
            try:
                rl, rn, ra, _ = _erddap_nc(ds, "chlor_a", f"{day}T12:00:00Z", lat0, lat1, lon0, lon1, altitude=True)
            except Exception:
                continue
            cov = float(np.isfinite(ra).mean() / ocean_frac) if ocean_frac and ocean_frac > 0 else float(np.isfinite(ra).mean())
            cov = min(cov, 1.0)
            if off == 0:
                same_day_cov = max(same_day_cov, cov)
            if best is None or cov > best[4] + 1e-9:
                best = (rl, rn, ra, f"{ds} ({day})", cov, off)
    res = dict(
        lon=gap[1] if gap else np.array([]), lat=gap[0] if gap else np.array([]),
        chl_mg_m3=gap[2] if gap else np.zeros((0, 0), np.float32),
        source=f"{_CHL_GAPFILLED} (DINEOF gap-filled, ~2 km)" if gap else "unavailable",
        days_from_scene=gap[3] if gap else 999,
        raw_lon=best[1] if best else np.array([]), raw_lat=best[0] if best else np.array([]),
        raw_chl=best[2] if best else np.zeros((0, 0), np.float32),
        raw_source=best[3] if best else "unavailable", raw_days_from_scene=best[5] if best else 999,
        raw_coverage=best[4] if best else 0.0, raw_coverage_same_day=same_day_cov)
    _save(path, **res)
    return res


# ----------------------------------------------------------------------------- currents
def currents(scene_id, step=1 / 6):
    """Surface currents at the scene time: dict(lon, lat, u, v [m/s, flow-towards convention], speed, source)
    or None if unavailable (reason in currents_status(scene_id))."""
    path = CACHE / f"cur_{scene_id}.npz"
    if path.exists():
        d = _load(path)
        return None if d.get("status", "ok") != "ok" else d
    lon0, lat0, lon1, lat1 = _bbox(scene_id)
    lons, lats = _grid(lon0, lon1, step), _grid(lat0, lat1, step)
    LON, LAT = np.meshgrid(lons, lats)
    t = _scene_dt(scene_id)
    day0 = (t - timedelta(hours=1)).strftime("%Y-%m-%d")
    day1 = (t + timedelta(hours=1)).strftime("%Y-%m-%d")
    try:
        pts = _openmeteo_points(
            "https://marine-api.open-meteo.com/v1/marine", LAT.ravel(), LON.ravel(),
            dict(start_date=day0, end_date=day1, hourly="ocean_current_velocity,ocean_current_direction",
                 timezone="GMT", cell_selection="sea"))
    except Exception as e:
        _save(path, status=f"failed: {e}")
        return None
    u = np.full(LAT.size, np.nan)
    v = np.full(LAT.size, np.nan)
    for k, pt in enumerate(pts):
        h = pt.get("hourly", {})
        if not h or h.get("ocean_current_velocity") is None:
            continue
        i, j, w = _time_weights(h["time"], t)
        sp = np.array([np.nan if x is None else x for x in h["ocean_current_velocity"]], float) / 3.6  # km/h -> m/s
        dr = np.deg2rad(np.array([np.nan if x is None else x for x in h["ocean_current_direction"]], float))
        uu, vv = sp * np.sin(dr), sp * np.cos(dr)                                    # towards convention
        u[k] = (1 - w) * uu[i] + w * uu[j]
        v[k] = (1 - w) * vv[i] + w * vv[j]
    u, v = u.reshape(LAT.shape), v.reshape(LAT.shape)
    if not np.isfinite(u).any():
        _save(path, status="failed: no valid current values returned")
        return None
    res = dict(lon=lons, lat=lats, u=u, v=v, speed=np.hypot(u, v), time_utc=t.strftime("%Y-%m-%dT%H:%M"),
               source="Open-Meteo marine (MeteoFrance SMOC: Eulerian+waves+tides, native 0.08deg), sampled 1/6deg",
               status="ok")
    _save(path, **res)
    return res


def currents_status(scene_id):
    path = CACHE / f"cur_{scene_id}.npz"
    return _load(path).get("status", "missing") if path.exists() else "missing (not fetched)"


# ----------------------------------------------------------------------------- regridding
def to_grid(field_lon, field_lat, values, X_utm, Y_utm, epsg=config.EPSG, fill_nan_nearest=False):
    """Bilinear interpolation of a regular lon/lat field (values[lat, lon]) onto a UTM grid.

    X_utm, Y_utm: 2-D meshgrids in metres (epsg). Points outside the field -> NaN.
    fill_nan_nearest=True first fills NaN cells (e.g. land/cloud gaps in SST/chl) with the nearest
    valid value so that coastal sea pixels get a value."""
    from pyproj import Transformer
    from scipy import ndimage
    from scipy.interpolate import RegularGridInterpolator

    lon = np.asarray(field_lon, float)
    lat = np.asarray(field_lat, float)
    val = np.asarray(values, float)
    if lat[0] > lat[-1]:
        lat, val = lat[::-1], val[::-1]
    if lon[0] > lon[-1]:
        lon, val = lon[::-1], val[:, ::-1]
    if fill_nan_nearest and np.isnan(val).any() and np.isfinite(val).any():
        idx = ndimage.distance_transform_edt(np.isnan(val), return_distances=False, return_indices=True)
        val = val[tuple(idx)]
    tr = Transformer.from_crs(epsg, 4326, always_xy=True)
    lo, la = tr.transform(np.asarray(X_utm, float), np.asarray(Y_utm, float))
    it = RegularGridInterpolator((lat, lon), val, method="linear", bounds_error=False, fill_value=np.nan)
    return it((la, lo))


# ----------------------------------------------------------------------------- quick-look figures
PLUME_BOX = (56.35, 17.45, 57.0, 17.95)   # lon0, lat0, lon1, lat1 — area NE of the source where the plume sits


def box_stats(scene_id, box=PLUME_BOX):
    """Mean SST / chlorophyll / wind / current inside `box` and their contrast to the scene AOI median."""
    out = {"scene": scene_id, "time_utc": _scene(scene_id)["time"]}

    def inbox(lon, lat, a):
        LON, LAT = np.meshgrid(lon, lat)
        m = (LON >= box[0]) & (LON <= box[2]) & (LAT >= box[1]) & (LAT <= box[3])
        return a[m]

    t = sst(scene_id)
    b = inbox(t["lon"], t["lat"], t["sst_c"])
    out["sst_box_c"] = float(np.nanmean(b))
    out["sst_box_min_c"] = float(np.nanmin(b))
    out["sst_aoi_median_c"] = float(np.nanmedian(t["sst_c"]))
    c = chl(scene_id)
    if c["chl_mg_m3"].size:
        b = inbox(c["lon"], c["lat"], c["chl_mg_m3"])
        out["chl_box_median"] = float(np.nanmedian(b))
        out["chl_aoi_median"] = float(np.nanmedian(c["chl_mg_m3"]))
    e = era5(scene_id)
    out["wspd_box"] = float(np.nanmean(inbox(e["lon"], e["lat"], e["wspd"])))
    uu, vv = np.nanmean(inbox(e["lon"], e["lat"], e["u10"])), np.nanmean(inbox(e["lon"], e["lat"], e["v10"]))
    out["wdir_from_box"] = float((np.rad2deg(np.arctan2(-uu, -vv)) + 360) % 360)
    out["precip_3h_box_mm"] = float(np.nanmax(inbox(e["lon"], e["lat"], e["precip_3h_mm"])))
    cu = currents(scene_id)
    if cu is not None:
        cu_u, cu_v = np.nanmean(inbox(cu["lon"], cu["lat"], cu["u"])), np.nanmean(inbox(cu["lon"], cu["lat"], cu["v"]))
        out["cur_speed_box"] = float(np.hypot(cu_u, cu_v))
        out["cur_dir_to_box"] = float((np.rad2deg(np.arctan2(cu_u, cu_v)) + 360) % 360)
    return out


def quicklook_figure(scene_ids, out_png, view=(55.9, 17.0, 58.4, 18.6)):
    """Rows = scenes; columns = SST (+ERA5 wind black, currents blue) and gap-filled chlorophyll."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm

    n = len(scene_ids)
    fig, axes = plt.subplots(n, 2, figsize=(12.5, 3.6 * n), dpi=110, squeeze=False)
    for r, sid in enumerate(scene_ids):
        sc = _scene(sid)
        t, c, e, cu = sst(sid), chl(sid), era5(sid), currents(sid)
        ax = axes[r, 0]
        vals = t["sst_c"]
        im = ax.pcolormesh(t["lon"], t["lat"], vals, cmap="RdYlBu_r", shading="auto",
                           vmin=np.nanpercentile(vals, 2), vmax=np.nanpercentile(vals, 98))
        plt.colorbar(im, ax=ax, label="SST, °C", shrink=0.85)
        LON, LAT = np.meshgrid(e["lon"], e["lat"])
        ax.quiver(LON, LAT, e["u10"], e["v10"], color="k", scale=250, width=0.003)
        if cu is not None:
            CL, CA = np.meshgrid(cu["lon"], cu["lat"])
            ax.quiver(CL, CA, cu["u"], cu["v"], color="#1f4fd1", scale=6, width=0.003)
        ax.set_title(f"{sid} ({sc['role']}) {sc['time']} UTC — MUR SST; ERA5 ветер (чёрн.), течения (син.)", fontsize=8)
        ax = axes[r, 1]
        if c["chl_mg_m3"].size:
            im = ax.pcolormesh(c["lon"], c["lat"], c["chl_mg_m3"], cmap="viridis", shading="auto",
                               norm=LogNorm(vmin=0.1, vmax=10))
            plt.colorbar(im, ax=ax, label="Chl-a, мг/м³", shrink=0.85)
        ax.set_title(f"Хлорофилл DINEOF (gap-filled), сдвиг {int(c['days_from_scene'])} дн; "
                     f"реальное покрытие без облаков ±3 дн: {float(c['raw_coverage']):.0%}", fontsize=8)
        for ax in axes[r]:
            ax.plot(*config.SOURCE_LONLAT, marker="*", color="red", ms=12, mec="k")
            bx = PLUME_BOX
            ax.plot([bx[0], bx[2], bx[2], bx[0], bx[0]], [bx[1], bx[1], bx[3], bx[3], bx[1]], "m--", lw=0.8)
            ax.set_xlim(view[0], view[2])
            ax.set_ylim(view[1], view[3])
            ax.set_aspect(1 / np.cos(np.deg2rad(np.mean(view[1::2]))))
            ax.set_facecolor("#bbb")
            ax.tick_params(labelsize=7)
    fig.tight_layout()
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, facecolor="white")
    plt.close(fig)
    return out_png


def timeseries_figure(out_png, scene_ids=None):
    """Plume-box SST anomaly, chlorophyll ratio, wind and current vs time for the island scenes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    scene_ids = scene_ids or [s["id"] for s in config.ISLAND_SCENES]
    rows = sorted((box_stats(s) for s in scene_ids), key=lambda r: r["time_utc"])
    tt = [datetime.strptime(r["time_utc"], "%Y-%m-%dT%H:%M") for r in rows]
    fig, ax = plt.subplots(4, 1, figsize=(9, 9), dpi=110, sharex=True)
    ax[0].plot(tt, [r["sst_box_c"] - r["sst_aoi_median_c"] for r in rows], "o-", label="средняя в боксе − медиана района")
    ax[0].plot(tt, [r["sst_box_min_c"] - r["sst_aoi_median_c"] for r in rows], "v--", label="минимум в боксе − медиана района")
    ax[0].axhline(0, color="gray", lw=0.6)
    ax[0].set_ylabel("ΔSST, °C")
    ax[0].legend(fontsize=7)
    ax[1].plot(tt, [r.get("chl_box_median", np.nan) / r.get("chl_aoi_median", np.nan) for r in rows], "o-g")
    ax[1].axhline(1, color="gray", lw=0.6)
    ax[1].set_ylabel("Chl бокс / район")
    ax[2].plot(tt, [r["wspd_box"] for r in rows], "o-k", label="ERA5 ветер, м/с")
    ax[2].set_ylabel("ветер, м/с")
    ax2 = ax[2].twinx()
    ax2.plot(tt, [r["wdir_from_box"] for r in rows], "s:", color="#888", label="направление (откуда), °")
    ax2.set_ylabel("откуда, °")
    ax[3].plot(tt, [r.get("cur_speed_box", np.nan) for r in rows], "o-", color="#1f4fd1")
    ax[3].set_ylabel("течение, м/с")
    for a in ax:
        a.axvline(datetime.strptime(config.GROUNDING_DATE, "%Y-%m-%d"), color="r", ls=":", lw=1)
        a.grid(alpha=0.3)
    ax[0].set_title("Внешние условия в боксе шлейфа (56.35–57.0° в.д., 17.45–17.95° с.ш.); красная линия — посадка на мель",
                    fontsize=9)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(out_png, facecolor="white")
    plt.close(fig)
    return rows


# ----------------------------------------------------------------------------- prefetch + availability
def prefetch_all(write_report=True):
    """Fetch (or load from cache) all ancillary fields for every scene in config.SCENES and
    write results/m20_availability.json. Returns the availability dict."""
    rep = {"generated_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "sources": {}, "scenes": {}}
    for s in config.SCENES:
        sid = s["id"]
        row = {"time_utc": s["time"], "aoi": s["aoi"]}
        try:
            e = era5(sid)
            row["era5"] = {"ok": True, "wspd_median": round(float(np.nanmedian(e["wspd"])), 2),
                           "wspd_min": round(float(np.nanmin(e["wspd"])), 2),
                           "wdir_from_median": round(float(np.nanmedian(e["wdir_from_deg"])), 1),
                           "precip_3h_max_mm": round(float(np.nanmax(e["precip_3h_mm"])), 2),
                           "grid": f"{len(e['lat'])}x{len(e['lon'])}"}
        except Exception as ex:
            row["era5"] = {"ok": False, "error": str(ex)[:300]}
        try:
            t = sst(sid)
            a = t["sst_c"]
            row["sst"] = {"ok": True, "source": str(t["source"]), "valid_frac": round(float(np.isfinite(a).mean()), 3),
                          "min_c": round(float(np.nanmin(a)), 2), "median_c": round(float(np.nanmedian(a)), 2),
                          "max_c": round(float(np.nanmax(a)), 2), "grid": f"{a.shape[0]}x{a.shape[1]}"}
        except Exception as ex:
            row["sst"] = {"ok": False, "error": str(ex)[:300]}
        try:
            c = chl(sid)
            a = c["chl_mg_m3"]
            row["chl"] = {"ok": a.size > 0, "source": str(c["source"]), "days_from_scene": int(c["days_from_scene"]),
                          "median_mg_m3": round(float(np.nanmedian(a)), 3) if a.size else None,
                          "p90_mg_m3": round(float(np.nanpercentile(a, 90)), 3) if a.size else None,
                          "raw_source": str(c["raw_source"]), "raw_days_from_scene": int(c["raw_days_from_scene"]),
                          "raw_coverage_best_within_3d": round(float(c["raw_coverage"]), 3),
                          "raw_coverage_same_day": round(float(c["raw_coverage_same_day"]), 3)}
        except Exception as ex:
            row["chl"] = {"ok": False, "error": str(ex)[:300]}
        try:
            cu = currents(sid)
            if cu is None:
                row["currents"] = {"ok": False, "reason": currents_status(sid)}
            else:
                row["currents"] = {"ok": True, "speed_median_ms": round(float(np.nanmedian(cu["speed"])), 3),
                                   "speed_max_ms": round(float(np.nanmax(cu["speed"])), 3),
                                   "valid_frac": round(float(np.isfinite(cu["u"]).mean()), 3),
                                   "grid": f"{len(cu['lat'])}x{len(cu['lon'])}"}
        except Exception as ex:
            row["currents"] = {"ok": False, "error": str(ex)[:300]}
        rep["scenes"][sid] = row
        print(sid, {k: (v.get("ok") if isinstance(v, dict) else v) for k, v in row.items()})
    rep["sources"] = {
        "era5": {"endpoint": "https://archive-api.open-meteo.com/v1/archive (models=era5)",
                 "resolution": "0.25 deg, hourly; linear in time to the acquisition minute",
                 "variables": "wind_speed_10m, wind_direction_10m, precipitation"},
        "sst": {"endpoint": f"{ERDDAP}/jplMURSST41 (fallback ncdcOisst21Agg_LonPM180)",
                "resolution": "0.01 deg daily (MUR L4, 09:00 UTC analysis)"},
        "chl": {"endpoint": f"{ERDDAP}/{_CHL_GAPFILLED} (+ raw {', '.join(_CHL_RAW)})",
                "resolution": "gap-filled ~0.02 deg daily; raw 0.0375 deg daily with cloud gaps"},
        "currents": {"endpoint": "https://marine-api.open-meteo.com/v1/marine",
                     "resolution": "model native 0.08 deg hourly (MeteoFrance SMOC), sampled every 1/6 deg",
                     "convention": "u,v in m/s, direction = flow towards"},
    }
    files = sorted(CACHE.glob("*.npz"))
    rep["cache"] = {"dir": str(CACHE), "n_files": len(files),
                    "size_mb": round(sum(f.stat().st_size for f in files) / 2**20, 2)}
    if write_report:
        config.RESULTS.mkdir(parents=True, exist_ok=True)
        (config.RESULTS / "m20_availability.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    return rep
