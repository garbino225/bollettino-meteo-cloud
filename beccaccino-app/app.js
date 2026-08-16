'use strict';

/* ---------------------------------------------------------------------- *
 *  Modello del mazzo romagnolo (40 carte, 4 semi)
 * ---------------------------------------------------------------------- */

const SUITS = [
  { id: 'denari', name: 'Denari', color: '#c9941f', icon: iconDenari() },
  { id: 'coppe', name: 'Coppe', color: '#b23b3b', icon: iconCoppe() },
  { id: 'bastoni', name: 'Bastoni', color: '#3f6b3f', icon: iconBastoni() },
  { id: 'spade', name: 'Spade', color: '#2b3a4a', icon: iconSpade() },
];

// Ordine di forza dal più debole al più forte (uguale in ogni seme).
const RANK_ORDER = ['4', '5', '6', '7', 'fante', 'cavallo', 're', 'asso', '2', '3'];
const RANK_LABEL = { '4': '4', '5': '5', '6': '6', '7': '7', fante: 'F', cavallo: 'C', re: 'R', asso: 'A', '2': '2', '3': '3' };

function rankStrength(rank) {
  return RANK_ORDER.indexOf(rank);
}

// Valore in punti espresso in "terzi" per evitare arrotondamenti con i decimali.
// Asso = 1 punto (3 terzi). 3, 2, Re, Cavallo, Fante = 1/3 di punto (1 terzo). Il resto = 0.
function cardPointThirds(rank) {
  if (rank === 'asso') return 3;
  if (['3', '2', 're', 'cavallo', 'fante'].includes(rank)) return 1;
  return 0;
}

function buildDeck() {
  const deck = [];
  for (const suit of SUITS) {
    for (const rank of RANK_ORDER) {
      deck.push({
        id: `${suit.id}-${rank}`,
        suit: suit.id,
        rank,
        strength: rankStrength(rank),
        pointThirds: cardPointThirds(rank),
      });
    }
  }
  return deck;
}

function shuffle(arr) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function suitInfo(id) {
  return SUITS.find((s) => s.id === id);
}

// Determina l'indice (0..3) della carta vincente in una presa.
// playedCards: array di 4 carte nell'ordine in cui sono state giocate.
function trickWinner(playedCards, ledSuit, trumpSuit) {
  const trumps = playedCards
    .map((c, i) => ({ c, i }))
    .filter((x) => x.c.suit === trumpSuit);
  if (trumps.length > 0) {
    return trumps.reduce((best, x) => (x.c.strength > best.c.strength ? x : best)).i;
  }
  const ledCards = playedCards
    .map((c, i) => ({ c, i }))
    .filter((x) => x.c.suit === ledSuit);
  return ledCards.reduce((best, x) => (x.c.strength > best.c.strength ? x : best)).i;
}

function thirdsToLabel(thirds) {
  const whole = Math.floor(thirds / 3);
  const rest = thirds % 3;
  if (rest === 0) return `${whole}`;
  return `${whole} e ${rest}/3`;
}

function cardText(card) {
  return `${RANK_LABEL[card.rank]} di ${suitInfo(card.suit).name.toLowerCase()}`;
}

/* Piccole icone SVG inline per i quattro semi romagnoli */
function iconDenari() {
  return '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" stroke-width="1.6"/></svg>';
}
function iconCoppe() {
  return '<svg viewBox="0 0 24 24"><path d="M5 4h14l-1.4 8.2A5.6 5.6 0 0 1 12 17a5.6 5.6 0 0 1-5.6-4.8L5 4z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M12 17v3M8 20h8" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
}
function iconBastoni() {
  return '<svg viewBox="0 0 24 24"><path d="M6 19L18 5" fill="none" stroke="currentColor" stroke-width="3.4" stroke-linecap="round"/><circle cx="6" cy="19" r="2.4" fill="currentColor"/><circle cx="18" cy="5" r="2.4" fill="currentColor"/></svg>';
}
function iconSpade() {
  return '<svg viewBox="0 0 24 24"><path d="M12 2l3 3-3 12-3-12 3-3z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/><path d="M7 12h10M12 17v5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
}

/* ---------------------------------------------------------------------- *
 *  Navigazione fra le sezioni
 * ---------------------------------------------------------------------- */

const views = document.querySelectorAll('.view');
const navButtons = document.querySelectorAll('[data-nav]');

function showView(name) {
  views.forEach((v) => v.classList.toggle('active', v.id === `view-${name}`));
  navButtons.forEach((b) => b.classList.toggle('active', b.dataset.nav === name));
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

navButtons.forEach((btn) => btn.addEventListener('click', () => showView(btn.dataset.nav)));
document.querySelectorAll('[data-go]').forEach((btn) =>
  btn.addEventListener('click', () => showView(btn.dataset.go))
);

/* ---------------------------------------------------------------------- *
 *  Sezione "Regole": tabella di riferimento gerarchia carte
 * ---------------------------------------------------------------------- */

function renderRankLadder() {
  const el = document.getElementById('rank-ladder');
  if (!el) return;
  const ordered = RANK_ORDER.slice().reverse(); // dal più forte al più debole
  el.innerHTML = ordered
    .map((rank, i) => {
      const pts = cardPointThirds(rank);
      const ptsLabel = pts === 0 ? '—' : pts === 3 ? '1 punto' : '1/3 di punto';
      return `<div class="ladder-row">
        <span class="ladder-pos">${i + 1}ª</span>
        <span class="ladder-rank">${RANK_LABEL[rank]}</span>
        <span class="ladder-name">${rankFullName(rank)}</span>
        <span class="ladder-pts">${ptsLabel}</span>
      </div>`;
    })
    .join('');
}

function rankFullName(rank) {
  const names = { '4': 'Quattro', '5': 'Cinque', '6': 'Sei', '7': 'Sette', fante: 'Fante', cavallo: 'Cavallo', re: 'Re', asso: 'Asso', '2': 'Due', '3': 'Tre' };
  return names[rank];
}

function renderSuitLegend() {
  const el = document.getElementById('suit-legend');
  if (!el) return;
  el.innerHTML = SUITS.map(
    (s) => `<div class="suit-chip" style="--suit-color:${s.color}"><span class="suit-icon">${s.icon}</span>${s.name}</div>`
  ).join('');
}

/* ---------------------------------------------------------------------- *
 *  Sezione Quiz
 * ---------------------------------------------------------------------- */

const QUIZ_QUESTIONS = [
  {
    q: 'Quante carte compongono il mazzo del Beccaccino?',
    options: ['32', '40', '52', '36'],
    correct: 1,
    explain: 'Si usa il mazzo romagnolo/italiano da 40 carte (niente 8, 9, 10).',
  },
  {
    q: 'In ogni seme, qual è la carta più forte?',
    options: ['Il Re', 'L\'Asso', 'Il 3', 'Il 7'],
    correct: 2,
    explain: 'La gerarchia è: 3, 2, Asso, Re, Cavallo, Fante, 7, 6, 5, 4. Il 3 è il più forte.',
  },
  {
    q: 'Chi sceglie il seme di briscola e gioca la prima carta?',
    options: ['Il mazziere', 'Chi ha il 4 di denari', 'Chi ha l\'asso di spade', 'Si tira a sorte'],
    correct: 1,
    explain: 'Il giocatore che riceve il 4 di denari "battezza" la briscola e apre la prima presa.',
  },
  {
    q: 'Quanto vale un Asso in punti?',
    options: ['1/3 di punto', '1 punto', '2 punti', '0 punti'],
    correct: 1,
    explain: 'Gli assi valgono 1 punto pieno ciascuno.',
  },
  {
    q: 'Quanto valgono il 3, il 2, il Re, il Cavallo e il Fante?',
    options: ['0 punti', '1 punto', '1/3 di punto ciascuna', '1/2 punto ciascuna'],
    correct: 2,
    explain: 'Sono gli "onori": ciascuna vale 1/3 di punto.',
  },
  {
    q: 'Le carte dal 4 al 7 (le "scartine") quanto valgono?',
    options: ['0 punti', '1/3 di punto', '1 punto', 'Dipende dal seme'],
    correct: 0,
    explain: 'Le scartine (o "lisce") non valgono nulla in punti, servono solo per giocare o per rispondere al seme.',
  },
  {
    q: 'Se non hai carte del seme chiamato, cosa puoi giocare?',
    options: [
      'Solo carte di briscola',
      'Devi passare il turno',
      'Qualunque carta, anche la briscola',
      'Solo scartine',
    ],
    correct: 2,
    explain: 'Se sei "in fallo" di quel seme puoi giocare liberamente qualsiasi carta, briscola compresa.',
  },
  {
    q: 'Chi vince una presa in cui è stata giocata almeno una briscola?',
    options: [
      'La carta più alta del seme chiamato',
      'La briscola più alta giocata',
      'Chi ha aperto la presa',
      'La prima briscola giocata, sempre',
    ],
    correct: 1,
    explain: 'Se qualcuno gioca briscola, vince la briscola più forte comparsa nella presa.',
  },
  {
    q: 'Cosa significa il segnale "busso" (o il pugno battuto sul tavolo)?',
    options: [
      'Non ho più carte di questo seme',
      'Ho ancora carte di questo seme ma deboli',
      'Ho ancora carte forti di questo seme: torna a giocarlo',
      'Sto per fare la marafona',
    ],
    correct: 2,
    explain: 'Il "busso" invita il compagno a tornare su quel seme perché hai carte forti lì.',
  },
  {
    q: 'Cosa significa "volo" (alzare la mano)?',
    options: [
      'Ho ancora carte di quel seme',
      'Non ho più carte di quel seme',
      'Ho la marafona',
      'Voglio cambiare la briscola',
    ],
    correct: 1,
    explain: '"Volo" segnala al compagno che sei in fallo (non hai più carte) di quel seme.',
  },
  {
    q: 'Cos\'è la "marafona" (o cricca)?',
    options: [
      'Avere tre assi in mano',
      'Avere Asso, 2 e 3 dello stesso seme di briscola',
      'Vincere tutte le prese',
      'Avere quattro figure di seguito',
    ],
    correct: 1,
    explain: 'Chi ha Asso+2+3 di briscola può dichiarare la marafona: +3 punti bonus per la propria squadra.',
  },
  {
    q: 'A quanti punti si vince tradizionalmente una partita (variante lunga)?',
    options: ['21', '31', '41', '61'],
    correct: 2,
    explain: 'La partita si gioca fino a 41 punti (31 nella variante "corta").',
  },
];

let quizIndex = 0;
let quizScore = 0;
let quizOrder = [];

function startQuiz() {
  quizIndex = 0;
  quizScore = 0;
  quizOrder = shuffle(QUIZ_QUESTIONS.map((_, i) => i));
  document.getElementById('quiz-result').classList.add('hidden');
  document.getElementById('quiz-question-wrap').classList.remove('hidden');
  renderQuizQuestion();
}

function renderQuizQuestion() {
  const wrap = document.getElementById('quiz-question-wrap');
  if (quizIndex >= quizOrder.length) {
    finishQuiz();
    return;
  }
  const item = QUIZ_QUESTIONS[quizOrder[quizIndex]];
  document.getElementById('quiz-progress').textContent = `Domanda ${quizIndex + 1} di ${quizOrder.length} — Punteggio: ${quizScore}`;
  document.getElementById('quiz-question').textContent = item.q;
  const optsEl = document.getElementById('quiz-options');
  optsEl.innerHTML = '';
  document.getElementById('quiz-feedback').textContent = '';
  document.getElementById('quiz-feedback').className = 'quiz-feedback';
  document.getElementById('quiz-next').classList.add('hidden');

  item.options.forEach((opt, i) => {
    const b = document.createElement('button');
    b.className = 'quiz-option';
    b.textContent = opt;
    b.addEventListener('click', () => answerQuiz(i, item));
    optsEl.appendChild(b);
  });
}

function answerQuiz(choice, item) {
  const optsEl = document.getElementById('quiz-options');
  [...optsEl.children].forEach((b, i) => {
    b.disabled = true;
    if (i === item.correct) b.classList.add('correct');
    else if (i === choice) b.classList.add('wrong');
  });
  const fb = document.getElementById('quiz-feedback');
  if (choice === item.correct) {
    quizScore++;
    fb.textContent = `✅ Esatto! ${item.explain}`;
    fb.classList.add('ok');
  } else {
    fb.textContent = `❌ Non proprio. ${item.explain}`;
    fb.classList.add('ko');
  }
  document.getElementById('quiz-next').classList.remove('hidden');
}

function finishQuiz() {
  document.getElementById('quiz-question-wrap').classList.add('hidden');
  const resEl = document.getElementById('quiz-result');
  resEl.classList.remove('hidden');
  const pct = Math.round((quizScore / quizOrder.length) * 100);
  let verdict = 'Continua a esercitarti: le regole del Beccaccino richiedono un po\' di pratica al tavolo!';
  if (pct >= 90) verdict = 'Ottimo! Conosci le regole meglio di molti giocatori esperti. 🏆';
  else if (pct >= 70) verdict = 'Molto bene! Sei quasi pronto per sederti al tavolo.';
  else if (pct >= 50) verdict = 'Buona base, ripassa i segnali e il punteggio delle carte.';
  resEl.innerHTML = `<h3>Hai totalizzato ${quizScore} / ${quizOrder.length} (${pct}%)</h3><p>${verdict}</p>
    <button class="btn primary" id="quiz-retry">Rifai il quiz</button>`;
  document.getElementById('quiz-retry').addEventListener('click', startQuiz);
}

document.getElementById('quiz-next')?.addEventListener('click', () => {
  quizIndex++;
  renderQuizQuestion();
});
document.getElementById('quiz-start')?.addEventListener('click', startQuiz);

/* ---------------------------------------------------------------------- *
 *  Sezione "Allenati": chi vince la presa?
 * ---------------------------------------------------------------------- */

const POSITIONS = ['Sud', 'Ovest', 'Nord', 'Est'];
let trainerRound = null;
let trainerScore = { right: 0, total: 0 };

function newTrainerRound() {
  const trumpSuit = SUITS[Math.floor(Math.random() * SUITS.length)].id;
  const ledSuit = SUITS[Math.floor(Math.random() * SUITS.length)].id;

  const used = new Set();
  function randomCardOfSuit(suit) {
    let card;
    do {
      const rank = RANK_ORDER[Math.floor(Math.random() * RANK_ORDER.length)];
      card = { suit, rank, strength: rankStrength(rank), pointThirds: cardPointThirds(rank) };
    } while (used.has(`${card.suit}-${card.rank}`));
    used.add(`${card.suit}-${card.rank}`);
    return card;
  }

  const played = POSITIONS.map((_, i) => {
    if (i === 0) return randomCardOfSuit(ledSuit); // chi apre gioca il seme chiamato
    const roll = Math.random();
    if (roll < 0.55) return randomCardOfSuit(ledSuit); // segue il seme
    if (roll < 0.8 && trumpSuit !== ledSuit) return randomCardOfSuit(trumpSuit); // taglia con briscola
    // scarto: un seme qualunque diverso da quello chiamato
    const otherSuits = SUITS.map((s) => s.id).filter((s) => s !== ledSuit);
    return randomCardOfSuit(otherSuits[Math.floor(Math.random() * otherSuits.length)]);
  });

  trainerRound = { trumpSuit, ledSuit, played, winnerIdx: trickWinner(played, ledSuit, trumpSuit) };
  renderTrainerRound();
}

function renderTrainerRound() {
  const r = trainerRound;
  document.getElementById('trainer-trump').innerHTML = `Briscola: <span class="suit-chip" style="--suit-color:${suitInfo(r.trumpSuit).color}"><span class="suit-icon">${suitInfo(r.trumpSuit).icon}</span>${suitInfo(r.trumpSuit).name}</span>`;
  document.getElementById('trainer-led').innerHTML = `Seme chiamato: <span class="suit-chip" style="--suit-color:${suitInfo(r.ledSuit).color}"><span class="suit-icon">${suitInfo(r.ledSuit).icon}</span>${suitInfo(r.ledSuit).name}</span>`;

  const table = document.getElementById('trainer-table');
  table.innerHTML = '';
  r.played.forEach((card, i) => {
    const s = suitInfo(card.suit);
    const div = document.createElement('button');
    div.className = 'trick-card-btn';
    div.innerHTML = `<span class="pos-label">${POSITIONS[i]}${i === 0 ? ' (apre)' : ''}</span>
      <span class="play-card" style="--suit-color:${s.color}">
        <span class="pc-rank">${RANK_LABEL[card.rank]}</span>
        <span class="pc-suit">${s.icon}</span>
      </span>`;
    div.addEventListener('click', () => answerTrainer(i));
    table.appendChild(div);
  });
  document.getElementById('trainer-feedback').textContent = '';
  document.getElementById('trainer-feedback').className = 'quiz-feedback';
  document.getElementById('trainer-next').classList.add('hidden');
  document.getElementById('trainer-score').textContent = `Indovinate: ${trainerScore.right} / ${trainerScore.total}`;
}

function answerTrainer(choiceIdx) {
  const r = trainerRound;
  trainerScore.total++;
  const buttons = document.querySelectorAll('.trick-card-btn');
  buttons.forEach((b, i) => {
    b.disabled = true;
    if (i === r.winnerIdx) b.classList.add('correct');
    else if (i === choiceIdx) b.classList.add('wrong');
  });
  const winnerCard = r.played[r.winnerIdx];
  const usedTrump = r.played.some((c) => c.suit === r.trumpSuit);
  const reason = usedTrump
    ? `perché è la briscola (${suitInfo(r.trumpSuit).name}) più alta della presa.`
    : `perché è la carta più alta del seme chiamato (${suitInfo(r.ledSuit).name}), non essendo uscita briscola.`;
  const fb = document.getElementById('trainer-feedback');
  if (choiceIdx === r.winnerIdx) {
    trainerScore.right++;
    fb.textContent = `✅ Esatto! Vince ${POSITIONS[r.winnerIdx]} con ${cardText(winnerCard)}, ${reason}`;
    fb.classList.add('ok');
  } else {
    fb.textContent = `❌ Vince invece ${POSITIONS[r.winnerIdx]} con ${cardText(winnerCard)}, ${reason}`;
    fb.classList.add('ko');
  }
  document.getElementById('trainer-score').textContent = `Indovinate: ${trainerScore.right} / ${trainerScore.total}`;
  document.getElementById('trainer-next').classList.remove('hidden');
}

document.getElementById('trainer-next')?.addEventListener('click', newTrainerRound);
document.getElementById('trainer-start')?.addEventListener('click', () => {
  trainerScore = { right: 0, total: 0 };
  newTrainerRound();
});

/* ---------------------------------------------------------------------- *
 *  Sezione "Gioca": mini-partita simulata contro 3 avversari
 *
 *  Semplificazione didattica dichiarata: per far scegliere sempre a te la
 *  briscola (come da regola, tocca a chi ha il 4 di denari), il 4 di denari
 *  viene garantito nella mano di Sud (tu). Squadre: Sud+Nord vs Ovest+Est.
 * ---------------------------------------------------------------------- */

const GAME_POS = ['Sud', 'Ovest', 'Nord', 'Est']; // ordine di gioco antiorario, Sud = umano
const TEAM_OF = { Sud: 'A', Nord: 'A', Ovest: 'B', Est: 'B' };

let game = null;

function dealGame() {
  let deck = shuffle(buildDeck());
  // garantisce il 4 di denari a Sud (indice 0) per la scelta della briscola
  const idx4Denari = deck.findIndex((c) => c.suit === 'denari' && c.rank === '4');
  const [card4] = deck.splice(idx4Denari, 1);
  const hands = { Sud: [card4], Ovest: [], Nord: [], Est: [] };
  let p = 1;
  while (deck.length) {
    const pos = GAME_POS[p % 4];
    hands[pos].push(deck.pop());
    p++;
  }
  GAME_POS.forEach((pos) => hands[pos].sort((a, b) => suitOrderIdx(a.suit) - suitOrderIdx(b.suit) || a.strength - b.strength));

  game = {
    hands,
    trumpSuit: null,
    leader: 'Sud',
    trickNum: 1,
    current: [], // {pos, card}
    ledSuit: null,
    points: { A: 0, B: 0 },
    marafona: null,
    log: [],
    finished: false,
  };
  document.getElementById('game-hand-wrap').classList.remove('hidden');
  renderHandPreview();
  showTrumpPicker();
}

function suitOrderIdx(id) {
  return SUITS.findIndex((s) => s.id === id);
}

// Mostra le carte in mano (senza poterle giocare) mentre si sceglie la briscola.
function renderHandPreview() {
  const handEl = document.getElementById('game-hand');
  handEl.innerHTML = '';
  game.hands.Sud.forEach((card) => {
    const s = suitInfo(card.suit);
    const div = document.createElement('div');
    div.className = 'hand-card';
    div.style.setProperty('--suit-color', s.color);
    div.innerHTML = `<span class="pc-rank">${RANK_LABEL[card.rank]}</span><span class="pc-suit">${s.icon}</span>`;
    handEl.appendChild(div);
  });
}

function showTrumpPicker() {
  const el = document.getElementById('game-trump-picker');
  el.classList.remove('hidden');
  document.getElementById('game-table-wrap').classList.add('hidden');
  el.innerHTML = `<p>Hai visto le tue carte e hai il <strong>4 di denari</strong>: tocca a te scegliere la briscola!</p><div class="trump-choices">${SUITS.map(
    (s) => `<button class="btn suit-btn" data-suit="${s.id}" style="--suit-color:${s.color}"><span class="suit-icon">${s.icon}</span>${s.name}</button>`
  ).join('')}</div>`;
  el.querySelectorAll('[data-suit]').forEach((b) =>
    b.addEventListener('click', () => chooseTrump(b.dataset.suit))
  );
}

function chooseTrump(suit) {
  game.trumpSuit = suit;
  detectMarafona();
  document.getElementById('game-trump-picker').classList.add('hidden');
  document.getElementById('game-table-wrap').classList.remove('hidden');
  renderGame();
  playTurnIfAI();
}

function detectMarafona() {
  for (const pos of GAME_POS) {
    const hand = game.hands[pos];
    const has = ['asso', '2', '3'].every((r) => hand.some((c) => c.suit === game.trumpSuit && c.rank === r));
    if (has) {
      game.marafona = pos;
      game.points[TEAM_OF[pos]] += 9; // +3 punti = 9 terzi
      game.log.unshift(`🎉 ${pos} ha la Marafona (Asso, 2, 3 di ${suitInfo(game.trumpSuit).name})! +3 punti alla squadra ${TEAM_OF[pos]}.`);
      return;
    }
  }
}

function legalCardsFor(pos) {
  const hand = game.hands[pos];
  if (!game.ledSuit) return hand;
  const followers = hand.filter((c) => c.suit === game.ledSuit);
  return followers.length ? followers : hand;
}

function playCard(pos, card) {
  const hand = game.hands[pos];
  hand.splice(hand.indexOf(card), 1);
  if (game.current.length === 0) game.ledSuit = card.suit;
  game.current.push({ pos, card });
}

function isHumanTurn() {
  const nextIdx = game.current.length;
  const order = turnOrder();
  return order[nextIdx] === 'Sud';
}

function turnOrder() {
  const startIdx = GAME_POS.indexOf(game.leader);
  return [0, 1, 2, 3].map((i) => GAME_POS[(startIdx + i) % 4]);
}

function playTurnIfAI() {
  if (game.finished) return;
  const order = turnOrder();
  const nextIdx = game.current.length;
  if (nextIdx >= 4) {
    resolveTrick();
    return;
  }
  const pos = order[nextIdx];
  if (pos === 'Sud') {
    renderGame();
    return;
  }
  setTimeout(() => {
    const card = aiChooseCard(pos);
    playCard(pos, card);
    renderGame();
    playTurnIfAI();
  }, 550);
}

function aiChooseCard(pos) {
  const legal = legalCardsFor(pos);
  // Se sta seguendo il seme chiamato: prova a vincere "al risparmio", altrimenti scarta la più bassa.
  const currentBest = currentTrickBest();
  const winningOptions = legal.filter((c) => wouldWin(c, pos));
  if (winningOptions.length) {
    // gioca la più bassa fra quelle che vincono comunque (risparmia le carte forti)
    return winningOptions.reduce((a, b) => (a.strength < b.strength ? a : b));
  }
  // non può/non conviene vincere: scarta la carta di minor valore
  return legal.reduce((a, b) => (cardWeight(a) < cardWeight(b) ? a : b));
}

function cardWeight(c) {
  return c.pointThirds * 10 + c.strength; // preferisce scartare carte senza punti e deboli
}

function currentTrickBest() {
  if (!game.current.length) return null;
  const cards = game.current.map((x) => x.card);
  const idx = trickWinner(cards, game.ledSuit, game.trumpSuit);
  return game.current[idx];
}

function wouldWin(card, pos) {
  const hypothetical = [...game.current.map((x) => x.card), card];
  const ledSuit = game.ledSuit || card.suit;
  const idx = trickWinner(hypothetical, ledSuit, game.trumpSuit);
  return idx === hypothetical.length - 1;
}

function resolveTrick() {
  const cards = game.current.map((x) => x.card);
  const winIdx = trickWinner(cards, game.ledSuit, game.trumpSuit);
  const winner = game.current[winIdx].pos;
  const team = TEAM_OF[winner];
  const thirds = cards.reduce((s, c) => s + c.pointThirds, 0) + (game.trickNum === 10 ? 1 : 0);
  game.points[team] += thirds;
  game.log.unshift(
    `Presa ${game.trickNum}: vince ${winner} (${cardText(game.current[winIdx].card)}) — ${thirdsToLabel(thirds)} punti alla squadra ${team}.`
  );

  game.leader = winner;
  game.current = [];
  game.ledSuit = null;

  if (game.trickNum === 10) {
    game.finished = true;
    renderGame();
    return;
  }
  game.trickNum++;
  renderGame();
  playTurnIfAI();
}

function renderGame() {
  const wrap = document.getElementById('game-table-wrap');
  const trumpS = suitInfo(game.trumpSuit);
  document.getElementById('game-status').innerHTML = `Presa ${Math.min(game.trickNum, 10)} di 10 — Briscola: <span class="suit-chip" style="--suit-color:${trumpS.color}"><span class="suit-icon">${trumpS.icon}</span>${trumpS.name}</span>`;
  document.getElementById('game-score').textContent = `Squadra A (Sud-Nord): ${thirdsToLabel(game.points.A)} · Squadra B (Ovest-Est): ${thirdsToLabel(game.points.B)}`;

  const table = document.getElementById('game-table');
  table.innerHTML = '';
  ['Nord', 'Ovest', 'Est', 'Sud'].forEach((pos) => {
    const played = game.current.find((x) => x.pos === pos);
    const div = document.createElement('div');
    div.className = `table-slot slot-${pos.toLowerCase()}`;
    if (played) {
      const s = suitInfo(played.card.suit);
      div.innerHTML = `<span class="pos-label">${pos}</span><span class="play-card" style="--suit-color:${s.color}"><span class="pc-rank">${RANK_LABEL[played.card.rank]}</span><span class="pc-suit">${s.icon}</span></span>`;
    } else {
      div.innerHTML = `<span class="pos-label">${pos}</span><span class="play-card empty">·</span>`;
    }
    table.appendChild(div);
  });

  const handEl = document.getElementById('game-hand');
  handEl.innerHTML = '';
  const legal = isHumanTurn() && !game.finished ? legalCardsFor('Sud') : [];
  game.hands.Sud.forEach((card) => {
    const s = suitInfo(card.suit);
    const btn = document.createElement('button');
    const playable = legal.includes(card);
    btn.className = `hand-card${playable ? '' : ' disabled'}`;
    btn.style.setProperty('--suit-color', s.color);
    btn.innerHTML = `<span class="pc-rank">${RANK_LABEL[card.rank]}</span><span class="pc-suit">${s.icon}</span>`;
    btn.disabled = !playable;
    btn.addEventListener('click', () => {
      playCard('Sud', card);
      renderGame();
      playTurnIfAI();
    });
    handEl.appendChild(btn);
  });

  document.getElementById('game-log').innerHTML = game.log.slice(0, 6).map((l) => `<div>${l}</div>`).join('');

  const endEl = document.getElementById('game-end');
  if (game.finished) {
    endEl.classList.remove('hidden');
    const winTeam = game.points.A > game.points.B ? 'A (Sud-Nord)' : game.points.B > game.points.A ? 'B (Ovest-Est)' : null;
    endEl.innerHTML = `<h3>Mano conclusa!</h3>
      <p>Squadra A (Sud-Nord): <strong>${thirdsToLabel(game.points.A)}</strong> punti<br>
      Squadra B (Ovest-Est): <strong>${thirdsToLabel(game.points.B)}</strong> punti</p>
      <p>${winTeam ? `Questa mano la vince la squadra <strong>${winTeam}</strong>! Nella partita reale si continua a fare mani fino a 41 punti.` : 'Mano in perfetta parità!'}</p>
      <button class="btn primary" id="game-again">Gioca un\'altra mano</button>`;
    document.getElementById('game-again').addEventListener('click', dealGame);
  } else {
    endEl.classList.add('hidden');
  }
}

document.getElementById('game-start')?.addEventListener('click', dealGame);

/* ---------------------------------------------------------------------- *
 *  Init
 * ---------------------------------------------------------------------- */

renderRankLadder();
renderSuitLegend();
showView('home');
