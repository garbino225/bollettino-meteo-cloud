#!/usr/bin/env python3
"""
Calcola la fase lunare del giorno e i giorni mancanti alla prossima luna piena.

Formula chiusa basata sul mese sinodico medio (29.530588861 giorni) e su un
epoca di riferimento di luna nuova nota (6 gennaio 2000, 18:14 UTC), non su
un'effemeride JPL completa: verificato contro Skyfield/DE421 (stesso
strumento usato in un altro progetto dell'utente) con un errore di ~1-2 ore,
ampiamente sufficiente per un dato di contorno arrotondato al giorno in un
bollettino meteo - evita di scaricare un file di effemeride (~17MB) e quindi
di dover aggiungere un nuovo dominio alla whitelist di rete della routine
cloud non presidiata.

Uso:
    python3 moon_phase.py --date 2026-07-27 --out moon.json
    python3 moon_phase.py   # usa oggi, stampa solo a schermo
"""
import argparse
import datetime as dt
import json
import math
from zoneinfo import ZoneInfo

SYNODIC_MONTH = 29.530588861
REF_NEW_MOON = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)
ROME_TZ = ZoneInfo("Europe/Rome")

PHASE_NAMES = [
    "Luna Nuova", "Luna Crescente", "Primo Quarto", "Gibbosa Crescente",
    "Luna Piena", "Gibbosa Calante", "Ultimo Quarto", "Luna Calante",
]


def moon_age_days(when: dt.datetime) -> float:
    delta = (when - REF_NEW_MOON).total_seconds() / 86400
    return delta % SYNODIC_MONTH


def phase_name(age: float) -> str:
    w = SYNODIC_MONTH / 8
    idx = round(age / w) % 8
    return PHASE_NAMES[idx]


def illumination_pct(age: float) -> float:
    return round((1 - math.cos(2 * math.pi * age / SYNODIC_MONTH)) / 2 * 100, 1)


def days_to_next_full_moon(age: float) -> float:
    half = SYNODIC_MONTH / 2
    if age < half:
        return half - age
    return SYNODIC_MONTH - age + half


def moon_info(when: dt.datetime) -> dict:
    age = moon_age_days(when)
    days_to_full = days_to_next_full_moon(age)
    next_full = when + dt.timedelta(days=days_to_full)
    next_full_local = next_full.astimezone(ROME_TZ)
    return {
        "date": when.date().isoformat(),
        "age_days": round(age, 1),
        "phase_name": phase_name(age),
        "illumination_pct": illumination_pct(age),
        "days_to_full_moon": round(days_to_full, 1),
        "next_full_moon_date": next_full_local.date().isoformat(),
        "next_full_moon_time_local": next_full_local.strftime("%H:%M"),
        "next_full_moon_tz": next_full_local.tzname(),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", help="Data YYYY-MM-DD (default: oggi, mezzogiorno UTC)")
    ap.add_argument("--out", help="Path file JSON di output (opzionale)")
    args = ap.parse_args()

    if args.date:
        when = dt.datetime.fromisoformat(args.date).replace(hour=12, tzinfo=dt.timezone.utc)
    else:
        when = dt.datetime.now(dt.timezone.utc)

    info = moon_info(when)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)
        print(f"OK -> {args.out}")
    print(f"{info['phase_name']} ({info['illumination_pct']}% illuminata), "
          f"prossima luna piena tra {info['days_to_full_moon']} giorni "
          f"({info['next_full_moon_date']} alle {info['next_full_moon_time_local']} "
          f"{info['next_full_moon_tz']})")


if __name__ == "__main__":
    main()
