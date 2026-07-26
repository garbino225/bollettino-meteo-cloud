#!/usr/bin/env python3
"""
Scarica immagini satellite METEOSAT REALI e ufficiali dal Centro Nazionale
di Meteorologia e Climatologia Aeronautica (CNMCA, Aeronautica Militare),
via l'API pubblica del loro CMS (cm.meteoam.it). Sostituisce la mappa
satellite live via RainViewer (JS, richiedeva connessione nel browser di
chi apre il file e non funzionava in anteprima con JS disabilitato):
qui le immagini sono scaricate una volta in fase di generazione e
incorporate come GIF animata, nessuna dipendenza da rete/JS per chi apre
il bollettino.

Licenza: dati/immagini Meteosat diffusi "on the hour" (ogni ora e frazioni
regolari come i 15 minuti qui usati) sono classificati "Essential" dalla
EUMETSAT Data Policy e liberamente utilizzabili da qualunque categoria di
utente senza restrizioni (vedi meteoam.it/it/licenze-uso-eumetsat) -
attribuzione "CNMCA - Aeronautica Militare / EUMETSAT" comunque inclusa.

Prodotto di default: ITALIA24 (combo HRV di giorno / IR 10.8um di notte,
utilizzabile a qualunque ora, importante per la routine automatica che
gira all'alba). Altri prodotti disponibili in PRODOTTI sotto - passa
--product per usarne un altro, in particolare **RADSATLAM** (radar
precipitazioni reale SRI mm/h + satellite IR + fulmini reali rete
LAMPINET, ~20 min): usalo per il bollettino al posto della vecchia mappa
radar live RainViewer/Leaflet, stesso motivo (JS che non funziona in
anteprime che lo disabilitano) e con il vantaggio aggiuntivo di includere
i fulmini, che prima non avevamo nessuna fonte gratuita per mostrare.

Uso:
    python3 fetch_meteoam_satellite.py --frames 8 --outdir /tmp/meteo_<slug>/charts --prefix imola
    python3 fetch_meteoam_satellite.py --product RADSATLAM --frames 8 --outdir /tmp/meteo_<slug>/charts --prefix imola_radar
"""
import argparse
import json
import os

import requests

API = "https://cm.meteoam.it/content/published/api/v1.1/items"
TIMEOUT = 20
ATTRIBUTION = "CNMCA - Aeronautica Militare / EUMETSAT"

PRODOTTI = {
    "ITALIA24": "98126dc89e7844ae96118da03a93ec40",       # HRV/IR combo, giorno e notte
    "EUROPA108": "186d2a613a844ab9994a318c6f042fbb",       # infrarosso 10.8um, Europa, giorno e notte
    "TRUECOLORRGB": "432fdc6873734a2b9a5886655e9a2eec",    # colori naturali, solo diurna
    "NEFOITALIA": "fec9cc38633e4afea3689b19fe7ef08a",       # analisi nubi Italia
    "RADSATLAM": "265296ba8be0410caa87a18186bcbb43",        # radar precipitazioni (SRI mm/h) + IR + fulmini reali (rete LAMPINET), ~20 min
}


def large_jpg_url(item):
    for rend in item["fields"]["renditions"]:
        if rend["name"] == "Large":
            for f in rend["formats"]:
                if f["format"] == "jpg":
                    return f["links"][0]["href"]
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--product", default="ITALIA24", choices=list(PRODOTTI))
    ap.add_argument("--frames", type=int, default=8, help="quanti frame recenti scaricare (15 min l'uno)")
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--prefix", default="sat")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    token = PRODOTTI[args.product]

    r = requests.get(API, params={"channelToken": token, "fields": "all",
                                   "limit": args.frames, "orderBy": "fields.date:desc"}, timeout=TIMEOUT)
    r.raise_for_status()
    items = r.json().get("items", [])
    items.reverse()  # dal piu' vecchio al piu' recente, per l'animazione

    frames = []
    for i, it in enumerate(items):
        url = large_jpg_url(it)
        if not url:
            print(f"ERR frame {i}: nessuna rendition Large trovata")
            continue
        try:
            img = requests.get(url, timeout=TIMEOUT)
            img.raise_for_status()
        except Exception as e:
            print(f"ERR frame {i}: {e}")
            continue
        fname = f"{args.prefix}_meteosat_{args.product}_{i:02d}.jpg"
        out_path = os.path.join(args.outdir, fname)
        with open(out_path, "wb") as f:
            f.write(img.content)
        date_val = it["fields"]["date"]["value"]
        label = date_val[11:16] + " UTC il " + date_val[8:10] + "/" + date_val[5:7]
        frames.append({"file": fname, "label": label})
        print(f"OK  frame {i} ({date_val}) -> {fname}")

    manifest = {"product": args.product, "attribution": ATTRIBUTION, "frames": frames}
    manifest_path = os.path.join(args.outdir, f"{args.prefix}_meteosat_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"Manifest -> {manifest_path} ({len(frames)} frame)")


if __name__ == "__main__":
    main()
