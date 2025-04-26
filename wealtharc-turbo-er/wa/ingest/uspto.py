# wealtharc-turbo-er/wa/ingest/uspto.py

import asyncio
import httpx
import pandas as pd
from datetime import datetime, timezone
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed
import duckdb
import json

# from ..config import settings # Unused import
from ..db import USPTO_PATENTS_TABLE, get_db_connection

# USPTO API Details
# Using the Patent Public Search API (PPUBS)
USPTO_PPUBS_API_URL = "https://ppubs.uspto.gov/api/v1/search/results"
# API_KEY = settings.USPTO_API_KEY # PPUBS Search API doesn't seem to require one currently

# Define table names (using constants from db.py now)
RAW_USPTO_TABLE = "raw_uspto" # For raw JSON payload
USPTO_PATENTS_TABLE = "uspto_patents"

# --- API Client Setup ---

async def make_uspto_ppubs_search_request(query_payload: dict) -> dict | None:
    """Makes a POST request to the USPTO PPUBS Search API."""
    url = USPTO_PPUBS_API_URL
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    # No API key seems needed for this specific API endpoint currently
    # if API_KEY:
    #     headers["X-API-Key"] = API_KEY # Example header name

    async with httpx.AsyncClient() as client:
        try:
            logger.debug(f"Making USPTO PPUBS search request to {url} with payload: {json.dumps(query_payload)}")
            response = await client.post(url, json=query_payload, headers=headers, timeout=120.0) # Longer timeout for search
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error searching USPTO PPUBS {url}: {e.response.status_code} - {e.request.url} - Response: {e.response.text}")
            # Handle specific errors like 400 (bad query), 429 (rate limit)
            return None
        except Exception as e:
            logger.error(f"Unexpected error searching USPTO PPUBS {url}: {e}")
            return None

# --- API Fetching Functions ---

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
async def search_uspto_patents(assignee_name: str, limit: int = 20) -> list[dict]:
    """
    Searches USPTO patents by assignee name (Placeholder implementation).

    Args:
        assignee_name: Name of the company/assignee.
        limit: Max number of results.

    Returns:
        A list of patent data dictionaries or an empty list.
    """
    logger.info(f"Searching USPTO patents for assignee: '{assignee_name}'")
    # Placeholder: This requires knowing the correct API endpoint and query parameters
    # Example using a hypothetical search endpoint:
    # params = {"assignee": assignee_name, "limit": limit, "sort": "date_desc"}
    # data = await make_uspto_request("search", params=params)

    # Removed Mock implementation block

    """
    Searches USPTO patents by assignee name using the PPUBS API.

    Args:
        assignee_name: Name of the company/assignee.
        limit: Max number of results.

    Returns:
        A list of patent data dictionaries or an empty list.
    """
    logger.info(f"Searching USPTO PPUBS for assignee: '{assignee_name}', limit: {limit}")

    query_payload = {
        "query": {
            "querySyntax": "proximity", # Or "standard" if preferred/needed
            "operator": "AND",
            "searchFields": [
                {
                    "field": "assigneeName", # Field for assignee name search
                    "values": [assignee_name]
                }
            ]
        },
        "start": 0,
        "rows": limit,
        "sort": "publicationDate desc" # Sort by publication date descending
        # Consider adding filters for patent type (e.g., utility) if needed
    }

    data = await make_uspto_ppubs_search_request(query_payload)

    if data and 'results' in data and 'patents' in data['results']:
        raw_patents = data['results']['patents']
        logger.success(f"Found {len(raw_patents)} patents for {assignee_name} via PPUBS API.")
        # Adapt the raw API response structure to the expected format
        processed_patents = []
        for p in raw_patents:
            # Extract relevant fields - adjust based on actual API response structure!
            # Example extraction - VERIFY FIELD NAMES FROM ACTUAL API RESPONSE
            patent_details = p.get('patent', {})
            application_details = p.get('patentApplication', {})

            processed_patents.append({
                "patentNumber": patent_details.get('patentNumber', application_details.get('patentNumber')), # Prefer patent number if available
                "patentTitle": patent_details.get('inventionTitle', {}).get('content', [''])[0],
                "filingDate": application_details.get('filingDate'),
                "grantDate": patent_details.get('grantDate'), # May be called publicationDate or similar
                "assigneeEntityName": patent_details.get('assigneeEntityName', {}).get('content', [assignee_name])[0], # Use original name if not found
                "abstract": patent_details.get('abstractText', {}).get('content', [''])[0],
                # Add other fields as needed/available, e.g., inventors, classifications
            })
        return processed_patents
    elif data and 'results' in data and not data['results'].get('patents'):
         logger.info(f"No patents found for assignee '{assignee_name}' via PPUBS API.")
         return []
    else:
        logger.warning(f"Failed to retrieve or parse patent data for assignee '{assignee_name}' from PPUBS API.")
        return []

# --- Database Storage Functions ---

async def store_uspto_patent_data(patents: list[dict], con: duckdb.DuckDBPyConnection):
    """Stores cleaned USPTO patent metadata."""
    if not patents: return

    logger.info(f"Storing metadata for {len(patents)} USPTO patents...")
    fetched_at = datetime.now(timezone.utc)
    records_to_insert = []

    for patent in patents:
        # Parse dates safely
        filing_date = pd.to_datetime(patent.get('filingDate'), errors='coerce').date()
        grant_date = pd.to_datetime(patent.get('grantDate'), errors='coerce').date()

        record = (
            patent.get('patentNumber'),
            patent.get('patentTitle'),
            patent.get('assigneeEntityName'),
            filing_date,
            grant_date,
            fetched_at,
            patent.get('abstract') # Add abstract if extracted
        )
        records_to_insert.append(record)

    try:
        con.executemany(
            f"""
            INSERT INTO {USPTO_PATENTS_TABLE} (
                patent_number, title, assignee, filing_date, grant_date, fetched_at, abstract
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(patent_number) DO UPDATE SET
                title = excluded.title,
                assignee = excluded.assignee,
                filing_date = excluded.filing_date,
                grant_date = excluded.grant_date,
                fetched_at = excluded.fetched_at,
                abstract = excluded.abstract;
            """,
            records_to_insert
        )
        logger.success(f"Successfully stored/updated metadata for {len(records_to_insert)} USPTO patents.")
    except Exception as e:
        logger.error(f"Error storing USPTO patent metadata: {e}")


# --- Main Ingestion Function ---

async def ingest_uspto_patents(assignee_name: str, limit: int = 20, con: duckdb.DuckDBPyConnection | None = None):
    """Searches for and stores USPTO patent metadata for an assignee."""
    logger.info(f"Starting USPTO patent ingestion for assignee: {assignee_name}")
    conn_local = con or get_db_connection()

    try:
        patents_data = await search_uspto_patents(assignee_name, limit=limit)

        if patents_data:
            await store_uspto_patent_data(patents_data, con=conn_local)
        else:
            logger.info(f"No patents found or processed for assignee '{assignee_name}'.")

    except Exception as e:
        logger.exception(f"Error during USPTO ingestion pipeline for {assignee_name}: {e}")
    finally:
        if not con and conn_local:
            conn_local.close()


# Example Usage
async def main():
    test_assignee = "Apple Inc."
    conn = get_db_connection()
    try:
        from .. import db
        db.create_schema(conn) # Ensure schema exists
        await ingest_uspto_patents(test_assignee, limit=10, con=conn)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # API Key check might be needed depending on the final API used
    # if not API_KEY:
    #     print("USPTO_API_KEY might be required. Please check configuration.")
    asyncio.run(main())
