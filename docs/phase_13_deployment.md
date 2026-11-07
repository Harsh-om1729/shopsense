# Phase 13: Deployment and documentation

Deployment is local only, through Docker. A public site would first need a login and a confirmed dataset licence.

## Run it

```bash
docker compose up --build   # http://localhost:8088
```

## How it's built

- **`api/serve.py`** serves the API under `/api` and the built site at `/`, from one address, so production needs no CORS. Unknown site paths return `index.html`, so refreshing a page like `/reviews` works.
- **The `Dockerfile` has two stages.** Node builds the site, and a slim Python 3.13 image runs it, as a non-root user with a health check.
- **The image holds code only.** `docker-compose.yml` attaches `models/` as read-only and `data/processed/`, which stays writable for the prediction log.
- **The port is `127.0.0.1:8088`.** 8000 and 8080 were taken on the development machine, by another project and Jenkins. Binding to `127.0.0.1` keeps the unauthenticated app off the network. Set `SHOPSENSE_PORT` to change the port.
- **The image is 1.49 GB, down from 2.14 GB.** Notebook-only packages moved to the dev group, and bytecode pre-compiling is off. The rest is scikit-learn, scipy, pandas, pyarrow, and numpy, which the app needs.

## Checks

| Check | Result |
|---|---|
| Serving tests | 7 pass: API under `/api`, site at `/`, page refresh, unknown API paths stay 404, API docs, and a clear error if the site isn't built |
| Container | Reports healthy, runs as `shopsense`, and serves the site, a refreshed `/sellers`, and the API |
| Answers | Freight is 15.40 in the container, matching local runs |
| Browser | Overview and Forecasts load in Chrome from the container, with no console errors |
| Logging | Turned off during the check, so the prediction log is unchanged |

## Documentation added

- `README.md`: results, architecture, Docker, building, and checks.
- `docs/model_cards.md`: one card per problem.
- `docs/retraining.md`: how to retrain and re-test on new data.
- `docs/project_summary.md`: decisions, mistakes caught, and lessons.
- `docs/images/`: page screenshots from the browser tests.

## Known gaps

- **No public deployment,** for the reasons above.
- **The image isn't published,** so build it locally.
- **The Docker workflow wasn't tested on Linux or Windows,** only on an Apple silicon Mac.
- **Saved models are tied to the scikit-learn version.** They need the same version, which `uv.lock` pins.
