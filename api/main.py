"""Telos API.

Stage 1 of the React migration. Every endpoint is a thin wrapper over an
existing core/ function: database access, quota accounting, the spend ceiling,
prompt fencing and output validation are not reimplemented here, because
reimplementing them would re-open every security property they hold.

Run:  uvicorn api.main:app --host 127.0.0.1 --port 8000
Caddy serves the built React files and proxies /api/* to this process.
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from api.routers import account, auth, billing, guide, jobs, match, profile

log = logging.getLogger("telos.api")

@asynccontextmanager
async def lifespan(_: FastAPI):
    from core.database import init_db
    init_db()
    log.info("telos api ready (env=%s)", os.getenv("TELOS_ENV", "dev"))
    yield


app = FastAPI(title="Telos API", version="1.0", docs_url=None, redoc_url=None,
              lifespan=lifespan)

for r in (auth.router, account.router, jobs.router, profile.router,
          match.router, guide.router, billing.router):
    app.include_router(r)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    """Last line of defence. An unexpected failure must not put a traceback,
    a connection string or an API key in front of a user."""
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our side. Try again in a moment."})


@app.get("/api/health")
def health():
    """Liveness only. Deliberately says nothing about the database or the
    model provider, because an unauthenticated endpoint is not the place to
    report which dependencies exist or how they are configured."""
    return {"ok": True}
