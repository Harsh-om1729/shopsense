# Phase 11: Frontend

The website uses React, Vite, and TypeScript, and the code is in `frontend/`. It shows only what the API returns, and keeps the Phase 7 verdicts and limits visible.

## Run it

```bash
uv run uvicorn api.main:app --reload
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. If port 8000 is taken, run the API on another port and start the site with `SHOPSENSE_API_URL=http://127.0.0.1:8010 npm run dev`.

## Pages

| Page | Shows | API |
|---|---|---|
| Overview | System status, plus all 7 problems with their verdicts, including the held model's reason | `/health`, `/models` |
| Review queue | Recent orders ranked by low-review risk | `/reviews/queue` |
| Sellers | At-risk sellers with revenue and days since last sale | `/sellers/at-risk` |
| Freight | An estimate for a route and product | `/predict/freight` |
| Forecasts | Daily orders chart, category demand, and delivery time | `/forecast/*`, `/predict/delivery-time` |

## Decisions

- **Types come from the API.** `api/export_openapi.py` writes `frontend/openapi.json`, and `npm run generate:api` turns it into `src/api/schema.d.ts`. A test fails if the API changes without regenerating, so the site can't drift from the API.
- **The type generator runs separately.** `openapi-typescript` doesn't support TypeScript 7 yet, so it runs pinned with TypeScript 5 through `npx`, rather than forcing an unsupported install.
- **Dev requests go through a proxy.** Vite forwards `/api` to FastAPI. CORS is also set for listed addresses through `SHOPSENSE_CORS_ORIGINS`.
- **Forecast limits come from the API.** The new `/forecast/options` endpoint gives the date range and categories, so the site never hard-codes them.
- **The chart loads on demand.** The main bundle is 309 kB, and the Forecasts page adds 369 kB only when opened.
- **Honesty is on the page:**
  - Every page says the data is historical.
  - Queue pages say scores came from training data and aren't probabilities.
  - The seller page says days since last sale caught more revenue.
  - API errors are shown as written.
- **Freight requires weight and dimensions,** because Phase 10 showed estimates without them are unreliable.
- **Values have no currency symbol,** because the data doesn't state one.
- **Colours meet chart rules.** Text uses text colours, labels carry meaning without relying on colour, and dark mode has its own palette.

## Checks

| Check | Result |
|---|---|
| Type check, lint, and production build | Pass |
| Frontend tests | 19 pass, covering error messages, labels, required fields, zip requests, forecast dates, API errors, a wrong or missing API, and page crashes |
| Backend tests | 182 pass, including CORS, `/forecast/options`, and the schema-sync test |
| Browser | Every page was used in Chrome against the live API, with no console errors |

Browser results matched the API: 6 of 7 packages loaded, 1,311 orders in the review queue, 386 seller alerts, freight of 15.40 for a São Paulo to Rio route, a 7.24-day delivery estimate for SP, and 136 items for the first category week.

The browser check found and fixed four problems:

1. The Overview said simple rules "beat" the models, which overstated the daily forecast result.
2. Revenue showed uneven decimals.
3. Chart grid lines were too bright, because a CSS selector didn't match the chart library.
4. Tooltip text used the line colour instead of a text colour.

## Blank-screen bug, found after release

**What happened:** with another app on port 8000 and the ShopSense API stopped, the site showed a blank screen. That app answered `/api` requests with its own web page.

**Why it went blank:** the client treated that page as a successful reply with no data, a page crashed, and React cleared the screen. The browser then kept serving the cached page, because the other app sent caching headers.

**The fixes:**
- A reply that isn't JSON now becomes a clear error. That error says another program may be using the port, and explains how to use port 8010.
- An error boundary shows a message and a Reload button if any page crashes, instead of a blank screen.
- API requests skip the browser cache.

**The tests:** four new tests cover a web page returned instead of data, an API that isn't running, a proxy error, and a page crash. The fix was also checked in Chrome against the real port conflict.

**The lesson:** earlier browser checks ran against the right API, so they never met this case. A browser test should include an unavailable or wrong API.

## Known gaps

- **Phone width wasn't checked in a real browser.** Chrome didn't resize the window, so the narrow layout is untested. The CSS uses wrapping grids and scrolling tables, but Phase 12 should confirm it.
- **The site has no login,** so like the API, run it locally only.
- **Light mode wasn't viewed.** The browser was in dark mode, and light mode has its own palette but wasn't seen.
- **Dates are historical.** Forecasts run to September 2018, because the data ends there.
