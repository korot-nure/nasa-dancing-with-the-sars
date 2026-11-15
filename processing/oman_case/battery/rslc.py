"""M16 (sub-look / sub-aperture analysis) and M17 (Doppler anomaly) on NISAR RSLC.

Oman case, track 150 descending, frame 080 (window around Al-Qibliyah and the plume).

Notebook API (no side effects on import; reruns from cache without network):
    fetch_rslc_window(scene_id, bbox=WINDOW_BBOX, pol="HH", overwrite=False) -> Path
    load_window(scene_id, pol="HH") -> dict
    gcov_slick_mask(scene_id) -> dict(x, y, slick, sea, land, delta_db, g0_db)
    sublook_analysis(win, ...) -> dict          (M16, maps on a ~58 m radar grid + lon/lat)
    doppler_analysis(win, ...) -> dict          (M17, maps on a block grid + lon/lat)
    run_scene(scene_id, refresh=False) -> dict  (writes results/m16_m17_<scene_id>.npz, returns stats)
    run_all(scene_ids=None, refresh=False) -> dict (writes results/m16_m17_summary.json)
    plot_scene(scene_id) -> list[Path]          (results/figures/m16_<id>.png, m17_<id>.png)
    plot_summary(summary=None) -> Path          (results/figures/m16_m17_classes.png)

Physics notes
-------------
* RSLC pixels are calibrated so that |s|^2 = beta0 (LUT == 1); the noise-equivalent backscatter
  (NEB) in the product is in the same DN^2 units, so SNR = <|s|^2>/NEB - 1.
* NISAR RSLC is focused by time-domain backprojection to zero-Doppler geometry with a
  rectangular azimuth window of `processedAzimuthBandwidth` (~1262 Hz) centred on the
  geometric Doppler centroid LUT (~938 Hz here; output PRF 1520 Hz, so the band wraps).
* M16: the processed azimuth band is split into sub-looks. Two sub-looks separated by df Hz
  see the scene dt = df/|Ka| seconds apart (Ka = azimuth FM rate). For a stationary distributed
  target the expected coherence equals the spectral overlap; the sea decorrelates in time,
  rigid targets (ships, island, tanker) stay coherent. Thermal noise is a fixed realisation in
  the data, so in overlapping sub-bands it is *coherent* with coherence = overlap: low-SNR areas
  (oil) are biased towards the overlap value. `subcoh_t_*` maps are noise-corrected.
* M17: the lag-1 azimuth autocorrelation phase gives the spectral centroid of the focused data.
  Its departure from the geometric LUT is antenna mis-pointing (smooth) + geophysical Doppler
  (surface motion: currents, wind drift, wave orbital motion). Noise has its centroid exactly at
  the LUT and dilutes the measured shift; the estimate is corrected per block with the SNR and
  the measured / theoretical lag-1 correlation magnitudes. A smooth 2-D polynomial fitted over
  clean sea removes mis-pointing; the residual is the Doppler anomaly. LOS velocity = lambda*f/2
  (positive = towards the radar).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

try:  # package import (notebook) or plain script import
    from . import config
except ImportError:  # pragma: no cover
    import config  # type: ignore

C_LIGHT = 299_792_458.0

RSLC_SCENES = {
    "HH_0624": "NISAR_L1_PR_RSLC_023_150_D_080_2005_DHDH_A_20260624T144949_20260624T145011_P05023_N_P_J_001",
    "HH_0811": "NISAR_L1_PR_RSLC_027_150_D_080_2005_DHDH_A_20260811T144946_20260811T145009_P05023_N_P_J_001",
    "HH_0904": "NISAR_L1_PR_RSLC_029_150_D_080_2005_DHDH_A_20260904T144946_20260904T145008_P05023_N_P_J_001",
}
# lon0, lat0, lon1, lat1: island + plume + clean sea (kept < ~350 MB of complex64 per scene)
WINDOW_BBOX = (56.28, 17.43, 56.72, 17.80)

# multilook / decimation of the M16 output grid (az x rg samples): 13 x 6 ~ 58 m x 57 m
ML_DEC = (13, 6)
# coherence estimation window (az x rg samples): 39 x 18 ~ 174 m x 170 m, ~700 samples
COH_WIN = (39, 18)
# small window for point targets (ships, tanker): 7 x 5 samples ~ 31 m x 47 m, max-pooled to the output grid
PT_WIN = (7, 5)


# ----------------------------------------------------------------------------- I/O
def _granule_url(name: str) -> str:
    level = "L2" if "_L2_" in name else "L1"
    ptype = name.split("_")[3]
    crid = [p for p in name.split("_") if p.startswith("P0")][0]
    maturity = "PROVISIONAL_V1" if crid == "P05023" else "V1"
    return (f"https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_{level}_{ptype}_{maturity}/"
            f"{name}/{name}.h5")


def _open_remote(name: str):
    """Open a remote NISAR granule (credentials from ~/.netrc). Signed URLs are never printed."""
    import fsspec
    import h5py
    import requests

    sess = requests.Session()
    r = sess.get(_granule_url(name), headers={"Range": "bytes=0-0"}, allow_redirects=True,
                 timeout=120, stream=True)
    r.close()
    if r.status_code not in (200, 206):
        raise RuntimeError(f"access failed: HTTP {r.status_code} for {name}")
    fobj = fsspec.filesystem("http").open(r.url, mode="rb", block_size=8 * 2**20, cache_type="blockcache")
    return h5py.File(fobj, "r")


def _cache_path(scene_id: str, pol: str = "HH") -> Path:
    return Path(config.RSLC_CACHE) / f"{scene_id}_{pol}_window.npz"


def fetch_rslc_window(scene_id: str, bbox=WINDOW_BBOX, pol: str = "HH", overwrite: bool = False) -> Path:
    """Read the radar-geometry window covering `bbox` from the remote RSLC and cache it as .npz."""
    out = _cache_path(scene_id, pol)
    if out.exists() and not overwrite:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    name = RSLC_SCENES[scene_id]
    f = _open_remote(name)
    r = f["science/LSAR/RSLC"]
    sw = r["swaths"]
    fa = sw["frequencyA"]
    zdt = sw["zeroDopplerTime"][:]
    srg = fa["slantRange"][:]
    prf = 1.0 / float(sw["zeroDopplerTimeSpacing"][()])
    az_bw = float(fa["processedAzimuthBandwidth"][()])
    fc = float(fa["processedCenterFrequency"][()])
    at_spacing = float(fa["sceneCenterAlongTrackSpacing"][()])
    gr_spacing = float(fa["sceneCenterGroundRangeSpacing"][()])
    sr_spacing = float(fa["slantRangeSpacing"][()])
    rg_bw = float(fa["processedRangeBandwidth"][()])

    g = r["metadata/geolocationGrid"]
    h = g["heightAboveEllipsoid"][:]
    k = int(np.argmin(np.abs(h)))
    gx, gy = g["coordinateX"][k], g["coordinateY"][k]
    ginc = g["incidenceAngle"][k]
    gt, gr = g["zeroDopplerTime"][:], g["slantRange"][:]
    m = (gx >= bbox[0]) & (gx <= bbox[2]) & (gy >= bbox[1]) & (gy <= bbox[3])
    if not m.any():
        raise RuntimeError(f"{scene_id}: bbox outside RSLC footprint")
    ii, jj = np.nonzero(m)
    a0 = int(np.searchsorted(zdt, gt[ii.min()]))
    a1 = int(np.searchsorted(zdt, gt[ii.max()]))
    r0 = int(np.searchsorted(srg, gr[jj.min()]))
    r1 = int(np.searchsorted(srg, gr[jj.max()]))
    a0, r0 = max(a0, 0), max(r0, 0)
    a1, r1 = min(a1, len(zdt)), min(r1, len(srg))
    # trim to multiples of the decimation factors
    a1 = a0 + (a1 - a0) // ML_DEC[0] * ML_DEC[0]
    r1 = r0 + (r1 - r0) // ML_DEC[1] * ML_DEC[1]
    slc = fa[pol][a0:a1, r0:r1].astype(np.complex64)

    # coarse metadata subsets (with one-cell margin) for interpolation
    gi0, gi1 = max(ii.min() - 2, 0), min(ii.max() + 3, len(gt))
    gj0, gj1 = max(jj.min() - 2, 0), min(jj.max() + 3, len(gr))
    dcg = r["metadata/processingInformation/parameters/frequencyA"]
    neb = r[f"metadata/calibrationInformation/frequencyA/noiseEquivalentBackscatter/{pol}"]
    vel = r["metadata/orbit/velocity"][:]
    np.savez(
        out,
        slc=slc,
        az_time=zdt[a0:a1], slant_range=srg[r0:r1],
        prf=prf, az_bw=az_bw, wavelength=C_LIGHT / fc, rg_bw=rg_bw,
        at_spacing=at_spacing, gr_spacing=gr_spacing, sr_spacing=sr_spacing,
        sat_speed=float(np.median(np.linalg.norm(vel, axis=1))),
        geo_t=gt[gi0:gi1], geo_r=gr[gj0:gj1],
        geo_lon=gx[gi0:gi1, gj0:gj1], geo_lat=gy[gi0:gi1, gj0:gj1], geo_inc=ginc[gi0:gi1, gj0:gj1],
        dc_t=dcg["zeroDopplerTime"][:], dc_r=dcg["slantRange"][:], dc=dcg["dopplerCentroid"][:],
        neb_t=neb.parent["zeroDopplerTime"][:], neb_r=neb.parent["slantRange"][:], neb=neb[:].astype(np.float64),
        rows=np.array([a0, a1]), cols=np.array([r0, r1]), granule=np.array(name), bbox=np.array(bbox),
    )
    f.close()
    return out


def load_window(scene_id: str, pol: str = "HH") -> dict:
    p = _cache_path(scene_id, pol)
    if not p.exists():
        fetch_rslc_window(scene_id, pol=pol)
    d = np.load(p, allow_pickle=False)
    win = {k: d[k] for k in d.files}
    for k in ("prf", "az_bw", "wavelength", "rg_bw", "at_spacing", "gr_spacing", "sr_spacing", "sat_speed"):
        win[k] = float(win[k])
    win["granule"] = str(win["granule"])
    win["scene_id"] = scene_id
    return win


# ----------------------------------------------------------------------------- helpers
def _interp2(t_axis, r_axis, grid, tq, rq):
    """Bilinear interpolation of a (t, r) LUT at query points (tq, rq) (broadcast arrays)."""
    from scipy.interpolate import RegularGridInterpolator

    ta, ga = (t_axis, grid) if t_axis[0] < t_axis[-1] else (t_axis[::-1], grid[::-1])
    it = RegularGridInterpolator((ta, r_axis), ga, bounds_error=False, fill_value=None)
    tq, rq = np.broadcast_arrays(tq, rq)
    return it(np.stack([tq.ravel(), rq.ravel()], -1)).reshape(tq.shape)


def look_geometry(win: dict) -> dict:
    """Horizontal look direction (sensor -> ground) and ground-track heading at the window centre."""
    from pyproj import Geod

    g = Geod(ellps="WGS84")
    lon, lat = win["geo_lon"], win["geo_lat"]
    i, j = lon.shape[0] // 2, lon.shape[1] // 2
    look, _, _ = g.inv(lon[i, j], lat[i, j], lon[i, j + 1], lat[i, j + 1])
    head, _, _ = g.inv(lon[i, j], lat[i, j], lon[i + 1, j], lat[i + 1, j])
    return dict(look_azimuth_deg=float(look % 360), heading_deg=float(head % 360))


# ERA5 10-m wind at the island at acquisition time (Open-Meteo archive, used in the main analysis)
ERA5_WIND = {"HH_0624": (11.3, 212), "HH_0811": (11.3, 217), "HH_0904": (6.8, 176)}  # (m/s, from deg)


def _wrap(f, prf):
    return (f + prf / 2) % prf - prf / 2


def _lonlat(win, tq, rq):
    lon = _interp2(win["geo_t"], win["geo_r"], win["geo_lon"], tq, rq)
    lat = _interp2(win["geo_t"], win["geo_r"], win["geo_lat"], tq, rq)
    inc = _interp2(win["geo_t"], win["geo_r"], win["geo_inc"], tq, rq)
    return lon, lat, inc


def _neb_cols(win):
    """Noise-equivalent beta0 per window column (mean over the NEB time samples)."""
    neb = np.nanmean(win["neb"], axis=0)
    return np.interp(win["slant_range"], win["neb_r"], neb)


def _dc_cols(win):
    """Geometric Doppler centroid (Hz, baseband) per column at the window centre time."""
    tmid = float(np.mean(win["az_time"]))
    dc = _interp2(win["dc_t"], win["dc_r"], win["dc"], np.full(win["slant_range"].shape, tmid), win["slant_range"])
    return dc


def _fm_rate(win):
    """Azimuth FM rate |Ka| (Hz/s) at the window centre: 2 v_eff^2 / (lambda R)."""
    v_s = win["sat_speed"]
    v_g = win["at_spacing"] * win["prf"]
    v_eff2 = v_s * v_g
    R = float(np.mean(win["slant_range"]))
    return 2 * v_eff2 / (win["wavelength"] * R)


def _boxsum(a, w):
    from scipy import ndimage

    if np.iscomplexobj(a):
        return ndimage.uniform_filter(a.real, w, mode="nearest") + 1j * ndimage.uniform_filter(a.imag, w, mode="nearest")
    return ndimage.uniform_filter(a, w, mode="nearest")


# ----------------------------------------------------------------------------- M16
# sub-look definitions relative to the Doppler centroid, in units of the processed band B:
# (start, width) with start measured from -B/2
SUBLOOKS = {"A": (0.0, 0.5), "B": (0.5, 0.5), "C": (0.25, 0.5), "D": (0.125, 0.5)}
PAIRS = {"half": ("A", "B"), "q25": ("A", "C"), "q125": ("A", "D")}  # shift 0.5B, 0.25B, 0.125B


def sublook_analysis(win: dict, ml_dec=ML_DEC, coh_win=COH_WIN, col_chunk: int = 504) -> dict:
    """M16: sub-look coherence (raw and noise-corrected) and sub-look intensity ratio.

    Returns maps on the decimated radar grid (rows = az / ml_dec[0], cols = rg / ml_dec[1]) with
    lon, lat, incidence, beta0 (multilooked), snr, and per-pair raw / corrected coherences.
    """
    slc = win["slc"]
    na, nr = slc.shape
    prf, B = win["prf"], win["az_bw"]
    dca = _dc_cols(win)
    neb = _neb_cols(win)
    freqs = np.fft.fftfreq(na, d=1.0 / prf)
    nbins = 240
    spec_u = np.linspace(-prf / 2, prf / 2, nbins + 1)
    spec_acc = np.zeros(nbins)
    spec_cnt = np.zeros(nbins)

    dA, dR = ml_dec
    oa, orr = na // dA, nr // dR
    out = {k: np.full((oa, orr), np.nan, np.float32) for k in
           ["beta0", "snr", "subint_ratio_db", "coh_half_pt"] + [f"coh_{p}" for p in PAIRS]}
    looks_int = {k: np.full((oa, orr), np.nan, np.float32) for k in SUBLOOKS}
    margin = int(np.ceil(coh_win[1] / dR)) * dR
    col_chunk = max(dR, col_chunk // dR * dR)
    valid_full = np.abs(slc) > 0
    for c0 in range(0, nr, col_chunk):
        c1 = min(nr, c0 + col_chunk)
        e0, e1 = max(0, c0 - margin), min(nr, c1 + margin)
        blk = slc[:, e0:e1]
        S = np.fft.fft(blk, axis=0)
        u = _wrap(freqs[:, None] - dca[None, e0:e1], prf)  # frequency relative to the centroid
        # scene-average spectrum (own columns only), used for reference coherence and window gain
        own = slice(c0 - e0, c0 - e0 + (c1 - c0))
        P = (np.abs(S[:, own]) ** 2) / na
        idx = np.clip(np.digitize(u[:, own], spec_u) - 1, 0, nbins - 1).ravel()
        spec_acc += np.bincount(idx, weights=P.ravel(), minlength=nbins)
        spec_cnt += np.bincount(idx, minlength=nbins)
        looks = {}
        for name, (st, wd) in SUBLOOKS.items():
            lo = -B / 2 + st * B
            hi = lo + wd * B
            M = (u >= lo) & (u < hi)
            looks[name] = np.fft.ifft(S * M, axis=0).astype(np.complex64)
        sl = slice(c0 - e0, c0 - e0 + (c1 - c0))
        vmask = valid_full[:, e0:e1].astype(np.float32)
        # multilooked beta0 and SNR
        I = _boxsum((np.abs(blk) ** 2).astype(np.float32), ml_dec)[:, sl]
        cnt = _boxsum(vmask, ml_dec)[:, sl]
        I = np.where(cnt > 0.5, I / np.maximum(cnt, 1e-6), np.nan)
        rows = np.arange(dA // 2, oa * dA, dA)
        cols_local = np.arange(dR // 2, c1 - c0, dR)
        ocols = (c0 + cols_local) // dR
        out["beta0"][:, ocols] = I[np.ix_(rows, cols_local)]
        nebc = neb[c0:c1][cols_local]
        out["snr"][:, ocols] = np.maximum(I[np.ix_(rows, cols_local)] / nebc[None, :] - 1.0, 1e-3)
        # sub-look intensities (multilooked)
        for name, L in looks.items():
            Li = _boxsum((np.abs(L) ** 2).astype(np.float32), ml_dec)[:, sl]
            looks_int[name][:, ocols] = Li[np.ix_(rows, cols_local)]
        # point-target coherence of the non-overlapping halves (small window, max over each output cell)
        from scipy import ndimage as _ndi
        num = _boxsum(looks["A"] * np.conj(looks["B"]), PT_WIN)[:, sl]
        den = np.sqrt(_boxsum(np.abs(looks["A"]) ** 2, PT_WIN)[:, sl] * _boxsum(np.abs(looks["B"]) ** 2, PT_WIN)[:, sl])
        cpt = _ndi.maximum_filter(np.abs(num) / np.maximum(den, 1e-20), size=ml_dec)
        out["coh_half_pt"][:, ocols] = cpt[np.ix_(rows, cols_local)]
        # coherences
        for pname, (a, b) in PAIRS.items():
            num = _boxsum(looks[a] * np.conj(looks[b]), coh_win)[:, sl]
            den = np.sqrt(_boxsum(np.abs(looks[a]) ** 2, coh_win)[:, sl] * _boxsum(np.abs(looks[b]) ** 2, coh_win)[:, sl])
            coh = np.abs(num) / np.maximum(den, 1e-20)
            out[f"coh_{pname}"][:, ocols] = coh[np.ix_(rows, cols_local)]

    # intensity ratio of the two non-overlapping halves, normalised by the window median
    with np.errstate(divide="ignore", invalid="ignore"):
        r = 10 * np.log10(looks_int["A"] / looks_int["B"])
    out["subint_ratio_db"] = (r - np.nanmedian(r)).astype(np.float32)

    # reference coherences: stationary signal (from the average spectrum minus flat noise) and noise
    spec = spec_acc / np.maximum(spec_cnt, 1)
    uc = 0.5 * (spec_u[1:] + spec_u[:-1])
    inb = np.abs(uc) <= B / 2
    noise_level = np.nanmedian(neb) * (prf / B)  # flat in-band noise power per bin (|S|^2/N units)
    sig = np.clip(spec - noise_level * inb, 0, None)

    def band(st, wd):
        lo = -B / 2 + st * B
        return (uc >= lo) & (uc < lo + wd * B)

    ka = _fm_rate(win)
    refs = {}
    for pname, (a, b) in PAIRS.items():
        ma, mb = band(*SUBLOOKS[a]), band(*SUBLOOKS[b])
        ov = ma & mb
        g_sig = sig[ov].sum() / np.sqrt(sig[ma].sum() * sig[mb].sum())
        g_noise = ov.sum() / np.sqrt(ma.sum() * mb.sum())
        shift_hz = (SUBLOOKS[b][0] - SUBLOOKS[a][0]) * B
        refs[pname] = dict(g_sig=float(g_sig), g_noise=float(g_noise), dt_s=float(shift_hz / ka), df_hz=float(shift_hz))
        snr = out["snr"]
        g_t = (out[f"coh_{pname}"] * (snr + 1) - g_noise) / np.maximum(snr * g_sig, 1e-6)
        out[f"cohT_{pname}"] = np.clip(g_t, -0.5, 1.5).astype(np.float32)

    rows = np.arange(dA // 2, oa * dA, dA)
    cols = np.arange(dR // 2, orr * dR, dR)
    tq = win["az_time"][rows][:, None]
    rq = win["slant_range"][cols][None, :]
    lon, lat, inc = _lonlat(win, tq, rq)
    out.update(lon=lon.astype(np.float64), lat=lat.astype(np.float64), inc=inc.astype(np.float32),
               refs=refs, fm_rate=float(ka), spectrum_u=uc, spectrum=spec, noise_level=float(noise_level))
    return out


# ----------------------------------------------------------------------------- M17
def doppler_analysis(win: dict, tile=(32, 32), block_tiles=(16, 16), step_tiles=(4, 4),
                     poly_order: int = 2, exclude_mask_fn=None, bright_k: float = 20.0) -> dict:
    """M17: Doppler centroid per block (lag-1 azimuth autocorrelation), noise-corrected anomaly.

    Blocks are block_tiles * tile samples (default 512 x 512 ~ 2.3 km az x 4.8 km ground range),
    computed every step_tiles * tile samples. `exclude_mask_fn(lon, lat) -> bool array` marks
    blocks to exclude from the mis-pointing trend fit (slick / bright targets). Single-look samples
    brighter than `bright_k` x the column median (~ +13 dB; sea false-alarm probability ~1e-9) are
    zeroed with a 3-sample dilation before the sums.
    """
    slc = win["slc"]
    na, nr = slc.shape
    ta, tr = tile
    nta, ntr = (na - 1) // ta, nr // tr
    prf, B, lam = win["prf"], win["az_bw"], win["wavelength"]
    # tile sums of lag-1 product and power (computed in column chunks to save memory)
    R1 = np.zeros((nta, ntr), np.complex128)
    R0 = np.zeros((nta, ntr))
    NV = np.zeros((nta, ntr))
    from scipy import ndimage

    for c0 in range(0, ntr * tr, 64 * tr):
        c1 = min(ntr * tr, c0 + 64 * tr)
        s = slc[: nta * ta + 1, c0:c1].copy()
        # remove bright point targets (ships, tanker, island): their own Doppler (moving ships,
        # stationary land) would dominate a block; > bright_k x column median of |s|^2, dilated
        pw = np.abs(s) ** 2
        med = np.nanmedian(np.where(pw > 0, pw, np.nan), axis=0, keepdims=True)
        bright = ndimage.binary_dilation(pw > bright_k * med, iterations=3)
        s[bright] = 0
        p1 = s[1:] * np.conj(s[:-1])
        p0 = (np.abs(s[:-1]) ** 2).astype(np.float64)
        v = ((np.abs(s[1:]) > 0) & (np.abs(s[:-1]) > 0)).astype(np.float64)
        sh = (nta, ta, (c1 - c0) // tr, tr)
        R1[:, c0 // tr:c1 // tr] = p1.reshape(sh).sum(axis=(1, 3))
        R0[:, c0 // tr:c1 // tr] = p0.reshape(sh).sum(axis=(1, 3))
        NV[:, c0 // tr:c1 // tr] = v.reshape(sh).sum(axis=(1, 3))
    ba, br = block_tiles
    sa, sr = step_tiles
    ia = np.arange(0, nta - ba + 1, sa)
    ir = np.arange(0, ntr - br + 1, sr)
    cs = lambda a: np.pad(a.cumsum(0).cumsum(1), ((1, 0), (1, 0)))  # noqa: E731
    C1, C0, CV = cs(R1), cs(R0), cs(NV)

    def bsum(Cm):
        return Cm[ia[:, None] + ba, ir[None, :] + br] - Cm[ia[:, None], ir[None, :] + br] \
            - Cm[ia[:, None] + ba, ir[None, :]] + Cm[ia[:, None], ir[None, :]]

    S1, S0, SV = bsum(C1), bsum(C0), bsum(CV)
    frac_valid = SV / (ba * ta * br * tr)
    rho = np.abs(S1) / np.maximum(S0, 1e-20)
    f_meas = prf / (2 * np.pi) * np.angle(S1)
    # block centres
    rows_c = (ia + ba / 2) * ta
    cols_c = (ir + br / 2) * tr
    tq = np.interp(rows_c, np.arange(na), win["az_time"])[:, None]
    rq = np.interp(cols_c, np.arange(nr), win["slant_range"])[None, :]
    f_lut = _wrap(_interp2(win["dc_t"], win["dc_r"], win["dc"], tq, rq), prf)
    df_raw = _wrap(f_meas - f_lut, prf)
    # SNR per block
    neb_c = np.interp(np.broadcast_to(rq, df_raw.shape), win["neb_r"], np.nanmean(win["neb"], axis=0))
    mean_pow = S0 / np.maximum(SV, 1)
    snr = np.maximum(mean_pow / neb_c - 1.0, 1e-3)
    # noise dilution correction: noise spectrum = flat band B centred on the LUT
    rho_n = abs(np.sinc(B / prf))
    rho_s = np.clip((rho * (snr + 1) - rho_n) / snr, 1e-3, 1.0)
    w = snr * rho_s / (snr * rho_s + rho_n)
    df_corr = df_raw / w
    lon, lat, inc = _lonlat(win, tq, rq)
    lon, lat, inc = np.broadcast_to(lon, df_raw.shape), np.broadcast_to(lat, df_raw.shape), np.broadcast_to(inc, df_raw.shape)
    good = (frac_valid > 0.8) & np.isfinite(df_corr)
    fit_mask = good.copy()
    if exclude_mask_fn is not None:
        fit_mask &= ~exclude_mask_fn(lon, lat)

    # smooth mis-pointing trend (robust 2-D polynomial in normalised row/col)
    yy = (np.broadcast_to(rows_c[:, None], df_raw.shape) / na) * 2 - 1
    xx = (np.broadcast_to(cols_c[None, :], df_raw.shape) / nr) * 2 - 1
    terms = [np.ones_like(xx)]
    for o in range(1, poly_order + 1):
        for i in range(o + 1):
            terms.append(xx ** (o - i) * yy ** i)
    Amat = np.stack([t[fit_mask] for t in terms], -1)

    def fit(z):
        zz = z[fit_mask]
        keep = np.ones(zz.size, bool)
        coef = None
        for _ in range(5):
            coef, *_ = np.linalg.lstsq(Amat[keep], zz[keep], rcond=None)
            res = zz - Amat @ coef
            s = 1.4826 * np.median(np.abs(res[keep] - np.median(res[keep])))
            keep = np.abs(res) < 3 * max(s, 1e-6)
        return sum(c * t for c, t in zip(coef, terms))

    trend_raw, trend_corr = fit(df_raw), fit(df_corr)
    anom_raw = np.where(good, df_raw - trend_raw, np.nan)
    anom = np.where(good, df_corr - trend_corr, np.nan)
    sin_inc = np.sin(np.deg2rad(inc))
    los = lam * anom / 2.0  # m/s, positive towards the radar
    # theoretical precision of the lag-1 phase (per block), N_eff = samples / oversampling
    n_eff = (ba * ta * br * tr) / ((prf / B) * (C_LIGHT / (2 * win["rg_bw"]) / win["sr_spacing"]))
    sig_phi = np.sqrt((1 - rho ** 2) / (2 * n_eff * np.maximum(rho, 1e-3) ** 2))
    sig_f = prf / (2 * np.pi) * sig_phi / w
    return dict(lon=lon, lat=lat, inc=inc, rows=rows_c, cols=cols_c, f_meas=f_meas, f_lut=f_lut,
                df_raw=df_raw, df_corr=df_corr, trend=trend_corr, anom_raw=anom_raw, anom=anom,
                los=los, hvel=los / sin_inc, rho=rho, rho_s=rho_s, rho_n=rho_n, snr=snr, w=w,
                sigma_f_theory=sig_f, good=good, fit_mask=fit_mask,
                block_m=(ba * ta * win["at_spacing"], br * tr * win["gr_spacing"]))


def doppler_window_gain(spectrum_u, spectrum, noise_level, B, prf, delta: float = 10.0) -> float:
    """d(measured centroid) / d(true Doppler shift) for the signal spectrum moving inside the fixed
    rectangular processing window (the window does not follow the geophysical Doppler)."""
    u = np.asarray(spectrum_u, float)
    W = (np.abs(u) <= B / 2).astype(float)
    sig = np.clip(np.asarray(spectrum, float) - noise_level * W, 0, None)

    def centroid(d):
        s = np.interp(u - d, u, sig, left=0, right=0) * W
        return prf / (2 * np.pi) * np.angle(np.sum(s * np.exp(2j * np.pi * u / prf)))

    return float((centroid(delta) - centroid(-delta)) / (2 * delta))


# ----------------------------------------------------------------------------- GCOV slick mask
def _scene_cfg(scene_id):
    return next(s for s in config.SCENES if s["id"] == scene_id)


def _land_mask(xs, ys, res):
    from matplotlib.path import Path as MPath
    from matplotlib.transforms import Bbox
    from PIL import Image, ImageDraw
    from pyproj import Transformer
    from scipy import ndimage
    import shapefile

    to_ll = Transformer.from_crs(config.EPSG, 4326, always_xy=True)
    to_utm = Transformer.from_crs(4326, config.EPSG, always_xy=True)
    lo, la = to_ll.transform([xs[0], xs[-1], xs[0], xs[-1]], [ys[0], ys[0], ys[-1], ys[-1]])
    lon0, lon1, lat0, lat1 = min(lo), max(lo), min(la), max(la)
    canvas = Image.new("1", (len(xs), len(ys)), 0)
    draw = ImageDraw.Draw(canvas)
    clip = Bbox([[lon0 - 0.3, lat0 - 0.3], [lon1 + 0.3, lat1 + 0.3]])
    for shp in shapefile.Reader(str(config.LAND_SHP)).shapes():
        b = shp.bbox
        if b[2] < lon0 - 0.5 or b[0] > lon1 + 0.5 or b[3] < lat0 - 0.5 or b[1] > lat1 + 0.5:
            continue
        parts = list(shp.parts) + [len(shp.points)]
        for a, e in zip(parts[:-1], parts[1:]):
            clipped = MPath(np.array(shp.points[a:e])).clip_to_bbox(clip, inside=True)
            clipped.should_simplify = False   # paths >= 128 vertices are otherwise simplified in degree units (~0.1 deg)
            for poly in clipped.to_polygons():
                if len(poly) < 3:
                    continue
                px, py = to_utm.transform(poly[:, 0], poly[:, 1])
                cols = (np.asarray(px) - xs[0]) / (xs[1] - xs[0])
                rows = (np.asarray(py) - ys[0]) / (ys[1] - ys[0])
                draw.polygon(list(zip(cols.tolist(), rows.tolist())), fill=1)
    land = np.array(canvas, dtype=bool)
    return ndimage.binary_dilation(land, iterations=max(1, int(1000 / res)))


def gcov_slick_mask(scene_id: str, thr_db: float = 0.8, smooth_px: int = 5, min_km2: float = 2.0,
                    block_m: float = 20000) -> dict:
    """Same rule as the main calibrated analysis (gamma0 HH, 60 m grid of the island_hh cut-outs)."""
    from scipy import ndimage

    sc = _scene_cfg(scene_id)
    ds = [np.load(Path(config.CUTOUTS) / fn) for fn in sc["files"]]
    x, y = ds[0]["x"], ds[0]["y"]
    g0 = np.full((len(y), len(x)), np.nan, np.float32)
    for d in ds:
        if not (np.allclose(d["x"], x) and np.allclose(d["y"], y)):
            raise RuntimeError("cut-out grids differ; expected identical island_hh grids")
        a = d[sc["pol"]]
        m = np.isfinite(a)
        g0[m] = a[m]
    res = float(abs(x[1] - x[0]))
    land = _land_mask(x, y, res)
    co = np.where(land, np.nan, g0)
    edge = ndimage.binary_erosion(np.isfinite(co), iterations=max(1, int(600 / res)))
    co[~edge] = np.nan
    m = np.isfinite(co)
    s = ndimage.uniform_filter(np.where(m, co, 0), smooth_px)
    c = ndimage.uniform_filter(m.astype(float), smooth_px)
    s = np.where((c > 0.5) & m, s / np.maximum(c, 1e-9), np.nan)
    Bk = max(4, int(block_m / res))
    ny, nx = int(np.ceil(s.shape[0] / Bk)), int(np.ceil(s.shape[1] / Bk))
    med = np.full((ny, nx), np.nan)
    for i in range(ny):
        for j in range(nx):
            blk = s[i * Bk:(i + 1) * Bk, j * Bk:(j + 1) * Bk]
            blk = blk[np.isfinite(blk)]
            if blk.size > 0.15 * Bk * Bk:
                med[i, j] = np.median(blk)
    idx = ndimage.distance_transform_edt(np.isnan(med), return_distances=False, return_indices=True)
    med = med[tuple(idx)]
    bg = np.exp(ndimage.zoom(np.log(med), (s.shape[0] / ny, s.shape[1] / nx), order=1)[: s.shape[0], : s.shape[1]])
    with np.errstate(divide="ignore", invalid="ignore"):
        delta = 10 * np.log10(s) - 10 * np.log10(bg)
    dark = ndimage.binary_opening((delta < -thr_db) & np.isfinite(delta), iterations=1)
    lab, n = ndimage.label(dark)
    px_km2 = (res / 1000) ** 2
    sizes = ndimage.sum(dark, lab, range(1, n + 1)) * px_km2
    slick = np.isin(lab, np.nonzero(sizes >= min_km2)[0] + 1)
    sea = np.isfinite(delta)
    with np.errstate(divide="ignore", invalid="ignore"):
        g0_db = 10 * np.log10(g0)
    return dict(x=x, y=y, slick=slick, sea=sea, land=land, delta_db=delta.astype(np.float32),
                g0_db=g0_db.astype(np.float32))


# ----------------------------------------------------------------------------- resampling
def _to_utm(lon, lat):
    from pyproj import Transformer

    tr = Transformer.from_crs(4326, config.EPSG, always_xy=True)
    return tr.transform(lon, lat)


def to_grid(lon, lat, values, x, y, method: str = "linear"):
    """Resample scattered (lon, lat) values onto the UTM grid (x, y) of the cut-outs."""
    from scipy.interpolate import griddata

    ex, ey = _to_utm(np.ravel(lon), np.ravel(lat))
    v = np.ravel(values)
    ok = np.isfinite(v) & np.isfinite(ex) & np.isfinite(ey)
    XX, YY = np.meshgrid(x, y)
    # restrict to the bounding box of the data to save time
    out = np.full(XX.shape, np.nan, np.float32)
    bx = (XX >= ex[ok].min()) & (XX <= ex[ok].max()) & (YY >= ey[ok].min()) & (YY <= ey[ok].max())
    out[bx] = griddata((ex[ok], ey[ok]), v[ok], (XX[bx], YY[bx]), method=method)
    return out


def _grid_lookup(mask_grid, x, y, lon, lat):
    """Nearest-pixel lookup of a UTM-grid boolean mask at (lon, lat) points."""
    ex, ey = _to_utm(np.asarray(lon), np.asarray(lat))
    ci = np.rint((ex - x[0]) / (x[1] - x[0])).astype(int)
    ri = np.rint((ey - y[0]) / (y[1] - y[0])).astype(int)
    ok = (ci >= 0) & (ci < len(x)) & (ri >= 0) & (ri < len(y))
    out = np.zeros(np.shape(lon), bool)
    out[ok] = mask_grid[ri[ok], ci[ok]]
    return out


# ----------------------------------------------------------------------------- driver
def _stats(v, m):
    v = v[m & np.isfinite(v)]
    if v.size == 0:
        return None
    q = np.percentile(v, [25, 50, 75])
    return dict(n=int(v.size), median=float(q[1]), iqr=[float(q[0]), float(q[2])], mean=float(v.mean()),
                std=float(v.std()))


def _cohen_auc(va, vb):
    va, vb = va[np.isfinite(va)], vb[np.isfinite(vb)]
    if va.size < 5 or vb.size < 5:
        return None
    sp = np.sqrt(0.5 * (va.var() + vb.var()))
    d = float((vb.mean() - va.mean()) / sp) if sp > 0 else None
    # AUC via ranks (subsample for speed)
    rng = np.random.default_rng(0)
    va = rng.choice(va, min(va.size, 20000), replace=False)
    vb = rng.choice(vb, min(vb.size, 20000), replace=False)
    allv = np.concatenate([va, vb])
    ranks = allv.argsort().argsort().astype(float) + 1
    auc = float((ranks[va.size:].sum() - vb.size * (vb.size + 1) / 2) / (va.size * vb.size))
    return dict(cohen_d=d, auc=auc)


def run_scene(scene_id: str, refresh: bool = False) -> dict:
    """Compute M16 + M17 for one scene, save results/m16_m17_<scene_id>.npz, return statistics."""
    from scipy import ndimage

    res_dir = Path(config.RESULTS)
    res_dir.mkdir(parents=True, exist_ok=True)
    out_npz = res_dir / f"m16_m17_{scene_id}.npz"
    win = load_window(scene_id)
    gm = gcov_slick_mask(scene_id)
    x, y = gm["x"], gm["y"]
    slick_buf = ndimage.binary_dilation(gm["slick"], iterations=8)  # ~0.5 km guard

    sub = sublook_analysis(win)
    # classes on the M16 radar grid
    is_slick = _grid_lookup(gm["slick"], x, y, sub["lon"], sub["lat"])
    near_slick = _grid_lookup(slick_buf, x, y, sub["lon"], sub["lat"])
    is_sea = _grid_lookup(gm["sea"], x, y, sub["lon"], sub["lat"]) & ~near_slick
    b0db = 10 * np.log10(sub["beta0"])
    sea_med = np.nanmedian(b0db[is_sea]) if is_sea.any() else np.nanmedian(b0db)
    is_bright = b0db > sea_med + 10
    is_slick &= ~is_bright
    is_sea &= ~is_bright

    def excl(lon, lat):
        return _grid_lookup(slick_buf, x, y, lon, lat)

    dop = doppler_analysis(win, exclude_mask_fn=excl)
    gain = doppler_window_gain(sub["spectrum_u"], sub["spectrum"], sub["noise_level"], win["az_bw"], win["prf"])
    dop["anom_geo"] = dop["anom"] / gain
    dop["los"] = win["wavelength"] * dop["anom_geo"] / 2.0
    dop["hvel"] = dop["los"] / np.sin(np.deg2rad(dop["inc"]))
    d_slick = _grid_lookup(gm["slick"], x, y, dop["lon"], dop["lat"])
    # block-level slick fraction: resample slick mask to blocks via lookup at block centre and its neighbours
    d_sea = dop["good"] & ~_grid_lookup(slick_buf, x, y, dop["lon"], dop["lat"])

    geom = look_geometry(win)
    ws, wd = ERA5_WIND.get(scene_id, (np.nan, np.nan))
    comp = float(np.cos(np.deg2rad((wd + 180) % 360 - geom["look_azimuth_deg"])))
    stats = {"scene_id": scene_id, "granule": win["granule"], "window_shape": list(win["slc"].shape),
             "fm_rate_hz_s": sub["fm_rate"], "sublook_refs": sub["refs"], "geometry": geom,
             "era5_wind": dict(speed_ms=ws, from_deg=wd, component_along_look=comp,
                               expected_slick_anomaly_sign=("+" if comp > 0 else "-"))}
    m16 = {}
    for k in ["coh_half", "coh_half_pt", "coh_q25", "coh_q125", "cohT_q25", "cohT_q125", "subint_ratio_db", "snr"]:
        v = sub[k]
        m16[k] = {c: _stats(v, mk) for c, mk in (("sea", is_sea), ("slick", is_slick), ("bright", is_bright))}
        m16[k]["slick_vs_sea"] = _cohen_auc(v[is_sea], v[is_slick])
        m16[k]["bright_vs_sea"] = _cohen_auc(v[is_sea], v[is_bright])
    stats["m16"] = m16
    m17 = {}
    for k in ["anom_geo", "anom", "anom_raw", "los", "hvel", "snr", "rho"]:
        v = dop[k]
        m17[k] = {c: _stats(np.asarray(v), mk) for c, mk in (("sea", d_sea), ("slick", d_slick & dop["good"]))}
        m17[k]["slick_vs_sea"] = _cohen_auc(np.asarray(v)[d_sea], np.asarray(v)[d_slick & dop["good"]])
    # precision: theoretical median, and empirical std over sea using non-overlapping blocks
    step = 4  # block_tiles / step_tiles -> every 4th block is non-overlapping
    nov = np.zeros_like(dop["good"])
    nov[::step, ::step] = True
    sea_nov = d_sea & nov
    if sea_nov.sum() > 5:
        v = dop["anom_geo"][sea_nov]
        v = v[np.isfinite(v)]
        emp = float(1.4826 * np.median(np.abs(v - np.median(v))))
    else:
        emp = None
    stats["m17"] = m17
    stats["m17_precision"] = dict(
        block_m=[float(v) for v in dop["block_m"]],
        sigma_f_theory_hz_median=float(np.nanmedian(dop["sigma_f_theory"][dop["good"]])),
        sigma_f_empirical_sea_hz_robust=emp,
        hz_to_los_ms=win["wavelength"] / 2,
        window_gain=gain,
        sigma_f_theory_geo_hz_median=float(np.nanmedian(dop["sigma_f_theory"][dop["good"]]) / gain),
        rho_noise=float(dop["rho_n"]),
        rho_signal_median=float(np.nanmedian(dop["rho_s"][dop["good"]])),
        n_blocks=int(dop["good"].sum()), n_slick_blocks=int((d_slick & dop["good"]).sum()),
    )
    stats["n_pixels_m16"] = dict(sea=int(is_sea.sum()), slick=int(is_slick.sum()), bright=int(is_bright.sum()))
    # point-like targets: high coherence between non-overlapping sub-looks (small window)
    pt = np.nan_to_num(sub["coh_half_pt"]) > 0.6
    lab, npt = ndimage.label(pt)
    stats["m16_point_targets"] = dict(
        n_objects=int(npt), n_pixels=int(pt.sum()),
        frac_of_pt_pixels_that_are_bright=float((pt & is_bright).sum() / max(pt.sum(), 1)),
        frac_of_bright_pixels_with_pt=float((pt & is_bright).sum() / max(is_bright.sum(), 1)),
        frac_sea_pixels_flagged=float((pt & is_sea).sum() / max(is_sea.sum(), 1)),
        frac_slick_pixels_flagged=float((pt & is_slick).sum() / max(is_slick.sum(), 1)),
    )

    # resample maps to the island_hh UTM grid
    grids = {}
    for k in ("coh_half", "coh_half_pt", "cohT_q125", "subint_ratio_db", "beta0"):
        grids[k] = to_grid(sub["lon"], sub["lat"], sub[k], x, y)
    for k in ("f_meas", "df_corr", "anom_geo", "los"):
        grids["dop_" + k] = to_grid(dop["lon"], dop["lat"], np.asarray(dop[k], float), x, y)
    valid = np.isfinite(grids["coh_half"])
    np.savez_compressed(
        out_npz, x=x, y=y,
        subcoh=grids["coh_half"], subcoh_pt=grids["coh_half_pt"], subcohT_q125=grids["cohT_q125"], subint_ratio_db=grids["subint_ratio_db"],
        beta0_db=10 * np.log10(grids["beta0"]),
        doppler_hz=grids["dop_f_meas"], doppler_rel_hz=grids["dop_df_corr"], doppler_anom_hz=grids["dop_anom_geo"],
        los_vel_ms=grids["dop_los"], valid=valid, slick=gm["slick"], sea=gm["sea"],
    )
    # radar-geometry products for plotting
    np.savez_compressed(Path(config.RSLC_CACHE) / f"{scene_id}_m16_m17_radar.npz",
                        **{k: sub[k] for k in ("lon", "lat", "beta0", "snr", "coh_half", "coh_half_pt", "coh_q25", "coh_q125",
                                               "cohT_q25", "cohT_q125", "subint_ratio_db")},
                        is_slick=is_slick, is_sea=is_sea, is_bright=is_bright,
                        spectrum_u=sub["spectrum_u"], spectrum=sub["spectrum"],
                        d_lon=dop["lon"], d_lat=dop["lat"], d_anom=dop["anom_geo"], d_anom_raw=dop["anom_raw"],
                        d_los=dop["los"], d_snr=dop["snr"], d_good=dop["good"], d_slick=d_slick,
                        d_sigma=dop["sigma_f_theory"], d_df_corr=dop["df_corr"], d_trend=dop["trend"])
    return stats


def run_all(scene_ids=None, refresh: bool = False) -> dict:
    scene_ids = scene_ids or list(RSLC_SCENES)
    summary = {"method": "M16 sub-look coherence / M17 Doppler anomaly on RSLC HH, track 150D frame 080",
               "window_bbox": list(WINDOW_BBOX), "scenes": {}}
    for sid in scene_ids:
        summary["scenes"][sid] = run_scene(sid, refresh=refresh)
    summary["placebo"] = placebo_test()
    p = Path(config.RESULTS) / "m16_m17_summary.json"
    p.write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    return summary


def placebo_test(control="HH_0624", masks_from=("HH_0811", "HH_0904")) -> dict:
    """Doppler anomaly of the control scene (before grounding) inside the slick footprints of later
    dates: should be ~0 if the slick anomaly is not a fixed geographic / processing artefact."""
    res = {}
    c = np.load(Path(config.RESULTS) / f"m16_m17_{control}.npz")
    for sid in masks_from:
        p = Path(config.RESULTS) / f"m16_m17_{sid}.npz"
        if not p.exists():
            continue
        e = np.load(p)
        m = e["slick"] & np.isfinite(c["doppler_anom_hz"])
        sea = c["sea"] & ~e["slick"] & np.isfinite(c["doppler_anom_hz"])
        res[f"{control}_in_{sid}_slick"] = dict(
            slick_footprint=_stats(c["doppler_anom_hz"], m), sea=_stats(c["doppler_anom_hz"], sea),
            event_scene_slick=_stats(e["doppler_anom_hz"], e["slick"] & np.isfinite(e["doppler_anom_hz"])))
    return res


# ----------------------------------------------------------------------------- plots
def plot_scene(scene_id: str) -> list:
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    fig_dir = Path(config.FIGURES)
    fig_dir.mkdir(parents=True, exist_ok=True)
    r = np.load(Path(config.RESULTS) / f"m16_m17_{scene_id}.npz")
    x, y = r["x"] / 1e3, r["y"] / 1e3
    ext = [x[0], x[-1], y[-1], y[0]]
    v = r["valid"]
    rows = np.nonzero(v.any(1))[0]
    cols = np.nonzero(v.any(0))[0]
    xl = (x[cols.min()], x[cols.max()])
    yl = (y[rows.max()], y[rows.min()])
    paths = []

    def panel(ax, a, title, cmap, vmin, vmax, cb=""):
        im = ax.imshow(a, extent=ext, cmap=cmap, vmin=vmin, vmax=vmax, interpolation="nearest")
        ax.contour(x, y, r["slick"].astype(float), levels=[0.5], colors="red", linewidths=0.6)
        ax.set_xlim(*xl)
        ax.set_ylim(*yl)
        ax.set_title(title, fontsize=8)
        ax.tick_params(labelsize=6)
        ax.set_facecolor("#555")
        plt.colorbar(im, ax=ax, shrink=0.75).set_label(cb, fontsize=7)

    fig, ax = plt.subplots(1, 5, figsize=(23, 4.8), dpi=110)
    panel(ax[0], r["beta0_db"], f"{scene_id}: beta0 HH, dB (RSLC, ~58 m)", "gray", -23, -15, "dB")
    panel(ax[1], r["subcoh"], "M16: sub-look coherence, halves, 170 m window", "magma", 0, 0.2, "|gamma|")
    panel(ax[2], r["subcoh_pt"], "M16: same, 30x50 m window (max per cell): point targets", "magma", 0, 1, "|gamma|")
    panel(ax[3], r["subcohT_q125"], "M16: noise-corrected coherence, 75% overlap", "viridis", 0.8, 1.2, "gamma_t")
    panel(ax[4], r["subint_ratio_db"], "M16: sub-look intensity ratio (front/back), dB", "RdBu_r", -1.0, 1.0, "dB")
    fig.suptitle("Red contour: slick mask from GCOV (dark < -0.8 dB vs 20-km background)", fontsize=8)
    fig.tight_layout()
    p = fig_dir / f"m16_{scene_id}.png"
    fig.savefig(p, facecolor="white")
    plt.close(fig)
    paths.append(p)

    fig, ax = plt.subplots(1, 3, figsize=(15, 4.8), dpi=110)
    panel(ax[0], r["beta0_db"], f"{scene_id}: beta0 HH, dB", "gray", -23, -15, "dB")
    panel(ax[1], r["doppler_rel_hz"], "M17: Doppler minus geometric LUT (noise-corrected), Hz", "RdBu_r", -15, 15, "Hz")
    panel(ax[2], r["doppler_anom_hz"], "M17: Doppler anomaly after mis-pointing trend, Hz", "RdBu_r", -4, 4, "Hz")
    fig.suptitle("Blocks 512x512 samples (~2.3 x 4.8 km), step 128; 1 Hz = 0.12 m/s LOS", fontsize=8)
    fig.tight_layout()
    p = fig_dir / f"m17_{scene_id}.png"
    fig.savefig(p, facecolor="white")
    plt.close(fig)
    paths.append(p)
    return paths


def plot_summary(summary: dict | None = None) -> Path:
    import matplotlib

    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt

    if summary is None:
        summary = json.loads((Path(config.RESULTS) / "m16_m17_summary.json").read_text())
    sids = list(summary["scenes"])
    fig, axes = plt.subplots(1, 4, figsize=(18, 4.2), dpi=110)
    specs = [("m16", "coh_half_pt", "sub-look coherence, point-target window"),
             ("m16", "cohT_q125", "noise-corr. temporal coherence dt~0.4 s"),
             ("m16", "subint_ratio_db", "sub-look intensity ratio, dB"),
             ("m17", "anom_geo", "Doppler anomaly, Hz")]
    colors = {"sea": "#2471a3", "slick": "#c0392b", "bright": "#7f8c8d"}
    for ax, (grp, key, title) in zip(axes, specs):
        labelled = set()
        for i, sid in enumerate(sids):
            st = summary["scenes"][sid][grp][key]
            for j, cls in enumerate(("sea", "slick", "bright")):
                s = st.get(cls)
                if not s:
                    continue
                xpos = i + (j - 1) * 0.25
                ax.plot([xpos, xpos], s["iqr"], color=colors[cls], lw=4, alpha=0.6)
                ax.plot(xpos, s["median"], "o", color=colors[cls], label=None if cls in labelled else cls)
                labelled.add(cls)
        ax.set_xticks(range(len(sids)))
        ax.set_xticklabels(sids, fontsize=7)
        ax.set_title(title, fontsize=9)
        ax.grid(alpha=0.3)
    axes[0].legend(fontsize=7)
    fig.suptitle("M16/M17 by class (median and IQR). HH_0624 = control (before grounding)", fontsize=9)
    fig.tight_layout()
    p = Path(config.FIGURES) / "m16_m17_classes.png"
    fig.savefig(p, facecolor="white")
    plt.close(fig)
    return p
