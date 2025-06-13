# app.py
import os
import logging
from flask import Flask, jsonify, request
from dotenv import load_dotenv
from supabase import create_client
from utils.engine import find_jobs, handle_job_insert, JobSite, TBS


# ─── Load configuration and initialize clients ───────────────────
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY in environment")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configure logging
logging.basicConfig(level=logging.INFO)

# ─── Flask + static setup ────────────────────────────────────────
app = Flask(
    __name__,
    static_folder="static",   
    static_url_path=""        
)


@app.route("/")
def index():
    # return static/index.html
    return app.send_static_file("index.html")

# Default search parameters
DEFAULT_QUERY = """(software OR SWE OR SDE OR "back end" OR systems OR programmer OR coder
     OR "machine learning" OR ML OR "data science" OR "data engineer" OR "data" OR quantitative OR quant OR "full stack") (engineer OR developer OR analyst OR scientist OR researcher)"""
DEFAULT_TBS = TBS.PAST_DAY
DEFAULT_MAX = 100

# ─── API Endpoints ──────────────────────────────────────────────
@app.route("/api/jobs", methods=["GET"])
def api_jobs():
    """
    Return the most recent jobs from the database as JSON.
    """
    try:
        resp = (
            supabase
            .from_("jobs")
            .select("*")
            .order("years", desc=False)
            .limit(100)
            .execute()
        )
        return jsonify(resp.data)
    except Exception as e:
        logging.exception("Exception in api_jobs")
        return jsonify({"error": str(e)}), 500

@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    """
    Trigger scraping of new jobs and upsert into the database.
    Optional JSON payload: {"query": str, "tbs": "PAST_DAY", "max": int}
    """
    try:
        payload = request.get_json(silent=True) or {}
        query = payload.get("query", DEFAULT_QUERY)
        tbs = TBS[payload.get("tbs", DEFAULT_TBS.name)]
        max_results = int(payload.get("max", DEFAULT_MAX))
        
        # Perform the search
        boards = [JobSite.LEVER, JobSite.GREENHOUSE, JobSite.ASHBY]
        urls_by_board = find_jobs(query, boards, tbs, max_results)
        
        
        # Upsert results
        total = 0
        for site, urls in urls_by_board.items():
            logging.info("Refreshing %d jobs from %s", len(urls), site.name)
            handle_job_insert(supabase, urls, site)
            total += len(urls)

        return jsonify({"status": "ok", "refreshed": total})
    except Exception as e:
        logging.exception("Exception in api_refresh")
        return jsonify({"error": str(e)}), 500

# ─── Application entrypoint ─────────────────────────────────────
if __name__ == "__main__":
    # Listen on all interfaces, default port 5000
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
