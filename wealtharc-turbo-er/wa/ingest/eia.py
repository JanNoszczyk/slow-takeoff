import asyncio
import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date, timezone
import pandas as pd

from wa.config import settings
from wa.db import get_db_connection

# Base URL for EIA API v2
EIA_BASE_URL = "https://api.eia.gov/v2"

@retry(stop=stop_after_attempt(3), wait=wait_fixed(3))
async def fetch_eia_data(series_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Fetches data for a specific series ID from the EIA API v2.

    Args:
        series_id: The EIA series ID (e.g., 'PET.W_EPC0_FPF_R10_MBBLD.W').
        start_date: Optional start date (YYYY-MM-DD).
        end_date: Optional end date (YYYY-MM-DD).

    Returns:
        The parsed JSON response containing series data, or None if an error occurs.
    """
    if not settings.EIA_API_KEY:
        logger.warning("EIA_API_KEY not set. Skipping EIA fetch.")
        return None

    # Construct the path part of the URL correctly for series ID
    # Example: /seriesid/PET.W_EPC0_FPF_R10_MBBLD.W
    url_path = f"/seriesid/{series_id}"
    url = f"{EIA_BASE_URL}{url_path}"

    params = {
        "api_key": settings.EIA_API_KEY,
        "out": "json" # Explicitly request JSON output
    }
    # EIA API v2 uses 'start' and 'end' facets for date range
    facets = {}
    if start_date:
        facets["start"] = start_date
    if end_date:
        facets["end"] = end_date

    # Data facets and frequency need to be specified for most series
    # These are placeholders, you might need specific 'frequency' and 'data[0]' for different series
    request_data = {
        "frequency": "weekly", # Common for petroleum, adjust as needed (e.g., 'monthly', 'annual')
        "data": ["value"],     # Request the 'value' column
        "facets": facets,      # Include start/end date facets if provided
        "sort": [{"column": "period", "direction": "desc"}] # Get latest data first
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            logger.info(f"Fetching data from EIA: {url} with data payload: {request_data}")
            # EIA API v2 often uses GET with parameters encoded in URL for simple calls,
            # but might need different method/payload for complex queries.
            # Sticking to GET with params for series ID endpoint.
            # The documentation implies params for filtering, sorting, etc.

            # Update params with data request specifics, encoded for URL
            params["frequency"] = request_data["frequency"]
            params["data[0]"] = request_data["data"][0] # Adjust index if requesting multiple data columns
            if "start" in request_data["facets"]:
                params["start"] = request_data["facets"]["start"]
            if "end" in request_data["facets"]:
                params["end"] = request_data["facets"]["end"]
            params["sort[0][column]"] = request_data["sort"][0]["column"]
            params["sort[0][direction]"] = request_data["sort"][0]["direction"]


            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Check for API errors within the response structure
            if 'response' not in data or 'data' not in data['response']:
                 # Sometimes errors are at the top level
                 if data.get('error'):
                     logger.error(f"EIA API Error: {data['error']}")
                     return None
                 # Or within a 'request' block but without 'response'
                 if 'request' in data and 'error' in data['request']:
                      logger.error(f"EIA API Request Error: {data['request']['error']}")
                      return None
                 logger.error(f"Unexpected EIA API response structure for {series_id}. Missing 'response' or 'response.data'. Response: {str(data)[:500]}...")
                 return None

            logger.success(f"Successfully fetched data from EIA for series: {series_id}")
            return data

        except httpx.HTTPStatusError as e:
            error_details = e.response.text
            try:
                 # Try to parse JSON error if possible
                 error_json = e.response.json()
                 error_details = error_json.get("error", error_details)
            except Exception:
                 pass # Ignore if not JSON
            logger.error(f"HTTP error fetching {url}: {e.response.status_code} - {error_details}")
            raise
        except Exception as e:
            logger.error(f"Error fetching data from {url}: {e}")
            raise

async def store_raw_eia_data(conn, series_id: str, data: Any):
    """Stores the raw EIA API response."""
    if data:
        raw_id = f"eia_{series_id}" # Simple ID based on series
        logger.debug(f"Storing raw EIA data for {series_id}")
        await conn.execute("""
            INSERT INTO raw_eia (id, fetched_at, payload)
            VALUES ($1, CURRENT_TIMESTAMP, $2::JSON)
            ON CONFLICT (id) DO UPDATE SET
                fetched_at = excluded.fetched_at,
                payload = excluded.payload;
        """, raw_id, str(data)) # Pass data as string for JSON conversion
        logger.success(f"Stored raw EIA data for {series_id}")

def parse_eia_data(series_id: str, raw_data: Dict[str, Any]) -> Optional[Tuple[Dict[str, Any], pd.DataFrame]]:
    """
    Parses the EIA API v2 response to extract metadata and observations.

    Returns:
        A tuple (metadata, observations_df), or None if parsing fails.
    """
    try:
        response_data = raw_data.get("response", {})
        series_info_list = response_data.get("data", [])
        if not series_info_list:
            logger.warning(f"No 'data' array found in EIA response for {series_id}.")
            return None

        # --- Extract Metadata ---
        # Metadata might be in the response top level or description fields
        metadata = {
            "series_id": series_id,
            "name": response_data.get("description", series_id), # Use description or fallback
            "units": None,
            "frequency": None,
            # Add more fields if available in response
        }
        # Try to extract from the first data point's metadata if available
        if series_info_list:
             first_point = series_info_list[0]
             metadata["units"] = first_point.get("unit", first_point.get("units"))
             metadata["frequency"] = first_point.get("frequency", response_data.get("frequency"))
             # Use more specific name if available
             if first_point.get("seriesDescription"):
                  metadata["name"] = first_point.get("seriesDescription")
             elif first_point.get("series-description"): # Handle potential variations
                 metadata["name"] = first_point.get("series-description")


        logger.debug(f"Extracted EIA metadata for {series_id}: {metadata}")

        # --- Extract Observations ---
        observations = []
        for point in series_info_list:
            try:
                # Period format varies (YYYY, YYYY-MM, YYYY-MM-DD, YYYY-Qx, etc.)
                period_str = point.get("period")
                value = point.get("value") # EIA uses 'value' generally

                if period_str is None or value is None:
                    continue # Skip points missing essential info

                # Attempt to parse period string into a date (use end of period)
                obs_date: Optional[date] = None
                if len(period_str) == 4: # Annual YYYY
                    obs_date = date(int(period_str), 12, 31)
                elif len(period_str) == 7 and '-' in period_str: # Monthly YYYY-MM
                    year, month = map(int, period_str.split('-'))
                    # Get last day of month
                    next_month = date(year, month, 1).replace(day=28) + pd.Timedelta(days=4)
                    obs_date = next_month - pd.Timedelta(days=next_month.day)
                elif len(period_str) == 10 and period_str.count('-') == 2: # Daily YYYY-MM-DD
                    obs_date = date.fromisoformat(period_str)
                elif 'Q' in period_str and len(period_str) == 6: # Quarterly YYYY-Qx
                     year, quarter_str = period_str.split('-Q')
                     quarter_end_month = int(quarter_str) * 3
                     next_month_start = date(int(year), quarter_end_month, 1).replace(day=28) + pd.Timedelta(days=4)
                     obs_date = next_month_start - pd.Timedelta(days=next_month_start.day)
                # Add weekly handling if needed ('W' format?) - EIA format varies

                if obs_date:
                    observations.append({"date": obs_date, "value": float(value)})
                else:
                    logger.warning(f"Could not parse EIA period '{period_str}' for {series_id}. Skipping point.")

            except (ValueError, TypeError) as e:
                logger.warning(f"Skipping EIA observation due to parsing error: {e}. Raw point: {point}")
                continue

        if not observations:
            logger.warning(f"No valid observations parsed for EIA series {series_id}.")
            # Return metadata even if observations are empty
            return metadata, pd.DataFrame(columns=['date', 'value'])

        observations_df = pd.DataFrame(observations).sort_values(by="date").reset_index(drop=True)
        logger.success(f"Parsed {len(observations_df)} observations for EIA series {series_id}.")
        return metadata, observations_df

    except Exception as e:
        logger.error(f"Failed to parse EIA API response structure for {series_id}: {e}")
        return None


async def ingest_eia_series(conn, series_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Fetches, parses, and stores data for a specific EIA series ID."""
    logger.info(f"Ingesting EIA series: {series_id}")

    raw_data = await fetch_eia_data(series_id, start_date, end_date)
    if not raw_data:
        logger.error(f"Failed to fetch data for EIA series: {series_id}")
        return False

    await store_raw_eia_data(conn, series_id, raw_data)

    parsed_result = parse_eia_data(series_id, raw_data)
    if not parsed_result:
        logger.error(f"Failed to parse data for EIA series: {series_id}")
        return False

    metadata, observations_df = parsed_result

    # --- Store Metadata in macro_series ---
    try:
        name = metadata.get("name", series_id)
        frequency = metadata.get("frequency") # Already parsed to Daily, Weekly, etc. if possible
        units = metadata.get("units")
        source = "eia"

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
        logger.success(f"Successfully updated metadata for EIA series: {series_id}")
    except Exception as e:
        logger.error(f"Error storing EIA series metadata for {series_id}: {e}\nMetadata: {metadata}")
        # Continue to store observations?

    # --- Store Observations in macro_data ---
    if observations_df.empty:
        logger.warning(f"No valid observations to store for EIA series: {series_id}")
        return True # Not an error if no data points

    rows_to_insert = [
        (series_id, row['date'], row['value'])
        for _, row in observations_df.iterrows() if pd.notna(row['value'])
    ]

    if not rows_to_insert:
        logger.warning(f"No valid (non-null) observations to insert for {series_id}.")
        return True

    try:
        await conn.executemany("""
            INSERT INTO macro_data (series_id, date, value, fetched_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (series_id, date) DO UPDATE SET
                value = excluded.value,
                fetched_at = excluded.fetched_at;
        """, rows_to_insert)
        logger.success(f"Successfully inserted/updated {len(rows_to_insert)} observations for EIA series: {series_id}")
        return True
    except Exception as e:
        logger.error(f"Database error inserting EIA observations for {series_id}: {e}")
        return False

async def run_eia_ingestion(series_ids: List[str], start_date: Optional[str] = None, end_date: Optional[str] = None):
    """Ingests data for a list of EIA series IDs."""
    logger.info(f"Starting EIA ingestion for {len(series_ids)} series...")
    conn = None
    try:
        conn = await get_db_connection()
        results = {}
        for i, series_id in enumerate(series_ids):
            logger.info(f"Processing EIA series {i+1}/{len(series_ids)}: {series_id}")
            # Add delay between requests
            await asyncio.sleep(1)
            success = await ingest_eia_series(conn, series_id, start_date, end_date)
            results[series_id] = success

        # Log summary
        successful_ids = [sid for sid, ok in results.items() if ok]
        failed_ids = [sid for sid, ok in results.items() if not ok]
        if successful_ids:
            logger.success(f"Successfully ingested EIA data for: {', '.join(successful_ids)}")
        if failed_ids:
            logger.error(f"Failed to ingest EIA data for: {', '.join(failed_ids)}")

    except Exception as e:
        logger.error(f"General error during EIA ingestion: {e}")
    finally:
        if conn:
            await conn.close()
            logger.info("Database connection closed for EIA ingest.")

# Example usage (optional):
# if __name__ == "__main__":
#     async def main():
#         # Example: Weekly US Ending Stocks of Crude Oil (Thousand Barrels)
#         # Example: Henry Hub Natural Gas Spot Price (Dollars per Million Btu) - Daily needs freq='daily' adjustment
#         # Example: US Regular Conventional Retail Gasoline Prices (Dollars per Gallon) - Weekly
#         test_series = [
#             "PET.WCRSTUS1.W",
#             "NG.RNGWHHD.D", # Daily - Adjust fetch/parse logic frequency
#             "PET.EMM_EPM0_PTE_NUS_DPG.W"
#         ]
#         # Need to handle different frequencies potentially
#         await run_eia_ingestion(test_series, start_date="2023-01-01")
#     asyncio.run(main())

```

I'll wait for confirmation that `wealtharc-turbo-er/wa/ingest/eia.py` was created successfully. Then, I'll update the Streamlit app.
