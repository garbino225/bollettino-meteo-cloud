/**
 * Relay Cloudflare Worker per dati in tempo reale da centraline Ecowitt.
 *
 * Le vere ECOWITT_APPLICATION_KEY / ECOWITT_API_KEY vivono solo nel secret
 * store del Worker (wrangler secret put ...) e non vengono mai restituite
 * al browser: il widget JS pubblico chiama solo questo Worker, che a sua
 * volta interroga api.ecowitt.net lato server.
 *
 * Endpoint:
 *   GET /stations            -> elenco nomi stazione configurati
 *   GET /realtime             -> dati di tutte le stazioni configurate
 *   GET /realtime?station=xxx -> dati della singola stazione
 *
 * I valori restituiti da Ecowitt includono gia' un campo "unit" per ogni
 * grandezza: questo Worker li inoltra cosi' come sono (nessuna conversione
 * o rietichettatura locale), per evitare di mostrare unita' sbagliate.
 */

const ECOWITT_REALTIME_URL = "https://api.ecowitt.net/api/v3/device/real_time";

function parseStations(env) {
  try {
    const parsed = JSON.parse(env.STATIONS || "{}");
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function corsOrigin(request, env) {
  const allowed = (env.ALLOWED_ORIGINS || "*").split(",").map((s) => s.trim()).filter(Boolean);
  if (allowed.includes("*")) return "*";
  const origin = request.headers.get("Origin");
  return origin && allowed.includes(origin) ? origin : null;
}

function corsHeaders(request, env) {
  const origin = corsOrigin(request, env);
  const headers = {
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    Vary: "Origin",
  };
  if (origin) headers["Access-Control-Allow-Origin"] = origin;
  return headers;
}

function jsonResponse(body, status, request, env) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=UTF-8",
      ...corsHeaders(request, env),
    },
  });
}

async function fetchStationRealtime(deviceId, env) {
  const params = new URLSearchParams({
    application_key: env.ECOWITT_APPLICATION_KEY,
    api_key: env.ECOWITT_API_KEY,
    call_back: "all",
  });
  if (deviceId.startsWith("imei:")) {
    params.set("imei", deviceId.slice("imei:".length));
  } else {
    params.set("mac", deviceId);
  }

  const upstream = await fetch(`${ECOWITT_REALTIME_URL}?${params.toString()}`, {
    headers: { "User-Agent": "ecowitt-relay-worker" },
  });
  const payload = await upstream.json();

  if (!upstream.ok || payload.code !== 0) {
    throw new Error(payload.msg || `Ecowitt API error (HTTP ${upstream.status})`);
  }
  return { time: payload.time, data: payload.data };
}

async function handleRealtime(request, env, ctx, stationParam) {
  const cacheKey = new Request(request.url, request);
  const cache = caches.default;
  const cached = await cache.match(cacheKey);
  if (cached) return cached;

  const stations = parseStations(env);
  const names = stationParam ? [stationParam] : Object.keys(stations);

  if (stationParam && !stations[stationParam]) {
    return jsonResponse({ error: `stazione sconosciuta: ${stationParam}` }, 404, request, env);
  }
  if (names.length === 0) {
    return jsonResponse({ error: "nessuna stazione configurata (env STATIONS)" }, 500, request, env);
  }

  const results = {};
  await Promise.all(
    names.map(async (name) => {
      try {
        results[name] = await fetchStationRealtime(stations[name], env);
      } catch (e) {
        results[name] = { error: String(e.message || e) };
      }
    })
  );

  const body = stationParam ? results[stationParam] : results;
  const ttl = parseInt(env.CACHE_TTL_SECONDS || "60", 10);
  const response = jsonResponse(body, 200, request, env);
  const toCache = response.clone();
  toCache.headers.set("Cache-Control", `public, max-age=${ttl}`);
  ctx.waitUntil(cache.put(cacheKey, toCache));
  return response;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders(request, env) });
    }
    if (request.method !== "GET") {
      return jsonResponse({ error: "metodo non consentito" }, 405, request, env);
    }

    if (url.pathname === "/stations") {
      return jsonResponse({ stations: Object.keys(parseStations(env)) }, 200, request, env);
    }
    if (url.pathname === "/realtime") {
      return handleRealtime(request, env, ctx, url.searchParams.get("station"));
    }
    return jsonResponse({ error: "not found" }, 404, request, env);
  },
};
