#!/usr/bin/env python3
"""
Genera la tabella HTML di confronto multi-modello (severita' a colori, linea di
tendenza a sfondo, vento/onda con direzione) a partire da dati REALI scaricati
con fetch_forecast.py (e opzionalmente fetch_marine.py per localita' costiere).

Non scarica nulla da solo: prende in input i JSON gia' prodotti da quegli
script e scrive un singolo file HTML autonomo e statico (nessun
JavaScript: masthead, almanacco, sezioni e linea di tendenza SVG sono
markup generato in Python, CSS incorporato, nessuna dipendenza esterna
salvo i Google Fonts e, se presente, il logo Meteo Garbino incorporato
come base64).

Uso:
    python3 build_comparison_table.py --data data.json --mode daily \
        --moon-dir /tmp/moon --out bollettino_bologna.html

    python3 build_comparison_table.py --data data.json --marine marine.json \
        --mode hourly --moon-dir /tmp/moon --out out.html
"""
import argparse
import base64
import datetime as dt
import glob
import json
import math
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOGO = os.path.join(SCRIPT_DIR, "..", "assets", "logo_garbino.png")


def b64_file(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

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

from site_common import THEME_TOGGLE_HTML, CHART_INTERACTION_JS, CHANGELOG, render_changelog, render_footer  # noqa: E402


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


def classify(param, v):
    if v is None:
        return None
    if param in ("temp", "tmax"):
        return 0 if v < 28 else 1 if v <= 31 else 2 if v <= 33 else 3 if v <= 36 else 4
    if param == "tmin":
        return 0 if v < 20 else 1 if v <= 24 else 2 if v <= 27 else 3 if v <= 30 else 4
    if param == "pressione":
        return 0 if v >= 1013 else 1 if v >= 1008 else 2 if v >= 1003 else 3 if v >= 998 else 4
    if param == "umidita":
        return 0 if v < 60 else 1 if v <= 70 else 2 if v <= 80 else 3 if v <= 90 else 4
    if param == "vento":
        return 0 if v < 11 else 1 if v <= 21 else 2 if v <= 32 else 3 if v <= 48 else 4
    if param == "copertura":
        return 0 if v < 20 else 1 if v <= 50 else 2 if v <= 80 else 3 if v <= 95 else 4
    if param == "pioggia":
        return 0 if v <= 10 else 1 if v <= 40 else 2 if v <= 70 else 3 if v <= 90 else 4
    if param == "pioggia_mm":
        return 0 if v < 0.5 else 1 if v <= 2 else 2 if v <= 6 else 3 if v <= 15 else 4
    if param == "pioggia_mm_daily":
        return 0 if v <= 1 else 1 if v <= 10 else 2 if v <= 30 else 3 if v <= 60 else 4
    if param == "ondoso":
        return 0 if v < 0.3 else 1 if v <= 0.6 else 2 if v <= 1.0 else 3 if v <= 1.5 else 4
    if param == "basenubi":
        return 4 if v < 0.3 else 3 if v <= 0.6 else 2 if v <= 1.5 else 1 if v <= 3.0 else 0
    if param == "cape":
        return 0 if v < 300 else 1 if v <= 1000 else 2 if v <= 2500 else 3 if v <= 4000 else 4
    if param == "cin":
        # CIN alto = forte inibizione (cappa) = temporali meno probabili: scala invertita.
        return 0 if v >= 100 else 1 if v >= 50 else 2 if v >= 25 else 3 if v >= 10 else 4
    if param == "lifted_index":
        return 0 if v >= 0 else 1 if v >= -2 else 2 if v >= -4 else 3 if v >= -6 else 4
    if param == "tcwv":
        return 0 if v < 20 else 1 if v <= 30 else 2 if v <= 40 else 3 if v <= 50 else 4
    return None


def fmt_val(v, decimals):
    if v is None:
        return "—"
    return f"{v:.{decimals}f}" if decimals > 0 else str(round(v))


def render_trend_svg(values_by_model, model_codes, ncols):
    all_vals = [v for c in model_codes for v in values_by_model.get(c, []) if v is not None]
    if not all_vals:
        return ""
    lo, hi = min(all_vals), max(all_vals)
    pad = (hi - lo) * 0.18 or 1
    lo -= pad
    hi += pad

    def x(i):
        return (i / (ncols - 1)) * 700 if ncols > 1 else 350

    def y(v):
        return 90 - ((v - lo) / (hi - lo)) * 76

    lines = []
    for c in model_codes:
        pts = [f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(values_by_model.get(c, [])) if v is not None]
        if len(pts) >= 2:
            lines.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="var(--ink-faint)" '
                          f'stroke-width="1" opacity="0.28" stroke-linejoin="round" stroke-linecap="round" />')
    mean_pts = []
    for i in range(ncols):
        vals = [values_by_model[c][i] for c in model_codes if values_by_model.get(c) and values_by_model[c][i] is not None]
        if vals:
            mean_pts.append(f"{x(i):.1f},{y(sum(vals) / len(vals)):.1f}")
    if not mean_pts:
        return ""
    mean_line = " ".join(mean_pts)
    x0 = mean_pts[0].split(",")[0]
    x1 = mean_pts[-1].split(",")[0]
    area = f'<polygon points="{x0},96 {mean_line} {x1},96" fill="var(--accent)" opacity="0.08" />'
    return (f'<svg viewBox="0 0 700 100" preserveAspectRatio="none">{area}{"".join(lines)}'
            f'<polyline points="{mean_line}" fill="none" stroke="var(--accent)" stroke-width="2" '
            f'stroke-linejoin="round" stroke-linecap="round" /></svg>')


def col_label(mode, tc, day_labels):
    if mode == "hourly":
        return f"{day_labels[tc['dayIndex']]} {tc['hod']:02d}:00"
    return f"{tc['d']} {tc['date']}"


def render_chart_svg(p, mode, time_cols, day_labels, is_conv=False):
    """Grafico a linee grande e interattivo (a differenza del mini-trend di
    render_trend_svg, gia' usato come sfondo della riga media): una linea
    per modello sovrapposte per il confronto, la media in evidenza, e un
    cerchio invisibile per colonna con i dati gia' formattati (valore,
    etichetta data/ora) che lo script CHART_INTERACTION_JS usa per
    disegnare il crosshair al passaggio del mouse o al tocco."""
    ncols = len(time_cols)
    if is_conv:
        model_codes = []
        mean_vals = p["values"]
    else:
        model_codes = p["modelCodes"]
        mean_vals = []
        for i in range(ncols):
            vals = [p["values"][c][i] for c in model_codes if p["values"].get(c) and p["values"][c][i] is not None]
            mean_vals.append(sum(vals) / len(vals) if vals else None)

    all_vals = [v for v in mean_vals if v is not None]
    if not is_conv:
        for c in model_codes:
            all_vals += [v for v in p["values"].get(c, []) if v is not None]
    if not all_vals:
        return ""

    lo, hi = min(all_vals), max(all_vals)
    pad = (hi - lo) * 0.12 or 1
    lo -= pad
    hi += pad

    margin_l, margin_r, margin_t, plot_h, margin_b = 48, 14, 14, 220, 34
    hourly_wide = mode == "hourly"
    W = max(860, ncols * 16) if hourly_wide else 860
    H = plot_h + margin_t + margin_b

    def x(i):
        usable = W - margin_l - margin_r
        return margin_l + (i / (ncols - 1)) * usable if ncols > 1 else margin_l + usable / 2

    def y(v):
        return margin_t + plot_h - ((v - lo) / (hi - lo)) * plot_h

    grid = []
    for t in range(5):
        gv = lo + (hi - lo) * t / 4
        gy = y(gv)
        grid.append(f'<line x1="{margin_l}" y1="{gy:.1f}" x2="{W - margin_r}" y2="{gy:.1f}" '
                     f'stroke="var(--panel-line)" stroke-width="1"/>')
        grid.append(f'<text x="{margin_l - 8}" y="{gy + 3:.1f}" text-anchor="end" font-size="10" '
                     f'fill="var(--ink-faint)" font-family="IBM Plex Mono, monospace">{fmt_val(gv, p["decimals"])}</text>')

    lines = []
    if not is_conv:
        for c in model_codes:
            pts = [f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(p["values"].get(c, [])) if v is not None]
            if len(pts) >= 2:
                lines.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="var(--ink-faint)" '
                              f'stroke-width="1" opacity="0.35"/>')

    mean_pts, circles = [], []
    for i, v in enumerate(mean_vals):
        if v is None:
            continue
        px, py = x(i), y(v)
        mean_pts.append(f"{px:.1f},{py:.1f}")
        lbl = col_label(mode, time_cols[i], day_labels)
        circles.append(f'<circle class="chart-pt" cx="{px:.1f}" cy="{py:.1f}" r="10" fill="transparent" '
                        f'data-x="{px:.1f}" data-y="{py:.1f}" '
                        f'data-value="{fmt_val(v, p["decimals"])} {p["unit"]}" data-label="{lbl}"/>')
    mean_line = (f'<polyline points="{" ".join(mean_pts)}" fill="none" stroke="var(--accent)" stroke-width="2.4" '
                 f'stroke-linejoin="round" stroke-linecap="round"/>') if len(mean_pts) >= 2 else ""

    xlabels = []
    for i, tc in enumerate(time_cols):
        show = (tc["hod"] == 0) if mode == "hourly" else True
        if not show:
            continue
        lbl = day_labels[tc["dayIndex"]] if mode == "hourly" else f"{tc['d']} {tc['date']}"
        xlabels.append(f'<text x="{x(i):.1f}" y="{H - 10}" text-anchor="middle" font-size="10" '
                        f'fill="var(--ink-faint)" font-family="IBM Plex Mono, monospace">{lbl}</text>')
        if mode == "hourly" and i > 0:
            xlabels.append(f'<line x1="{x(i):.1f}" y1="{margin_t}" x2="{x(i):.1f}" y2="{margin_t + plot_h}" '
                            f'stroke="var(--panel-line)" stroke-width="1" stroke-dasharray="2,2"/>')

    crosshair = ('<g class="chart-crosshair" style="display:none">'
                 '<line class="ch-vline" stroke="var(--accent)" stroke-width="1" stroke-dasharray="3,3"/>'
                 '<line class="ch-hline" stroke="var(--accent)" stroke-width="1" stroke-dasharray="3,3"/>'
                 '<rect class="ch-label-bg" rx="4" ry="4" fill="var(--ink)"/>'
                 '<text class="ch-label" font-size="11" fill="var(--panel)" font-family="IBM Plex Mono, monospace"></text>'
                 '<circle class="ch-dot" r="4" fill="var(--accent)"/>'
                 '</g>')

    style = f'width:{W}px;height:{H}px;' if hourly_wide else f'width:100%;height:{H}px;'
    scroll_class = "chart-scroll" if hourly_wide else ""

    svg = (f'<svg class="chart-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none" style="{style}">'
           + "".join(grid) + "".join(lines) + mean_line + "".join(circles) + "".join(xlabels) + crosshair
           + '</svg>')
    return f'<div class="{scroll_class}">{svg}</div>'


def render_section(p, mode, time_cols, day_labels, models_lookup):
    codes = p["modelCodes"]
    ncols = len(time_cols)
    trend_svg = render_trend_svg(p["values"], codes, ncols)

    def dsc(i):
        if mode != "hourly":
            return ""
        return " day-start" if (time_cols[i]["hod"] == 0 and i > 0) else ""

    classify_as = p.get("classifyAs", p["key"])
    has_dir = bool(p.get("hasDirection"))  # vento + moto ondoso: value(/gust) on top, direction wraps below

    def fmt_value_dir(value_v, gust_v, dir_v, decimals):
        s = fmt_val(value_v, decimals)
        if gust_v is not None:
            s += f"/{fmt_val(gust_v, decimals)}"
        top = f'<span class="wv">{s}</span>'
        bottom = f'<span class="wd">{dir_v}</span>' if dir_v else ""
        return f'<div class="wind-compact">{top}{bottom}</div>'

    consensus_cells = []
    for i in range(ncols):
        vals = [p["values"][c][i] for c in codes if p["values"].get(c) and p["values"][c][i] is not None]
        avg = sum(vals) / len(vals) if vals else None
        sev = classify(classify_as, avg)
        sev_class = f"sev-{sev}" if sev is not None else ""
        if has_dir:
            gavg = None
            if p.get("hasGust") and p.get("gustValues"):
                gvals = [p["gustValues"][c][i] for c in codes if p["gustValues"].get(c) and p["gustValues"][c][i] is not None]
                gavg = sum(gvals) / len(gvals) if gvals else None
            dir_v = p.get("dirValues", [None] * ncols)[i]
            content = f'<div class="cval {sev_class}">{fmt_value_dir(avg, gavg, dir_v, p["decimals"])}</div>'
        else:
            content = f'<span class="cval {sev_class}">{fmt_val(avg, p["decimals"])}</span>'
        consensus_cells.append(
            f'<div class="cell consensus-cell{dsc(i)}" style="grid-column:{2 + i};grid-row:1;">{content}</div>')

    prev_group = None
    model_rows = []
    for code in codes:
        meta = models_lookup.get(code, {})
        cells = []
        col_vals = p["values"].get(code, [None] * ncols)
        col_dirs = (p.get("dirValuesByModel") or {}).get(code)
        col_gusts = (p.get("gustValues") or {}).get(code) if p.get("hasGust") else None
        for i in range(ncols):
            v = col_vals[i]
            if v is None:
                cells.append(f'<div class="cell na{dsc(i)}">—</div>')
            else:
                sev = classify(classify_as, v)
                if has_dir:
                    gv = col_gusts[i] if col_gusts else None
                    dv = col_dirs[i] if col_dirs else None
                    text = fmt_value_dir(v, gv, dv, p["decimals"])
                else:
                    text = fmt_val(v, p["decimals"])
                cells.append(f'<div class="cell sev-{sev}{dsc(i)}">{text}</div>')
        group = meta.get("group")
        divider = ""
        if group and group != prev_group and len(codes) > 4:
            label = "globali" if group == "globale" else "locali (area limitata)" if group == "locale" else group
            divider = (f'<div style="display:contents"><div class="cell group-label" '
                       f'style="grid-column:1/-1;">Modelli {label}</div></div>')
        prev_group = group
        model_rows.append(divider + f'<div class="model-row" style="display:contents">'
                                     f'<div class="cell rowlabel">{code}</div>{"".join(cells)}</div>')

    head_cells = []
    for i, tc in enumerate(time_cols):
        if mode == "hourly":
            daytag = f'<span class="daytag">{day_labels[tc["dayIndex"]]}</span>' if tc["hod"] == 0 else ""
            head_cells.append(f'<div class="cell colhead{dsc(i)}">{daytag}<span class="day">{tc["hod"]:02d}</span></div>')
        else:
            head_cells.append(f'<div class="cell colhead"><span class="day">{tc["d"]}</span><span class="date">{tc["date"]}</span></div>')

    excluded = p.get("excludedModels") or []
    excluded_html = ""
    if excluded:
        ne = len(excluded)
        title = " · ".join(f'{e["code"]}: {e["reason"]}' for e in excluded)
        excluded_html = f'<span class="warn" title="{title}">{ne} modell{"o" if ne == 1 else "i"} escluso{"" if ne == 1 else "i"}</span>'

    hourly_class = "hourly" if mode == "hourly" else ""
    open_attr = " open" if p.get("openDefault") else ""
    chart_svg = render_chart_svg(p, mode, time_cols, day_labels)

    return f'''<details class="param"{open_attr}>
    <summary><span class="arrow">&#9656;</span> {p["label"]} <span class="unit">{p["unit"]}</span>{excluded_html}<span class="desc">{p["threshTxt"]}</span></summary>
    <div class="param-toolbar"><button type="button" class="chart-toggle-btn">Grafico</button></div>
    <div class="table-wrap">
      <div class="pgrid {hourly_class}">
        <div class="cell rowlabel" style="font-weight:700;">{"Ora" if mode == "hourly" else "Giorno"}</div>
        {"".join(head_cells)}
        <div class="consensus-row {hourly_class}">
          <div class="cell rowlabel" style="grid-column:1;grid-row:1;">Media modelli</div>
          <div class="consensus-svg" style="grid-column:2/-1;grid-row:1;">{trend_svg}</div>
          {"".join(consensus_cells)}
        </div>
        {"".join(model_rows)}
      </div>
    </div>
    <div class="chart-wrap" hidden>{chart_svg}</div>
  </details>'''


def render_convective_section(p, mode, time_cols, day_labels):
    """Tabella a riga singola per un parametro convettivo: a differenza degli
    altri parametri non c'e' un confronto multi-modello, il dato viene da
    un'unica sorgente (il profilo verticale del blend Best Match)."""
    ncols = len(time_cols)
    values = p["values"]
    trend_svg = render_trend_svg({"BM": values}, ["BM"], ncols)

    def dsc(i):
        if mode != "hourly":
            return ""
        return " day-start" if (time_cols[i]["hod"] == 0 and i > 0) else ""

    cells = []
    for i in range(ncols):
        v = values[i]
        sev = classify(p.get("classifyAs", p["key"]), v)
        sev_class = f"sev-{sev}" if sev is not None else ""
        cells.append(f'<div class="cell consensus-cell{dsc(i)}" style="grid-column:{2 + i};grid-row:1;">'
                      f'<span class="cval {sev_class}">{fmt_val(v, p["decimals"])}</span></div>')

    head_cells = []
    for i, tc in enumerate(time_cols):
        if mode == "hourly":
            daytag = f'<span class="daytag">{day_labels[tc["dayIndex"]]}</span>' if tc["hod"] == 0 else ""
            head_cells.append(f'<div class="cell colhead{dsc(i)}">{daytag}<span class="day">{tc["hod"]:02d}</span></div>')
        else:
            head_cells.append(f'<div class="cell colhead"><span class="day">{tc["d"]}</span><span class="date">{tc["date"]}</span></div>')

    hourly_class = "hourly" if mode == "hourly" else ""
    open_attr = " open" if p.get("openDefault") else ""
    chart_svg = render_chart_svg(p, mode, time_cols, day_labels, is_conv=True)

    return f'''<details class="param"{open_attr}>
    <summary><span class="arrow">&#9656;</span> {p["label"]} <span class="unit">{p["unit"]}</span><span class="desc">{p["threshTxt"]}</span></summary>
    <div class="param-toolbar"><button type="button" class="chart-toggle-btn">Grafico</button></div>
    <div class="table-wrap">
      <div class="pgrid {hourly_class}">
        <div class="cell rowlabel" style="font-weight:700;">{"Ora" if mode == "hourly" else "Giorno"}</div>
        {"".join(head_cells)}
        <div class="consensus-row {hourly_class}">
          <div class="cell rowlabel" style="grid-column:1;grid-row:1;">Best Match</div>
          <div class="consensus-svg" style="grid-column:2/-1;grid-row:1;">{trend_svg}</div>
          {"".join(cells)}
        </div>
      </div>
    </div>
    <div class="chart-wrap" hidden>{chart_svg}</div>
  </details>'''


def render_almanac(day_labels, alba, tramonto, luna):
    head = "".join(f'<div class="cell colhead"><span class="day">{d}</span></div>' for d in day_labels)
    alba_html = "".join(f'<div class="cell time-cell">{t or "—"}</div>' for t in alba)
    tram_html = "".join(f'<div class="cell time-cell">{t or "—"}</div>' for t in tramonto)
    cells = []
    for l in luna:
        if l["pct"] is None:
            cells.append('<div class="cell moon-cell" style="border-bottom:none;"><span class="moonpct">n/d</span></div>')
        else:
            cells.append(f'<div class="cell moon-cell" style="border-bottom:none;">'
                          f'<span class="moonpct">{l["pct"]}%</span>'
                          f'<span class="spread-track"><span class="spread-fill" style="width:{l["pct"]}%"></span></span>'
                          f'<span class="moonlabel">{l["label"]}</span></div>')
    luna_html = "".join(cells)
    ncols = len(day_labels)
    return f'''<div class="pgrid" style="grid-template-columns:var(--label-w) repeat({ncols},minmax(60px,1fr));">
      <div class="cell rowlabel" style="font-weight:700;">Giorno</div>
      {head}
      <div class="cell rowlabel">Alba</div>
      {alba_html}
      <div class="cell rowlabel">Tramonto</div>
      {tram_html}
      <div class="cell rowlabel" style="border-bottom:none;">Fase lunare</div>
      {luna_html}
    </div>'''


SEV_LABELS = {3: "Rosso", 4: "Fucsia"}


def compute_alerts(params, conv_params, time_cols, day_labels, mode):
    """Scansiona il valore medio (o, per i convettivi, l'unico valore) di
    ogni parametro/colonna e segnala le soglie rosso/fucsia (severita' 3-4):
    una vista rapida di cosa merita attenzione, senza dover aprire ogni
    singola tabella."""
    ncols = len(time_cols)

    def time_label(i):
        tc = time_cols[i]
        if mode == "hourly":
            return f"{day_labels[tc['dayIndex']]} {tc['hod']:02d}:00"
        return f"{tc['d']} {tc['date']}"

    alerts = []
    for p in params:
        classify_as = p.get("classifyAs", p["key"])
        codes = p["modelCodes"]
        for i in range(ncols):
            vals = [p["values"][c][i] for c in codes if p["values"].get(c) and p["values"][c][i] is not None]
            v = sum(vals) / len(vals) if vals else None
            sev = classify(classify_as, v)
            if sev is not None and sev >= 3:
                alerts.append({"col": i, "time": time_label(i), "label": p["label"],
                                "value": fmt_val(v, p["decimals"]), "unit": p["unit"], "sev": sev})
    for p in conv_params:
        classify_as = p.get("classifyAs", p["key"])
        for i in range(ncols):
            v = p["values"][i]
            sev = classify(classify_as, v)
            if sev is not None and sev >= 3:
                alerts.append({"col": i, "time": time_label(i), "label": p["label"],
                                "value": fmt_val(v, p["decimals"]), "unit": p["unit"], "sev": sev})
    alerts.sort(key=lambda a: (a["col"], -a["sev"]))
    return alerts


def render_alerts(alerts):
    if not alerts:
        return ('<div class="alert-panel alert-panel-clear"><span class="legend-title">&#9888; Attenzione</span>'
                '<p class="alert-empty">Nessuna criticit&agrave; rilevata nel periodo: nessun valore medio in soglia rossa o fucsia.</p></div>')
    rows = []
    for a in alerts:
        rows.append(f'<tr><td class="al-time">{a["time"]}</td><td class="al-label">{a["label"]}</td>'
                     f'<td class="al-value"><span class="sev-{a["sev"]} al-badge">{a["value"]} {a["unit"]}</span> '
                     f'<span class="al-sevlabel">{SEV_LABELS[a["sev"]]}</span></td></tr>')
    n = len(alerts)
    return (f'<div class="alert-panel"><span class="legend-title">&#9888; Attenzione &middot; '
            f'{n} segnalazion{"e" if n == 1 else "i"}</span>'
            f'<div class="table-wrap" style="padding:0;"><table class="alert-table">'
            f'<thead><tr><th>Quando</th><th>Parametro</th><th>Valore</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div></div>')


def lcl_km(t, td):
    if t is None or td is None:
        return None
    return max(0.05, (t - td) * 0.125)


def profile_series(profile, field, mode, ref_times, seen_days, agg):
    """Serie di un campo del profilo verticale (unica sorgente: Best Match),
    allineata alle stesse colonne orarie/giornaliere del resto della tabella."""
    h = (profile or {}).get("hourly") or {}
    times = h.get("time") or []
    vals = h.get(field)
    if not vals:
        return [None] * (len(ref_times) if mode == "hourly" else len(seen_days))
    tmap = dict(zip(times, vals))
    if mode == "hourly":
        return [tmap.get(t) for t in ref_times]
    by_day = {d: [] for d in seen_days}
    for t, v in zip(times, vals):
        dp = t.split("T")[0]
        if dp in by_day and v is not None:
            by_day[dp].append(v)
    out = []
    for d in seen_days:
        vs = by_day[d]
        if not vs:
            out.append(None)
        elif agg == "max":
            out.append(max(vs))
        elif agg == "min":
            out.append(min(vs))
        else:
            out.append(sum(vs) / len(vs))
    return out


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

    dir_values_by_model = {c: [cardinal(d) for d in degs] for c, degs in dir_deg_per_model.items()}

    params.append({"key": "vento", "label": "Vento", "unit": "kn", "decimals": 0, "hasDirection": True, "hasGust": True,
                    "threshTxt": "medio/raffica in nodi, direzione a capo (es. 2/3, SO sotto) · &lt;11 bianco · 11–21 giallo · 22–32 arancio · 33–48 rosso · &ge;49 fucsia (in base al medio)",
                    "modelCodes": model_codes_for(v_wind), "values": v_wind, "gustValues": v_gust,
                    "dirValues": dir_values, "dirValuesByModel": dir_values_by_model,
                    "excludedModels": ex_wind, "openDefault": True})

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

        wave_dir_values_by_model = {c: [cardinal(d) for d in degs] for c, degs in wave_dir_per_model.items()}

        params.append({"key": "ondoso", "label": "Moto ondoso (altezza onda)", "unit": "m", "decimals": 2, "hasDirection": True,
                        "threshTxt": "&lt;0,3 bianco (calmo) · 0,3–0,6 giallo (poco mosso) · 0,6–1,0 arancio (mosso) · 1,0–1,5 rosso (molto mosso) · &gt;1,5 fucsia (agitato)",
                        "modelCodes": [c for c in [WAVE_MODEL_META[mk]["code"] for mk in wm_ok] if c in v_wave],
                        "values": v_wave, "dirValues": wave_dir_values, "dirValuesByModel": wave_dir_values_by_model,
                        "excludedModels": ex_wave, "openDefault": True})

    # --- Parametri convettivi (rischio temporali): unica sorgente, il profilo
    # verticale del blend Best Match scaricato da fetch_forecast.py. Non e' un
    # confronto multi-modello come gli altri parametri: ogni parametro e' una
    # tabella separata a riga singola.
    profile = data.get("profile") or {}
    conv_params = []
    if not profile.get("error") and profile.get("hourly"):
        conv_defs = [
            ("cape", "cape", "CAPE (energia potenziale convettiva)", "J/kg", 0, "max",
             "&lt;300 bianco (debole) · 300–1000 giallo (moderata) · 1000–2500 arancio (forte) · 2500–4000 rosso (molto forte) · &gt;4000 fucsia (estrema)"),
            ("cin", "convective_inhibition", "CIN (inibizione convettiva)", "J/kg", 0, "min",
             "scala invertita: cappa debole = innesco temporali piu' facile · &ge;100 bianco (cappa forte) · 50–99 giallo · 25–49 arancio · 10–24 rosso · &lt;10 fucsia (nessuna inibizione)"),
            ("lifted_index", "lifted_index", "Lifted Index", "°C", 1, "min",
             "&ge;0 bianco (stabile) · 0/-2 giallo (marginale) · -2/-4 arancio (instabile) · -4/-6 rosso (molto instabile) · &lt;-6 fucsia (estremo)"),
            ("freezing_level", "freezing_level_height", "Quota dello zero termico", "m", 0, "mean",
             "informativo, nessuna soglia di rischio: utile per la quota neve e per stimare la dimensione della grandine"),
            ("boundary_layer", "boundary_layer_height", "Altezza dello strato limite", "m", 0, "max",
             "informativo, nessuna soglia di rischio: altezza di rimescolamento dell'aria vicino al suolo"),
            ("tcwv", "total_column_integrated_water_vapour", "Acqua precipitabile (colonna totale)", "kg/m²", 0, "max",
             "&lt;20 bianco · 20–30 giallo · 30–40 arancio · 40–50 rosso · &gt;50 fucsia (colonna satura, nubifragi possibili)"),
        ]
        for key, field, label, unit, decimals, agg, thresh in conv_defs:
            s = profile_series(profile, field, args.mode, ref_times, seen_days, agg)
            if any(v is not None for v in s):
                conv_params.append({"key": key, "classifyAs": key, "label": label, "unit": unit,
                                     "decimals": decimals, "threshTxt": thresh, "values": s})

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
        "<strong>Direzione vento/onda</strong>: media circolare reale tra i modelli disponibili in quell'ora/giorno (non un'assunzione fissa come nei mockup precedenti). Vento e Moto ondoso usano lo stesso formato compatto: valore (e per il vento anche la raffica, come medio/raffica) con la direzione a capo sotto, sia nella media sia in ogni riga modello, per stare dentro alla larghezza della cella anche con 72 colonne orarie; il colore della cella segue la severit&agrave; del valore medio/altezza.",
    ]
    if args.cloud_base:
        notes_items.append("<strong>Base nubi</strong>: non è una variabile diretta di Open-Meteo — stimata dalla formula standard LCL (altezza ≈ 0,125 km per ogni °C di scarto tra temperatura e punto di rugiada), calcolata dai dati reali di temperatura/dew point di ciascun modello.")
    if all_excluded:
        notes_items.append("<strong>Variabili non disponibili per alcuni modelli</strong> (celle con un trattino, segnalato anche nel titolo di sezione): " + "; ".join(all_excluded) + ".")
    if conv_params:
        notes_items.append("<strong>Parametri convettivi</strong> (CAPE, CIN, Lifted Index, zero termico, strato limite, acqua precipitabile): a differenza degli altri parametri non sono un confronto multi-modello, ma provengono da un'unica sorgente — il profilo verticale del blend Best Match scaricato da <code>fetch_forecast.py</code> — perché Open-Meteo espone questi campi solo per quel modello, non per i singoli centri di calcolo. Nella vista giornaliera ogni parametro è aggregato con il criterio più indicativo del rischio (es. CAPE e acqua precipitabile: massimo del giorno; CIN e Lifted Index: minimo, cioè il momento più favorevole ai temporali).")
    notes_items.append("<strong>Rispetto ai mockup con dati di prova</strong>: qui il roster modelli è quello realmente disponibile via Open-Meteo (12, non gli stessi 10 inventati prima) — MOLOCH e BOLAM sono usciti perché non hanno un'API pubblica (documentato in SKILL.md), sostituiti da ICON-EU, ARPEGE, GEM, HARMONIE-AROME, ALADIN che invece sono scaricabili davvero.")

    notes_html = "<ul>" + "".join(f"<li>{it}</li>" for it in notes_items) + "</ul>"

    all_models_meta = modelsMeta + waveModelsMeta
    models_lookup = {m["code"]: m for m in all_models_meta}

    eyebrow = f"Dati reali · confronto multi-modello · {'ogni ora' if args.mode == 'hourly' else 'giornaliera'}"
    title_html = f"{loc_label} <em>&middot; dati reali</em>"
    sub_html = (f"{admin or ''}{' · ' if admin else ''}{f'{elevation:.0f} m s.l.m. · ' if elevation and elevation > 200 else ''}{period_label}"
                f"{' · localit&agrave; costiera, incluso moto ondoso' if args.marine else ''}."
                f" Fonte: Open-Meteo (dati reali multi-modello).")
    meta_strip = f"lat {loc['lat']:.4f} · lon {loc['lon']:.4f}" + (f" · {elevation:.0f} m" if elevation is not None else "")

    # Solo il primo parametro e' aperto di default: con fino a 72-168 colonne
    # orarie per sezione, tenerle tutte espanse appesantisce inutilmente il
    # rendering iniziale della pagina (migliaia di celle mai guardate). Le
    # <details> chiuse non richiedono layout finche' l'utente non le apre,
    # nessun JavaScript necessario.
    for i, p in enumerate(params):
        p["openDefault"] = (i == 0)
    for p in conv_params:
        p["openDefault"] = False

    almanac_html = render_almanac(day_labels, alba, tramonto, luna)
    models_key_html = "".join(f'<span class="mk" title="{m["full"]}"><b>{m["code"]}</b></span>' for m in all_models_meta)
    sections_html = "\n".join(render_section(p, args.mode, time_cols, day_labels, models_lookup) for p in params)
    conv_sections_html = "\n".join(render_convective_section(p, args.mode, time_cols, day_labels) for p in conv_params)
    alerts_html = render_alerts(compute_alerts(params, conv_params, time_cols, day_labels, args.mode))

    css = open(os.path.join(SCRIPT_DIR, "table_engine.css"), encoding="utf-8").read()
    page_style = f' style="--ncols:{n};"'

    logo_html = ""
    if args.logo and os.path.exists(args.logo):
        logo_html = f'<img class="brand-logo" src="data:image/png;base64,{b64_file(args.logo)}" alt="Meteo Garbino">'

    html = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{loc_label} — Tabella meteo {'oraria' if args.mode == 'hourly' else 'giornaliera'} (dati reali)</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@700;800;900&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600;700&display=swap">
<style>
{css}
</style>
{THEME_TOGGLE_HTML}
{CHART_INTERACTION_JS}
<div class="page"{page_style}>
  <div class="masthead">
    <div class="masthead-row">
      <div class="masthead-main">
        <div class="eyebrow-row">
          <div class="eyebrow">{eyebrow}</div>
        </div>
        <h1>{title_html}</h1>
        <p class="sub">{sub_html}</p>
        <div class="meta-strip">{meta_strip}</div>
      </div>
      <div class="brand-stack">
        {logo_html}
        <div class="version-badge">{args.version}</div>
      </div>
    </div>
    <div class="spectrum"></div>
  </div>

  <div class="almanac-panel">
    <span class="legend-title">Alba &middot; tramonto &middot; fase lunare (reali)</span>
    <div class="table-wrap" style="padding:0;">
      {almanac_html}
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
    <div class="models-key">{models_key_html}</div>
  </div>

  {alerts_html}

  <div class="sections">
    {sections_html}
  </div>

  {f'''<div style="margin:2px 2px 2px;"><span class="legend-title">Parametri convettivi (rischio temporali) &middot; sorgente singola: blend Best Match, non confronto multi-modello</span></div>
  <div class="sections">
    {conv_sections_html}
  </div>''' if conv_params else ''}

  <div class="notes">
    <h2>Note</h2>
    {notes_html}
  </div>

  {render_footer()}
</div>
"""

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK -> {args.out} ({len(modelsMeta)} modelli, {n} colonne, {len(params)} parametri) — HTML statico, nessun JavaScript")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="JSON prodotto da fetch_forecast.py")
    ap.add_argument("--marine", help="JSON prodotto da fetch_marine.py (localita' costiere)")
    ap.add_argument("--mode", choices=["daily", "hourly"], required=True)
    ap.add_argument("--hours", type=int, default=None, help="Limita le colonne orarie (default: tutte quelle nel JSON)")
    ap.add_argument("--moon-dir", help="Cartella con <data>.json prodotti da moon_phase.py per ogni giorno del periodo")
    ap.add_argument("--cloud-base", action="store_true", help="Includi la sezione Base nubi (stima LCL)")
    ap.add_argument("--version", default=f"Rev. {CHANGELOG[0]['version']}")
    ap.add_argument("--logo", default=DEFAULT_LOGO, help="Path al logo (default: assets/logo.png della skill). Passa --logo '' per ometterlo.")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    build(args)


if __name__ == "__main__":
    main()
