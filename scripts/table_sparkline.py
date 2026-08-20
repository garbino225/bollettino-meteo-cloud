#!/usr/bin/env python3
"""
Genera la "tabella convettiva" standalone: pagina HTML autonoma con la
tabella tri-oraria (temperatura, vento, pioggia, parametri convettivi MetPy,
mare se disponibile) e, per ogni colonna numerica, un grafico a linea in
filigrana sullo sfondo delle celle che ne mostra l'andamento scorrendo la
colonna verso il basso (scala min-max propria di quella colonna).

E' il deliverable "solo la tabella" della skill bollettino-meteo (vedi
SKILL.md, punto 7.5): stesso stile/target di design della versione completa
(PDF+HTML), ma come singolo file leggero pensato per essere aperto/
condiviso da solo, senza il resto del bollettino.

Uso:
    python3 table_sparkline.py \\
        --data data.json --indices indices.json [--marine marine.json] \\
        --location-label "Punta Marina Terme (RA)" \\
        --out tabella.html

data.json / indices.json / marine.json sono gli output di fetch_forecast.py,
indices.py e (se la localita' e' costiera) fetch_marine.py: questo script
non scarica nulla, solo unisce e disegna quanto gia' raccolto.
"""
import argparse
import base64
import datetime as dt
import io
import json
import math

RH = 32  # altezza fissa riga corpo tabella, px - deve combaciare con lo sfondo sparkline

# Versione del template (non del dato): incrementa quando cambia design/colonne/logica
# di questo script, cosi' chi guarda una tabella generata sa a quale revisione risale.
# 1.0.0 (2026-08-16): prima versione di produzione - sparkline per colonna, legenda
#   parametri con range osservato, copertura nuvolosa in ottavi, colonne mare opzionali.
# 1.1.0 (2026-08-16): colorazione per gravita' delle singole celle (giallo/arancio/
#   rosso/fucsia, soglie specifiche per parametro - vedi SEVERITY_RULES), soglie
#   mostrate in legenda; sparkline ridisegnato con tecnica alone+linea (halo) per
#   restare leggibile sopra qualunque colore di sfondo; hover non copre piu' il
#   colore di gravita' della cella.
# 1.2.0 (2026-08-16): aggiunte le colonne Pressione (mslp, hPa) e Umidita' (%) nel
#   gruppo Atmosfera. Nessuna colorazione per gravita' su queste due (come Nuv.:
#   descrittive, non parametri di rischio in se' con una soglia universale sensata).
# 1.3.0 (2026-08-16): aggiunta riga astronomica prima del titolo con alba/tramonto
#   (dal blend Best Match, giorno d'inizio periodo) e fase lunare (stessa formula a
#   forma chiusa - mese sinodico + epoca nota - gia' usata da moon_phase.py per il
#   bollettino completo, reimplementata qui per non richiedere un file di input in
#   piu': e' un calcolo puro, non un dato scaricato).
# 1.3.1 (2026-08-16): fix caratteri accentati/speciali illeggibili (mojibake) quando
#   il file HTML viene aperto direttamente da disco (file://): mancava una dichiarazione
#   esplicita <meta charset="utf-8">, quindi il browser doveva indovinare la codifica e
#   in alcuni ambienti sbagliava. Il file era gia' scritto correttamente in UTF-8 su
#   disco (open(..., encoding="utf-8")), il problema era solo nella lettura senza
#   dichiarazione esplicita. Aggiunta come primissima riga del template.
# 1.3.2 (2026-08-16): fix sovrapposizione tag giorno/ora nella colonna Data/ora sulle
#   righe di inizio giornata (es. "DOM 16/08" e "00:00" si accavallavano): colonna
#   time allargata da 108 a 142px, non c'era abbastanza spazio per entrambi affiancati
#   nel flex .col-time. Segnalato dall'utente il 2026-08-16.
# 1.4.0 (2026-08-16): allineamento orari nella colonna Data/ora (il tag del giorno
#   occupava larghezza variabile/zero secondo il contenuto, spostando "00:00" rispetto
#   a "03:00"/"06:00"/...: ora .day-tag-slot ha larghezza fissa, tutti gli orari sono
#   allineati alla stessa colonna). Aggiunto logo meteoP@d0 opzionale (--logo) in alto
#   a destra nell'intestazione, accanto al blocco di testo.
# 1.4.1 (2026-08-16): logo ingrandito (44px -> 72px di altezza), su richiesta utente.
# 1.4.2 (2026-08-16): logo ulteriormente ingrandito (72px -> 104px) e sfondo "carta"
#   dell'immagine originale (assets/logo.png non ha canale alpha) reso trasparente
#   via soglia luminosita'+saturazione (vedi logo_png_bytes) - elaborato solo per
#   l'embedding qui, il file sorgente non viene toccato. Richiede Pillow e numpy
#   (gia' dipendenze della skill).
# 1.4.3 (2026-08-16): rebrand logo, sostituito assets/logo.png con il nuovo logo
#   "meteogarbino225" (icona quadrata a sfondo blu notte pieno, non piu' un wordmark
#   su carta chiara). logo_png_bytes() non rimuove nulla su questo file (le soglie
#   agiscono solo su sfondi chiari/poco saturi, lo sfondo blu notte resta intatto
#   com'e' voluto). Aggiunto border-radius:18px al tag <img> per renderlo un'icona
#   con angoli smussati invece di un rettangolo netto. Vecchio logo conservato in
#   assets/logo_meteopd0_old.png.
# 1.4.4 (2026-08-19): aggiunta una tabella "Revisioni" in fondo alla pagina (sotto
#   la legenda parametri, sopra il footer) che elenca ogni versione dello script e
#   le novita' introdotte, cosi' chi apre il file vede lo storico senza dover
#   guardare questo changelog nel codice sorgente. Contenuto letto da CHANGELOG
#   qui sotto (stessa fonte di verita' di questi commenti, tenerli allineati ad
#   ogni nuova versione).
# 1.5.0 (2026-08-19): aggiunto un pannello "Confronto multi-modello per parametro"
#   dopo la legenda, con un grafico per Temperatura, Vento, Raffiche, Pioggia,
#   Pressione, Umidita', Nuvolosita' (e Onda se costiera) che sovrappone tutti i
#   modelli numerici scaricati (linee sottili colorate) al Best Match usato nella
#   tabella sopra (linea blu scura in evidenza) - la tabella stessa resta invariata,
#   mostra sempre solo Best Match. Dati gia' presenti in data.json/marine.json,
#   nessun nuovo fetch. Richiede matplotlib (gia' dipendenza della skill).
SCRIPT_VERSION = "1.5.0"

# Fonte dati per la tabella "Revisioni" mostrata in fondo alla pagina generata
# (vedi build_changelog()): tienila allineata ai commenti di versione qui sopra.
CHANGELOG = [
    ("1.0.0", "Prima versione di produzione: sparkline in filigrana per colonna, "
              "legenda parametri con range osservato, copertura nuvolosa in ottavi, "
              "colonne mare opzionali."),
    ("1.1.0", "Colorazione delle singole celle per gravita' (giallo/arancio/rosso/"
              "fucsia, soglie specifiche per parametro), soglie mostrate in legenda."),
    ("1.2.0", "Aggiunte le colonne Pressione (hPa) e Umidita' (%)."),
    ("1.3.0", "Aggiunta la riga con alba, tramonto e fase lunare prima del titolo."),
    ("1.3.1", "Fix caratteri accentati/speciali illeggibili aprendo il file da disco "
              "(mancava la dichiarazione <meta charset=\"utf-8\">)."),
    ("1.3.2", "Fix sovrapposizione tra il tag del giorno e l'orario 00:00 nella "
              "colonna Data/ora."),
    ("1.4.0", "Allineati tutti gli orari alla stessa colonna; aggiunto il logo "
              "opzionale in alto a destra nell'intestazione."),
    ("1.4.1", "Logo ingrandito (44px -> 72px)."),
    ("1.4.2", "Logo ulteriormente ingrandito (72px -> 104px) e sfondo del logo reso "
              "trasparente."),
    ("1.4.3", "Rebrand: nuovo logo meteogarbino225, angoli smussati."),
    ("1.4.4", "Aggiunta questa tabella delle revisioni in fondo alla pagina."),
    ("1.5.0", "Aggiunto il pannello \"Confronto multi-modello per parametro\": un "
              "grafico per parametro con tutti i modelli numerici sovrapposti al "
              "Best Match usato in tabella. La tabella resta invariata."),
]

# Stessa formula/costanti di moon_phase.py (mese sinodico medio + epoca di
# riferimento nota) - non duplicare logica diversa altrove nella skill.
SYNODIC_MONTH = 29.530588861
REF_NEW_MOON = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)
MOON_PHASE_NAMES = [
    "Luna Nuova", "Luna Crescente", "Primo Quarto", "Gibbosa Crescente",
    "Luna Piena", "Gibbosa Calante", "Ultimo Quarto", "Luna Calante",
]


def moon_phase_label(when):
    age = (when - REF_NEW_MOON).total_seconds() / 86400 % SYNODIC_MONTH
    idx = round(age / (SYNODIC_MONTH / 8)) % 8
    illum = round((1 - math.cos(2 * math.pi * age / SYNODIC_MONTH)) / 2 * 100)
    return f"{MOON_PHASE_NAMES[idx]} ({illum}% illuminata)"


def logo_png_bytes(path):
    """Carica il logo e rende trasparente lo sfondo chiaro/testurizzato (il file
    originale in assets/logo.png non ha canale alpha: sfondo "carta" quasi bianco
    con una leggera grana, non un bianco piatto). Non tocca il file su disco: lo
    fa solo per l'embedding nella tabella, che vive su sfondi diversi (tema chiaro
    e scuro) dove uno sfondo bianco piatto stonerebbe. Soglia a due parametri
    (luminosita' + saturazione) cosi' il testo/icona del logo (saturi, spesso
    scuri) resta intatto mentre lo sfondo (chiaro e desaturato) sparisce."""
    from PIL import Image
    import numpy as np

    im = Image.open(path).convert("RGBA")
    arr = np.array(im).astype(np.float32)
    brightness = arr[..., :3].mean(axis=-1)
    sat = arr[..., :3].max(axis=-1) - arr[..., :3].min(axis=-1)
    bg_bright = np.clip((brightness - 190) / (235 - 190), 0, 1)
    bg_sat = np.clip((30 - sat) / (30 - 8), 0, 1)
    bg_score = bg_bright * bg_sat
    alpha = ((1 - bg_score) * 255).astype(np.uint8)
    arr[..., 3] = np.minimum(arr[..., 3], alpha)

    out = Image.fromarray(arr.astype(np.uint8), "RGBA")
    buf = io.BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()

# Soglie di severita' per singolo parametro (valore >= soglia -> livello), verificate
# dall'alto verso il basso. "li" e "cin" usano logica invertita (valore piu' vicino a
# zero = piu' attenzione), gestita a parte in severity(). Nessuna regola per una
# colonna = cella sempre normale (bianca). Le soglie ricalcano quelle gia' documentate
# in SKILL.md (punto 2) per CAPE/TT/K/SWEAT/Shear, estese agli altri parametri con lo
# stesso criterio (debole/moderato/forte/estremo).
SEVERITY_RULES = {
    "temp":   [(35, "fuchsia"), (32, "red"), (30, "orange"), (28, "yellow")],
    "wind":   [(35, "fuchsia"), (25, "red"), (18, "orange"), (12, "yellow")],
    "precip": [(30, "fuchsia"), (15, "red"), (8, "orange"), (3, "yellow")],
    "sbcape": [(3500, "fuchsia"), (2500, "red"), (1500, "orange"), (500, "yellow")],
    "k":      [(35, "fuchsia"), (30, "red"), (25, "orange"), (20, "yellow")],
    "tt":     [(56, "fuchsia"), (52, "red"), (48, "orange"), (44, "yellow")],
    "sweat":  [(500, "fuchsia"), (400, "red"), (300, "orange"), (250, "yellow")],
    "shear":  [(45, "fuchsia"), (35, "red"), (25, "orange"), (20, "yellow")],
    "srh":    [(250, "fuchsia"), (150, "red"), (100, "orange"), (50, "yellow")],
    "pwat":   [(55, "fuchsia"), (45, "red"), (35, "orange"), (25, "yellow")],
    "wave":   [(4, "fuchsia"), (2.5, "red"), (1.25, "orange"), (0.5, "yellow")],
    # invertite: valore <= soglia -> livello (piu' negativo = piu' instabile/permissivo)
    "li":     [(-9, "fuchsia"), (-6, "red"), (-3, "orange"), (0, "yellow")],
    "cin":    [(-25, "red"), (-75, "orange"), (-150, "yellow")],
}
SEVERITY_INVERTED = {"li", "cin"}


def severity(key, value):
    """Livello di gravita' ('yellow'/'orange'/'red'/'fuchsia') o None (normale)."""
    if value is None:
        return None
    rules = SEVERITY_RULES.get(key)
    if not rules:
        return None
    inverted = key in SEVERITY_INVERTED
    for threshold, level in rules:
        if (value <= threshold) if inverted else (value >= threshold):
            return level
    return None

# (chiave in ogni riga unita, classe CSS colonna, larghezza px, chiave sparkline o None,
#  etichetta header, tooltip/descrizione legenda, unita' di misura per la legenda o None)
BASE_COLS = [
    ("time",   "col-time", 142, None,     "Data / ora", None, None),
    ("temp",   "sc-t",      56, "temp",   "T (°C)", "Temperatura a 2m", "°C"),
    ("wind",   "sc-vt",     60, "wind",   "Vento (kn)", "Vento medio a 10m", "kn"),
    ("dirv",   "dir",       52, None,     "Dir.V", "Direzione del vento", None),
    ("pressure", "sc-pres", 64, "pressure", "Press. (hPa)", "Pressione media sul livello del mare", "hPa"),
    ("humidity", "sc-hum",  56, "humidity", "Umid. (%)", "Umidita' relativa a 2m", "%"),
    ("precip", "sc-pr",     60, "precip", "Pioggia (mm)", "Precipitazione cumulata nelle 3 ore seguenti", "mm"),
    ("cloud",  "sc-cld",    56, "cloud",  "Nuv. (/8)", "Copertura nuvolosa in ottavi (0/8 = cielo sereno, 8/8 = cielo totalmente coperto)", "/8"),
    ("sbcape", "sc-cape",   68, "sbcape", "SBCAPE", "Surface Based CAPE – energia potenziale convettiva disponibile per un aggiornamento partito dal suolo", "J/kg"),
    ("cin",    "sc-cin",    64, "cin",    "CIN", "Convective Inhibition – inibizione convettiva, la “cappa” da vincere perché parta un temporale", "J/kg"),
    ("li",     "sc-li",     44, "li",     "LI", "Lifted Index – quanto piu' negativo, tanto piu' l'atmosfera e' instabile", "°C"),
    ("k",      "sc-k",      40, "k",      "K", "K-Index – gradiente termico e umidita' medio-bassa, indica probabilita' di temporali diffusi", "°C"),
    ("tt",     "sc-tt",     44, "tt",     "TT", "Total Totals Index – simile al K-Index, piu' sensibile all'instabilita' pura", "°C"),
    ("sweat",  "sc-swt",    56, "sweat",  "SWEAT", "SWEAT Index – rischio temporali severi/supercelle non trascurabile sopra 300", None),
    ("shear",  "sc-shear",  62, "shear",  "Shear0-6", "Bulk shear 0-6 km – taglio del vento con la quota, l'ingrediente chiave per organizzare i temporali", "kn"),
    ("srh",    "sc-srh",    62, "srh",    "SRH0-3", "Storm Relative Helicity 0-3 km – rotazione disponibile nei bassi strati", "m²/s²"),
    ("pwat",   "sc-pwat",   52, "pwat",   "PWAT", "Acqua precipitabile (Precipitable Water) – acqua totale in colonna, alta = piu' potenziale per piogge intense", "kg/m²"),
]
MARINE_COLS = [
    ("wave",   "sc-onda",   56, "wave",   "Onda (m)", "Altezza onda significativa", "m"),
    ("diro",   "dir",       52, None,     "Dir.O", "Direzione dell'onda", None),
]
NOTE_COL = ("note", "col-note", 168, None, "Nota", None, None)

DIRS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"]


def dirlabel(d):
    if d is None:
        return "-"
    return DIRS[round(d / 22.5) % 16]


def cloud_okta(pct):
    """Converte copertura nuvolosa da percentuale (Open-Meteo) a ottavi (0-8), scala meteorologica standard."""
    if pct is None:
        return None
    return min(8, max(0, round(pct / 100 * 8)))


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_rows(data, indices, marine):
    bm = data["models"]["best_match"]["hourly"]
    times = bm["time"]
    idx_by_time = {t["time"]: t for t in indices.get("timesteps", [])}

    marine_by_time = {}
    if marine is not None:
        wm = marine.get("wave_models", {}).get("best_match", {})
        if not wm.get("error") and wm.get("hourly"):
            wh = wm["hourly"]
            marine_by_time = {t: i for i, t in enumerate(wh["time"])}

    rows = []
    for i, t in enumerate(times):
        hh = t[11:13]
        if hh not in ("00", "03", "06", "09", "12", "15", "18", "21"):
            continue
        window = [j for j in range(i, min(i + 3, len(times)))]
        precip = sum(bm["precipitation"][j] for j in window if bm["precipitation"][j] is not None)

        ind = idx_by_time.get(t, {})
        cape = ind.get("sbcape_Jkg") or 0
        cin = ind.get("sbcin_Jkg")
        shear = ind.get("shear_0_6km_kn") or 0
        flag = None
        if cape >= 1500 and shear >= 25:
            flag = "organized"
        elif cin is not None and cin >= -75 and cape >= 1000:
            flag = "trigger"

        wave = wave_dir = None
        if marine_by_time and t in marine_by_time:
            mi = marine_by_time[t]
            wh = marine["wave_models"]["best_match"]["hourly"]
            wave = wh["wave_height"][mi]
            wave_dir = wh["wave_direction"][mi]

        rows.append({
            "time": t,
            "temp": bm["temperature_2m"][i],
            "wind": bm["wind_speed_10m"][i],
            "dirv": dirlabel(bm["wind_direction_10m"][i]),
            "pressure": bm["pressure_msl"][i],
            "humidity": bm["relative_humidity_2m"][i],
            "precip": round(precip, 1),
            "cloud": cloud_okta(bm["cloud_cover"][i]),
            "sbcape": cape, "cin": cin, "li": ind.get("lifted_index"),
            "k": ind.get("k_index"), "tt": ind.get("total_totals"),
            "sweat": ind.get("sweat_index"), "shear": shear, "srh": ind.get("srh_0_3km_m2s2"),
            "pwat": ind.get("pwat_kg_m2"),
            "wave": wave, "diro": dirlabel(wave_dir),
            "flag": flag,
        })
    return rows


def make_svg(rows, key, col_w, total_h, color, opacity, halo, halo_opacity, dot_colors):
    """Sparkline con tecnica 'alone+linea': un tratto largo e semitrasparente nel
    colore dell'alone sotto la linea vera e propria, cosi' la linea resta leggibile
    sia sullo sfondo di superficie normale sia sopra le celle colorate per gravita'
    (giallo/arancio/rosso/fucsia) - nessuna delle due tinte e' scelta pensando a un
    solo colore di sfondo possibile."""
    vals = [r[key] for r in rows]
    lo, hi = min(vals), max(vals)
    if hi - lo < 1e-9:
        lo -= 1
        hi += 1
    rng = hi - lo
    pad_x = max(5, col_w * 0.16)
    usable = col_w - 2 * pad_x
    pts, dots = [], []
    for i, r in enumerate(rows):
        x = pad_x + usable * (r[key] - lo) / rng
        y = RH * i + RH / 2
        pts.append(f"{x:.1f},{y:.1f}")
        if r["flag"] == "trigger":
            dots.append((x, y, dot_colors[0]))
        elif r["flag"] == "organized":
            dots.append((x, y, dot_colors[1]))
    poly = " ".join(pts)
    midx = col_w / 2
    circles = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.2" fill="{halo}" fill-opacity="{halo_opacity:.2f}"/>'
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.1" fill="{c}" fill-opacity="0.95"/>'
        for x, y, c in dots
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{col_w}" height="{total_h}">'
        f'<line x1="{midx:.1f}" y1="0" x2="{midx:.1f}" y2="{total_h}" stroke="{halo}" '
        f'stroke-opacity="{halo_opacity*0.5:.2f}" stroke-width="1.4" stroke-dasharray="1.5 3"/>'
        f'<polyline points="{poly}" fill="none" stroke="{halo}" stroke-width="3.4" '
        f'stroke-opacity="{halo_opacity:.2f}" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="1.3" '
        f'stroke-opacity="{opacity:.2f}" stroke-linecap="round" stroke-linejoin="round"/>'
        f'{circles}</svg>'
    )


def b64(svg):
    return base64.b64encode(svg.encode("utf-8")).decode("ascii")


LIGHT_LINE, LIGHT_OP = "#33415E", 0.78
LIGHT_HALO, LIGHT_HALO_OP = "#FFFFFF", 0.60
DARK_LINE, DARK_OP = "#C7D6EC", 0.82
DARK_HALO, DARK_HALO_OP = "#05070C", 0.55
LIGHT_DOTS = ("#B9790E", "#A7362A")
DARK_DOTS = ("#E3A73F", "#E27567")


def build_spark_assets(rows, cols, total_h):
    light_vars, dark_vars, css_rules = [], [], []
    for _, cls, w, skey, _, _, _ in cols:
        if skey is None:
            continue
        svg_l = make_svg(rows, skey, w, total_h, LIGHT_LINE, LIGHT_OP, LIGHT_HALO, LIGHT_HALO_OP, LIGHT_DOTS)
        svg_d = make_svg(rows, skey, w, total_h, DARK_LINE, DARK_OP, DARK_HALO, DARK_HALO_OP, DARK_DOTS)
        light_vars.append(f'    --spark-{cls}: url("data:image/svg+xml;base64,{b64(svg_l)}");')
        dark_vars.append(f'      --spark-{cls}: url("data:image/svg+xml;base64,{b64(svg_d)}");')
        css_rules.append(
            f'  td.{cls} {{ position: relative; z-index: 0; width: {w}px; }}\n'
            f'  td.{cls}::before {{ content: ""; position: absolute; inset: 0; z-index: -1; '
            f'background-image: var(--spark-{cls}); background-repeat: no-repeat; '
            f'background-size: {w}px {total_h}px; background-position: 0 calc(var(--ri, 0) * -{RH}px); '
            f'pointer-events: none; }}'
        )
    return "\n".join(light_vars), "\n".join(dark_vars), "\n".join(css_rules)


def fmt(v):
    return "&ndash;" if v is None else str(v)


def fmt_num(v):
    """Numero per la legenda: interi senza decimali, altrimenti 1 decimale."""
    if float(v).is_integer():
        return str(int(v))
    return f"{v:.1f}"


def build_thresholds_html(key, unit):
    """Chip colorati con le soglie di severita' di una colonna, per la legenda.
    Ordine di lettura sempre giallo->arancio->rosso->fucsia, anche per le colonne a
    logica invertita (li/cin), dove la soglia numerica scende leggendo da sinistra
    verso destra invece di salire."""
    rules = SEVERITY_RULES.get(key)
    if not rules:
        return '<span class="lg-none">&ndash;</span>'
    inverted = key in SEVERITY_INVERTED
    # SEVERITY_RULES e' sempre memorizzato dal piu' severo al meno severo (ordine di
    # verifica in severity()); per la legenda vogliamo sempre l'ordine di lettura
    # crescente giallo->fucsia, quindi si inverte sempre, non solo per le colonne
    # a logica invertita (bug corretto il 2026-08-16: qui prima si invertiva solo
    # se "inverted", lasciando le colonne normali in ordine fucsia->giallo).
    ordered = list(reversed(rules))
    unit_s = f"{unit}" if unit else ""
    cmp = "&le;" if inverted else "&ge;"
    return " ".join(
        f'<span class="chip chip-{level}">{cmp}{fmt_num(threshold)}{unit_s}</span>'
        for threshold, level in ordered
    )


def build_legend(rows, cols):
    items = []
    for _, _, _, skey, label, desc, unit in cols:
        if skey is None:
            continue
        vals = [r[skey] for r in rows]
        lo, hi = min(vals), max(vals)
        unit_s = f" {unit}" if unit else ""
        if abs(hi - lo) < 1e-9:
            campo = f"costante: {fmt_num(lo)}{unit_s}"
        else:
            campo = f"da {fmt_num(lo)} a {fmt_num(hi)}{unit_s}"
        soglie = build_thresholds_html(skey, unit)
        items.append((label, desc, campo, soglie))

    rows_html = "\n".join(
        f'<tr><td class="lg-param">{label}</td><td class="lg-desc">{desc}</td>'
        f'<td class="lg-range">{campo}</td><td class="lg-thresh">{soglie}</td></tr>'
        for label, desc, campo, soglie in items
    )
    return rows_html


def build_changelog():
    return "\n".join(
        f'<tr><td class="cl-version">v{version}</td><td class="cl-note">{note}</td></tr>'
        for version, note in CHANGELOG
    )


MODEL_CHART_COLORS = ["#4C6EF5", "#F76707", "#37B24D", "#E64980", "#7048E8",
                       "#12B886", "#F59F00", "#1098AD", "#E03131", "#5C7CFA",
                       "#099268", "#9C36B5"]
GIORNI_IT = ["lun", "mar", "mer", "gio", "ven", "sab", "dom"]

# Un grafico per parametro (Temperatura, Vento, Raffiche, Pioggia, Pressione,
# Umidita', Nuvolosita', +Onda se costiera): key nel dizionario modelli,
# titolo, etichetta asse Y, unita'.
MODEL_CHART_SPECS = [
    ("temperature_2m", "Temperatura a 2m", "Temperatura", "°C"),
    ("wind_speed_10m", "Velocita' del vento a 10m", "Vento", "kn"),
    ("wind_gusts_10m", "Raffiche di vento a 10m", "Raffiche", "kn"),
    ("precipitation", "Precipitazione oraria", "Pioggia", "mm"),
    ("pressure_msl", "Pressione al livello del mare", "Pressione", "hPa"),
    ("relative_humidity_2m", "Umidita' relativa a 2m", "Umidita'", "%"),
    ("cloud_cover", "Copertura nuvolosa", "Nuvolosita'", "%"),
]


def build_model_charts(data, marine, has_marine):
    """Un PNG (base64) per parametro: tutti i modelli scaricati sovrapposti al
    Best Match usato nella tabella. Auto-contenuto (non importa charts.py) per
    non introdurre una dipendenza tra i due script standalone della skill."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.ticker import FuncFormatter

    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 10,
        "axes.edgecolor": "#888888", "axes.grid": True,
        "grid.alpha": 0.25, "grid.linestyle": "--",
        "axes.spines.top": False, "axes.spines.right": False,
        "figure.facecolor": "white", "axes.facecolor": "white",
    })

    def parse_times(strs):
        return [dt.datetime.fromisoformat(s) for s in strs]

    def day_label(x, pos=None):
        d = mdates.num2date(x)
        return f"{GIORNI_IT[d.weekday()]} {d.strftime('%d/%m')}"

    def fmt_time_axis(ax):
        ax.xaxis.set_major_locator(mdates.DayLocator())
        ax.xaxis.set_major_formatter(FuncFormatter(day_label))
        ax.xaxis.set_minor_locator(mdates.HourLocator(byhour=[6, 12, 18]))
        ax.xaxis.set_minor_formatter(mdates.DateFormatter("%Hh"))
        ax.tick_params(axis="x", which="minor", labelsize=7, colors="#777777")
        ax.tick_params(axis="x", which="major", labelsize=9, pad=14)

    def chart_png_b64(model_dict, var, title, ylabel, unit):
        series = [(mk, mv) for mk, mv in model_dict.items()
                  if not mv.get("error") and mv.get("hourly") and var in (mv.get("hourly") or {})]
        if not series:
            return None
        fig, ax = plt.subplots(figsize=(9, 3.4))
        best = None
        i = 0
        for mk, mv in series:
            times = parse_times(mv["hourly"]["time"])
            vals = mv["hourly"][var]
            if mk == "best_match":
                best = (times, vals)
                continue
            ax.plot(times, vals, color=MODEL_CHART_COLORS[i % len(MODEL_CHART_COLORS)],
                    linewidth=1.1, alpha=0.75, label=mv.get("label", mk))
            i += 1
        if best:
            ax.plot(best[0], best[1], color="#1a1a2e", linewidth=2.6,
                    label="Best Match (usato in tabella)", zorder=10)
        ax.set_title(title, fontsize=12, fontweight="bold", loc="left")
        ax.set_ylabel(f"{ylabel} ({unit})" if unit else ylabel)
        fmt_time_axis(ax)
        ax.legend(fontsize=7, ncol=2, loc="upper left", bbox_to_anchor=(1.01, 1.0), frameon=False)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    panels = []
    for var, title, ylabel, unit in MODEL_CHART_SPECS:
        b64 = chart_png_b64(data["models"], var, title, ylabel, unit)
        if b64:
            panels.append((title, b64))

    if has_marine and marine:
        b64 = chart_png_b64(marine.get("wave_models", {}), "wave_height",
                             "Altezza onda significativa", "Onda", "m")
        if b64:
            panels.append(("Altezza onda significativa", b64))

    return panels


def build_model_charts_html(panels):
    if not panels:
        return ""
    figures = "\n".join(
        f'    <img class="model-chart" src="data:image/png;base64,{b64}" alt="{title}">'
        for title, b64 in panels
    )
    return f'''
  <div class="panel model-charts">
    <h2>Confronto multi-modello per parametro</h2>
    <p class="model-charts-note">La tabella sopra usa sempre il solo modello Best
      Match (blend automatico). Qui, per ogni parametro, tutti i modelli numerici
      scaricati per questa localita' sono sovrapposti (linea sottile colorata) al
      Best Match (linea blu scura in evidenza) &mdash; utile per vedere quanto
      concordano o divergono tra loro.</p>
{figures}
  </div>'''


DAY_ABBR = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]


def day_tag(iso_date):
    d = dt.date.fromisoformat(iso_date)
    return f"{DAY_ABBR[d.weekday()]} {d.strftime('%d/%m')}"


def build_tbody(rows):
    trs = []
    prev_day = None
    for i, r in enumerate(rows):
        date_part, hhmm = r["time"][:10], r["time"][11:16]
        day_change = date_part != prev_day
        prev_day = date_part

        classes = []
        if r["flag"] == "organized":
            classes.append("risk-organized")
        elif r["flag"] == "trigger":
            classes.append("risk-trigger")
        if day_change:
            classes.append("day-start")
        cls_attr = f' class="{" ".join(classes)}"' if classes else ""

        day_cell = f'<span class="day-tag">{day_tag(date_part)}</span>' if day_change else ""

        if r["flag"] == "organized":
            pill = '<span class="pill pill-organized">Temporali organizzati</span>'
        elif r["flag"] == "trigger":
            pill = '<span class="pill pill-trigger">Innesco possibile</span>'
        else:
            pill = '<span class="pill pill-none">&ndash;</span>'

        def cell(cls, key):
            value = r[key]
            sev = severity(key, value)
            sev_cls = f" sev-{sev}" if sev else ""
            return f'<td class="{cls} num{sev_cls}">{fmt(value)}</td>'

        cells = [
            f'<td class="col-time"><span class="day-tag-slot">{day_cell}</span><span class="time-val">{hhmm}</span></td>',
            cell("sc-t", "temp"),
            cell("sc-vt", "wind"),
            f'<td class="dir">{r["dirv"]}</td>',
            cell("sc-pres", "pressure"),
            cell("sc-hum", "humidity"),
            cell("sc-pr", "precip"),
            f'<td class="sc-cld num">{fmt(r["cloud"])}</td>',
            cell("sc-cape", "sbcape"),
            cell("sc-cin", "cin"),
            cell("sc-li", "li"),
            cell("sc-k", "k"),
            cell("sc-tt", "tt"),
            cell("sc-swt", "sweat"),
            cell("sc-shear", "shear"),
            cell("sc-srh", "srh"),
            cell("sc-pwat", "pwat"),
        ]
        if "wave" in r:
            cells.append(cell("sc-onda", "wave"))
            cells.append(f'<td class="dir">{r["diro"]}</td>')
        cells.append(f'<td class="col-note">{pill}</td>')

        trs.append(f'<tr{cls_attr} style="--ri:{i}">\n' + "\n".join(cells) + "\n</tr>")
    return "\n".join(trs)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="data.json (fetch_forecast.py)")
    ap.add_argument("--indices", required=True, help="indices.json (indices.py)")
    ap.add_argument("--marine", default=None, help="marine.json (fetch_marine.py), opzionale")
    ap.add_argument("--location-label", default=None, help="Etichetta localita' per il titolo; default dal geocoding")
    ap.add_argument("--logo", default=None, help="logo.png (opzionale) da mostrare in alto a destra")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    data = load(args.data)
    indices = load(args.indices)
    marine = load(args.marine) if args.marine else None

    rows = build_rows(data, indices, marine)
    # se nessuna riga ha un valore mare valido, non mostrare le colonne mare
    has_marine = any(r.get("wave") is not None for r in rows)

    cols = list(BASE_COLS)
    if has_marine:
        cols += MARINE_COLS
    cols.append(NOTE_COL)

    if not has_marine:
        for r in rows:
            r.pop("wave", None)
            r.pop("diro", None)

    n = len(rows)
    total_h = RH * n
    total_w = sum(w for _, _, w, _, _, _, _ in cols)

    light_vars, dark_vars, spark_rules = build_spark_assets(rows, cols, total_h)
    tbody = build_tbody(rows)

    colgroup = "\n".join(f'<col style="width:{w}px">' for _, _, w, _, _, _, _ in cols)

    loc = args.location_label or data["location"]["name"]
    lat, lon = data["location"]["lat"], data["location"]["lon"]
    p_start, p_end = data["period"]["start"], data["period"]["end"]
    start_label = dt.date.fromisoformat(p_start).strftime("%d/%m/%Y")
    end_label = dt.date.fromisoformat(p_end).strftime("%d/%m/%Y")
    generated = dt.datetime.now().strftime("%d/%m/%Y %H:%M")

    daily = data["models"]["best_match"].get("daily") or {}
    sunrise_list, sunset_list = daily.get("sunrise"), daily.get("sunset")
    sunrise = sunrise_list[0][11:16] if sunrise_list else None
    sunset = sunset_list[0][11:16] if sunset_list else None
    moon_line = moon_phase_label(dt.datetime.fromisoformat(p_start).replace(
        hour=12, tzinfo=dt.timezone.utc))
    astro_parts = []
    if sunrise and sunset:
        astro_parts.append(f"Alba {sunrise} &middot; Tramonto {sunset} ({start_label})")
    astro_parts.append(moon_line)
    astro_line = " &middot; ".join(astro_parts)

    logo_html = ""
    if args.logo:
        logo_b64 = base64.b64encode(logo_png_bytes(args.logo)).decode("ascii")
        logo_html = f'<img class="head-logo" src="data:image/png;base64,{logo_b64}" alt="meteogarbino225">'

    header_cells = [
        '<th class="col-time">Data / ora</th>',
        '<th><abbr title="Temperatura a 2m">T (&deg;C)</abbr></th>',
        '<th><abbr title="Vento medio a 10m">Vento (kn)</abbr></th>',
        '<th><abbr title="Direzione del vento">Dir.V</abbr></th>',
        '<th><abbr title="Pressione media sul livello del mare">Press. (hPa)</abbr></th>',
        '<th><abbr title="Umidita\' relativa a 2m">Umid. (%)</abbr></th>',
        '<th><abbr title="Precipitazione cumulata nelle 3 ore seguenti">Pioggia (mm)</abbr></th>',
        '<th><abbr title="Copertura nuvolosa in ottavi (0/8 = sereno, 8/8 = coperto)">Nuv. (/8)</abbr></th>',
        '<th><abbr title="Surface Based CAPE &ndash; energia potenziale convettiva disponibile">SBCAPE</abbr></th>',
        '<th><abbr title="Convective Inhibition &ndash; inibizione convettiva (la &quot;cappa&quot;)">CIN</abbr></th>',
        '<th><abbr title="Lifted Index">LI</abbr></th>',
        '<th><abbr title="K-Index">K</abbr></th>',
        '<th><abbr title="Total Totals Index">TT</abbr></th>',
        '<th><abbr title="SWEAT Index &ndash; rischio temporali severi/supercelle oltre 300">SWEAT</abbr></th>',
        '<th><abbr title="Bulk shear 0-6 km">Shear0-6</abbr></th>',
        '<th><abbr title="Storm Relative Helicity 0-3 km">SRH0-3</abbr></th>',
        '<th><abbr title="Acqua precipitabile (Precipitable Water)">PWAT</abbr></th>',
    ]
    if has_marine:
        header_cells.append('<th><abbr title="Altezza onda significativa">Onda (m)</abbr></th>')
        header_cells.append('<th><abbr title="Direzione dell\'onda">Dir.O</abbr></th>')
    header_cells.append('<th>Nota</th>')

    group_row = (
        '<tr class="group-row"><th class="g-time">&nbsp;</th>'
        '<th colspan="7">Atmosfera</th>'
        '<th colspan="9">Convezione (MetPy)</th>'
        + ('<th colspan="2">Mare</th>' if has_marine else '')
        + '<th class="g-note">&nbsp;</th></tr>'
    )

    legend_rows = build_legend(rows, cols)
    changelog_rows = build_changelog()
    model_chart_panels = build_model_charts(data, marine, has_marine)
    model_charts_html = build_model_charts_html(model_chart_panels)

    html = TEMPLATE.format(
        loc=loc, lat=lat, lon=lon, start=start_label, end=end_label, generated=generated,
        light_vars=light_vars, dark_vars=dark_vars, spark_rules=spark_rules,
        colgroup=colgroup, group_row=group_row, header_cells="\n            ".join(header_cells),
        tbody=tbody, total_w=max(total_w, 900), rh=RH, legend_rows=legend_rows, version=SCRIPT_VERSION,
        changelog_rows=changelog_rows, model_charts_html=model_charts_html,
        astro_line=astro_line, logo_html=logo_html,
        marine_title=" e mare" if has_marine else "",
        marine_sub="; onda da Open-Meteo Marine" if has_marine else "",
        marine_footer=" &middot; stato del mare Open-Meteo Marine" if has_marine else "",
    )

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK -> {args.out} ({n} righe, mare: {'si' if has_marine else 'no'})")


TEMPLATE = '''<meta charset="utf-8">
<title>Tabella Convettiva {loc}</title>
<style>
  :root {{
    --paper: #F3F6F9;
    --surface: #FFFFFF;
    --surface-2: #EBF0F5;
    --line: #DCE3EB;
    --line-soft: #E9EEF3;
    --text: #131C2C;
    --text-soft: #56647A;
    --text-faint: #8494AA;
    --navy: #101B33;
    --navy-2: #1B2C4C;
    --amber: #B9790E;
    --amber-bg: #FBF0DC;
    --storm: #A7362A;
    --storm-bg: #FBE6E2;
    --sea: #146B72;
    --shadow: 0 1px 2px rgba(16, 27, 51, 0.06), 0 8px 24px -12px rgba(16, 27, 51, 0.18);
    --row-hover: rgba(16, 27, 51, 0.045);
    --sev-yellow: #F9E8B4; --sev-yellow-ink: #8F7014;
    --sev-orange: #F9D2B4; --sev-orange-ink: #8F4914;
    --sev-red: #F9B8B4; --sev-red-ink: #8F1D14;
    --sev-fuchsia: #F9B4E4; --sev-fuchsia-ink: #8F146A;
{light_vars}
  }}

  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --paper: #0A111D;
      --surface: #101928;
      --surface-2: #16223640;
      --line: #263349;
      --line-soft: #1C283C;
      --text: #E7ECF4;
      --text-soft: #9CACC4;
      --text-faint: #64768F;
      --navy: #0C1526;
      --navy-2: #182338;
      --amber: #E3A73F;
      --amber-bg: #2E260F;
      --storm: #E27567;
      --storm-bg: #331714;
      --sea: #55C2C9;
      --shadow: 0 1px 2px rgba(0, 0, 0, 0.4), 0 8px 24px -12px rgba(0, 0, 0, 0.6);
      --row-hover: rgba(231, 236, 244, 0.06);
      --sev-yellow: #433714; --sev-yellow-ink: #EDD282;
      --sev-orange: #432814; --sev-orange-ink: #EDB082;
      --sev-red: #431714; --sev-red-ink: #ED8982;
      --sev-fuchsia: #431435; --sev-fuchsia-ink: #ED82CD;
{dark_vars}
    }}
  }}

  :root[data-theme="dark"] {{
    --paper: #0A111D;
    --surface: #101928;
    --surface-2: #16223640;
    --line: #263349;
    --line-soft: #1C283C;
    --text: #E7ECF4;
    --text-soft: #9CACC4;
    --text-faint: #64768F;
    --navy: #0C1526;
    --navy-2: #182338;
    --amber: #E3A73F;
    --amber-bg: #2E260F;
    --storm: #E27567;
    --storm-bg: #331714;
    --sea: #55C2C9;
    --shadow: 0 1px 2px rgba(0, 0, 0, 0.4), 0 8px 24px -12px rgba(0, 0, 0, 0.6);
    --row-hover: rgba(231, 236, 244, 0.06);
    --sev-yellow: #433714; --sev-yellow-ink: #EDD282;
    --sev-orange: #432814; --sev-orange-ink: #EDB082;
    --sev-red: #431714; --sev-red-ink: #ED8982;
    --sev-fuchsia: #431435; --sev-fuchsia-ink: #ED82CD;
{dark_vars}
  }}

  * {{ box-sizing: border-box; }}

  body {{
    margin: 0;
    background: var(--paper);
    color: var(--text);
    font-family: ui-sans-serif, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    padding: clamp(16px, 4vw, 40px);
    display: flex;
    justify-content: center;
  }}

  .sheet {{ width: 100%; max-width: 1180px; display: flex; flex-direction: column; gap: 18px; }}

  header.head {{
    display: flex; flex-direction: row; align-items: flex-start; justify-content: space-between;
    gap: 16px; padding: 4px 2px 2px;
  }}

  .head-text {{ display: flex; flex-direction: column; gap: 6px; min-width: 0; }}

  .head-logo {{ height: 104px; width: auto; flex: none; border-radius: 18px; }}

  .eyebrow {{
    font-size: 11.5px; font-weight: 700; letter-spacing: 0.09em;
    text-transform: uppercase; color: var(--sea);
  }}

  .astro {{ font-size: 12px; color: var(--text-faint); }}

  h1 {{
    margin: 0; font-size: clamp(20px, 2.6vw, 26px); font-weight: 700;
    letter-spacing: -0.01em; text-wrap: balance; color: var(--text);
  }}

  .sub {{ margin: 0; font-size: 13.5px; color: var(--text-soft); line-height: 1.5; max-width: 76ch; }}

  .legend {{
    display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center;
    padding: 12px 16px; background: var(--surface); border: 1px solid var(--line);
    border-radius: 10px; box-shadow: var(--shadow);
  }}

  .legend-item {{ display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--text-soft); }}

  .swatch {{ width: 12px; height: 12px; border-radius: 3px; flex: none; }}
  .swatch.trigger {{ background: var(--amber); }}
  .swatch.organized {{ background: var(--storm); }}
  .swatch.line {{ width: 16px; height: 2px; border-radius: 1px; background: var(--text-faint); }}

  .legend-sep {{ width: 1px; height: 16px; background: var(--line); }}

  .panel {{
    background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
    box-shadow: var(--shadow); overflow: hidden;
  }}

  .scroll {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}

  .data-table {{
    border-collapse: separate; border-spacing: 0; width: 100%; min-width: {total_w}px;
    table-layout: fixed; font-variant-numeric: tabular-nums;
  }}

  .data-table thead th {{
    position: sticky; top: 0; z-index: 3; background: var(--navy); color: #EAF0FA;
    font-weight: 600; text-align: right; padding: 7px 10px; font-size: 11px;
    letter-spacing: 0.01em; border-bottom: 1px solid var(--navy-2); white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis;
  }}

  .data-table thead tr.group-row th {{
    top: 0; z-index: 4; background: var(--navy-2); font-size: 10px; font-weight: 700;
    letter-spacing: 0.08em; text-transform: uppercase; color: #B9C6DE; text-align: center;
    padding: 6px 8px 5px; border-bottom: 1px solid var(--navy);
  }}

  .data-table thead tr.col-row th {{ top: 26px; }}

  .data-table thead th abbr {{ text-decoration: none; border-bottom: 1px dotted rgba(234, 240, 250, 0.45); cursor: help; }}

  .data-table thead th.col-time, .data-table thead th.col-note,
  .data-table .group-row th.g-time, .data-table .group-row th.g-note {{ text-align: left; }}

  .data-table th.col-time, .data-table td.col-time {{
    position: sticky; left: 0; z-index: 2; text-align: left; background: var(--surface);
    box-shadow: 1px 0 0 var(--line);
  }}

  .data-table thead th.col-time {{ z-index: 5; background: var(--navy); }}
  .data-table thead tr.group-row th.g-time {{ z-index: 5; background: var(--navy-2); }}

  .data-table tbody tr {{ height: {rh}px; }}

  .data-table tbody td {{
    height: {rh}px; padding: 0 10px; font-size: 12px; text-align: right;
    border-bottom: 1px solid var(--line-soft); color: var(--text); white-space: nowrap; overflow: hidden;
  }}

  .data-table tbody tr:hover td:not([class*="sev-"]) {{ background: var(--row-hover); }}
  .data-table tbody tr:hover td.col-time {{ background: var(--row-hover); }}

  .data-table td.sev-yellow {{ background-color: var(--sev-yellow); }}
  .data-table td.sev-orange {{ background-color: var(--sev-orange); }}
  .data-table td.sev-red {{ background-color: var(--sev-red); }}
  .data-table td.sev-fuchsia {{ background-color: var(--sev-fuchsia); }}

  .data-table td.col-time {{ display: flex; align-items: center; gap: 8px; font-weight: 600; font-variant-numeric: tabular-nums; }}

  .data-table .day-tag-slot {{ display: inline-flex; flex: none; width: 70px; }}

  .data-table .day-tag {{
    font-size: 10px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
    color: var(--sea); background: color-mix(in srgb, var(--sea) 14%, transparent);
    padding: 2px 6px; border-radius: 5px; white-space: nowrap;
  }}

  .data-table td.dir {{ text-align: center; color: var(--text-soft); font-size: 11.5px; }}
  .data-table td.col-note {{ text-align: left; }}

  .data-table tr.day-start td.col-time {{ box-shadow: 1px 0 0 var(--line), inset 0 2px 0 var(--line); }}
  .data-table tr.risk-trigger td.col-time {{ box-shadow: 1px 0 0 var(--line), inset 3px 0 0 var(--amber); }}
  .data-table tr.risk-organized td.col-time {{ box-shadow: 1px 0 0 var(--line), inset 3px 0 0 var(--storm); }}
  .data-table tr.day-start.risk-trigger td.col-time {{ box-shadow: 1px 0 0 var(--line), inset 0 2px 0 var(--line), inset 3px 0 0 var(--amber); }}
  .data-table tr.day-start.risk-organized td.col-time {{ box-shadow: 1px 0 0 var(--line), inset 0 2px 0 var(--line), inset 3px 0 0 var(--storm); }}
  .data-table tr.day-start td:not(.col-time) {{ box-shadow: inset 0 2px 0 var(--line); }}

  .pill {{ display: inline-block; font-size: 10.5px; font-weight: 700; letter-spacing: 0.02em; padding: 3px 9px; border-radius: 999px; }}
  .pill-none {{ color: var(--text-faint); font-weight: 500; }}
  .pill-trigger {{ background: var(--amber-bg); color: var(--amber); }}
  .pill-organized {{ background: var(--storm-bg); color: var(--storm); }}

{spark_rules}

  .glossary {{ display: flex; flex-direction: column; gap: 10px; padding: 16px; }}

  .glossary h2 {{
    margin: 0; font-size: 13.5px; font-weight: 700; color: var(--text);
    letter-spacing: -0.005em;
  }}

  .glossary-table {{ border-collapse: separate; border-spacing: 0; width: 100%; }}

  .glossary-table th {{
    background: var(--navy); color: #EAF0FA; font-weight: 600; font-size: 10.5px;
    letter-spacing: 0.03em; text-transform: uppercase; text-align: left;
    padding: 7px 12px; white-space: nowrap;
  }}

  .glossary-table th:first-child {{ border-top-left-radius: 6px; }}
  .glossary-table th:last-child {{ border-top-right-radius: 6px; }}

  .glossary-table td {{
    padding: 7px 12px; font-size: 12.5px; border-bottom: 1px solid var(--line-soft);
    color: var(--text); vertical-align: top;
  }}

  .glossary-table tr:last-child td {{ border-bottom: none; }}
  .glossary-table tr:hover td {{ background: var(--row-hover); }}

  .glossary-table td.lg-param {{
    font-weight: 700; white-space: nowrap; color: var(--sea);
    font-variant-numeric: tabular-nums;
  }}

  .glossary-table td.lg-desc {{ color: var(--text-soft); line-height: 1.4; }}

  .glossary-table td.lg-range {{
    white-space: nowrap; text-align: left; font-variant-numeric: tabular-nums;
    color: var(--text); font-weight: 600;
  }}

  .glossary-table td.lg-thresh {{ white-space: nowrap; font-variant-numeric: tabular-nums; }}
  .glossary-table .lg-none {{ color: var(--text-faint); }}

  .chip {{
    display: inline-block; padding: 2px 7px; border-radius: 6px;
    font-size: 11px; font-weight: 700; margin-right: 3px;
  }}
  .chip-yellow {{ background: var(--sev-yellow); color: var(--sev-yellow-ink); }}
  .chip-orange {{ background: var(--sev-orange); color: var(--sev-orange-ink); }}
  .chip-red {{ background: var(--sev-red); color: var(--sev-red-ink); }}
  .chip-fuchsia {{ background: var(--sev-fuchsia); color: var(--sev-fuchsia-ink); }}

  @media (max-width: 640px) {{
    .glossary-table th:nth-child(2), .glossary-table td.lg-desc {{ display: none; }}
  }}

  .changelog {{ display: flex; flex-direction: column; gap: 10px; padding: 16px; }}

  .changelog h2 {{
    margin: 0; font-size: 13.5px; font-weight: 700; color: var(--text);
    letter-spacing: -0.005em;
  }}

  .changelog-table {{ border-collapse: separate; border-spacing: 0; width: 100%; }}

  .changelog-table th {{
    background: var(--navy); color: #EAF0FA; font-weight: 600; font-size: 10.5px;
    letter-spacing: 0.03em; text-transform: uppercase; text-align: left;
    padding: 7px 12px; white-space: nowrap;
  }}

  .changelog-table th:first-child {{ border-top-left-radius: 6px; }}
  .changelog-table th:last-child {{ border-top-right-radius: 6px; }}

  .changelog-table td {{
    padding: 7px 12px; font-size: 12.5px; border-bottom: 1px solid var(--line-soft);
    color: var(--text); vertical-align: top;
  }}

  .changelog-table tr:last-child td {{ border-bottom: none; }}
  .changelog-table tr:hover td {{ background: var(--row-hover); }}

  .changelog-table td.cl-version {{
    font-weight: 700; white-space: nowrap; color: var(--sea);
    font-variant-numeric: tabular-nums;
  }}

  .changelog-table td.cl-note {{ color: var(--text-soft); line-height: 1.4; text-align: left; }}

  .model-charts {{ display: flex; flex-direction: column; gap: 12px; padding: 16px; }}

  .model-charts h2 {{
    margin: 0; font-size: 13.5px; font-weight: 700; color: var(--text);
    letter-spacing: -0.005em;
  }}

  .model-charts-note {{ margin: 0; font-size: 12px; line-height: 1.5; color: var(--text-soft); }}

  .model-chart {{
    width: 100%; height: auto; display: block; border-radius: 6px;
    border: 1px solid var(--line-soft); background: #fff;
  }}

  footer.foot {{
    display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px;
    padding: 2px 4px; font-size: 11px; color: var(--text-faint);
  }}

  @media (max-width: 640px) {{ .legend {{ font-size: 11.5px; }} }}
</style>

<div class="sheet">
  <header class="head">
    <div class="head-text">
      <span class="eyebrow">{loc} &middot; {lat:.2f}&deg;N {lon:.2f}&deg;E</span>
      <span class="astro">{astro_line}</span>
      <h1>Tabella tri-oraria &mdash; parametri convettivi, vento{marine_title} e pioggia</h1>
      <p class="sub">{start}&ndash;{end}, ogni 3 ore (00&ndash;21 locali). Blend Best Match (Open-Meteo);
        indici convettivi calcolati con MetPy sul profilo verticale orario{marine_sub}. Ogni colonna numerica
        porta in filigrana il proprio andamento (scala min&ndash;max propria della colonna, non comparabile tra colonne diverse)
        e uno sfondo colorato quando il singolo valore esce dalla norma per quel parametro (soglie specifiche per colonna,
        vedi Legenda parametri in fondo alla pagina).</p>
    </div>
    {logo_html}
  </header>

  <div class="legend">
    <div class="legend-item"><span class="swatch line"></span>Linea = andamento del valore scorrendo nel tempo</div>
    <div class="legend-sep"></div>
    <div class="legend-item"><span class="swatch trigger"></span>Innesco possibile &mdash; CIN &ge; &minus;75 J/kg con SBCAPE &ge; 1000 J/kg</div>
    <div class="legend-sep"></div>
    <div class="legend-item"><span class="swatch organized"></span>Temporali organizzati &mdash; SBCAPE &ge; 1500 J/kg con Shear 0&ndash;6km &ge; 25 kn</div>
    <div class="legend-sep"></div>
    <div class="legend-item">
      Cella colorata = valore fuori norma:
      <span class="chip chip-yellow">lieve</span>
      <span class="chip chip-orange">moderato</span>
      <span class="chip chip-red">elevato</span>
      <span class="chip chip-fuchsia">estremo</span>
    </div>
  </div>

  <div class="panel">
    <div class="scroll">
      <table class="data-table">
        <colgroup>
{colgroup}
        </colgroup>
        <thead>
          {group_row}
          <tr class="col-row">
            {header_cells}
          </tr>
        </thead>
        <tbody>
{tbody}
        </tbody>
      </table>
    </div>
  </div>

  <div class="panel glossary">
    <h2>Legenda parametri</h2>
    <table class="glossary-table">
      <thead>
        <tr><th>Parametro</th><th>Descrizione</th><th>Campo in questo periodo</th><th>Soglie colore (giallo&rarr;fucsia)</th></tr>
      </thead>
      <tbody>
{legend_rows}
      </tbody>
    </table>
  </div>
{model_charts_html}

  <div class="panel changelog">
    <h2>Revisioni</h2>
    <table class="changelog-table">
      <thead>
        <tr><th>Versione</th><th>Novita' introdotte</th></tr>
      </thead>
      <tbody>
{changelog_rows}
      </tbody>
    </table>
  </div>

  <footer class="foot">
    <span>Fonte dati: Open-Meteo (blend Best Match) &middot; indici convettivi calcolati con MetPy{marine_footer}</span>
    <span>Generato {generated} &middot; Tabella convettiva v{version}</span>
  </footer>
</div>
'''


if __name__ == "__main__":
    main()
