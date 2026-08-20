/*
 * Meteo Garbino - generatore live.
 * Chiama direttamente le API pubbliche Open-Meteo dal browser (CORS aperto,
 * niente chiave/backend) e ricostruisce la stessa tabella multi-modello dei
 * bollettini statici (scripts/build_comparison_table.py), calcolata al volo
 * per la localita'/durata/risoluzione scelte dall'utente.
 */
(function () {
  "use strict";

  var GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search";
  var FORECAST_URL = "https://api.open-meteo.com/v1/forecast";
  var MARINE_URL = "https://marine-api.open-meteo.com/v1/marine";

  var MODEL_META = {
    ecmwf_ifs025:               { code: "ECMWF",    full: "ECMWF IFS — globale", group: "globale" },
    gfs_seamless:                { code: "GFS",      full: "NOAA GFS — globale", group: "globale" },
    icon_seamless:                { code: "ICON",     full: "DWD ICON — globale", group: "globale" },
    icon_eu:                      { code: "ICON-EU",  full: "DWD ICON-EU — area limitata Europa 13km", group: "locale" },
    icon_d2:                      { code: "ICON-D2",  full: "DWD ICON-D2 — area limitata 2km", group: "locale" },
    meteofrance_arpege_europe:    { code: "ARPEGE",   full: "Météo-France ARPEGE — globale", group: "globale" },
    meteofrance_arome_france_hd:  { code: "AROME",    full: "Météo-France AROME — area limitata Francia 1.3km", group: "locale" },
    gem_seamless:                  { code: "GEM",      full: "ECCC GEM (Canada) — globale", group: "globale" },
    ukmo_seamless:                { code: "UKMO",     full: "Met Office UM — globale", group: "globale" },
    knmi_harmonie_arome_europe:   { code: "HARMONIE", full: "KNMI HARMONIE-AROME — area limitata Europa/Benelux", group: "locale" },
    chmi_aladin_seamless:         { code: "ALADIN",   full: "CHMI ALADIN — area limitata Europa centrale", group: "locale" },
    italia_meteo_arpae_icon_2i:   { code: "ICON-2I",  full: "ItaliaMeteo/ARPAE ICON-2I — LAM Italia 2km", group: "locale" }
  };

  var WAVE_MODEL_META = {
    ecmwf_wam025:     { code: "ECMWF-WAM", full: "ECMWF WAM — onda globale" },
    meteofrance_wave: { code: "MFWAM",     full: "Météo-France MFWAM — onda globale" },
    ncep_gfswave025:  { code: "GFS-Wave",  full: "NOAA GFS-Wave — onda globale" },
    dwd_ewam:         { code: "EWAM",      full: "DWD EWAM — onda Europa" },
    dwd_gwam:         { code: "GWAM",      full: "DWD GWAM — onda globale" }
  };

  var IT_WEEKDAYS = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"];

  var SURFACE_HOURLY = [
    "temperature_2m", "relative_humidity_2m", "dew_point_2m",
    "precipitation_probability", "precipitation",
    "cloud_cover", "pressure_msl",
    "wind_speed_10m", "wind_gusts_10m", "wind_direction_10m"
  ];
  var SURFACE_DAILY = [
    "temperature_2m_max", "temperature_2m_min", "precipitation_sum",
    "precipitation_probability_max", "wind_gusts_10m_max", "wind_direction_10m_dominant",
    "sunrise", "sunset"
  ];
  var PROFILE_HOURLY = [
    "cape", "convective_inhibition", "lifted_index",
    "freezing_level_height", "total_column_integrated_water_vapour", "boundary_layer_height"
  ];
  var WAVE_HOURLY = ["wave_height", "wave_direction", "wave_period"];

  // ---------- utilita' pure (stesse soglie/formule di build_comparison_table.py) ----------

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function classify(param, v) {
    if (v === null || v === undefined) return null;
    if (param === "temp" || param === "tmax") return v < 28 ? 0 : v <= 31 ? 1 : v <= 33 ? 2 : v <= 36 ? 3 : 4;
    if (param === "tmin") return v < 20 ? 0 : v <= 24 ? 1 : v <= 27 ? 2 : v <= 30 ? 3 : 4;
    if (param === "pressione") return v >= 1013 ? 0 : v >= 1008 ? 1 : v >= 1003 ? 2 : v >= 998 ? 3 : 4;
    if (param === "umidita") return v < 60 ? 0 : v <= 70 ? 1 : v <= 80 ? 2 : v <= 90 ? 3 : 4;
    if (param === "vento") return v < 11 ? 0 : v <= 21 ? 1 : v <= 32 ? 2 : v <= 48 ? 3 : 4;
    if (param === "copertura") return v < 20 ? 0 : v <= 50 ? 1 : v <= 80 ? 2 : v <= 95 ? 3 : 4;
    if (param === "pioggia") return v <= 10 ? 0 : v <= 40 ? 1 : v <= 70 ? 2 : v <= 90 ? 3 : 4;
    if (param === "pioggia_mm") return v < 0.5 ? 0 : v <= 2 ? 1 : v <= 6 ? 2 : v <= 15 ? 3 : 4;
    if (param === "pioggia_mm_daily") return v <= 1 ? 0 : v <= 10 ? 1 : v <= 30 ? 2 : v <= 60 ? 3 : 4;
    if (param === "ondoso") return v < 0.3 ? 0 : v <= 0.6 ? 1 : v <= 1.0 ? 2 : v <= 1.5 ? 3 : 4;
    if (param === "basenubi") return v < 0.3 ? 4 : v <= 0.6 ? 3 : v <= 1.5 ? 2 : v <= 3.0 ? 1 : 0;
    if (param === "cape") return v < 300 ? 0 : v <= 1000 ? 1 : v <= 2500 ? 2 : v <= 4000 ? 3 : 4;
    if (param === "cin") return v >= 100 ? 0 : v >= 50 ? 1 : v >= 25 ? 2 : v >= 10 ? 3 : 4;
    if (param === "lifted_index") return v >= 0 ? 0 : v >= -2 ? 1 : v >= -4 ? 2 : v >= -6 ? 3 : 4;
    if (param === "tcwv") return v < 20 ? 0 : v <= 30 ? 1 : v <= 40 ? 2 : v <= 50 ? 3 : 4;
    return null;
  }

  function fmtVal(v, decimals) {
    if (v === null || v === undefined || Number.isNaN(v)) return "—";
    return decimals > 0 ? v.toFixed(decimals) : String(Math.round(v));
  }

  function cardinal(deg) {
    if (deg === null || deg === undefined) return null;
    var dirs = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"];
    var idx = Math.floor((((deg % 360) + 360) % 360 + 22.5) / 45) % 8;
    return dirs[idx];
  }

  function circularMeanDeg(degs) {
    var vals = degs.filter(function (d) { return d !== null && d !== undefined; });
    if (!vals.length) return null;
    var sx = 0, cx = 0;
    vals.forEach(function (d) { sx += Math.sin(d * Math.PI / 180); cx += Math.cos(d * Math.PI / 180); });
    if (sx === 0 && cx === 0) return null;
    return (Math.atan2(sx, cx) * 180 / Math.PI + 360) % 360;
  }

  function lclKm(t, td) {
    if (t === null || t === undefined || td === null || td === undefined) return null;
    return Math.max(0.05, (t - td) * 0.125);
  }

  function mean(arr) {
    var vals = arr.filter(function (v) { return v !== null && v !== undefined; });
    if (!vals.length) return null;
    return vals.reduce(function (a, b) { return a + b; }, 0) / vals.length;
  }

  // ---------- date helpers ----------

  function pad2(n) { return n < 10 ? "0" + n : String(n); }

  function localISODate(d) { return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate()); }

  function addDaysISO(iso, n) {
    var p = iso.split("-").map(Number);
    var d = new Date(p[0], p[1] - 1, p[2]);
    d.setDate(d.getDate() + n);
    return localISODate(d);
  }

  function weekdayOf(iso) {
    var p = iso.split("-").map(Number);
    var d = new Date(p[0], p[1] - 1, p[2]);
    return IT_WEEKDAYS[(d.getDay() + 6) % 7];
  }

  function hourISO(dateISO, hod) { return dateISO + "T" + pad2(hod) + ":00"; }

  // ---------- fetch ----------

  function fetchJSON(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) return r.text().then(function (t) { throw new Error("HTTP " + r.status + ": " + t.slice(0, 200)); });
      return r.json();
    });
  }

  function toLoc(r) {
    return { name: r.name, admin1: r.admin1, country: r.country, lat: r.latitude, lon: r.longitude, elevation: r.elevation, timezone: r.timezone };
  }

  // Cerca localita' alternative quando il nome esatto non da' risultati: la
  // ricerca di Open-Meteo e' un prefix-match, quindi un refuso in coda al
  // nome (es. "Imolla") non trova nulla mentre un prefisso piu' corto
  // ("Imol") si'; qui accorciamo progressivamente il nome finche' non
  // troviamo candidati, poi li ordiniamo alfabeticamente per proporli.
  function geocodeSuggestions(name) {
    var base = name.trim();
    function tryPrefix(n) {
      if (n.length < 2) return Promise.resolve([]);
      var url = GEOCODING_URL + "?name=" + encodeURIComponent(n) + "&count=10&language=it&format=json";
      return fetchJSON(url).then(function (js) {
        var results = js.results || [];
        if (results.length) return results;
        return tryPrefix(n.slice(0, -1));
      }).catch(function () { return []; });
    }
    return tryPrefix(base).then(function (results) {
      return results
        .map(toLoc)
        .sort(function (a, b) { return a.name.localeCompare(b.name, "it"); })
        .slice(0, 8);
    });
  }

  function geocode(name) {
    var url = GEOCODING_URL + "?name=" + encodeURIComponent(name) + "&count=1&language=it&format=json";
    return fetchJSON(url).then(function (js) {
      var top = js.results && js.results[0];
      if (top) return toLoc(top);
      return geocodeSuggestions(name).then(function (suggestions) {
        var err = new Error(
          suggestions.length
            ? "Località «" + name + "» non trovata. Forse cercavi:"
            : "Località «" + name + "» non trovata. Prova con un nome più preciso (es. «Rimini, Italia») o usa le coordinate."
        );
        err.suggestions = suggestions;
        throw err;
      });
    });
  }

  function forecastUrl(lat, lon, start, end, model, hourly, daily) {
    var params = [
      "latitude=" + lat, "longitude=" + lon,
      "start_date=" + start, "end_date=" + end,
      "hourly=" + hourly.join(","),
      "timezone=auto", "wind_speed_unit=kn", "precipitation_unit=mm"
    ];
    if (daily) params.push("daily=" + daily.join(","));
    if (model) params.push("models=" + model);
    return FORECAST_URL + "?" + params.join("&");
  }

  function fetchModel(lat, lon, start, end, model, hourly, daily) {
    return fetchJSON(forecastUrl(lat, lon, start, end, model, hourly, daily))
      .then(function (js) { return { error: null, hourly: js.hourly || null, daily: js.daily || null }; })
      .catch(function (e) { return { error: String(e.message || e), hourly: null, daily: null }; });
  }

  function fetchWaveModel(lat, lon, start, end, model) {
    var url = MARINE_URL + "?latitude=" + lat + "&longitude=" + lon + "&start_date=" + start +
      "&end_date=" + end + "&hourly=" + WAVE_HOURLY.join(",") + "&timezone=auto&models=" + model;
    return fetchJSON(url)
      .then(function (js) { return { error: null, hourly: js.hourly || null }; })
      .catch(function (e) { return { error: String(e.message || e), hourly: null }; });
  }

  // ---------- fase lunare (porting di scripts/moon_phase.py) ----------

  var SYNODIC_MONTH = 29.530588861;
  var REF_NEW_MOON_MS = Date.UTC(2000, 0, 6, 18, 14);
  var PHASE_NAMES = ["Luna Nuova", "Luna Crescente", "Primo Quarto", "Gibbosa Crescente",
    "Luna Piena", "Gibbosa Calante", "Ultimo Quarto", "Luna Calante"];

  function moonInfo(dateISO) {
    var p = dateISO.split("-").map(Number);
    var whenMs = Date.UTC(p[0], p[1] - 1, p[2], 12, 0);
    var ageDays = (((whenMs - REF_NEW_MOON_MS) / 86400000) % SYNODIC_MONTH + SYNODIC_MONTH) % SYNODIC_MONTH;
    var idx = Math.round(ageDays / (SYNODIC_MONTH / 8)) % 8;
    var pct = Math.round((1 - Math.cos(2 * Math.PI * ageDays / SYNODIC_MONTH)) / 2 * 1000) / 10;
    return { pct: pct, label: PHASE_NAMES[idx] };
  }

  // ---------- time-map (allineamento robusto per tempo, non per posizione) ----------

  function zipMap(times, values) {
    var m = new Map();
    if (!times || !values) return m;
    for (var i = 0; i < times.length; i++) m.set(times[i], values[i]);
    return m;
  }

  function windowValues(map, dateISO, hod, step) {
    var out = [];
    for (var h = hod; h < hod + step && h < 24; h++) {
      var v = map.get(hourISO(dateISO, h));
      if (v !== undefined) out.push(v);
    }
    return out;
  }

  function windowAgg(map, dateISO, hod, step, mode) {
    if (mode === "snapshot") {
      var v0 = map.get(hourISO(dateISO, hod));
      return v0 === undefined ? null : v0;
    }
    var vals = windowValues(map, dateISO, hod, step).filter(function (v) { return v !== null && v !== undefined; });
    if (!vals.length) return null;
    if (mode === "sum") return vals.reduce(function (a, b) { return a + b; }, 0);
    if (mode === "max") return Math.max.apply(null, vals);
    if (mode === "min") return Math.min.apply(null, vals);
    return mean(vals);
  }

  function dayValues(map, dateISO) {
    var out = [];
    for (var h = 0; h < 24; h++) {
      var v = map.get(hourISO(dateISO, h));
      if (v !== null && v !== undefined) out.push(v);
    }
    return out;
  }

  function dailyAgg(dailyMap, hourlyMap, dateISO, mode) {
    if (dailyMap && dailyMap.has(dateISO) && dailyMap.get(dateISO) !== null && dailyMap.get(dateISO) !== undefined) {
      return dailyMap.get(dateISO);
    }
    if (!hourlyMap) return null;
    var vals = dayValues(hourlyMap, dateISO);
    if (!vals.length) return null;
    if (mode === "sum") return vals.reduce(function (a, b) { return a + b; }, 0);
    if (mode === "max") return Math.max.apply(null, vals);
    if (mode === "min") return Math.min.apply(null, vals);
    return mean(vals);
  }

  // ---------- rendering (stessa struttura/classi CSS di build_comparison_table.py) ----------

  function renderTrendSvg(valuesByModel, modelCodes, ncols) {
    var allVals = [];
    modelCodes.forEach(function (c) { (valuesByModel[c] || []).forEach(function (v) { if (v !== null && v !== undefined) allVals.push(v); }); });
    if (!allVals.length) return "";
    var lo = Math.min.apply(null, allVals), hi = Math.max.apply(null, allVals);
    var pad = (hi - lo) * 0.18 || 1;
    lo -= pad; hi += pad;
    function x(i) { return ncols > 1 ? (i / (ncols - 1)) * 700 : 350; }
    function y(v) { return 90 - ((v - lo) / (hi - lo)) * 76; }
    var lines = [];
    modelCodes.forEach(function (c) {
      var pts = [];
      (valuesByModel[c] || []).forEach(function (v, i) { if (v !== null && v !== undefined) pts.push(x(i).toFixed(1) + "," + y(v).toFixed(1)); });
      if (pts.length >= 2) {
        lines.push('<polyline points="' + pts.join(" ") + '" fill="none" stroke="var(--ink-faint)" stroke-width="1" opacity="0.28" stroke-linejoin="round" stroke-linecap="round" />');
      }
    });
    var meanPts = [];
    for (var i = 0; i < ncols; i++) {
      var vals = modelCodes.map(function (c) { return (valuesByModel[c] || [])[i]; }).filter(function (v) { return v !== null && v !== undefined; });
      if (vals.length) meanPts.push(x(i).toFixed(1) + "," + y(mean(vals)).toFixed(1));
    }
    if (!meanPts.length) return "";
    var meanLine = meanPts.join(" ");
    var x0 = meanPts[0].split(",")[0], x1 = meanPts[meanPts.length - 1].split(",")[0];
    var area = '<polygon points="' + x0 + ',96 ' + meanLine + ' ' + x1 + ',96" fill="var(--accent)" opacity="0.08" />';
    return '<svg viewBox="0 0 700 100" preserveAspectRatio="none">' + area + lines.join("") +
      '<polyline points="' + meanLine + '" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" /></svg>';
  }

  function colLabel(mode, tc, dayLabels) {
    return mode === "hourly" ? (dayLabels[tc.dayIndex] + " " + pad2(tc.hod) + ":00") : (tc.d + " " + tc.date);
  }

  function seriesColor(i) { return "--series-" + (i % 12); }

  function renderChartLegend(modelCodes) {
    var items = modelCodes.map(function (c, i) {
      return '<span class="chart-legend-item"><span class="chart-legend-sw" style="background:var(' + seriesColor(i) + ')"></span>' + esc(c) + '</span>';
    }).join("");
    return '<div class="chart-legend">' + items + '</div>';
  }

  // Grafico a linee grande e interattivo (a differenza del mini-trend sopra,
  // usato come sfondo della riga media): stessa logica/stesse classi CSS di
  // render_chart_svg in build_comparison_table.py, cosi' CHART_INTERACTION_JS
  // (script condiviso, gia' caricato in questa pagina) funziona identico sia
  // sui bollettini statici sia qui.
  function renderChartSvg(p, mode, timeCols, dayLabels, isConv) {
    var ncols = timeCols.length;
    var unit = p.unit, decimals = p.decimals;
    var meanLabel = isConv ? "Best Match" : "Media modelli";
    var modelCodes = isConv ? [] : p.modelCodes;
    var meanVals;
    if (isConv) {
      meanVals = p.values;
    } else {
      meanVals = [];
      for (var i = 0; i < ncols; i++) {
        var vals = modelCodes.map(function (c) { return (p.values[c] || [])[i]; }).filter(function (v) { return v !== null && v !== undefined; });
        meanVals.push(vals.length ? mean(vals) : null);
      }
    }
    var allVals = meanVals.filter(function (v) { return v !== null && v !== undefined; });
    if (!isConv) {
      modelCodes.forEach(function (c) { allVals = allVals.concat((p.values[c] || []).filter(function (v) { return v !== null && v !== undefined; })); });
    }
    if (!allVals.length) return "";

    var lo = Math.min.apply(null, allVals), hi = Math.max.apply(null, allVals);
    var pad = (hi - lo) * 0.12 || 1;
    lo -= pad; hi += pad;

    var marginL = 46, marginR = 14, marginT = 14, plotH = 230, marginB = 32;
    var W = 760;
    var H = plotH + marginT + marginB;

    function x(i) { var usable = W - marginL - marginR; return ncols > 1 ? marginL + (i / (ncols - 1)) * usable : marginL + usable / 2; }
    function y(v) { return marginT + plotH - ((v - lo) / (hi - lo)) * plotH; }

    var grid = [];
    for (var t = 0; t <= 4; t++) {
      var gv = lo + (hi - lo) * t / 4, gy = y(gv);
      grid.push('<line x1="' + marginL + '" y1="' + gy.toFixed(1) + '" x2="' + (W - marginR) + '" y2="' + gy.toFixed(1) + '" stroke="var(--panel-line)" stroke-width="1"/>');
      grid.push('<text x="' + (marginL - 8) + '" y="' + (gy + 3).toFixed(1) + '" text-anchor="end" font-size="10" fill="var(--ink-faint)" font-family="IBM Plex Mono, monospace">' + fmtVal(gv, p.decimals) + '</text>');
    }

    var lines = [];
    if (!isConv) {
      modelCodes.forEach(function (c, idx) {
        var pts = [];
        (p.values[c] || []).forEach(function (v, i) { if (v !== null && v !== undefined) pts.push(x(i).toFixed(1) + "," + y(v).toFixed(1)); });
        if (pts.length >= 2) lines.push('<polyline points="' + pts.join(" ") + '" fill="none" stroke="var(' + seriesColor(idx) + ')" stroke-width="1.3" opacity="0.75"/>');
      });
    }

    var meanPts = [], circles = [];
    meanVals.forEach(function (v, i) {
      if (v === null || v === undefined) return;
      var px = x(i), py = y(v);
      meanPts.push(px.toFixed(1) + "," + py.toFixed(1));
      var lbl = colLabel(mode, timeCols[i], dayLabels);
      var rows = [meanLabel + "," + fmtVal(v, decimals) + " " + unit + ",--accent"];
      modelCodes.forEach(function (c, idx) {
        var mv = (p.values[c] || [])[i];
        var mvTxt = (mv !== null && mv !== undefined) ? (fmtVal(mv, decimals) + " " + unit) : "—";
        rows.push(c + "," + mvTxt + "," + seriesColor(idx));
      });
      var dataRows = rows.join("|");
      circles.push('<circle class="chart-pt" cx="' + px.toFixed(1) + '" cy="' + py.toFixed(1) + '" r="10" fill="transparent" ' +
        'data-x="' + px.toFixed(1) + '" data-y="' + py.toFixed(1) + '" data-label="' + esc(lbl) + '" data-rows="' + esc(dataRows) + '"/>');
    });
    var meanLine = meanPts.length >= 2 ? '<polyline points="' + meanPts.join(" ") + '" fill="none" stroke="var(--accent)" stroke-width="2.4" stroke-linejoin="round" stroke-linecap="round"/>' : "";

    var xlabels = [];
    timeCols.forEach(function (tc, i) {
      var show = mode === "hourly" ? tc.hod === 0 : true;
      if (!show) return;
      var lbl = mode === "hourly" ? dayLabels[tc.dayIndex] : (tc.d + " " + tc.date);
      xlabels.push('<text x="' + x(i).toFixed(1) + '" y="' + (H - 10) + '" text-anchor="middle" font-size="10" fill="var(--ink-faint)" font-family="IBM Plex Mono, monospace">' + esc(lbl) + '</text>');
      if (mode === "hourly" && i > 0) {
        xlabels.push('<line x1="' + x(i).toFixed(1) + '" y1="' + marginT + '" x2="' + x(i).toFixed(1) + '" y2="' + (marginT + plotH) + '" stroke="var(--panel-line)" stroke-width="1" stroke-dasharray="2,2"/>');
      }
    });

    var crosshair = '<g class="chart-crosshair" style="display:none">' +
      '<line class="ch-vline" stroke="var(--accent)" stroke-width="1" stroke-dasharray="3,3"/>' +
      '<line class="ch-hline" stroke="var(--accent)" stroke-width="1" stroke-dasharray="3,3"/>' +
      '<rect class="ch-label-bg" rx="4" ry="4" fill="var(--panel)" stroke="var(--panel-line)"/>' +
      '<text class="ch-label" font-size="10.5" font-family="IBM Plex Mono, monospace"></text>' +
      '<circle class="ch-dot" r="4" fill="var(--accent)"/></g>';

    var svg = '<svg class="chart-svg" viewBox="0 0 ' + W + ' ' + H + '">' +
      grid.join("") + lines.join("") + meanLine + circles.join("") + xlabels.join("") + crosshair + '</svg>';
    var legend = modelCodes.length ? renderChartLegend(modelCodes) : "";
    return '<div>' + svg + legend + '</div>';
  }

  function headCells(mode, timeCols, dayLabels) {
    return timeCols.map(function (tc, i) {
      if (mode === "hourly") {
        var dsc = (tc.hod === 0 && i > 0) ? " day-start" : "";
        var daytag = tc.hod === 0 ? '<span class="daytag">' + esc(dayLabels[tc.dayIndex]) + '</span>' : "";
        return '<div class="cell colhead' + dsc + '">' + daytag + '<span class="day">' + pad2(tc.hod) + '</span></div>';
      }
      return '<div class="cell colhead"><span class="day">' + esc(tc.d) + '</span><span class="date">' + esc(tc.date) + '</span></div>';
    }).join("");
  }

  function dscOf(mode, timeCols, i) {
    if (mode !== "hourly") return "";
    return (timeCols[i].hod === 0 && i > 0) ? " day-start" : "";
  }

  function fmtValueDir(valueV, gustV, dirV, decimals) {
    var s = fmtVal(valueV, decimals);
    if (gustV !== null && gustV !== undefined) s += "/" + fmtVal(gustV, decimals);
    var top = '<span class="wv">' + s + '</span>';
    var bottom = dirV ? '<span class="wd">' + esc(dirV) + '</span>' : "";
    return '<div class="wind-compact">' + top + bottom + '</div>';
  }

  function renderSection(p, mode, timeCols, dayLabels, modelsLookup) {
    var codes = p.modelCodes, ncols = timeCols.length;
    var trendSvg = renderTrendSvg(p.values, codes, ncols);
    var classifyAs = p.classifyAs || p.key;
    var hasDir = !!p.hasDirection;

    var consensusCells = [];
    for (var i = 0; i < ncols; i++) {
      var vals = codes.map(function (c) { return (p.values[c] || [])[i]; }).filter(function (v) { return v !== null && v !== undefined; });
      var avg = vals.length ? mean(vals) : null;
      var sev = classify(classifyAs, avg);
      var sevClass = sev !== null ? "sev-" + sev : "";
      var content;
      if (hasDir) {
        var gavg = null;
        if (p.hasGust && p.gustValues) {
          var gv = codes.map(function (c) { return (p.gustValues[c] || [])[i]; }).filter(function (v) { return v !== null && v !== undefined; });
          gavg = gv.length ? mean(gv) : null;
        }
        var dirV = (p.dirValues || [])[i] || null;
        content = '<div class="cval ' + sevClass + '">' + fmtValueDir(avg, gavg, dirV, p.decimals) + '</div>';
      } else {
        content = '<span class="cval ' + sevClass + '">' + fmtVal(avg, p.decimals) + '</span>';
      }
      consensusCells.push('<div class="cell consensus-cell' + dscOf(mode, timeCols, i) + '" style="grid-column:' + (2 + i) + ';grid-row:1;">' + content + '</div>');
    }

    var prevGroup = null, modelRows = [];
    codes.forEach(function (code) {
      var meta = modelsLookup[code] || {};
      var colVals = p.values[code] || new Array(ncols).fill(null);
      var colDirs = (p.dirValuesByModel || {})[code];
      var colGusts = p.hasGust ? (p.gustValues || {})[code] : null;
      var cells = [];
      for (var i = 0; i < ncols; i++) {
        var v = colVals[i];
        if (v === null || v === undefined) {
          cells.push('<div class="cell na' + dscOf(mode, timeCols, i) + '">—</div>');
        } else {
          var sev2 = classify(classifyAs, v);
          var text;
          if (hasDir) {
            var gv2 = colGusts ? colGusts[i] : null;
            var dv2 = colDirs ? colDirs[i] : null;
            text = fmtValueDir(v, gv2, dv2, p.decimals);
          } else {
            text = fmtVal(v, p.decimals);
          }
          cells.push('<div class="cell sev-' + sev2 + dscOf(mode, timeCols, i) + '">' + text + '</div>');
        }
      }
      var group = meta.group, divider = "";
      if (group && group !== prevGroup && codes.length > 4) {
        var label = group === "globale" ? "globali" : group === "locale" ? "locali (area limitata)" : group;
        divider = '<div style="display:contents"><div class="cell group-label" style="grid-column:1/-1;">Modelli ' + label + '</div></div>';
      }
      prevGroup = group;
      modelRows.push(divider + '<div class="model-row" style="display:contents"><div class="cell rowlabel">' + esc(code) + '</div>' + cells.join("") + '</div>');
    });

    var excluded = p.excludedModels || [], excludedHtml = "";
    if (excluded.length) {
      var ne = excluded.length;
      var title = excluded.map(function (e) { return e.code + ": " + e.reason; }).join(" · ");
      excludedHtml = '<span class="warn" title="' + esc(title) + '">' + ne + " modell" + (ne === 1 ? "o" : "i") + " esclus" + (ne === 1 ? "o" : "i") + '</span>';
    }
    var hourlyClass = mode === "hourly" ? "hourly" : "";
    var openAttr = p.openDefault ? " open" : "";
    var chartSvg = renderChartSvg(p, mode, timeCols, dayLabels, false);

    return '<details class="param"' + openAttr + '>' +
      '<summary><span class="arrow">&#9656;</span> ' + esc(p.label) + ' <span class="unit">' + esc(p.unit) + '</span>' + excludedHtml + '<span class="desc">' + p.threshTxt + '</span></summary>' +
      '<div class="param-toolbar"><button type="button" class="chart-toggle-btn">Tabella</button></div>' +
      '<div class="table-wrap" hidden><div class="pgrid ' + hourlyClass + '">' +
      '<div class="cell rowlabel" style="font-weight:700;">' + (mode === "hourly" ? "Ora" : "Giorno") + '</div>' +
      headCells(mode, timeCols, dayLabels) +
      '<div class="consensus-row ' + hourlyClass + '">' +
      '<div class="cell rowlabel" style="grid-column:1;grid-row:1;">Media modelli</div>' +
      '<div class="consensus-svg" style="grid-column:2/-1;grid-row:1;">' + trendSvg + '</div>' +
      consensusCells.join("") + '</div>' +
      modelRows.join("") +
      '</div></div>' +
      '<div class="chart-wrap">' + chartSvg + '</div>' +
      '</details>';
  }

  function renderConvectiveSection(p, mode, timeCols, dayLabels) {
    var ncols = timeCols.length;
    var trendSvg = renderTrendSvg({ BM: p.values }, ["BM"], ncols);
    var cells = [];
    for (var i = 0; i < ncols; i++) {
      var v = p.values[i];
      var sev = classify(p.classifyAs || p.key, v);
      var sevClass = sev !== null ? "sev-" + sev : "";
      cells.push('<div class="cell consensus-cell' + dscOf(mode, timeCols, i) + '" style="grid-column:' + (2 + i) + ';grid-row:1;"><span class="cval ' + sevClass + '">' + fmtVal(v, p.decimals) + '</span></div>');
    }
    var hourlyClass = mode === "hourly" ? "hourly" : "";
    var openAttr = p.openDefault ? " open" : "";
    var chartSvg = renderChartSvg(p, mode, timeCols, dayLabels, true);
    return '<details class="param"' + openAttr + '>' +
      '<summary><span class="arrow">&#9656;</span> ' + esc(p.label) + ' <span class="unit">' + esc(p.unit) + '</span><span class="desc">' + p.threshTxt + '</span></summary>' +
      '<div class="param-toolbar"><button type="button" class="chart-toggle-btn">Tabella</button></div>' +
      '<div class="table-wrap" hidden><div class="pgrid ' + hourlyClass + '">' +
      '<div class="cell rowlabel" style="font-weight:700;">' + (mode === "hourly" ? "Ora" : "Giorno") + '</div>' +
      headCells(mode, timeCols, dayLabels) +
      '<div class="consensus-row ' + hourlyClass + '">' +
      '<div class="cell rowlabel" style="grid-column:1;grid-row:1;">Best Match</div>' +
      '<div class="consensus-svg" style="grid-column:2/-1;grid-row:1;">' + trendSvg + '</div>' +
      cells.join("") + '</div></div>' +
      '<div class="chart-wrap">' + chartSvg + '</div>' +
      '</details>';
  }

  function renderAlmanac(dayLabels, alba, tramonto, luna) {
    var head = dayLabels.map(function (d) { return '<div class="cell colhead"><span class="day">' + esc(d) + '</span></div>'; }).join("");
    var albaHtml = alba.map(function (t) { return '<div class="cell time-cell">' + esc(t || "—") + '</div>'; }).join("");
    var tramHtml = tramonto.map(function (t) { return '<div class="cell time-cell">' + esc(t || "—") + '</div>'; }).join("");
    var lunaHtml = luna.map(function (l) {
      if (l.pct === null) return '<div class="cell moon-cell" style="border-bottom:none;"><span class="moonpct">n/d</span></div>';
      return '<div class="cell moon-cell" style="border-bottom:none;"><span class="moonpct">' + l.pct + '%</span>' +
        '<span class="spread-track"><span class="spread-fill" style="width:' + l.pct + '%"></span></span>' +
        '<span class="moonlabel">' + esc(l.label) + '</span></div>';
    }).join("");
    return '<div class="pgrid" style="grid-template-columns:var(--label-w) repeat(' + dayLabels.length + ',minmax(60px,1fr));">' +
      '<div class="cell rowlabel" style="font-weight:700;">Giorno</div>' + head +
      '<div class="cell rowlabel">Alba</div>' + albaHtml +
      '<div class="cell rowlabel">Tramonto</div>' + tramHtml +
      '<div class="cell rowlabel" style="border-bottom:none;">Fase lunare</div>' + lunaHtml + '</div>';
  }

  // ---------- orchestrazione ----------

  var form = document.getElementById("gen-form");
  var statusEl = document.getElementById("gen-status");
  var suggestionsEl = document.getElementById("gen-suggestions");
  var submitBtn = document.getElementById("gen-submit");
  var resultEl = document.getElementById("gen-result");
  var fieldCity = document.getElementById("field-city");
  var fieldLat = document.getElementById("field-lat");
  var fieldLon = document.getElementById("field-lon");

  Array.prototype.forEach.call(document.getElementsByName("locmode"), function (r) {
    r.addEventListener("change", function () {
      var isCity = form.locmode.value === "city";
      fieldCity.classList.toggle("gen-hidden", !isCity);
      fieldLat.classList.toggle("gen-hidden", isCity);
      fieldLon.classList.toggle("gen-hidden", isCity);
    });
  });

  function setStatus(msg, isErr) {
    statusEl.textContent = msg || "";
    statusEl.classList.toggle("err", !!isErr);
  }

  function renderSuggestions(list) {
    if (!suggestionsEl) return;
    if (!list || !list.length) { suggestionsEl.innerHTML = ""; return; }
    suggestionsEl.innerHTML = list.map(function (loc) {
      var label = loc.name + (loc.admin1 ? ", " + loc.admin1 : "") + (loc.country ? " (" + loc.country + ")" : "");
      return '<button type="button" class="gen-suggestion-btn" data-city="' + esc(loc.name) + '">' + esc(label) + '</button>';
    }).join("");
  }

  if (suggestionsEl) {
    suggestionsEl.addEventListener("click", function (e) {
      var btn = e.target && e.target.closest && e.target.closest(".gen-suggestion-btn");
      if (!btn) return;
      document.getElementById("input-city").value = btn.getAttribute("data-city");
      renderSuggestions([]);
      runGenerate().catch(function (err) {
        console.error(err);
        setStatus("Errore: " + (err && err.message ? err.message : err), true);
        renderSuggestions(err && err.suggestions);
        submitBtn.disabled = false;
      });
    });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    runGenerate().catch(function (err) {
      console.error(err);
      setStatus("Errore: " + (err && err.message ? err.message : err), true);
      renderSuggestions(err && err.suggestions);
      submitBtn.disabled = false;
    });
  });

  function runGenerate() {
    renderSuggestions([]);
    var locModeEl = form.querySelector('input[name="locmode"]:checked');
    if (!locModeEl) { setStatus("Scegli se cercare per città o per coordinate.", true); return Promise.resolve(); }
    var locMode = locModeEl.value;

    var daysEl = form.querySelector('input[name="days"]:checked');
    if (!daysEl) { setStatus("Scegli la durata.", true); return Promise.resolve(); }
    var days = parseInt(daysEl.value, 10);

    var stepEl = form.querySelector('input[name="step"]:checked');
    if (!stepEl) { setStatus("Scegli la risoluzione oraria.", true); return Promise.resolve(); }
    var step = parseInt(stepEl.value, 10);

    submitBtn.disabled = true;
    resultEl.innerHTML = "";
    setStatus("Risoluzione località…");

    var locPromise;
    if (locMode === "city") {
      var cityName = document.getElementById("input-city").value.trim();
      if (!cityName) { submitBtn.disabled = false; setStatus("Inserisci il nome di una città.", true); return Promise.resolve(); }
      locPromise = geocode(cityName);
    } else {
      var lat = parseFloat(document.getElementById("input-lat").value);
      var lon = parseFloat(document.getElementById("input-lon").value);
      if (Number.isNaN(lat) || Number.isNaN(lon)) { submitBtn.disabled = false; setStatus("Inserisci latitudine e longitudine valide.", true); return Promise.resolve(); }
      locPromise = Promise.resolve({ name: lat.toFixed(3) + ", " + lon.toFixed(3), admin1: null, country: null, lat: lat, lon: lon, elevation: null, timezone: null });
    }

    return locPromise.then(function (loc) {
      var startISO = localISODate(new Date());
      var endISO = addDaysISO(startISO, days - 1);
      var modelKeys = Object.keys(MODEL_META);

      setStatus("Scaricamento dati da Open-Meteo (" + modelKeys.length + " modelli" + (step < 24 ? "" : "") + ")…");

      var modelPromises = modelKeys.map(function (mk) {
        return fetchModel(loc.lat, loc.lon, startISO, endISO, mk, SURFACE_HOURLY, SURFACE_DAILY).then(function (r) { return [mk, r]; });
      });
      var profilePromise = fetchModel(loc.lat, loc.lon, startISO, endISO, "best_match", PROFILE_HOURLY, null);
      var wavePromises = Object.keys(WAVE_MODEL_META).map(function (mk) {
        return fetchWaveModel(loc.lat, loc.lon, startISO, endISO, mk).then(function (r) { return [mk, r]; });
      });

      return Promise.all([Promise.all(modelPromises), profilePromise, Promise.all(wavePromises)]).then(function (res) {
        var models = {}; res[0].forEach(function (pair) { models[pair[0]] = pair[1]; });
        var profile = res[1];
        var waveModels = {}; res[2].forEach(function (pair) { waveModels[pair[0]] = pair[1]; });
        setStatus("Elaborazione tabella…");
        var html = buildReport(loc, startISO, endISO, days, step, models, profile, waveModels);
        resultEl.innerHTML = html;
        setStatus("Fatto — " + loc.name + ", " + startISO + " → " + endISO + (step === 24 ? " (giornaliera)" : " (ogni " + step + "h)"));
        submitBtn.disabled = false;
        resultEl.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }

  function buildReport(loc, startISO, endISO, days, step, models, profile, waveModels) {
    var mode = step === 24 ? "daily" : "hourly";
    var okModelIds = Object.keys(models).filter(function (mk) { return !models[mk].error && MODEL_META[mk]; });
    if (!okModelIds.length) throw new Error("Nessun modello disponibile per questa località/periodo.");

    // --- griglia temporale ---
    var seenDays = [];
    for (var d = 0; d < days; d++) seenDays.push(addDaysISO(startISO, d));

    var timeCols = [], dayLabels = seenDays.map(function (iso) { return weekdayOf(iso) + " " + iso.slice(8, 10) + "/" + iso.slice(5, 7); });
    if (mode === "daily") {
      timeCols = seenDays.map(function (iso) { return { d: weekdayOf(iso), date: iso.slice(8, 10) + "/" + iso.slice(5, 7) }; });
    } else {
      seenDays.forEach(function (iso, di) {
        for (var h = 0; h < 24; h += step) timeCols.push({ hod: h, dayIndex: di, date: iso });
      });
    }
    var ncols = timeCols.length;

    // --- helper: costruisce la serie di un campo per un modello, allineata a timeCols ---
    function series(mk, hourlyField, dailyField, aggDaily, windowMode) {
      var mdl = models[mk];
      var hMap = mdl.hourly ? zipMap(mdl.hourly.time, mdl.hourly[hourlyField]) : null;
      var dMap = (dailyField && mdl.daily) ? zipMap(mdl.daily.time, mdl.daily[dailyField]) : null;
      if (mode === "daily") {
        return seenDays.map(function (iso) { return dailyAgg(dMap, hMap, iso, aggDaily || "mean"); });
      }
      if (!hMap) return timeCols.map(function () { return null; });
      return timeCols.map(function (tc) { return windowAgg(hMap, tc.date, tc.hod, step, windowMode || "snapshot"); });
    }

    function collect(hourlyField, dailyField, aggDaily, windowMode) {
      var values = {}, excluded = [];
      okModelIds.forEach(function (mk) {
        var code = MODEL_META[mk].code;
        var s = series(mk, hourlyField, dailyField, aggDaily, windowMode);
        if (s.every(function (v) { return v === null || v === undefined; })) {
          excluded.push({ code: code, reason: "variabile non fornita da questo modello" });
        } else {
          values[code] = s;
        }
      });
      return { values: values, excluded: excluded };
    }

    function modelCodesFor(values) {
      return okModelIds.map(function (mk) { return MODEL_META[mk].code; }).filter(function (c) { return values.hasOwnProperty(c); });
    }

    var params = [];
    var modelsMeta = okModelIds.map(function (mk) { return MODEL_META[mk]; });

    // Temperatura
    if (mode === "daily") {
      var rMax = collect("temperature_2m", "temperature_2m_max", "max");
      var rMin = collect("temperature_2m", "temperature_2m_min", "min");
      params.push({ key: "tmax", classifyAs: "tmax", label: "Temperatura massima", unit: "°C", decimals: 1,
        threshTxt: "&lt;30 bianco · 30–33 giallo · 33–36 arancio · 36–40 rosso · &gt;40 fucsia",
        modelCodes: modelCodesFor(rMax.values), values: rMax.values, excludedModels: rMax.excluded });
      params.push({ key: "tmin", classifyAs: "tmin", label: "Temperatura minima", unit: "°C", decimals: 1,
        threshTxt: "&lt;20 bianco · 20–24 giallo (notte tropicale) · &gt;24 arancio+",
        modelCodes: modelCodesFor(rMin.values), values: rMin.values, excludedModels: rMin.excluded });
    } else {
      var rTemp = collect("temperature_2m", null, "mean", "snapshot");
      params.push({ key: "temp", classifyAs: "temp", label: "Temperatura", unit: "°C", decimals: 1,
        threshTxt: "&lt;28 bianco · 28–31 giallo · 31–33 arancio · 33–36 rosso · &gt;36 fucsia",
        modelCodes: modelCodesFor(rTemp.values), values: rTemp.values, excludedModels: rTemp.excluded });
    }

    var rPres = collect("pressure_msl", null, "mean", "snapshot");
    params.push({ key: "pressione", label: "Pressione (SLP)", unit: "hPa", decimals: 0,
      threshTxt: "ridotta al livello del mare · &ge;1013 bianco · 1008–1012 giallo · 1003–1007 arancio · 998–1002 rosso · &lt;998 fucsia",
      modelCodes: modelCodesFor(rPres.values), values: rPres.values, excludedModels: rPres.excluded });

    var rHum = collect("relative_humidity_2m", null, "mean", "snapshot");
    params.push({ key: "umidita", label: "Umidità", unit: "%", decimals: 0,
      threshTxt: "&lt;60 bianco · 60–70 giallo · 70–80 arancio · 80–90 rosso · &gt;90 fucsia",
      modelCodes: modelCodesFor(rHum.values), values: rHum.values, excludedModels: rHum.excluded });

    var rCov = collect("cloud_cover", null, "mean", "snapshot");
    params.push({ key: "copertura", label: "Copertura nuvolosa", unit: "%", decimals: 0,
      threshTxt: "&lt;20 bianco (sereno) · 20–50 giallo · 50–80 arancio · 80–95 rosso · &gt;95 fucsia",
      modelCodes: modelCodesFor(rCov.values), values: rCov.values, excludedModels: rCov.excluded });

    // Base nubi (stima LCL da temperatura/dew point)
    (function () {
      var values = {}, excluded = [];
      okModelIds.forEach(function (mk) {
        var code = MODEL_META[mk].code, mdl = models[mk];
        if (!mdl.hourly || !mdl.hourly.temperature_2m || !mdl.hourly.dew_point_2m) {
          excluded.push({ code: code, reason: "temperatura/dew point non disponibili" }); return;
        }
        var tMap = zipMap(mdl.hourly.time, mdl.hourly.temperature_2m);
        var tdMap = zipMap(mdl.hourly.time, mdl.hourly.dew_point_2m);
        var s;
        if (mode === "daily") {
          s = seenDays.map(function (iso) {
            var vs = [];
            for (var h = 0; h < 24; h++) {
              var t = tMap.get(hourISO(iso, h)), td = tdMap.get(hourISO(iso, h));
              var lcl = lclKm(t, td); if (lcl !== null) vs.push(lcl);
            }
            return vs.length ? Math.min.apply(null, vs) : null;
          });
        } else {
          s = timeCols.map(function (tc) { return lclKm(tMap.get(hourISO(tc.date, tc.hod)), tdMap.get(hourISO(tc.date, tc.hod))); });
        }
        values[code] = s;
      });
      params.push({ key: "basenubi", label: "Base nubi (stima LCL)", unit: "km", decimals: 1,
        threshTxt: "stima da T e punto di rugiada (0,125 km/°C di scarto) · &lt;0,3 fucsia (nebbia) · 0,3–0,6 rosso · 0,6–1,5 arancio · 1,5–3 giallo · &gt;3 bianco",
        modelCodes: modelCodesFor(values), values: values, excludedModels: excluded });
    })();

    // Probabilita' pioggia
    var rRp = mode === "daily" ? collect("precipitation_probability", "precipitation_probability_max", "max")
      : collect("precipitation_probability", null, "mean", "max");
    params.push({ key: "pioggia", label: "Probabilità pioggia", unit: "%", decimals: 0,
      threshTxt: "0–10 bianco · 11–40 giallo · 41–70 arancio · 71–90 rosso · &gt;90 fucsia",
      modelCodes: modelCodesFor(rRp.values), values: rRp.values, excludedModels: rRp.excluded });

    // Quantita' precipitazione
    var classifyMm, unitMm, threshMm, rMm;
    if (mode === "daily") {
      rMm = collect("precipitation", "precipitation_sum", "sum");
      classifyMm = "pioggia_mm_daily"; unitMm = "mm";
      threshMm = "totale giornaliero · &le;1 bianco · 1–10 giallo · 10–30 arancio · 30–60 rosso · &gt;60 fucsia";
    } else {
      rMm = collect("precipitation", null, "sum", "sum");
      classifyMm = "pioggia_mm"; unitMm = step === 1 ? "mm/h" : "mm/" + step + "h";
      threshMm = (step === 1 ? "intensità oraria" : "totale nella finestra di " + step + "h") +
        " · &lt;0,5 bianco (assente) · 0,5–2 giallo (debole) · 2–6 arancio (moderata) · 6–15 rosso (forte) · &gt;15 fucsia (nubifragio)";
    }
    params.push({ key: "pioggia_mm", classifyAs: classifyMm, label: "Quantità precipitazione", unit: unitMm, decimals: 1,
      threshTxt: threshMm, modelCodes: modelCodesFor(rMm.values), values: rMm.values, excludedModels: rMm.excluded });

    // Vento (medio + raffica + direzione)
    var rWind, rGustVals = {}, dirDegPerModel = {};
    if (mode === "daily") {
      rWind = collect("wind_speed_10m", null, "mean");
      okModelIds.forEach(function (mk) {
        var code = MODEL_META[mk].code, mdl = models[mk];
        if (mdl.daily && mdl.daily.wind_gusts_10m_max) {
          var dMap = zipMap(mdl.daily.time, mdl.daily.wind_gusts_10m_max);
          var s = seenDays.map(function (iso) { return dMap.has(iso) ? dMap.get(iso) : null; });
          if (s.some(function (v) { return v !== null; })) rGustVals[code] = s;
        }
        if (mdl.daily && mdl.daily.wind_direction_10m_dominant) {
          var dMap2 = zipMap(mdl.daily.time, mdl.daily.wind_direction_10m_dominant);
          var s2 = seenDays.map(function (iso) { return dMap2.has(iso) ? dMap2.get(iso) : null; });
          if (s2.some(function (v) { return v !== null; })) dirDegPerModel[code] = s2;
        }
      });
    } else {
      rWind = collect("wind_speed_10m", null, "mean", "snapshot");
      var rGust = collect("wind_gusts_10m", null, "max", "max");
      rGustVals = rGust.values;
      var rDir = collect("wind_direction_10m", null, "mean", "snapshot");
      dirDegPerModel = rDir.values;
    }
    var dirValues = [];
    for (var i = 0; i < ncols; i++) {
      var degs = Object.keys(dirDegPerModel).map(function (c) { return dirDegPerModel[c][i]; }).filter(function (v) { return v !== null && v !== undefined; });
      dirValues.push(cardinal(circularMeanDeg(degs)));
    }
    var dirValuesByModel = {};
    Object.keys(dirDegPerModel).forEach(function (c) { dirValuesByModel[c] = dirDegPerModel[c].map(cardinal); });

    params.push({ key: "vento", label: "Vento", unit: "kn", decimals: 0, hasDirection: true, hasGust: true,
      threshTxt: "medio/raffica in nodi, direzione a capo (es. 2/3, SO sotto) · &lt;11 bianco · 11–21 giallo · 22–32 arancio · 33–48 rosso · &ge;49 fucsia (in base al medio)",
      modelCodes: modelCodesFor(rWind.values), values: rWind.values, gustValues: rGustVals,
      dirValues: dirValues, dirValuesByModel: dirValuesByModel, excludedModels: rWind.excluded });

    // --- Moto ondoso (solo se marine.json restituisce dati per questo punto) ---
    var waveModelsMeta = [], wmOk = Object.keys(waveModels).filter(function (mk) { return !waveModels[mk].error && waveModels[mk].hourly; });
    if (wmOk.length) {
      var vWave = {}, exWave = [], waveDirPerModel = {};
      function waveSeries(mk, field, aggDaily) {
        var mdl = waveModels[mk];
        var hMap = zipMap(mdl.hourly.time, mdl.hourly[field]);
        if (mode === "daily") return seenDays.map(function (iso) { return dailyAgg(null, hMap, iso, aggDaily || "mean"); });
        return timeCols.map(function (tc) { var v = hMap.get(hourISO(tc.date, tc.hod)); return v === undefined ? null : v; });
      }
      wmOk.forEach(function (mk) {
        var code = WAVE_MODEL_META[mk].code;
        var s = waveSeries(mk, "wave_height", "mean");
        if (s.every(function (v) { return v === null; })) { exWave.push({ code: code, reason: "onda non disponibile per quest'area" }); }
        else { vWave[code] = s; waveModelsMeta.push(WAVE_MODEL_META[mk]); }
        var d = waveSeries(mk, "wave_direction", "mean");
        if (d.some(function (v) { return v !== null; })) waveDirPerModel[code] = d;
      });
      if (Object.keys(vWave).length) {
        var waveDirValues = [];
        for (var wi = 0; wi < ncols; wi++) {
          var wdegs = Object.keys(waveDirPerModel).map(function (c) { return waveDirPerModel[c][wi]; }).filter(function (v) { return v !== null && v !== undefined; });
          waveDirValues.push(cardinal(circularMeanDeg(wdegs)));
        }
        var waveDirByModel = {};
        Object.keys(waveDirPerModel).forEach(function (c) { waveDirByModel[c] = waveDirPerModel[c].map(cardinal); });
        params.push({ key: "ondoso", label: "Moto ondoso (altezza onda)", unit: "m", decimals: 2, hasDirection: true,
          threshTxt: "&lt;0,3 bianco (calmo) · 0,3–0,6 giallo (poco mosso) · 0,6–1,0 arancio (mosso) · 1,0–1,5 rosso (molto mosso) · &gt;1,5 fucsia (agitato)",
          modelCodes: waveModelsMeta.map(function (m) { return m.code; }).filter(function (c) { return vWave.hasOwnProperty(c); }),
          values: vWave, dirValues: waveDirValues, dirValuesByModel: waveDirByModel, excludedModels: exWave });
      }
    }

    // --- Parametri convettivi (unica sorgente: profilo Best Match) ---
    var convParams = [];
    if (!profile.error && profile.hourly) {
      var pHourlyMap = {};
      PROFILE_HOURLY.forEach(function (f) { pHourlyMap[f] = zipMap(profile.hourly.time, profile.hourly[f]); });
      function convSeries(field, aggDaily) {
        var hMap = pHourlyMap[field];
        if (mode === "daily") return seenDays.map(function (iso) { return dailyAgg(null, hMap, iso, aggDaily); });
        return timeCols.map(function (tc) { var v = hMap.get(hourISO(tc.date, tc.hod)); return v === undefined ? null : v; });
      }
      var convDefs = [
        ["cape", "cape", "CAPE (energia potenziale convettiva)", "J/kg", 0, "max",
          "&lt;300 bianco (debole) · 300–1000 giallo (moderata) · 1000–2500 arancio (forte) · 2500–4000 rosso (molto forte) · &gt;4000 fucsia (estrema)"],
        ["cin", "convective_inhibition", "CIN (inibizione convettiva)", "J/kg", 0, "min",
          "scala invertita: cappa debole = innesco temporali più facile · &ge;100 bianco (cappa forte) · 50–99 giallo · 25–49 arancio · 10–24 rosso · &lt;10 fucsia (nessuna inibizione)"],
        ["lifted_index", "lifted_index", "Lifted Index", "°C", 1, "min",
          "&ge;0 bianco (stabile) · 0/-2 giallo (marginale) · -2/-4 arancio (instabile) · -4/-6 rosso (molto instabile) · &lt;-6 fucsia (estremo)"],
        ["freezing_level", "freezing_level_height", "Quota dello zero termico", "m", 0, "mean",
          "informativo, nessuna soglia di rischio: utile per la quota neve e per stimare la dimensione della grandine"],
        ["boundary_layer", "boundary_layer_height", "Altezza dello strato limite", "m", 0, "max",
          "informativo, nessuna soglia di rischio: altezza di rimescolamento dell'aria vicino al suolo"],
        ["tcwv", "total_column_integrated_water_vapour", "Acqua precipitabile (colonna totale)", "kg/m²", 0, "max",
          "&lt;20 bianco · 20–30 giallo · 30–40 arancio · 40–50 rosso · &gt;50 fucsia (colonna satura, nubifragi possibili)"]
      ];
      convDefs.forEach(function (def) {
        var s = convSeries(def[1], def[5]);
        if (s.some(function (v) { return v !== null && v !== undefined; })) {
          convParams.push({ key: def[0], classifyAs: def[0], label: def[2], unit: def[3], decimals: def[4], threshTxt: def[6], values: s });
        }
      });
    }

    // --- Almanacco ---
    var alba = [], tramonto = [];
    seenDays.forEach(function (iso) {
      var sunrise = null, sunset = null;
      for (var mi = 0; mi < okModelIds.length && (!sunrise || !sunset); mi++) {
        var mdl = models[okModelIds[mi]];
        if (mdl.daily && mdl.daily.time) {
          var idx = mdl.daily.time.indexOf(iso);
          if (idx >= 0) {
            var sr = mdl.daily.sunrise && mdl.daily.sunrise[idx];
            var ss = mdl.daily.sunset && mdl.daily.sunset[idx];
            if (sr) sunrise = sr.split("T")[1].slice(0, 5);
            if (ss) sunset = ss.split("T")[1].slice(0, 5);
          }
        }
      }
      alba.push(sunrise); tramonto.push(sunset);
    });
    var luna = seenDays.map(moonInfo);

    // --- meta ---
    var admin = loc.admin1;
    var periodLabel = timeCols.length && mode === "daily"
      ? (timeCols[0].d + " " + timeCols[0].date + " – " + timeCols[timeCols.length - 1].d + " " + timeCols[timeCols.length - 1].date)
      : (weekdayOf(seenDays[0]) + " " + seenDays[0].slice(8, 10) + "/" + seenDays[0].slice(5, 7) + " – " +
        weekdayOf(seenDays[seenDays.length - 1]) + " " + seenDays[seenDays.length - 1].slice(8, 10) + "/" + seenDays[seenDays.length - 1].slice(5, 7));

    var allExcluded = [];
    params.forEach(function (p) { (p.excludedModels || []).forEach(function (e) { allExcluded.push(p.label + ": " + e.code + " (" + e.reason + ")"); }); });

    var allModelsMeta = modelsMeta.concat(waveModelsMeta);
    var modelsLookup = {}; allModelsMeta.forEach(function (m) { modelsLookup[m.code] = m; });

    var eyebrow = "Dati reali · confronto multi-modello · generato dal browser · " + (mode === "daily" ? "giornaliera" : "ogni " + step + " ore");
    var titleHtml = esc(loc.name) + " <em>&middot; dati reali</em>";
    var subHtml = esc(admin || "") + (admin ? " · " : "") +
      (loc.elevation && loc.elevation > 200 ? Math.round(loc.elevation) + " m s.l.m. · " : "") +
      esc(periodLabel) + (waveModelsMeta.length ? " · località costiera, incluso moto ondoso" : "") +
      ". Fonte: Open-Meteo (dati reali multi-modello), calcolato nel browser.";
    var metaStrip = "lat " + loc.lat.toFixed(4) + " · lon " + loc.lon.toFixed(4) + (loc.elevation !== null && loc.elevation !== undefined ? " · " + Math.round(loc.elevation) + " m" : "");

    // Solo il primo parametro aperto di default: con fino a 168 colonne
    // orarie per sezione, tenerle tutte espanse appesantisce il rendering
    // iniziale (migliaia di celle mai guardate). Le <details> chiuse non
    // richiedono layout finche' l'utente non le apre.
    params.forEach(function (p, i) { p.openDefault = (i === 0); });
    convParams.forEach(function (p) { p.openDefault = false; });

    var almanacHtml = renderAlmanac(dayLabels, alba, tramonto, luna);
    var sectionsHtml = params.map(function (p) { return renderSection(p, mode, timeCols, dayLabels, modelsLookup); }).join("\n");
    var convSectionsHtml = convParams.map(function (p) { return renderConvectiveSection(p, mode, timeCols, dayLabels); }).join("\n");

    var notesItems = [
      "<strong>Dati reali</strong>: scaricati da Open-Meteo direttamente dal tuo browser (nessun server nel mezzo) il " + new Date().toLocaleString("it-IT") + ".",
      "<strong>Modelli confrontati (" + modelsMeta.length + "):</strong> " + modelsMeta.map(function (m) { return m.code; }).join(", ") + ". <code>best_match</code> (blend automatico) &egrave; escluso dal confronto per non falsare la media con un modello non distinto.",
      "<strong>Risoluzione</strong>: " + (mode === "daily" ? "una colonna per giorno (aggregati: max/min/somma a seconda del parametro)." : "una colonna ogni " + step + " " + (step === 1 ? "ora" : "ore") + " (valore puntuale, tranne pioggia/raffica che sono aggregate sulla finestra)."),
      "<strong>Parametri convettivi</strong>: a differenza degli altri, provengono da un'unica sorgente (profilo Best Match), non da un confronto multi-modello."
    ];
    if (allExcluded.length) notesItems.push("<strong>Variabili non disponibili per alcuni modelli</strong>: " + allExcluded.join("; ") + ".");
    var notesHtml = "<ul>" + notesItems.map(function (it) { return "<li>" + it + "</li>"; }).join("") + "</ul>";

    return '<div class="masthead" style="margin-top:8px;">' +
      '<div class="masthead-row"><div class="masthead-main">' +
      '<div class="eyebrow-row"><div class="eyebrow">' + eyebrow + '</div></div>' +
      '<h1>' + titleHtml + '</h1>' +
      '<p class="sub">' + subHtml + '</p>' +
      '<div class="meta-strip">' + metaStrip + '</div>' +
      '</div></div><div class="spectrum"></div></div>' +
      '<div class="almanac-panel"><span class="legend-title">Alba &middot; tramonto &middot; fase lunare (reali)</span>' +
      '<div class="table-wrap" style="padding:0;">' + almanacHtml + '</div></div>' +
      '<div class="sections" style="--ncols:' + ncols + ';">' + sectionsHtml + '</div>' +
      (convParams.length ? '<div style="margin:2px;"><span class="legend-title">Parametri convettivi (rischio temporali) &middot; sorgente singola: blend Best Match</span></div>' +
        '<div class="sections" style="--ncols:' + ncols + ';">' + convSectionsHtml + '</div>' : "") +
      '<div class="notes"><h2>Note</h2>' + notesHtml + '</div>';
  }
})();
