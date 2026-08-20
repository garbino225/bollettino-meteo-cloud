#!/usr/bin/env python3
"""
Genera il sito statico (per GitHub Pages) a partire dai bollettini gia'
prodotti in output/: copia ogni file HTML in docs/ e genera un
docs/index.html con le card di collegamento, leggendo titolo/periodo/
versione direttamente dall'HTML di ciascun bollettino (nessun dato
duplicato a mano), piu' docs/revisioni.html con lo storico versioni
(scripts/site_common.py, condiviso con build_comparison_table.py).

A differenza dei file autonomi in output/ (pensati per essere inviati
singolarmente, con CSS e logo incorporati), le pagine copiate qui dentro
usano un link esterno a table_engine.css/logo_garbino.png in docs/assets/:
scaricati una volta sola e riusati in cache su tutte le pagine del sito,
per una navigazione interna molto piu' leggera.

Uso:
    python3 build_site.py
"""
import glob
import os
import re
import shutil

from site_common import THEME_TOGGLE_HTML, CHANGELOG, render_changelog, render_footer

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(SCRIPT_DIR, "..")
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
DOCS_DIR = os.path.join(ROOT_DIR, "docs")
DOCS_ASSETS_DIR = os.path.join(DOCS_DIR, "assets")
LOGO_PATH = os.path.join(ROOT_DIR, "assets", "logo_garbino.png")

# Localita' messa in evidenza per prima nell'indice (badge "citta' principale").
# Il match e' sul nome file (es. "imola_giornaliera.html").
MAIN_CITY_FILE_PREFIX = "imola"

# docs/genera.html e docs/assets/meteo-engine.js sono scritti a mano (il
# generatore live client-side): questo script li lascia intatti, copia solo
# gli asset condivisi (CSS, logo) e aggiunge la card di collegamento.


def extract(html, pattern, default=""):
    m = re.search(pattern, html, re.S)
    return m.group(1).strip() if m else default


def page_meta(html):
    title = extract(html, r"<title>(.*?)</title>")
    sub = extract(html, r'class="sub">(.*?)</p>')
    version = extract(html, r'class="version-badge">(.*?)</div>')
    return {"title": title, "sub": sub, "version": version}


def lighten_for_site(html):
    """I bollettini di output/ sono file autonomi (CSS e logo incorporati
    come base64) cosi' funzionano anche inviati singolarmente. Dentro al
    sito quell'incorporamento e' solo peso morto ripetuto su ogni pagina
    (~500KB-1MB a pagina, mai in cache): qui lo si sostituisce con un link
    esterno a table_engine.css e al logo in docs/assets/, scaricati una
    volta sola dal browser e riusati su tutte le pagine successive."""
    html = re.sub(r"<style>.*?</style>", '<link rel="stylesheet" href="assets/table_engine.css">',
                   html, count=1, flags=re.S)
    html = re.sub(r'src="data:image/png;base64,[^"]*"', 'src="assets/logo_garbino.png"', html)
    return html


def build_revisions_page():
    html = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Meteo Garbino — Revisioni</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@700;800;900&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600;700&display=swap">
<link rel="stylesheet" href="assets/table_engine.css">
{THEME_TOGGLE_HTML}
<div class="page">
  <div class="masthead">
    <div class="masthead-row">
      <div class="masthead-main">
        <div class="eyebrow-row">
          <div class="eyebrow">Storico dello strumento</div>
        </div>
        <h1>Revisioni <em>&middot; novit&agrave;</em></h1>
        <p class="sub"><a href="index.html">&larr; Torna alla home</a></p>
      </div>
    </div>
    <div class="spectrum"></div>
  </div>

  {render_changelog(CHANGELOG)}

  {render_footer()}
</div>
"""
    out_path = os.path.join(DOCS_DIR, "revisioni.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK -> {out_path}")


def build():
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(DOCS_ASSETS_DIR, exist_ok=True)

    shutil.copyfile(os.path.join(SCRIPT_DIR, "table_engine.css"), os.path.join(DOCS_ASSETS_DIR, "table_engine.css"))
    if os.path.exists(LOGO_PATH):
        shutil.copyfile(LOGO_PATH, os.path.join(DOCS_ASSETS_DIR, "logo_garbino.png"))

    build_revisions_page()

    sources = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*.html")))
    if not sources:
        raise SystemExit(f"Nessun file HTML trovato in {OUTPUT_DIR}: genera prima i bollettini con build_comparison_table.py")

    cards = []
    for src in sources:
        fname = os.path.basename(src)
        html_src = open(src, encoding="utf-8").read()
        meta = page_meta(html_src)
        with open(os.path.join(DOCS_DIR, fname), "w", encoding="utf-8") as f:
            f.write(lighten_for_site(html_src))
        cards.append({"file": fname, "is_main": fname.startswith(MAIN_CITY_FILE_PREFIX), **meta})

    # La localita' principale va prima, poi tutte le altre nell'ordine dei file.
    cards.sort(key=lambda c: (not c["is_main"], c["file"]))

    logo_html = '<img class="brand-logo" src="assets/logo_garbino.png" alt="Meteo Garbino">' if os.path.exists(LOGO_PATH) else ""

    genera_card = '''<a class="site-card site-card-highlight" href="genera.html">
      <div class="site-card-title">Genera il tuo bollettino</div>
      <div class="site-card-sub">Scegli citt&agrave; (o coordinate), durata e risoluzione oraria: la tabella viene generata al volo nel browser con dati reali Open-Meteo.</div>
      <div class="site-card-foot"><span class="version-badge">live</span><span class="site-card-arrow">apri &rarr;</span></div>
    </a>'''

    def card_html(c):
        title = c["title"] or c["file"]
        main_badge = '<span class="site-card-badge">citt&agrave; principale</span>' if c["is_main"] else ""
        return f'''<a class="site-card{' site-card-highlight' if c['is_main'] else ''}" href="{c["file"]}">
      <div class="site-card-title">{title}{main_badge}</div>
      <div class="site-card-sub">{c["sub"] or "&nbsp;"}</div>
      <div class="site-card-foot"><span class="version-badge">{c["version"] or "—"}</span><span class="site-card-arrow">apri &rarr;</span></div>
    </a>'''

    cards_html = genera_card + "\n" + "\n".join(card_html(c) for c in cards)

    html = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Meteo Garbino — Confronto multi-modello</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@700;800;900&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600;700&display=swap">
<link rel="stylesheet" href="assets/table_engine.css">
{THEME_TOGGLE_HTML}
<div class="page">
  <div class="masthead">
    <div class="masthead-row">
      <div class="brand-stack">
        {logo_html}
      </div>
      <div class="masthead-main">
        <div class="eyebrow-row">
          <div class="eyebrow">Dati reali &middot; confronto multi-modello</div>
        </div>
        <h1>Meteo Garbino</h1>
        <p class="sub">Tabelle di confronto multi-modello, generate da dati reali Open-Meteo. Pagine statiche e responsive; solo il generatore live e il selettore tema usano JavaScript.</p>
      </div>
    </div>
    <div class="spectrum"></div>
  </div>

  <div class="site-grid">
    {cards_html}
  </div>

  {render_footer()}
</div>
"""

    out_path = os.path.join(DOCS_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK -> {out_path} ({len(cards)} pagine)")


if __name__ == "__main__":
    build()
