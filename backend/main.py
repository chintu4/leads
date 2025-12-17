# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any
from fastapi.middleware.cors import CORSMiddleware
import os
import sys
import dotenv
dotenv.load_dotenv()


# Ensure the 'backend' folder is on sys.path so `src` is importable when running this file directly
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# Initialize logging early so other modules pick it up
from src import logging_config  # sets up file + console logging and stdout/stderr capture

import logging
import uvicorn
from src.handlers import handle
from src.handlers import google_export
from src.handlers import auth_google

app = FastAPI()

# Allow frontend dev server (port 3000) to access the API in development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# include routers from handlers
app.include_router(google_export.router)
app.include_router(auth_google.router)


@app.get("/")
async def root():
    return {"status": "ok"}

class ScrapeRequest(BaseModel):
    input: str

class ProcessRequest(BaseModel):
    # Accept any payload for flexibility in tests and clients
    response: Optional[Any] = None
    ok: Optional[str] = ""
    wow: Optional[str] = ""

@app.post("/scrape")
async def scrape(req: ScrapeRequest):
    # pass the incoming query string to the handler
    return handle.scrape(req.input)
    

from fastapi.responses import StreamingResponse
import json
import asyncio
import threading

@app.get("/scrape/stream")
async def scrape_stream(input: str, max_results: int = 200, domains: str = "pubmed,linkedin"):
    """SSE endpoint that streams progress events while scraping."""
    # Parse domains
    if domains.lower() == "all":
        allowed_sources = None
    else:
        domain_map = {
            "pubmed": "https://pubmed.ncbi.nlm.nih.gov/",
            "linkedin": "https://linkedin.com/"
        }
        allowed_sources = []
        for d in domains.split(","):
            d = d.strip().lower()
            if d in domain_map:
                allowed_sources.append(domain_map[d])
            else:
                # For custom domains, just use the domain name as-is
                allowed_sources.append(d)
    async def event_generator():
        q: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def progress_cb(event: dict):
            # log event for diagnostics and push events to the asyncio queue from worker thread
            logging.info("sse: enqueue event: %s", event)
            try:
                asyncio.run_coroutine_threadsafe(q.put(event), loop)
            except Exception:
                logging.exception("sse: failed to enqueue event")

        def worker():
            logging.info("sse: worker started for input=%s", input)
            try:
                handle.scrape_progress(input, max_results=max_results, allowed_sources=allowed_sources, progress_callback=progress_cb)
            except Exception as e:
                logging.exception("sse: worker error for input=%s: %s", input, e)
                asyncio.run_coroutine_threadsafe(q.put({"type": "error", "msg": str(e)}), loop)
                asyncio.run_coroutine_threadsafe(q.put({"type": "done", "percent": 100, "results": []}), loop)

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        while True:
            event = await q.get()
            logging.info("sse: yielding event: %s", event)
            # Send as SSE 'data:' lines
            yield f"data: {json.dumps(event)}\n\n"
            # Only terminate the SSE stream when the worker signals completion.
            # Per-URL errors are non-fatal and should not close the connection so
            # clients can still receive further progress and the final results.
            if event.get("type") == "done":
                break

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/debug/sse-test")
async def sse_test():
    """Simple SSE test endpoint that emits periodic progress messages (0-100).

    Use this to verify SSE is received by the browser independently of the scraper.
    """
    async def gen():
        import time
        import json
        for p in range(0, 101, 10):
            yield f"data: {json.dumps({'type': 'progress', 'percent': p})}\n\n"
            # small sleep so the client can observe intermediate values
            await asyncio.sleep(0.5)
        yield f"data: {json.dumps({'type': 'done', 'percent': 100, 'results': []})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")

@app.post("/process")
async def process(req: ProcessRequest):
    # Forward structured scraped response to handler.process
    return handle.process(req.response)

if __name__ == "__main__":
    # Allow development reload to be controlled via environment variable (DEV_RELOAD)
    reload_flag = os.getenv("DEV_RELOAD", "false").lower() in ("1", "true", "yes")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=reload_flag)

