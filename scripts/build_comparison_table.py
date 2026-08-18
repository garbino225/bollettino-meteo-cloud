#!/usr/bin/env python3
"""
Genera la tabella HTML di confronto multi-modello (severita' a colori, linea di
tendenza a sfondo, vento/onda con direzione) a partire da dati REALI scaricati
con fetch_forecast.py (e opzionalmente fetch_marine.py per localita' costiere).

Non scarica nulla da solo: prende in input i JSON gia' prodotti da quegli
script, li trasforma nella forma richiesta da table_engine.js e scrive un
singolo file HTML autonomo (CSS+JS incorporati, nessuna dipendenza esterna
salvo i Google Fonts).

Uso:
    python3 build_comparison_table.py --data data.json --mode daily \
        --title "Bologna" --moon-dir /tmp/moon --out bollettino_bologna.html

    python3 build_comparison_table.py --data data.json --marine marine.json \
        --mode hourly --title "Punta Marina" --moon-dir /tmp/moon --out out.html
"""
import argparse
import datetime as dt
import glob
import json
import math
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Mappa model-id Open-Meteo -> {codice breve, gruppo}. "best_match" e'
# volutamente escluso dal confronto: e' un blend automatico, non un modello
# distinto, includerlo falserebbe la media.
MODEL_META = {
    "ecmwf_ifs025":                {"code": "ECMWF",      "full": "ECMWF IFS — globale", "group": "globale"},
    "gfs_seamless":                {"code": "GFS",        "full": "NOAA GFS — globale", "group": "globale"},
    "icon_seamless":                {"code": "ICON",       "full": "DWD ICON — globale", "group": "globale"},
    "icon_eu":                      {"code": "ICON-EU",    "full": "DWD ICON-EU — area limitata Europa 13km", "group": "locale"},
    "icon_d2":                      {"code": "ICON-D2",    "full": "DWD ICON-D2 — area limitata 2km", "group": "locale"},
    "meteofrance_arpege_europe":    {"code": "ARPEGE",     "full": "Météo-France ARPEGE — globale", "group": "globale"},
    "meteofrance_arome_france_hd":  {"code": "AROME",      "full": "Météo-France AROME — area limitata Francia 1.3km", "group": "locale"},
    "gem_seamless":                  {"code": "GEM",        "full": "ECCC GEM (Canada) — globale", "group": "globale"},
    "ukmo_seamless":                {"code": "UKMO",       "full": "Met Office UM — globale", "group": "globale"},
    "knmi_harmonie_arome_europe":   {"code": "HARMONIE",   "full": "KNMI HARMONIE-AROME — area limitata Europa/Benelux", "group": "locale"},
    "chmi_aladin_seamless":         {"code": "ALADIN",     "full": "CHMI ALADIN — area limitata Europa centrale", "group": "locale"},
    "italia_meteo_arpae_icon_2i":   {"code": "ICON-2I",    "full": "ItaliaMeteo/ARPAE ICON-2I — LAM Italia 2km", "group": "locale"},
}

WAVE_MODEL_META = {
    "ecmwf_wam025":     {"code": "ECMWF-WAM", "full": "ECMWF WAM — onda globale", "group": "onda"},
    "meteofrance_wave": {"code": "MFWAM",     "full": "Météo-France MFWAM — onda globale", "group": "onda"},
    "ncep_gfswave025":  {"code": "GFS-Wave",  "full": "NOAA GFS-Wave — onda globale", "group": "onda"},
    "dwd_ewam":         {"code": "EWAM",      "full": "DWD EWAM — onda Europa", "group": "onda"},
    "dwd_gwam":         {"code": "GWAM",      "full": "DWD GWAM — onda globale", "group": "onda"},
}

IT_MONTHS = ["", "gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
IT_WEEKDAYS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]


def cardinal(deg):
    if deg is None:
        return None
    dirs = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
    idx = int(((deg % 360) + 22.5) // 45) % 8
    return dirs[idx]


def circular_mean_deg(degs):
    vals = [d for d in degs if d is not None]
    if not vals:
        return None
    sx = sum(math.sin(math.radians(d)) for d in vals)
    cx = sum(math.cos(math.radians(d)) for d in vals)
    if sx == 0 and cx == 0:
        return None
    return math.degrees(math.atan2(sx, cx)) % 360


def lcl_km(t, td):
    if t is None or td is None:
        return None
    return max(0.05, (t - td) * 0.125)


def parse_date_label(iso_date):
    y, m, d = iso_date.split("-")
    wd = dt.date(int(y), int(m), int(d)).weekday()
    return {"d": IT_WEEKDAYS[wd], "date": f"{d}/{m}"}


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def first_ok(models_dict, keys=None):
    for mk, v in models_dict.items():
        if keys and mk not in keys:
            continue
        if not v.get("error"):
            return mk, v
    return None, None


def build(args):
    data = load_json(args.data)
    models = data["models"]
    loc = data["location"]
    ok_model_ids = [mk for mk, v in models.items() if not v.get("error") and mk in MODEL_META]

    ref_mk, ref_model = first_ok(models, ok_model_ids)
    if not ref_model:
        raise SystemExit("Nessun modello disponibile in data.json: impossibile costruire la tabella.")

    if args.mode == "hourly":
        ref_times = ref_model["hourly"]["time"][: args.hours] if args.hours else ref_model["hourly"]["time"]
        n = len(ref_times)
        time_cols = []
        day_labels = []
        seen_days = []
        for i, t in enumerate(ref_times):
            date_part, time_part = t.split("T")
            hod = int(time_part[:2])
            if date_part not in seen_days:
                seen_days.append(date_part)
                y, m, d = date_part.split("-")
                wd = dt.date(int(y), int(m), int(d)).weekday()
                day_labels.append(f"{IT_WEEKDAYS[wd]} {d}/{m}")
            time_cols.append({"hod": hod, "dayIndex": len(seen_days) - 1})
        n_days = len(seen_days)
    else:
        ref_times = ref_model["daily"]["time"]
        n = len(ref_times)
        time_cols = [parse_date_label(t) for t in ref_times]
        day_labels = [f"{c['d']} {c['date']}" for c in time_cols]
        seen_days = ref_times
        n_days = n

    def hourly_series(mk, field):
        h = models[mk].get("hourly") or {}
        arr = h.get(field)
        if arr is None:
            return [None] * n
        return arr[: len(ref_model["hourly"]["time"])][: n] if args.mode == "hourly" else arr

    def daily_series(mk, field):
        d = models[mk].get("daily") or {}
        arr = d.get(field)
        if arr is None:
            return [None] * n
        return arr[:n]

    def daily_from_hourly(mk, field, agg):
        h = models[mk].get("hourly") or {}
        times = h.get("time") or []
        vals = h.get(field)
        if vals is None:
            return [None] * n_days
        by_day = {d: [] for d in seen_days}
        for t, v in zip(times, vals):
            dpart = t.split("T")[0]
            if dpart in by_day and v is not None:
                by_day[dpart].append(v)
        out = []
        for d in seen_days:
            vs = by_day[d]
            if not vs:
                out.append(None)
            elif agg == "mean":
                out.append(sum(vs) / len(vs))
            elif agg == "max":
                out.append(max(vs))
            elif agg == "sum":
                out.append(sum(vs))
        return out

    def get_series(mk, hourly_field, daily_field=None, agg="mean"):
        if args.mode == "hourly":
            return hourly_series(mk, hourly_field)
        else:
            if daily_field:
                s = daily_series(mk, daily_field)
                if any(v is not None for v in s):
                    return s
            return daily_from_hourly(mk, hourly_field, agg)

    params = []
    excluded_log = {}

    def collect(key, hourly_field, daily_field=None, agg="mean"):
        values = {}
        excluded = []
        for mk in ok_model_ids:
            code = MODEL_META[mk]["code"]
            s = get_series(mk, hourly_field, daily_field, agg)
            if all(v is None for v in s):
                excluded.append({"code": code, "reason": "variabile non fornita da questo modello"})
            else:
                values[code] = s
        return values, excluded

    def model_codes_for(values):
        return [MODEL_META[mk]["code"] for mk in ok_model_ids if MODEL_META[mk]["code"] in values]

    modelsMeta = [MODEL_META[mk] for mk in ok_model_ids]

    # --- Temperatura ---
    if args.mode == "daily":
        v_max, exmax = collect("tmax", "temperature_2m", "temperature_2m_max", "max")
        v_min, exmin = collect("tmin", "temperature_2m", "temperature_2m_min", "min" if False else "mean")
        # tmin needs "min" aggregation, not covered by daily_from_hourly's agg set -> handle manually
        v_min = {}
        exmin = []
        for mk in ok_model_ids:
            code = MODEL_META[mk]["code"]
            d = models[mk].get("daily") or {}
            s = d.get("temperature_2m_min")
            if s is None:
                h = models[mk].get("hourly") or {}
                times = h.get("time") or []
                vals = h.get("temperature_2m")
                by_day = {dd: [] for dd in seen_days}
                if vals:
                    for t, v in zip(times, vals):
                        dp = t.split("T")[0]
                        if dp in by_day and v is not None:
                            by_day[dp].append(v)
                s = [min(by_day[dd]) if by_day[dd] else None for dd in seen_days]
            if all(v is None for v in s):
                exmin.append({"code": code, "reason": "variabile non fornita"})
            else:
                v_min[code] = s[:n]
        params.append({"key": "tmax", "classifyAs": "tmax", "label": "Temperatura massima", "unit": "°C", "decimals": 1,
                        "threshTxt": "&lt;30 bianco · 30–33 giallo · 33–36 arancio · 36–40 rosso · &gt;40 fucsia",
                        "modelCodes": model_codes_for(v_max), "values": v_max, "excludedModels": exmax, "openDefault": True})
        params.append({"key": "tmin", "classifyAs": "tmin", "label": "Temperatura minima", "unit": "°C", "decimals": 1,
                        "threshTxt": "&lt;20 bianco · 20–24 giallo (notte tropicale) · &gt;24 arancio+",
                        "modelCodes": model_codes_for(v_min), "values": v_min, "excludedModels": exmin, "openDefault": True})
    else:
        v_temp, ex_temp = collect("temp", "temperature_2m")
        params.append({"key": "temp", "classifyAs": "temp", "label": "Temperatura", "unit": "°C", "decimals": 1,
                        "threshTxt": "&lt;28 bianco · 28–31 giallo · 31–33 arancio · 33–36 rosso · &gt;36 fucsia",
                        "modelCodes": model_codes_for(v_temp), "values": v_temp, "excludedModels": ex_temp, "openDefault": True})

    # --- Pressione (msl) ---
    v_pres, ex_pres = collect("pressione", "pressure_msl", None, "mean")
    params.append({"key": "pressione", "label": "Pressione (SLP)", "unit": "hPa", "decimals": 0,
                    "threshTxt": "ridotta al livello del mare · &ge;1013 bianco · 1008–1012 giallo · 1003–1007 arancio · 998–1002 rosso · &lt;998 fucsia",
                    "modelCodes": model_codes_for(v_pres), "values": v_pres, "excludedModels": ex_pres, "openDefault": True})

    # --- Umidita' ---
    v_hum, ex_hum = collect("umidita", "relative_humidity_2m", None, "mean")
    params.append({"key": "umidita", "label": "Umidità", "unit": "%", "decimals": 0,
                    "threshTxt": "&lt;60 bianco · 60–70 giallo · 70–80 arancio · 80–90 rosso · &gt;90 fucsia",
                    "modelCodes": model_codes_for(v_hum), "values": v_hum, "excludedModels": ex_hum, "openDefault": True})

    # --- Copertura nuvolosa ---
    v_cov, ex_cov = collect("copertura", "cloud_cover", None, "mean")
    params.append({"key": "copertura", "label": "Copertura nuvolosa", "unit": "%", "decimals": 0,
                    "threshTxt": "&lt;20 bianco (sereno) · 20–50 giallo · 50–80 arancio · 80–95 rosso · &gt;95 fucsia",
                    "modelCodes": model_codes_for(v_cov), "values": v_cov, "excludedModels": ex_cov, "openDefault": True})

    # --- Base nubi (solo se richiesta esplicitamente: stima LCL) ---
    if args.cloud_base:
        v_base = {}
        ex_base = []
        for mk in ok_model_ids:
            code = MODEL_META[mk]["code"]
            h = models[mk].get("hourly") or {}
            t_arr, td_arr, times = h.get("temperature_2m"), h.get("dew_point_2m"), h.get("time") or []
            if not t_arr or not td_arr:
                ex_base.append({"code": code, "reason": "temperatura/dew point non disponibili"})
                continue
            if args.mode == "hourly":
                v_base[code] = [lcl_km(t, td) for t, td in zip(t_arr, td_arr)][:n]
            else:
                by_day = {dd: [] for dd in seen_days}
                for t, tv, td in zip(times, t_arr, td_arr):
                    dp = t.split("T")[0]
                    if dp in by_day and tv is not None and td is not None:
                        by_day[dp].append(lcl_km(tv, td))
                v_base[code] = [(min(by_day[dd]) if by_day[dd] else None) for dd in seen_days]
        params.append({"key": "basenubi", "label": "Base nubi (stima LCL)", "unit": "km", "decimals": 1,
                        "threshTxt": "stima da T e punto di rugiada (0,125 km/°C di scarto) · &lt;0,3 fucsia (nebbia) · 0,3–0,6 rosso · 0,6–1,5 arancio · 1,5–3 giallo · &gt;3 bianco",
                        "modelCodes": model_codes_for(v_base), "values": v_base, "excludedModels": ex_base, "openDefault": True})

    # --- Probabilita' pioggia ---
    if args.mode == "daily":
        v_rp, ex_rp = collect("pioggia", "precipitation_probability", "precipitation_probability_max", "max")
    else:
        v_rp, ex_rp = collect("pioggia", "precipitation_probability")
    params.append({"key": "pioggia", "label": "Probabilità pioggia", "unit": "%", "decimals": 0,
                    "threshTxt": "0–10 bianco · 11–40 giallo · 41–70 arancio · 71–90 rosso · &gt;90 fucsia",
                    "modelCodes": model_codes_for(v_rp), "values": v_rp, "excludedModels": ex_rp, "openDefault": True})

    # --- Quantita' precipitazione ---
    if args.mode == "daily":
        v_mm, ex_mm = collect("pioggia_mm", "precipitation", "precipitation_sum", "sum")
        classify_mm = "pioggia_mm_daily"
        unit_mm, thresh_mm = "mm", "totale giornaliero · &le;1 bianco · 1–10 giallo · 10–30 arancio · 30–60 rosso · &gt;60 fucsia"
    else:
        v_mm, ex_mm = collect("pioggia_mm", "precipitation")
        classify_mm = "pioggia_mm"
        unit_mm, thresh_mm = "mm/h", "intensità oraria · &lt;0,5 bianco (assente) · 0,5–2 giallo (debole) · 2–6 arancio (moderata) · 6–15 rosso (forte) · &gt;15 fucsia (nubifragio)"
    params.append({"key": "pioggia_mm", "classifyAs": classify_mm, "label": "Quantità precipitazione", "unit": unit_mm, "decimals": 1,
                    "threshTxt": thresh_mm,
                    "modelCodes": model_codes_for(v_mm), "values": v_mm, "excludedModels": ex_mm, "openDefault": True})

    # --- Vento (medio + raffica + direzione) ---
    if args.mode == "daily":
        v_wind, ex_wind = collect("vento", "wind_speed_10m", None, "mean")
        v_gust = {}
        for mk in ok_model_ids:
            code = MODEL_META[mk]["code"]
            s = daily_series(mk, "wind_gusts_10m_max")
            if any(v is not None for v in s):
                v_gust[code] = s
        dir_deg_per_model = {}
        for mk in ok_model_ids:
            code = MODEL_META[mk]["code"]
            s = daily_series(mk, "wind_direction_10m_dominant")
            if any(v is not None for v in s):
                dir_deg_per_model[code] = s
    else:
        v_wind, ex_wind = collect("vento", "wind_speed_10m")
        v_gust, _ = collect("vento_gust", "wind_gusts_10m")
        dir_deg_per_model, _ = collect("vento_dir", "wind_direction_10m")

    dir_values = []
    for i in range(n):
        degs = [dir_deg_per_model[c][i] for c in dir_deg_per_model if dir_deg_per_model[c][i] is not None]
        dir_values.append(cardinal(circular_mean_deg(degs)))

    params.append({"key": "vento", "label": "Vento", "unit": "kn", "decimals": 0, "hasDirection": True, "hasGust": True,
                    "threshTxt": "medio 10 min + raffica massima · &lt;11 bianco · 11–21 giallo · 22–32 arancio · 33–48 rosso · &ge;49 fucsia (nodi)",
                    "modelCodes": model_codes_for(v_wind), "values": v_wind, "gustValues": v_gust,
                    "dirValues": dir_values, "excludedModels": ex_wind, "openDefault": True})

    # --- Moto ondoso (solo se marine.json fornito) ---
    waveModelsMeta = []
    if args.marine:
        marine = load_json(args.marine)
        wave_models = marine.get("wave_models", {})
        wm_ok = [mk for mk, v in wave_models.items() if not v.get("error") and mk in WAVE_MODEL_META]
        waveModelsMeta = [WAVE_MODEL_META[mk] for mk in wm_ok]

        def wave_hourly(mk, field):
            h = wave_models[mk].get("hourly") or {}
            arr = h.get(field)
            if arr is None:
                return [None] * n
            times = h.get("time") or []
            if args.mode == "hourly":
                return arr[:n]
            by_day = {dd: [] for dd in seen_days}
            for t, v in zip(times, arr):
                dp = t.split("T")[0]
                if dp in by_day and v is not None:
                    by_day[dp].append(v)
            return [(sum(by_day[dd]) / len(by_day[dd]) if by_day[dd] else None) for dd in seen_days]

        v_wave = {}
        ex_wave = []
        wave_dir_per_model = {}
        for mk in wm_ok:
            code = WAVE_MODEL_META[mk]["code"]
            s = wave_hourly(mk, "wave_height")
            if all(v is None for v in s):
                ex_wave.append({"code": code, "reason": "onda non disponibile per quest'area"})
            else:
                v_wave[code] = s
            d = wave_hourly(mk, "wave_direction")
            if any(v is not None for v in d):
                wave_dir_per_model[code] = d

        wave_dir_values = []
        for i in range(n):
            degs = [wave_dir_per_model[c][i] for c in wave_dir_per_model if wave_dir_per_model[c][i] is not None]
            wave_dir_values.append(cardinal(circular_mean_deg(degs)))

        params.append({"key": "ondoso", "label": "Moto ondoso (altezza onda)", "unit": "m", "decimals": 2, "hasDirection": True,
                        "threshTxt": "&lt;0,3 bianco (calmo) · 0,3–0,6 giallo (poco mosso) · 0,6–1,0 arancio (mosso) · 1,0–1,5 rosso (molto mosso) · &gt;1,5 fucsia (agitato)",
                        "modelCodes": [c for c in [WAVE_MODEL_META[mk]["code"] for mk in wm_ok] if c in v_wave],
                        "values": v_wave, "dirValues": wave_dir_values, "excludedModels": ex_wave, "openDefault": True})

    # --- Almanacco: alba/tramonto/luna ---
    alba, tramonto = [], []
    for i, dstr in enumerate(seen_days):
        sunrise = sunset = None
        for mk in ok_model_ids:
            d = models[mk].get("daily") or {}
            times = d.get("time") or []
            if dstr in times:
                idx = times.index(dstr)
                sr = (d.get("sunrise") or [None] * len(times))[idx]
                ss = (d.get("sunset") or [None] * len(times))[idx]
                if sr:
                    sunrise = sr.split("T")[1][:5]
                if ss:
                    sunset = ss.split("T")[1][:5]
                if sunrise and sunset:
                    break
        alba.append(sunrise)
        tramonto.append(sunset)

    luna = []
    for dstr in seen_days:
        mf = os.path.join(args.moon_dir, f"{dstr}.json") if args.moon_dir else None
        if mf and os.path.exists(mf):
            mj = load_json(mf)
            luna.append({"pct": round(mj["illumination_pct"], 1), "label": mj["phase_name"]})
        else:
            luna.append({"pct": None, "label": "n/d"})

    # --- Meta/testo ---
    loc_label = loc.get("name") or loc.get("query")
    admin = loc.get("admin1")
    elevation = loc.get("elevation")
    period_label = f"{time_cols[0]['d'] if args.mode=='daily' else IT_WEEKDAYS[dt.date.fromisoformat(seen_days[0]).weekday()]} " \
                    f"{seen_days[0].split('-')[2]}/{seen_days[0].split('-')[1]} – " \
                    f"{IT_WEEKDAYS[dt.date.fromisoformat(seen_days[-1]).weekday()]} {seen_days[-1].split('-')[2]}/{seen_days[-1].split('-')[1]} {seen_days[-1].split('-')[0]}"

    all_excluded = []
    for p in params:
        for e in p.get("excludedModels", []):
            all_excluded.append(f"{p['label']}: {e['code']} ({e['reason']})")

    notes_items = [
        f"<strong>Dati reali</strong>: scaricati da Open-Meteo (aggregatore ECMWF/GFS/ICON/GEM/UKMO/ARPEGE/AROME/HARMONIE/ALADIN/ICON-2I ARPAE) il {dt.datetime.now().strftime('%d/%m/%Y alle %H:%M')} UTC tramite <code>fetch_forecast.py</code>{' + <code>fetch_marine.py</code>' if args.marine else ''}. Non più dati di prova.",
        f"<strong>Modelli confrontati ({len(modelsMeta)}):</strong> " + ", ".join(f"{m['code']}" for m in modelsMeta) + ". <code>best_match</code> (blend automatico di Open-Meteo) è escluso dal confronto per non falsare la media con un modello non distinto.",
        "<strong>Pressione</strong> mostrata come SLP (ridotta al livello del mare), non pressione di stazione.",
        "<strong>Direzione vento/onda</strong>: media circolare reale tra i modelli disponibili in quell'ora/giorno (non un'assunzione fissa come nei mockup precedenti).",
    ]
    if args.cloud_base:
        notes_items.append("<strong>Base nubi</strong>: non è una variabile diretta di Open-Meteo — stimata dalla formula standard LCL (altezza ≈ 0,125 km per ogni °C di scarto tra temperatura e punto di rugiada), calcolata dai dati reali di temperatura/dew point di ciascun modello.")
    if all_excluded:
        notes_items.append("<strong>Variabili non disponibili per alcuni modelli</strong> (celle con un trattino, segnalato anche nel titolo di sezione): " + "; ".join(all_excluded) + ".")
    notes_items.append("<strong>Rispetto ai mockup con dati di prova</strong>: qui il roster modelli è quello realmente disponibile via Open-Meteo (12, non gli stessi 10 inventati prima) — MOLOCH e BOLAM sono usciti perché non hanno un'API pubblica (documentato in SKILL.md), sostituiti da ICON-EU, ARPEGE, GEM, HARMONIE-AROME, ALADIN che invece sono scaricabili davvero.")

    notes_html = "<ul>" + "".join(f"<li>{it}</li>" for it in notes_items) + "</ul>"

    table_data = {
        "mode": args.mode,
        "timeCols": time_cols,
        "dayLabels": day_labels,
        "almanac": {"alba": alba, "tramonto": tramonto, "luna": luna},
        "modelsMeta": modelsMeta,
        "waveModelsMeta": waveModelsMeta,
        "params": params,
        "meta": {
            "eyebrow": f"Dati reali · confronto multi-modello · {'ogni ora' if args.mode=='hourly' else 'giornaliera'}",
            "titleHtml": f"{loc_label} <em>&middot; dati reali</em>",
            "version": args.version,
            "subHtml": f"{admin or ''}{' · ' if admin else ''}{f'{elevation:.0f} m s.l.m. · ' if elevation and elevation > 200 else ''}{period_label}"
                        f"{' · localit&agrave; costiera, incluso moto ondoso' if args.marine else ''}."
                        f" Fonte: Open-Meteo (dati reali multi-modello).",
            "metaStripHtml": f"lat {loc['lat']:.4f} · lon {loc['lon']:.4f}" + (f" · {elevation:.0f} m" if elevation is not None else ""),
        },
        "notesHtml": notes_html,
    }

    css = open(os.path.join(SCRIPT_DIR, "table_engine.css"), encoding="utf-8").read()
    js = open(os.path.join(SCRIPT_DIR, "table_engine.js"), encoding="utf-8").read()

    html = f"""<title>{loc_label} — Tabella meteo {'oraria' if args.mode=='hourly' else 'giornaliera'} (dati reali)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@700;800;900&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600;700&display=swap">
<style>
{css}
</style>
<div class="page">
  <div class="masthead">
    <div class="eyebrow-row">
      <div class="eyebrow" id="mh-eyebrow"></div>
      <div class="version-badge" id="mh-version"></div>
    </div>
    <h1 id="mh-title"></h1>
    <p class="sub" id="mh-sub"></p>
    <div class="meta-strip" id="mh-meta-strip"></div>
    <div class="spectrum"></div>
  </div>

  <div class="almanac-panel">
    <span class="legend-title">Alba &middot; tramonto &middot; fase lunare (reali)</span>
    <div class="table-wrap" style="padding:0;">
      <div class="pgrid" id="almanacGrid"></div>
    </div>
  </div>

  <div class="toolbar">
    <span class="legend-title">Severit&agrave;</span>
    <div class="swatches">
      <div class="sw sw-0">Bianco <em>nessun rischio</em></div>
      <div class="sw sw-1">Giallo <em>moderato</em></div>
      <div class="sw sw-2">Arancio <em>elevato</em></div>
      <div class="sw sw-3">Rosso <em>molto elevato</em></div>
      <div class="sw sw-4">Fucsia <em>estremo</em></div>
    </div>
    <div class="models-key" id="modelsKey"></div>
  </div>

  <div class="sections" id="sections"></div>

  <div class="notes">
    <h2>Note</h2>
    <div id="notesHtml"></div>
  </div>
</div>

<script>
window.TABLE_DATA = {json.dumps(table_data, ensure_ascii=False)};
</script>
<script>
{js}
</script>
"""

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK -> {args.out} ({len(modelsMeta)} modelli, {n} colonne, {len(params)} parametri)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="JSON prodotto da fetch_forecast.py")
    ap.add_argument("--marine", help="JSON prodotto da fetch_marine.py (localita' costiere)")
    ap.add_argument("--mode", choices=["daily", "hourly"], required=True)
    ap.add_argument("--hours", type=int, default=None, help="Limita le colonne orarie (default: tutte quelle nel JSON)")
    ap.add_argument("--moon-dir", help="Cartella con <data>.json prodotti da moon_phase.py per ogni giorno del periodo")
    ap.add_argument("--cloud-base", action="store_true", help="Includi la sezione Base nubi (stima LCL)")
    ap.add_argument("--version", default="Rev. 1.0.0")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    build(args)


if __name__ == "__main__":
    main()
