#!/usr/bin/env python3
"""
Genera il report HTML del bollettino: stesso contenuto testuale/tabelle del
PDF (build_pdf.py, stesso report.json) ma con IN PIU':
  - animazioni (loop) delle cartine ECMWF su piu' istanti temporali, per
    tutti i prodotti scaricati come "series" da fetch_ecmwf_charts.py;
  - una mappa radar live (RainViewer, dati reali, ultime ~2 ore, aggiornate
    ogni 10 minuti) centrata sulla localita', con loop play/pause;
  - satellite (infrarosso, RainViewer) nella stessa mappa quando la fonte
    gratuita lo rende disponibile in quel momento (non sempre presente:
    vedi nota nello script).
  - NON include fulmini: non esiste una fonte gratuita con licenza chiara
    per la ridistribuzione (vedi MANUTENZIONE.md).

A differenza del PDF, il report HTML e' un file locale pensato per essere
aperto in un browser con connessione internet (la mappa radar/satellite si
carica live via JavaScript quando apri il file, non e' "congelata" al
momento della generazione).

Uso:
    python3 build_html.py report.json --charts-dir charts/ --logo logo.png --lat 44.44 --lon 12.29 --out bollettino.html

report.json: stesso schema di build_pdf.py, con in piu' (opzionale):
  "animations": [
    {"title": "Evoluzione pressione e precipitazioni",
     "note": "ECMWF ufficiale, CC BY 4.0",
     "frames": [{"file": "ecmwf_..._anim.png", "label": "23/07 12:00 UTC"}, ...]}
  ]
Puoi costruire questa lista leggendo "sequences" da ecmwf_manifest.json
(prodotto da fetch_ecmwf_charts.py quando usi "series" in requests.json) e
copiandola quasi identica (rinomina "caption" -> "title" e "frames" resta
uguale).
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


PLAYER_JS_ONCE = """
function initPlayer(id, frames, intervalMs) {
  const img = document.getElementById(id + '_img');
  const label = document.getElementById(id + '_label');
  const slider = document.getElementById(id + '_slider');
  const btn = document.getElementById(id + '_playbtn');
  let idx = 0, playing = true, timer = null;
  function show(i) {
    idx = i;
    img.src = frames[i].file;
    label.textContent = frames[i].label;
    slider.value = i;
  }
  function tick() { show((idx + 1) % frames.length); }
  function play() { if (timer) return; timer = setInterval(tick, intervalMs); playing = true; btn.textContent = '\\u23F8 Pausa'; }
  function pause() { clearInterval(timer); timer = null; playing = false; btn.textContent = '\\u25B6 Play'; }
  btn.addEventListener('click', () => playing ? pause() : play());
  slider.addEventListener('input', (e) => { pause(); show(parseInt(e.target.value)); });
  show(0);
  play();
}
"""

RADAR_JS = """
async function initRadarMap(lat, lon) {
  const map = L.map('radarmap').setView([lat, lon], 7);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors', maxZoom: 12
  }).addTo(map);
  L.marker([lat, lon]).addTo(map);
  const statusEl = document.getElementById('radar_status');
  try {
    const res = await fetch('https://api.rainviewer.com/public/weather-maps.json');
    const data = await res.json();
    const host = data.host;
    const frames = (data.radar && data.radar.past) ? data.radar.past : [];
    const satFrames = (data.satellite && data.satellite.infrared) ? data.satellite.infrared : [];
    if (frames.length === 0) {
      statusEl.textContent = 'Radar non disponibile al momento dalla fonte gratuita (RainViewer).';
      return;
    }
    let radarLayers = frames.map(f => L.tileLayer(host + f.path + '/256/{z}/{x}/{y}/2/1_1.png', {opacity: 0.75, zIndex: 5}));
    let satLayers = satFrames.map(f => L.tileLayer(host + f.path + '/256/{z}/{x}/{y}/0/0_0.png', {opacity: 0.6, zIndex: 4}));
    let idx = frames.length - 1;
    let currentRadar = radarLayers[idx].addTo(map);
    let currentSat = satLayers.length ? satLayers[Math.min(idx, satLayers.length - 1)].addTo(map) : null;
    let playing = true, timer = null;
    const label = document.getElementById('radar_label');
    const slider = document.getElementById('radar_slider');
    slider.max = frames.length - 1;
    function showFrame(i) {
      map.removeLayer(currentRadar);
      if (currentSat) map.removeLayer(currentSat);
      currentRadar = radarLayers[i].addTo(map);
      if (satLayers.length) currentSat = satLayers[Math.min(i, satLayers.length - 1)].addTo(map);
      idx = i;
      const d = new Date(frames[i].time * 1000);
      label.textContent = 'Radar: ' + d.toLocaleString('it-IT', {hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit'}) + ' locale';
      slider.value = i;
    }
    function tick() { showFrame((idx + 1) % frames.length); }
    const btn = document.getElementById('radar_playbtn');
    function play() { if (timer) return; timer = setInterval(tick, 600); playing = true; btn.textContent = '\\u23F8 Pausa'; }
    function pause() { clearInterval(timer); timer = null; playing = false; btn.textContent = '\\u25B6 Play'; }
    btn.addEventListener('click', () => playing ? pause() : play());
    slider.addEventListener('input', (e) => { pause(); showFrame(parseInt(e.target.value)); });
    showFrame(idx);
    play();
    statusEl.textContent = 'Radar: ultimi ' + frames.length + ' frame (~' + Math.round(frames.length * 10 / 60 * 10) / 10 + ' min, ogni 10 min) - fonte RainViewer.'
      + (satLayers.length ? ' Satellite infrarosso disponibile.' : ' Satellite infrarosso non disponibile in questo momento dalla fonte gratuita.');
  } catch (e) {
    statusEl.textContent = 'Impossibile caricare il radar live (serve connessione internet nel browser che apre questo file). Dettaglio: ' + e;
  }
}
"""


def render_animation(anim, idx):
    player_id = f"anim{idx}"
    # f["file"] e' gia' una data URI base64 (vedi chart_src in main): non va
    # passata da os.path.basename, che troncherebbe l'immagine al primo '/'
    # incontrato nel payload base64 (l'alfabeto base64 include '/')
    frames_js = json.dumps([{"file": f["file"], "label": f.get("label", "")}
                             for f in anim["frames"]])
    n = len(anim["frames"])
    return f"""
<div class="anim-block">
  <h3>{esc(anim.get('title', ''))}</h3>
  {f'<p class="note">{esc(anim["note"])}</p>' if anim.get('note') else ''}
  <div class="player">
    <img id="{player_id}_img" class="player-img" src="{esc(anim['frames'][0]['file'])}" />
    <div class="player-controls">
      <button id="{player_id}_playbtn" class="btn">&#9208; Pausa</button>
      <input id="{player_id}_slider" type="range" min="0" max="{n-1}" value="0" step="1" style="flex:1" />
      <span id="{player_id}_label" class="label"></span>
    </div>
  </div>
</div>
<script>
initPlayer("{player_id}", {frames_js}, 900);
</script>
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report_json")
    ap.add_argument("--charts-dir", required=True)
    ap.add_argument("--logo", required=True)
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
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
        for i, anim in enumerate(anims):
            frames = [{"file": chart_src(fr["file"]), "label": fr.get("label", "")} for fr in anim["frames"]]
            blocks.append(render_animation({**anim, "frames": frames}, i))
        animations_html = "\n".join(blocks)

    static_charts_html = ""
    if data.get("charts"):
        items = []
        for ch in data["charts"]:
            p = os.path.join(args.charts_dir, ch["file"])
            if not os.path.exists(p):
                continue
            items.append(f'''<figure class="chart">
  <img src="{chart_src(ch["file"])}" />
  <figcaption>{esc(ch.get("caption", ""))}</figcaption>
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
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
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
  #radarmap {{ height:460px; width:100%; border-radius:8px; }}
  .risk {{ font-weight:700; }}
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

<section>
  <h2>Radar e satellite osservato (ultime ore)</h2>
  <p class="note">Mappa live (si aggiorna ogni volta che apri questo file, serve connessione internet nel browser): radar RainViewer, dati OSSERVATI (non previsione). Mostra il massimo storico che la fonte gratuita mette a disposizione in questo momento &mdash; tipicamente le ultime ~2 ore, un frame ogni 10 minuti: non esiste una fonte gratuita con storico piu' lungo e licenza di ridistribuzione chiara gia' validata (vedi MANUTENZIONE.md). Satellite infrarosso incluso quando la fonte gratuita lo rende disponibile in quel momento. I fulmini non sono inclusi per lo stesso motivo di licenza.</p>
  <div id="radarmap"></div>
  <div class="player-controls">
    <button id="radar_playbtn" class="btn">&#9208; Pausa</button>
    <input id="radar_slider" type="range" min="0" max="12" value="12" step="1" style="flex:1" />
    <span id="radar_label" class="label"></span>
  </div>
  <p id="radar_status" class="note"></p>
</section>

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
<footer>Generato con meteoP@d0 &middot; dati modelli numerici pubblici (Open-Meteo, ECMWF OpenCharts CC BY 4.0, RainViewer)</footer>

<script>
{PLAYER_JS_ONCE}
{RADAR_JS}
initRadarMap({args.lat}, {args.lon});
</script>
</body>
</html>
"""

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK -> {args.out}")


if __name__ == "__main__":
    main()
