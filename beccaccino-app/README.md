# Impara il Beccaccino

Web app statica (HTML/CSS/JS puro, nessuna dipendenza) per imparare a giocare
a **Beccaccino** — il gioco di carte tradizionale romagnolo noto anche come
Marafone, Maraffone o Trionfo a seconda della zona.

## Contenuti

- **Regole**: tutorial completo (mazzo, gerarchia delle carte, punteggio,
  briscola, segnali busso/striscio/volo, marafona, punteggio partita).
- **Quiz**: 12 domande a risposta multipla per verificare quanto imparato.
- **Allenati**: esercizio "chi vince la presa?" per allenare la lettura
  veloce del tavolo.
- **Gioca**: mini-partita simulata (una mano da 10 prese) contro 3
  avversari automatici, per esercitarsi a giocare rispettando l'obbligo
  di rispondere al seme e la gerarchia delle carte.

## Come usarla

Nessuna build necessaria: basta aprire `index.html` in un browser, oppure
servire la cartella con un qualsiasi server statico, ad esempio:

```bash
python3 -m http.server 8000 -d beccaccino-app
```

e poi visitare `http://localhost:8000`.

## Nota didattica

Nella modalità "Gioca", per permettere di scegliere sempre la briscola
(come da regola, spetta a chi riceve il 4 di denari), il 4 di denari viene
sempre assegnato al giocatore umano (Sud). È una semplificazione pensata
per l'allenamento, non altera le altre regole del gioco.
