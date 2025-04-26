import httpx
import json
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import duckdb

from wa import config, db

# URL for the OFAC SDN list in JSON format
OFAC_SDN_JSON_URL = "https://www.treasury.gov/ofac/downloads/sdn.json" # Check if this URL is current

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(httpx.RequestError), # Retry only on network errors for downloads
    reraise=True
)
async def download_ofac_sdn_list(client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
    """
    Downloads the latest OFAC SDN list JSON file.

    Args:
        client: An httpx.AsyncClient instance.

    Returns:
        The parsed JSON data as a dictionary, or None if failed.
    """
    logger.info(f"Attempting to download OFAC SDN list from: {OFAC_SDN_JSON_URL}")
    headers = {'User-Agent': config.DEFAULT_USER_AGENT} # Be polite

    try:
        # Use a longer timeout for potentially large file downloads
        timeout = httpx.Timeout(60.0, connect=15.0)
        response = await client.get(OFAC_SDN_JSON_URL, headers=headers, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        sdn_data = response.json()
        logger.info(f"Successfully downloaded and parsed OFAC SDN JSON. Published Date: {sdn_data.get('publishDate')}")
        return sdn_data

    except httpx.HTTPStatusError as e:
        logger.error(f"Failed to download OFAC SDN list, status {e.response.status_code}: {e.response.text}")
        # Don't retry on 4xx/5xx errors for file download unless specifically needed
        return None
    except httpx.RequestError as e:
        logger.error(f"Network error downloading OFAC SDN list: {e}")
        raise # Let tenacity handle retries
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode OFAC SDN JSON: {e}. Content snippet: {response.text[:500]}")
        return None # Don't retry on decode error
    except Exception as e:
        logger.error(f"Unexpected error downloading OFAC SDN list: {e}")
        return None


def store_raw_ofac_sdn_entries(sdn_list_data: Dict[str, Any], con: duckdb.DuckDBPyConnection):
    """Stores individual SDN entries in the raw_ofac_sdn table."""
    entries = sdn_list_data.get('sdnEntries', [])
    if not entries:
        logger.warning("No 'sdnEntries' found in the downloaded OFAC data.")
        return 0

    now_ts = datetime.now(timezone.utc)
    insert_sql = """
        INSERT INTO raw_ofac_sdn (id, fetched_at, payload)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            fetched_at = excluded.fetched_at,
            payload = excluded.payload;
    """
    data_to_insert = []
    for entry in entries:
        uid = entry.get('uid')
        if uid:
            # Use UID as the primary key for the raw table
            raw_id = f"ofac_{uid}"
            data_to_insert.append((raw_id, now_ts, json.dumps(entry)))
        else:
            logger.warning(f"Found SDN entry without a UID: {entry.get('lastName', entry.get('sdnType', 'Unknown Type'))}")

    if data_to_insert:
        try:
            con.executemany(insert_sql, data_to_insert)
            logger.info(f"Stored {len(data_to_insert)} raw OFAC SDN entries.")
            return len(data_to_insert)
        except Exception as e:
            logger.error(f"Failed to store raw OFAC SDN data: {e}")
            return 0
    return 0


def store_clean_ofac_sdn_entities(sdn_list_data: Dict[str, Any], con: duckdb.DuckDBPyConnection):
    """Parses and stores relevant SDN entity details in the sdn_entities table."""
    entries = sdn_list_data.get('sdnEntries', [])
    if not entries:
        logger.warning("No 'sdnEntries' found in the downloaded OFAC data for clean storage.")
        return 0

    now_ts = datetime.now(timezone.utc)
    insert_sql = """
        INSERT INTO sdn_entities (
            sdn_uid, name, sdn_type, program, title, call_sign, vess_type,
            tonnage, grt, vess_flag, vess_owner, remarks, raw_entry, fetched_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (sdn_uid) DO UPDATE SET
            name = excluded.name,
            sdn_type = excluded.sdn_type,
            program = excluded.program,
            title = excluded.title,
            call_sign = excluded.call_sign,
            vess_type = excluded.vess_type,
            tonnage = excluded.tonnage,
            grt = excluded.grt,
            vess_flag = excluded.vess_flag,
            vess_owner = excluded.vess_owner,
            remarks = excluded.remarks,
            raw_entry = excluded.raw_entry,
            fetched_at = excluded.fetched_at;
    """
    data_to_insert = []
    processed_count = 0
    for entry in entries:
        uid = entry.get('uid')
        if not uid:
            continue # Skip entries without UID

        # Combine first/last name or use primary name
        first_name = entry.get('firstName', '')
        last_name = entry.get('lastName', '')
        if first_name and last_name:
            name = f"{last_name}, {first_name}".strip()
        elif last_name:
            name = last_name
        else:
             # Look for other potential name fields if lastName is missing (e.g., for Entities)
             # This needs inspection of the actual JSON structure for non-individual types
             name = last_name # Fallback to potentially empty lastName

        if not name:
             logger.warning(f"SDN entry UID {uid} has no discernible name. Using UID as name.")
             name = f"Unknown SDN {uid}"


        # Extract programs (can be a list)
        programs = entry.get('programs', [])
        program_str = ", ".join(programs) if isinstance(programs, list) else programs if isinstance(programs, str) else None


        data_to_insert.append((
            uid,
            name,
            entry.get('sdnType'),
            program_str,
            entry.get('title'),
            entry.get('callSign'),
            entry.get('vesselType'),
            entry.get('tonnage'),
            entry.get('grossRegisteredTonnage'),
            entry.get('vesselFlag'),
            entry.get('vesselOwner'),
            entry.get('remarks'),
            json.dumps(entry), # Store the full original entry as JSON
            now_ts
        ))
        processed_count += 1

    if data_to_insert:
        try:
            con.executemany(insert_sql, data_to_insert)
            logger.info(f"Stored/Updated {processed_count} clean OFAC SDN entities.")
            return processed_count
        except Exception as e:
            logger.error(f"Failed to store clean OFAC SDN entities: {e}")
            return 0
    return 0


async def ingest_ofac_sdn_list(con: duckdb.DuckDBPyConnection = None):
    """
    High-level function to download the OFAC SDN list, store raw entries,
    and store parsed entities.

    Args:
        con: Optional DuckDB connection.
    """
    close_conn_locally = False
    if con is None:
        con = db.get_db_connection()
        close_conn_locally = True

    start_time = time.time()
    total_raw_stored = 0
    total_clean_stored = 0

    try:
        async with httpx.AsyncClient() as client:
            sdn_data = await download_ofac_sdn_list(client)

            if sdn_data:
                # Store raw data
                total_raw_stored = store_raw_ofac_sdn_entries(sdn_data, con)

                # Store clean data
                if total_raw_stored > 0:
                    total_clean_stored = store_clean_ofac_sdn_entities(sdn_data, con)
            else:
                logger.error("Failed to download or parse OFAC SDN list. Ingestion aborted.")

    except Exception as e:
        logger.error(f"An unexpected error occurred during OFAC SDN ingestion: {e}")
    finally:
        end_time = time.time()
        logger.info(f"OFAC SDN ingestion finished in {end_time - start_time:.2f}s. Stored {total_raw_stored} raw entries, {total_clean_stored} clean entities.")
        if close_conn_locally:
            db.close_db_connection()


if __name__ == "__main__":
    # Example usage: Download and ingest the list
    import asyncio

    # Make sure the DB schema exists first
    try:
        conn = db.get_db_connection()
        db.create_schema(conn)
        asyncio.run(ingest_ofac_sdn_list(con=conn))
    except Exception as e:
        logger.error(f"Main execution error: {e}")
    finally:
        db.close_db_connection()
