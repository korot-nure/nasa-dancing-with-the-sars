"""ERA5 wind/precipitation and surface currents for an acquisition (Open-Meteo, no account needed),
cached per acquisition. Adapted from oman_case/battery/ancillary.py (bbox/time instead of scene ids)."""
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

import numpy as np
from pyproj import Transformer
from scipy import ndimage
from scipy.interpolate import RegularGridInterpolator


RATE_WAIT_S, RATE_TRIES = 300, 14      # Open-Meteo free tier: 600/min, 5000/h, 10000/day location-calls -> HTTP 429


ERA5_STEP = 0.5   # deg; caches made before 15.11.2026 16:xx used 0.25 (oman, uae_uaq, ei316, gc600, most of wreck1487)


class DailyLimit(RuntimeError):
    """Open-Meteo daily quota exhausted: retrying today is pointless."""


_DAILY_OFF = {}                        # API host -> time its "daily" quota was reported exhausted
DAILY_RETRY_S = 1800                   # the quota window is rolling in practice: probe the host again after 30 min


def _get(url, timeout=180, tries=3):
    """GET with retries. HTTP 429 with the hourly/minutely limit: wait RATE_WAIT_S and retry (clears within
    the hour). 429 with the DAILY limit: raise DailyLimit at once (and for every later call to that host)."""
    host = urllib.parse.urlparse(url).netloc
    if host in _DAILY_OFF and time.time() - _DAILY_OFF[host] < DAILY_RETRY_S:
        raise DailyLimit(f"{host}: daily request limit exceeded (earlier in this run)")
    last, k, waits = None, 0, 0
    while k < tries:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "nisar-oil-pipeline/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                try:
                    reason = json.loads(e.read().decode()).get("reason", "")
                except Exception:
                    reason = ""
                if "daily" in reason.lower():
                    _DAILY_OFF[host] = time.time()
                    raise DailyLimit(f"{host}: {reason}")
                if waits < RATE_TRIES:
                    waits += 1
                    time.sleep(RATE_WAIT_S)
                    continue
            k += 1
            time.sleep(3 * k)
        except Exception as e:
            last = e
            k += 1
            time.sleep(3 * k)
    raise RuntimeError(f"request failed after {tries} tries ({waits} rate-limit waits): {last}")


def _points(base, lats, lons, params, chunk=100):
    out = []
    for i in range(0, len(lats), chunk):
        q = dict(params)
        q["latitude"] = ",".join(f"{v:.4f}" for v in lats[i:i + chunk])
        q["longitude"] = ",".join(f"{v:.4f}" for v in lons[i:i + chunk])
        js = json.loads(_get(base + "?" + urllib.parse.urlencode(q)))
        out.extend(js if isinstance(js, list) else [js])
        time.sleep(0.5)
    return out


def _weights(times_iso, t):
    ts = [datetime.strptime(s, "%Y-%m-%dT%H:%M") for s in times_iso]
    for i in range(len(ts) - 1):
        if ts[i] <= t <= ts[i + 1]:
            return i, i + 1, (t - ts[i]).total_seconds() / (ts[i + 1] - ts[i]).total_seconds()
    j = int(np.argmin([abs((x - t).total_seconds()) for x in ts]))
    return j, j, 0.0


def _grid(lo, hi, step):
    return np.round(np.arange(np.floor(lo / step) * step, np.ceil(hi / step) * step + step / 2, step), 6)


def _cache(region, kind, acq_id):
    return region.ancillary_dir / f"{kind}_{acq_id}.npz"


def _load(p):
    d = np.load(p, allow_pickle=False)
    return {k: (d[k].item() if d[k].ndim == 0 else d[k]) for k in d.files}


def era5(region, acq_id, time_utc):
    """ERA5 10 m wind (u, v, speed, direction-from) and precipitation (3 h before), 0.25 deg."""
    p = _cache(region, "era5", acq_id)
    if p.exists():
        return _load(p)
    lon0, lat0, lon1, lat1 = region.bbox
    lons, lats = _grid(lon0 - 0.25, lon1 + 0.25, ERA5_STEP), _grid(lat0 - 0.25, lat1 + 0.25, ERA5_STEP)
    LON, LAT = np.meshgrid(lons, lats)
    t = datetime.strptime(time_utc[:16], "%Y-%m-%dT%H:%M")
    pts = _points("https://archive-api.open-meteo.com/v1/archive", LAT.ravel(), LON.ravel(),
                  dict(start_date=(t - timedelta(hours=3)).strftime("%Y-%m-%d"), end_date=(t + timedelta(hours=1)).strftime("%Y-%m-%d"),
                       hourly="wind_speed_10m,wind_direction_10m,precipitation", wind_speed_unit="ms", timezone="GMT", models="era5"))
    u, v, p3 = (np.full(LAT.size, np.nan) for _ in range(3))
    for k, pt in enumerate(pts):
        h = pt["hourly"]
        i, j, w = _weights(h["time"], t)
        ws = np.array(h["wind_speed_10m"], float)
        wd = np.deg2rad(np.array(h["wind_direction_10m"], float))
        uu, vv = -ws * np.sin(wd), -ws * np.cos(wd)
        u[k], v[k] = (1 - w) * uu[i] + w * uu[j], (1 - w) * vv[i] + w * vv[j]
        pr = np.array([np.nan if x is None else x for x in h["precipitation"]], float)
        p3[k] = np.nansum(pr[max(0, j - 2):j + 1])
    u, v = u.reshape(LAT.shape), v.reshape(LAT.shape)
    res = dict(lon=lons, lat=lats, u10=u, v10=v, wspd=np.hypot(u, v),
               wdir_from=(np.rad2deg(np.arctan2(-u, -v)) + 360) % 360, precip_3h=p3.reshape(LAT.shape))
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(p, **res)
    return res


def currents(region, acq_id, time_utc, step=1 / 3):      # 1/3 deg: enough for a drift direction, 4x fewer calls than 1/6
    """Surface currents (towards convention, m/s) from Open-Meteo marine (MeteoFrance SMOC); None if unavailable."""
    p = _cache(region, "cur", acq_id)
    if p.exists():
        d = _load(p)
        return None if "u" not in d else d
    lon0, lat0, lon1, lat1 = region.bbox
    lons, lats = _grid(lon0 - 0.2, lon1 + 0.2, step), _grid(lat0 - 0.2, lat1 + 0.2, step)
    LON, LAT = np.meshgrid(lons, lats)
    t = datetime.strptime(time_utc[:16], "%Y-%m-%dT%H:%M")
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        pts = _points("https://marine-api.open-meteo.com/v1/marine", LAT.ravel(), LON.ravel(),
                      dict(start_date=(t - timedelta(hours=1)).strftime("%Y-%m-%d"), end_date=(t + timedelta(hours=1)).strftime("%Y-%m-%d"),
                           hourly="ocean_current_velocity,ocean_current_direction", timezone="GMT", cell_selection="sea"))
    except DailyLimit:
        return None                    # not cached: can be filled in later when the quota resets
    except Exception as e:
        np.savez_compressed(p, status=str(e)[:200])
        return None
    u, v = np.full(LAT.size, np.nan), np.full(LAT.size, np.nan)
    for k, pt in enumerate(pts):
        h = pt.get("hourly") or {}
        if h.get("ocean_current_velocity") is None:
            continue
        i, j, w = _weights(h["time"], t)
        sp = np.array([np.nan if x is None else x for x in h["ocean_current_velocity"]], float) / 3.6
        dr = np.deg2rad(np.array([np.nan if x is None else x for x in h["ocean_current_direction"]], float))
        uu, vv = sp * np.sin(dr), sp * np.cos(dr)
        u[k], v[k] = (1 - w) * uu[i] + w * uu[j], (1 - w) * vv[i] + w * vv[j]
    if not np.isfinite(u).any():
        np.savez_compressed(p, status="no data")
        return None
    res = dict(lon=lons, lat=lats, u=u.reshape(LAT.shape), v=v.reshape(LAT.shape))
    np.savez_compressed(p, **res)
    return res


def to_grid(region, field_lon, field_lat, values, fill_nan_nearest=True):
    """Bilinear interpolation of a lon/lat field onto the region grid."""
    lon, lat, val = np.asarray(field_lon, float), np.asarray(field_lat, float), np.asarray(values, float)
    if lat[0] > lat[-1]:
        lat, val = lat[::-1], val[::-1]
    if fill_nan_nearest and np.isnan(val).any() and np.isfinite(val).any():
        idx = ndimage.distance_transform_edt(np.isnan(val), return_distances=False, return_indices=True)
        val = val[tuple(idx)]
    XX, YY = region.mesh()
    lo, la = region.to_ll.transform(XX, YY)
    return RegularGridInterpolator((lat, lon), val, bounds_error=False, fill_value=np.nan)((la, lo))
