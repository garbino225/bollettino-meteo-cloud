/**
 * Widget vanilla-JS per mostrare i dati in tempo reale di una centralina
 * Ecowitt, letti dal relay Cloudflare Worker (worker/ecowitt-relay). Nessuna
 * chiave Ecowitt e' mai presente qui: il widget parla solo con il Worker.
 *
 * Uso automatico (nessun JS da scrivere):
 *   <link rel="stylesheet" href="ecowitt-widget.css">
 *   <div data-ecowitt-widget
 *        data-endpoint="https://tuo-worker.workers.dev/realtime"
 *        data-station="casa"
 *        data-refresh="60"
 *        data-title="Meteo Casa"></div>
 *   <script src="ecowitt-widget.js"></script>
 *
 * Uso manuale: EcowittWidget.mount(document.querySelector('#el'))
 *
 * I valori (value/unit) mostrati sono esattamente quelli restituiti da
 * Ecowitt: il widget non converte ne' rietichetta unita' di misura, per
 * evitare di mostrare dati con l'unita' sbagliata.
 */
(function () {
  const REFRESH_DEFAULT_S = 120;

  const FIELD_LABELS = {
    "outdoor.temperature": "Temperatura",
    "outdoor.feels_like": "Percepita",
    "outdoor.app_temp": "Percepita",
    "outdoor.humidity": "Umidità",
    "outdoor.dew_point": "Punto di rugiada",
    "indoor.temperature": "Temp. interna",
    "indoor.humidity": "Umidità interna",
    "wind.wind_speed": "Vento",
    "wind.wind_gust": "Raffica",
    "wind.wind_direction": "Direzione",
    "pressure.relative": "Pressione (rel.)",
    "pressure.absolute": "Pressione (ass.)",
    "rainfall.rain_rate": "Intensità pioggia",
    "rainfall.daily": "Pioggia oggi",
    "rainfall.event": "Pioggia evento",
    "rainfall.weekly": "Pioggia settimana",
    "rainfall.monthly": "Pioggia mese",
    "rainfall.yearly": "Pioggia anno",
    "solar_and_uvi.solar": "Radiazione solare",
    "solar_and_uvi.uvi": "Indice UV",
  };

  const CATEGORY_ORDER = ["outdoor", "wind", "pressure", "rainfall", "rainfall_piezo", "solar_and_uvi", "indoor", "battery"];
  const CATEGORY_LABELS = {
    outdoor: "Esterno",
    wind: "Vento",
    pressure: "Pressione",
    rainfall: "Pioggia",
    rainfall_piezo: "Pioggia",
    solar_and_uvi: "Sole / UV",
    indoor: "Interno",
    battery: "Batterie",
  };

  const COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"];

  function prettify(key) {
    const s = key.replace(/_/g, " ");
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  function degToCompass(deg) {
    const n = Number(deg);
    if (Number.isNaN(n)) return "";
    return COMPASS[Math.round(n / 22.5) % 16];
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function fieldRow(category, key, field) {
    if (!field || typeof field.value === "undefined") return "";
    const label = FIELD_LABELS[`${category}.${key}`] || prettify(key);
    const unit = field.unit || "";
    const compass = key.indexOf("direction") !== -1 ? ` ${degToCompass(field.value)}` : "";
    return `<div class="ecowitt-row"><span class="ecowitt-label">${escapeHtml(label)}</span><span class="ecowitt-value">${escapeHtml(field.value)}${escapeHtml(unit)}${escapeHtml(compass)}</span></div>`;
  }

  function render(el, payload) {
    const body = el.querySelector(".ecowitt-body");
    const updated = el.querySelector(".ecowitt-updated");

    if (!payload || payload.error) {
      body.innerHTML = `<div class="ecowitt-error">Dati non disponibili${payload && payload.error ? `: ${escapeHtml(payload.error)}` : ""}</div>`;
      return;
    }

    const data = payload.data || {};
    const categories = CATEGORY_ORDER.filter((c) => data[c]);
    Object.keys(data).forEach((c) => {
      if (categories.indexOf(c) === -1) categories.push(c);
    });

    let html = "";
    categories.forEach((cat) => {
      const rows = Object.keys(data[cat])
        .map((k) => fieldRow(cat, k, data[cat][k]))
        .filter(Boolean)
        .join("");
      if (rows) {
        html += `<div class="ecowitt-category"><h4>${escapeHtml(CATEGORY_LABELS[cat] || prettify(cat))}</h4>${rows}</div>`;
      }
    });

    body.innerHTML = html || '<div class="ecowitt-error">Nessun dato</div>';

    if (updated) {
      const epoch = Number(payload.time);
      const d = Number.isFinite(epoch) && epoch > 0 ? new Date(epoch * 1000) : new Date();
      updated.textContent = `Aggiornato: ${d.toLocaleTimeString("it-IT")}`;
    }
  }

  function buildUrl(endpoint, station) {
    const url = new URL(endpoint, window.location.href);
    if (station) url.searchParams.set("station", station);
    return url.toString();
  }

  async function tick(el, url) {
    try {
      const res = await fetch(url, { cache: "no-store" });
      const payload = await res.json();
      render(el, payload);
    } catch (e) {
      if (!el.querySelector(".ecowitt-row")) {
        el.querySelector(".ecowitt-body").innerHTML = '<div class="ecowitt-error">Connessione non riuscita</div>';
      }
    }
  }

  function mount(el) {
    if (!el || el._ecowittMounted) return;
    const endpoint = el.dataset.endpoint;
    if (!endpoint) return;

    const station = el.dataset.station || "";
    const refreshS = Math.max(10, parseInt(el.dataset.refresh || REFRESH_DEFAULT_S, 10));
    const title = el.dataset.title || "";
    const url = buildUrl(endpoint, station);

    el.classList.add("ecowitt-widget");
    el.innerHTML = `${title ? `<h3 class="ecowitt-title">${escapeHtml(title)}</h3>` : ""}<div class="ecowitt-body">Caricamento…</div><div class="ecowitt-updated"></div>`;

    tick(el, url);
    const intervalId = setInterval(() => tick(el, url), refreshS * 1000);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") tick(el, url);
    });

    el._ecowittMounted = true;
    el._ecowittInterval = intervalId;
  }

  function init() {
    document.querySelectorAll("[data-ecowitt-widget]").forEach(mount);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.EcowittWidget = { mount, init };
})();
