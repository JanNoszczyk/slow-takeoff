# wealtharc-turbo-er/wa/ingest/epo.py

import asyncio
import httpx
import pandas as pd
from datetime import datetime, timezone, timedelta
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed
import duckdb
import json
import base64
from typing import Optional, Any, Dict, List
import xml.etree.ElementTree as ET # Import ElementTree for XML parsing

from ..config import EPO_OPS_KEY, EPO_OPS_SECRET # Import specific variables
from ..db import get_db_connection, EPO_PATENTS_TABLE # Import the constant

# EPO OPS API Details
EPO_AUTH_URL = "https://ops.epo.org/3.2/auth/accesstoken"
EPO_API_BASE_URL = "https://ops.epo.org/3.2/rest-services/" # Published data endpoint

# Credentials
CONSUMER_KEY = EPO_OPS_KEY # Use imported variable
CONSUMER_SECRET = EPO_OPS_SECRET # Use imported variable

# Global variable to cache the access token
_epo_access_token: Optional[str] = None
_epo_token_expires_at: Optional[datetime] = None

# Define table names
RAW_EPO_TABLE = "raw_epo"
# EPO_PATENTS_TABLE = "epo_patents" # Now imported

# --- Authentication ---

async def get_epo_access_token() -> Optional[str]:
    """Retrieves or refreshes the EPO OPS access token."""
    global _epo_access_token, _epo_token_expires_at
    now = datetime.now(timezone.utc)
    if _epo_access_token and _epo_token_expires_at and now < _epo_token_expires_at - timedelta(minutes=5):
        return _epo_access_token

    if not CONSUMER_KEY or not CONSUMER_SECRET:
        logger.error("EPO_OPS_KEY and/or EPO_OPS_SECRET are not configured.")
        raise ValueError("EPO OPS credentials not configured.")

    logger.info("Requesting new EPO OPS access token...")
    auth_header = base64.b64encode(f"{CONSUMER_KEY}:{CONSUMER_SECRET}".encode()).decode()
    headers = {"Authorization": f"Basic {auth_header}", "Content-Type": "application/x-www-form-urlencoded"}
    payload = {"grant_type": "client_credentials"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(EPO_AUTH_URL, headers=headers, data=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            _epo_access_token = data.get("access_token")
            expires_in = int(data.get("expires_in", 0))
            _epo_token_expires_at = now + timedelta(seconds=expires_in)
            logger.success(f"Obtained new EPO access token, expires in {expires_in}s.")
            return _epo_access_token
        except httpx.HTTPStatusError as e: logger.error(f"HTTP error getting EPO token: {e.response.status_code} - {e.response.text}"); return None
        except Exception as e: logger.error(f"Unexpected error getting EPO token: {e}"); return None

# --- API Client Setup ---

async def make_epo_request(endpoint: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> Optional[Any]:
    """Makes an authenticated request to the EPO OPS API."""
    try:
        token = await get_epo_access_token()
        if not token: return None
    except ValueError as e: # Catch credential config error
         logger.error(f"Cannot make EPO request: {e}")
         return None

    url = f"{EPO_API_BASE_URL}{endpoint.lstrip('/')}"
    request_headers = headers or {}; request_headers["Authorization"] = f"Bearer {token}"
    request_headers["Accept"] = "application/json, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.7" # Prefer JSON, accept XML

    async with httpx.AsyncClient() as client:
        try:
            logger.debug(f"Making EPO request to {url} with params: {params}")
            response = await client.get(url, params=params, headers=request_headers, timeout=60.0)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "application/json" in content_type:
                try: return response.json()
                except json.JSONDecodeError: logger.warning(f"EPO gave JSON type but failed parse {url}. Fallback text."); return response.text
            elif "xml" in content_type: logger.debug(f"EPO returned XML for {url}."); return response.text
            else: logger.warning(f"Unexpected content type '{content_type}' from EPO {url}."); return response.text
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error EPO {url}: {e.response.status_code} - {e.request.url}")
            if e.response.status_code == 401: logger.warning("EPO 401, force token refresh next time."); global _epo_access_token; _epo_access_token = None
            return None
        except Exception as e: logger.error(f"Unexpected error EPO {url}: {e}"); return None

# --- API Fetching Functions ---

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
async def search_epo_published_data(applicant_name: str, start_range: int = 1, end_range: int = 20) -> list[dict]:
    """Searches EPO published data by applicant name."""
    logger.info(f"Searching EPO published data for applicant: '{applicant_name}'")
    cql_query = f'pa="{applicant_name}"'; endpoint = "published-data/search"
    params = {"q": cql_query, "Range": f"{start_range}-{end_range}"}
    data = await make_epo_request(endpoint, params=params)
    if not data: logger.warning(f"No data received from EPO search for '{applicant_name}'."); return []

    patents: List[Dict[str, Any]] = []
    try:
        if isinstance(data, dict): # JSON parsing
            logger.debug("Parsing EPO JSON response.")
            biblio_search = data.get('ops:world-patent-data', {}).get('ops:biblio-search', {})
            total_results = int(biblio_search.get('@total-result-count', 0))
            logger.info(f"EPO Search: Found {total_results} total results for '{applicant_name}'. Processing {start_range}-{end_range}.")
            publication_refs = biblio_search.get('ops:search-result', {}).get('ops:publication-reference', [])
            if isinstance(publication_refs, dict): publication_refs = [publication_refs]
            for ref in publication_refs:
                doc_ids = ref.get('document-id', []);
                if isinstance(doc_ids, dict): doc_ids = [doc_ids]
                pub_num, pub_date, title = None, None, "N/A"
                for doc_id in doc_ids:
                    if doc_id.get('@document-id-type') == 'epodoc':
                        pub_num = doc_id.get('doc-number', {}).get('#text'); pub_date = doc_id.get('date', {}).get('#text'); break
                if pub_num: patents.append({"publication_number": pub_num, "title": title, "applicant": applicant_name, "publication_date": pub_date})
        elif isinstance(data, str): # XML parsing
            logger.debug("Parsing EPO XML response.")
            root = ET.fromstring(data)
            ns = {'ops': 'http://ops.epo.org'}
            for ref in root.findall('.//ops:publication-reference', ns):
                pub_num_elem = ref.find('.//ops:document-id[@document-id-type="epodoc"]/ops:doc-number', ns)
                pub_date_elem = ref.find('.//ops:document-id[@document-id-type="epodoc"]/ops:date', ns)
                pub_num = pub_num_elem.text if pub_num_elem is not None else None
                pub_date = pub_date_elem.text if pub_date_elem is not None else None
                if pub_num: patents.append({"publication_number": pub_num, "title": "N/A", "applicant": applicant_name, "publication_date": pub_date})
        logger.success(f"Parsed {len(patents)} patent references for '{applicant_name}'.")
        return patents
    except ET.ParseError as e: logger.error(f"Failed to parse XML from EPO: {e}"); return []
    except Exception as e: logger.error(f"Error parsing EPO response for '{applicant_name}': {e}"); return []

# --- Database Storage Functions ---

async def store_epo_patent_data(patents_metadata: list[dict], db_path: str | None = None):
    """Stores cleaned EPO patent metadata."""
    if not patents_metadata: return
    logger.info(f"Storing metadata for {len(patents_metadata)} EPO patents...")
    fetched_at = datetime.now(timezone.utc)
    records_to_insert = []
    for patent in patents_metadata:
        pub_date = pd.to_datetime(patent.get('publication_date'), errors='coerce').date()
        record = (patent.get("publication_number"), patent.get("title"), patent.get("applicant"), pub_date, fetched_at)
        if record[0]: records_to_insert.append(record)
        else: logger.warning(f"Skipping EPO record due to missing publication number: {patent}")

    if not records_to_insert: logger.info("No valid EPO records to store."); return

    try:
        def db_operations_in_thread(path: str | None, data: list):
            conn = None
            try:
                conn = get_db_connection(path)
                conn.executemany(
                    f"""
                    INSERT INTO {EPO_PATENTS_TABLE} (publication_number, title, applicant, publication_date, fetched_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(publication_number) DO UPDATE SET
                        title=excluded.title, applicant=excluded.applicant,
                        publication_date=excluded.publication_date, fetched_at=excluded.fetched_at;
                    """, data
                )
                logger.success(f"Thread stored/updated metadata for {len(data)} EPO patents.")
            except Exception as thread_e: logger.error(f"Error in thread storing EPO patent metadata: {thread_e}"); raise
            finally:
                if conn: conn.close(); logger.debug("Thread closed EPO patent data DB connection.")
        await asyncio.to_thread(db_operations_in_thread, db_path, records_to_insert)
    except Exception as e: logger.error(f"Error storing EPO patent metadata: {e}"); raise


# --- Main Ingestion Function ---

async def ingest_epo_patents(applicant_name: str, limit: int = 20, db_path: str | None = None):
    """Searches for and stores EPO patent metadata for an applicant."""
    if not CONSUMER_KEY or not CONSUMER_SECRET:
        logger.error("Cannot ingest EPO data: Credentials not set.")
        return

    logger.info(f"Starting EPO patent ingestion for applicant: {applicant_name}")
    try:
        start, end = 1, min(limit, 100)
        patents_data = await search_epo_published_data(applicant_name, start_range=start, end_range=end)
        if patents_data:
            try:
                await store_epo_patent_data(patents_data, db_path=db_path)
            except Exception as store_e:
                 logger.error(f"Failed to store EPO patent data: {store_e}", exc_info=True)
        else:
            logger.info(f"No patents found or processed for applicant '{applicant_name}'.")
    except ValueError as ve: logger.error(f"Configuration error: {ve}"); raise
    except Exception as e: logger.exception(f"Error during EPO ingestion pipeline for {applicant_name}: {e}"); raise


# Example Usage
async def main():
    test_applicant = "Siemens Aktiengesellschaft"
    test_db_path = "test_epo.db"
    conn = None
    try:
        conn = get_db_connection(test_db_path)
        from .. import db
        db.create_schema(conn); conn.close(); conn = None
        await ingest_epo_patents(test_applicant, limit=10, db_path=test_db_path)
    except Exception as e: logger.exception(f"EPO example failed: {e}")
    finally:
        if conn: conn.close()
        import os
        if os.path.exists(test_db_path): os.remove(test_db_path); logger.info(f"Cleaned up {test_db_path}")

if __name__ == "__main__":
    if not CONSUMER_KEY or not CONSUMER_SECRET:
        print("Please set EPO_OPS_KEY and EPO_OPS_SECRET environment variables.")
    else:
        asyncio.run(main())
