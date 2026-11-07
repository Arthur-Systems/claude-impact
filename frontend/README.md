# ClearPath frontend

A one-page Irvine ADU permit dashboard built with Next.js and React. It brings together document readiness, approval estimates, a journey stepper, path comparison, a MapLibre map, Navigator chat, search and Ask the City. The splash and dashboard share the forest, teal and paper palette defined in `app/globals.css`.

## Run locally

Use Node.js 18.17 or newer. From `frontend/`:

```sh
npm ci
npm run dev
```

Open http://localhost:3000. For a production build, stop the dev server before using the same build directory:

```sh
npm run build
npm run start
```

Both `predev` and `prebuild` run `scripts/copy-map-worker.mjs`. It copies the installed MapLibre module worker, source map and license into the generated, git-ignored `public/maplibre/` directory. The browser loads this local worker without a CDN request or Next.js minification.

## Demo behavior and sources

- Document selection records filenames in memory and guesses checklist matches from those names. It does not upload file contents or perform OCR. Matches can be reassigned; readiness and estimates update together.
- Project state, selected address and question tracking are in memory and reset on reload. There is no production persistence.
- Search uses local entries in `lib/knowledge.ts`, displays their sources and also searches selected filenames. It is not a live regulatory search.
- Approval totals are estimates. The chart labels the completeness-check assumption separately from the decision legal limit; use the linked sources to check requirements.
- Navigator falls back to demo answers when no API is configured or a request fails. These replies visibly say “Demo answer, backend not connected.” All replies remind users to check sources.
- Ask the City opens a draft through `mailto:` and tracks the email-opening action locally. It does not send email or confirm delivery. Replies go to the user's inbox.

## Optional Navigator API

Set `NEXT_PUBLIC_API_URL` in `.env.local` before starting dev or building. Navigator sends `POST {NEXT_PUBLIC_API_URL}/api/navigator` with `{ question, context }` and expects `{ answer, sources: [{ label, url }] }`. This is an optional integration contract, not evidence of a connected backend.

## Map and navigation

MapLibre renders the map using WebGL. OpenFreeMap styles and tiles and OpenStreetMap Nominatim address lookup require network access; the worker is served locally. Failed map loading shows a location fallback with a Google Maps link, and failed address lookup shows an error.

The dashboard retains reduced-motion handling, keyboard focus styles and accessible control labels. Old routes redirect to the dashboard: `/documents`, `/navigator` and `/timeline` target their sections; `/search` and `/questions` return to `/`.
