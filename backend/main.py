# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any
from fastapi.middleware.cors import CORSMiddleware
import os
import sys

# Ensure the 'backend' folder is on sys.path so `src` is importable when running this file directly
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

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
    

@app.post("/process")
async def process(req: ProcessRequest):
    # Forward structured scraped response to handler.process
    return handle.process(req.response)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

