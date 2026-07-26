#!/usr/bin/env python3
"""
Legge il dato in tempo reale della centralina personale Weathercloud
dell'utente (non un dato di modello, ma la lettura vera dello strumento
installato in loco).

ATTENZIONE - endpoint non ufficiale: Weathercloud non pubblica una API
pubblica documentata per i singoli dispositivi. Questo script usa
l'endpoint POST /device/values (reverse-engineered da progetti terzi,
es. github.com/maxime-mrl/weathercloud-js), verificato funzionante nel
luglio 2026. E' comunque un dato REALE letto dallo strumento (non
un'immagine scaricata/scrapata), coerente con la regola della skill di
usare dati numerici veri: la differenza rispetto a Open-Meteo/ECMWF/
RainViewer e' che qui l'endpoint non e' ufficialmente documentato e
potrebbe cambiare senza preavviso. Se in futuro smette di funzionare,
non insistere con tentativi ripetuti: segnalalo nel bollettino come
dato non disponibile invece di inventare valori.

Uso:
    python3 fetch_weathercloud.py --code 1172679827 --out weathercloud.json

--code e' la sequenza numerica nell'URL della centralina, es. da
"https://app.weathercloud.net/d1172679827#current" il code e' 1172679827.
"""
import argparse
import json

import requests

URL = "https://app.weathercloud.net/device/values"
TIMEOUT = 15


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--code", required=True, help="Codice numerico della centralina (dall'URL app.weathercloud.net/d<code>)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0",
    }
    try:
        r = requests.post(URL, params={"code": args.code}, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        raw = r.json()
    except Exception as e:
        print(f"ERR fetch_weathercloud: {e}")
        json.dump({"error": str(e)}, open(args.out, "w", encoding="utf-8"))
        return

    def kn(ms):
        return round(ms * 1.943844, 1) if ms is not None else None

    out = {
        "epoch": raw.get("epoch"),
        "temperature_c": raw.get("temp"),
        "humidity_pct": raw.get("hum"),
        "pressure_hpa": raw.get("bar"),
        "dewpoint_c": raw.get("dew"),
        "wind_speed_kn": kn(raw.get("wspd")),
        "wind_speed_avg_kn": kn(raw.get("wspdavg")),
        "wind_gust_kn": kn(raw.get("wspdhi")),
        "wind_dir_deg": raw.get("wdiravg", raw.get("wdir")),
        "rain_today_mm": raw.get("rain"),
        "rain_rate_mmh": raw.get("rainrate"),
        "solar_rad_wm2": raw.get("solarrad"),
        "uv_index": raw.get("uvi"),
        "raw": raw,
    }
    json.dump(out, open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"OK -> {args.out}  temp={out['temperature_c']}C hum={out['humidity_pct']}% bar={out['pressure_hpa']}hPa")


if __name__ == "__main__":
    main()
