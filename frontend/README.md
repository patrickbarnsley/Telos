# Telos frontend

Stage 2 of the React migration. Vite + React + TypeScript, talking to the
FastAPI service in `api/`.

    npm install
    npm run dev        # proxies /api to http://127.0.0.1:8000

Run the API alongside it:

    uvicorn api.main:app --host 127.0.0.1 --port 8000

## Dependencies, and why each one is here

Four runtime packages, deliberately. The prototype's CSS is the design system,
so there is no component framework.

- `react-router-dom`  routing
- `@tanstack/react-query`  server state, and the optimistic update the board needs
- `@dnd-kit/core`  the drag on the pipeline board

## The one place this departs from the prototype

`src/styles/tokens.css` carries every token verbatim except the semantic pair.
The prototype's green and red sit 1.13 apart in relative luminance, so an offer
and a rejection are the same brightness and become indistinguishable in
greyscale or to a viewer with red-green colour blindness. The replacements
separate by 1.58 and read more strongly against both surfaces than the
originals. Status chips also carry a distinct glyph, so the state survives with
no colour at all.

## Verified

Built clean, run against the real API and a real PostgreSQL. A card dragged from
Screening to Interview issued `PATCH /api/jobs/{id}` and the row changed in the
database. Optimistic update rolls back on failure.
