# JobSearch Dashboard

A lightweight job-scraping and dashboard application that:

- **Scrapes** job postings from Lever, Greenhouse, and Ashby using Google search (or direct ATS feeds).
- **Extracts** minimum years of experience and key technical skills via a Small LLM (Replicate).
- **Stores** each job in a Supabase table with upsert semantics (new entries only).
- **Serves** a REST API (`/api/jobs` and `/api/refresh`) via Flask.
- **Displays** results in a responsive, static front-end (Bulma or Bootstrap version).

## Table of Contents
1. [Features](#features)
2. [Prerequisites](#prerequisites)
3. [Project Structure](#project-structure)
4. [Installation](#installation)
5. [Setup](#setup)
6. [Running Locally](#running-locally)
7. [API Endpoints](#api-endpoints)
8. [Front-End](#front-end)
9. [Deployment](#deployment)
10. [Environment Variables](#environment-variables)
11. [Troubleshooting](#troubleshooting)

## Features
- **Multi-board scrape**: Lever, Greenhouse, and Ashby job boards.
- **Google‐based paging** (10 results per page) up to configurable `max_results`.
- **Lightweight LLM integration** (Replicate) to extract `"years"` and `"skills"`.
- **Supabase** as a Postgres-backed cloud database with upsert on `unique_id`.
- **Flask**-powered REST API, serving JSON to a static front end.
- **Responsive UI** using Bulma (or Bootstrap) to display job cards with tags.

## Prerequisites
- **Python 3.8+**
- **pip** (Python package installer)
- **Git** (to clone, optional)
- A **Supabase** project (free tier is sufficient)
- A **Replicate API token** (for the LLM extraction)

## Project Structure
```
JobSearch/
│
├── app.py
├── requirements.txt
├── README.md
├── .env                      ← environment variables (not committed)
│
├── static/
│   └── index.html            ← static front-end (Bulma or Bootstrap version)
│
├── utils/
│   └── engine.py             ← scraper + detail extractors + LLM + cleaner
│
└── .venv/                    ← (optional) Python virtualenv
```

- **app.py**
  - Flask application serving static files and API routes `/api/jobs` and `/api/refresh`.
- **requirements.txt**
  - Lists Python dependencies.
- **static/index.html**
  - Static front-end, calls the Flask API to fetch and refresh jobs.
- **utils/engine.py**
  - Core logic:
    - `find_jobs()`: Google-paged scraper (10 per page, up to `max_results`).
    - `get_{lever,greenhouse,ashby}_job_details()`: per-site HTML parsing.
    - `extract_requirements()`: calls Replicate LLM to return JSON `{ years, skills }`.
    - `handle_job_insert()`: checks for existing `unique_id`, runs LLM, upserts into Supabase.
    - `JobSearchResultCleaner`: prunes, dedupes, and reformats “apply” URLs.

## Installation
1. **Clone the repository** (if not already):
   ```bash
   git clone https://github.com/kevin0437/Job_search.git
   cd JobSearch
   ```
2. **Create and activate a virtual environment** (recommended):
   ```bash
   python -m venv .venv
   # macOS/Linux:
   source .venv/bin/activate
   # Windows PowerShell:
   .venv\Scripts\Activate.ps1
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Setup
1. **Create `.env`** in the project root with your credentials:
   ```ini
   SUPABASE_URL=https://<your-project>.supabase.co
   SUPABASE_KEY=<your-supabase-service-role-key>
   REPLICATE_API_TOKEN=<your-replicate-api-token>
   ```
   - `SUPABASE_URL` and `SUPABASE_KEY` come from your Supabase dashboard → Settings → API.
   - `REPLICATE_API_TOKEN` from https://replicate.com/account.

2. **Initialize your Supabase “jobs” table** (run this SQL in the Supabase SQL editor):
   ```sql
   create table if not exists jobs (
     unique_id   text primary key,
     company     text not null,
     job_title   text not null,
     image       text,
     description text,
     location    text,
     years       integer default 0,
     skills      jsonb default '[]',
     job_url     text not null,
     job_board   text not null,
     scraped_at  timestamptz default now()
   );
   ```

## Running Locally
1. **Activate your virtual environment** (if not already):
   ```bash
   source .venv/bin/activate   # macOS/Linux
   # or:
   .venv\Scripts\Activate.ps1  # Windows PowerShell
   ```
2. **Start the Flask server**:
   ```bash
   python app.py
   ```
   - The app will listen on **`http://localhost:5000/`** by default.
3. **Visit the front-end** in your browser:
   ```
   http://localhost:5000/
   ```
   You should see the job dashboard. Initially, it may be empty. Click **Refresh Jobs** to trigger a scrape.


---
**Enjoy using JobSearch Dashboard!** If you run into issues or want to propose enhancements, please open an issue or submit a pull request.

Part of the Code comes from this github repo: https://github.com/MochiDay
