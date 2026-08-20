#!/usr/bin/env python3
"""
Genera il sito statico (per GitHub Pages) a partire dai bollettini gia'
prodotti in output/: copia ogni file HTML in docs/ e genera un
docs/index.html con le card di collegamento, leggendo titolo/periodo/
versione direttamente dall'HTML di ciascun bollettino (nessun dato
duplicato a mano).

Nessuna dipendenza da rete o JavaScript: stessa filosofia di
build_comparison_table.py.

Uso:
    python3 build_site.py
"""
import base64
import glob
import os
import re
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.join(SCRIPT_DIR, "..")
OUTPUT_DIR = os.path.join(ROOT_DIR, "output")
DOCS_DIR = os.path.join(ROOT_DIR, "docs")
DOCS_ASSETS_DIR = os.path.join(DOCS_DIR, "assets")
LOGO_PATH = os.path.join(ROOT_DIR, "assets", "logo_garbino.png")

# docs/genera.html e docs/assets/meteo-engine.js sono scritti a mano (il
# generatore live client-side): questo script li lascia intatti, copia solo
# gli asset condivisi (CSS, logo) e aggiunge la card di collegamento.


def b64_file(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def extract(html, pattern, default=""):
    m = re.search(pattern, html, re.S)
    return m.group(1).strip() if m else default


def page_meta(path):
    html = open(path, encoding="utf-8").read()
    title = extract(html, r"<title>(.*?)</title>")
    sub = extract(html, r'class="sub">(.*?)</p>')
    version = extract(html, r'class="version-badge">(.*?)</div>')
    return {"title": title, "sub": sub, "version": version}


def build():
    os.makedirs(DOCS_DIR, exist_ok=True)
    os.makedirs(DOCS_ASSETS_DIR, exist_ok=True)

    shutil.copyfile(os.path.join(SCRIPT_DIR, "table_engine.css"), os.path.join(DOCS_ASSETS_DIR, "table_engine.css"))
    if os.path.exists(LOGO_PATH):
        shutil.copyfile(LOGO_PATH, os.path.join(DOCS_ASSETS_DIR, "logo_garbino.png"))

    sources = sorted(glob.glob(os.path.join(OUTPUT_DIR, "*.html")))
    if not sources:
        raise SystemExit(f"Nessun file HTML trovato in {OUTPUT_DIR}: genera prima i bollettini con build_comparison_table.py")

    cards = []
    for src in sources:
        fname = os.path.basename(src)
        shutil.copyfile(src, os.path.join(DOCS_DIR, fname))
        meta = page_meta(src)
        cards.append({"file": fname, **meta})

    css = open(os.path.join(SCRIPT_DIR, "table_engine.css"), encoding="utf-8").read()

    logo_html = ""
    if os.path.exists(LOGO_PATH):
        logo_html = f'<img class="brand-logo" src="data:image/png;base64,{b64_file(LOGO_PATH)}" alt="Meteo Garbino">'

    genera_card = '''<a class="site-card site-card-highlight" href="genera.html">
      <div class="site-card-title">Genera il tuo bollettino</div>
      <div class="site-card-sub">Scegli citt&agrave; (o coordinate), durata e risoluzione oraria: la tabella viene generata al volo nel browser con dati reali Open-Meteo.</div>
      <div class="site-card-foot"><span class="version-badge">live</span><span class="site-card-arrow">apri &rarr;</span></div>
    </a>'''

    cards_html = genera_card + "\n" + "\n".join(
        f'''<a class="site-card" href="{c["file"]}">
      <div class="site-card-title">{c["title"] or c["file"]}</div>
      <div class="site-card-sub">{c["sub"] or "&nbsp;"}</div>
      <div class="site-card-foot"><span class="version-badge">{c["version"] or "—"}</span><span class="site-card-arrow">apri &rarr;</span></div>
    </a>'''
        for c in cards
    )

    html = f"""<meta charset="utf-8">
<title>Meteo Garbino — Bollettini multi-modello</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@700;800;900&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600;700&display=swap">
<style>
{css}
.site-grid{{ display:grid; grid-template-columns:repeat(auto-fill,minmax(280px,1fr)); gap:16px; }}
.site-card{{ display:flex; flex-direction:column; gap:8px; background:var(--panel); border:1px solid var(--panel-line);
  border-radius:12px; padding:18px 20px; text-decoration:none; color:inherit; }}
.site-card-title{{ font-family:"Archivo", sans-serif; font-weight:800; font-size:17px; color:var(--ink); }}
.site-card-sub{{ font-size:13px; color:var(--ink-soft); line-height:1.5; flex:1; }}
.site-card-foot{{ display:flex; align-items:center; justify-content:space-between; margin-top:4px; }}
.site-card-arrow{{ font-family:"IBM Plex Mono", monospace; font-size:12px; font-weight:600; color:var(--accent); }}
.site-card-highlight{{ border-color:var(--accent); background:var(--accent-soft); }}
</style>
<div class="page">
  <div class="masthead">
    <div class="masthead-row">
      <div class="masthead-main">
        <div class="eyebrow-row">
          <div class="eyebrow">Dati reali &middot; confronto multi-modello</div>
        </div>
        <h1>Meteo Garbino <em>&middot; bollettini</em></h1>
        <p class="sub">Tabelle di confronto multi-modello, generate da dati reali Open-Meteo. Nessun JavaScript: pagine statiche autonome.</p>
      </div>
      <div class="brand-stack">
        {logo_html}
      </div>
    </div>
    <div class="spectrum"></div>
  </div>

  <div class="site-grid">
    {cards_html}
  </div>
</div>
"""

    out_path = os.path.join(DOCS_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"OK -> {out_path} ({len(cards)} pagine)")


if __name__ == "__main__":
    build()
