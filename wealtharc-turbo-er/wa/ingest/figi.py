import asyncio
import httpx
import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from wa import config, db

OPENFIGI_API_V3_URL = "https://api.openfigi.com/v3/mapping"
# OpenFIGI V3 has rate limits (check their documentation - often per IP)
# Example: 25 requests/5 seconds for unauthenticated, higher with API key
MAX_JOBS_PER_REQUEST = 100 # OpenFIGI V3 limit

async def map_identifiers(identifiers: List[Dict[str, str]], client: httpx.AsyncClient) -> Optional[List[Dict[str, Any]]]:
    """
    Sends a batch of mapping jobs to the OpenFIGI V3 API.

    Args:
        identifiers: A list of dictionaries, each representing a mapping job.
                     Example: [{'idType': 'ID_ISIN', 'idValue': 'US0378331005'}]
        client: An httpx.AsyncClient instance.

    Returns:
        A list of results from the API, or None if the request failed.
    """
    if not identifiers:
        return []

    headers = {'Content-Type': 'application/json'}
    if config.OPENFIGI_API_KEY:
        headers['X-OPENFIGI-APIKEY'] = config.OPENFIGI_API_KEY
        logger.debug("Using OpenFIGI API key.")
    else:
        logger.warning("OPENFIGI_API_KEY not set. Using unauthenticated rate limits.")

    try:
        response = await client.post(
            OPENFIGI_API_V3_URL,
            json=identifiers,
            headers=headers,
            timeout=config.HTTPX_TIMEOUT
        )
        response.raise_for_status() # Raise an exception for 4xx or 5xx status codes
        results = response.json()
        logger.debug(f"OpenFIGI API response received for {len(identifiers)} items.")
        return results
    except httpx.HTTPStatusError as e:
        logger.error(f"OpenFIGI API request failed with status {e.response.status_code}: {e.response.text}")
        # Specific handling for rate limits (429 Too Many Requests) might be needed if not using tenacity
        if e.response.status_code == 429:
            logger.warning("OpenFIGI rate limit likely exceeded. Consider adding delays.")
        return None
    except httpx.RequestError as e:
        logger.error(f"Network error contacting OpenFIGI API: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode OpenFIGI API JSON response: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during OpenFIGI request: {e}")
        return None

def store_raw_figi_data(results: List[Dict[str, Any]], con: duckdb.DuckDBPyConnection):
    """Stores the raw mapping results in the raw_figi table."""
    if not results:
        return 0

    now_ts = datetime.now(timezone.utc)
    insert_sql = """
        INSERT INTO raw_figi (id, fetched_at, payload)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            fetched_at = excluded.fetched_at,
            payload = excluded.payload;
    """
    data_to_insert = []
    processed_count = 0
    # The structure of the response is a list, potentially containing multiple results per input job
    # We need a way to uniquely identify each raw result payload for storage.
    # Using a combination of input ID value and result FIGI might work, or generate a hash.
    # For simplicity here, we'll just use the first FIGI found + timestamp as ID, which isn't robust.
    # A better approach might store the original request batch and link results.
    for entry in results: # Each entry corresponds to one input job
         if isinstance(entry, dict) and 'data' in entry and entry['data']:
            # Process each instrument found for the input job
            for instrument in entry['data']:
                figi = instrument.get('figi')
                if figi:
                    # Create a somewhat unique ID - IMPROVE THIS FOR PRODUCTION
                    raw_id = f"figi_{figi}_{now_ts.timestamp()}"
                    data_to_insert.append((raw_id, now_ts, json.dumps(instrument)))
                    processed_count += 1
         elif isinstance(entry, dict) and 'warning' in entry:
             logger.warning(f"OpenFIGI returned a warning for an item: {entry.get('warning')}")
         elif isinstance(entry, dict) and 'error' in entry:
             logger.error(f"OpenFIGI returned an error for an item: {entry.get('error')}")


    if data_to_insert:
        try:
            con.executemany(insert_sql, data_to_insert)
            logger.info(f"Stored {len(data_to_insert)} raw FIGI mapping results.")
            return len(data_to_insert)
        except Exception as e:
            logger.error(f"Failed to store raw FIGI data: {e}")
            return 0
    return 0

async def update_assets_with_figi(con: duckdb.DuckDBPyConnection):
    """
    Processes raw_figi data to update the assets table with FIGI and other identifiers.
    Simple example: assumes raw_figi payload contains instrument data with 'figi', 'ticker', etc.
    and tries to match based on 'exchCode' and 'securityType2'.
    """
    logger.info("Attempting to update assets table from raw_figi data...")
    # This logic needs refinement based on actual OpenFIGI response structure and desired matching rules.
    # Example: Update assets where ISIN matches, adding FIGI and Ticker if available
    # This query is complex because the payload is JSON.
    update_query = """
    WITH figi_data AS (
        SELECT
            json_extract_string(payload, '$.figi') as figi,
            json_extract_string(payload, '$.ticker') as ticker,
            json_extract_string(payload, '$.exchCode') as exchCode,
            json_extract_string(payload, '$.marketSector') as marketSector,
            json_extract_string(payload, '$.securityType2') as securityType,
            json_extract_string(payload, '$.name') as figi_name,
            -- Extract the originally queried ID if stored in payload or link via request ID
            -- For now, we assume we match back via other means (e.g., a separate lookup before insert)
            -- Let's assume we can somehow link raw_figi.id back to an ISIN/CUSIP searched for
            id as raw_id
        FROM raw_figi
        WHERE figi IS NOT NULL
    )
    UPDATE assets
    SET
        figi = COALESCE(assets.figi, fd.figi),
        ticker = COALESCE(assets.ticker, fd.ticker),
        exchange = COALESCE(assets.exchange, fd.exchCode),
        -- Potentially update name if figi_name seems better? Needs careful consideration.
        -- name = COALESCE(assets.name, fd.figi_name),
        updated_at = current_timestamp
    FROM figi_data fd
    WHERE
        -- THIS MATCHING LOGIC IS HIGHLY SIMPLISTIC AND NEEDS REFINEMENT
        -- It assumes we can magically link back or are updating based on existing ISIN/CUSIP
        -- Option 1: If assets table already has ISIN/CUSIP populated from elsewhere
        -- assets.isin = (SELECT original_isin FROM some_lookup WHERE raw_id = fd.raw_id) OR
        -- assets.cusip = (SELECT original_cusip FROM some_lookup WHERE raw_id = fd.raw_id)

        -- Option 2: If we ONLY add FIGI to existing rows matched by other means (less useful)
        assets.figi IS NULL AND fd.figi IS NOT NULL
        -- Add more sophisticated join conditions based on how you link requests to results
    ;
    """
    try:
        result = con.execute(update_query)
        # DuckDB execute doesn't directly return rows affected for UPDATE FROM
        # We'd need a SELECT COUNT(*) before/after or other method if exact count needed.
        logger.info(f"Ran update assets query based on raw_figi data.") # Result object is limited
    except Exception as e:
        logger.error(f"Failed to update assets table from raw_figi: {e}")


async def ingest_figi_mappings(identifiers_to_map: List[Dict[str, str]], con: duckdb.DuckDBPyConnection = None):
    """
    High-level function to fetch mappings for given identifiers, store raw data,
    and potentially update the assets table.

    Args:
        identifiers_to_map: List of dicts like {'idType': 'ID_ISIN', 'idValue': '...'}
        con: Optional DuckDB connection.
    """
    if not identifiers_to_map:
        logger.info("No identifiers provided for FIGI mapping.")
        return

    close_conn_locally = False
    if con is None:
        con = db.get_db_connection()
        close_conn_locally = True

    total_stored = 0
    processed_identifiers = 0
    start_time = time.time()

    try:
        async with httpx.AsyncClient() as client:
            # Process identifiers in batches
            for i in range(0, len(identifiers_to_map), MAX_JOBS_PER_REQUEST):
                batch = identifiers_to_map[i:i + MAX_JOBS_PER_REQUEST]
                logger.info(f"Processing FIGI mapping batch {i // MAX_JOBS_PER_REQUEST + 1} ({len(batch)} items)...")

                results = await map_identifiers(batch, client)

                if results:
                    stored_count = store_raw_figi_data(results, con)
                    total_stored += stored_count
                else:
                    logger.warning(f"Failed to get FIGI results for batch starting at index {i}.")

                processed_identifiers += len(batch)
                # Optional: Add delay between batches if hitting rate limits even with API key
                await asyncio.sleep(0.5) # Small delay

        if total_stored > 0:
             # Optionally trigger asset table update after storing raw data
             await update_assets_with_figi(con)

    except Exception as e:
        logger.error(f"An error occurred during FIGI ingestion: {e}")
    finally:
        end_time = time.time()
        logger.info(f"FIGI mapping ingestion finished for {processed_identifiers} identifiers in {end_time - start_time:.2f}s. Stored {total_stored} raw results.")
        if close_conn_locally:
            db.close_db_connection()


if __name__ == "__main__":
    # Example usage: Map some ISINs
    example_isins = [
        "US0378331005", # Apple
        "US5949181045", # Microsoft
        "US88160R1014", # Tesla
        "DE0007100000", # Siemens AG
        "FR0000120271", # LVMH
        "GB0002634946", # Diageo PLC
        "INVALIDISIN", # Example of an invalid one
    ]

    jobs = [{"idType": "ID_ISIN", "idValue": isin} for isin in example_isins]

    # Make sure the DB schema exists first
    try:
        conn = db.get_db_connection()
        db.create_schema(conn)
        asyncio.run(ingest_figi_mappings(jobs, con=conn))
    except Exception as e:
        logger.error(f"Main execution error: {e}")
    finally:
        db.close_db_connection()
