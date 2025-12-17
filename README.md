# Lead Finder

Lead Finder — a lightweight **web scraper** for discovering potential leads (researchers, professionals, and organizations). Fast, configurable, and designed for streaming results to a web frontend.

## How It Works

How it works — at a glance:

1. 🔍 **Querying search engines** (DuckDuckGo via the `ddgs` library) to discover candidate pages
2. 🕷️ **Crawling internal links** to extract lead details and scraping via Scrapy and Playwright
3. 🌐 **Serving a frontend** built with React + TypeScript and a backend powered by FastAPI

## Project Overview

Lead Finder is a **lead-finding application** that searches for potential leads (researchers, professionals, and organizations) across academic and professional platforms. It has two main components: a backend service for scraping and processing, and a frontend UI for interacting with results.

### Backend — FastAPI (Server) 🔧
- **Purpose**: Handles web scraping, crawling, and lead processing
- **Key Features**:
  - Searches DuckDuckGo for initial results
  - Optional Scrapy crawling for one-off page extraction
  - Optional deep Playwright crawling for in-depth site exploration (e.g., LinkedIn, ResearchGate)
  - Lead enrichment and processing
  - Server-Sent Events (SSE) for real-time progress streaming
  - Google Sheets export integration
  - OAuth authentication for Google services

### Frontend — React + TypeScript (Client) 🎯
- **Purpose**: User interface for searching, displaying results, and managing leads
- **Key Features**:
  - Real-time progress updates via SSE
  - Results table with filtering
  - CSV and Google Sheets export
  - Settings for search domains and result limits
  - Responsive design

## Architecture

### Data Flow
1. 👤 User enters a search query in the frontend
2. 🔍 Backend performs DuckDuckGo search to get initial URLs
3. 🕷️ Optional crawling phases: Scrapy for quick extraction, Playwright for deep crawling
4. ⚙️ Leads are processed and enriched with contact information
5. 📊 Results are streamed back to frontend via SSE
6. 📤 Users can export results to CSV or Google Sheets

### Key Technologies
- **Backend**: Python, FastAPI, Scrapy, Playwright, DuckDuckGo
- **Frontend**: React, TypeScript, CSS
- **Deployment**: Render (backend); Vercel / Netlify (frontend)

## Key Files & Responsibilities

### Backend
- `main.py`: FastAPI app with SSE `/scrape/stream`, `/scrape`, and `/process` endpoints
- `src/handlers/handle.py`: Core orchestration for scraping and processing
- `src/utils/duck.py`: DuckDuckGo search integration
- `src/utils/scrapy_ok.py`: Scrapy spider for page extraction
- `src/utils/playwright_deep.py`: Deep site crawling with Playwright
- `src/utils/profile.py`: Heuristics for detecting profile-like URLs
- `src/handlers/auth_google.py` & `google_export.py`: Google OAuth and Sheets export

### Frontend
- `src/LeadFinder.tsx`: Main component with SSE client and UI state
- `src/components/ResultsTable.tsx`: Results display and processing triggers
- `src/components/SearchBar.tsx`: Search input and action buttons
- `src/components/ProgressBar.tsx`: Progress visualization

## Development Setup

### Backend
```bash
cd backend
pip install -r requirements.txt
python -m main  # Runs on port 8000
```

### Frontend
```bash
cd frontend
npm install  # or bun install
npm run dev  # Runs on port 3000, expects backend on 8000
```

### Testing
```bash
pytest  # From repo root, runs backend and frontend tests
```

## Configuration

### Environment Variables
- `USE_PLAYWRIGHT_DEEP`: Enable/disable deep crawling
- `ALLOW_LINKEDIN_DEEP`: Allow LinkedIn deep crawling
- `CRAWL_TIMEOUT`: Timeout for crawling operations
- `DEEP_TIMEOUT_S`: Timeout for deep crawling
- `DEEP_MAX_PAGES`: Maximum pages to crawl deeply

### Search Domains
- 🧾 `pubmed` — Academic publications
- 💼 `linkedin` — Professional profiles
- ➕ Custom domains can be added via settings

## Security & Best Practices

- Playwright is lazy-loaded to avoid import-time failures and reduce startup friction
- Defensive error handling is used for all external dependencies and network operations
- Server-side heuristics prioritize profile-like URLs to improve result quality
- Google Sheets export uses OAuth for secure access
- The crawler avoids sites that explicitly block automation by default

## Deployment

- The backend is deployed to Render: `https://leads-59wq.onrender.com`
- The frontend can be deployed to Vercel, Netlify, or similar platforms
- Ensure CORS and environment variables are configured appropriately for production

