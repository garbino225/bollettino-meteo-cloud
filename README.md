# bollettino-meteo (versione cloud)

Copia della skill personale `bollettino-meteo`, adattata per girare in una
routine cloud schedulata (claude.ai/code/routines) invece che in sessione
interattiva locale.

Istruzioni complete in `SKILL.md` (identiche alla skill originale). Unica
differenza: l'invio finale non usa `send_telegram.py` (che richiede il
token Telegram in chiaro come variabile d'ambiente locale), ma
`scripts/relay_send.py`, che passa il PDF a un Cloudflare Worker che
tiene il vero token Telegram cifrato nel suo secret store. Questo script
vede solo un `RELAY_SECRET` (chiave anti-abuso, non il token Telegram).

## Dipendenze

```bash
pip install -r requirements.txt
```

## Invio del bollettino

```bash
python3 scripts/relay_send.py --url $RELAY_URL --secret $RELAY_SECRET \
    --pdf /tmp/bollettino.pdf --caption "Bollettino <Localita> - <data>"
```

`RELAY_URL` e `RELAY_SECRET` sono passati come parte del prompt della
routine cloud (non sono segreti sensibili: il primo è pubblico per
definizione, il secondo protegge solo da spam sul Worker, non dal furto
del bot Telegram).

## Dati in tempo reale sul sito (widget Ecowitt)

Oltre al bollettino periodico, il repo include un widget da incorporare
sul proprio sito per mostrare i dati live delle centraline Ecowitt
(temperatura, vento, pioggia, pressione, ecc.), letti dall'API cloud
`ecowitt.net`.

Stesso principio del relay Telegram: le chiavi Ecowitt (`application_key` /
`api_key`) non finiscono mai nel browser. Un Cloudflare Worker
(`worker/ecowitt-relay`) le tiene nel proprio secret store, interroga
`api.ecowitt.net` lato server e restituisce solo il JSON con i dati (in
cache qualche decina di secondi, per non consumare la quota API a ogni
visita del sito). Il widget statico (`widget/ecowitt-widget.js`) chiama
solo questo Worker.

### 1. Deploy del Worker

```bash
cd worker/ecowitt-relay
npx wrangler deploy
npx wrangler secret put ECOWITT_APPLICATION_KEY
npx wrangler secret put ECOWITT_API_KEY
```

Le due chiavi si generano su `ecowitt.net` → *Account* → *API*. In
`wrangler.toml` configura:

- `STATIONS`: mappa `{"nome-a-scelta": "MAC-del-gateway"}` (il MAC si
  trova su ecowitt.net in *My Devices*; per dispositivi cellulari senza
  gateway WiFi usa `"imei:<numero>"` al posto del MAC).
- `ALLOWED_ORIGINS`: `"*"` oppure il dominio del tuo sito, per limitare da
  dove il widget può essere incorporato.
- `CACHE_TTL_SECONDS`: quanto (in secondi) tenere in cache la risposta
  prima di richiamare di nuovo `ecowitt.net` (default 60).

### 2. Incorporazione sul sito

```html
<link rel="stylesheet" href="ecowitt-widget.css">
<div
  data-ecowitt-widget
  data-endpoint="https://ecowitt-relay.<account>.workers.dev/realtime"
  data-station="nome-a-scelta"
  data-refresh="60"
  data-title="Meteo Casa"
></div>
<script src="ecowitt-widget.js"></script>
```

Copia `widget/ecowitt-widget.js` e `widget/ecowitt-widget.css` sul tuo
sito (o serviteli direttamente dal Worker/da un altro hosting statico).
`widget/demo.html` è una pagina di esempio pronta all'uso.

**Nota sulle unità di misura**: il Worker inoltra i valori esattamente
come li restituisce `ecowitt.net`, incluso il campo unità che l'API
allega a ogni misura, senza conversioni locali. Le unità preferite
(°C/°F, hPa/inHg, km/h/mph, ecc.) si impostano nel proprio account
ecowitt.net.
