#!/usr/bin/env python3
"""
Scarica mappe/cartine REALI e ufficiali ECMWF dall'OpenCharts API pubblica
(https://charts.ecmwf.int) - licenza CC-BY-4.0 (riutilizzo consentito con
attribuzione, gia' inclusa nell'immagine stessa).

A differenza di charts.py (che genera grafici propri dai dati Open-Meteo),
questo script scarica le cartine sinottiche originali prodotte da ECMWF:
utile per l'analisi sinottica (pressione/geopotenziale/fronti) e come
cross-check visivo indipendente dei parametri convettivi.

Uso:
    python3 fetch_ecmwf_charts.py --lat 44.06 --lon 12.57 --requests requests.json --outdir ecmwf_charts/

requests.json e' una lista di oggetti scritta dall'agente dopo aver deciso
quali giorni/orari sono editorialmente rilevanti (es. un giorno per
l'evoluzione sinottica, l'ora di picco convettivo per i parametri
avanzati):
[
  {"product": "medium-mslp-rain", "valid_time": "2026-07-25T12:00:00Z", "caption": "Pressione e piogge - 25/07 12 UTC"},
  {"product": "medium-z500-t850", "valid_time": "2026-07-25T12:00:00Z", "caption": "Geopotenziale 500hPa e T 850hPa - 25/07"},
  {"product": "medium-uv-rh", "valid_time": "2026-07-25T15:00:00Z", "level": 700, "caption": "Vento e umidita' a 700hPa - 25/07 15 UTC"},
  {"product": "medium-cape-cin", "valid_time": "2026-07-25T15:00:00Z", "caption": "CAPE/CIN ECMWF - 25/07 15 UTC"}
]

Per generare un'ANIMAZIONE (usata dal report HTML, vedi build_html.py) usa
un oggetto con "series" invece di "valid_time" singolo: scarica un frame
per ogni step da series_start a series_end e produce in
ecmwf_manifest.json una voce "sequences" pronta da passare a build_html.py
senza dover enumerare a mano gli orari (allineati automaticamente a step
di 3h):
[
  {"product": "medium-mslp-rain", "series_start": "2026-07-23T12:00:00Z",
   "series_end": "2026-07-25T12:00:00Z", "interval_hours": 6,
   "caption": "Evoluzione pressione e precipitazioni"}
]

Prodotti disponibili piu' utili per un bollettino (nome -> contenuto):
  medium-2t-wind      Temperatura 2m + vento 10m
  medium-2t-dp        Temperatura 2m + punto di rugiada
  medium-mslp-rain    Pressione mslp + precipitazione 6h
  medium-rain-acc     Precipitazione cumulata
  medium-cape-cin     CAPE e CIN (MUCAPE/MUCIN)
  medium-bulk-shear   Shear (wind shear 0-6km)
  medium-uv-rh        Vento + umidita' relativa a un livello di pressione (richiede "level": 850/700/500/...)
  medium-t-z          Temperatura + geopotenziale a un livello di pressione (richiede "level")
  medium-z500-t850    Geopotenziale 500hPa + temperatura 850hPa (combo pronta)
  medium-zero-level   Quota dello zero termico
  medium-snowfall     Nevicate previste
  medium-indices      Indici convettivi (cartina ECMWF ufficiale)
  medium-cloud-parameters  Parametri di nuvolosita'
  medium-wind-10m     Vento a 10m
  medium-wind-100m    Vento a 100m

La proiezione (area geografica) viene scelta automaticamente in base a
lat/lon; puoi forzarla con --projection.

IMPORTANTE: valid_time deve cadere su uno degli step disponibili per il
base_time scelto automaticamente dall'API (in genere ogni 3 ore: 00, 03,
06, 09, 12, 15, 18, 21 UTC). Se sbagli, l'errore HTTP 404 restituito
elenca comodamente i valid_time validi ("Current available valid_time
[...]"): usa quella lista invece di ritentare a caso.
"""
import argparse
import datetime
import json
import os

import requests

API = "https://charts.ecmwf.int/opencharts-api/v1/products/{product}/"
LANDING_URL = "https://charts.ecmwf.int/products/{product}"
TIMEOUT = 30

ATTRIBUTION = "© ECMWF - Licenza CC BY 4.0 - www.ecmwf.int"


def region_for(lat, lon):
    """Euristica lat/lon -> proiezione opencharts. Non perfetta, ma ragionevole."""
    if 34 <= lat <= 72 and -25 <= lon <= 45:
        if lat >= 55 and lon > 5:
            return "opencharts_north_east_europe"
        if lat >= 48 and lon <= 5:
            return "opencharts_north_west_europe"
        if lat < 45 and lon <= 5:
            return "opencharts_south_west_europe"
        if lat < 48 and lon > 5:
            return "opencharts_south_east_europe"
        if 45 <= lat < 55:
            return "opencharts_central_europe"
        return "opencharts_europe"
    if 10 <= lat <= 40 and -20 <= lon <= 60:
        return "opencharts_northern_africa"
    if -40 <= lat < 10 and -20 <= lon <= 55:
        return "opencharts_africa"
    if 5 <= lat <= 60 and 60 <= lon <= 100:
        return "opencharts_southern_asia"
    if -10 <= lat <= 55 and 100 <= lon <= 150:
        return "opencharts_eastern_asia"
    if 15 <= lat <= 75 and -170 <= lon <= -50:
        return "opencharts_north_america"
    if -60 <= lat < 15 and -90 <= lon <= -30:
        return "opencharts_south_america"
    if -50 <= lat <= 10 and 110 <= lon <= 180:
        return "opencharts_australasia"
    return "opencharts_global"


def fetch_one(product, valid_time=None, level=None, projection=None, out_path=None):
    params = {}
    if valid_time:
        params["valid_time"] = valid_time
    if level:
        params["level"] = level
    if projection:
        params["projection"] = projection
    url = API.format(product=product)
    r = requests.get(url, params=params, timeout=TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    if "error" in data:
        raise RuntimeError(str(data["error"]))
    img_url = data["data"]["link"]["href"]
    title = data["data"]["attributes"].get("title", product)
    description = data["data"]["attributes"].get("description", "")
    img = requests.get(img_url, timeout=TIMEOUT)
    img.raise_for_status()
    with open(out_path, "wb") as f:
        f.write(img.content)
    return {"title": title, "description": description, "source_url": img_url}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--requests", required=True, help="Path a requests.json (vedi docstring)")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--projection", default=None, help="Forza una proiezione invece dell'euristica automatica")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    projection = args.projection or region_for(args.lat, args.lon)

    with open(args.requests, encoding="utf-8") as f:
        reqs = json.load(f)

    manifest = []
    sequences = []
    counter = 0
    for item in reqs:
        product = item["product"]
        level = item.get("level")

        if "series" in item or "series_start" in item:
            start = datetime.datetime.fromisoformat(item["series_start"].replace("Z", "+00:00"))
            end = datetime.datetime.fromisoformat(item["series_end"].replace("Z", "+00:00"))
            step_h = int(item.get("interval_hours", 6))
            caption = item.get("caption", product)
            frames = []
            t = start
            while t <= end:
                vt = t.strftime("%Y-%m-%dT%H:00:00Z")
                fname = f"ecmwf_{product}_{counter:02d}" + (f"_{level}hPa" if level else "") + "_anim.png"
                out_path = os.path.join(args.outdir, fname)
                counter += 1
                try:
                    meta = fetch_one(product, vt, level, projection, out_path)
                    frames.append({"file": fname, "valid_time": vt, "label": t.strftime("%d/%m %H:00 UTC")})
                    print(f"OK  [seq] {product} ({vt}) -> {fname}")
                except Exception as e:
                    print(f"ERR [seq] {product} ({vt}): {e}")
                t += datetime.timedelta(hours=step_h)
            if frames:
                sequences.append({"product": product, "caption": caption, "level": level,
                                   "landing_url": LANDING_URL.format(product=product), "frames": frames})
            continue

        valid_time = item.get("valid_time")
        caption = item.get("caption", product)
        fname = f"ecmwf_{product}_{counter:02d}" + (f"_{level}hPa" if level else "") + ".png"
        out_path = os.path.join(args.outdir, fname)
        counter += 1
        try:
            meta = fetch_one(product, valid_time, level, projection, out_path)
            manifest.append({
                "file": fname, "caption": caption, "title": meta["title"],
                "description": meta["description"], "attribution": ATTRIBUTION,
                "landing_url": LANDING_URL.format(product=product),
                "projection": projection, "error": None,
            })
            print(f"OK  {product} ({valid_time}, level={level}) -> {fname}  [{meta['description']}]")
        except Exception as e:
            manifest.append({"file": None, "caption": caption, "product": product,
                              "valid_time": valid_time, "level": level, "error": str(e)})
            print(f"ERR {product} ({valid_time}, level={level}): {e}")

    with open(os.path.join(args.outdir, "ecmwf_manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"projection": projection, "attribution": ATTRIBUTION, "charts": manifest,
                    "sequences": sequences}, f, ensure_ascii=False, indent=2)
    print(f"Proiezione usata: {projection}")
    if sequences:
        print(f"Sequenze per animazione: {len(sequences)} ({[s['product'] + ':' + str(len(s['frames'])) + 'frame' for s in sequences]})")


if __name__ == "__main__":
    main()
