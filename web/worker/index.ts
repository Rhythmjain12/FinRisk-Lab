/**
 * FinRisk-Lab relay. Static files are served by Cloudflare's asset handler;
 * this Worker only answers /api/*, relaying two Yahoo Finance endpoints that
 * browsers cannot call directly.
 *
 * It is not an open proxy: the upstream host is fixed and inputs are validated.
 * It receives symbols and search text only, never amounts, and logs nothing.
 */

const UPSTREAM_HEADERS = { "User-Agent": "Mozilla/5.0 (compatible; FinRisk-Lab)", Accept: "application/json" };
const SYMBOL = /^[A-Za-z0-9.^=&-]{1,24}$/;
// Some exchanges quote in a minor unit (London in pence): currency -> [major currency, scale].
const MINOR_UNITS: Record<string, [string, number]> = {
  GBp: ["GBP", 0.01], GBX: ["GBP", 0.01], ZAc: ["ZAR", 0.01], ILA: ["ILS", 0.01],
};

const json = (body: unknown, status = 200, maxAge = 0) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": maxAge ? `public, max-age=${maxAge}` : "no-store" },
  });

async function chart(url: URL): Promise<Response> {
  const symbol = (url.searchParams.get("symbol") ?? "").toUpperCase();
  const from = url.searchParams.get("from") ?? "";
  if (!SYMBOL.test(symbol)) return json({ error: "That does not look like a ticker." }, 400);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(from)) return json({ error: "Bad start date." }, 400);

  const period1 = Math.floor(Date.parse(from) / 1000);
  const period2 = Math.floor(Date.now() / 1000);
  const upstream = await fetch(
    `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}` +
    `?period1=${period1}&period2=${period2}&interval=1d&events=div%2Csplits`,
    { headers: UPSTREAM_HEADERS },
  );
  if (upstream.status === 404) return json({ error: "no such ticker on Yahoo Finance." }, 404);
  if (upstream.status === 429) return json({ error: "the price source is rate-limiting us; try again in a minute." }, 503);
  if (!upstream.ok) return json({ error: `the price source answered ${upstream.status}.` }, 502);

  const result = ((await upstream.json()) as any)?.chart?.result?.[0];
  const timestamps: number[] = result?.timestamp ?? [];
  // Adjusted closes fold dividends, splits and bonuses into the price (same as yfinance auto_adjust).
  const closes: (number | null)[] =
    result?.indicators?.adjclose?.[0]?.adjclose ?? result?.indicators?.quote?.[0]?.close ?? [];
  const [currency, scale] = MINOR_UNITS[result?.meta?.currency] ?? [String(result?.meta?.currency ?? "").toUpperCase(), 1];
  if (!timestamps.length || !currency) return json({ error: "no price history on Yahoo Finance." }, 404);

  // Dates in the exchange's own time zone; today's unfinished bar is left out.
  const offset: number = result.meta.gmtoffset ?? 0;
  const today = new Date().toISOString().slice(0, 10);
  const dates: string[] = [], close: number[] = [];
  timestamps.forEach((t, i) => {
    const day = new Date((t + offset) * 1000).toISOString().slice(0, 10);
    const price = closes[i];
    if (price != null && price > 0 && day < today && day !== dates[dates.length - 1]) {
      dates.push(day);
      close.push(price * scale);
    }
  });
  return json({ symbol, currency, name: result.meta.longName ?? result.meta.shortName ?? symbol, dates, close }, 200, 3600);
}

async function search(url: URL): Promise<Response> {
  const query = (url.searchParams.get("q") ?? "").trim().slice(0, 60);
  if (query.length < 2) return json([]);
  const upstream = await fetch(
    `https://query2.finance.yahoo.com/v1/finance/search?q=${encodeURIComponent(query)}&quotesCount=10&newsCount=0&listsCount=0`,
    { headers: UPSTREAM_HEADERS },
  );
  if (!upstream.ok) return json({ error: "search is unavailable right now; type the ticker instead." }, 502);
  const quotes: any[] = ((await upstream.json()) as any)?.quotes ?? [];
  const matches = quotes
    .filter((q) => q.symbol && ["EQUITY", "ETF", "MUTUALFUND", "INDEX"].includes(q.quoteType))
    .map((q) => ({ symbol: q.symbol, name: q.longname ?? q.shortname ?? q.symbol, detail: `${q.symbol} · ${q.exchDisp ?? ""}` }));
  return json(matches, 200, 86400);
}

export default {
  async fetch(request: Request, _env: unknown, ctx: { waitUntil(p: Promise<unknown>): void }): Promise<Response> {
    const url = new URL(request.url);
    if (request.method !== "GET") return json({ error: "GET only." }, 405);
    const handler = url.pathname === "/api/yahoo/chart" ? chart : url.pathname === "/api/yahoo/search" ? search : null;
    if (!handler) return json({ error: "Not found." }, 404);

    // Edge cache: repeat lookups of the same symbol do not go back to Yahoo for an hour.
    const cache = (caches as unknown as { default: Cache }).default;
    const cached = await cache.match(request);
    if (cached) return cached;
    const response = await handler(url);
    if (response.ok) ctx.waitUntil(cache.put(request, response.clone()));
    return response;
  },
};
