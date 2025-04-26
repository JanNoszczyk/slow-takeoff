import asyncio
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed
from typing import List, Dict, Any
from datetime import datetime, date

from wa.config import settings
from wa.db import get_db_connection

# Base URL for FRED API
FRED_BASE_URL = "https://api.stlouisfed.org/fred"

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
async def fetch_fred_data(endpoint: str, params: Dict[str, Any] = None) -> Any:
    """Fetches data from a specific FRED API endpoint."""
    if not settings.FRED_API_KEY:
        logger.warning("FRED_API_KEY not set. Skipping FRED fetch.")
        return None

    base_params = {
        "api_key": settings.FRED_API_KEY,
        "file_type": "json", # Request JSON format
    }
    if params:
        base_params.update(params)

    url = f"{FRED_BASE_URL}/{endpoint}"
    async with httpx.AsyncClient(timeout=60.0) as client: # Longer timeout for potentially large series data
        try:
            logger.info(f"Fetching data from FRED endpoint: {endpoint} with params: {params}")
            response = await client.get(url, params=base_params)
            response.raise_for_status()
            data = response.json()
            # FRED API might return error messages within JSON, check common patterns
            if "error_code" in data and data["error_code"] != 0:
                 logger.error(f"FRED API error: Code {data.get('error_code')} - {data.get('error_message', 'Unknown FRED Error')}")
                 return None # Indicate error

            logger.success(f"Successfully fetched data from FRED endpoint {endpoint}")
            return data
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching {url}: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error fetching data from {endpoint}: {e}")
            raise

async def store_raw_fred_data(conn, series_id: str, endpoint_type: str, data: Any):
    """Stores the raw FRED data."""
    if data:
        # Create a unique ID based on series and endpoint type (e.g., 'series' or 'observations')
        raw_id = f"fred_{endpoint_type}_{series_id}"
        logger.debug(f"Storing raw FRED {endpoint_type} data for {series_id}")
        await conn.execute("""
            INSERT INTO raw_fred (id, fetched_at, payload)
            VALUES ($1, CURRENT_TIMESTAMP, $2::JSON)
            ON CONFLICT (id) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                payload = excluded.payload;
        """, raw_id, str(data)) # Pass data as string for JSON conversion
        logger.success(f"Stored raw FRED {endpoint_type} data for {series_id}")

async def update_macro_series_metadata(conn, series_id: str):
    """Fetches and stores/updates metadata for a FRED series."""
    logger.debug(f"Fetching metadata for FRED series: {series_id}")
    params = {"series_id": series_id}
    data = await fetch_fred_data("series", params=params)

    if not data or "seriess" not in data or not data["seriess"]:
        logger.warning(f"No metadata found or error fetching metadata for FRED series: {series_id}")
        return False

    await store_raw_fred_data(conn, series_id, "series", data)

    series_info = data["seriess"][0] # Assume first result is the correct one
    try:
        name = series_info.get("title")
        frequency = series_info.get("frequency")
        units = series_info.get("units")
        source = "fred" # Hardcode source

        if not name:
            logger.error(f"Could not extract series title for {series_id} from metadata: {series_info}")
            return False

        logger.info(f"Updating metadata for {series_id}: Name='{name}', Freq='{frequency}', Units='{units}'")
        await conn.execute("""
            INSERT INTO macro_series (series_id, name, frequency, units, source)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (series_id) DO UPDATE SET
                name = excluded.name,
                frequency = excluded.frequency,
                units = excluded.units,
                source = excluded.source;
        """, series_id, name, frequency, units, source)
        logger.success(f"Successfully updated metadata for FRED series: {series_id}")
        return True
    except Exception as e:
        logger.error(f"Error parsing/storing FRED series metadata for {series_id}: {e}\nRaw info: {series_info}")
        return False

async def ingest_fred_series_observations(conn, series_id: str, start_date: str = None, end_date: str = None):
    """Fetches and stores observations for a given FRED series ID."""
    logger.info(f"Ingesting observations for FRED series: {series_id}")

    # First, ensure metadata exists
    if not await update_macro_series_metadata(conn, series_id):
        logger.error(f"Cannot ingest observations for {series_id} as metadata update failed.")
        return False

    # Fetch observations
    params = {"series_id": series_id}
    if start_date:
        params["observation_start"] = start_date
    if end_date:
        params["observation_end"] = end_date

    logger.debug(f"Fetching observations for {series_id} with params: {params}")
    data = await fetch_fred_data("series/observations", params=params)

    if not data or "observations" not in data:
        logger.warning(f"No observations data found or error fetching for FRED series: {series_id}")
        return False

    await store_raw_fred_data(conn, series_id, "observations", data)

    observations = data["observations"]
    logger.info(f"Received {len(observations)} observations for {series_id}. Processing...")

    rows_to_insert = []
    for obs in observations:
        try:
            # FRED uses '.' for missing values, need to handle this
            value_str = obs.get("value")
            if value_str is None or value_str == ".":
                continue # Skip missing values

            obs_date = date.fromisoformat(obs.get("date"))
            value = float(value_str)
            rows_to_insert.append((series_id, obs_date, value))

        except Exception as e:
            logger.warning(f"Skipping observation due to parsing error for {series_id} on date {obs.get('date')}: {e}. Raw obs: {obs}")
            continue

    if not rows_to_insert:
        logger.warning(f"No valid observations processed for {series_id}.")
        return True # Not necessarily an error if series has no recent data

    try:
        # Use executemany for potentially faster bulk inserts
        await conn.executemany("""
            INSERT INTO macro_data (series_id, date, value, fetched_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (series_id, date) DO UPDATE SET
                value = excluded.value,
                fetched_at = excluded.fetched_at;
        """, rows_to_insert)
        logger.success(f"Successfully inserted/updated {len(rows_to_insert)} observations for FRED series: {series_id}")
        return True
    except Exception as e:
        logger.error(f"Database error inserting observations for {series_id}: {e}")
        return False

async def ingest_fred_series(series_ids: List[str], start_date: str = None, end_date: str = None):
    """Ingests metadata and observations for a list of FRED series IDs."""
    logger.info(f"Starting FRED series ingestion for IDs: {series_ids}")
    conn = None
    try:
        conn = await get_db_connection()
        results = {}
        for series_id in series_ids:
            # Add a small delay between series to be nice to the API
            await asyncio.sleep(0.5)
            success = await ingest_fred_series_observations(conn, series_id, start_date, end_date)
            results[series_id] = success

        # Log summary
        successful_ids = [sid for sid, ok in results.items() if ok]
        failed_ids = [sid for sid, ok in results.items() if not ok]
        if successful_ids:
            logger.success(f"Successfully ingested FRED data for: {', '.join(successful_ids)}")
        if failed_ids:
            logger.error(f"Failed to ingest FRED data for: {', '.join(failed_ids)}")

    except Exception as e:
        logger.error(f"General error during FRED series ingestion: {e}")
    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed for FRED ingest.")

# Example usage (optional):
# if __name__ == "__main__":
#     async def main():
#         test_series = ["DGS10", "GDP", "CPIAUCSL", "UNRATE"] # 10-Yr Treasury, GDP, CPI, Unemployment Rate
#         # Fetch data from start of 2023
#         await ingest_fred_series(test_series, start_date="2023-01-01")
#     asyncio.run(main())

```

I'll wait for confirmation that `wealtharc-turbo-er/wa/ingest/fred.py` was created successfully. Then, I will update the Streamlit app.
