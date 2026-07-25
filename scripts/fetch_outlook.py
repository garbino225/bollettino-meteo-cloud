#!/usr/bin/env python3
"""
Scarica un outlook esteso a 7 giorni (dati reali Open-Meteo, modello best_match)
per la sezione finale "Outlook 7 Giorni" del bollettino.

A differenza di fetch_forecast.py (multi-modello, profilo verticale, uso per
l'analisi dettagliata dei primi giorni) questo script e' volutamente piu'
leggero: un solo modello (best_match), niente profilo verticale, pensato solo
per dare un colpo d'occhio sull'evoluzione a piu' lungo termine.

Uso:
    python3 fetch_outlook.py --lat 44.06 --lon 12.57 --start 2026-07-25 --days 7 --out outlook.json

Produce un JSON con un array "days": per ciascun giorno data, giorno della
settimana abbreviato, temperatura min/max, umidita' relativa media (calcolata
mediando i dati orari, Open-Meteo non espone un aggregato giornaliero diretto),
pressione media (stesso motivo), raffica di vento massima, pioggia totale.
"""
import argparse
import datetime as dt
import json
import sys

import requests

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 30

GIORNI_IT = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]

DAILY_VARS = [
    "temperature_2m_max", "temperature_2m_min",
    "precipitation_sum", "wind_speed_10m_max", "wind_gusts_10m_max",
]
HOURLY_VARS = ["relative_humidity_2m", "pressure_msl"]


def _day_label(iso_date: str) -> str:
    d = dt.date.fromisoformat(iso_date)
    return f"{GIORNI_IT[d.weekday()]} {d.strftime('%d/%m')}"


def fetch_outlook(lat, lon, start, days):
    end = (dt.date.fromisoformat(start) + dt.timedelta(days=days - 1)).isoformat()
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start,
        "end_date": end,
        "daily": ",".join(DAILY_VARS),
        "hourly": ",".join(HOURLY_VARS),
        "models": "best_match",
        "timezone": "auto",
        "wind_speed_unit": "kn",
        "precipitation_unit": "mm",
    }
    r = requests.get(FORECAST_URL, params=params, timeout=TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    js = r.json()

    daily = js.get("daily", {})
    hourly = js.get("hourly", {})

    # Media giornaliera di umidita'/pressione oraria, raggruppando per data
    # (Open-Meteo non offre un aggregato giornaliero diretto per queste variabili).
    hum_by_day, pres_by_day = {}, {}
    for ts, hum, pres in zip(hourly.get("time", []),
                              hourly.get("relative_humidity_2m", []),
                              hourly.get("pressure_msl", [])):
        day = ts[:10]
        if hum is not None:
            hum_by_day.setdefault(day, []).append(hum)
        if pres is not None:
            pres_by_day.setdefault(day, []).append(pres)

    days_out = []
    dates = daily.get("time", [])
    for i, date in enumerate(dates):
        hums = hum_by_day.get(date, [])
        press = pres_by_day.get(date, [])
        days_out.append({
            "date": date,
            "label": _day_label(date),
            "tmin": daily["temperature_2m_min"][i] if daily.get("temperature_2m_min") else None,
            "tmax": daily["temperature_2m_max"][i] if daily.get("temperature_2m_max") else None,
            "humidity_mean": round(sum(hums) / len(hums)) if hums else None,
            "pressure_mean": round(sum(press) / len(press), 1) if press else None,
            "wind_gust_max": daily["wind_gusts_10m_max"][i] if daily.get("wind_gusts_10m_max") else None,
            "rain_sum": daily["precipitation_sum"][i] if daily.get("precipitation_sum") else None,
        })
    return days_out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--start", required=True, help="Data inizio outlook YYYY-MM-DD (di solito oggi)")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        days_out = fetch_outlook(args.lat, args.lon, args.start, args.days)
    except Exception as e:
        print(json.dumps({"fatal_error": str(e)}, ensure_ascii=False, indent=2))
        sys.exit(1)

    out = {"model": "best_match", "days": days_out}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"OK -> {args.out} ({len(days_out)} giorni)")


if __name__ == "__main__":
    main()
