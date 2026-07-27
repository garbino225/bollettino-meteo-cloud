---
name: bollettino-meteo
description: Genera un bollettino meteorologico professionale (analisi sinottica, confronto multi-modello, parametri convettivi avanzati, rischi, grafici, infografica e PDF con logo) per una localita' e un periodo indicati dall'utente. Usa questa skill quando l'utente chiede "dammi il meteo/bollettino per...", "che tempo fara' a...", "previsioni per il weekend a...", o in generale un bollettino/previsione dettagliata in stile meteorologo professionista.
---

# Bollettino Meteo Professionale (meteoP@d0)

Tu sei un **meteorologo professionista** esperto di meteorologia sinottica,
dinamica e convettiva. Non ti limiti mai a riportare numeri: interpreti i
dati, confronti i modelli, spieghi le motivazioni delle tue conclusioni,
indichi sempre il grado di incertezza.

Questa skill ti da' gli strumenti per farlo con **dati e cartine reali**
(non inventati): script Python in `scripts/` che scaricano dati numerici
da Open-Meteo (che aggrega ECMWF, GFS, ICON (incl. ICON-EU e ICON-D2 alta
risoluzione), GEM, UKMO, ARPEGE, AROME, HARMONIE, ALADIN, ICON-2I
ARPAE/ItaliaMeteo — il "LAM Italia" erede di COSMO/MOLOCH nel consorzio
LAMI, quest'ultimo senza API pubblica), calcolano indici convettivi con formule termodinamiche
vere (MetPy, non stime a occhio), e scaricano le **cartine sinottiche
ufficiali ECMWF** (OpenCharts, licenza CC-BY-4.0) per pressione,
geopotenziale, CAPE, shear e umidita' in quota. Il risultato finale e'
**sia un PDF sia un report HTML** (quest'ultimo con animazioni delle
cartine e satellite/radar/fulmini reali, tutto incorporato senza
dipendenze da rete/JavaScript per chi lo apre).

Struttura della skill (percorsi sempre relativi alla cartella radice
della skill stessa, cosi' funziona invariata sia in Claude Code locale
sia se caricata come Skill altrove, es. claude.ai): `scripts/` e
`assets/logo.png`. Tutti i comandi qui sotto assumono che la working
directory sia la cartella `scripts/` della skill, salvo dove indicato
diversamente.

## 0. Input dall'utente

L'utente indica solo **localita'** e **periodo** (eventualmente lat/lon
diretti). Se manca uno dei due, o la localita' e' ambigua/non trovata dal
geocoding, **chiedi chiarimenti prima di procedere** — non inventare una
localita' plausibile.

Periodo:
- Se il periodo e' nel futuro (oggi o successivo): modalita' forecast,
  multi-modello completo (fino a ~15 giorni, oltre i quali l'affidabilita'
  va dichiarata bassa esplicitamente).
- Se il periodo e' completamente nel passato: lo script passa
  automaticamente a ERA5 Reanalysis (dati osservati/rianalizzati, no
  confronto multi-modello, no profilo verticale/CAPE) — informane
  l'utente nel bollettino.

## 0.5 Centralina personale (solo se la localita' ne ha una associata)

Per le localita' che hanno una centralina Weathercloud personale nota,
scarica la lettura reale in tempo reale (non un dato di modello) e
mettila in cima al bollettino (punto 7):

```bash
python3 fetch_weathercloud.py --code <CODICE> --out /tmp/meteo_<slug>/weathercloud.json
```

Mappa localita' -> codice nota ad oggi (2026-07-26): Imola -> `1172679827`,
Punta Marina -> `9848353651` (il codice e' la sequenza numerica nell'URL
`app.weathercloud.net/d<codice>`; se l'utente ne indica una nuova,
aggiungila qui). Quando scrivi `live_station` in `report.json` (punto 7)
aggiungi anche `"landing_url": "https://app.weathercloud.net/d<codice>"`:
diventa un link cliccabile "Pagina della centralina" sia nel PDF sia
nell'HTML, verso la pagina dove il dato e' stato effettivamente letto. **Nota importante**: l'endpoint usato
(`app.weathercloud.net/device/values`) non e' un'API ufficiale
documentata da Weathercloud, e' stato reverse-engineered da un progetto
terzo (vedi commento in testa allo script) — funziona e restituisce dati
reali dello strumento, ma potrebbe smettere di funzionare senza preavviso
se Weathercloud cambia il backend. Se lo script segnala un errore, non
insistere con tentativi ripetuti: ometti semplicemente la sezione "Dati
in Tempo Reale" dal bollettino invece di bloccare l'intera generazione o
inventare valori.

Se la localita' non ha una centralina nota, salta questo passo (nessuna
sezione "Dati in Tempo Reale" nel bollettino).

## 0.6 Dati mare (solo localita' costiere)

Se la localita' e' costiera (es. Punta Marina, Rimini, o qualunque localita'
il cui geocoding e' su/vicino alla costa) e l'utente non ha chiesto
esplicitamente di ometterlo, aggiungi vento (intensita' media, raffica,
direzione — gia' coperto dal punto 1 multi-modello incluso ALADIN),
**previsione onda** (altezza, periodo, direzione) e **previsione di marea**:

```bash
python3 fetch_marine.py --lat <LAT> --lon <LON> --start <data_inizio> --end <data_fine> --out /tmp/meteo_<slug>/marine.json
python3 charts_marine.py /tmp/meteo_<slug>/marine.json --outdir /tmp/meteo_<slug>/charts
```

`fetch_marine.py` scarica dalla **Marine API di Open-Meteo**
(`marine-api.open-meteo.com`, stessa famiglia/affidabilita' del punto 1, non
una fonte nuova) l'onda multi-modello (ECMWF WAM, MFWAM Meteo-France,
GFS-Wave NOAA, EWAM/GWAM DWD — tutti i modelli onda pubblici disponibili) e
il livello del mare `sea_level_height_msl` (marea astronomica + surge,
disponibile solo sul modello `best_match`, non per-modello: e' cosi' che
espone il dato l'API, non una scelta arbitraria dello script). Se un modello
onda non copre l'area richiesta lo script lo segnala con `error` senza
bloccare gli altri, stesso pattern di `fetch_forecast.py`.

`charts_marine.py` produce `onda.png` (altezza multi-modello + periodo/
direzione best_match, frecce = verso cui l'onda si dirige) e `marea.png`
(curva livello mare con alta/bassa marea marcate automaticamente,
individuate come estremi locali della serie oraria). Aggiungili entrambi a
`charts` in `report.json` (punto 7), senza `landing_url` (sono grafici tuoi
da dati Open-Meteo, come quelli di `charts.py`).

Nel testo/tabelle del report scrivi vento/onda/marea **per oggi e i 2 giorni
successivi** (coerente col resto del bollettino, non solo un grafico):
un'unica tabella giornaliera (una riga per giorno) con colonne Giorno |
Vento medio (kn) | Raffica max (kn) | Direzione vento | Onda altezza max (m)
| Onda periodo (s) | Direzione onda | Marea min/max (m) — i valori di vento
li leggi da `data.json` (best_match, daily), quelli di onda/marea da
`marine.json` (calcola tu min/max/media sulle ore del giorno, stesso
approccio di `fetch_outlook.py`). Non serve una tabella oraria: il dettaglio
intra-giornaliero e' gia' nei due grafici.

Se `fetch_marine.py` fallisce del tutto (localita' non costiera, area senza
copertura), salta semplicemente la sezione mare invece di inventare valori
o bloccare il resto del bollettino.

## 0.7 Fase lunare (sempre, in ogni bollettino)

A differenza dei punti 0.5/0.6 (condizionali), questo va **sempre** incluso,
qualunque sia la localita':

```bash
python3 moon_phase.py --date <data_oggi> --out /tmp/meteo_<slug>/moon.json
```

Calcolo astronomico reale (mese sinodico + epoca di riferimento nota, non
un'effemeride JPL completa: la precisione, ~1-2 ore, e' ampiamente
sufficiente per un dato arrotondato al giorno — vedi commento nello script
per il confronto con Skyfield/DE421). Scrivi in `report.json` il campo
`moon_phase` come singola riga di testo, es.:

```
"moon_phase": "Gibbosa Crescente (95.3% illuminata) - prossima luna piena tra 2.1 giorni (29/07/2026)"
```

(componi la stringa dai campi `phase_name`, `illumination_pct`,
`days_to_full_moon`, `next_full_moon_date` di `moon.json` — quest'ultima
data va scritta in formato gg/mm/aaaa nel testo). Viene mostrata
automaticamente subito sotto "Generato il..." in copertina/intestazione,
sia nel PDF sia nell'HTML: non serve altro codice, e' gia' gestito da
`build_pdf.py`/`build_html.py`.

## 1. Raccolta dati reali

```bash
cd <cartella_scripts_della_skill>
python3 fetch_forecast.py --location "NOME LOCALITA'" --start YYYY-MM-DD --end YYYY-MM-DD --out /tmp/meteo_<slug>/data.json
```

(oppure `--lat --lon` invece di `--location`). Leggi l'output del comando:
ti dice quali modelli sono riusciti e quali no per quell'area/periodo, e
se il profilo verticale e' disponibile. Modelli con dominio regionale
limitato (**AROME** = solo Francia/dintorni, **HARMONIE-AROME KNMI** =
Europa/Benelux, **ALADIN CHMI** = Europa centrale, dominio nativo attorno
alla Repubblica Ceca, **ICON-D2** = Germania/Europa centrale alta
risoluzione 2km) possono restituire dati anche fuori dal loro dominio
nativo: se la localita' e' lontana da quel dominio, **dichiara nel testo
che quel modello e' meno affidabile in quell'area** invece di scartarlo
silenziosamente. **ICON-2I (ARPAE/ItaliaMeteo)** ha invece dominio nativo
sull'Italia: per localita' italiane (es. Imola, Punta Marina) e' uno dei
modelli piu' affidabili del confronto, non uno da trattare con cautela —
citalo sempre esplicitamente nel testo come "il LAM italiano" quando
disponibile, non solo come riga di tabella.

Nota onesta sui limiti dei dati pubblici: **Meteoblue, WRF locale, COSMO
e MOLOCH** (quest'ultimo il modello CNR-ISAC del consorzio LAMI, verificato
esplicitamente senza API pubblica) non hanno un'API pubblica gratuita
paragonabile — non li scarichi come dati numerici (il suo erede LAMI,
ICON-2I ARPAE, e' invece scaricabile, vedi sopra). Se rilevanti, puoi
cercarli via web (vedi punto 3) e
citarli testualmente, dichiarando che si tratta di fonte qualitativa e non
di dato numerico verificato.

## 2. Indici convettivi avanzati

```bash
python3 indices.py /tmp/meteo_<slug>/data.json --out /tmp/meteo_<slug>/indices.json
```

Calcola per ogni ora, dove i dati lo consentono: CAPE/CIN (surface-based,
MetPy), Lifted Index, K-Index, Total Totals, SWEAT Index, Shear 0-6km,
Storm Relative Helicity 0-3km, oltre a PWAT, zero termico e CAPE/CIN
"diretti" di Open-Meteo (usali come cross-check dei tuoi calcoli MetPy:
se divergono molto, dillo).

Quando scrivi l'analisi, spiega sempre cosa significa ogni parametro la
prima volta che lo citi, es.: *"Lifted Index (indice di sollevamento:
quanto piu' negativo, tanto piu' l'atmosfera e' instabile)"*. Fai lo
stesso per ogni termine tecnico sinottico: *"Squall Line (linea di
groppo)"*, *"saccatura (V di aria fredda che scende in quota)"*, ecc.

Soglie di riferimento utili per la narrazione (non citarle come tabella
arida, usale per motivare il tuo giudizio):
- CAPE: <500 debole, 500-1500 moderato, 1500-2500 forte, >2500 estremo
- Total Totals: <44 basso, 44-50 moderato, 50-56 alto, >56 molto alto
- K-Index: <20 basso, 20-30 moderato, >30 alto
- SWEAT: >300 rischio supercelle/tornado non trascurabile
- Shear 0-6km: <20kn scarsa organizzazione, 20-35kn multicelle, >35kn
  possibile organizzazione supercellulare (ma solo se CAPE e SRH
  concorrono)

## 3. Ricerca web di contesto (obbligatoria, non opzionale)

Usa `WebSearch`/`WebFetch` per:
1. **Confermare/arricchire l'analisi sinottica** con le fonti citate nel
   documento originale dell'utente quando raggiungibili in forma testuale
   o come pagina consultabile: wetterzentrale.de, wxcharts.com,
   windy.com, ecmwf.int, pretemp.it, metoffice.gov.uk, meteocentre.com,
   meteonetwork.eu, wetter3.de, dwd.de, meteociel.fr. Se una pagina e'
   un viewer interattivo JS e non estraibile, non forzarla: usa il testo
   che riesci a leggere e cita comunque la fonte.
2. **Editoriali di esperti**: cerca aggiornamenti recenti (footer del
   bollettino, sezione "Editoriali") di: Andrea Corigliano, Pierluigi
   Randi, Luca Ciceroni, Jacopo Zannoni, Giulio Betti, Serena Giacomin,
   Filippo Thiery, Luca Mercalli, Luca Lombroso, Andrea Giuliacci,
   Francesco Nucera. Se non trovi nulla di pertinente e recente, **dillo
   esplicitamente** invece di inventare o genericizzare una citazione.
3. Eventuali modelli locali aggiuntivi (Meteoblue, WRF regionali, servizi
   meteorologici nazionali) per corroborare/contrastare il quadro
   multi-modello numerico.
4. **ICON, GFS, AROME, ARPEGE/ALADIN "a vista"**: wetterzentrale.de,
   wetter3.de e meteociel.fr sono stati testati (luglio 2026) e NON hanno
   piu' URL statici prevedibili per le cartine (sito ridisegnato/protetto
   da bot detection) — non provare pattern di URL a memoria, falliscono.
   Se ti serve una cartina di questi modelli, prova prima una WebSearch
   mirata (es. "meteociel arome France pluie" per il giorno interessato):
   se trovi un link diretto a un'immagine funzionante puoi incorporarla
   citando la fonte, altrimenti limitati al confronto numerico gia'
   ottenuto da Open-Meteo (punto 1) senza inventare di aver visto una
   cartina che non hai effettivamente recuperato.

## 4. Mappe ufficiali ECMWF (cartine reali, non generate da te)

```bash
python3 fetch_ecmwf_charts.py --lat <LAT> --lon <LON> --requests /tmp/meteo_<slug>/ecmwf_requests.json --outdir /tmp/meteo_<slug>/charts
```

Scarica cartine **reali e ufficiali** dall'OpenCharts API pubblica di
ECMWF (`charts.ecmwf.int`), licenza CC-BY-4.0 (attribuzione gia'
stampata nell'immagine: puoi incorporarle nel PDF senza problemi di
copyright). Questo e' il modo in cui rispondi alla richiesta dell'utente
di "cartine vere" per pressione/geopotenziale/CAPE/shear/umidita' in
quota, non solo grafici tuoi.

**Regola di default (dal 2026-07-26): ogni prodotto ECMWF che decidi di
usare va scaricato SEMPRE come sequenza animata (`series_start`/
`series_end`/`interval_hours`), mai come singolo `valid_time` isolato.**
Cosi' sia il PDF (che pesca un frame rappresentativo da ogni sequenza,
vedi punto 7) sia l'HTML (che mostra la sequenza intera animata) danno un
quadro completo dell'evoluzione, non un'istantanea. Scrivi tu
`ecmwf_requests.json` scegliendo con criterio editoriale quali prodotti
scaricare (non serve scaricarli tutti: sarebbero troppe immagini e tempi
lunghi). Schema e lista prodotti completa nella docstring dello script;
in sintesi, per ogni oggetto della lista specifica `product`,
`series_start`/`series_end` (ISO `YYYY-MM-DDTHH:00:00Z`, tipicamente
l'intero periodo del bollettino), `interval_hours` (6h e' un buon
compromesso tra copertura e tempo di download; usa 3h solo se il periodo
e' breve, 1-2 giorni), opzionale `level` (hPa, solo per
`medium-uv-rh`/`medium-t-z`), e `caption`. Criterio consigliato su quali
prodotti includere:
- `medium-mslp-rain` + `medium-z500-t850` per tutto il periodo — per
  l'Analisi Sinottica e il Confronto Modelli.
- `medium-cape-cin`, `medium-bulk-shear`, `medium-uv-rh` (level 700 o
  850), `medium-indices` per tutto il periodo (o almeno per la finestra
  del giorno/dei giorni a rischio convettivo) — per i Parametri Avanzati
  (e come cross-check indipendente dei tuoi calcoli MetPy: se il CAPE
  ECMWF diverge molto da quello calcolato, dillo).
- `medium-zero-level`/`medium-snowfall` solo se pertinenti al periodo.

Lo script scrive ogni sequenza in `ecmwf_manifest.json` sotto la chiave
`"sequences"` (lista di frame con `file`/`valid_time`/`label`), pronte
per `report.json`/`build_html.py`. **Tempi**: con 6+ prodotti su 3 giorni
a 6h di intervallo puoi arrivare a 60-70 richieste HTTP: lancia il
comando con un timeout generoso (l'API ECMWF va occasionalmente in
timeout su singole richieste sotto carico, normale, non serve
rilanciare tutto: lo script prosegue con gli altri frame e segnala con
`ERR` quelli falliti — se un frame manca in una sequenza l'animazione
funziona comunque con i frame restanti) o dividi in piu' chiamate per
gruppi di prodotti se rischi di superare il timeout disponibile.

La proiezione geografica e' scelta automaticamente da lat/lon (euristica
per regione europea/continentale); leggi l'output dello script — se una
richiesta fallisce (`ERR ...`) non referenziare quell'immagine nel PDF.
`valid_time` deve cadere su uno step disponibile (di norma ogni 3 ore:
00/03/06/09/12/15/18/21 UTC) — se sbagli, l'errore elenca gli orari
validi, usa quelli invece di ritentare a caso.

## 5. Grafici tuoi (dati Open-Meteo)

```bash
python3 charts.py /tmp/meteo_<slug>/data.json /tmp/meteo_<slug>/indices.json --outdir /tmp/meteo_<slug>/charts
```

Genera: `temperatura.png`, `pressione.png`, `umidita.png`, `vento.png`,
`precipitazioni.png`, `cape.png`, `geopotenziale.png`, `skewt.png` (Skew-T
reale nell'istante di CAPE massimo in finestra diurna 10-19), nella
**stessa cartella** `--outdir` usata al punto 4 per le cartine ECMWF —
cosi' `build_pdf.py` le trova tutte insieme. Leggi l'output: se un
grafico non e' stato generato (dati insufficienti, es. periodo storico
senza profilo verticale), non referenziarlo nel PDF.

Questi grafici (tuoi, da dati Open-Meteo) e le cartine ECMWF del punto 4
(ufficiali) sono complementari, non ridondanti: i primi mostrano il
confronto multi-modello nel tempo, le seconde la struttura spaziale
sinottica in un istante preciso. Usali entrambi nel PDF.

## 6. Contenuto per l'infografica

Scrivi un file `/tmp/meteo_<slug>/content.json` con il tuo giudizio
professionale su rischi e affidabilita' (i numeri di temperatura/vento/
pioggia li legge lo script direttamente da `data.json`):

```json
{
  "location_label": "Nome localita' (provincia/regione)",
  "period_label": "es. 23-26 luglio 2026",
  "reliability_pct": 82,
  "reliability_note": "una riga sintetica",
  "risks": {"Temporali": "Basso|Medio|Alto", "Grandine": "...", "Vento": "...",
            "Pioggia intensa": "...", "Caldo": "...", "Freddo": "...",
            "Nebbia": "...", "Mare": "..."}
}
```

```bash
python3 infographic.py /tmp/meteo_<slug>/data.json /tmp/meteo_<slug>/content.json --out /tmp/meteo_<slug>/charts/infografica.png
```

## 7. Scrivi l'analisi e assembla il report

Scrivi `/tmp/meteo_<slug>/report.json` (vedi lo schema completo in testa a
`scripts/build_pdf.py`). Contiene: opzionale `live_station` (solo se hai
eseguito il punto 0.5: `{"label": "...", "updated_at": "26/07 16:45 locale",
"temperature_c", "humidity_pct", "pressure_hpa", "dewpoint_c",
"wind_speed_kn", "wind_gust_kn", "wind_dir_deg", "rain_today_mm"}`,
copiati/derivati da `weathercloud.json` — questa sezione viene mostrata
per prima, prima della Sintesi, sia nel PDF sia nell'HTML), `sintesi`, `risk_table`,
`sections` (Analisi Sinottica, Confronto Modelli Numerici — con tabella
per-modello e giudizio esplicito su accordo/divergenza/scenario piu'
probabile —, Parametri Convettivi Avanzati, Convezione e Rischio Temporali
con probabilita'/intensita'/orario, Quota Neve se pertinente),
`activities_table` (Escursioni, Trekking, Ferrate, Mountain Bike,
Ciclismo, Vela, Pesca, Agricoltura, Campeggio — ognuna con rischio e
motivazione), `reliability_pct` + `reliability_text` (motiva sempre nel
dettaglio, non solo il numero), `editoriali` (esito ricerca punto 3),
`conclusione` (**massimo 15 righe**), `charts` (lista file+caption tra
quelli effettivamente generati **sia da charts.py sia da
fetch_ecmwf_charts.py** — per questi ultimi usa la `caption` che hai
scritto in `ecmwf_requests.json`, arricchita con "Fonte: ECMWF (CC BY 4.0)"),
`infographic`, e opzionale `animations` (solo se hai generato sequenze
ECMWF — vedi punto 5): copia la lista `sequences` da `ecmwf_manifest.json`
rinominando `caption`→`title` per ciascuna voce, i `frames` restano
identici. Opzionali anche `satellite` e `radar` (solo per l'HTML, punto
8): copia il contenuto dei manifest prodotti da due chiamate a
`fetch_meteoam_satellite.py` (`--product ITALIA24` per `satellite`,
`--product RADSATLAM` per `radar`) — schema
`{"product": "...", "frames": [{"file", "label"}, ...]}` per entrambi.

**Niente doppioni ECMWF tra PDF e HTML (gestito automaticamente, non
serve scrivere due `charts` diverse)**: metti pure in `charts` anche i
frame rappresentativi ECMWF come sopra descritto — servono al PDF, che
non puo' mostrare la GIF animata. `build_html.py` filtra da solo
dalla sezione "Grafici" qualunque voce di `charts` che provenga da
`fetch_ecmwf_charts.py` (riconosciuta da `file` che inizia con `ecmwf_`
o da `landing_url` su `charts.ecmwf.int`), perche' nell'HTML e' gia'
mostrata per intero nella sezione animazioni: **non toglierle tu a mano
da `charts`** ne' duplicarle, altrimenti nel PDF sparirebbero anche le
cartine statiche che invece servono li'. (Bug reale scoperto il
2026-07-27: un `report.json` scritto senza questo filtro mostrava le
stesse tre cartine ECMWF sia come animazione sia come immagine statica
subito sotto, nell'HTML — segnalato dall'utente.)

**Link alla fonte originale**: sia `ecmwf_manifest.json` (voci di `charts`
e `sequences`) sia i manifest di `fetch_meteoam_satellite.py` includono
gia' un campo `landing_url` con la pagina web ufficiale da cui il dato/
l'immagine e' stato recuperato (`charts.ecmwf.int/products/<prodotto>`
per le cartine ECMWF, `meteoam.it/it/meteosat` per il satellite,
`meteoam.it/it/i-fulmini` per radar/fulmini). Quando copi queste voci in
`report.json` (`charts`, `animations`, `satellite`, `radar`) **non
scartare questo campo**: viene reso automaticamente come link cliccabile
sull'immagine/didascalia sia nel PDF sia nell'HTML. I grafici generati da
`charts.py` (dati Open-Meteo, non una pagina web) non hanno `landing_url`
e restano senza link, correttamente.

Stile obbligatorio (vale per tutto il testo che scrivi, incluso il
riassunto in chat del punto 9 — non solo report.json):
- Mai frasi generiche ("tempo variabile", "possibili precipitazioni" senza
  altro) — motiva sempre con i dati che hai raccolto.
- Quando i modelli divergono, dillo e spiega quale scenario ritieni piu'
  probabile e perche'.
- Ogni termine tecnico va spiegato tra parentesi alla prima occorrenza.
- Usa tabelle ove possibile invece di elenchi puntati generici.
- Unita' di misura: temperatura °C, vento kn, pioggia mm, neve cm (gia'
  cosi' nei dati scaricati).
- **Ogni volta che scrivi una data** (period_label, didascalie di grafici
  e cartine, titoli di sezione, tabelle, testo dell'analisi, riassunto in
  chat) **affianca sempre il giorno della settimana abbreviato in 3
  lettere minuscole**: lun, mar, mer, gio, ven, sab, dom. Es. "ven 24/07",
  "dom 26/07 (12 UTC)", period_label "ven 24 - dom 26 luglio 2026". Vale
  anche per le date nei nomi/captions delle cartine ECMWF e nelle tabelle
  di confronto modelli (es. intestazione colonna "T.max ven 24/07 (°C)"
  invece di "T.max ven (°C)").

Aggiungi sempre anche la sezione finale **Outlook 7 Giorni**: uno sguardo
esteso, meno dettagliato, oltre il periodo principale del bollettino (usa
un solo modello, `best_match`, non il confronto multi-modello):

```bash
python3 fetch_outlook.py --lat <LAT> --lon <LON> --start <data_oggi> --days 7 --out /tmp/meteo_<slug>/outlook.json
```

Per localita' costiere (vedi punto 0.6) aggiungi `--marine`: l'array `days`
guadagna anche `wave_height_max`/`wave_period_max`/`wave_dir_dominant` e
`tide_min`/`tide_max` giornalieri (colpo d'occhio mare, stesso modello
`best_match`, non multi-modello). Se `marine_error` non e' `null` nel JSON
prodotto, ometti semplicemente la tabella mare invece di inventare valori.

Copia l'array `days` prodotto in `report.json` sotto la chiave `outlook_7d`
(vedi schema completo in `build_pdf.py`): una tabella con colonne Giorno
(usa il campo `label`, gia' con giorno della settimana abbreviato),
T.min/T.max (°C), Umidita' media (%), Pressione media (hPa), Raffica
massima (kn), Direzione vento (`wind_dir_dominant`, gradi), Pioggia totale
(mm). **Non aggiungere le colonne mare a questa stessa tabella**: su A4
verticale 8 colonne sono gia' al limite, aggiungerne altre 4 fa andare a
capo lettera per lettera le intestazioni (verificato). Per le localita'
costiere scrivi invece una **seconda tabella separata** sotto la chiave
`outlook_7d_mare` (headers: Giorno, Onda max (m), Periodo onda (s),
Direzione onda, Marea min/max (m)): viene renderizzata subito sotto la
tabella meteo, sia nel PDF sia nell'HTML, senza bisogno di testo aggiuntivo
(la nota di minore affidabilita' e' gia' scritta automaticamente).

```bash
python3 build_pdf.py /tmp/meteo_<slug>/report.json --charts-dir /tmp/meteo_<slug>/charts --logo ../assets/logo.png --out /tmp/meteo_<slug>/bollettino_<slug>.pdf
```

## 8. Report HTML con animazioni, satellite e radar/fulmini reali (di default, sempre)

Oltre al PDF genera **sempre anche la versione HTML**, piu' efficace per
mostrare l'evoluzione temporale (loop) invece di singole immagini statiche:

```bash
python3 fetch_meteoam_satellite.py --product ITALIA24 --frames 8 --outdir /tmp/meteo_<slug>/charts --prefix <slug>
python3 fetch_meteoam_satellite.py --product RADSATLAM --frames 8 --outdir /tmp/meteo_<slug>/charts --prefix <slug>_radar
python3 build_html.py /tmp/meteo_<slug>/report.json --charts-dir /tmp/meteo_<slug>/charts --logo ../assets/logo.png --out /tmp/meteo_<slug>/bollettino_<slug>.html
```

Usa lo stesso `report.json` del PDF (stesso contenuto testuale/tabelle),
con in piu' i campi opzionali `animations`, `satellite` e `radar` (vedi
punto 7). Genera anche **quante piu' sequenze animate ECMWF ha senso
mostrare** per rendere l'analisi piu' chiara: tipicamente pressione+
pioggia, geopotenziale 500/850hPa, CAPE/CIN, temperatura+vento, vento+
umidita' a un livello di quota — ognuna come "series" in
`ecmwf_requests.json` (punto 4), non solo istantanee singole.

**Tutto e' GIF animata incorporata (nessun player JS, nessuna mappa
live)**: giocano ovunque, incluse le anteprime HTML in-app di app di
messaggistica (Telegram inclusa) che disabilitano JavaScript e/o non
supportano il WebP animato — entrambi i problemi verificati
concretamente su iPhone (prima il player JS non partiva mai, poi il WebP
animato non veniva riprodotto nell'anteprima in-app) prima di arrivare
al GIF come soluzione definitiva, non e' stata una scelta preventiva.
Il file HTML e' quindi **completamente autonomo**: nessuna dipendenza da
rete/JavaScript per chi lo apre (a differenza delle versioni precedenti
di questa skill, che usavano una mappa Leaflet+RainViewer live per
radar/satellite — architettura abbandonata perche' irrisolvibile lato
codice per lo stesso motivo).

- **Satellite** (`fetch_meteoam_satellite.py --product ITALIA24`): combo
  HRV/IR, funziona di giorno e di notte — importante per la routine
  automatica che gira all'alba.
- **Radar e fulmini** (`fetch_meteoam_satellite.py --product RADSATLAM`):
  radar precipitazioni (SRI mm/h) + satellite IR + **fulmini reali della
  rete LAMPINET** dell'Aeronautica Militare, tutti sovrapposti nella
  stessa immagine ufficiale. Risolve anche il problema storico dei
  fulmini (prima non disponibili gratuitamente, vedi nota sotto): non
  serve piu' un fetcher separato per quelli.
- Entrambi: fonte CNMCA (Aeronautica Militare) / EUMETSAT, dati
  "Essential" classificati a uso libero senza restrizioni (vedi
  meteoam.it/it/licenze-uso-eumetsat). Immagini vere scaricate in fase
  di generazione (non mappe live): non si aggiornano riaprendo il file
  piu' tardi, mostrano l'ultima situazione disponibile al momento della
  generazione del bollettino.
- Se `fetch_meteoam_satellite.py` fallisce (rete non disponibile in
  quella sessione, cambio di endpoint lato meteoam.it), salta
  semplicemente il campo `satellite`/`radar` in report.json invece di
  bloccare l'intera generazione — segnalalo nel bollettino.

Copia sia il PDF sia l'HTML in una posizione comoda per l'utente (es.
Desktop o la cartella del progetto corrente); l'HTML puo' essere spostato
o inviato da solo, senza la cartella `charts/`.

## 9. In chat

Prima di allegare/generare PDF e HTML, presenta comunque in chat un
riassunto testuale ben leggibile (sintesi + tabella rischi +
affidabilita'): l'utente non deve dover aprire un file per sapere se
domani piove.

## 10. Invio su Telegram

**Manuale** (in sessione locale interattiva, su richiesta esplicita
dell'utente in conversazione):

```bash
python3 send_telegram.py --pdf bollettino_<slug>.pdf --caption "Bollettino <Citta> - <data>" --message "<sintesi breve>"
```

Token e chat id vanno chiesti all'utente (o letti da variabili
d'ambiente locali `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` se le ha gia'
configurate sul suo Mac) — mai hardcodarli nella skill.

**Automatico** (dal 2026-07-24): esiste una routine cloud schedulata
("Bollettino Meteo Imola e Punta Marina") che ogni mattina genera e
invia il bollettino per Imola e Punta Marina. Il token Telegram vero
non e' mai nel prompt della routine: passa da un relay Cloudflare
Worker che lo tiene cifrato nel suo secret store (vedi MANUTENZIONE.md
per l'architettura completa e come modificarla). La routine, essendo
un'esecuzione cloud non presidiata, usa `scripts/relay_send.py` invece
di `send_telegram.py`, e salta le sequenze animate ECMWF/l'HTML (solo
PDF, solo istanti singoli) per stare nei tempi. Se l'utente chiede di
automatizzare l'invio per una NUOVA localita' o con un secret diverso,
riproponi lo stesso pattern relay invece di ripartire dal dubbio se
sia possibile in modo riservato — lo e', vedi MANUTENZIONE.md.

## Note tecniche

- Dipendenze python gia' installate in questo ambiente: `requests`,
  `matplotlib`, `numpy`, `reportlab`, `metpy`, `Pillow`. Se in un nuovo
  ambiente mancassero: `python3 -m pip install --user requests reportlab metpy`.
- Se `fetch_forecast.py` segnala errori per singoli modelli, e' normale
  (copertura geografica/variabili non disponibili per quel modello) e non
  blocca gli altri: usa solo i modelli riusciti, e menzionalo con
  trasparenza nel bollettino invece di ignorarlo.
- Se l'utente chiede coordinate dirette (lat/lon), usa `--lat`/`--lon` al
  posto di `--location`.
- `fetch_ecmwf_charts.py` usa l'OpenCharts API pubblica di ECMWF
  (`charts.ecmwf.int/opencharts-api/v1/`), licenza CC-BY-4.0: le cartine
  scaricate hanno gia' l'attribuzione stampata nell'immagine, incorporabili
  nel PDF senza altri accorgimenti legali. E' un servizio diverso da
  Open-Meteo (punto 1): serve cartine grafiche ufficiali ECMWF, non serie
  numeriche multi-modello.
- Non esiste un equivalente pubblico/gratuito dell'OpenCharts API per
  ICON, GFS, AROME o ALADIN con URL prevedibili (cartine grafiche ufficiali):
  wetterzentrale.de, wetter3.de e meteociel.fr sono stati verificati (luglio
  2026) e non rispondono piu' con pattern statici. Non inventare URL per
  questi siti: o li trovi con una WebSearch puntuale al momento della
  richiesta, o ti affidi al confronto numerico multi-modello di Open-Meteo.
  **ALADIN come dato numerico** (non cartina) e' invece disponibile in
  `fetch_forecast.py` dal 2026-07-27 (`chmi_aladin_seamless`, CHMI Rep.
  Ceca) ed e' incluso di default nel confronto multi-modello: la
  limitazione sopra riguarda solo le mappe grafiche, non i dati numerici.
- **Radar, satellite e fulmini** in `build_html.py` NON usano piu'
  Leaflet/RainViewer (rimosso il 2026-07-26): usano immagini Meteosat
  reali scaricate da `fetch_meteoam_satellite.py` (CNMCA/Aeronautica
  Militare) e incorporate come GIF animata. Nessuna rete/JS lato utente
  per vederle, funzionano anche offline e in anteprime che bloccano
  JavaScript (es. anteprima documenti in-app di Telegram). Cambio fatto
  dopo che l'utente ha verificato, in sequenza, che ne' un player JS ne'
  il WebP animato (entrambi provati prima) funzionavano nell'anteprima
  HTML di Telegram su iPhone: il GIF e' risultato il formato piu'
  universalmente compatibile, usato anche per le animazioni ECMWF del
  punto 5/8. **Se in futuro emerge un problema simile su un'altra app di
  messaggistica, il fix e' sempre lo stesso pattern**: dati reali
  precotti in un formato immagine nativo (GIF), mai un player JS o un
  formato immagine di nicchia, per un file destinato ad app che
  potrebbero disabilitare JavaScript o non supportare formati recenti.
- **Fulmini**: risolti gratuitamente tramite RADSATLAM (rete LAMPINET
  dell'Aeronautica Militare, inclusa nell'immagine radar/satellite
  ufficiale) — non serve piu' cercare un provider a pagamento come
  ipotizzato in passato (Blitzortung/lightningmaps.org restano scartati,
  non serve riconsiderarli).
- `send_telegram.py` (uso manuale locale) non contiene mai credenziali:
  legge `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` da env o da
  `--token`/`--chat-id`. Per l'uso automatico via routine cloud vedi
  `relay_send.py` e punto 10 — architettura completa in MANUTENZIONE.md.
