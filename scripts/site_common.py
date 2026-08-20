#!/usr/bin/env python3
"""
Pezzi condivisi tra build_comparison_table.py e build_site.py: storico
revisioni dello strumento, selettore tema chiaro/scuro, footer. Un'unica
fonte cosi' i due script (che restano indipendenti/eseguibili da soli) non
divergono piu' silenziosamente.
"""

# Selettore tema chiaro/scuro: le variabili CSS in table_engine.css gia'
# supportano :root[data-theme="dark"|"light"] (oltre a prefers-color-scheme
# automatico); qui c'e' solo il controllo visivo + lo script minimo per
# leggerlo/salvarlo. Se lo script non viene eseguito (anteprime senza JS) il
# bottone semplicemente non fa nulla: il tema segue comunque il sistema
# operativo via prefers-color-scheme, quindi il contenuto resta leggibile.
THEME_TOGGLE_HTML = ('''<script>(function(){try{var t=localStorage.getItem('meteo-garbino-theme');'''
                      '''if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t);'''
                      '''}catch(e){}})();</script>\n'''
                      '''<button type="button" class="theme-toggle" aria-label="Cambia tema chiaro/scuro" '''
                      '''title="Tema chiaro/scuro" onclick="(function(){var d=document.documentElement,'''
                      '''mq=window.matchMedia('(prefers-color-scheme: dark)');'''
                      '''var cur=d.getAttribute('data-theme')||(mq.matches?'dark':'light');'''
                      '''var next=cur==='dark'?'light':'dark';d.setAttribute('data-theme',next);'''
                      '''try{localStorage.setItem('meteo-garbino-theme',next);}catch(e){}})()">'''
                      '''<span class="theme-toggle-icon icon-sun">☀️</span>'''
                      '''<span class="theme-toggle-icon icon-moon">\U0001f319</span></button>''')

# Interazione tabella<->grafico: generica, guidata dai dati nel markup (non
# sa nulla del parametro specifico). Un pulsante .chart-toggle-btn mostra/
# nasconde i fratelli .table-wrap/.chart-wrap dentro lo stesso <details> (il
# grafico e' la vista di default, la tabella si apre col pulsante); sopra
# ogni .chart-svg, muovendo (o toccando) il puntatore, cerca il punto dati
# piu' vicino tra i .chart-pt (cerchi invisibili con data-x/data-y in
# coordinate SVG e data-rows gia' formattato in Python/JS al momento della
# generazione: una riga "etichetta,valore,colore" per ogni serie, media
# compresa) e disegna il crosshair con tutte le righe colorate. Una volta
# mostrato il crosshair resta visibile (non sparisce quando il puntatore
# esce dal grafico), cosi' il valore letto resta leggibile anche dopo aver
# spostato lo sguardo. Stesso script, sia nei bollettini statici (embedded
# qui sotto) sia nel generatore live (docs/genera.html carica lo stesso
# codice): il markup che produce e' identico (stesse classi/attributi),
# quindi un solo script basta per entrambi. Se non viene eseguito, tabella e
# grafico restano comunque entrambi presenti nell'HTML: il grafico (SVG puro,
# nessun JS necessario per disegnarlo) e' quello visibile di default.
CHART_INTERACTION_JS = '''<script>(function(){
  function svgPoint(svg, clientX, clientY){
    var pt = svg.createSVGPoint();
    pt.x = clientX; pt.y = clientY;
    var ctm = svg.getScreenCTM();
    if (!ctm) return null;
    return pt.matrixTransform(ctm.inverse());
  }
  function nearestPoint(svg, svgX){
    var pts = svg.querySelectorAll('.chart-pt'), best = null, bestDist = Infinity;
    for (var i = 0; i < pts.length; i++) {
      var d = Math.abs(parseFloat(pts[i].getAttribute('data-x')) - svgX);
      if (d < bestDist) { bestDist = d; best = pts[i]; }
    }
    return best;
  }
  function colorVar(c){ return c.indexOf('var(') === 0 ? c : ('var(' + c + ')'); }
  function escHtml(s){
    return String(s).replace(/[&<>"]/g, function(c){ return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; });
  }
  // L'etichetta con i valori e' un tooltip HTML in position:fixed (vedi CSS
  // .chart-tooltip), non testo SVG: un font-size SVG fisso diventerebbe
  // illeggibile o farebbe traboccare il riquadro quando il grafico si
  // restringe alla larghezza di uno smartphone (fino a 13 righe media+
  // modelli su un grafico alto poche decine di pixel). Un overlay HTML usa
  // px reali indipendenti dallo scaling del viewBox, e puo' sporgere
  // liberamente sopra il resto della pagina come un tooltip normale (non e'
  // vincolato all'altezza del grafico). vline/hline/dot restano invece SVG,
  // allineati ai dati.
  // Grafici il cui puntatore e' attualmente mostrato: essendo il tooltip
  // position:fixed (coordinate di viewport, non di pagina), scorrendo la
  // pagina il punto SVG si sposta ma il tooltip restava fermo, "staccandosi"
  // visivamente dal grafico. Tenendo traccia dei grafici attivi possiamo
  // ricalcolare la posizione del tooltip ad ogni scroll/resize (stesso
  // calcolo di updateCrosshair, che usa getScreenCTM: riflette sempre la
  // posizione a schermo corrente), cosi' il tooltip segue il punto invece di
  // restare ancorato a coordinate ormai sbagliate.
  var activeCharts = [];
  function hideTooltip(svg){
    var g = svg.querySelector('.chart-crosshair');
    var tooltip = svg.parentElement && svg.parentElement.querySelector(':scope > .chart-tooltip');
    if (g) g.style.display = 'none';
    if (tooltip) tooltip.style.display = 'none';
    svg.__activePt = null;
    var idx = activeCharts.indexOf(svg);
    if (idx !== -1) activeCharts.splice(idx, 1);
  }
  function updateCrosshair(svg, pt){
    var g = svg.querySelector('.chart-crosshair');
    var tooltip = svg.parentElement && svg.parentElement.querySelector(':scope > .chart-tooltip');
    if (!g || !pt) return;
    var vb = svg.viewBox.baseVal;
    var x = parseFloat(pt.getAttribute('data-x')), y = parseFloat(pt.getAttribute('data-y'));
    var vline = g.querySelector('.ch-vline'), hline = g.querySelector('.ch-hline'), dot = g.querySelector('.ch-dot');
    vline.setAttribute('x1', x); vline.setAttribute('x2', x);
    vline.setAttribute('y1', vb.y); vline.setAttribute('y2', vb.y + vb.height);
    hline.setAttribute('y1', y); hline.setAttribute('y2', y);
    hline.setAttribute('x1', vb.x); hline.setAttribute('x2', vb.x + vb.width);
    dot.setAttribute('cx', x); dot.setAttribute('cy', y);
    g.style.display = '';
    svg.__activePt = pt;
    if (activeCharts.indexOf(svg) === -1) activeCharts.push(svg);

    if (!tooltip) return;
    var dateTimeLabel = pt.getAttribute('data-label') || '';
    var rows = (pt.getAttribute('data-rows') || '').split('|').filter(Boolean).map(function(r){
      var parts = r.split(',');
      return { label: parts[0], value: parts[1], color: colorVar(parts[2]) };
    });
    tooltip.innerHTML = '<div class="tt-date">' + escHtml(dateTimeLabel) + '</div>' +
      rows.map(function(r){
        return '<div class="tt-row" style="color:' + r.color + '">' + escHtml(r.label) + ': ' + escHtml(r.value) + '</div>';
      }).join('');
    tooltip.style.display = 'block';

    var ctm = svg.getScreenCTM();
    if (!ctm) return;
    var spt = svg.createSVGPoint();
    spt.x = x; spt.y = y;
    var screenPt = spt.matrixTransform(ctm);
    var tw = tooltip.offsetWidth, th = tooltip.offsetHeight;
    var left = screenPt.x + 14, top = screenPt.y - th - 14;
    if (left + tw > window.innerWidth - 4) left = screenPt.x - tw - 14;
    if (left < 4) left = 4;
    if (top < 4) top = screenPt.y + 14;
    if (top + th > window.innerHeight - 4) top = window.innerHeight - th - 4;
    tooltip.style.left = left + 'px';
    tooltip.style.top = top + 'px';
  }
  function repositionActive(){
    // Copia perche' hideTooltip modifica activeCharts durante l'iterazione.
    activeCharts.slice().forEach(function(svg){
      if (!svg.isConnected || svg.getClientRects().length === 0) { hideTooltip(svg); return; }
      if (svg.__activePt) updateCrosshair(svg, svg.__activePt);
    });
  }
  var repositionScheduled = false;
  function scheduleReposition(){
    if (repositionScheduled) return;
    repositionScheduled = true;
    requestAnimationFrame(function(){ repositionScheduled = false; repositionActive(); });
  }
  function handleMove(e){
    var svg = e.target && e.target.closest && e.target.closest('.chart-svg');
    if (!svg) return;
    var cx = e.touches ? e.touches[0].clientX : e.clientX, cy = e.touches ? e.touches[0].clientY : e.clientY;
    var p = svgPoint(svg, cx, cy);
    if (!p) return;
    var pt = nearestPoint(svg, p.x);
    if (pt) updateCrosshair(svg, pt);
  }
  document.addEventListener('pointermove', handleMove);
  document.addEventListener('pointerdown', handleMove);
  window.addEventListener('scroll', scheduleReposition, { passive: true, capture: true });
  window.addEventListener('resize', scheduleReposition, { passive: true });
  document.addEventListener('click', function(e){
    var btn = e.target && e.target.closest && e.target.closest('.chart-toggle-btn');
    if (!btn) return;
    var details = btn.closest('details.param');
    if (!details) return;
    var tableWrap = details.querySelector(':scope > .table-wrap'), chartWrap = details.querySelector(':scope > .chart-wrap');
    if (!tableWrap || !chartWrap) return;
    var showingTable = !tableWrap.hasAttribute('hidden');
    if (showingTable) { tableWrap.setAttribute('hidden', ''); chartWrap.removeAttribute('hidden'); btn.textContent = 'Tabella'; }
    else {
      var svgInChart = chartWrap.querySelector('.chart-svg');
      if (svgInChart) hideTooltip(svgInChart);
      chartWrap.setAttribute('hidden', ''); tableWrap.removeAttribute('hidden'); btn.textContent = 'Grafico';
    }
  });
})();</script>'''

# Storico revisioni dello strumento. Aggiungere una voce in cima ad ogni
# modifica rilasciata; viene stampata in fondo a ogni file HTML generato e
# nella pagina dedicata docs/revisioni.html.
CHANGELOG = [
    {"version": "1.0.19", "date": "20/08/2026", "changes": [
        "Possibile fix per i grafici invisibili su iPhone/Safari segnalati per i parametri convettivi nel generatore live: l'SVG del grafico aveva solo larghezza/altezza via CSS (width:100%;height:auto) senza attributi width/height propri, e Safari puo' non ricavare correttamente il rapporto d'aspetto dal solo viewBox in questo caso (bug noto di WebKit, non riproducibile con gli strumenti di test disponibili in questo ambiente, solo Chromium). Aggiunti attributi width/height espliciti sull'SVG di ogni grafico, in aggiunta al CSS responsive gia' presente.",
    ]},
    {"version": "1.0.18", "date": "20/08/2026", "changes": [
        "Nuova sezione \"Marea\" per le localit&agrave; costiere: livello del mare (Open-Meteo Marine API, modello Best Match/GTSM), stessa presentazione dei parametri convettivi (sorgente singola, non confronto multi-modello).",
        "Grafico di vento e moto ondoso: l'etichetta del puntatore mostrava solo il valore (velocit&agrave;/altezza), non la direzione. Ora mostra entrambi, sia per la media sia per ogni modello.",
        "Corretto un bug del puntatore: scorrendo la pagina dopo averlo usato, l'etichetta (in position:fixed, quindi ancorata allo schermo) restava ferma invece di seguire il grafico, staccandosi visivamente dal punto indicato. Ora la posizione viene ricalcolata ad ogni scroll/resize. Individuato e corretto anche un bug pi&ugrave; sottile emerso durante la verifica: il controllo che doveva nascondere il puntatore quando il grafico non &egrave; pi&ugrave; visibile (es. passando alla vista tabella) si basava su una propriet&agrave; (<code>offsetParent</code>) che per l'elemento <code>&lt;svg&gt;</code> risulta sempre vuota in Chromium anche a grafico visibile: il puntatore si nascondeva erroneamente al primo scroll o ridimensionamento della finestra, sempre. Ora il controllo usa <code>getClientRects()</code>, corretto per gli SVG.",
    ]},
    {"version": "1.0.17", "date": "20/08/2026", "changes": [
        "Generatore live: il campo citt&agrave; propone ora un menu di localit&agrave; mentre si scrive (autocompletamento, ordinato alfabeticamente), non solo dopo una ricerca fallita: un clic riempie il campo senza generare subito il bollettino.",
        "Rimpicciolito il riquadro del puntatore del grafico su smartphone (font e interlinea ridotti, larghezza massima limitata): sugli schermi stretti risultava sproporzionato rispetto al grafico, che invece si restringe.",
    ]},
    {"version": "1.0.16", "date": "20/08/2026", "changes": [
        "Etichetta del puntatore del grafico: riscritta come riquadro HTML sovrapposto alla pagina invece che testo SVG. Un +2pt sul testo SVG restava comunque illeggibile su smartphone (il grafico si restringe alla larghezza dello schermo e ne scala in giu' anche il testo) o avrebbe fatto traboccare il riquadro nei parametri con piu' modelli (fino a 13 righe): ora il testo usa px reali (13px), sempre leggibile e identico su ogni dispositivo, e il riquadro puo' sporgere liberamente sopra il resto della pagina come un tooltip.",
        "Generatore live: il campo \"Nome citt&agrave;\" mostra ora \"es. Imola\" come esempio invece di \"es. Bologna\", coerente con Imola come localit&agrave; principale del sito.",
    ]},
    {"version": "1.0.15", "date": "20/08/2026", "changes": [
        "Logo centrato orizzontalmente nell'intestazione.",
        "Corretto un bug di layout che lasciava circa 260px di spazio vuoto sotto il blocco titolo/descrizione: una regola CSS scritta per il vecchio impaginato (logo a fianco del testo) faceva ancora crescere in verticale il blocco titolo dopo lo spostamento del logo sopra il testo.",
        "Generatore live: se la citt&agrave; cercata non viene trovata, propone in ordine alfabetico le localit&agrave; pi&ugrave; simili (accorciando progressivamente il nome cercato finch&eacute; non trova corrispondenze); un clic su un suggerimento genera subito il bollettino per quella localit&agrave;.",
    ]},
    {"version": "1.0.14", "date": "20/08/2026", "changes": [
        "Corretto il puntatore del grafico: dalla v1.0.11 mostrava media e modelli ma aveva perso la data/ora del punto (rimasta nell'attributo dati ma mai disegnata). Ora la prima riga dell'etichetta e' sempre data e ora, in grassetto, seguita da media e ogni modello.",
    ]},
    {"version": "1.0.13", "date": "20/08/2026", "changes": [
        "Corretto un errore ortografico: l'avviso \"N modelli esclusi\" veniva scritto \"esclusoi\" al plurale.",
        "Generatore live: aggiunti i pulsanti di durata \"1 giorno\" e \"2 giorni\", oltre ai gi&agrave; presenti 3 e 7 giorni.",
    ]},
    {"version": "1.0.12", "date": "20/08/2026", "changes": [
        "Logo Meteo Garbino ingrandito (x3) nell'intestazione.",
        "Rimossa la barra \"Severit&agrave;\" (legenda colori + elenco modelli) sotto l'almanacco: era un'altra fonte di confusione simile alla sezione Attenzione gi&agrave; rimossa, e l'informazione sui colori resta comunque nella descrizione di ogni parametro.",
    ]},
    {"version": "1.0.11", "date": "20/08/2026", "changes": [
        "Rimossa la sezione \"Attenzione\": generava confusione, l'informazione era gia' leggibile nelle celle colorate delle tabelle.",
        "Il grafico e' ora la vista di default di ogni parametro (prima era la tabella); un pulsante la converte in tabella e viceversa.",
        "Grafico: ogni modello ha una linea di colore diverso per riconoscerlo a colpo d'occhio, con legenda sotto il grafico.",
        "Puntatore del grafico: resta visibile una volta usato (prima spariva non appena il mouse usciva dal grafico), e la sua etichetta mostra sempre tutti i valori (media e ogni singolo modello), non solo la media.",
        "Grafico: larghezza sempre adattata allo schermo del dispositivo, niente piu' scorrimento orizzontale interno (restava solo per le tabelle orarie, che continuano a scorrere verso destra).",
        "Intestazione: il logo Meteo Garbino ora sta sopra al titolo/descrizione invece che di fianco.",
    ]},
    {"version": "1.0.10", "date": "20/08/2026", "changes": [
        "Nuova sezione \"Attenzione\" in ogni tabella: scansiona automaticamente tutti i parametri e segnala giorni/ore con valori in soglia rossa o fucsia (rischio elevato/estremo), con motivo e valore.",
        "Nuova pagina dedicata Revisioni (docs/revisioni.html), separata dalla tabella: raccoglie tutto lo storico che prima stava solo in fondo ad ogni bollettino.",
        "Aggiunta Imola come localita' principale, con bollettino giornaliero 7 giorni.",
        "Versione mostrata anche nel footer, non solo nel badge in alto.",
        "Ogni tabella parametro ha ora un pulsante \"Grafico\" che la converte in un grafico a linee (una per modello, piu' la media in evidenza): passandoci sopra il mouse (o toccando su mobile) appare un puntatore con linea verticale/orizzontale ed etichetta di valore e data/ora. Funziona anche senza rieseguire i calcoli: il grafico e' gia' pronto, il pulsante mostra/nasconde.",
    ]},
    {"version": "1.0.9", "date": "20/08/2026", "changes": [
        "Ridotta la larghezza della colonna dei modelli (etichetta di riga) da 150px a 120px, per lasciare piu' spazio alle colonne dati.",
    ]},
    {"version": "1.0.8", "date": "20/08/2026", "changes": [
        "Sito molto piu' veloce da navigare: le pagine copiate in docs/ ora linkano CSS e logo come file esterni condivisi invece di incorporarli (base64) su ognuna — scaricati una volta sola dal browser e riusati in cache su tutte le pagine successive. La home e' passata da ~500KB a ~4KB, i bollettini da 600KB-1.1MB a 100-600KB.",
        "Solo la prima sezione (Temperatura) e' aperta di default in ogni tabella: con tabelle fino a 168 colonne orarie, tenerle tutte espanse appesantiva inutilmente il caricamento iniziale. Le altre restano un clic di distanza (funziona anche senza JavaScript: sono elementi HTML nativi).",
    ]},
    {"version": "1.0.7", "date": "20/08/2026", "changes": [
        "Aggiunto il footer \"MeteoGarbino225®\" in fondo a ogni pagina del sito.",
    ]},
    {"version": "1.0.6", "date": "20/08/2026", "changes": [
        "Aggiunto un selettore tema chiaro/scuro (bottone in alto a destra): forza il tema scelto (salvato nel browser) invece di seguire solo il tema del sistema operativo.",
        "Rimossa la parola \"bollettini\" dal titolo del sito.",
        "Rifiniture responsive per schermi stretti (telefono): spazio per il selettore tema, logo e margini ridotti sotto i 640px.",
        "Aggiunto il tag <code>&lt;meta name=&quot;viewport&quot;&gt;</code> mancante, e corretto uno scroll orizzontale indesiderato su schermi stretti causato dalle liste puntate (Note/Revisioni) e dalle colonne delle tabelle che non si restringevano sotto la loro larghezza di contenuto.",
    ]},
    {"version": "1.0.5", "date": "20/08/2026", "changes": [
        "Nuovo sito su GitHub Pages (docs/): pagina indice con le tabelle già pronte, e un generatore live (docs/genera.html) dove si sceglie città/coordinate, durata (3 o 7 giorni) e risoluzione (24/12/6/3/1 ore) e la tabella viene calcolata al volo nel browser chiamando direttamente le API Open-Meteo.",
        "Fix impaginazione: la griglia delle tabelle usa sempre il numero reale di colonne (--ncols) invece di assumere 7 colonne fisse in modalità giornaliera, così anche una tabella giornaliera a 3 giorni non lascia colonne vuote.",
    ]},
    {"version": "1.0.4", "date": "19/08/2026", "changes": [
        "Nuova sezione \"Parametri convettivi\" (rischio temporali): CAPE, CIN, Lifted Index, quota dello zero termico, altezza dello strato limite, acqua precipitabile — una tabella separata per ciascun parametro, prima della tabella delle revisioni.",
        "A differenza degli altri parametri, i dati convettivi provengono da un'unica sorgente (profilo verticale del blend Best Match), non da un confronto multi-modello: Open-Meteo non espone questi campi per i singoli centri di calcolo.",
    ]},
    {"version": "1.0.3", "date": "19/08/2026", "changes": [
        "Aggiunta questa tabella delle revisioni in fondo ad ogni file generato.",
        "Nuova convenzione nome file: Luogo_ggmm-inizio_ggmm-fine_ggmmaaaa-ora-generazione.html.",
    ]},
    {"version": "1.0.2", "date": "19/08/2026", "changes": [
        "Vento: direzione e raffica mostrate anche per ogni singolo modello, non solo per la media.",
        "Vento e moto ondoso: formato compatto medio/raffica con direzione a capo (es. 2/3 poi SO sotto), per restare dentro alla cella anche con 72 colonne orarie.",
        "Aggiunto il logo Meteo Garbino in alto a destra nell'intestazione, ingrandito e riposizionato su richiesta.",
        "Fix impaginazione: eliminato lo spazio vuoto sotto l'eyebrow causato dal logo piu' alto del testo.",
    ]},
    {"version": "1.0.1", "date": "19/08/2026", "changes": [
        "Fix caratteri accentati: aggiunto il tag <code>&lt;meta charset=&quot;utf-8&quot;&gt;</code> mancante nei file scaricati come file locale.",
    ]},
    {"version": "1.0.0", "date": "18/08/2026", "changes": [
        "Prima versione con dati reali: lo strumento passa dal mockup con dati di prova ai dati veri scaricati da Open-Meteo (fetch_forecast.py + fetch_marine.py).",
        "Tabella HTML resa completamente statica (nessun JavaScript), per essere leggibile anche nei client che non eseguono script (anteprime, email, ecc.).",
    ]},
]

CURRENT_VERSION = CHANGELOG[0]["version"]


def render_changelog(changelog):
    rows = []
    for entry in changelog:
        changes_html = "<ul>" + "".join(f"<li>{c}</li>" for c in entry["changes"]) + "</ul>"
        rows.append(f'<tr><td class="rv-version">{entry["version"]}</td>'
                     f'<td class="rv-date">{entry["date"]}</td>'
                     f'<td class="rv-changes">{changes_html}</td></tr>')
    return (f'<div class="revisions"><h2>Revisioni</h2>'
            f'<table><thead><tr><th>Versione</th><th>Data</th><th>Novit&agrave;</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def render_footer():
    return (f'<footer class="site-footer">MeteoGarbino225&reg; &middot; Rev. {CURRENT_VERSION} &middot; '
            f'<a href="revisioni.html">Revisioni e novit&agrave;</a></footer>')
