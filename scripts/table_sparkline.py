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
import json

RH = 32  # altezza fissa riga corpo tabella, px - deve combaciare con lo sfondo sparkline

# (chiave in ogni riga unita, classe CSS colonna, larghezza px, chiave sparkline o None, etichetta header, tooltip)
BASE_COLS = [
    ("time",   "col-time", 108, None,     "Data / ora", None),
    ("temp",   "sc-t",      56, "temp",   "T (°C)", "Temperatura a 2m"),
    ("wind",   "sc-vt",     60, "wind",   "Vento (kn)", "Vento medio a 10m"),
    ("dirv",   "dir",       52, None,     "Dir.V", "Direzione del vento"),
    ("precip", "sc-pr",     60, "precip", "Pioggia (mm)", "Precipitazione cumulata nelle 3 ore seguenti"),
    ("sbcape", "sc-cape",   68, "sbcape", "SBCAPE", "Surface Based CAPE – energia potenziale convettiva disponibile"),
    ("cin",    "sc-cin",    64, "cin",    "CIN", "Convective Inhibition – inibizione convettiva (la “cappa”)"),
    ("li",     "sc-li",     44, "li",     "LI", "Lifted Index"),
    ("k",      "sc-k",      40, "k",      "K", "K-Index"),
    ("tt",     "sc-tt",     44, "tt",     "TT", "Total Totals Index"),
    ("sweat",  "sc-swt",    56, "sweat",  "SWEAT", "SWEAT Index – rischio temporali severi/supercelle oltre 300"),
    ("shear",  "sc-shear",  62, "shear",  "Shear0-6", "Bulk shear 0-6 km"),
    ("srh",    "sc-srh",    62, "srh",    "SRH0-3", "Storm Relative Helicity 0-3 km"),
    ("pwat",   "sc-pwat",   52, "pwat",   "PWAT", "Acqua precipitabile (Precipitable Water)"),
]
MARINE_COLS = [
    ("wave",   "sc-onda",   56, "wave",   "Onda (m)", "Altezza onda significativa"),
    ("diro",   "dir",       52, None,     "Dir.O", "Direzione dell'onda"),
]
NOTE_COL = ("note", "col-note", 168, None, "Nota", None)

DIRS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"]


def dirlabel(d):
    if d is None:
        return "-"
    return DIRS[round(d / 22.5) % 16]


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
            "precip": round(precip, 1),
            "sbcape": cape, "cin": cin, "li": ind.get("lifted_index"),
            "k": ind.get("k_index"), "tt": ind.get("total_totals"),
            "sweat": ind.get("sweat_index"), "shear": shear, "srh": ind.get("srh_0_3km_m2s2"),
            "pwat": ind.get("pwat_kg_m2"),
            "wave": wave, "diro": dirlabel(wave_dir),
            "flag": flag,
        })
    return rows


def make_svg(rows, key, col_w, total_h, color, opacity, dot_colors):
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
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.1" fill="{c}" fill-opacity="0.85"/>'
        for x, y, c in dots
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{col_w}" height="{total_h}">'
        f'<line x1="{midx:.1f}" y1="0" x2="{midx:.1f}" y2="{total_h}" stroke="{color}" '
        f'stroke-opacity="{opacity*0.45:.2f}" stroke-width="1" stroke-dasharray="1.5 3"/>'
        f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="1.3" '
        f'stroke-opacity="{opacity:.2f}" stroke-linecap="round" stroke-linejoin="round"/>'
        f'{circles}</svg>'
    )


def b64(svg):
    return base64.b64encode(svg.encode("utf-8")).decode("ascii")


LIGHT_LINE, LIGHT_OP = "#57708C", 0.40
DARK_LINE, DARK_OP = "#9FB6D6", 0.40
LIGHT_DOTS = ("#B9790E", "#A7362A")
DARK_DOTS = ("#E3A73F", "#E27567")


def build_spark_assets(rows, cols, total_h):
    light_vars, dark_vars, css_rules = [], [], []
    for _, cls, w, skey, _, _ in cols:
        if skey is None:
            continue
        svg_l = make_svg(rows, skey, w, total_h, LIGHT_LINE, LIGHT_OP, LIGHT_DOTS)
        svg_d = make_svg(rows, skey, w, total_h, DARK_LINE, DARK_OP, DARK_DOTS)
        light_vars.append(f'    --spark-{cls}: url("data:image/svg+xml;base64,{b64(svg_l)}");')
        dark_vars.append(f'      --spark-{cls}: url("data:image/svg+xml;base64,{b64(svg_d)}");')
        css_rules.append(
            f'  td.{cls} {{ position: relative; width: {w}px; }}\n'
            f'  td.{cls}::before {{ content: ""; position: absolute; inset: 0; z-index: -1; '
            f'background-image: var(--spark-{cls}); background-repeat: no-repeat; '
            f'background-size: {w}px {total_h}px; background-position: 0 calc(var(--ri, 0) * -{RH}px); '
            f'pointer-events: none; }}'
        )
    return "\n".join(light_vars), "\n".join(dark_vars), "\n".join(css_rules)


def fmt(v):
    return "&ndash;" if v is None else str(v)


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

        cells = [
            f'<td class="col-time"><span class="day-tag-slot">{day_cell}</span><span class="time-val">{hhmm}</span></td>',
            f'<td class="sc-t num">{fmt(r["temp"])}</td>',
            f'<td class="sc-vt num">{fmt(r["wind"])}</td>',
            f'<td class="dir">{r["dirv"]}</td>',
            f'<td class="sc-pr num">{fmt(r["precip"])}</td>',
            f'<td class="sc-cape num">{fmt(r["sbcape"])}</td>',
            f'<td class="sc-cin num">{fmt(r["cin"])}</td>',
            f'<td class="sc-li num">{fmt(r["li"])}</td>',
            f'<td class="sc-k num">{fmt(r["k"])}</td>',
            f'<td class="sc-tt num">{fmt(r["tt"])}</td>',
            f'<td class="sc-swt num">{fmt(r["sweat"])}</td>',
            f'<td class="sc-shear num">{fmt(r["shear"])}</td>',
            f'<td class="sc-srh num">{fmt(r["srh"])}</td>',
            f'<td class="sc-pwat num">{fmt(r["pwat"])}</td>',
        ]
        if "wave" in r:
            cells.append(f'<td class="sc-onda num">{fmt(r["wave"])}</td>')
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
    total_w = sum(w for _, _, w, _, _, _ in cols)

    light_vars, dark_vars, spark_rules = build_spark_assets(rows, cols, total_h)
    tbody = build_tbody(rows)

    colgroup = "\n".join(f'<col style="width:{w}px">' for _, _, w, _, _, _ in cols)

    loc = args.location_label or data["location"]["name"]
    lat, lon = data["location"]["lat"], data["location"]["lon"]
    p_start, p_end = data["period"]["start"], data["period"]["end"]
    start_label = dt.date.fromisoformat(p_start).strftime("%d/%m/%Y")
    end_label = dt.date.fromisoformat(p_end).strftime("%d/%m/%Y")
    generated = dt.datetime.now().strftime("%d/%m/%Y %H:%M")

    header_cells = [
        '<th class="col-time">Data / ora</th>',
        '<th><abbr title="Temperatura a 2m">T (&deg;C)</abbr></th>',
        '<th><abbr title="Vento medio a 10m">Vento (kn)</abbr></th>',
        '<th><abbr title="Direzione del vento">Dir.V</abbr></th>',
        '<th><abbr title="Precipitazione cumulata nelle 3 ore seguenti">Pioggia (mm)</abbr></th>',
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
        '<th colspan="4">Atmosfera</th>'
        '<th colspan="9">Convezione (MetPy)</th>'
        + ('<th colspan="2">Mare</th>' if has_marine else '')
        + '<th class="g-note">&nbsp;</th></tr>'
    )

    html = TEMPLATE.format(
        loc=loc, lat=lat, lon=lon, start=start_label, end=end_label, generated=generated,
        light_vars=light_vars, dark_vars=dark_vars, spark_rules=spark_rules,
        colgroup=colgroup, group_row=group_row, header_cells="\n            ".join(header_cells),
        tbody=tbody, total_w=max(total_w, 900), rh=RH,
        marine_title=" e mare" if has_marine else "",
        marine_sub="; onda da Open-Meteo Marine" if has_marine else "",
        marine_footer=" &middot; stato del mare Open-Meteo Marine" if has_marine else "",
    )

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK -> {args.out} ({n} righe, mare: {'si' if has_marine else 'no'})")


TEMPLATE = '''<title>Tabella Convettiva {loc}</title>
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

  header.head {{ display: flex; flex-direction: column; gap: 6px; padding: 4px 2px 2px; }}

  .eyebrow {{
    font-size: 11.5px; font-weight: 700; letter-spacing: 0.09em;
    text-transform: uppercase; color: var(--sea);
  }}

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

  table {{
    border-collapse: separate; border-spacing: 0; width: 100%; min-width: {total_w}px;
    table-layout: fixed; font-variant-numeric: tabular-nums;
  }}

  thead th {{
    position: sticky; top: 0; z-index: 3; background: var(--navy); color: #EAF0FA;
    font-weight: 600; text-align: right; padding: 7px 10px; font-size: 11px;
    letter-spacing: 0.01em; border-bottom: 1px solid var(--navy-2); white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis;
  }}

  thead tr.group-row th {{
    top: 0; z-index: 4; background: var(--navy-2); font-size: 10px; font-weight: 700;
    letter-spacing: 0.08em; text-transform: uppercase; color: #B9C6DE; text-align: center;
    padding: 6px 8px 5px; border-bottom: 1px solid var(--navy);
  }}

  thead tr.col-row th {{ top: 26px; }}

  thead th abbr {{ text-decoration: none; border-bottom: 1px dotted rgba(234, 240, 250, 0.45); cursor: help; }}

  thead th.col-time, thead th.col-note,
  .group-row th.g-time, .group-row th.g-note {{ text-align: left; }}

  th.col-time, td.col-time {{
    position: sticky; left: 0; z-index: 2; text-align: left; background: var(--surface);
    box-shadow: 1px 0 0 var(--line);
  }}

  thead th.col-time {{ z-index: 5; background: var(--navy); }}
  thead tr.group-row th.g-time {{ z-index: 5; background: var(--navy-2); }}

  tbody tr {{ height: {rh}px; }}

  tbody td {{
    height: {rh}px; padding: 0 10px; font-size: 12px; text-align: right;
    border-bottom: 1px solid var(--line-soft); color: var(--text); white-space: nowrap; overflow: hidden;
  }}

  tbody tr:hover td {{ background: var(--row-hover); }}
  tbody tr:hover td.col-time {{ background: var(--row-hover); }}

  td.col-time {{ display: flex; align-items: center; gap: 8px; font-weight: 600; font-variant-numeric: tabular-nums; }}

  .day-tag-slot {{ display: inline-flex; min-width: 0; }}

  .day-tag {{
    font-size: 10px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
    color: var(--sea); background: color-mix(in srgb, var(--sea) 14%, transparent);
    padding: 2px 6px; border-radius: 5px; white-space: nowrap;
  }}

  td.dir {{ text-align: center; color: var(--text-soft); font-size: 11.5px; }}
  td.col-note {{ text-align: left; }}

  tr.day-start td.col-time {{ box-shadow: 1px 0 0 var(--line), inset 0 2px 0 var(--line); }}
  tr.risk-trigger td.col-time {{ box-shadow: 1px 0 0 var(--line), inset 3px 0 0 var(--amber); }}
  tr.risk-organized td.col-time {{ box-shadow: 1px 0 0 var(--line), inset 3px 0 0 var(--storm); }}
  tr.day-start.risk-trigger td.col-time {{ box-shadow: 1px 0 0 var(--line), inset 0 2px 0 var(--line), inset 3px 0 0 var(--amber); }}
  tr.day-start.risk-organized td.col-time {{ box-shadow: 1px 0 0 var(--line), inset 0 2px 0 var(--line), inset 3px 0 0 var(--storm); }}
  tr.day-start td:not(.col-time) {{ box-shadow: inset 0 2px 0 var(--line); }}

  .pill {{ display: inline-block; font-size: 10.5px; font-weight: 700; letter-spacing: 0.02em; padding: 3px 9px; border-radius: 999px; }}
  .pill-none {{ color: var(--text-faint); font-weight: 500; }}
  .pill-trigger {{ background: var(--amber-bg); color: var(--amber); }}
  .pill-organized {{ background: var(--storm-bg); color: var(--storm); }}

{spark_rules}

  footer.foot {{
    display: flex; flex-wrap: wrap; justify-content: space-between; gap: 8px;
    padding: 2px 4px; font-size: 11px; color: var(--text-faint);
  }}

  @media (max-width: 640px) {{ .legend {{ font-size: 11.5px; }} }}
</style>

<div class="sheet">
  <header class="head">
    <span class="eyebrow">{loc} &middot; {lat:.2f}&deg;N {lon:.2f}&deg;E</span>
    <h1>Tabella tri-oraria &mdash; parametri convettivi, vento{marine_title} e pioggia</h1>
    <p class="sub">{start}&ndash;{end}, ogni 3 ore (00&ndash;21 locali). Blend Best Match (Open-Meteo);
      indici convettivi calcolati con MetPy sul profilo verticale orario{marine_sub}. Ogni colonna numerica
      porta in filigrana il proprio andamento (scala min&ndash;max propria della colonna, non comparabile tra colonne diverse).</p>
  </header>

  <div class="legend">
    <div class="legend-item"><span class="swatch line"></span>Linea = andamento del valore scorrendo nel tempo</div>
    <div class="legend-sep"></div>
    <div class="legend-item"><span class="swatch trigger"></span>Innesco possibile &mdash; CIN &ge; &minus;75 J/kg con SBCAPE &ge; 1000 J/kg</div>
    <div class="legend-sep"></div>
    <div class="legend-item"><span class="swatch organized"></span>Temporali organizzati &mdash; SBCAPE &ge; 1500 J/kg con Shear 0&ndash;6km &ge; 25 kn</div>
  </div>

  <div class="panel">
    <div class="scroll">
      <table>
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

  <footer class="foot">
    <span>Fonte dati: Open-Meteo (blend Best Match) &middot; indici convettivi calcolati con MetPy{marine_footer}</span>
    <span>Generato {generated}</span>
  </footer>
</div>
'''


if __name__ == "__main__":
    main()
