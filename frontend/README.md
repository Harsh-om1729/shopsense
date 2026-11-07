# ShopSense frontend

React, Vite, and TypeScript. Every number on the site comes from the ShopSense API.

```bash
npm install
npm run dev        # http://localhost:5173, with the API on port 8000
npm run typecheck
npm run lint
npm test
npm run build
npm run e2e        # browser tests, starting the API on 8011 and the site on 5174
```

- **API address:** set `SHOPSENSE_API_URL` if the API runs on another port. Dev requests to `/api` are forwarded there.
- **Deployed site:** set `VITE_API_BASE` to the API's address when building.
- **Types:** `src/api/schema.d.ts` is generated from `openapi.json`. After changing the API, run `uv run python -m api.export_openapi` from the project root, then `npm run generate:api`.

See `docs/phase_11_frontend.md` for design decisions.
