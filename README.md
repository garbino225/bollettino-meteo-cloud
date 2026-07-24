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
