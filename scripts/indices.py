#!/usr/bin/env python3
"""
Calcola indici convettivi avanzati da un profilo verticale (output di fetch_forecast.py)
usando formule termodinamiche reali (libreria MetPy), non stime a occhio.

Uso:
    python3 indices.py data.json --out indices.json

Per ogni istante orario del profilo calcola (quando i dati lo consentono):
  - CAPE / CIN (surface-based)
  - Lifted Index
  - K-Index
  - Total Totals Index
  - SWEAT Index (formula classica)
  - Shear 0-6 km (bulk shear, kn)
  - Storm Relative Helicity 0-3 km (Bunkers right-mover)
  - PWAT, zero termico, CAPE/CIN "diretti" da Open-Meteo (cross-check)

Ogni indice che non puo' essere calcolato (dati mancanti/instabilita' numerica)
viene impostato a null col motivo, senza bloccare gli altri.
"""
import argparse
import json
import math
import warnings

import numpy as np

warnings.filterwarnings("ignore")

import metpy.calc as mpcalc
from metpy.units import units

PROFILE_LEVELS = [1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150, 100]


def safe(fn):
    try:
        return fn(), None
    except Exception as e:
        return None, str(e)


def sweat_index(td850, tt, ff850, ff500, dd850, dd500):
    """SWEAT Index (Severe Weather Threat) - formula classica NWS."""
    term1 = 12 * max(td850, 0)
    term2 = 20 * max(tt - 49, 0)
    term3 = 2 * ff850
    term4 = ff500
    shear_ok = (130 <= dd850 <= 250) and (210 <= dd500 <= 310) and (dd500 - dd850 > 0) \
        and (ff850 >= 15) and (ff500 >= 15)
    term5 = 125 * (math.sin(math.radians(dd500 - dd850)) + 0.2) if shear_ok else 0
    return term1 + term2 + term3 + term4 + max(term5, 0)


def compute_timestep(hourly, t_idx):
    out = {}
    pressures, temps, rhs, wspd, wdir, heights = [], [], [], [], [], []
    for lvl in PROFILE_LEVELS:
        t = hourly.get(f"temperature_{lvl}hPa", [None] * (t_idx + 1))[t_idx]
        rh = hourly.get(f"relative_humidity_{lvl}hPa", [None] * (t_idx + 1))[t_idx]
        ws = hourly.get(f"wind_speed_{lvl}hPa", [None] * (t_idx + 1))[t_idx]
        wd = hourly.get(f"wind_direction_{lvl}hPa", [None] * (t_idx + 1))[t_idx]
        gh = hourly.get(f"geopotential_height_{lvl}hPa", [None] * (t_idx + 1))[t_idx]
        if None in (t, rh, ws, wd, gh):
            continue
        pressures.append(lvl)
        temps.append(t)
        rhs.append(rh)
        wspd.append(ws)
        wdir.append(wd)
        heights.append(gh)

    if len(pressures) < 6:
        return {"error": "profilo insufficiente a questo istante (dati modello mancanti)"}

    p = np.array(pressures) * units.hPa
    T = np.array(temps) * units.degC
    RH = np.array(rhs) * units.percent
    height = np.array(heights) * units.meter
    # wind_speed_unit richiesto in kn nel fetch -> converti in m/s per MetPy
    spd_ms = (np.array(wspd) * units.knots).to("m/s")
    wd_arr = np.array(wdir) * units.deg

    Td, err = safe(lambda: mpcalc.dewpoint_from_relative_humidity(T, RH))
    out["dewpoint_850hPa"] = None
    if Td is not None and 850 in pressures:
        idx850 = pressures.index(850)
        out["dewpoint_850hPa"] = round(float(Td[idx850].magnitude), 1)

    u, v = None, None
    if Td is not None:
        u, v = mpcalc.wind_components(spd_ms, wd_arr)

    # CAPE/CIN + Lifted Index (surface-based)
    if Td is not None:
        parcel, err_p = safe(lambda: mpcalc.parcel_profile(p, T[0], Td[0]))
        if parcel is not None:
            (sbcape_sbcin), err_c = safe(lambda: mpcalc.cape_cin(p, T, Td, parcel))
            if sbcape_sbcin is not None:
                sbcape, sbcin = sbcape_sbcin
                out["sbcape_Jkg"] = round(float(sbcape.magnitude), 0)
                out["sbcin_Jkg"] = round(float(sbcin.magnitude), 0)
            else:
                out["sbcape_Jkg"] = None
                out["sbcin_Jkg"] = None
                out["sbcape_error"] = err_c
            li, err_li = safe(lambda: mpcalc.lifted_index(p, T, parcel))
            out["lifted_index"] = round(float(np.atleast_1d(li.magnitude)[0]), 1) if li is not None else None
        else:
            out["sbcape_Jkg"] = out["sbcin_Jkg"] = out["lifted_index"] = None
            out["parcel_error"] = err_p

    # K-Index e Total Totals (richiedono 850/700/500 hPa)
    if Td is not None and all(l in pressures for l in (850, 700, 500)):
        ki, err_k = safe(lambda: mpcalc.k_index(p, T, Td))
        out["k_index"] = round(float(ki.magnitude), 1) if ki is not None else None
        tt, err_t = safe(lambda: mpcalc.total_totals_index(p, T, Td))
        out["total_totals"] = round(float(tt.magnitude), 1) if tt is not None else None

        if out.get("total_totals") is not None and out.get("dewpoint_850hPa") is not None:
            i850, i500 = pressures.index(850), pressures.index(500)
            ff850 = wspd[i850]
            ff500 = wspd[i500]
            dd850 = wdir[i850]
            dd500 = wdir[i500]
            try:
                out["sweat_index"] = round(sweat_index(out["dewpoint_850hPa"], out["total_totals"],
                                                         ff850, ff500, dd850, dd500), 0)
            except Exception as e:
                out["sweat_index"] = None
                out["sweat_error"] = str(e)
    else:
        out["k_index"] = out["total_totals"] = out["sweat_index"] = None

    # Shear 0-6km e SRH 0-3km (richiedono vento+quota su piu' livelli)
    if u is not None and len(height) >= 6:
        try:
            order = np.argsort(height.magnitude)
            h_s = height[order]
            u_s = u[order]
            v_s = v[order]
            p_s = p[order]
            shear_u, shear_v = mpcalc.bulk_shear(p_s, u_s, v_s, height=h_s, depth=6000 * units.meter)
            shear_mag = np.sqrt(shear_u ** 2 + shear_v ** 2).to("knots")
            out["shear_0_6km_kn"] = round(float(shear_mag.magnitude), 0)
        except Exception as e:
            out["shear_0_6km_kn"] = None
            out["shear_error"] = str(e)

        try:
            right_mover, left_mover, mean_wind = mpcalc.bunkers_storm_motion(p_s, u_s, v_s, h_s)
            srh_pos, srh_neg, srh_tot = mpcalc.storm_relative_helicity(
                h_s, u_s, v_s, depth=3000 * units.meter,
                storm_u=right_mover[0], storm_v=right_mover[1])
            out["srh_0_3km_m2s2"] = round(float(srh_tot.magnitude), 0)
        except Exception as e:
            out["srh_0_3km_m2s2"] = None
            out["srh_error"] = str(e)
    else:
        out["shear_0_6km_kn"] = out["srh_0_3km_m2s2"] = None

    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("data_json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.data_json, encoding="utf-8") as f:
        data = json.load(f)

    profile = data.get("profile", {})
    if profile.get("error") or not profile.get("hourly"):
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"error": profile.get("error", "profilo non disponibile")}, f, ensure_ascii=False, indent=2)
        print("Nessun profilo disponibile, indici non calcolati.")
        return

    hourly = profile["hourly"]
    times = hourly["time"]
    results = []
    for i, t in enumerate(times):
        r = compute_timestep(hourly, i)
        r["time"] = t
        # cross-check diretti Open-Meteo
        r["cape_openmeteo_Jkg"] = hourly.get("cape", [None] * len(times))[i]
        r["cin_openmeteo_Jkg"] = hourly.get("convective_inhibition", [None] * len(times))[i]
        r["lifted_index_openmeteo"] = hourly.get("lifted_index", [None] * len(times))[i]
        r["freezing_level_m"] = hourly.get("freezing_level_height", [None] * len(times))[i]
        r["pwat_kg_m2"] = hourly.get("total_column_integrated_water_vapour", [None] * len(times))[i]
        r["boundary_layer_height_m"] = hourly.get("boundary_layer_height", [None] * len(times))[i]
        results.append(r)

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"timesteps": results}, f, ensure_ascii=False, indent=2)

    n_ok = sum(1 for r in results if r.get("sbcape_Jkg") is not None)
    print(f"OK -> {args.out} ({len(results)} istanti, CAPE calcolato in {n_ok})")


if __name__ == "__main__":
    main()
