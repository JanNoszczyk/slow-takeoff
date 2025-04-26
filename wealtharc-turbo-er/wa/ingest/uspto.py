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
USPTO_PPUBS_API_URL = "https://ppubs.uspto.gov/api/v1/search/results"

# Define table names
RAW_USPTO_TABLE = "raw_uspto" # For raw JSON payload
# USPTO_PATENTS_TABLE = "uspto_patents" # Now imported

# --- API Client Setup ---

async def make_uspto_ppubs_search_request(query_payload: dict) -> dict | None:
    """Makes a POST request to the USPTO PPUBS Search API."""
    url = USPTO_PPUBS_API_URL
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    async with httpx.AsyncClient() as client:
        try:
            logger.debug(f"Making USPTO PPUBS search request to {url} with payload: {json.dumps(query_payload)}")
            response = await client.post(url, json=query_payload, headers=headers, timeout=120.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error searching USPTO PPUBS {url}: {e.response.status_code} - {e.request.url} - Response: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error searching USPTO PPUBS {url}: {e}")
            return None

# --- API Fetching Functions ---

@retry(stop=stop_after_attempt(3), wait=wait_fixed(5))
async def search_uspto_patents(assignee_name: str, limit: int = 20) -> list[dict]:
    """Searches USPTO patents by assignee name using the PPUBS API."""
    logger.info(f"Searching USPTO PPUBS for assignee: '{assignee_name}', limit: {limit}")
    query_payload = {
        "query": {
            "querySyntax": "proximity", "operator": "AND",
            "searchFields": [{"field": "assigneeName", "values": [assignee_name]}]
        },
        "start": 0, "rows": limit, "sort": "publicationDate desc"
    }
    data = await make_uspto_ppubs_search_request(query_payload)

    if data and 'results' in data and 'patents' in data['results']:
        raw_patents = data['results']['patents']
        logger.success(f"Found {len(raw_patents)} patents for {assignee_name} via PPUBS API.")
        processed_patents = []
        for p in raw_patents:
            patent_details = p.get('patent', {})
            application_details = p.get('patentApplication', {})
            processed_patents.append({
                "patentNumber": patent_details.get('patentNumber', application_details.get('patentNumber')),
                "patentTitle": patent_details.get('inventionTitle', {}).get('content', [''])[0],
                "filingDate": application_details.get('filingDate'),
                "grantDate": patent_details.get('grantDate'),
                "assigneeEntityName": patent_details.get('assigneeEntityName', {}).get('content', [assignee_name])[0],
                "abstract": patent_details.get('abstractText', {}).get('content', [''])[0],
            })
        return processed_patents
    elif data and 'results' in data and not data['results'].get('patents'):
         logger.info(f"No patents found for assignee '{assignee_name}' via PPUBS API.")
         return []
    else:
        logger.warning(f"Failed to retrieve or parse patent data for assignee '{assignee_name}' from PPUBS API.")
        return []

# --- Database Storage Functions ---

async def store_uspto_patent_data(patents: list[dict], db_path: str | None = None):
    """Stores cleaned USPTO patent metadata."""
    if not patents: return
    logger.info(f"Storing metadata for {len(patents)} USPTO patents...")
    fetched_at = datetime.now(timezone.utc)
    records_to_insert = []
    for patent in patents:
        filing_date = pd.to_datetime(patent.get('filingDate'), errors='coerce').date()
        grant_date = pd.to_datetime(patent.get('grantDate'), errors='coerce').date()
        record = (
            patent.get('patentNumber'), patent.get('patentTitle'), patent.get('assigneeEntityName'),
            filing_date, grant_date, fetched_at, patent.get('abstract')
        )
        # Basic validation
        if record[0]:
            records_to_insert.append(record)
        else:
            logger.warning(f"Skipping USPTO record due to missing patent number: {patent}")

    if not records_to_insert:
        logger.info("No valid USPTO records to store.")
        return

    try:
        def db_operations_in_thread(path: str | None, data: list):
            conn = None
            try:
                conn = get_db_connection(path)
                conn.executemany(
                    f"""
                    INSERT INTO {USPTO_PATENTS_TABLE} (
                        patent_number, title, assignee, filing_date, grant_date, fetched_at, abstract
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(patent_number) DO UPDATE SET
                        title=excluded.title, assignee=excluded.assignee, filing_date=excluded.filing_date,
                        grant_date=excluded.grant_date, fetched_at=excluded.fetched_at, abstract=excluded.abstract;
                    """, data
                )
                logger.success(f"Thread successfully stored/updated metadata for {len(data)} USPTO patents.")
            except Exception as thread_e:
                logger.error(f"Error in thread storing USPTO patent metadata: {thread_e}")
                raise
            finally:
                if conn: conn.close(); logger.debug("Thread closed USPTO patent data DB connection.")

        await asyncio.to_thread(db_operations_in_thread, db_path, records_to_insert)

    except Exception as e:
        logger.error(f"Error storing USPTO patent metadata: {e}"); raise


# --- Main Ingestion Function ---

async def ingest_uspto_patents(assignee_name: str, limit: int = 20, db_path: str | None = None):
    """Searches for and stores USPTO patent metadata for an assignee."""
    logger.info(f"Starting USPTO patent ingestion for assignee: {assignee_name}")
    try:
        patents_data = await search_uspto_patents(assignee_name, limit=limit)
        if patents_data:
             try:
                 await store_uspto_patent_data(patents_data, db_path=db_path)
             except Exception as store_e:
                  logger.error(f"Failed to store USPTO patent data: {store_e}", exc_info=True)
        else:
            logger.info(f"No patents found or processed for assignee '{assignee_name}'.")
    except Exception as e:
        logger.exception(f"Error during USPTO ingestion pipeline for {assignee_name}: {e}")
        raise # Re-raise


# Example Usage
async def main():
    test_assignee = "Apple Inc."
    test_db_path = "test_uspto.db"
    conn = None
    try:
        conn = get_db_connection(test_db_path)
        from .. import db
        db.create_schema(conn); conn.close(); conn = None
        await ingest_uspto_patents(test_assignee, limit=10, db_path=test_db_path)
    except Exception as e: logger.exception(f"USPTO example failed: {e}")
    finally:
        if conn: conn.close()
        import os
        if os.path.exists(test_db_path): os.remove(test_db_path); logger.info(f"Cleaned up {test_db_path}")

if __name__ == "__main__":
    asyncio.run(main())
