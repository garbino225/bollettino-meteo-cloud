#!/usr/bin/env python3
"""
Scarica dati meteo reali da Open-Meteo (geocoding + multi-modello + profilo verticale).

Uso:
    python3 fetch_forecast.py --location "Rimini" --start 2026-07-25 --end 2026-07-27 --out data.json
    python3 fetch_forecast.py --lat 44.06 --lon 12.57 --start 2026-07-25 --end 2026-07-27 --out data.json

Produce un unico JSON con:
  - location: geocoding risolto (nome, paese, lat, lon, elevazione, timezone)
  - period: start/end/timezone richiesti
  - models: dati di superficie per ciascun modello numerico disponibile
  - profile: profilo verticale completo (1000-100 hPa) dal modello piu' ricco (best_match)
             usato per calcolare CAPE/CIN/LI/K-Index/shear/SRH e per il grafico skew-T.

Ogni modello che fallisce (non disponibile per quell'area/periodo) viene segnalato
con un campo "error" ma non blocca gli altri: lo script e' pensato per essere
resiliente, non per fallire in blocco.
"""
import argparse
import datetime as dt
import json
import sys

import requests

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"

TIMEOUT = 30

# Modelli numerici richiesti dal documento di specifica, mappati sui nomi
# che Open-Meteo espone pubblicamente. Ogni "seamless" e' un blend automatico
# globale+regionale del centro di calcolo indicato.
MODELS = {
    "best_match":                   "Best Match (blend automatico)",
    "ecmwf_ifs025":                 "ECMWF IFS",
    "gfs_seamless":                 "GFS (NOAA)",
    "icon_seamless":                "ICON (DWD)",
    "icon_eu":                      "ICON-EU (DWD)",
    "icon_d2":                      "ICON-D2 (DWD, alta risoluzione 2km)",
    "meteofrance_arpege_europe":    "ARPEGE (Meteo-France)",
    "meteofrance_arome_france_hd":  "AROME (Meteo-France, solo Francia)",
    "gem_seamless":                 "GEM (ECCC Canada)",
    "ukmo_seamless":                "UKMO (Met Office UK)",
    "knmi_harmonie_arome_europe":   "HARMONIE-AROME (KNMI)",
    "chmi_aladin_seamless":         "ALADIN (CHMI, Europa centrale)",
    "italia_meteo_arpae_icon_2i":   "ICON-2I (ItaliaMeteo/ARPAE, LAM Italia 2km)",
}

# NOTA: MOLOCH (CNR-ISAC, storicamente nel consorzio LAMI insieme a COSMO)
# NON ha un'API pubblica gratuita: e' stato verificato esplicitamente (nessun
# model id funzionante su Open-Meteo, ne' un'API ARPAE-SIMC diversa scriptabile
# per questo dato specifico) - non ritentare pattern a memoria, citarlo solo
# testualmente via WebSearch se rilevante. Il suo erede nel consorzio LAMI,
# ICON-2I (ARPAE/ItaliaMeteo), e' invece disponibile numericamente sopra
# come "italia_meteo_arpae_icon_2i" ed e' il modello da citare quando si
# parla del "LAM Italia": stessa famiglia/filosofia di MOLOCH (modello ad
# area limitata ad alta risoluzione sull'Italia), copertura 2km, run ogni 12h.

# NOTA: Meteoblue, WRF locale e COSMO non hanno un'API pubblica gratuita
# equivalente: non vengono scaricati come dati numerici, ma possono essere
# citati testualmente nell'analisi (SKILL.md lo prevede via ricerca web).

SURFACE_HOURLY = [
    "temperature_2m", "apparent_temperature", "relative_humidity_2m", "dew_point_2m",
    "precipitation_probability", "precipitation", "rain", "showers", "snowfall",
    "weather_code", "cloud_cover", "pressure_msl", "surface_pressure",
    "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m",
    # Diagnostica convettiva nativa di ciascun modello (non calcolata da noi con
    # MetPy come il SBCAPE/CIN/LI del profilo verticale di best_match - vedi
    # indices.py): serve solo per il confronto multi-modello di table_sparkline.py
    # v1.5.1, verificata disponibile per tutti e 13 i modelli (2026-08-20).
    "cape", "convective_inhibition", "lifted_index",
]

SURFACE_DAILY = [
    "temperature_2m_max", "temperature_2m_min",
    "apparent_temperature_max", "apparent_temperature_min",
    "precipitation_sum", "precipitation_probability_max", "precipitation_hours",
    "wind_speed_10m_max", "wind_gusts_10m_max", "wind_direction_10m_dominant",
    "sunrise", "sunset", "uv_index_max", "snowfall_sum",
]

PROFILE_LEVELS = [1000, 975, 950, 925, 900, 850, 800, 700, 600, 500, 400, 300, 250, 200, 150, 100]

PROFILE_SURFACE_EXTRA = [
    "cape", "convective_inhibition", "lifted_index",
    "freezing_level_height", "total_column_integrated_water_vapour", "boundary_layer_height",
    "temperature_2m", "dew_point_2m", "wind_speed_10m", "wind_direction_10m", "surface_pressure",
]


def geocode(location: str):
    r = requests.get(GEOCODING_URL, params={"name": location, "count": 5, "language": "it", "format": "json"},
                      timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    results = data.get("results")
    if not results:
        raise ValueError(f"Localita' '{location}' non trovata. Prova con un nome piu' preciso "
                          f"(es. 'Rimini, Italia') o fornisci --lat/--lon.")
    top = results[0]
    return {
        "query": location,
        "name": top.get("name"),
        "admin1": top.get("admin1"),
        "country": top.get("country"),
        "lat": top["latitude"],
        "lon": top["longitude"],
        "elevation": top.get("elevation"),
        "timezone": top.get("timezone"),
        "candidates": [
            {"name": c.get("name"), "admin1": c.get("admin1"), "country": c.get("country"),
             "lat": c["latitude"], "lon": c["longitude"]}
            for c in results
        ],
    }


def fetch_model(base_url, lat, lon, start, end, model, hourly, daily, extra_params=None):
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(hourly),
        "timezone": "auto",
        "wind_speed_unit": "kn",
        "precipitation_unit": "mm",
    }
    if daily:
        params["daily"] = ",".join(daily)
    if model and base_url == FORECAST_URL:
        params["models"] = model
    if extra_params:
        params.update(extra_params)
    r = requests.get(base_url, params=params, timeout=TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    return r.json()


def build_profile_vars():
    hourly = []
    for lvl in PROFILE_LEVELS:
        hourly += [
            f"temperature_{lvl}hPa",
            f"relative_humidity_{lvl}hPa",
            f"wind_speed_{lvl}hPa",
            f"wind_direction_{lvl}hPa",
            f"geopotential_height_{lvl}hPa",
        ]
    hourly += PROFILE_SURFACE_EXTRA
    return hourly


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--location", help="Nome localita' (es. 'Rimini')")
    ap.add_argument("--lat", type=float, help="Latitudine (alternativa a --location)")
    ap.add_argument("--lon", type=float, help="Longitudine (alternativa a --location)")
    ap.add_argument("--start", required=True, help="Data inizio YYYY-MM-DD")
    ap.add_argument("--end", required=True, help="Data fine YYYY-MM-DD")
    ap.add_argument("--out", required=True, help="Path file JSON di output")
    ap.add_argument("--models", help="Lista modelli separati da virgola (default: tutti)", default=None)
    args = ap.parse_args()

    if not args.location and (args.lat is None or args.lon is None):
        print("ERRORE: fornire --location oppure --lat/--lon", file=sys.stderr)
        sys.exit(2)

    loc = None
    if args.location:
        try:
            loc = geocode(args.location)
        except Exception as e:
            print(json.dumps({"fatal_error": str(e)}, ensure_ascii=False, indent=2))
            sys.exit(1)
        lat, lon = loc["lat"], loc["lon"]
    else:
        lat, lon = args.lat, args.lon
        loc = {"query": f"{lat},{lon}", "name": f"{lat:.3f}, {lon:.3f}", "lat": lat, "lon": lon,
               "admin1": None, "country": None, "elevation": None, "timezone": "auto"}

    today = dt.date.today()
    end_date = dt.date.fromisoformat(args.end)
    is_historical = end_date < today

    base_url = ARCHIVE_URL if is_historical else FORECAST_URL
    model_keys = list(MODELS.keys()) if not args.models else args.models.split(",")
    if is_historical:
        model_keys = ["era5"]  # l'archive API non fa multi-modello, e' rianalisi ERA5

    models_out = {}
    for mk in model_keys:
        label = MODELS.get(mk, "ERA5 Reanalysis (dati passati)" if mk == "era5" else mk)
        try:
            model_param = None if mk == "era5" else mk
            js = fetch_model(base_url, lat, lon, args.start, args.end, model_param,
                              SURFACE_HOURLY, SURFACE_DAILY)
            models_out[mk] = {"label": label, "error": None, "hourly": js.get("hourly"),
                               "daily": js.get("daily"), "hourly_units": js.get("hourly_units"),
                               "daily_units": js.get("daily_units")}
        except Exception as e:
            models_out[mk] = {"label": label, "error": str(e), "hourly": None, "daily": None}

    # Profilo verticale: solo se non storico (l'archive API ha copertura pressure-level
    # limitata) e usando il modello piu' completo disponibile.
    profile_out = {"model": None, "error": None, "hourly": None, "hourly_units": None}
    if not is_historical:
        try:
            js = fetch_model(FORECAST_URL, lat, lon, args.start, args.end, "best_match",
                              build_profile_vars(), None)
            profile_out = {"model": "best_match", "error": None, "hourly": js.get("hourly"),
                            "hourly_units": js.get("hourly_units"), "levels": PROFILE_LEVELS}
        except Exception as e:
            profile_out = {"model": "best_match", "error": str(e), "hourly": None}

    out = {
        "location": loc,
        "period": {"start": args.start, "end": args.end, "historical": is_historical},
        "models": models_out,
        "profile": profile_out,
        "sources": ["Open-Meteo (open-meteo.com) - aggregatore dati ECMWF/GFS/ICON (incl. D2)/GEM/UKMO/ARPEGE/AROME/HARMONIE/ALADIN/ICON-2I ARPAE"],
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    ok_models = [mk for mk, v in models_out.items() if not v["error"]]
    failed_models = [mk for mk, v in models_out.items() if v["error"]]
    print(f"OK -> {args.out}")
    print(f"Localita' risolta: {loc.get('name')} ({loc.get('admin1')}, {loc.get('country')}) "
          f"lat={lat} lon={lon}")
    print(f"Modelli riusciti ({len(ok_models)}): {', '.join(ok_models)}")
    if failed_models:
        print(f"Modelli non disponibili per quest'area/periodo ({len(failed_models)}): {', '.join(failed_models)}")
    print(f"Profilo verticale: {'OK' if not profile_out['error'] else 'ERRORE: ' + profile_out['error']}")


if __name__ == "__main__":
    main()
