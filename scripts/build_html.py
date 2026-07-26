#!/usr/bin/env python3
"""
Genera il report HTML del bollettino: stesso contenuto testuale/tabelle del
PDF (build_pdf.py, stesso report.json) ma con IN PIU' animazioni (loop) di:
  - cartine ECMWF su piu' istanti temporali, per tutti i prodotti
    scaricati come "series" da fetch_ecmwf_charts.py;
  - satellite Meteosat (fetch_meteoam_satellite.py, prodotto ITALIA24);
  - radar precipitazioni + fulmini reali rete LAMPINET (stesso script,
    prodotto RADSATLAM).
Tutte incorporate come GIF animate multi-frame (non un player JS, non
mappe live): giocano ovunque, incluse le anteprime HTML in-app di app
come Telegram che disabilitano JavaScript e/o non riproducono il WebP
animato (entrambi i problemi verificati concretamente su iPhone prima di
arrivare al GIF come soluzione definitiva - vedi MANUTENZIONE.md). Il
file e' quindi **completamente autonomo**: nessuna dipendenza da
rete/JavaScript per chi lo apre, a differenza delle versioni precedenti
di questa skill che usavano mappe Leaflet+RainViewer live.
NON include un satellite/radar "live" nel senso stretto (dati che
cambiano mentre guardi): le immagini sono quelle piu' recenti disponibili
al momento della generazione del report, non si aggiornano riaprendo il
file piu' tardi.

Uso:
    python3 build_html.py report.json --charts-dir charts/ --logo logo.png --out bollettino.html

report.json: stesso schema di build_pdf.py, con in piu' (opzionale):
  "animations": [
    {"title": "Evoluzione pressione e precipitazioni",
     "note": "ECMWF ufficiale, CC BY 4.0",
     "frames": [{"file": "ecmwf_..._anim.png", "label": "23/07 12:00 UTC"}, ...]}
  ],
  "satellite": {"product": "ITALIA24", "frames": [{"file": "..._meteosat_..._00.jpg", "label": "13:30 UTC il 26/07"}, ...]},
  "radar": {"product": "RADSATLAM", "frames": [{"file": "..._meteosat_..._00.jpg", "label": "..."}, ...]}
Le "animations" si costruiscono leggendo "sequences" da ecmwf_manifest.json
(prodotto da fetch_ecmwf_charts.py quando usi "series" in requests.json) e
copiandole quasi identiche (rinomina "caption" -> "title" e "frames" resta
uguale). "satellite" e "radar" si costruiscono copiando il contenuto dei
manifest prodotti da due chiamate a fetch_meteoam_satellite.py (una con
--product ITALIA24, una con --product RADSATLAM).
"""
import argparse
import base64
import io
import json
import os

from PIL import Image

NAVY = "#1a1a2e"
ORANGE = "#F59F00"
BLUE = "#4C6EF5"
RISK_COLORS = {"Basso": "#37B24D", "Medio": "#F59F00", "Alto": "#E03131"}


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def b64_file(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def img_data_uri(path, quality=82, max_dim=1600):
    # Ricomprime in WebP (con canale alpha se presente) prima di incorporare:
    # le cartine ECMWF sono PNG da 1-2MB l'una e con 30+ immagini/animazioni
    # per bollettino l'HTML autonomo superava facilmente i 50MB (limite
    # Telegram sendDocument). WebP q82 riduce ~5-8x restando leggibile.
    im = Image.open(path)
    has_alpha = "A" in im.getbands()
    im = im.convert("RGBA" if has_alpha else "RGB")
    if max(im.size) > max_dim:
        ratio = max_dim / max(im.size)
        im = im.resize((max(1, int(im.width * ratio)), max(1, int(im.height * ratio))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=quality, method=6)
    return f"data:image/webp;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"


COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO"]


def compass(deg):
    if deg is None:
        return ""
    return COMPASS[round(deg / 22.5) % 16]


def render_live_station(live):
    if not live:
        return ""
    def stat(label, value):
        if value is None or value == "":
            return ""
        return f'<div class="live-stat"><span class="live-val">{esc(value)}</span><span class="live-lbl">{esc(label)}</span></div>'
    wdir = live.get("wind_dir_deg")
    wdir_txt = f"{wdir}° {compass(wdir)}" if wdir is not None else None
    stats = "".join([
        stat("Temperatura", f"{live['temperature_c']}°C" if live.get("temperature_c") is not None else None),
        stat("Umidita'", f"{live['humidity_pct']}%" if live.get("humidity_pct") is not None else None),
        stat("Pressione", f"{live['pressure_hpa']} hPa" if live.get("pressure_hpa") is not None else None),
        stat("Punto di rugiada", f"{live['dewpoint_c']}°C" if live.get("dewpoint_c") is not None else None),
        stat("Vento", f"{live['wind_speed_kn']} kn" if live.get("wind_speed_kn") is not None else None),
        stat("Raffica", f"{live['wind_gust_kn']} kn" if live.get("wind_gust_kn") is not None else None),
        stat("Direzione vento", wdir_txt),
        stat("Pioggia oggi", f"{live['rain_today_mm']} mm" if live.get("rain_today_mm") is not None else None),
    ])
    landing_url = live.get("landing_url")
    link_note = f' <a href="{esc(landing_url)}" target="_blank" rel="noopener">Pagina della centralina</a>.' if landing_url else ""
    return f"""
<section class="live-station">
  <h2>Dati in Tempo Reale (centralina locale)</h2>
  <p class="note">{esc(live.get('label', ''))} &mdash; aggiornato {esc(live.get('updated_at', ''))}. Lettura strumentale reale, non un dato di modello: puo' differire localmente dai valori di modello usati nel resto del bollettino.{link_note}</p>
  <div class="live-grid">{stats}</div>
</section>
"""


def risk_span(level):
    color = RISK_COLORS.get(level, "#868e96")
    return f'<span class="risk" style="color:{color};font-weight:700">{esc(level)}</span>'


def render_table(headers, rows, risk_col=None):
    thead = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body_rows = []
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            if risk_col is not None and i == risk_col and str(cell) in RISK_COLORS:
                cells.append(f"<td>{risk_span(cell)}</td>")
            else:
                cells.append(f"<td>{esc(cell)}</td>")
        body_rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table class="tbl"><thead><tr>{thead}</tr></thead><tbody>{"".join(body_rows)}</tbody></table>'


def render_paragraphs(body):
    parts = []
    for para in body.split("\n\n"):
        para = para.strip()
        if para:
            parts.append(f"<p>{esc(para)}</p>")
    return "\n".join(parts)


def render_meteoam_gallery(title, note, gallery, charts_dir):
    # Usato sia per il satellite (ITALIA24) sia per il radar/fulmini
    # (RADSATLAM): entrambi sono immagini REALI scaricate da meteoam.it
    # (CNMCA - Aeronautica Militare) in fase di generazione, non mappe
    # live via JS - giocano ovunque, incluse le anteprime che
    # disabilitano JavaScript.
    if not gallery or not gallery.get("frames"):
        return ""
    paths = [os.path.join(charts_dir, fr["file"]) for fr in gallery["frames"]]
    data_uri = animated_webp_data_uri(paths)
    n = len(paths)
    first_label = gallery["frames"][0].get("label", "")
    last_label = gallery["frames"][-1].get("label", "")
    landing_url = gallery.get("landing_url")
    img_tag = f'<img class="player-img" src="{data_uri}" />'
    if landing_url:
        img_tag = f'<a href="{esc(landing_url)}" target="_blank" rel="noopener">{img_tag}</a>'
    link_note = f' &mdash; <a href="{esc(landing_url)}" target="_blank" rel="noopener">pagina sorgente</a>.' if landing_url else ""
    return f"""
<section>
  <h2>{esc(title)}</h2>
  <p class="note">{note} {esc(n)} istanti da {esc(first_label)} a {esc(last_label)}, animazione automatica in loop. Prodotto: {esc(gallery.get('product', ''))}.{link_note}</p>
  {img_tag}
</section>
"""


def animated_webp_data_uri(paths, max_dim=1200, duration_ms=900):
    # GIF animato, non WebP: l'anteprima HTML di Telegram su iPhone usa
    # con ogni evidenza un renderer molto limitato (verosimilmente Quick
    # Look di Apple, non un WebView completo) che non riproduce il WebP
    # animato - confermato dall'utente dopo il primo tentativo con WebP,
    # nonostante fosse un formato immagine nativo e non richiedesse
    # JavaScript. Il GIF animato e' supportato ovunque da decenni,
    # incluso Quick Look: e' la scelta piu' compatibile anche se la
    # palette a 256 colori perde un po' di qualita' sui gradienti delle
    # cartine ECMWF rispetto al WebP. Nome funzione invariato per non
    # dover toccare i chiamanti, ma il formato prodotto e' GIF.
    frames = []
    size = None
    for p in paths:
        im = Image.open(p).convert("RGB")
        if max(im.size) > max_dim:
            ratio = max_dim / max(im.size)
            im = im.resize((max(1, int(im.width * ratio)), max(1, int(im.height * ratio))), Image.LANCZOS)
        if size is None:
            size = im.size
        elif im.size != size:
            im = im.resize(size, Image.LANCZOS)
        frames.append(im.convert("P", palette=Image.ADAPTIVE, colors=256))
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:],
                    duration=duration_ms, loop=0, optimize=True)
    return f"data:image/gif;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"


def render_animation(anim, paths):
    data_uri = animated_webp_data_uri(paths)
    n = len(paths)
    first_label = anim["frames"][0].get("label", "")
    last_label = anim["frames"][-1].get("label", "")
    landing_url = anim.get("landing_url")
    img_tag = f'<img class="player-img" src="{data_uri}" />'
    if landing_url:
        img_tag = f'<a href="{esc(landing_url)}" target="_blank" rel="noopener">{img_tag}</a>'
    link_note = f' <a href="{esc(landing_url)}" target="_blank" rel="noopener">Pagina sorgente ECMWF</a>.' if landing_url else ""
    return f"""
<div class="anim-block">
  <h3>{esc(anim.get('title', ''))}</h3>
  {f'<p class="note">{esc(anim["note"])}</p>' if anim.get('note') else ''}
  <p class="note">Animazione automatica in loop ({n} istanti, da {esc(first_label)} a {esc(last_label)}). Se nell'app in cui hai aperto questo file non si muove, prova ad aprirlo in un browser (Safari/Chrome) invece dell'anteprima interna.{link_note}</p>
  {img_tag}
</div>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report_json")
    ap.add_argument("--charts-dir", required=True)
    ap.add_argument("--logo", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    with open(args.report_json, encoding="utf-8") as f:
        data = json.load(f)

    charts_dir = os.path.abspath(args.charts_dir)

    def chart_src(fname):
        # base64 data URI: l'HTML deve restare un file singolo autonomo
        # (es. inviato via Telegram), non puo' contare su una cartella
        # charts/ che lo accompagni
        return img_data_uri(os.path.join(charts_dir, fname))

    logo_b64 = b64_file(args.logo)

    risk_html = ""
    if data.get("risk_table"):
        rt = data["risk_table"]
        risk_idx = rt["headers"].index("Livello") if "Livello" in rt["headers"] else 1
        risk_html = render_table(rt["headers"], rt["rows"], risk_col=risk_idx)

    infographic_html = ""
    if data.get("infographic"):
        p = os.path.join(args.charts_dir, data["infographic"])
        if os.path.exists(p):
            infographic_html = f'<img class="full-img" src="{chart_src(data["infographic"])}" />'

    sections_html = []
    for section in data.get("sections", []):
        block = f'<h3>{esc(section["heading"])}</h3>' + render_paragraphs(section.get("body", ""))
        if section.get("table"):
            tb = section["table"]
            block += render_table(tb["headers"], tb["rows"])
        sections_html.append(block)

    animations_html = ""
    anims = data.get("animations", [])
    if anims:
        blocks = []
        for anim in anims:
            paths = [os.path.join(charts_dir, fr["file"]) for fr in anim["frames"]]
            blocks.append(render_animation(anim, paths))
        animations_html = "\n".join(blocks)

    static_charts_html = ""
    if data.get("charts"):
        items = []
        for ch in data["charts"]:
            p = os.path.join(args.charts_dir, ch["file"])
            if not os.path.exists(p):
                continue
            img_tag = f'<img src="{chart_src(ch["file"])}" />'
            landing_url = ch.get("landing_url")
            if landing_url:
                img_tag = f'<a href="{esc(landing_url)}" target="_blank" rel="noopener">{img_tag}</a>'
            caption = esc(ch.get("caption", ""))
            if landing_url:
                caption += f' &mdash; <a href="{esc(landing_url)}" target="_blank" rel="noopener">pagina sorgente</a>'
            items.append(f'''<figure class="chart">
  {img_tag}
  <figcaption>{caption}</figcaption>
</figure>''')
        static_charts_html = '<div class="chart-grid">' + "\n".join(items) + "</div>"

    activities_html = ""
    if data.get("activities_table"):
        at = data["activities_table"]
        risk_idx = at["headers"].index("Rischio") if "Rischio" in at["headers"] else 1
        activities_html = render_table(at["headers"], at["rows"], risk_col=risk_idx)

    outlook_html = ""
    if data.get("outlook_7d"):
        ot = data["outlook_7d"]
        outlook_html = render_table(ot["headers"], ot["rows"])

    html = f"""<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(data.get('title', 'Bollettino Meteorologico'))} - {esc(data.get('location_label',''))}</title>
<style>
  :root {{ --navy:{NAVY}; --orange:{ORANGE}; --blue:{BLUE}; --bg:#f8f9fa; --card:#ffffff; --text:#1a1a2e; --muted:#495057; --border:#dee2e6; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#14151c; --card:#1e1f29; --text:#eef0f4; --muted:#aab0bd; --border:#33354a; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; background:var(--bg); color:var(--text); }}
  header {{ background:var(--navy); color:#fff; padding:28px 24px; text-align:center; border-bottom:4px solid var(--orange); }}
  header img {{ height:64px; margin-bottom:10px; }}
  header h1 {{ margin:4px 0; font-size:1.6rem; }}
  header .sub {{ opacity:.85; font-size:1.05rem; }}
  main {{ max-width:980px; margin:0 auto; padding:24px 16px 60px; }}
  section {{ background:var(--card); border:1px solid var(--border); border-radius:10px; padding:20px 24px; margin-bottom:20px; }}
  h2 {{ color:var(--navy); border-left:5px solid var(--orange); padding-left:10px; }}
  @media (prefers-color-scheme: dark) {{ h2 {{ color:#fff; }} }}
  h3 {{ color:var(--navy); margin-top:22px; }}
  @media (prefers-color-scheme: dark) {{ h3 {{ color:#fff; }} }}
  p {{ line-height:1.55; }}
  .note {{ color:var(--muted); font-size:.85rem; font-style:italic; }}
  .note a {{ color:var(--blue); font-style:normal; }}
  a:has(> img) {{ display:block; }}
  figure.chart figcaption a {{ color:var(--blue); }}
  table.tbl {{ width:100%; border-collapse:collapse; margin:12px 0 20px; font-size:.92rem; }}
  table.tbl th {{ background:var(--navy); color:#fff; text-align:left; padding:8px 10px; }}
  table.tbl td {{ padding:8px 10px; border-bottom:1px solid var(--border); }}
  table.tbl tr:nth-child(even) td {{ background: rgba(128,128,128,.06); }}
  .full-img {{ width:100%; border-radius:8px; margin:10px 0; }}
  .chart-grid {{ display:grid; grid-template-columns:1fr; gap:18px; }}
  figure.chart {{ margin:0; }}
  figure.chart img {{ width:100%; border-radius:8px; border:1px solid var(--border); }}
  figcaption {{ font-size:.85rem; color:var(--muted); margin-top:6px; text-align:center; }}
  .anim-block {{ margin-bottom:28px; }}
  .player-img {{ width:100%; border-radius:8px; border:1px solid var(--border); background:#fff; }}
  .player-controls {{ display:flex; align-items:center; gap:10px; margin-top:8px; }}
  .btn {{ background:var(--navy); color:#fff; border:none; border-radius:6px; padding:6px 12px; cursor:pointer; font-size:.9rem; }}
  .btn:hover {{ opacity:.85; }}
  .label {{ font-size:.85rem; color:var(--muted); min-width:140px; text-align:right; }}
  .risk {{ font-weight:700; }}
  .live-grid {{ display:flex; flex-wrap:wrap; gap:12px; margin-top:10px; }}
  .live-stat {{ background:rgba(76,110,245,.08); border:1px solid var(--border); border-radius:8px; padding:10px 16px; min-width:120px; display:flex; flex-direction:column; align-items:center; }}
  .live-val {{ font-size:1.25rem; font-weight:700; color:var(--navy); }}
  @media (prefers-color-scheme: dark) {{ .live-val {{ color:#fff; }} }}
  .live-lbl {{ font-size:.78rem; color:var(--muted); margin-top:2px; }}
  footer {{ text-align:center; color:var(--muted); font-size:.8rem; padding:20px; }}
</style>
</head>
<body>
<header>
  <img src="data:image/png;base64,{logo_b64}" />
  <h1>{esc(data.get('title', 'Bollettino Meteorologico Professionale'))}</h1>
  <div class="sub">{esc(data.get('location_label',''))} &middot; {esc(data.get('period_label',''))}</div>
  <div class="sub" style="font-size:.85rem;opacity:.7">Generato il {esc(data.get('generated_at',''))}</div>
</header>
<main>

{render_live_station(data.get('live_station'))}
<section>
  <h2>Sintesi</h2>
  <p>{esc(data.get('sintesi',''))}</p>
</section>

<section>
  <h2>Quadro dei Rischi</h2>
  {risk_html}
  {infographic_html}
</section>

<section>
  <h2>Analisi</h2>
  {"".join(sections_html)}
</section>

{render_meteoam_gallery("Satellite osservato (ultime ore)",
                         'Immagini Meteosat REALI e ufficiali (CNMCA - Aeronautica Militare / EUMETSAT, dati "Essential" a uso libero), non generate/previste:',
                         data.get('satellite'), charts_dir)}

{render_meteoam_gallery("Radar e fulmini osservati (ultime ore)",
                         'Immagini REALI e ufficiali CNMCA (Aeronautica Militare): radar precipitazioni (SRI mm/h) + satellite IR + fulmini reali rete LAMPINET sovrapposti, non generate/previste:',
                         data.get('radar'), charts_dir)}

{"<section><h2>Animazioni modelli previsti (ECMWF ufficiale, CC BY 4.0)</h2>" + animations_html + "</section>" if animations_html else ""}

<section>
  <h2>Grafici</h2>
  {static_charts_html}
</section>

{"<section><h2>Attivita' Consigliate</h2>" + activities_html + "</section>" if activities_html else ""}

<section>
  <h2>Affidabilita' della Previsione: {esc(data.get('reliability_pct',''))}%</h2>
  {render_paragraphs(data.get('reliability_text',''))}
</section>

{"<section><h2>Editoriali e Approfondimenti di Esperti</h2>" + render_paragraphs(data.get("editoriali","")) + "</section>" if data.get("editoriali") else ""}

<section>
  <h2>Conclusioni</h2>
  {render_paragraphs(data.get('conclusione',''))}
</section>

{"<section><h2>Outlook 7 Giorni</h2><p class='note'>Tendenza estesa a colpo d'occhio (modello best_match, singolo modello: affidabilita' minore rispetto all'analisi multi-modello dei giorni precedenti).</p>" + outlook_html + "</section>" if outlook_html else ""}

</main>
<footer>Generato con meteoP@d0 &middot; dati modelli numerici pubblici (Open-Meteo, ECMWF OpenCharts CC BY 4.0, CNMCA/Aeronautica Militare - EUMETSAT)</footer>

</body>
</html>
"""

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK -> {args.out}")


if __name__ == "__main__":
    main()
