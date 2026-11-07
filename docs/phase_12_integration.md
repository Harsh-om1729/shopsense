# Phase 12: Integration testing

## Run every check

```bash
scripts/check_all.sh            # lint, tests, type checks, build, and browser tests
scripts/check_all.sh --rebuild  # also rebuild everything from raw data, about 30 seconds more
```

## What's tested

| Layer | Tool | Count | Needs local data |
|---|---|---:|---|
| Backend unit and API tests | pytest | 191 | Some (39 skip without it) |
| Frontend unit tests | Vitest | 19 | No |
| Browser tests | Playwright | 28 (14 tests at 2 screen sizes) | Yes |
| Full rebuild | `scripts/rebuild_check.py` | Every key API answer | Yes |
| GitHub Actions | `.github/workflows/ci.yml` | Backend and frontend checks | No |

## Browser tests

`frontend/e2e/app.spec.ts` starts the real API on port 8011 and the site on port 5174, so it never clashes with anything on 8000 or 5173. It sets `SHOPSENSE_LOG_PREDICTIONS=false`, so tests don't fill the prediction log.

Each test runs at **desktop width in dark mode** and **phone width (Pixel 7) in light mode**. Together they check:

- Every page loads real data, with no loading or error messages left showing.
- The historical-data banner appears on every page.
- No page scrolls sideways.
- Each colour scheme uses its own background.
- The browser logs no errors.
- Every interaction works: queue length, seller filter, freight form checks, freight estimates and the unknown-distance warning, the forecast chart and its values table, category and delivery estimates, and the not-found page.
- **A wrong API**, such as another app's web page, and **a stopped API** both show a clear message, not a blank screen.

Screenshots of every page are saved to `frontend/test-results/` and reviewed by eye. That review found the chart's "0" overlapping the first date at phone width, which is now fixed.

## Full rebuild

`uv run python -m scripts.rebuild_check` records key answers, reruns `make_dataset`, `make_features`, `package`, and `db.load`, then compares:

- the freight estimate,
- both delivery estimates,
- the forecast range,
- a daily forecast,
- all 10 category forecasts,
- the top 20 review orders and sellers with their scores,
- the alert count.

The latest run reproduced every answer exactly.

**What it doesn't rerun:** tuning, because its settings are frozen in `reports/tuned_models.json`.

**Registry:** packaging rewrites `reports/model_registry.json` with the current commit, so the check restores that file afterwards.

## Failure handling

`tests/test_integration.py` runs the real API with parts missing:

- **Empty database:** `/health` reports `degraded`. The queues and zip lookups return 503, saying to run `src.db.load`, and rules that don't need the database keep working.
- **No packages:** every model endpoint returns 503, saying to run `src.models.package`.
- **An unexpected error:** it returns a plain 500, without internal details.

## GitHub Actions

The workflow runs lint, formatting, and tests for the backend, plus type checks, lint, tests, and a build for the frontend. Tests that need data skip themselves with a reason.

A clean copy of the repository, with no data or models, gave 152 passed, 39 skipped, and 0 failed for the backend, and passed every frontend step. That matches how GitHub will run it.

## Bugs found by this phase

- **A test pattern blocked the site's own code.** `**/api/**` in a browser test also matched `/src/api/client.ts`, so the faked broken API stopped the app from loading. The test now matches only real API calls.
- **The rebuild check couldn't find the `api` package** when run as a file. It now runs as a module.
- **Running the rebuild changed a tracked file,** the model registry. The check now restores it.
- **Chart labels overlapped at phone width.**

## Known gaps

- **The workflow hasn't run on GitHub yet.** The action versions (`checkout@v4`, `setup-uv@v6`, `setup-node@v4`) are checked only once it's pushed. Check the Actions tab after pushing.
- **Browser tests and the rebuild need local data,** so they don't run in CI.
- **Only Chromium is tested.** Safari and Firefox aren't.
- **Disk space:** Playwright's Chromium takes about 600 MB in `~/Library/Caches/ms-playwright`.
