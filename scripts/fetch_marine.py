#!/usr/bin/env python3
"""
Scarica dati mare reali (onde multi-modello + marea) da Open-Meteo Marine API,
per il bollettino di localita' costiere.

Uso:
    python3 fetch_marine.py --lat 44.47 --lon 12.31 --start 2026-07-27 --end 2026-07-29 --out marine.json

Produce un JSON con:
  - wave_models: altezza/direzione/periodo onda per ciascun modello (stesso
    pattern multi-modello di fetch_forecast.py: ogni modello che fallisce per
    quell'area/periodo viene segnalato con "error" ma non blocca gli altri)
  - tide: livello del mare orario (sea_level_height_msl, include la marea
    astronomica + surge), disponibile solo su "best_match" (la Marine API di
    Open-Meteo non lo espone per-modello)

Nota: la Marine API non ha un endpoint storico equivalente ad archive-api per
il meteo di superficie; per periodi nel passato lo script segnala l'errore
per ciascun modello invece di inventare un fallback.
"""
import argparse
import json
import sys

import requests

MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
TIMEOUT = 30

WAVE_MODELS = {
    "best_match":         "Best Match (blend automatico)",
    "ecmwf_wam025":       "ECMWF WAM",
    "meteofrance_wave":   "MFWAM (Meteo-France)",
    "ncep_gfswave025":    "GFS-Wave (NOAA)",
    "dwd_ewam":           "EWAM (DWD, Europa)",
    "dwd_gwam":           "GWAM (DWD, globale)",
}

WAVE_HOURLY = ["wave_height", "wave_direction", "wave_period"]
TIDE_HOURLY = ["sea_level_height_msl"]


def fetch(lat, lon, start, end, model, hourly):
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(hourly),
        "timezone": "auto",
    }
    if model:
        params["models"] = model
    r = requests.get(MARINE_URL, params=params, timeout=TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--start", required=True, help="Data inizio YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="Data fine YYYY-MM-DD")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    wave_models_out = {}
    for mk, label in WAVE_MODELS.items():
        try:
            js = fetch(args.lat, args.lon, args.start, args.end, mk, WAVE_HOURLY)
            wave_models_out[mk] = {"label": label, "error": None, "hourly": js.get("hourly"),
                                    "hourly_units": js.get("hourly_units")}
        except Exception as e:
            wave_models_out[mk] = {"label": label, "error": str(e), "hourly": None}

    tide_out = {"model": "best_match", "error": None, "hourly": None, "hourly_units": None}
    try:
        js = fetch(args.lat, args.lon, args.start, args.end, "best_match", TIDE_HOURLY)
        tide_out = {"model": "best_match", "error": None, "hourly": js.get("hourly"),
                    "hourly_units": js.get("hourly_units")}
    except Exception as e:
        tide_out = {"model": "best_match", "error": str(e), "hourly": None}

    out = {
        "period": {"start": args.start, "end": args.end},
        "wave_models": wave_models_out,
        "tide": tide_out,
        "sources": ["Open-Meteo Marine API (open-meteo.com) - ECMWF WAM/MFWAM/GFS-Wave/EWAM/GWAM; "
                    "livello del mare (marea) da GTSM/modello best_match"],
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    ok = [mk for mk, v in wave_models_out.items() if not v["error"]]
    failed = [mk for mk, v in wave_models_out.items() if v["error"]]
    print(f"OK -> {args.out}")
    print(f"Modelli onda riusciti ({len(ok)}): {', '.join(ok)}")
    if failed:
        print(f"Modelli onda non disponibili per quest'area/periodo ({len(failed)}): {', '.join(failed)}")
    print(f"Marea (sea_level_height_msl): {'OK' if not tide_out['error'] else 'ERRORE: ' + tide_out['error']}")


if __name__ == "__main__":
    main()
