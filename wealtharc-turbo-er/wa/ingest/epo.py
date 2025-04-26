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

# Global variable to cache the access token (simple approach)
# A more robust solution might use a class or persistent storage
_epo_access_token: Optional[str] = None
_epo_token_expires_at: Optional[datetime] = None

# Define table names (now imported)
RAW_EPO_TABLE = "raw_epo" # For raw JSON/XML payload
# EPO_PATENTS_TABLE = "epo_patents" # Now imported

# --- Authentication ---

async def get_epo_access_token() -> Optional[str]:
    """Retrieves or refreshes the EPO OPS access token."""
    global _epo_access_token, _epo_token_expires_at

    now = datetime.now(timezone.utc)
    if _epo_access_token and _epo_token_expires_at and now < _epo_token_expires_at - timedelta(minutes=5):
        logger.debug("Using cached EPO access token.")
        return _epo_access_token

    if not CONSUMER_KEY or not CONSUMER_SECRET:
        logger.error("EPO_OPS_KEY and/or EPO_OPS_SECRET are not configured.")
        raise ValueError("EPO OPS credentials not configured.")

    logger.info("Requesting new EPO OPS access token...")
    auth_header = base64.b64encode(f"{CONSUMER_KEY}:{CONSUMER_SECRET}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_header}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
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
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error getting EPO token: {e.response.status_code} - {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting EPO token: {e}")
            return None

# --- API Client Setup ---

async def make_epo_request(endpoint: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> Optional[Any]:
    """Makes an authenticated request to the EPO OPS API."""
    token = await get_epo_access_token()
    if not token:
        return None

    url = f"{EPO_API_BASE_URL}{endpoint.lstrip('/')}"
    request_headers = headers or {}
    request_headers["Authorization"] = f"Bearer {token}"
    # OPS often returns XML, explicitly ask for JSON if possible/supported
    request_headers["Accept"] = "application/json"

    async with httpx.AsyncClient() as client:
        try:
            logger.debug(f"Making EPO request to {url} with params: {params}")
            response = await client.get(url, params=params, headers=request_headers, timeout=60.0)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower()
            if "application/json" in content_type:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    logger.warning(f"EPO returned content-type json but failed to parse for {url}. Falling back to text.")
                    return response.text # Return raw text if JSON parsing fails
            elif "application/xml" in content_type or "text/xml" in content_type:
                logger.info(f"EPO returned XML for {url}. Returning raw text for parsing.")
                return response.text # Return raw XML text
            else:
                 logger.warning(f"Unexpected content type '{content_type}' from EPO {url}. Returning raw text.")
                 return response.text # Return raw text for unknown types

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching EPO data {url}: {e.response.status_code} - {e.request.url}")
            if e.response.status_code == 401: # Unauthorized - possibly expired token
                 logger.warning("EPO request unauthorized (401), attempting token refresh on next call.")
                 global _epo_access_token, _epo_token_expires_at
                 _epo_access_token = None # Force refresh next time
            # Handle 404, 429 (Rate Limit) etc.
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching EPO data {url}: {e}")
            return None

# --- API Fetching Functions ---

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
async def search_epo_published_data(applicant_name: str, start_range: int = 1, end_range: int = 20) -> Optional[list[dict]]:
    """
    Searches EPO published data by applicant name (Placeholder).
    Uses the OPS Published Data Search V1.1 endpoint.
    NOTE: Requires careful construction of the CQL query.

    Args:
        applicant_name: Name of the applicant (company).
        start_range: Start index for results (min 1).
        end_range: End index for results (max start_range + 99).

    Returns:
        A list of patent publication references or None.
    """
    logger.info(f"Searching EPO published data for applicant: '{applicant_name}'")
    # Construct CQL query (needs care based on exact field names in EPO docs)
    # Example: Search for applicant name 'pa' field
    cql_query = f'pa="{applicant_name}"'
    endpoint = "published-data/search"
    params = {"q": cql_query, "Range": f"{start_range}-{end_range}"}

    # This endpoint often returns XML, handling might be basic
    data = await make_epo_request(endpoint, params=params)

    if data:
         # --- TODO: Parse the actual response ---
         # The structure depends heavily on whether JSON or XML is returned
         # and the specifics of the OPS Published Data Search schema.
         # This is a placeholder assuming a JSON list under a specific key.
         logger.warning("EPO search response parsing is a placeholder. Needs implementation based on actual API response structure.")
         # Example hypothetical parsing:
         # biblio_search = data.get('ops:world-patent-data', {}).get('ops:biblio-search', {})
         # results = biblio_search.get('ops:search-result', {}).get('ops:publication-reference', [])
         # if isinstance(results, dict): # If only one result
         #      results = [results]
         # logger.success(f"Mock parsing found {len(results)} results for {applicant_name}")
         # return results # Return the list of publication references
         return [{"mock_publication_ref": f"EP{i+1000000}A1"} for i in range(min(5, end_range - start_range + 1))] # Return mock data
    else:
        data = await make_epo_request(endpoint, params=params)

    if not data:
        logger.warning(f"No data received from EPO for applicant '{applicant_name}'.")
        return []

    patents: List[Dict[str, Any]] = []

    try:
        # Attempt to parse based on data type (JSON dict or XML string)
        if isinstance(data, dict): # Assume JSON response
            logger.debug("Attempting to parse EPO response as JSON.")
            # Navigate the potential nested structure (adjust based on actual response)
            biblio_search = data.get('ops:world-patent-data', {}).get('ops:biblio-search', {})
            total_results = int(biblio_search.get('@total-result-count', 0))
            logger.info(f"EPO Search: Found {total_results} total results for '{applicant_name}'. Processing {start_range}-{end_range}.")

            search_results = biblio_search.get('ops:search-result', {})
            publication_refs = search_results.get('ops:publication-reference', [])
            if isinstance(publication_refs, dict): # Handle single result case
                publication_refs = [publication_refs]

            for ref in publication_refs:
                doc_ids = ref.get('document-id', [])
                if isinstance(doc_ids, dict): doc_ids = [doc_ids]

                pub_num, pub_date = None, None
                for doc_id in doc_ids:
                    if doc_id.get('@document-id-type') == 'epodoc':
                        pub_num = doc_id.get('doc-number', {}).get('#text')
                        pub_date = doc_id.get('date', {}).get('#text')
                        break # Found the primary ID

                # Fetching title/applicant might require another API call using the pub_num
                # For simplicity here, we'll extract if available directly, otherwise leave None
                # This part is highly dependent on the actual verbosity of the search result
                title = ref.get('title', 'N/A') # Placeholder - title unlikely in search result ref
                applicant = applicant_name # Assume applicant name matches query for now

                if pub_num:
                    patents.append({
                        "publication_number": pub_num,
                        "title": title,
                        "applicant": applicant,
                        "publication_date": pub_date,
                    })

        elif isinstance(data, str): # Assume XML response
            logger.debug("Attempting to parse EPO response as XML.")
            root = ET.fromstring(data)
            # Define namespaces used by EPO OPS XML (adjust if necessary)
            ns = {
                'ops': 'http://ops.epo.org',
                'xlink': 'http://www.w3.org/1999/xlink',
                # Add other namespaces as found in the XML
            }
            # Find publication references using XPath
            # Example XPath - adjust based on actual XML structure!
            # Example: Find within //ops:biblio-search/ops:search-result/ops:publication-reference
            for ref in root.findall('.//ops:publication-reference', ns):
                pub_num_elem = ref.find('.//ops:document-id[@document-id-type="epodoc"]/ops:doc-number', ns)
                pub_date_elem = ref.find('.//ops:document-id[@document-id-type="epodoc"]/ops:date', ns)

                pub_num = pub_num_elem.text if pub_num_elem is not None else None
                pub_date = pub_date_elem.text if pub_date_elem is not None else None

                # Title/applicant might be elsewhere or need another query
                title = "N/A" # Placeholder
                applicant = applicant_name # Placeholder

                if pub_num:
                    patents.append({
                        "publication_number": pub_num,
                        "title": title,
                        "applicant": applicant,
                        "publication_date": pub_date,
                    })

        logger.success(f"Successfully parsed {len(patents)} patent references for '{applicant_name}'.")
        return patents

    except ET.ParseError as e:
        logger.error(f"Failed to parse XML response from EPO: {e}")
        return []
    except Exception as e:
        logger.error(f"Error parsing EPO response for '{applicant_name}': {e}")
        return []


# --- Database Storage Functions ---

async def store_epo_patent_data(patents_metadata: list[dict], con: duckdb.DuckDBPyConnection):
    """Stores cleaned EPO patent metadata (Placeholder)."""
    if not patents_metadata: return

    logger.info(f"Storing metadata for {len(patents_metadata)} EPO patents (Placeholder)...")
    fetched_at = datetime.now(timezone.utc)
    records_to_insert = []

    for patent in patents_metadata:
        # Parse date safely
        publication_date = pd.to_datetime(patent.get('publication_date'), errors='coerce').date()

        record = (
            patent.get("publication_number"),
            patent.get("title"),
            patent.get("applicant"),
            publication_date,
            fetched_at
        )
        # Basic validation: ensure publication_number exists
        if record[0]:
            records_to_insert.append(record)
        else:
            logger.warning(f"Skipping EPO record due to missing publication number: {patent}")

    try:
        con.executemany(
            f"""
            INSERT INTO {EPO_PATENTS_TABLE} (
                publication_number, title, applicant, publication_date, fetched_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(publication_number) DO UPDATE SET
                title = excluded.title,
                applicant = excluded.applicant,
                publication_date = excluded.publication_date,
                fetched_at = excluded.fetched_at;
            """,
            records_to_insert
        )
        logger.success(f"Successfully stored/updated metadata for {len(records_to_insert)} EPO patents.")
    except Exception as e:
        logger.error(f"Error storing EPO patent metadata: {e}")


# --- Main Ingestion Function ---

async def ingest_epo_patents(applicant_name: str, limit: int = 20, con: duckdb.DuckDBPyConnection | None = None):
    """Searches for and stores EPO patent metadata for an applicant."""
    if not CONSUMER_KEY or not CONSUMER_SECRET:
        logger.error("Cannot ingest EPO data: Credentials not set.")
        return

    logger.info(f"Starting EPO patent ingestion for applicant: {applicant_name}")
    conn_local = con or get_db_connection()

    try:
        # Calculate range for API call (max 100 per request)
        start = 1
        end = min(limit, 100) # Fetch up to 'limit' but max 100 per call
        patents_data = await search_epo_published_data(applicant_name, start_range=start, end_range=end)

        if patents_data:
            await store_epo_patent_data(patents_data, con=conn_local)
        else:
            logger.info(f"No patents found or processed for applicant '{applicant_name}'.")

    except ValueError as ve: # Catch config errors
        logger.error(f"Configuration error: {ve}")
    except Exception as e:
        logger.exception(f"Error during EPO ingestion pipeline for {applicant_name}: {e}")
    finally:
        if not con and conn_local:
            conn_local.close()


# Example Usage
async def main():
    test_applicant = "Siemens Aktiengesellschaft"
    conn = get_db_connection()
    try:
        from .. import db
        db.create_schema(conn) # Ensure schema exists
        await ingest_epo_patents(test_applicant, limit=10, con=conn)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if not CONSUMER_KEY or not CONSUMER_SECRET:
        print("Please set EPO_OPS_KEY and EPO_OPS_SECRET environment variables.")
    else:
        asyncio.run(main())
